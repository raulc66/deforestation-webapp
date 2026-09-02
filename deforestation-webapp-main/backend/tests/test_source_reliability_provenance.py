"""European Source Reliability & Provenance — source intelligence tests."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, source_intelligence_service_dep
from app.core.ingestion.correlation_key import observation_correlation_key
from app.core.ingestion.ingestion_metadata import build_ingestion_metadata
from app.core.ingestion.provenance import (
    build_detection_provenance,
    provenance_from_event_metadata,
    provenance_from_ingestion_metadata,
)
from app.core.ingestion.provider_health import ProviderHealthStatus, health_status_from_run
from app.core.ingestion.source_descriptor import SourceType, source_descriptor_from_describe
from app.core.ingestion.source_reliability import (
    ReliabilityDimensions,
    SourceReliabilityInput,
    compute_baseline_reliability_score,
    compute_baseline_reliability_score_legacy,
    firms_reliability_alert_trigger,
)
from app.models.user import UserPublic
from app.modules.analytics.analytics_routes import router
from app.modules.analytics.detection_adapters import detection_from_anomaly_dict
from app.modules.ingestion.providers.cems_rapid_mapping import CEMSRapidMappingProvider
from app.modules.ingestion.providers.eea_air_quality import EEAAirQualityProvider
from app.modules.ingestion.providers.firms import FIRMSProvider
from app.repositories.provider_health_repository import ProviderHealthRepository
from app.services.clms_context_provider import CLMSContextProvider
from app.services.scheduler_service import SchedulerService
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


def _make_scheduler_with_providers(
    providers: list,
    *,
    health_repo=None,
    analytics=None,
) -> tuple[SchedulerService, AsyncMock]:
    runs_repo = AsyncMock()
    runs_repo.create_run = AsyncMock(
        return_value={"status": "success", "duration_seconds": 0.1}
    )
    analytics = analytics or AsyncMock()
    analytics.reconcile_intelligence_events = AsyncMock(return_value={})
    firms = providers[0]
    svc = SchedulerService(
        firms_provider=firms,
        events_service=AsyncMock(),
        events_repo=AsyncMock(),
        analytics_service=analytics,
        intelligence_service=AsyncMock(),
        runs_repo=runs_repo,
        ingestion_providers=providers,
        health_repo=health_repo,
    )
    return svc, runs_repo


# ---------------------------------------------------------------------------
# 1. SourceDescriptor
# ---------------------------------------------------------------------------


class TestSourceDescriptor:
    def test_from_firms_describe(self):
        provider = FIRMSProvider(api_key="")
        desc = source_descriptor_from_describe(
            provider.describe(),
            incident_categories=provider.supported_incident_categories,
        )
        assert desc.provider_id == "nasa.firms"
        assert "wildfire" in desc.incident_categories
        assert desc.source_type == SourceType.OBSERVATION.value

    def test_from_eea_describe(self):
        provider = EEAAirQualityProvider()
        desc = source_descriptor_from_describe(
            provider.describe(),
            incident_categories=provider.supported_incident_categories,
        )
        assert desc.provider_id == "eea.air_quality"
        assert "air_quality" in desc.incident_categories

    def test_from_cems_describe(self):
        provider = CEMSRapidMappingProvider()
        desc = source_descriptor_from_describe(
            provider.describe(),
            incident_categories=provider.supported_incident_categories,
        )
        assert desc.provider_id == "cems.rapid_mapping"

    def test_from_clms_describe(self):
        provider = CLMSContextProvider()
        desc = source_descriptor_from_describe(
            provider.describe(),
            source_type=SourceType.CONTEXTUAL.value,
        )
        assert desc.provider_id == "clms.land_cover"
        assert "Europe" in desc.geographic_coverage


# ---------------------------------------------------------------------------
# 2–3. Provider health lifecycle
# ---------------------------------------------------------------------------


class TestProviderHealthLifecycle:
    def test_unknown_when_never_run(self):
        record = {"provider_id": "test", "current_status": ProviderHealthStatus.UNKNOWN.value}
        assert record["current_status"] == ProviderHealthStatus.UNKNOWN.value

    def test_success_telemetry_healthy(self):
        status = health_status_from_run(
            success=True,
            observations_rejected=0,
            observations_received=10,
            consecutive_failures=0,
            enabled=True,
        )
        assert status == ProviderHealthStatus.HEALTHY.value

    def test_failure_telemetry_degraded(self):
        status = health_status_from_run(
            success=False,
            observations_rejected=0,
            observations_received=0,
            consecutive_failures=1,
            enabled=True,
        )
        assert status == ProviderHealthStatus.DEGRADED.value

    def test_consecutive_failures_marks_failed(self):
        status = health_status_from_run(
            success=False,
            observations_rejected=0,
            observations_received=0,
            consecutive_failures=3,
            enabled=True,
        )
        assert status == ProviderHealthStatus.FAILED.value

    def test_recovery_after_failure_status(self):
        status = health_status_from_run(
            success=True,
            observations_rejected=0,
            observations_received=5,
            consecutive_failures=0,
            enabled=True,
        )
        assert status == ProviderHealthStatus.HEALTHY.value

    def test_disabled_status(self):
        status = health_status_from_run(
            success=False,
            observations_rejected=0,
            observations_received=0,
            consecutive_failures=5,
            enabled=False,
        )
        assert status == ProviderHealthStatus.DISABLED.value

    def test_high_rejection_rate_degraded(self):
        status = health_status_from_run(
            success=True,
            observations_rejected=8,
            observations_received=10,
            consecutive_failures=0,
            enabled=True,
        )
        assert status == ProviderHealthStatus.DEGRADED.value


# ---------------------------------------------------------------------------
# 4. Provenance preservation
# ---------------------------------------------------------------------------


class TestProvenancePreservation:
    def test_ingestion_metadata_extended_fields(self):
        meta = build_ingestion_metadata(
            source="EEA Air Quality",
            source_event_id="RO001:PM2.5:2026",
            is_romania=True,
            confidence=0.9,
            severity="high",
            provider_id="eea.air_quality",
            dataset_id="eea.aq.e2a",
            provenance_label="monitoring_station",
        )
        assert meta.provider_id == "eea.air_quality"
        assert meta.dataset_id == "eea.aq.e2a"

    def test_provenance_from_ingestion_metadata(self):
        meta = build_ingestion_metadata(
            source="NASA FIRMS",
            source_event_id="firms-123",
            is_romania=True,
            confidence=0.85,
            severity="high",
            provider_id="nasa.firms",
        )
        prov = provenance_from_ingestion_metadata(meta, geographic_scope="romania")
        assert prov["provider_id"] == "nasa.firms"
        assert prov["geographic_scope"] == "romania"
        assert prov["ingested_at"] is not None

    def test_provenance_from_persisted_event(self):
        metadata = {
            "ingestion": {
                "source": "EEA Air Quality",
                "provider_id": "eea.air_quality",
                "source_event_id": "DE-BER:PM2.5",
                "ingestion_timestamp": _NOW.isoformat(),
            },
            "observation": {
                "observed_at": _NOW.isoformat(),
                "pollutant": "PM2.5",
                "station_id": "DE-BER-AQ01",
            },
        }
        prov = provenance_from_event_metadata(metadata, geographic_scope="europe")
        assert prov["domain_evidence"]["observation"]["pollutant"] == "PM2.5"

    def test_time_distinctions_in_detection_provenance(self):
        observed = _NOW.replace(hour=10)
        ingested = _NOW.replace(hour=11)
        detected = _NOW.replace(hour=12)
        prov = build_detection_provenance(
            {"observed_at": observed, "ingested_at": ingested},
            detected_at=detected,
            signal_type="baseline_deviation",
        )
        assert prov["observed_at"] != prov["domain_evidence"]["detected_at"]


# ---------------------------------------------------------------------------
# 5. Detection provenance
# ---------------------------------------------------------------------------


class TestDetectionProvenance:
    def test_firms_wildfire_provenance(self):
        detection = detection_from_anomaly_dict(
            {
                "region": "Suceava",
                "baseline_events": 2,
                "current_events": 8,
                "deviation_percent": 100.0,
                "anomaly_score": 0.7,
                "severity": "high",
            },
            detected_at=_NOW,
            incident_category="wildfire",
        )
        assert detection.evidence["provenance"]["domain_evidence"]["provider_class"] == (
            "satellite_fire_observations"
        )

    def test_eea_air_quality_provenance(self):
        detection = detection_from_anomaly_dict(
            {
                "region": "DE-BER-AQ01",
                "baseline_events": 2,
                "current_events": 8,
                "deviation_percent": 100.0,
                "anomaly_score": 0.7,
                "severity": "high",
                "station_id": "DE-BER-AQ01",
                "pollutant": "PM2.5",
            },
            detected_at=_NOW,
            incident_category="air_quality",
        )
        prov = detection.evidence["provenance"]
        assert prov["domain_evidence"]["station_id"] == "DE-BER-AQ01"
        assert prov["domain_evidence"]["pollutant"] == "PM2.5"

    def test_cems_hazard_provenance(self):
        detection = detection_from_anomaly_dict(
            {
                "region": "Romania",
                "baseline_events": 1,
                "current_events": 4,
                "deviation_percent": 300.0,
                "anomaly_score": 0.8,
                "severity": "high",
                "country": "Romania",
                "hazard_type": "wildfire",
                "activation_code": "EMSR-RO-01",
            },
            detected_at=_NOW,
            incident_category="environmental_hazard",
        )
        prov = detection.evidence["provenance"]
        assert prov["domain_evidence"]["activation_code"] == "EMSR-RO-01"


# ---------------------------------------------------------------------------
# 6. Reliability abstraction
# ---------------------------------------------------------------------------


class TestReliabilityAbstraction:
    def test_legacy_formula_unchanged(self):
        score = compute_baseline_reliability_score_legacy(
            0.8, 10, 6, {"low": 0, "medium": 4, "high": 6, "critical": 0}
        )
        assert score == pytest.approx(0.704, abs=0.001)

    def test_generalized_input_interface(self):
        score = compute_baseline_reliability_score(
            SourceReliabilityInput(
                average_confidence=0.8,
                total_events=10,
                in_scope_events=6,
                severity_distribution={"low": 0, "medium": 4, "high": 6, "critical": 0},
                dimensions=ReliabilityDimensions(freshness=0.9),
            )
        )
        assert score == pytest.approx(0.704, abs=0.001)

    def test_firms_alert_trigger_isolated(self):
        rows = [
            {"source": "NASA FIRMS", "total_events": 40, "reliability_score": 0.8},
            {"source": "EEA Air Quality", "total_events": 10, "reliability_score": 0.5},
        ]
        assert firms_reliability_alert_trigger(rows) is True


# ---------------------------------------------------------------------------
# 7. Correlation readiness
# ---------------------------------------------------------------------------


class TestCorrelationReadiness:
    def test_correlation_key_from_location_time(self):
        key = observation_correlation_key(
            incident_category="wildfire",
            latitude=45.94,
            longitude=25.45,
            observed_at=_NOW,
        )
        assert key.startswith("wildfire:45.94:25.45:")

    def test_correlation_key_none_without_coords(self):
        assert (
            observation_correlation_key(
                incident_category="air_quality",
                latitude=None,
                longitude=None,
                observed_at=_NOW,
            )
            is None
        )


# ---------------------------------------------------------------------------
# 8. Provider failure isolation
# ---------------------------------------------------------------------------


class TestProviderFailureIsolation:
    @pytest.mark.anyio
    async def test_firms_failure_eea_success(self):
        firms = AsyncMock()
        firms.source_name = "NASA FIRMS"
        firms.provider_id = "nasa.firms"
        firms.describe = MagicMock(
            return_value={"source": "NASA FIRMS", "provider_id": "nasa.firms"}
        )
        firms.run = AsyncMock(side_effect=RuntimeError("FIRMS down"))

        eea = AsyncMock()
        eea.source_name = "EEA Air Quality"
        eea.provider_id = "eea.air_quality"
        eea.describe = MagicMock(
            return_value={"source": "EEA Air Quality", "provider_id": "eea.air_quality"}
        )
        eea.run = AsyncMock(return_value={"total": 3, "created": 2, "skipped": 1, "errors": 0})

        analytics = AsyncMock()
        analytics.reconcile_intelligence_events = AsyncMock(return_value={})
        svc, _ = _make_scheduler_with_providers([firms, eea], analytics=analytics)
        await svc._run_cycle()
        eea.run.assert_awaited_once()
        analytics.reconcile_intelligence_events.assert_awaited_once()

    @pytest.mark.anyio
    async def test_eea_failure_cems_success(self):
        firms = AsyncMock()
        firms.source_name = "NASA FIRMS"
        firms.provider_id = "nasa.firms"
        firms.describe = MagicMock(
            return_value={"source": "NASA FIRMS", "provider_id": "nasa.firms"}
        )
        firms.run = AsyncMock(return_value={"total": 1, "created": 1, "skipped": 0, "errors": 0})

        eea = AsyncMock()
        eea.source_name = "EEA Air Quality"
        eea.provider_id = "eea.air_quality"
        eea.describe = MagicMock(
            return_value={"source": "EEA Air Quality", "provider_id": "eea.air_quality"}
        )
        eea.run = AsyncMock(side_effect=TimeoutError("EEA timeout"))

        cems = AsyncMock()
        cems.source_name = "Copernicus EMS"
        cems.provider_id = "cems.rapid_mapping"
        cems.describe = MagicMock(
            return_value={"source": "Copernicus EMS", "provider_id": "cems.rapid_mapping"}
        )
        cems.run = AsyncMock(return_value={"total": 5, "created": 3, "skipped": 2, "errors": 0})

        svc, runs_repo = _make_scheduler_with_providers([firms, eea, cems])
        await svc._run_cycle()
        cems.run.assert_awaited_once()
        assert runs_repo.create_run.call_count >= 4  # 3 providers + cycle summary

    @pytest.mark.anyio
    async def test_cems_failure_firms_success(self):
        firms = AsyncMock()
        firms.source_name = "NASA FIRMS"
        firms.provider_id = "nasa.firms"
        firms.describe = MagicMock(
            return_value={"source": "NASA FIRMS", "provider_id": "nasa.firms"}
        )
        firms.run = AsyncMock(return_value={"total": 2, "created": 2, "skipped": 0, "errors": 0})

        cems = AsyncMock()
        cems.source_name = "Copernicus EMS"
        cems.provider_id = "cems.rapid_mapping"
        cems.describe = MagicMock(
            return_value={"source": "Copernicus EMS", "provider_id": "cems.rapid_mapping"}
        )
        cems.run = AsyncMock(side_effect=ConnectionError("CEMS down"))

        svc, _ = _make_scheduler_with_providers([firms, cems])
        await svc._run_cycle()
        firms.run.assert_awaited_once()

    @pytest.mark.anyio
    async def test_all_providers_failing(self):
        def _fail_provider(name: str, pid: str) -> AsyncMock:
            p = AsyncMock()
            p.source_name = name
            p.provider_id = pid
            p.describe = MagicMock(return_value={"source": name, "provider_id": pid})
            p.run = AsyncMock(side_effect=RuntimeError(f"{name} down"))
            return p

        providers = [
            _fail_provider("NASA FIRMS", "nasa.firms"),
            _fail_provider("EEA Air Quality", "eea.air_quality"),
        ]
        analytics = AsyncMock()
        analytics.reconcile_intelligence_events = AsyncMock(return_value={})
        svc, runs_repo = _make_scheduler_with_providers(providers, analytics=analytics)
        await svc._run_cycle()
        analytics.reconcile_intelligence_events.assert_awaited_once()
        cycle_call = runs_repo.create_run.call_args_list[-1].kwargs
        assert cycle_call["provider_id"] == "scheduler.cycle"

    @pytest.mark.anyio
    async def test_health_state_isolated_per_provider(self):
        health_col = MagicMock()
        health_col.find_one = AsyncMock(return_value=None)
        health_col.update_one = AsyncMock()
        health_col.find = MagicMock(return_value=AsyncMock(__aiter__=lambda s: iter([])))

        db = MagicMock()
        db.__getitem__ = MagicMock(return_value=health_col)
        health_repo = ProviderHealthRepository(db)

        firms = AsyncMock()
        firms.source_name = "NASA FIRMS"
        firms.provider_id = "nasa.firms"
        firms.describe = MagicMock(
            return_value={"source": "NASA FIRMS", "provider_id": "nasa.firms"}
        )
        firms.run = AsyncMock(side_effect=RuntimeError("fail"))

        eea = AsyncMock()
        eea.source_name = "EEA Air Quality"
        eea.provider_id = "eea.air_quality"
        eea.describe = MagicMock(
            return_value={"source": "EEA Air Quality", "provider_id": "eea.air_quality"}
        )
        eea.run = AsyncMock(return_value={"total": 2, "created": 2, "skipped": 0, "errors": 0})

        svc, _ = _make_scheduler_with_providers([firms, eea], health_repo=health_repo)
        await svc._run_cycle()
        assert health_col.update_one.call_count >= 2


# ---------------------------------------------------------------------------
# 9. Geographic scope vs provider coverage
# ---------------------------------------------------------------------------


class TestGeographicScopeVsProviderCoverage:
    def test_descriptor_coverage_not_romania_only_for_europe_providers(self):
        eea = EEAAirQualityProvider()
        desc = source_descriptor_from_describe(
            eea.describe(),
            incident_categories=eea.supported_incident_categories,
        )
        assert "Romania" not in desc.geographic_coverage or "Europe" in desc.geographic_coverage

    @pytest.mark.anyio
    async def test_source_status_includes_scope_not_provider_label(self):
        health_repo = AsyncMock()
        health_repo.list_all = AsyncMock(return_value=[])
        settings = MagicMock()
        settings.geographic_scope = "romania"
        settings.enable_eea_air_quality = True
        settings.enable_cems_rapid_mapping = True

        firms = FIRMSProvider(api_key="")
        svc = SourceIntelligenceService(
            health_repo,
            settings=settings,
            ingestion_providers=[firms, EEAAirQualityProvider()],
        )
        status = await svc.get_source_status()
        assert status["geographic_scope"] == "romania"
        eea_entry = next(s for s in status["sources"] if s["provider_id"] == "eea.air_quality")
        assert "Romania-only" not in eea_entry.get("geographic_coverage", "")


# ---------------------------------------------------------------------------
# 10–11. Command Center + API
# ---------------------------------------------------------------------------


class TestCommandCenterSourceStatus:
    @pytest.mark.anyio
    async def test_health_summary_shape(self):
        health_repo = AsyncMock()
        health_repo.list_all = AsyncMock(
            return_value=[
                {
                    "provider_id": "nasa.firms",
                    "display_name": "NASA FIRMS",
                    "current_status": "healthy",
                    "last_success_at": _NOW,
                    "last_failure_at": None,
                }
            ]
        )
        settings = MagicMock()
        settings.geographic_scope = "romania"
        settings.enable_eea_air_quality = False
        settings.enable_cems_rapid_mapping = False
        svc = SourceIntelligenceService(
            health_repo,
            settings=settings,
            ingestion_providers=[FIRMSProvider(api_key="")],
        )
        summary = await svc.get_health_summary()
        assert summary[0]["provider_id"] == "nasa.firms"
        assert "incident_categories" in summary[0]


class TestSourceStatusApi:
    def test_read_only_no_side_effects(self):
        source_intel = MagicMock()
        source_intel.get_source_status = AsyncMock(
            return_value={"sources": [], "geographic_scope": "romania"}
        )

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = _mock_user
        app.dependency_overrides[source_intelligence_service_dep] = lambda: source_intel

        client = TestClient(app)
        resp = client.get("/analytics/intelligence/source-status")
        assert resp.status_code == 200
        source_intel.get_source_status.assert_awaited_once()

    def test_no_credential_leakage(self):
        health_repo = AsyncMock()
        health_repo.list_all = AsyncMock(
            return_value=[
                {
                    "provider_id": "nasa.firms",
                    "display_name": "NASA FIRMS",
                    "current_status": "healthy",
                    "last_success_at": _NOW,
                    "api_key": "SECRET",
                    "password": "SECRET",
                }
            ]
        )
        settings = MagicMock()
        settings.geographic_scope = "romania"
        settings.enable_eea_air_quality = False
        settings.enable_cems_rapid_mapping = False

        async def _run():
            svc = SourceIntelligenceService(
                health_repo,
                settings=settings,
                ingestion_providers=[FIRMSProvider(api_key="secret-key")],
            )
            return await svc.get_source_status()

        status = asyncio.run(_run())
        health = status["sources"][0].get("health") or {}
        assert "api_key" not in health
        assert "password" not in health
        assert "secret-key" not in str(status)


# ---------------------------------------------------------------------------
# 12. Scheduler telemetry
# ---------------------------------------------------------------------------


class TestSchedulerTelemetry:
    @pytest.mark.anyio
    async def test_per_provider_run_records_provider_id(self):
        firms = AsyncMock()
        firms.source_name = "NASA FIRMS"
        firms.provider_id = "nasa.firms"
        firms.describe = MagicMock(
            return_value={"source": "NASA FIRMS", "provider_id": "nasa.firms"}
        )
        firms.run = AsyncMock(return_value={"total": 4, "created": 2, "skipped": 2, "errors": 0})

        svc, runs_repo = _make_scheduler_with_providers([firms])
        await svc._run_cycle()

        provider_call = runs_repo.create_run.call_args_list[0].kwargs
        cycle_call = runs_repo.create_run.call_args_list[-1].kwargs
        assert provider_call["provider_id"] == "nasa.firms"
        assert cycle_call["provider_id"] == "scheduler.cycle"
        assert cycle_call["source"] == "scheduler.cycle"


# ---------------------------------------------------------------------------
# 13. Provider compatibility (CLMS / Weather)
# ---------------------------------------------------------------------------


class TestContextualProviderCompatibility:
    def test_clms_descriptor_contextual_type(self):
        provider = CLMSContextProvider()
        desc = source_descriptor_from_describe(
            provider.describe(),
            source_type=SourceType.CONTEXTUAL.value,
        )
        assert desc.source_type == SourceType.CONTEXTUAL.value
        assert desc.dataset_id == "clms.corine_land_cover"

    def test_open_meteo_in_source_intelligence(self):
        health_repo = AsyncMock()
        health_repo.list_all = AsyncMock(return_value=[])
        settings = MagicMock()
        settings.geographic_scope = "romania"
        settings.enable_eea_air_quality = False
        settings.enable_cems_rapid_mapping = False
        svc = SourceIntelligenceService(health_repo, settings=settings, ingestion_providers=[])
        descriptors = svc._build_descriptors()
        meteo = next(d for d in descriptors if d.provider_id == "open_meteo.weather")
        assert meteo.source_type == SourceType.METEOROLOGICAL.value


# ---------------------------------------------------------------------------
# 14. Phase 0 + determinism
# ---------------------------------------------------------------------------


class TestPhase0Compatibility:
    def test_oracle_unchanged(self):
        verify_generated_match_manifest(generate_golden_artifacts())

    def test_ten_run_determinism(self):
        """Ten consecutive golden generations must match the frozen manifest."""
        for _ in range(10):
            verify_generated_match_manifest(generate_golden_artifacts())
