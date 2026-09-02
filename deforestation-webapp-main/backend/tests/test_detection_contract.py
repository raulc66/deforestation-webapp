"""WP1.3 — Detection envelope contract tests."""
from datetime import datetime, timezone

import pytest

from app.modules.analytics.detection_contract import Detection, SignalType


_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


class TestDetectionContract:
    def test_constructs_valid_detection(self):
        detection = Detection(
            spatial_key="Suceava",
            incident_category="wildfire",
            signal_type=SignalType.BASELINE_DEVIATION.value,
            severity="high",
            score=0.64,
            evidence={"baseline_events": 1, "current_events": 5, "deviation_percent": 400.0},
            detected_at=_NOW,
        )
        assert detection.identity.spatial_key == "Suceava"
        assert detection.identity.incident_category == "wildfire"

    def test_score_must_be_within_unit_interval(self):
        with pytest.raises(ValueError):
            Detection(
                spatial_key="A",
                incident_category="wildfire",
                signal_type=SignalType.BASELINE_DEVIATION.value,
                severity="low",
                score=1.5,
                evidence={},
                detected_at=_NOW,
            )

    def test_detected_at_naive_datetime_coerced_to_utc(self):
        naive = datetime(2026, 6, 15, 12, 0, 0)
        detection = Detection(
            spatial_key="A",
            incident_category="wildfire",
            signal_type=SignalType.BASELINE_DEVIATION.value,
            severity="low",
            score=0.1,
            evidence={},
            detected_at=naive,
        )
        assert detection.detected_at.tzinfo is not None

    def test_model_is_immutable(self):
        detection = Detection(
            spatial_key="A",
            incident_category="wildfire",
            signal_type=SignalType.BASELINE_DEVIATION.value,
            severity="low",
            score=0.1,
            evidence={},
            detected_at=_NOW,
        )
        with pytest.raises(Exception):
            detection.score = 0.2  # type: ignore[misc]
