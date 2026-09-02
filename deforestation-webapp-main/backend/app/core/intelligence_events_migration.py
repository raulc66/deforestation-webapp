"""WP8 — intelligence events canonical migration and index alignment.

Idempotent startup migrations bringing persisted ``intelligence_events`` in line
with the WP1–WP3 canonical model ``(incident_category, spatial_key)``.

Category backfill (WP8.1)
-------------------------
* Preserves valid existing ``incident_category`` values.
* Backfills absent categories via :func:`resolve_incident_category` (legacy
  anomaly → wildfire).
* Marks explicit non-taxonomy values as *invalid* (no silent overwrite).
* Marks conflicting metadata signals as *ambiguous*.

Canonical re-key (WP8.2)
------------------------
* Persists ``spatial_key`` from ``region`` when absent (Phase 0 mapping).
* Syncs ``region`` from ``spatial_key`` when region absent.
* Detects active-event identity collisions on
  ``(incident_category, spatial_key)``.
* Resolves collisions deterministically: highest ``detection_count``, then latest
  ``last_detected_at``, then earliest ``_id`` wins; losers are *resolved* (not
  deleted) preserving their lifecycle history fields until resolution.

Index alignment (WP8.3)
-----------------------
* Retains legacy ``(event_type, region, status)`` index.
* Adds canonical ``(incident_category, spatial_key, status)`` index.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import OperationFailure

from app.core.ecosystem.canonical_identity import (
    region_from_spatial_key,
    spatial_key_from_region,
)
from app.core.ecosystem.incident_categories import (
    INCIDENT_CATEGORIES,
    map_forest_event_type_to_incident,
    normalize_incident_category,
    resolve_incident_category,
)
from app.core.ecosystem.intelligence_event_defaults import DERIVED_ANOMALY_EVENT_TYPE
from app.modules.analytics.reconciliation import identity_key_from_event

logger = logging.getLogger("forestwatch.migrations")

COLLECTION = "intelligence_events"

LEGACY_DEDUP_INDEX = [("event_type", 1), ("region", 1), ("status", 1)]
CANONICAL_IDENTITY_INDEX = [("incident_category", 1), ("spatial_key", 1), ("status", 1)]
LAST_DETECTED_INDEX = "last_detected_at"


@dataclass
class CategoryBackfillReport:
    scanned: int = 0
    already_canonical: int = 0
    backfilled: int = 0
    ambiguous: int = 0
    invalid: int = 0
    skipped: int = 0
    failed: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "scanned": self.scanned,
            "already_canonical": self.already_canonical,
            "backfilled": self.backfilled,
            "ambiguous": self.ambiguous,
            "invalid": self.invalid,
            "skipped": self.skipped,
            "failed": self.failed,
        }


@dataclass
class RekeyReport:
    scanned: int = 0
    already_canonical: int = 0
    rekeyed: int = 0
    ambiguous: int = 0
    invalid: int = 0
    skipped: int = 0
    failed: int = 0
    collisions_detected: int = 0
    collisions_resolved: int = 0
    collision_event_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "already_canonical": self.already_canonical,
            "rekeyed": self.rekeyed,
            "ambiguous": self.ambiguous,
            "invalid": self.invalid,
            "skipped": self.skipped,
            "failed": self.failed,
            "collisions_detected": self.collisions_detected,
            "collisions_resolved": self.collisions_resolved,
            "collision_event_ids": list(self.collision_event_ids),
        }


@dataclass
class IntelligenceEventsMigrationReport:
    category: CategoryBackfillReport = field(default_factory=CategoryBackfillReport)
    rekey: RekeyReport = field(default_factory=RekeyReport)
    indexes_ensured: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "category_backfill": self.category.as_dict(),
            "canonical_rekey": self.rekey.as_dict(),
            "indexes_ensured": self.indexes_ensured,
        }


def classify_category_backfill(doc: dict[str, Any]) -> tuple[str, str | None]:
    """Return ``(action, category)`` for WP8.1 category backfill."""
    raw = doc.get("incident_category")
    if raw is not None and str(raw).strip():
        normalized = str(raw).strip().lower()
        if normalized in INCIDENT_CATEGORIES:
            return "already_canonical", normalized
        return "invalid", None

    metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    meta_cat = metadata.get("incident_category")
    if meta_cat is not None and str(meta_cat).strip():
        meta_norm = str(meta_cat).strip().lower()
        if meta_norm in INCIDENT_CATEGORIES:
            return "backfill", normalize_incident_category(meta_norm)
        return "ambiguous", None

    event_type = doc.get("event_type")
    if event_type and event_type not in {DERIVED_ANOMALY_EVENT_TYPE, "anomaly"}:
        mapped = map_forest_event_type_to_incident(str(event_type))
        if mapped == "unknown" and not doc.get("region") and not doc.get("spatial_key"):
            return "ambiguous", None
        if mapped == "unknown":
            return "ambiguous", None
        return "backfill", mapped

    if not doc.get("region") and not doc.get("spatial_key"):
        return "ambiguous", None

    return "backfill", resolve_incident_category(doc)


def canonical_persisted_fields(doc: dict[str, Any]) -> tuple[str, str]:
    """Return persisted ``(incident_category, spatial_key)`` after defaults."""
    category = normalize_incident_category(doc.get("incident_category"))
    spatial_key = doc.get("spatial_key")
    region = doc.get("region")
    if spatial_key:
        spatial_key = str(spatial_key).strip()
    elif region:
        spatial_key = spatial_key_from_region(str(region))
    else:
        raise ValueError("missing spatial_key and region")
    return category, spatial_key


def rekey_update_fields(doc: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    """Return ``(action, $set fields)`` for WP8.2 canonical persistence."""
    if not doc.get("region") and not doc.get("spatial_key"):
        return "ambiguous", None

    raw_category = doc.get("incident_category")
    if raw_category is not None and str(raw_category).strip():
        normalized_raw = str(raw_category).strip().lower()
        if normalized_raw not in INCIDENT_CATEGORIES:
            return "invalid", None

    try:
        category, spatial_key = canonical_persisted_fields(doc)
        region = region_from_spatial_key(spatial_key)
    except ValueError:
        return "invalid", None

    updates: dict[str, Any] = {}
    stored_category = doc.get("incident_category")
    if stored_category is None or str(stored_category).strip() == "":
        updates["incident_category"] = category
    elif normalize_incident_category(stored_category) != category:
        return "invalid", None

    if doc.get("spatial_key") != spatial_key:
        updates["spatial_key"] = spatial_key
    if doc.get("region") != region:
        updates["region"] = region

    if not updates:
        return "already_canonical", None

    try:
        identity_key_from_event({**doc, **updates})
    except ValueError:
        return "invalid", None

    return "rekeyed", updates


def pick_collision_winner(docs: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministic winner for duplicate active canonical identities."""

    def sort_key(doc: dict[str, Any]) -> tuple[Any, ...]:
        last = doc.get("last_detected_at")
        if last is None:
            last = datetime.min.replace(tzinfo=timezone.utc)
        oid = doc.get("_id")
        oid_ts = oid.generation_time if isinstance(oid, ObjectId) else datetime.min.replace(
            tzinfo=timezone.utc
        )
        return (
            doc.get("detection_count", 0),
            last,
            oid_ts,
        )

    return max(docs, key=sort_key)


