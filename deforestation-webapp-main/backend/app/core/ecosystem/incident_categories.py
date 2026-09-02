"""Incident category taxonomy for ecosystem intelligence events.

``IncidentCategory`` generalises intelligence beyond wildfire while keeping
existing anomaly events compatible (default category: wildfire).
"""
from __future__ import annotations

from enum import StrEnum
from typing import Any


class IncidentCategory(StrEnum):
    WILDFIRE = "wildfire"
    AIR_QUALITY = "air_quality"
    ENVIRONMENTAL_HAZARD = "environmental_hazard"
    FOREST_DISTURBANCE = "forest_disturbance"
    ILLEGAL_LOGGING = "illegal_logging"
    TREE_THEFT = "tree_theft"
    DEFORESTATION = "deforestation"
    PROTECTED_AREA_VIOLATION = "protected_area_violation"
    HABITAT_DISTURBANCE = "habitat_disturbance"
    UNKNOWN = "unknown"


INCIDENT_CATEGORIES: tuple[str, ...] = tuple(c.value for c in IncidentCategory)

# Categories that receive zero-count slots in Phase 0 oracle artifacts.
# New categories (e.g. air_quality) appear only once they carry events/counts.
PHASE0_ORACLE_CATEGORY_KEYS: frozenset[str] = frozenset(
    cat
    for cat in INCIDENT_CATEGORIES
    if cat
    not in (
        IncidentCategory.AIR_QUALITY.value,
        IncidentCategory.ENVIRONMENTAL_HAZARD.value,
        IncidentCategory.FOREST_DISTURBANCE.value,
    )
)

# Maps existing ForestEvent.event_type values to ecosystem incident categories.
_FOREST_EVENT_TYPE_MAP: dict[str, IncidentCategory] = {
    "wildfire": IncidentCategory.WILDFIRE,
    "logging": IncidentCategory.ILLEGAL_LOGGING,
    "mining": IncidentCategory.HABITAT_DISTURBANCE,
    "agriculture": IncidentCategory.DEFORESTATION,
    "road_construction": IncidentCategory.DEFORESTATION,
    "urban_expansion": IncidentCategory.DEFORESTATION,
    "unknown": IncidentCategory.UNKNOWN,
}


def normalize_incident_category(value: str | None) -> str:
    """Return a valid category string, falling back to ``unknown``."""
    if not value:
        return IncidentCategory.WILDFIRE.value
    normalized = str(value).strip().lower()
    if normalized in INCIDENT_CATEGORIES:
        return normalized
    return IncidentCategory.UNKNOWN.value


def resolve_incident_category(source: dict | None = None) -> str:
    """Derive incident category from an anomaly or event payload.

    Priority:
      1. Explicit ``incident_category`` on *source*
      2. ``forest_event_type`` / non-anomaly ``event_type`` mapped via
         :func:`map_forest_event_type_to_incident`
      3. Default ``wildfire`` (preserves existing FIRMS anomaly behaviour)
    """
    if not source:
        return IncidentCategory.WILDFIRE.value

    explicit = source.get("incident_category")
    if explicit:
        return normalize_incident_category(explicit)

    metadata = source.get("metadata") or {}
    meta_category = metadata.get("incident_category")
    if meta_category:
        return normalize_incident_category(meta_category)

    forest_event_type = source.get("forest_event_type") or source.get("event_type")
    if forest_event_type and forest_event_type != "anomaly":
        return map_forest_event_type_to_incident(str(forest_event_type))

    return IncidentCategory.WILDFIRE.value


def map_forest_event_type_to_incident(event_type: str) -> str:
    """Map a :class:`~app.models.enums.EventType` value to an incident category."""
    mapped = _FOREST_EVENT_TYPE_MAP.get(event_type)
    if mapped is not None:
        return mapped.value
    return IncidentCategory.UNKNOWN.value


def forest_event_type_switch_branches() -> list[dict[str, Any]]:
    """MongoDB ``$switch`` branches derived from :data:`_FOREST_EVENT_TYPE_MAP`."""
    return [
        {"case": {"$eq": ["$event_type", event_type]}, "then": category.value}
        for event_type, category in _FOREST_EVENT_TYPE_MAP.items()
    ]
