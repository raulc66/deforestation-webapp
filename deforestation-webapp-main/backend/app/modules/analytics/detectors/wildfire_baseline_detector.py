"""Wildfire baseline-deviation detector — first registered detector (WP1 migration).

Wraps the existing rule-based anomaly evaluation without changing its logic.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.ecosystem.incident_categories import IncidentCategory
from app.modules.analytics.analytics_service import _evaluate_anomalies
from app.modules.analytics.detection_adapters import detection_from_anomaly_dict
from app.modules.analytics.detection_contract import Detection, SignalType
from app.modules.analytics.detector_contract import Detector
from app.modules.analytics.segmented_baseline import filter_baseline_regions_for_category


class WildfireBaselineDeviationDetector(Detector):
    """Existing regional baseline deviation rule as a registered detector."""

    @property
    def detector_id(self) -> str:
        return "wildfire_baseline_deviation"

    @property
    def incident_categories(self) -> tuple[str, ...]:
        return (IncidentCategory.WILDFIRE.value,)

    @property
    def signal_type(self) -> str:
        return SignalType.BASELINE_DEVIATION.value

    def detect(
        self,
        baseline_regions: list[dict[str, Any]],
        detected_at: datetime,
    ) -> list[Detection]:
        wildfire_regions = filter_baseline_regions_for_category(
            baseline_regions,
            IncidentCategory.WILDFIRE.value,
        )
        evaluated = _evaluate_anomalies(
            wildfire_regions,
            detected_at,
            incident_category=IncidentCategory.WILDFIRE.value,
        )
        return [
            detection_from_anomaly_dict(
                anomaly,
                detected_at=detected_at,
                incident_category=IncidentCategory.WILDFIRE.value,
                signal_type=self.signal_type,
            )
            for anomaly in evaluated["anomalies"]
        ]
