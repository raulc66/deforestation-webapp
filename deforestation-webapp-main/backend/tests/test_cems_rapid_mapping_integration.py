"""Copernicus EMS Rapid Mapping integration — environmental hazard domain."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.ecosystem.canonical_identity import spatial_key_from_cems_country
from app.core.ecosystem.environmental_hazard_constants import normalize_hazard_type
from app.core.ecosystem.incident_categories import IncidentCategory
from app.modules.analytics.analytics_service import _compute_baselines, _evaluate_anomalies
from app.modules.analytics.context_enrichment import enrich_detection_with_forest_context
from app.modules.analytics.detection_adapters import detection_from_anomaly_dict
from app.modules.analytics.detection_contract import SignalType
from app.modules.analytics.detector_registry import get_detector_registry
from app.modules.analytics.detectors.environmental_hazard_baseline_detector import (
    EnvironmentalHazardBaselineDetector,
)
from app.modules.analytics.detectors.wildfire_baseline_detector import (
    WildfireBaselineDeviationDetector,
)
from app.modules.analytics.map_contract import forest_event_map_marker
from app.modules.analytics.reconciliation import dedupe_detections, metadata_from_detection
from app.modules.analytics.segmented_baseline import aggregate_regional_baselines_by_category
from app.modules.ingestion.providers.cems_rapid_mapping import (
    CEMS_API_BASE,
    CEMSRapidMappingProvider,
    CEMS_DATASET_ID,
    CEMS_SOURCE_NAME,
    _DEFAULT_FIXTURE_RECORDS,
    is_european_activation,
    parse_wkt_point,
)
from app.services.forest_context_service import ForestContextService
from app.services.scheduler_service import SchedulerService
from fixtures.phase0_golden_fixture import CYCLE_ANCHORS, build_wildfire_events
from fixtures.phase0_golden_harness import Phase0FixtureAnalyticsRepository, generate_golden_artifacts
from fixtures.phase0_oracle_manifest import verify_generated_match_manifest

_NOW = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)


def _cems_events_from_fixture() -> list[dict]:
    provider = CEMSRapidMappingProvider()
    events: list[dict] = []
    for raw in _DEFAULT_FIXTURE_RECORDS:
        payload = provider.normalize(raw)
        data = payload.model_dump()
        data["detected_at"] = data["detected_at"] or _NOW
        data["metadata"]["ingestion"] = {
            **data["metadata"].get("ingestion", {}),
            "is_romania": raw.get("countries") == ["Romania"],
        }
        events.append(data)
    return events


def _hazard_baseline_regions(now: datetime | None = None):
    now = now or _NOW
    events = _cems_events_from_fixture()
    rows = aggregate_regional_baselines_by_category(events, now)
    return _compute_baselines(rows, generated_at=now)["regions"]


class TestCEMSProviderMetadata:
    def test_describe_documents_public_api(self):
        desc = CEMSRapidMappingProvider().describe()
        assert desc["source"] == CEMS_SOURCE_NAME
        assert desc["dataset_id"] == CEMS_DATASET_ID
        assert desc["live_access_status"] == "public_api"
        assert CEMS_API_BASE in desc["api_endpoint"]


class TestFixtureNormalization:
    def test_normalize_produces_activation_block(self):
        payload = CEMSRapidMappingProvider().normalize(_DEFAULT_FIXTURE_RECORDS[0])
        activation = payload.metadata["emergency_activation"]
        assert activation["activation_code"] == "EMSR-FIX-RO-01"
        assert activation["hazard_type"] == "flood"
        assert payload.metadata["incident_category"] == IncidentCategory.ENVIRONMENTAL_HAZARD.value
        assert payload.region == "Romania"


class TestHazardTypeNormalization:
    @pytest.mark.parametrize(
        "raw,expected",
        [("Wildfire", "wildfire"), ("Flood", "flood"), ("Volcanic activity", "volcanic")],
    )
    def test_cems_categories(self, raw, expected):
        assert normalize_hazard_type(raw) == expected


class TestWktCentroidParsing:
    def test_point_parsing(self):
        lat, lng = parse_wkt_point("POINT (26.259 47.6353)")
        assert lat == pytest.approx(47.6353)
        assert lng == pytest.approx(26.259)


class TestEuropeanFilter:
    def test_romania_is_european(self):
        assert is_european_activation(["Romania"]) is True

    def test_colombia_not_european(self):
        assert is_european_activation(["Colombia"]) is False


class TestSpatialIdentity:
    def test_country_spatial_key_on_detection(self):
        regions = _hazard_baseline_regions()
        detector = EnvironmentalHazardBaselineDetector()
        detections = detector.detect(regions, _NOW)
        ro = next((d for d in detections if d.evidence.get("country") == "Romania"), None)
        if ro is None:
            pytest.skip("Romania hazard baseline not anomalous in fixture window")
        assert ro.spatial_key == spatial_key_from_cems_country("Romania")


class TestBaselineComputation:
    def test_romania_segment_environmental_hazard(self):
        regions = _hazard_baseline_regions()
        ro = [
            r
            for r in regions
            if r.get("incident_category") == IncidentCategory.ENVIRONMENTAL_HAZARD.value
            and r["region"] == "Romania"
        ]
        assert ro
        assert ro[0]["current_events"] >= 3


class TestHazardAnomalyDetection:
    def test_romania_spike_triggers(self):
        regions = _hazard_baseline_regions()
        evaluated = _evaluate_anomalies(
            regions,
            _NOW,
            incident_category=IncidentCategory.ENVIRONMENTAL_HAZARD.value,
        )
        assert any(a["region"] == "Romania" for a in evaluated["anomalies"])


class TestDetectionContract:
    def test_envelope_fields(self):
        regions = _hazard_baseline_regions()
        det = EnvironmentalHazardBaselineDetector().detect(regions, _NOW)[0]
        assert det.incident_category == IncidentCategory.ENVIRONMENTAL_HAZARD.value
        assert det.signal_type == SignalType.BASELINE_DEVIATION.value


class TestDetectorRegistry:
    def test_environmental_hazard_detector_registered(self):
        assert get_detector_registry().get("environmental_hazard_baseline_deviation") is not None


class TestReconciliation:
    def test_metadata_includes_country(self):
        regions = _hazard_baseline_regions()
        dets = dedupe_detections(EnvironmentalHazardBaselineDetector().detect(regions, _NOW))
        meta = metadata_from_detection(dets[0])
        assert meta.get("country") == "Romania"


class TestCategoryIsolation:
    def test_wildfire_unchanged_on_phase0(self):
        import asyncio

        events = build_wildfire_events()
        repo = Phase0FixtureAnalyticsRepository(events)
        rows = asyncio.run(repo.regional_baselines(CYCLE_ANCHORS[0]))
        regions = _compute_baselines(rows, generated_at=CYCLE_ANCHORS[0])["regions"]
        wildfire = WildfireBaselineDeviationDetector().detect(regions, CYCLE_ANCHORS[0])
        legacy = _evaluate_anomalies(
            regions,
            CYCLE_ANCHORS[0],
            incident_category=IncidentCategory.WILDFIRE.value,
        )
        assert len(wildfire) == len(legacy["anomalies"])

    def test_hazard_empty_on_wildfire_only(self):
        import asyncio

        events = build_wildfire_events()
        repo = Phase0FixtureAnalyticsRepository(events)
        rows = asyncio.run(repo.regional_baselines(CYCLE_ANCHORS[0]))
        regions = _compute_baselines(rows, generated_at=CYCLE_ANCHORS[0])["regions"]
        assert EnvironmentalHazardBaselineDetector().detect(regions, CYCLE_ANCHORS[0]) == []


class TestCLMSEnrichment:
    def test_hazard_detection_receives_forest_context(self):
        anomaly = {
            "region": "Romania",
            "country": "Romania",
            "baseline_events": 1,
            "current_events": 5,
            "deviation_percent": 150.0,
            "anomaly_score": 0.7,
            "severity": "high",
            "latitude": 46.3548,
            "longitude": 25.7979,
            "hazard_type": "wildfire",
        }
        det = detection_from_anomaly_dict(
            anomaly,
            detected_at=_NOW,
            incident_category=IncidentCategory.ENVIRONMENTAL_HAZARD.value,
        )
        enriched = enrich_detection_with_forest_context(
            det,
            context_svc=ForestContextService(),
        )
        assert enriched.evidence.get("forest_context") is not None


class TestMapContract:
    def test_activation_marker_fields(self):
        payload = CEMSRapidMappingProvider().normalize(_DEFAULT_FIXTURE_RECORDS[2])
        marker = forest_event_map_marker({**payload.model_dump(), "id": "evt-cems-1"})
        assert marker["incident_category"] == "environmental_hazard"
        assert marker["hazard_type"] == "wildfire"
        assert marker["activation_code"] == "EMSR-FIX-RO-03"
        assert marker["coordinate_source"] == "activation_centroid"


class TestScheduler:
    @pytest.mark.anyio
    async def test_cems_provider_in_cycle(self):
        firms = MagicMock()
        firms.source_name = "NASA FIRMS"
        firms.provider_id = "nasa.firms"
        firms.describe = MagicMock(return_value={"source": "NASA FIRMS", "provider_id": "nasa.firms"})
        firms.run = AsyncMock(return_value={"total": 0, "created": 0, "skipped": 0, "errors": 0})
        cems = CEMSRapidMappingProvider()
        cems.run = AsyncMock(return_value={"total": 6, "created": 3, "skipped": 3, "errors": 0})

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
            ingestion_providers=[firms, cems],
            reconciliation_lock=MagicMock(try_acquire=AsyncMock(return_value=True), release=AsyncMock()),
        )
        await scheduler._run_cycle()
        cems.run.assert_awaited_once()


class TestProviderFailure:
    @pytest.mark.anyio
    async def test_live_failure_falls_back_to_fixture(self, monkeypatch):
        provider = CEMSRapidMappingProvider()

        def _boom(_url):
            raise ConnectionError("network down")

        monkeypatch.setattr(provider, "_http_get_json", _boom)
        records = await provider.fetch()
        assert len(records) == len(_DEFAULT_FIXTURE_RECORDS)


class TestDeterminism:
    @pytest.mark.anyio
    async def test_fixture_fetch_deterministic(self, monkeypatch):
        provider = CEMSRapidMappingProvider()

        def _fail():
            raise ConnectionError("network down")

        monkeypatch.setattr(provider, "_fetch_live", _fail)
        first = await provider.fetch()
        second = await provider.fetch()
        assert first == second


class TestPhase0Compatibility:
    def test_oracle_unchanged(self):
        verify_generated_match_manifest(generate_golden_artifacts())

    def test_detect_all_wildfire_count_unchanged(self):
        import asyncio

        events = build_wildfire_events()
        repo = Phase0FixtureAnalyticsRepository(events)
        rows = asyncio.run(repo.regional_baselines(CYCLE_ANCHORS[0]))
        regions = _compute_baselines(rows, generated_at=CYCLE_ANCHORS[0])["regions"]
        legacy = _evaluate_anomalies(
            regions,
            CYCLE_ANCHORS[0],
            incident_category=IncidentCategory.WILDFIRE.value,
        )
        all_dets = get_detector_registry().detect_all(regions, CYCLE_ANCHORS[0])
        wf = [d for d in all_dets if d.incident_category == IncidentCategory.WILDFIRE.value]
        assert len(wf) == len(legacy["anomalies"])