async def backfill_incident_categories(
    db: AsyncIOMotorDatabase,
) -> CategoryBackfillReport:
    """WP8.1 — idempotent ``incident_category`` backfill."""
    report = CategoryBackfillReport()
    col = db[COLLECTION]

    async for doc in col.find({}):
        report.scanned += 1
        action, category = classify_category_backfill(doc)
        if action == "already_canonical":
            report.already_canonical += 1
            continue
        if action == "invalid":
            report.invalid += 1
            continue
        if action == "ambiguous":
            report.ambiguous += 1
            continue
        if category is None:
            report.skipped += 1
            continue

        try:
            result = await col.update_one(
                {
                    "_id": doc["_id"],
                    "$or": [
                        {"incident_category": {"$exists": False}},
                        {"incident_category": None},
                        {"incident_category": ""},
                    ],
                },
                {"$set": {"incident_category": category}},
            )
            if result.modified_count:
                report.backfilled += 1
            else:
                report.already_canonical += 1
        except Exception:
            logger.exception(
                "Category backfill failed for intelligence event %s", doc.get("_id")
            )
            report.failed += 1

    return report


async def rekey_canonical_identity(
    db: AsyncIOMotorDatabase,
    *,
    migration_time: datetime | None = None,
) -> RekeyReport:
    """WP8.2 — persist canonical identity fields and resolve active collisions."""
    report = RekeyReport()
    col = db[COLLECTION]
    now = migration_time or datetime.now(timezone.utc)

    async for doc in col.find({}):
        report.scanned += 1
        action, updates = rekey_update_fields(doc)
        if action == "already_canonical":
            report.already_canonical += 1
            continue
        if action == "invalid":
            report.invalid += 1
            continue
        if action == "ambiguous":
            report.ambiguous += 1
            continue
        if not updates:
            report.skipped += 1
            continue

        try:
            result = await col.update_one({"_id": doc["_id"]}, {"$set": updates})
            if result.modified_count:
                report.rekeyed += 1
            else:
                report.already_canonical += 1
        except Exception:
            logger.exception(
                "Canonical re-key failed for intelligence event %s", doc.get("_id")
            )
            report.failed += 1

    active_docs = [doc async for doc in col.find({"status": "active"})]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for doc in active_docs:
        try:
            key = identity_key_from_event(doc)
        except ValueError:
            continue
        groups.setdefault(key, []).append(doc)

    for key, docs in sorted(groups.items()):
        if len(docs) <= 1:
            continue
        report.collisions_detected += len(docs) - 1
        winner = pick_collision_winner(docs)
        for doc in docs:
            if doc["_id"] == winner["_id"]:
                continue
            report.collision_event_ids.append(str(doc["_id"]))
            try:
                result = await col.update_one(
                    {
                        "_id": doc["_id"],
                        "status": "active",
                    },
                    {"$set": {"status": "resolved", "resolved_at": now}},
                )
                if result.modified_count:
                    report.collisions_resolved += 1
            except Exception:
                logger.exception(
                    "Collision resolve failed for intelligence event %s", doc.get("_id")
                )
                report.failed += 1

    return report


