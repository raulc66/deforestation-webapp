"""WP1 — detector registry tests."""
from datetime import datetime, timezone

import pytest

from app.core.ecosystem.incident_categories import IncidentCategory
from app.modules.analytics.detection_contract import Detection, SignalType
from app.modules.analytics.detector_contract import Detector
from app.modules.analytics.detector_registry import DetectorRegistry, get_detector_registry


_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


class StubDetector(Detector):
    def __init__(self, detector_id: str = "stub") -> None:
        self._id = detector_id

    @property
    def detector_id(self) -> str:
        return self._id

    @property
    def incident_categories(self) -> tuple[str, ...]:
        return (IncidentCategory.UNKNOWN.value,)

    @property
    def signal_type(self) -> str:
        return SignalType.BASELINE_DEVIATION.value

    def detect(self, baseline_regions, detected_at):
        return [
            Detection(
                spatial_key="Test",
                incident_category=IncidentCategory.UNKNOWN.value,
                signal_type=self.signal_type,
                severity="low",
                score=0.4,
                evidence={"baseline_events": 0, "current_events": 5, "deviation_percent": 100.0, "region": "Test"},
                detected_at=detected_at,
            )
        ]


class TestDetectorRegistry:
    def test_default_registry_includes_wildfire_detector(self):
        registry = get_detector_registry()
        assert registry.get("wildfire_baseline_deviation") is not None

    def test_register_second_detector_without_engine_edit(self):
        registry = DetectorRegistry()
        registry.register(StubDetector("alpha"))
        registry.register(StubDetector("beta"))
        assert len(registry.list_detectors()) == 2

    def test_duplicate_detector_id_rejected(self):
        registry = DetectorRegistry()
        registry.register(StubDetector("dup"))
        with pytest.raises(ValueError):
            registry.register(StubDetector("dup"))

    def test_detect_all_runs_registered_detectors(self):
        registry = DetectorRegistry()
        registry.register(StubDetector("stub"))
        detections = registry.detect_all([], _NOW)
        assert len(detections) == 1
        assert detections[0].spatial_key == "Test"
