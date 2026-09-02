"""Environmental hazard baseline-deviation detector (CEMS activations)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.ecosystem.incident_categories import IncidentCategory
from app.modules.analytics.analytics_service import _evaluate_anomalies
from app.modules.analytics.detection_adapters import detection_from_anomaly_dict
from app.modules.analytics.detection_contract import Detection, SignalType
from app.modules.analytics.detector_contract import Detector
from app.modules.analytics.segmented_baseline import filter_baseline_regions_for_category


class EnvironmentalHazardBaselineDetector(Detector):
    """Country-level activation count baseline deviation for EMS hazard events."""

    @property
    def detector_id(self) -> str:
        return "environmental_hazard_baseline_deviation"

    @property
    def incident_categories(self) -> tuple[str, ...]:
        return (IncidentCategory.ENVIRONMENTAL_HAZARD.value,)

    @property
    def signal_type(self) -> str:
        return SignalType.BASELINE_DEVIATION.value

    def detect(
        self,
        baseline_regions: list[dict[str, Any]],
        detected_at: datetime,
    ) -> list[Detection]:
        hazard_regions = filter_baseline_regions_for_category(
            baseline_regions,
            IncidentCategory.ENVIRONMENTAL_HAZARD.value,
        )
        evaluated = _evaluate_anomalies(
            hazard_regions,
            detected_at,
            incident_category=IncidentCategory.ENVIRONMENTAL_HAZARD.value,
        )
        detections: list[Detection] = []
        for anomaly in evaluated["anomalies"]:
            enriched = {**anomaly, "country": anomaly["region"]}
            detections.append(
                detection_from_anomaly_dict(
                    enriched,
                    detected_at=detected_at,
                    incident_category=IncidentCategory.ENVIRONMENTAL_HAZARD.value,
                    signal_type=self.signal_type,
                )
            )
        return detections
