"""Detector registry — open/closed registration per ADR-004 / ADR-005."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .detection_contract import Detection
from .detector_contract import Detector


class DetectorRegistry:
    """Register detectors without modifying analytics or reconciliation core."""

    def __init__(self) -> None:
        self._detectors: dict[str, Detector] = {}

    def register(self, detector: Detector) -> None:
        existing = self._detectors.get(detector.detector_id)
        if existing is not None and existing is not detector:
            raise ValueError(f"detector already registered: {detector.detector_id}")
        self._detectors[detector.detector_id] = detector

    def list_detectors(self) -> list[Detector]:
        return list(self._detectors.values())

    def get(self, detector_id: str) -> Detector | None:
        return self._detectors.get(detector_id)

    def detect_all(
        self,
        baseline_regions: list[dict[str, Any]],
        detected_at: datetime,
    ) -> list[Detection]:
        """Run every registered detector and return combined detections."""
        detections: list[Detection] = []
        for detector in self._detectors.values():
            detections.extend(detector.detect(baseline_regions, detected_at))
        detections.sort(key=lambda d: (-d.score, d.spatial_key))
        return detections


def build_default_detector_registry() -> DetectorRegistry:
    from .detectors.air_quality_baseline_detector import AirQualityBaselineDetector
    from .detectors.environmental_hazard_baseline_detector import (
        EnvironmentalHazardBaselineDetector,
    )
    from .detectors.forest_disturbance_detector import ForestDisturbanceDetector
    from .detectors.wildfire_baseline_detector import WildfireBaselineDeviationDetector

    registry = DetectorRegistry()
    registry.register(WildfireBaselineDeviationDetector())
    registry.register(AirQualityBaselineDetector())
    registry.register(EnvironmentalHazardBaselineDetector())
    registry.register(ForestDisturbanceDetector())
    return registry


_default_registry = build_default_detector_registry()


def get_detector_registry() -> DetectorRegistry:
    return _default_registry
