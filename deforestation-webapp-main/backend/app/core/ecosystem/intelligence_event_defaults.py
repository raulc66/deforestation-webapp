"""Deterministic legacy defaults for intelligence event read models (WP1.4)."""
from __future__ import annotations

from typing import Any

from app.core.ecosystem.canonical_identity import (
    region_from_spatial_key,
    spatial_key_from_region,
)
from app.core.ecosystem.incident_categories import normalize_incident_category

DERIVED_ANOMALY_EVENT_TYPE = "anomaly"
DEFAULT_SIGNAL_TYPE = "baseline_deviation"


def apply_legacy_intelligence_event_defaults(record: dict[str, Any]) -> dict[str, Any]:
    """Apply deterministic defaults for absent canonical fields on read."""
    out = dict(record)
    out["incident_category"] = normalize_incident_category(out.get("incident_category"))
    region = out.get("region")
    if region and not out.get("spatial_key"):
        out["spatial_key"] = spatial_key_from_region(str(region))
    elif out.get("spatial_key") and not region:
        out["region"] = region_from_spatial_key(str(out["spatial_key"]))
    if not out.get("signal_type"):
        out["signal_type"] = DEFAULT_SIGNAL_TYPE
    if not out.get("event_type"):
        out["event_type"] = DERIVED_ANOMALY_EVENT_TYPE
    return out