async def _ensure_named_index(col, keys, name: str) -> None:
    """Create ``name`` even if Mongo already has the same keys under an auto name."""
    try:
        await col.create_index(keys, name=name)
        return
    except OperationFailure as exc:
        if getattr(exc, "code", None) != 85:
            raise
        old_name = _conflicting_index_name(exc)
        if not old_name or old_name == name:
            raise
        await col.drop_index(old_name)
        await col.create_index(keys, name=name)
        logger.info(
            "Renamed intelligence_events index %s -> %s",
            old_name,
            name,
        )


def _conflicting_index_name(exc: OperationFailure) -> str | None:
    details = getattr(exc, "details", None) or {}
    errmsg = str(details.get("errmsg") or exc)
    marker = "different name: "
    if marker not in errmsg:
        return None
    return errmsg.split(marker, 1)[1].split(",", 1)[0].strip()


async def ensure_intelligence_events_indexes(db: AsyncIOMotorDatabase) -> int:
    """WP8.3 — idempotent index creation; returns count of index ensure calls."""
    col = db[COLLECTION]
    await _ensure_named_index(col, LEGACY_DEDUP_INDEX, "legacy_event_region_status")
    await _ensure_named_index(col, LAST_DETECTED_INDEX, "last_detected_at")
    await _ensure_named_index(col, CANONICAL_IDENTITY_INDEX, "canonical_identity_status")
    return 3


async def migrate_intelligence_events_canonical(
    db: AsyncIOMotorDatabase,
) -> IntelligenceEventsMigrationReport:
    """Run WP8.1 → WP8.2 → WP8.3 in order (idempotent)."""
    report = IntelligenceEventsMigrationReport()
    report.category = await backfill_incident_categories(db)
    report.rekey = await rekey_canonical_identity(db)
    report.indexes_ensured = await ensure_intelligence_events_indexes(db)

    changed = (
        report.category.backfilled
        + report.rekey.rekeyed
        + report.rekey.collisions_resolved
    )
    if changed:
        logger.info(
            "Intelligence events migration: category_backfilled=%d rekeyed=%d collisions_resolved=%d",
            report.category.backfilled,
            report.rekey.rekeyed,
            report.rekey.collisions_resolved,
        )
    return report
