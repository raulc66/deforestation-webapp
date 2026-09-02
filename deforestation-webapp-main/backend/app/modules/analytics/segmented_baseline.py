"""Category-segmented regional baseline aggregation (WP2.1–WP2.2).

Groups Romania forest events by ``(region, incident_category)`` in one pass.
Phase 0 uses administrative ``region`` as ``spatial_key``.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.core.geography.geographic_scope import GeographicScope, GeographicScopePolicy
from app.core.ecosystem.incident_categories import (
    IncidentCategory,
    forest_event_type_switch_branches,
    normalize_incident_category,
    resolve_incident_category,
)

_LC_LABELS: tuple[str, ...] = (
    "forest",
    "near_forest",
    "agriculture",
    "urban",
    "water",
    "unknown",
)

# MongoDB $switch branches — single source from incident_categories taxonomy.
_EVENT_TYPE_TO_CATEGORY_BRANCHES: list[dict[str, Any]] = forest_event_type_switch_branches()


def incident_category_add_fields_stage() -> dict[str, Any]:
    """Return a MongoDB ``$addFields`` stage deriving ``_segment_incident_category``."""
    return {
        "$addFields": {
            "_segment_incident_category": {
                "$cond": [
                    {"$ne": [{"$ifNull": ["$incident_category", ""]}, ""]},
                    {"$toLower": "$incident_category"},
                    {
                        "$cond": [
                            {
                                "$ne": [
                                    {"$ifNull": ["$metadata.incident_category", ""]},
                                    "",
                                ]
                            },
                            {"$toLower": "$metadata.incident_category"},
                            {
                                "$switch": {
                                    "branches": _EVENT_TYPE_TO_CATEGORY_BRANCHES,
                                    "default": IncidentCategory.WILDFIRE.value,
                                }
                            },
                        ]
                    },
                ]
            }
        }
    }


def parse_segment_key(row_id: Any) -> tuple[str, str]:
    """Parse aggregation ``_id`` into ``(region, incident_category)``."""
    if isinstance(row_id, dict):
        region = row_id.get("region")
        if region is None:
            region = row_id.get("spatial_key")
        category = normalize_incident_category(row_id.get("incident_category"))
        return (str(region) if region is not None else "Unknown", category)
    return (str(row_id) if row_id is not None else "Unknown", IncidentCategory.WILDFIRE.value)


def segment_key(region: str, incident_category: str) -> dict[str, str]:
    """Build a composite aggregation key."""
    return {
        "region": str(region),
        "incident_category": normalize_incident_category(incident_category),
    }


def _lc_bucket(land_cover_type: str | None) -> str:
    lc = land_cover_type or "unknown"
    return lc if lc in _LC_LABELS else "unknown"


def _empty_lc_counts() -> dict[str, int]:
    return {f"lc_{label}": 0 for label in _LC_LABELS}


def aggregate_regional_baselines_by_category(
    events: list[dict],
    now: datetime,
    *,
    scope_policy: GeographicScopePolicy | None = None,
    romania_only: bool | None = None,
) -> list[dict]:
    """Pure-Python mirror of ``AnalyticsRepository.regional_baselines`` (WP2.1)."""
    if scope_policy is None:
        if romania_only is False:
            scope_policy = GeographicScopePolicy(GeographicScope.ALL)
        else:
            scope_policy = GeographicScopePolicy(GeographicScope.ROMANIA)

    cutoff_7d = now - timedelta(days=7)
    cutoff_35d = now - timedelta(days=35)

    per_segment: dict[tuple[str, str], dict[str, int]] = {}

    for event in events:
        if not scope_policy.event_in_scope(event):
            continue

        detected_at = event["detected_at"]
        if detected_at < cutoff_35d:
            continue

        region = event.get("region", "Unknown")
        category = resolve_incident_category(event)
        key = (region, category)
        bucket = per_segment.setdefault(
            key,
            {
                "current_events": 0,
                "baseline_raw": 0,
                **_empty_lc_counts(),
            },
        )

        if detected_at >= cutoff_7d:
            bucket["current_events"] += 1
        else:
            bucket["baseline_raw"] += 1

        lc_key = f"lc_{_lc_bucket(event.get('land_cover_type'))}"
        bucket[lc_key] += 1

    rows = [
        {
            "_id": segment_key(region, category),
            **counts,
        }
        for (region, category), counts in sorted(
            per_segment.items(),
            key=lambda item: (item[0][0], item[0][1]),
        )
    ]
    return rows


def filter_baseline_regions_for_category(
    regions: list[dict[str, Any]],
    incident_category: str,
) -> list[dict[str, Any]]:
    """Return shaped baseline rows belonging to one incident category."""
    target = normalize_incident_category(incident_category)
    return [
        region
        for region in regions
        if normalize_incident_category(region.get("incident_category")) == target
    ]
