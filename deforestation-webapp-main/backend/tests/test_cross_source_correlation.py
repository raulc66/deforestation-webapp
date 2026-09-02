"""Cross-Source Correlation & Evidence Persistence tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import correlation_service_dep, get_current_user
from app.core.ecosystem.intelligence_event_defaults import DEFAULT_SIGNAL_TYPE
from app.core.ingestion.provider_health import ProviderHealthStatus
from app.models.user import UserPublic
from app.modules.analytics.analytics_routes import router
from app.modules.analytics.analytics_service import AnalyticsService
from app.modules.analytics.cross_source_correlator import CrossSourceCorrelator
from app.modules.analytics.detection_contract import Detection
from app.modules.analytics.intelligence_events_service import IntelligenceEventsService
from app.modules.analytics.provenance_persistence import sanitize_provenance_envelope
from app.modules.analytics.reconciliation import metadata_from_detection
from app.services.correlation_service import CorrelationService
from app.services.source_intelligence_service import SourceIntelligenceService
from fixtures.phase0_golden_harness import generate_golden_artifacts
from fixtures.phase0_oracle_manifest import verify_generated_match_manifest

_NOW = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)


def _mock_user() -> UserPublic:
    return UserPublic(
        id="1",
        email="test@example.com",
        name="Test",
        role="admin",
        provider="local",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def _detection(
    *,
    category: str,
    spatial_key: str,
    region: str,
    lat: float,
    lng: float,
    provider_id: str,
    provider_class: str,
    detected_at: datetime | None = None,
    hazard_type: str | None = None,
    country: str | None = None,
    station_id: str | None = None,
    score: float = 0.75,
) -> Detection:
    evidence: dict = {
        "baseline_events": 2,
        "current_events": 8,
        "deviation_percent": 100.0,
        "region": region,
        "latitude": lat,
        "longitude": lng,
        "provenance": {
            "provider_id": provider_id,
            "source_event_id": f"{provider_id}-{spatial_key}",
            "domain_evidence": {
                "provider_class": provider_class,
                "detection_method": DEFAULT_SIGNAL_TYPE,
            },
        },
    }
    if hazard_type:
        evidence["hazard_type"] = hazard_type
    if country:
        evidence["country"] = country
    if station_id:
        evidence["station_id"] = station_id
    return Detection(
        spatial_key=spatial_key,
        incident_category=category,
        signal_type=DEFAULT_SIGNAL_TYPE,
        severity="high",
        score=score,
        evidence=evidence,
        detected_at=detected_at or _NOW,
    )


def _firms(lat: float, lng: float, region: str = "Suceava", **kwargs) -> Detection:
    return _detection(
        category="wildfire",
        spatial_key=region,
        region=region,
        lat=lat,
        lng=lng,
        provider_id="nasa.firms",
        provider_class="satellite_fire_observations",
        **kwargs,
    )


def _eea(lat: float, lng: float, station: str = "RO-SV-AQ01", **kwargs) -> Detection:
    return _detection(
        category="air_quality",
        spatial_key=f"aq-station:{station}",
        region=station,
        lat=lat,
        lng=lng,
        provider_id="eea.air_quality",
        provider_class="eea_air_quality",
        station_id=station,
        **kwargs,
    )


def _cems(
    lat: float,
    lng: float,
    country: str = "Romania",
    hazard: str = "wildfire",
    **kwargs,
) -> Detection:
    return _detection(
        category="environmental_hazard",
        spatial_key=f"cems-country:{country}",
        region=country,
        lat=lat,
        lng=lng,
        provider_id="cems.rapid_mapping",
        provider_class="cems_rapid_mapping",
        hazard_type=hazard,
        country=country,
        **kwargs,
    )


class InMemoryCorrelationRepo:
    def __init__(self) -> None:
        self.records: list[dict] = []

    async def replace_all(self, records: list[dict], *, intelligence_cycle_id: str | None = None) -> None:
        self.records = []
        for record in records:
            doc = dict(record)
            if intelligence_cycle_id:
                doc["intelligence_cycle_id"] = intelligence_cycle_id
            self.records.append(doc)

    async def list_all(self) -> list[dict]:
        return list(self.records)


class InMemoryIntelRepo:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self._counter = 0

    async def find_active(self) -> list[dict]:
        return [e for e in self.events if e.get("status") == "active"]

    async def find_all(self) -> list[dict]:
        return list(self.events)

    async def create(self, event: dict) -> dict:
        self._counter += 1
        doc = {**event, "id": f"evt-{self._counter}"}
        self.events.append(doc)
        return doc

    async def update(self, event_id: str, update_data: dict) -> None:
        for event in self.events:
            if event["id"] == event_id:
                event.update(update_data)
                return

    async def resolve(self, event_id: str, resolved_at: datetime) -> None:
        for event in self.events:
            if event["id"] == event_id:
                event["status"] = "resolved"
                event["resolved_at"] = resolved_at
                return


class TestProvenancePersistence:
    def test_disabled_no_provenance_in_metadata(self):
        det = _firms(45.94, 25.45)
        meta = metadata_from_detection(det, include_provenance=False)
        assert "provenance" not in meta

    def test_enabled_persists_sanitized_provenance(self):
        det = _firms(45.94, 25.45)
        meta = metadata_from_detection(
            det,
            include_provenance=True,
            geographic_scope="romania",
        )
        assert meta["provenance"]["provider_id"] == "nasa.firms"
        assert meta["provenance"]["geographic_scope"] == "romania"

    def test_credentials_stripped_from_provenance(self):
        raw = {
            "provider_id": "nasa.firms",
            "api_key": "SECRET",
            "domain_evidence": {"provider_class": "satellite_fire_observations", "token": "SECRET"},
        }
        cleaned = sanitize_provenance_envelope(raw)
        assert "api_key" not in cleaned
        assert "token" not in cleaned.get("domain_evidence", {})

    @pytest.mark.anyio
    async def test_legacy_event_compatibility(self):
        repo = InMemoryIntelRepo()
        svc = IntelligenceEventsService(repo, include_provenance=False)
        await svc.reconcile_detections([_firms(45.94, 25.45)], _NOW)
        assert "provenance" not in repo.events[0].get("metadata", {})

    @pytest.mark.anyio
    async def test_enabled_provenance_persisted_on_create(self):
        repo = InMemoryIntelRepo()
        svc = IntelligenceEventsService(
            repo,
            include_provenance=True,
            geographic_scope="europe",
        )
        await svc.reconcile_detections([_firms(45.94, 25.45)], _NOW)
        assert "provenance" in repo.events[0]["metadata"]

    @pytest.mark.anyio
    async def test_read_model_strips_provenance_when_disabled(self):
        repo = InMemoryIntelRepo()
        svc = IntelligenceEventsService(repo, include_provenance=False)
        await svc.reconcile_detections([_firms(45.94, 25.45)], _NOW)
        events = await svc.get_events()
        assert "provenance" not in events["active"][0].get("metadata", {})


class TestCrossSourceCorrelation:
    def test_firms_cems_correlation(self):
        correlator = CrossSourceCorrelator()
        results = correlator.correlate(
            [_firms(45.94, 25.45), _cems(45.95, 25.46)],
            _NOW,
            geographic_scope="romania",
        )
        assert len(results) == 1
        assert results[0].correlation_rule == "firms_cems_wildfire_support"
        assert results[0].relationship_type == "supporting_evidence"

    def test_firms_eea_contextual_correlation(self):
        correlator = CrossSourceCorrelator()
        results = correlator.correlate(
            [_firms(45.94, 25.45), _eea(45.941, 25.451)],
            _NOW,
        )
        assert len(results) == 1
        assert results[0].relationship_type == "contextual_evidence"

    def test_eea_cems_multi_source(self):
        correlator = CrossSourceCorrelator()
        results = correlator.correlate(
            [_eea(44.43, 26.10), _cems(44.44, 26.11, hazard="flood")],
            _NOW,
        )
        assert len(results) == 1
        assert results[0].relationship_type == "multi_source_situation"

    def test_different_category_isolation(self):
        correlator = CrossSourceCorrelator()
        results = correlator.correlate(
            [_firms(45.94, 25.45), _cems(45.95, 25.46, hazard="flood")],
            _NOW,
        )
        assert not any(r.correlation_rule == "firms_cems_wildfire_support" for r in results)

    def test_temporal_window_boundary_excludes(self):
        correlator = CrossSourceCorrelator()
        old = _NOW - timedelta(hours=100)
        results = correlator.correlate(
            [_firms(45.94, 25.45), _cems(45.95, 25.46, detected_at=old)],
            _NOW,
        )
        assert len(results) == 0

    def test_spatial_window_boundary_excludes(self):
        correlator = CrossSourceCorrelator()
        results = correlator.correlate(
            [_firms(45.94, 25.45), _cems(50.0, 30.0)],
            _NOW,
        )
        assert len(results) == 0

    def test_same_source_no_self_correlation(self):
        correlator = CrossSourceCorrelator()
        results = correlator.correlate(
            [_firms(45.94, 25.45), _firms(45.941, 25.451)],
            _NOW,
        )
        assert len(results) == 0

    def test_deterministic_correlation_id_and_ordering(self):
        correlator = CrossSourceCorrelator()
        dets = [_firms(45.94, 25.45), _eea(45.941, 25.451), _cems(45.95, 25.46)]
        first = correlator.correlate(dets, _NOW)
        second = correlator.correlate(list(reversed(dets)), _NOW)
        assert [r.correlation_id for r in first] == [r.correlation_id for r in second]

    def test_one_to_many_correlations(self):
        correlator = CrossSourceCorrelator()
        results = correlator.correlate(
            [_firms(45.94, 25.45), _eea(45.941, 25.451), _cems(45.95, 25.46)],
            _NOW,
        )
        assert len(results) >= 2


class TestCorrelationIntegration:
    @pytest.mark.anyio
    async def test_correlation_persisted_when_enabled(self):
        repo = MagicMock()
        repo.regional_baselines = AsyncMock(return_value=[])
        repo.scope_policy = MagicMock(scope_value="romania")
        correlation_repo = InMemoryCorrelationRepo()
        analytics = AnalyticsService(repo, correlation_repo=correlation_repo)
        intel_svc = IntelligenceEventsService(InMemoryIntelRepo())
        detections = [_firms(45.94, 25.45), _cems(45.95, 25.46)]

        with patch("app.modules.analytics.detector_registry.get_detector_registry") as reg:
            with patch("app.core.config.get_settings") as settings_mock:
                settings = MagicMock()
                settings.enable_cross_source_correlation = True
                settings.enable_effis_wildfire_context = False
                settings.enable_forest_disturbance = False
                settings.geographic_scope = "romania"
                settings_mock.return_value = settings
                reg.return_value.detect_all = MagicMock(return_value=detections)
                with patch(
                    "app.modules.analytics.analytics_service._compute_baselines",
                    return_value={"regions": []},
                ):
                    await analytics.reconcile_intelligence_events(intel_svc)

        assert len(correlation_repo.records) == 1

    @pytest.mark.anyio
    async def test_correlation_disabled_by_default(self):
        repo = MagicMock()
        repo.regional_baselines = AsyncMock(return_value=[])
        correlation_repo = InMemoryCorrelationRepo()
        analytics = AnalyticsService(repo, correlation_repo=correlation_repo)
        intel_svc = IntelligenceEventsService(InMemoryIntelRepo())

        with patch("app.modules.analytics.detector_registry.get_detector_registry") as reg:
            reg.return_value.detect_all = MagicMock(return_value=[_firms(45.94, 25.45)])
            with patch(
                "app.modules.analytics.analytics_service._compute_baselines",
                return_value={"regions": []},
            ):
                with patch("app.core.config.get_settings") as settings_mock:
                    settings = MagicMock()
                    settings.enable_cross_source_correlation = False
                    settings.enable_effis_wildfire_context = False
                    settings.enable_forest_disturbance = False
                    settings.geographic_scope = "romania"
                    settings_mock.return_value = settings
                    await analytics.reconcile_intelligence_events(intel_svc)

        assert len(correlation_repo.records) == 0

    def test_correlated_events_not_merged(self):
        correlator = CrossSourceCorrelator()
        d_a = _firms(45.94, 25.45)
        d_b = _cems(45.95, 25.46)
        result = correlator.correlate([d_a, d_b], _NOW)[0]
        assert result.canonical_incident_category == "wildfire"
        assert result.relationship_type == "supporting_evidence"


class TestDegradedSourceAndApi:
    @pytest.mark.anyio
    async def test_degraded_does_not_fabricate_correlations(self):
        correlator = CrossSourceCorrelator()
        assert correlator.correlate([], _NOW) == []

    @pytest.mark.anyio
    async def test_degraded_sources_indicator(self):
        health_repo = AsyncMock()
        health_repo.list_all = AsyncMock(
            return_value=[
                {
                    "provider_id": "eea.air_quality",
                    "display_name": "EEA",
                    "current_status": ProviderHealthStatus.FAILED.value,
                }
            ]
        )
        settings = MagicMock()
        settings.geographic_scope = "romania"
        settings.enable_eea_air_quality = True
        settings.enable_cems_rapid_mapping = False
        svc = SourceIntelligenceService(health_repo, settings=settings, ingestion_providers=[])
        assert len(await svc.get_degraded_sources()) == 1

    def test_correlations_api_read_only(self):
        svc = MagicMock()
        svc.list_correlations = AsyncMock(return_value={"correlations": [], "total": 0})
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = _mock_user
        app.dependency_overrides[correlation_service_dep] = lambda: svc
        client = TestClient(app)
        assert client.get("/analytics/intelligence/correlations").status_code == 200
        svc.list_correlations.assert_awaited_once()

    @pytest.mark.anyio
    async def test_read_model_no_credentials(self):
        repo = InMemoryCorrelationRepo()
        results = CrossSourceCorrelator().correlate(
            [_firms(45.94, 25.45), _eea(45.941, 25.451)],
            _NOW,
        )
        await repo.replace_all([r.as_dict() for r in results])
        payload = await CorrelationService(repo).list_correlations()
        assert "api_key" not in str(payload)


class TestCommandQuerySeparation:
    def test_get_routes_no_correlation_side_effects(self):
        from tests.fixtures.intelligence_write_spy import (
            build_intelligence_read_client,
            iter_intelligence_get_routes,
        )

        client, spy = build_intelligence_read_client()
        for path, query in iter_intelligence_get_routes():
            assert client.get(path, params=query).status_code == 200
        spy.assert_no_persistence_or_reconciliation()


class TestPhase0Compatibility:
    def test_oracle_unchanged(self):
        verify_generated_match_manifest(generate_golden_artifacts())

    def test_ten_run_determinism(self):
        for _ in range(10):
            verify_generated_match_manifest(generate_golden_artifacts())
