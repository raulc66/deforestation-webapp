"""Per-category anomaly detection thresholds (WP2.4).

Wildfire values match the pre-WP2 constants in ``analytics_service``.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.ecosystem.incident_categories import IncidentCategory, normalize_incident_category


@dataclass(frozen=True)
class AnomalyThresholds:
    min_events: int
    min_deviation_percent: float


_DEFAULT_WILDFIRE = AnomalyThresholds(min_events=5, min_deviation_percent=50.0)

_CATEGORY_THRESHOLDS: dict[str, AnomalyThresholds] = {
    IncidentCategory.WILDFIRE.value: _DEFAULT_WILDFIRE,
    IncidentCategory.ILLEGAL_LOGGING.value: AnomalyThresholds(
        min_events=3, min_deviation_percent=40.0
    ),
    IncidentCategory.DEFORESTATION.value: AnomalyThresholds(
        min_events=3, min_deviation_percent=40.0
    ),
    IncidentCategory.AIR_QUALITY.value: AnomalyThresholds(
        min_events=3, min_deviation_percent=50.0
    ),
    IncidentCategory.ENVIRONMENTAL_HAZARD.value: AnomalyThresholds(
        min_events=3, min_deviation_percent=50.0
    ),
    IncidentCategory.FOREST_DISTURBANCE.value: AnomalyThresholds(
        min_events=2, min_deviation_percent=35.0
    ),
}


def get_anomaly_thresholds(incident_category: str | None) -> AnomalyThresholds:
    """Resolve thresholds for a category; unknown categories use wildfire defaults."""
    normalized = normalize_incident_category(incident_category)
    return _CATEGORY_THRESHOLDS.get(normalized, _DEFAULT_WILDFIRE)
