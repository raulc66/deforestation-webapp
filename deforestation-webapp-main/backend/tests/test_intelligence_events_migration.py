"""WP8.4 — intelligence events canonical migration tests."""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
from bson import ObjectId

from app.core.intelligence_events_migration import (
    CANONICAL_IDENTITY_INDEX,
    LEGACY_DEDUP_INDEX,
    CategoryBackfillReport,
    IntelligenceEventsMigrationReport,
    backfill_incident_categories,
    classify_category_backfill,
    ensure_intelligence_events_indexes,
    migrate_intelligence_events_canonical,
    pick_collision_winner,
    rekey_canonical_identity,
    rekey_update_fields,
)
from app.modules.analytics.reconciliation import identity_key_from_event
from tests.fixtures.fake_intelligence_events_collection import make_migration_db

_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
_GOLDEN_DIR = Path(__file__).resolve().parent / "fixtures" / "golden"


def _legacy_wildfire(
    region: str,
    *,
    event_id: str | None = None,
    status: str = "active",
    detection_count: int = 1,
    category: str | None = None,
    spatial_key: str | None = None,
) -> dict:
    doc = {
        "_id": ObjectId(event_id) if event_id else ObjectId(),
        "event_type": "anomaly",
        "region": region,
        "status": status,
        "severity": "high",
        "escalation_level": "normal",
        "previous_score": None,
        "trend": "new",
        "priority_score": 0.55,
        "first_detected_at": _NOW,
        "last_detected_at": _NOW,
        "detection_count": detection_count,
        "current_score": 0.64,
        "metadata": {"baseline_events": 1, "current_events": 5, "deviation_percent": 400.0},
    }
    if category is not None:
        doc["incident_category"] = category
    if spatial_key is not None:
        doc["spatial_key"] = spatial_key
    return doc


class TestCategoryBackfillClassification:
    def test_missing_category_maps_to_wildfire(self):
        action, cat = classify_category_backfill({"region": "Suceava", "event_type": "anomaly"})
        assert action == "backfill"
        assert cat == "wildfire"

    def test_existing_valid_category_is_canonical(self):
        action, cat = classify_category_backfill(
            {"incident_category": "illegal_logging", "region": "Cluj"}
        )
        assert action == "already_canonical"
        assert cat == "illegal_logging"

    def test_invalid_explicit_category(self):
        action, cat = classify_category_backfill(
            {"incident_category": "not_a_real_category", "region": "Cluj"}
        )
        assert action == "invalid"
        assert cat is None

    def test_ambiguous_without_region_or_spatial_key(self):
        action, _ = classify_category_backfill({"event_type": "anomaly"})
        assert action == "ambiguous"


class TestMigrationEmptyDatabase:
    @pytest.mark.anyio
    async def test_empty_database_migration_is_noop(self):
        db, _ = make_migration_db([])
        report = await migrate_intelligence_events_canonical(db)
        assert report.category.scanned == 0
        assert report.category.backfilled == 0
        assert report.rekey.rekeyed == 0
        assert report.indexes_ensured == 3


class TestMigrationAlreadyMigrated:
    @pytest.mark.anyio
    async def test_already_migrated_database_is_idempotent(self):
        docs = [
            _legacy_wildfire(
                "Suceava",
                category="wildfire",
                spatial_key="Suceava",
            )
        ]
        db, col = make_migration_db(docs)
        first = await migrate_intelligence_events_canonical(db)
        second = await migrate_intelligence_events_canonical(db)

        assert first.rekey.rekeyed == 0
        assert second.category.backfilled == 0
        assert second.rekey.rekeyed == 0
        assert second.rekey.collisions_resolved == 0
        stored = col.all_docs()[0]
        assert stored["incident_category"] == "wildfire"
        assert stored["spatial_key"] == "Suceava"


class TestLegacyWildfireBackfill:
    @pytest.mark.anyio
    async def test_legacy_wildfire_backfills_category_and_spatial_key(self):
        db, col = make_migration_db([_legacy_wildfire("Bacău")])
        report = await migrate_intelligence_events_canonical(db)

        assert report.category.backfilled == 1
        assert report.rekey.rekeyed == 1
        stored = col.all_docs()[0]
        assert stored["incident_category"] == "wildfire"
        assert stored["spatial_key"] == "Bacău"
        assert stored["region"] == "Bacău"
        assert stored["detection_count"] == 1
        assert stored["trend"] == "new"


