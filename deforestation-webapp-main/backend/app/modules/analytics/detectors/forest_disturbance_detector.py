"""Forest disturbance signal detector — deterministic, explainable scoring."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.ecosystem.incident_categories import IncidentCategory
from app.modules.analytics.detection_contract import Detection, SignalType
from app.modules.analytics.detector_contract import Detector
from app.modules.analytics.disturbance_detection import (
    DISTURBANCE_SCORE_THRESHOLD,
    compute_disturbance_score,
)
from app.modules.analytics.segmented_baseline import filter_baseline_regions_for_category


class ForestDisturbanceDetector(Detector):
    """Detect significant forest disturbance from segmented regional evidence."""

    @property
    def detector_id(self) -> str:
        return "forest_disturbance_signal"

    @property
    def incident_categories(self) -> tuple[str, ...]:
        return (IncidentCategory.FOREST_DISTURBANCE.value,)

    @property
    def signal_type(self) -> str:
        return SignalType.DISTURBANCE_SIGNAL.value

    def detect(
        self,
        baseline_regions: list[dict[str, Any]],
        detected_at: datetime,
    ) -> list[Detection]:
        regions = filter_baseline_regions_for_category(
            baseline_regions,
            IncidentCategory.FOREST_DISTURBANCE.value,
        )
        detections: list[Detection] = []
        for row in regions:
            region = str(row.get("region") or row.get("_id", {}).get("region") or "Unknown")
            current = int(row.get("current_events") or 0)
            if current <= 0:
                continue
            confidence = min(0.95, 0.55 + current * 0.05)
            area_ha = float(row.get("total_affected_area_ha") or current * 3.0)
            score = compute_disturbance_score(
                confidence=confidence,
                affected_area_ha=area_ha,
                forest_context={"is_forest": True},
                repeat_count=current,
                spatial_coherence=min(1.0, current / 3.0),
                temporal_persistence=min(1.0, current / 4.0),
            )
            if score < DISTURBANCE_SCORE_THRESHOLD:
                continue
            spatial_key = region
            detections.append(
                Detection(
                    spatial_key=spatial_key,
                    incident_category=IncidentCategory.FOREST_DISTURBANCE.value,
                    signal_type=self.signal_type,
                    severity="high" if score >= 0.75 else "medium",
                    score=score,
                    detected_at=detected_at,
                    evidence={
                        "region": region,
                        "latitude": row.get("latitude"),
                        "longitude": row.get("longitude"),
                        "baseline_events": int(row.get("baseline_events") or 0),
                        "current_events": current,
                        "affected_area_ha": area_ha,
                        "provenance": {
                            "provider_id": "gfw.integrated_alerts",
                            "domain_evidence": {
                                "provider_class": "gfw_integrated_alerts",
                                "detection_method": self.signal_type,
                            },
                        },
                    },
                )
            )
        return detections
