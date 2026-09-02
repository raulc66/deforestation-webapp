"""Platform generalization regression suite (Package G)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.ecosystem.canonical_identity import spatial_key_from_region
from app.core.ecosystem.incident_categories import IncidentCategory
from app.modules.analytics.anomaly_thresholds import get_anomaly_thresholds
from app.modules.analytics.detector_registry import get_detector_registry
from app.modules.analytics.detection_adapters import detection_from_anomaly_dict
from app.modules.analytics.incident_aggregation import build_default_incident_registry
from app.modules.analytics.map_contract import forest_event_map_marker
from app.modules.analytics.reconciliation import identity_key_from_detection
from app.modules.analytics.segmented_baseline import (
    aggregate_regional_baselines_by_category,
    segment_key,
)
from app.modules.ingestion.providers.firms import FIRMSProvider
from app.modules.ingestion.providers.synthetic_environmental import SyntheticEnvironmentalProvider
from fixtures.phase0_golden_harness import generate_golden_artifacts
from fixtures.phase0_oracle_manifest import verify_generated_match_manifest


_NOW = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)


def _romania_event(
    *,
    region: str,
    days_before: int,
    event_type: str = "wildfire",
    lat: float = 46.42,
    lng: float = 25.65,
):
    return {
        "region": region,
        "event_type": event_type,
        "latitude": lat,
        "longitude": lng,
        "detected_at": _NOW - timedelta(days=days_before),
        "metadata": {"ingestion": {"is_romania": True}},
    }


class TestTwoCategoriesOneRegion:
    def test_segmented_baselines_isolate_categories(self):
        events = [
            _romania_event(region="Gamma", days_before=1, event_type="wildfire"),
            _romania_event(region="Gamma", days_before=10, event_type="wildfire"),
            _romania_event(region="Gamma", days_before=1, event_type="logging"),
            _romania_event(region="Gamma", days_before=11, event_type="logging"),
        ]
        rows = aggregate_regional_baselines_by_category(events, _NOW)
        by_cat = {row["_id"]["incident_category"]: row for row in rows}
        assert by_cat["wildfire"]["current_events"] == 1
        assert by_cat["illegal_logging"]["current_events"] == 1


class TestTwoSpatialKeysOneCategory:
    def test_wildfire_segments_by_region(self):
        events = [
            _romania_event(region="Alpha", days_before=1),
            _romania_event(region="Beta", days_before=2),
        ]
        rows = aggregate_regional_baselines_by_category(events, _NOW)
        keys = {row["_id"]["region"] for row in rows if row["_id"]["incident_category"] == "wildfire"}
        assert keys == {"Alpha", "Beta"}


class TestSyntheticSecondProvider:
    def test_provider_contract_surface(self):
        provider = SyntheticEnvironmentalProvider()
        assert provider.source_name
        assert IncidentCategory.ILLEGAL_LOGGING.value in provider.supported_incident_categories

    def test_firms_remains_first_live_provider(self):
        provider = FIRMSProvider()
        assert provider.supported_incident_categories == (IncidentCategory.WILDFIRE.value,)


class TestCategoryIsolation:
    def test_logging_thresholds_differ_from_wildfire(self):
        wildfire = get_anomaly_thresholds("wildfire")
        logging = get_anomaly_thresholds("illegal_logging")
        assert wildfire != logging


class TestDetectorRegistryCompatibility:
    def test_open_closed_registry_lists_wildfire_detector(self):
        registry = get_detector_registry()
        ids = {d.detector_id for d in registry.list_detectors()}
        assert "wildfire_baseline_deviation" in ids


class TestReconciliationCompatibility:
    def test_detection_identity_uses_category_and_spatial_key(self):
        detection = detection_from_anomaly_dict(
            {
                "region": "Suceava",
                "baseline_events": 1,
                "current_events": 5,
                "deviation_percent": 400.0,
                "anomaly_score": 0.64,
                "severity": "high",
            },
            detected_at=_NOW,
            incident_category="wildfire",
        )
        assert identity_key_from_detection(detection) == (
            "wildfire",
            spatial_key_from_region("Suceava"),
        )


class TestApiSerialization:
    def test_map_marker_includes_incident_category_and_spatial_key(self):
        marker = forest_event_map_marker(
            {
                "latitude": 47.68,
                "longitude": 25.72,
                "region": "Suceava",
                "event_type": "wildfire",
                "metadata": {},
            }
        )
        assert marker["incident_category"] == "wildfire"
        assert marker["spatial_key"] == spatial_key_from_region("Suceava")


class TestWildfireBackwardCompatibility:
    @pytest.mark.anyio
    async def test_default_registry_still_registers_wildfire_aggregator(self):
        registry = build_default_incident_registry()
        analytics = MagicMock()
        analytics.overview = AsyncMock(return_value={})
        analytics.by_event_type = AsyncMock(
            return_value=[{"event_type": "wildfire", "event_count": 65, "affected_area_ha": 8580.0}]
        )
        analytics.get_anomalies = AsyncMock(return_value={"anomalies": []})
        payload = await registry.aggregate_all(analytics)
        assert payload["aggregators"]["wildfire"]["aggregator_id"] == "wildfire"
        assert payload["by_incident_category"]["wildfire"]["event_count"] == 65


class TestPhase0OracleCompatibility:
    def test_regenerated_artifacts_match_manifest(self):
        verify_generated_match_manifest(generate_golden_artifacts())

    def test_incident_aggregation_wildfire_counts_stable(self):
        artifacts = generate_golden_artifacts()
        payload = json.loads(artifacts["incident_aggregation.json"])
        assert payload["by_incident_category"]["wildfire"]["event_count"] == 65