class TestMultiCategoryIndependence:
    @pytest.mark.anyio
    async def test_same_region_different_categories_remain_independent(self):
        docs = [
            _legacy_wildfire("Suceava", category="wildfire"),
            _legacy_wildfire("Suceava", category="illegal_logging"),
        ]
        db, col = make_migration_db(docs)
        await migrate_intelligence_events_canonical(db)

        keys = [identity_key_from_event(d) for d in col.all_docs()]
        assert keys[0] != keys[1]
        assert col.all_docs()[0]["status"] == "active"
        assert col.all_docs()[1]["status"] == "active"


class TestSpatialKeyIndependence:
    @pytest.mark.anyio
    async def test_same_category_different_spatial_keys_remain_independent(self):
        docs = [
            _legacy_wildfire("Suceava", category="wildfire", spatial_key="Suceava"),
            _legacy_wildfire("Bacău", category="wildfire", spatial_key="Bacău"),
        ]
        db, col = make_migration_db(docs)
        await migrate_intelligence_events_canonical(db)
        active = [d for d in col.all_docs() if d["status"] == "active"]
        assert len(active) == 2


class TestMissingFields:
    @pytest.mark.anyio
    async def test_missing_category_backfilled(self):
        db, col = make_migration_db([_legacy_wildfire("Cluj")])
        await backfill_incident_categories(db)
        assert col.all_docs()[0]["incident_category"] == "wildfire"

    @pytest.mark.anyio
    async def test_missing_spatial_key_rekeyed_from_region(self):
        db, col = make_migration_db(
            [_legacy_wildfire("Cluj", category="wildfire")]
        )
        await rekey_canonical_identity(db)
        assert col.all_docs()[0]["spatial_key"] == "Cluj"

    @pytest.mark.anyio
    async def test_missing_region_and_spatial_key_is_ambiguous_on_rekey(self):
        action, updates = rekey_update_fields(
            {
                "incident_category": "wildfire",
                "event_type": "anomaly",
                "status": "active",
            }
        )
        assert action == "ambiguous"
        assert updates is None


class TestInvalidIdentity:
    def test_invalid_category_on_rekey(self):
        action, updates = rekey_update_fields(
            {
                "incident_category": "bogus",
                "region": "Suceava",
                "event_type": "anomaly",
            }
        )
        assert action == "invalid"
        assert updates is None


class TestCollisionHandling:
    def test_pick_collision_winner_prefers_higher_detection_count(self):
        low = _legacy_wildfire("Suceava", detection_count=1)
        high = _legacy_wildfire("Suceava", detection_count=5)
        winner = pick_collision_winner([low, high])
        assert winner["detection_count"] == 5

    @pytest.mark.anyio
    async def test_collision_detection_and_resolution(self):
        id_a = ObjectId()
        id_b = ObjectId()
        docs = [
            _legacy_wildfire("Suceava", event_id=str(id_a), detection_count=1),
            _legacy_wildfire("Suceava", event_id=str(id_b), detection_count=4),
        ]
        db, col = make_migration_db(docs)
        report = await migrate_intelligence_events_canonical(db)

        assert report.rekey.collisions_detected == 1
        assert report.rekey.collisions_resolved == 1
        stored = {str(d["_id"]): d for d in col.all_docs()}
        assert stored[str(id_b)]["status"] == "active"
        assert stored[str(id_a)]["status"] == "resolved"
        assert stored[str(id_a)]["detection_count"] == 1
        assert "resolved_at" in stored[str(id_a)]


class TestMigrationRerun:
    @pytest.mark.anyio
    async def test_rerun_after_partial_migration(self):
        docs = [_legacy_wildfire("Suceava"), _legacy_wildfire("Bacău")]
        db, col = make_migration_db(docs)
        await backfill_incident_categories(db)
        first_docs = col.all_docs()
        second = await migrate_intelligence_events_canonical(db)
        assert second.category.backfilled == 0
        assert second.rekey.rekeyed >= 0
        assert len(col.all_docs()) == len(first_docs)


