"""Central incident category registry (Package D).

Single source for category identifiers, display metadata, and compatibility
flags used by detectors and ingestion providers.
"""
from __future__ import annotations

from dataclasses import dataclass

from .incident_categories import (
    INCIDENT_CATEGORIES,
    IncidentCategory,
    map_forest_event_type_to_incident,
    normalize_incident_category,
    resolve_incident_category,
)


@dataclass(frozen=True)
class CategoryDefinition:
    identifier: str
    display_name: str
    enabled: bool = True
    detector_compatible: bool = True
    ingestion_compatible: bool = True


_DISPLAY_NAMES: dict[str, str] = {
    IncidentCategory.WILDFIRE.value: "Wildfire",
    IncidentCategory.AIR_QUALITY.value: "Air Quality",
    IncidentCategory.ENVIRONMENTAL_HAZARD.value: "Environmental Hazard",
    IncidentCategory.FOREST_DISTURBANCE.value: "Forest Disturbance",
    IncidentCategory.ILLEGAL_LOGGING.value: "Illegal Logging",
    IncidentCategory.TREE_THEFT.value: "Tree Theft",
    IncidentCategory.DEFORESTATION.value: "Deforestation",
    IncidentCategory.PROTECTED_AREA_VIOLATION.value: "Protected Area Violation",
    IncidentCategory.HABITAT_DISTURBANCE.value: "Habitat Disturbance",
    IncidentCategory.UNKNOWN.value: "Unknown",
}


class CategoryRegistry:
    """Read-only registry of platform incident categories."""

    def __init__(self) -> None:
        self._definitions: dict[str, CategoryDefinition] = {
            cat: CategoryDefinition(
                identifier=cat,
                display_name=_DISPLAY_NAMES.get(cat, cat.replace("_", " ").title()),
                enabled=cat != IncidentCategory.UNKNOWN.value,
                detector_compatible=cat
                in {
                    IncidentCategory.WILDFIRE.value,
                    IncidentCategory.AIR_QUALITY.value,
                    IncidentCategory.ENVIRONMENTAL_HAZARD.value,
                    IncidentCategory.FOREST_DISTURBANCE.value,
                    IncidentCategory.ILLEGAL_LOGGING.value,
                    IncidentCategory.DEFORESTATION.value,
                },
                ingestion_compatible=True,
            )
            for cat in INCIDENT_CATEGORIES
        }

    def categories(self) -> tuple[str, ...]:
        return INCIDENT_CATEGORIES

    def get(self, category_id: str) -> CategoryDefinition | None:
        normalized = normalize_incident_category(category_id)
        return self._definitions.get(normalized)

    def normalize(self, value: str | None) -> str:
        return normalize_incident_category(value)

    def resolve_from_event(self, source: dict | None = None) -> str:
        return resolve_incident_category(source)

    def map_event_type(self, event_type: str) -> str:
        return map_forest_event_type_to_incident(event_type)

    def enabled_categories(self) -> tuple[str, ...]:
        return tuple(
            cat for cat in INCIDENT_CATEGORIES if self._definitions[cat].enabled
        )


_default_registry = CategoryRegistry()


def get_category_registry() -> CategoryRegistry:
    return _default_registry
