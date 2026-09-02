"""Air quality baseline-deviation detector — first non-wildfire registered detector."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.ecosystem.incident_categories import IncidentCategory
from app.modules.analytics.analytics_service import _evaluate_anomalies
from app.modules.analytics.detection_adapters import detection_from_anomaly_dict
from app.modules.analytics.detection_contract import Detection, SignalType
from app.modules.analytics.detector_contract import Detector
from app.modules.analytics.segmented_baseline import filter_baseline_regions_for_category
from app.modules.ingestion.providers.eea_air_quality import STATION_REGISTRY


class AirQualityBaselineDetector(Detector):
    """Regional/station baseline deviation for air-quality observations."""

    @property
    def detector_id(self) -> str:
        return "air_quality_baseline_deviation"

    @property
    def incident_categories(self) -> tuple[str, ...]:
        return (IncidentCategory.AIR_QUALITY.value,)

    @property
    def signal_type(self) -> str:
        return SignalType.BASELINE_DEVIATION.value

    def detect(
        self,
        baseline_regions: list[dict[str, Any]],
        detected_at: datetime,
    ) -> list[Detection]:
        aq_regions = filter_baseline_regions_for_category(
            baseline_regions,
            IncidentCategory.AIR_QUALITY.value,
        )
        evaluated = _evaluate_anomalies(
            aq_regions,
            detected_at,
            incident_category=IncidentCategory.AIR_QUALITY.value,
        )
        detections: list[Detection] = []
        for anomaly in evaluated["anomalies"]:
            station_id = str(anomaly["region"])
            station = STATION_REGISTRY.get(station_id, {})
            enriched = {
                **anomaly,
                "station_id": station_id,
                "station_name": station.get("station_name", station_id),
                "pollutant": anomaly.get("pollutant", "PM2.5"),
                "latitude": anomaly.get("latitude") or station.get("latitude"),
                "longitude": anomaly.get("longitude") or station.get("longitude"),
            }
            detections.append(
                detection_from_anomaly_dict(
                    enriched,
                    detected_at=detected_at,
                    incident_category=IncidentCategory.AIR_QUALITY.value,
                    signal_type=self.signal_type,
                )
            )
        return detections