class TestIndexCreation:
    @pytest.mark.anyio
    async def test_index_creation_is_idempotent(self):
        db, col = make_migration_db([])
        count1 = await ensure_intelligence_events_indexes(db)
        count2 = await ensure_intelligence_events_indexes(db)
        assert count1 == 3
        assert count2 == 3
        assert len(col.indexes_created) == 6
        names = [spec[1].get("name") for spec in col.indexes_created[:3]]
        assert "legacy_event_region_status" in names
        assert "canonical_identity_status" in names

    @pytest.mark.anyio
    async def test_index_creation_replaces_auto_named_duplicate(self):
        db, col = make_migration_db([])
        col.indexes_created.append(
            (LEGACY_DEDUP_INDEX, {"name": "event_type_1_region_1_status_1"})
        )
        count = await ensure_intelligence_events_indexes(db)
        assert count == 3
        names = [spec[1].get("name") for spec in col.indexes_created]
        assert "legacy_event_region_status" in names
        assert "event_type_1_region_1_status_1" not in names
        assert "canonical_identity_status" in names


class TestLifecyclePreservation:
    @pytest.mark.anyio
    async def test_lifecycle_fields_preserved_on_winner(self):
        doc = _legacy_wildfire("Suceava", detection_count=7)
        doc["escalation_level"] = "critical"
        doc["previous_score"] = 0.5
        doc["trend"] = "worsening"
        db, col = make_migration_db([doc])
        await migrate_intelligence_events_canonical(db)
        stored = col.all_docs()[0]
        assert stored["detection_count"] == 7
        assert stored["escalation_level"] == "critical"
        assert stored["previous_score"] == 0.5
        assert stored["trend"] == "worsening"


class TestUnrelatedFieldsPreserved:
    @pytest.mark.anyio
    async def test_unrelated_fields_not_modified(self):
        doc = _legacy_wildfire("Suceava")
        doc["metadata"] = {"baseline_events": 2, "current_events": 9, "deviation_percent": 350.0}
        doc["priority_score"] = 0.77
        before = deepcopy(doc)
        db, col = make_migration_db([doc])
        await migrate_intelligence_events_canonical(db)
        stored = col.all_docs()[0]
        assert stored["metadata"] == before["metadata"]
        assert stored["priority_score"] == before["priority_score"]
        assert stored["severity"] == before["severity"]


class TestDeterministicReport:
    @pytest.mark.anyio
    async def test_deterministic_migration_report(self):
        docs = [_legacy_wildfire("Suceava"), _legacy_wildfire("Bacău")]
        db, _ = make_migration_db(docs)
        r1 = (await migrate_intelligence_events_canonical(db)).as_dict()
        r2 = (await migrate_intelligence_events_canonical(db)).as_dict()
        assert r1["category_backfill"]["backfilled"] == 2
        assert r2["category_backfill"]["backfilled"] == 0
        assert r2["canonical_rekey"]["rekeyed"] == 0


class TestNoSilentDeletion:
    @pytest.mark.anyio
    async def test_no_documents_deleted(self):
        docs = [
            _legacy_wildfire("Suceava", detection_count=1),
            _legacy_wildfire("Suceava", detection_count=3),
        ]
        db, col = make_migration_db(docs)
        await migrate_intelligence_events_canonical(db)
        assert len(col.all_docs()) == 2


class TestPhase0WildfireFixtureCompatibility:
    @pytest.mark.anyio
    async def test_phase0_golden_events_migrate_cleanly(self):
        golden = json.loads(
            (_GOLDEN_DIR / "cycle_0_intelligence_events.json").read_text(encoding="utf-8")
        )
        docs = []
        for event in golden["active"]:
            docs.append(
                {
                    "_id": ObjectId(),
                    **event,
                    "first_detected_at": _NOW,
                    "last_detected_at": _NOW,
                }
            )
        db, col = make_migration_db(docs)
        report = await migrate_intelligence_events_canonical(db)

        assert report.category.invalid == 0
        assert report.rekey.invalid == 0
        assert report.rekey.collisions_detected == 0
        for stored in col.all_docs():
            assert stored["incident_category"] == "wildfire"
            assert stored["spatial_key"] == stored["region"]
            assert stored["detection_count"] == 1


class TestMigrationReportShape:
    def test_report_contains_required_counters(self):
        report = IntelligenceEventsMigrationReport(
            category=CategoryBackfillReport(scanned=5, backfilled=2),
        ).as_dict()
        assert set(report["category_backfill"]) >= {
            "scanned",
            "already_canonical",
            "backfilled",
            "ambiguous",
            "invalid",
            "skipped",
            "failed",
        }


class TestIndexSpecConstants:
    def test_index_specs_match_server_alignment(self):
        assert LEGACY_DEDUP_INDEX == [("event_type", 1), ("region", 1), ("status", 1)]
        assert CANONICAL_IDENTITY_INDEX == [
            ("incident_category", 1),
            ("spatial_key", 1),
            ("status", 1),
        ]
