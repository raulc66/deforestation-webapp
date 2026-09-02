"""Wildfire baseline detector migration and adapter round-trip tests."""
from datetime import datetime, timezone

from app.modules.analytics.analytics_service import _evaluate_anomalies
from app.modules.analytics.detection_adapters import (
    anomaly_dict_from_detection,
    anomalies_response_from_detections,
    detection_from_anomaly_dict,
)
from app.modules.analytics.detectors.wildfire_baseline_detector import (
    WildfireBaselineDeviationDetector,
)
from fixtures.phase0_golden_fixture import CYCLE_ANCHORS, build_wildfire_events
from fixtures.phase0_golden_harness import Phase0FixtureAnalyticsRepository
from app.modules.analytics.analytics_service import _compute_baselines

_NOW = CYCLE_ANCHORS[0]


def _baseline_regions():
    import asyncio

    events = build_wildfire_events()
    repo = Phase0FixtureAnalyticsRepository(events)
    rows = asyncio.run(repo.regional_baselines(_NOW))
    return _compute_baselines(rows, generated_at=_NOW)["regions"]

class TestWildfireBaselineDetector:
    def test_detector_matches_evaluate_anomalies(self):
        regions = _baseline_regions()
        legacy = _evaluate_anomalies(regions, _NOW)
        detector = WildfireBaselineDeviationDetector()
        detections = detector.detect(regions, _NOW)
        assert len(detections) == len(legacy["anomalies"])
        for det, anomaly in zip(detections, legacy["anomalies"]):
            round_trip = anomaly_dict_from_detection(det)
            assert round_trip["region"] == anomaly["region"]
            assert round_trip["anomaly_score"] == anomaly["anomaly_score"]
            assert round_trip["severity"] == anomaly["severity"]

    def test_detection_round_trip_preserves_legacy_fields(self):
        regions = _baseline_regions()
        legacy = _evaluate_anomalies(regions, _NOW)
        for anomaly in legacy["anomalies"]:
            det = detection_from_anomaly_dict(anomaly, detected_at=_NOW)
            restored = anomaly_dict_from_detection(det)
            assert restored == {
                k: anomaly[k]
                for k in (
                    "region",
                    "baseline_events",
                    "current_events",
                    "deviation_percent",
                    "anomaly_score",
                    "severity",
                    "status",
                    "forest_confidence",
                )
            }

    def test_anomalies_response_from_detections_matches_legacy(self):
        regions = _baseline_regions()
        legacy = _evaluate_anomalies(regions, _NOW)
        detector = WildfireBaselineDeviationDetector()
        projected = anomalies_response_from_detections(
            detector.detect(regions, _NOW),
            generated_at=_NOW,
        )
        assert projected == legacy
