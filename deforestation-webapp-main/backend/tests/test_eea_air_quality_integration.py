"""EEA Air Quality integration — first non-wildfire European environmental source."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.core.ecosystem.air_quality_constants import (
    EEA_MISSING_VALUE,
    normalize_pollutant,
    normalize_unit,
)
from app.core.ecosystem.canonical_identity import spatial_key_from_station
from app.core.ecosystem.environmental_observation import EnvironmentalObservation
from app.core.ecosystem.incident_categories import IncidentCategory, resolve_incident_category
from app.modules.analytics.analytics_service import _compute_baselines, _evaluate_anomalies
from app.modules.analytics.context_enrichment import enrich_detection_with_forest_context
from app.modules.analytics.detection_adapters import detection_from_anomaly_dict
from app.modules.analytics.detection_contract import Detection, SignalType
from app.modules.analytics.detector_registry import get_detector_registry
from app.modules.analytics.detectors.air_quality_baseline_detector import (
    AirQualityBaselineDetector,
)
from app.modules.analytics.detectors.wildfire_baseline_detector import (
    WildfireBaselineDeviationDetector,
)
from app.modules.analytics.intelligence_events_service import IntelligenceEventsService
from app.modules.analytics.map_contract import forest_event_map_marker, intelligence_event_map_marker
from app.modules.analytics.reconciliation import dedupe_detections, metadata_from_detection
from app.modules.analytics.segmented_baseline import aggregate_regional_baselines_by_category
from app.modules.ingestion.providers.eea_aq_station_metadata import EEAAQStationMetadata
from app.modules.ingestion.providers.eea_air_quality import (
    EEAAirQualityProvider,
    EEA_AQ_DATASET_ID,
    EEA_AQ_SOURCE_NAME,
    STATION_REGISTRY,
    _DEFAULT_FIXTURE_RECORDS,
)
from app.services.forest_context_service import ForestContextService
from app.services.scheduler_service import SchedulerService
from fixtures.phase0_golden_fixture import CYCLE_ANCHORS, build_wildfire_events
from fixtures.phase0_golden_harness import Phase0FixtureAnalyticsRepository, generate_golden_artifacts
from fixtures.phase0_oracle_manifest import verify_generated_match_manifest

_NOW = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)


def _aq_events_from_fixture() -> list[dict]:
    provider = EEAAirQualityProvider()
    events: list[dict] = []
    for raw in _DEFAULT_FIXTURE_RECORDS:
        payload = provider.normalize(raw)
        data = payload.model_dump()
        data["detected_at"] = data["detected_at"] or _NOW
        data["metadata"]["ingestion"] = {**data["metadata"].get("ingestion", {}), "is_romania": True}
        events.append(data)
    return events


def _aq_baseline_regions(now: datetime | None = None):
    now = now or _NOW
    events = _aq_events_from_fixture()
    rows = aggregate_regional_baselines_by_category(events, now)
    return _compute_baselines(rows, generated_at=now)["regions"]


class TestEEAProviderMetadata:
    def test_describe_includes_source_model(self):
        desc = EEAAirQualityProvider().describe()
        assert desc["source"] == EEA_AQ_SOURCE_NAME
        assert desc["dataset_id"] == EEA_AQ_DATASET_ID
        assert desc["spatial_model"] == "monitoring_station"
        assert desc["temporal_resolution"] == "hourly"
        assert desc["license"]
        assert desc["live_access_status"] == "fixture_only"


class TestFixtureNormalization:
    def test_normalize_produces_observation_metadata(self):
        provider = EEAAirQualityProvider()
        payload = provider.normalize(_DEFAULT_FIXTURE_RECORDS[0])
        obs = payload.metadata["observation"]
        assert obs["pollutant"] == "PM2.5"
        assert obs["unit"] == "ug/m3"
        assert obs["station_id"] == "RO-BUC-AQ01"
        assert payload.metadata["incident_category"] == IncidentCategory.AIR_QUALITY.value

    def test_station_coordinates_from_registry(self):
        payload = EEAAirQualityProvider().normalize(_DEFAULT_FIXTURE_RECORDS[0])
        station = STATION_REGISTRY["RO-BUC-AQ01"]
        assert payload.latitude == station["latitude"]
        assert payload.longitude == station["longitude"]


class TestPollutantNormalization:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("pm2.5", "PM2.5"),
            ("NO2", "NO2"),
            ("ozone", "O3"),
        ],
    )
    def test_aliases(self, raw, expected):
        assert normalize_pollutant(raw) == expected


class TestUnitNormalization:
    def test_microgram_aliases(self):
        assert normalize_unit("PM2.5", "µg/m3") == "ug/m3"


class TestTimestampNormalization:
    def test_observed_at_is_utc(self):
        payload = EEAAirQualityProvider().normalize(_DEFAULT_FIXTURE_RECORDS[0])
        obs = EnvironmentalObservation.from_metadata_block(payload.metadata["observation"])
        assert obs is not None
        assert obs.observed_at.tzinfo is not None


class TestMissingValues:
    def test_missing_sentinel_rejected(self):
        provider = EEAAirQualityProvider()
        with pytest.raises(ValueError):
            provider.normalize(
                {"station_id": "RO-BUC-AQ01", "pollutant": "PM2.5", "value": EEA_MISSING_VALUE}
            )


class TestInvalidValues:
    def test_unknown_pollutant_rejected(self):
        provider = EEAAirQualityProvider()
        with pytest.raises(ValueError):
            provider.normalize({"station_id": "X", "pollutant": "", "value": 10.0})


class TestStationIdentity:
    def test_region_is_station_id(self):
        payload = EEAAirQualityProvider().normalize(_DEFAULT_FIXTURE_RECORDS[0])
        assert payload.region == "RO-BUC-AQ01"


class TestSpatialIdentity:
    def test_detection_uses_station_spatial_key(self):
        regions = _aq_baseline_regions()
        aq_regions = [r for r in regions if r.get("incident_category") == "air_quality"]
        if not aq_regions:
            pytest.skip("no air quality baseline in fixture window")
        detector = AirQualityBaselineDetector()
        detections = detector.detect(regions, _NOW)
        assert detections
        assert detections[0].spatial_key == spatial_key_from_station("RO-BUC-AQ01")


class TestBaselineComputation:
    def test_station_segment_has_air_quality_category(self):
        regions = _aq_baseline_regions()
        aq = [r for r in regions if r.get("incident_category") == IncidentCategory.AIR_QUALITY.value]
        assert len(aq) >= 1
        buc = next(r for r in aq if r["region"] == "RO-BUC-AQ01")
        assert buc["current_events"] >= 3
        assert buc["deviation_percent"] >= 50.0


class TestAirQualityAnomalyDetection:
    def test_spike_triggers_detection(self):
        regions = _aq_baseline_regions()
        evaluated = _evaluate_anomalies(
            regions,
            _NOW,
            incident_category=IncidentCategory.AIR_QUALITY.value,
        )
        assert evaluated["anomalies"]
        assert evaluated["anomalies"][0]["region"] == "RO-BUC-AQ01"


class TestDetectionContractCompatibility:
    def test_detection_fields(self):
        regions = _aq_baseline_regions()
        detector = AirQualityBaselineDetector()
        det = detector.detect(regions, _NOW)[0]
        assert det.incident_category == IncidentCategory.AIR_QUALITY.value
        assert det.signal_type == SignalType.BASELINE_DEVIATION.value
        assert "baseline_events" in det.evidence
        assert det.evidence.get("latitude") is not None


class TestDetectorRegistryRegistration:
    def test_air_quality_detector_registered(self):
        registry = get_detector_registry()
        assert registry.get("air_quality_baseline_deviation") is not None
        assert registry.get("wildfire_baseline_deviation") is not None


class TestReconciliation:
    def test_dedupe_and_metadata(self):
        regions = _aq_baseline_regions()
        detector = AirQualityBaselineDetector()
        detections = detector.detect(regions, _NOW)
        deduped = dedupe_detections(detections)
        meta = metadata_from_detection(deduped[0])
        assert meta["station_id"] == "RO-BUC-AQ01"
        assert "deviation_percent" in meta


class TestMultiplePollutantsSameStation:
    def test_shared_station_segment(self):
        events = _aq_events_from_fixture()
        rows = aggregate_regional_baselines_by_category(events, _NOW)
        buc_rows = [r for r in rows if r["_id"]["region"] == "RO-BUC-AQ01"]
        assert len(buc_rows) == 1


class TestSamePollutantDifferentStations:
    def test_distinct_segments(self):
        events = _aq_events_from_fixture()
        rows = aggregate_regional_baselines_by_category(events, _NOW)
        regions = {r["_id"]["region"] for r in rows if r["_id"]["incident_category"] == "air_quality"}
        assert "RO-BUC-AQ01" in regions
        assert "RO-CLJ-AQ01" in regions or "RO-TM-AQ01" in regions


class TestCategoryIsolationFromWildfire:
    def test_wildfire_detector_unchanged_on_phase0(self):
        import asyncio

        events = build_wildfire_events()
        repo = Phase0FixtureAnalyticsRepository(events)
        rows = asyncio.run(repo.regional_baselines(CYCLE_ANCHORS[0]))
        regions = _compute_baselines(rows, generated_at=CYCLE_ANCHORS[0])["regions"]
        wildfire = WildfireBaselineDeviationDetector()
        legacy = _evaluate_anomalies(
            regions,
            CYCLE_ANCHORS[0],
            incident_category=IncidentCategory.WILDFIRE.value,
        )
        detections = wildfire.detect(regions, CYCLE_ANCHORS[0])
        assert len(detections) == len(legacy["anomalies"])

    def test_air_quality_detector_empty_on_wildfire_only(self):
        import asyncio

        events = build_wildfire_events()
        repo = Phase0FixtureAnalyticsRepository(events)
        rows = asyncio.run(repo.regional_baselines(CYCLE_ANCHORS[0]))
        regions = _compute_baselines(rows, generated_at=CYCLE_ANCHORS[0])["regions"]
        aq = AirQualityBaselineDetector().detect(regions, CYCLE_ANCHORS[0])
        assert aq == []


class TestCLMSForestContextEnrichment:
    def test_air_quality_detection_receives_forest_context(self):
        anomaly = {
            "region": "RO-BUC-AQ01",
            "baseline_events": 1,
            "current_events": 5,
            "deviation_percent": 150.0,
            "anomaly_score": 0.7,
            "severity": "high",
            "station_id": "RO-BUC-AQ01",
            "latitude": STATION_REGISTRY["RO-BUC-AQ01"]["latitude"],
            "longitude": STATION_REGISTRY["RO-BUC-AQ01"]["longitude"],
            "pollutant": "PM2.5",
        }
        det = detection_from_anomaly_dict(
            anomaly,
            detected_at=_NOW,
            incident_category=IncidentCategory.AIR_QUALITY.value,
        )
        enriched = enrich_detection_with_forest_context(
            det,
            context_svc=ForestContextService(),
        )
        assert enriched.evidence.get("forest_context") is not None


class TestMapContract:
    def test_forest_event_marker_includes_pollutant(self):
        payload = EEAAirQualityProvider().normalize(_DEFAULT_FIXTURE_RECORDS[0])
        marker = forest_event_map_marker(
            {
                **payload.model_dump(),
                "id": "evt-1",
                "land_cover_type": "urban",
            }
        )
        assert marker["incident_category"] == "air_quality"
        assert marker["pollutant"] == "PM2.5"
        assert marker["coordinate_source"] == "monitoring_station"
        assert marker["spatial_key"] == spatial_key_from_station("RO-BUC-AQ01")

    def test_intelligence_marker_includes_station_metadata(self):
        regions = _aq_baseline_regions()
        det = AirQualityBaselineDetector().detect(regions, _NOW)[0]
        marker = intelligence_event_map_marker(
            {
                "id": "intel-1",
                "region": det.evidence["region"],
                "spatial_key": det.spatial_key,
                "incident_category": det.incident_category,
                "severity": det.severity,
                "metadata": metadata_from_detection(det),
            }
        )
        assert marker.get("pollutant") == "PM2.5"
        assert marker.get("station_id") == "RO-BUC-AQ01"


class TestSchedulerBehavior:
    @pytest.mark.anyio
    async def test_optional_eea_provider_in_cycle(self):
        firms = MagicMock()
        firms.source_name = "NASA FIRMS"
        firms.provider_id = "nasa.firms"
        firms.describe = MagicMock(return_value={"source": "NASA FIRMS", "provider_id": "nasa.firms"})
        firms.run = AsyncMock(return_value={"total": 0, "created": 0, "skipped": 0, "errors": 0})
        eea = EEAAirQualityProvider()
        eea.run = AsyncMock(return_value={"total": 8, "created": 2, "skipped": 6, "errors": 0})

        runs_repo = MagicMock()
        runs_repo.create_run = AsyncMock(return_value={"status": "success", "duration_seconds": 0.1})

        scheduler = SchedulerService(
            firms_provider=firms,
            events_service=MagicMock(),
            events_repo=MagicMock(),
            analytics_service=MagicMock(reconcile_intelligence_events=AsyncMock()),
            intelligence_service=MagicMock(),
            runs_repo=runs_repo,
            enabled=True,
            ingestion_providers=[firms, eea],
            reconciliation_lock=MagicMock(try_acquire=AsyncMock(return_value=True), release=AsyncMock()),
        )
        await scheduler._run_cycle()
        eea.run.assert_awaited_once()


class TestProviderFailureBehavior:
    @pytest.mark.anyio
    async def test_live_token_uses_live_path(self):
        from tests.test_eea_live_activation import _build_zip, _station_lookup

        settings = Settings(
            mongo_url="mongodb://localhost:27017",
            db_name="test",
            jwt_secret="secret",
            admin_email="admin@test.com",
            admin_password="pass",
            frontend_url="http://localhost:3000",
            eea_aq_api_token="a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        )
        mock_client = AsyncMock()
        mock_client.download_parquet_zip = AsyncMock(return_value=_build_zip())
        mock_client.fetch_dataset_version = AsyncMock(return_value="Raster1")
        mock_client.aclose = AsyncMock()

        provider = EEAAirQualityProvider(
            settings=settings,
            download_client=mock_client,
            station_metadata=EEAAQStationMetadata(index=_station_lookup()),
        )
        records = await provider.fetch()
        assert len(records) == 1
        assert records[0]["pollutant"] == "PM2.5"
        mock_client.download_parquet_zip.assert_awaited_once()


class TestDeterministicRepeatedRuns:
    @pytest.mark.anyio
    async def test_fetch_is_deterministic(self):
        provider = EEAAirQualityProvider()
        first = await provider.fetch()
        second = await provider.fetch()
        assert first == second


class TestPhase0Compatibility:
    def test_oracle_unchanged(self):
        generated = generate_golden_artifacts()
        verify_generated_match_manifest(generated)

    def test_registry_detect_all_on_phase0_wildfire_only(self):
        import asyncio

        events = build_wildfire_events()
        repo = Phase0FixtureAnalyticsRepository(events)
        rows = asyncio.run(repo.regional_baselines(CYCLE_ANCHORS[0]))
        regions = _compute_baselines(rows, generated_at=CYCLE_ANCHORS[0])["regions"]
        wildfire_only = _evaluate_anomalies(
            regions,
            CYCLE_ANCHORS[0],
            incident_category=IncidentCategory.WILDFIRE.value,
        )
        all_dets = get_detector_registry().detect_all(regions, CYCLE_ANCHORS[0])
        wf_dets = [d for d in all_dets if d.incident_category == IncidentCategory.WILDFIRE.value]
        assert len(wf_dets) == len(wildfire_only["anomalies"])
