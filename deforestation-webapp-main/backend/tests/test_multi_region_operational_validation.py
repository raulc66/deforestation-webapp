"""Multi-region operational validation and evidence loop hardening tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import (
    analytics_service_dep,
    aoi_enrichment_service_dep,
    evidence_aware_command_center_dep,
    get_current_user,
    get_organization_context,
    intelligence_events_service_dep,
    monitoring_area_service_dep,
    operational_status_service_dep,
)
from app.core.organization.organization_context import OrganizationContext
from app.core.config import Settings
from app.core.ecosystem.intelligence_event_defaults import DEFAULT_SIGNAL_TYPE
from app.core.geography.geographic_scope import GeographicScope, GeographicScopePolicy
from app.core.ingestion.provider_health import ProviderHealthStatus, health_status_from_run
from app.modules.analytics.analytics_routes import router
from app.modules.analytics.analytics_service import _compute_baselines
from app.modules.analytics.correlation_config import build_correlation_config
from app.modules.analytics.cross_source_correlator import CrossSourceCorrelator
from app.modules.analytics.correlation_result import CorrelationParticipant, CorrelationResult
from app.modules.analytics.detection_contract import Detection
from app.modules.analytics.evidence_summary import (
    build_evidence_summary,
    build_intelligence_evidence_payload,
    resolve_correlation_state,
)
from app.modules.analytics.intelligence_cycle import detection_fingerprint, resolve_intelligence_cycle_id
from app.modules.analytics.map_contract import (
    attach_region_centroid,
    forest_event_map_marker,
    intelligence_event_map_marker,
)
from app.modules.analytics.provenance_persistence import sanitize_provenance_envelope
from app.modules.analytics.segmented_baseline import aggregate_regional_baselines_by_category
from app.modules.ingestion.provider_execution_mode import resolve_provider_execution_mode
from app.services.evidence_aware_command_center_service import EvidenceAwareCommandCenterService
from app.services.operational_status_service import OperationalStatusService
from app.services.scheduler_service import SchedulerService
from fixtures.multi_region_operational_fixture import (
    build_multi_region_events,
    events_in_scope,
    reference_now,
)
from fixtures.multi_region_validation_report import (
    build_validation_report,
    verify_report_matches_golden,
)
from fixtures.phase0_golden_fixture import build_wildfire_events
from fixtures.phase0_golden_harness import generate_golden_artifacts
from fixtures.phase0_oracle_manifest import verify_generated_match_manifest

_NOW = reference_now()


def _settings(**overrides) -> Settings:
    base = {
        "mongo_url": "mongodb://localhost:27017",
        "db_name": "test",
        "jwt_secret": "secret",
        "admin_email": "admin@test.com",
        "admin_password": "pass",
        "frontend_url": "http://localhost:3000",
    }
    base.update(overrides)
    return Settings(**base)


def _detection(
    *,
    category: str,
    provider_id: str,
    provider_class: str,
    lat: float,
    lng: float,
    region: str,
    spatial_key: str | None = None,
    detected_at: datetime | None = None,
    hazard_type: str | None = None,
) -> Detection:
    key = spatial_key or region
    domain_evidence = {
        "provider_class": provider_class,
        "detection_method": DEFAULT_SIGNAL_TYPE,
    }
    if hazard_type:
        domain_evidence["hazard_type"] = hazard_type
    return Detection(
        spatial_key=key,
        incident_category=category,
        signal_type="baseline_deviation",
        severity="high",
        score=0.75,
        detected_at=detected_at or _NOW,
        evidence={
            "region": region,
            "latitude": lat,
            "longitude": lng,
            "hazard_type": hazard_type,
            "country": "Romania" if region in {"Suceava", "Romania"} else region,
            "provenance": {
                "provider_id": provider_id,
                "source_event_id": f"{provider_id}-{key}",
                "domain_evidence": domain_evidence,
            },
        },
    )


class TestGeographicScopeValidation:
    def test_romania_scope(self):
        events = build_multi_region_events()
        scoped = events_in_scope(events, "romania")
        countries = {e["country"] for e in scoped}
        assert "Romania" in countries
        assert "Germany" not in countries
        assert "Brazil" not in countries

    def test_europe_scope(self):
        events = build_multi_region_events()
        scoped = events_in_scope(events, "europe")
        countries = {e["country"] for e in scoped}
        assert {"Romania", "Germany", "Italy", "Spain", "France", "Poland"}.issubset(countries)
        assert "Brazil" not in countries

    def test_all_scope_includes_out_of_scope_event(self):
        events = build_multi_region_events()
        scoped = events_in_scope(events, "all")
        assert any(e["country"] == "Brazil" for e in scoped)

    def test_provider_coverage_differs_from_configured_scope(self):
        settings = _settings(geographic_scope="romania", enable_eea_air_quality=True)
        mode = resolve_provider_execution_mode(
            provider_id="eea.air_quality",
            enabled=True,
            settings=settings,
            health={"last_execution_mode": "live"},
            last_run={"status": "success"},
            describe={"live_access_status": "token_configured", "geographic_coverage": "Europe"},
        )
        assert mode == "live"
        assert settings.geographic_scope == "romania"


class TestMultiCountryBaselineIsolation:
    def test_country_baselines_isolated(self):
        events = build_multi_region_events()
        rows = aggregate_regional_baselines_by_category(
            events,
            _NOW,
            scope_policy=GeographicScopePolicy(GeographicScope.EUROPE),
        )
        regions = {(r["_id"]["region"], r["_id"]["incident_category"]) for r in rows}
        assert ("Bavaria", "wildfire") in regions
        assert ("Suceava", "wildfire") in regions
        assert ("DE-MUC-AQ01", "air_quality") in regions
        assert ("RO-BUC-AQ01", "air_quality") in regions

    def test_phase0_wildfire_unchanged(self):
        events = build_wildfire_events()
        rows = aggregate_regional_baselines_by_category(events, _NOW)
        regions = {r["_id"]["region"] for r in rows if r["_id"]["incident_category"] == "wildfire"}
        assert "Suceava" in regions


class TestProviderFailureIsolation:
    def _scheduler(self, providers, reconcile):
        firms = providers[0]
        runs_repo = MagicMock()
        runs_repo.create_run = AsyncMock(return_value={"status": "failed", "duration_seconds": 0.1})
        return SchedulerService(
            firms_provider=firms,
            events_service=MagicMock(),
            events_repo=MagicMock(),
            analytics_service=MagicMock(reconcile_intelligence_events=reconcile),
            intelligence_service=MagicMock(),
            runs_repo=runs_repo,
            enabled=True,
            ingestion_providers=providers,
            reconciliation_lock=MagicMock(try_acquire=AsyncMock(return_value=True), release=AsyncMock()),
        )

    @pytest.mark.anyio
    async def test_all_providers_success_reconciliation_runs(self):
        def _ok(name, pid):
            p = MagicMock()
            p.source_name = name
            p.provider_id = pid
            p.describe = MagicMock(return_value={"source": name})
            p.run = AsyncMock(return_value={"total": 1, "created": 1, "skipped": 0, "errors": 0})
            return p

        reconcile = AsyncMock()
        scheduler = self._scheduler(
            [
                _ok("NASA FIRMS", "nasa.firms"),
                _ok("EEA Air Quality", "eea.air_quality"),
                _ok("Copernicus EMS", "cems.rapid_mapping"),
            ],
            reconcile,
        )
        await scheduler._run_cycle()
        reconcile.assert_awaited_once()
        for provider in scheduler._ingestion_providers:
            provider.run.assert_awaited_once()

    @pytest.mark.anyio
    async def test_scheduler_passes_cycle_id_to_reconciliation(self):
        def _ok(name, pid):
            p = MagicMock()
            p.source_name = name
            p.provider_id = pid
            p.describe = MagicMock(return_value={"source": name})
            p.run = AsyncMock(return_value={"total": 1, "created": 1, "skipped": 0, "errors": 0})
            return p

        reconcile = AsyncMock()
        scheduler = self._scheduler(
            [
                _ok("NASA FIRMS", "nasa.firms"),
                _ok("EEA Air Quality", "eea.air_quality"),
                _ok("Copernicus EMS", "cems.rapid_mapping"),
            ],
            reconcile,
        )
        await scheduler._run_cycle()
        _, kwargs = reconcile.call_args
        cycle_id = kwargs.get("intelligence_cycle_id")
        assert cycle_id is not None
        assert len(cycle_id) == 36
        firms = MagicMock()
        firms.source_name = "NASA FIRMS"
        firms.provider_id = "nasa.firms"
        firms.describe = MagicMock(return_value={"source": "NASA FIRMS"})
        firms.run = AsyncMock(side_effect=RuntimeError("FIRMS down"))
        eea = MagicMock()
        eea.source_name = "EEA Air Quality"
        eea.provider_id = "eea.air_quality"
        eea.describe = MagicMock(return_value={"source": "EEA Air Quality"})
        eea.run = AsyncMock(return_value={"total": 1, "created": 1, "skipped": 0, "errors": 0})
        cems = MagicMock()
        cems.source_name = "Copernicus EMS"
        cems.provider_id = "cems.rapid_mapping"
        cems.describe = MagicMock(return_value={"source": "Copernicus EMS"})
        cems.run = AsyncMock(return_value={"total": 1, "created": 1, "skipped": 0, "errors": 0})
        reconcile = AsyncMock()
        scheduler = self._scheduler([firms, eea, cems], reconcile)
        await scheduler._run_cycle()
        eea.run.assert_awaited_once()
        cems.run.assert_awaited_once()
        reconcile.assert_awaited_once()

    @pytest.mark.anyio
    async def test_eea_failure_firms_cems_continue(self):
        firms = MagicMock()
        firms.source_name = "NASA FIRMS"
        firms.provider_id = "nasa.firms"
        firms.describe = MagicMock(return_value={"source": "NASA FIRMS"})
        firms.run = AsyncMock(return_value={"total": 1, "created": 1, "skipped": 0, "errors": 0})
        eea = MagicMock()
        eea.source_name = "EEA Air Quality"
        eea.provider_id = "eea.air_quality"
        eea.describe = MagicMock(return_value={"source": "EEA Air Quality"})
        eea.run = AsyncMock(side_effect=RuntimeError("EEA down"))
        cems = MagicMock()
        cems.source_name = "Copernicus EMS"
        cems.provider_id = "cems.rapid_mapping"
        cems.describe = MagicMock(return_value={"source": "Copernicus EMS"})
        cems.run = AsyncMock(return_value={"total": 1, "created": 1, "skipped": 0, "errors": 0})
        reconcile = AsyncMock()
        scheduler = self._scheduler([firms, eea, cems], reconcile)
        await scheduler._run_cycle()
        firms.run.assert_awaited_once()
        cems.run.assert_awaited_once()
        reconcile.assert_awaited_once()

    @pytest.mark.anyio
    async def test_cems_failure_firms_eea_continue(self):
        firms = MagicMock()
        firms.source_name = "NASA FIRMS"
        firms.provider_id = "nasa.firms"
        firms.describe = MagicMock(return_value={"source": "NASA FIRMS"})
        firms.run = AsyncMock(return_value={"total": 1, "created": 1, "skipped": 0, "errors": 0})
        eea = MagicMock()
        eea.source_name = "EEA Air Quality"
        eea.provider_id = "eea.air_quality"
        eea.describe = MagicMock(return_value={"source": "EEA Air Quality"})
        eea.run = AsyncMock(return_value={"total": 1, "created": 1, "skipped": 0, "errors": 0})
        cems = MagicMock()
        cems.source_name = "Copernicus EMS"
        cems.provider_id = "cems.rapid_mapping"
        cems.describe = MagicMock(return_value={"source": "Copernicus EMS"})
        cems.run = AsyncMock(side_effect=RuntimeError("CEMS down"))
        reconcile = AsyncMock()
        scheduler = self._scheduler([firms, eea, cems], reconcile)
        await scheduler._run_cycle()
        firms.run.assert_awaited_once()
        eea.run.assert_awaited_once()
        reconcile.assert_awaited_once()

    @pytest.mark.anyio
    async def test_all_providers_fail_reconciliation_still_runs(self):
        def _fail(name, pid):
            p = MagicMock()
            p.source_name = name
            p.provider_id = pid
            p.describe = MagicMock(return_value={"source": name})
            p.run = AsyncMock(side_effect=RuntimeError(f"{name} down"))
            return p

        reconcile = AsyncMock()
        scheduler = self._scheduler(
            [_fail("NASA FIRMS", "nasa.firms"), _fail("EEA Air Quality", "eea.air_quality"), _fail("Copernicus EMS", "cems.rapid_mapping")],
            reconcile,
        )
        await scheduler._run_cycle()
        reconcile.assert_awaited_once()


class TestExecutionModeObservability:
    def test_eea_live_from_health_not_token_only(self):
        settings = _settings(eea_aq_api_token="a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        assert resolve_provider_execution_mode(
            provider_id="eea.air_quality",
            enabled=True,
            settings=settings,
            health={"last_execution_mode": "fixture"},
            last_run={"status": "success"},
            describe={},
        ) == "fixture"

    def test_disabled_provider(self):
        settings = _settings(enable_eea_air_quality=False)
        assert resolve_provider_execution_mode(
            provider_id="eea.air_quality",
            enabled=False,
            settings=settings,
            health=None,
            last_run=None,
            describe={},
        ) == "disabled"


class TestCrossSourceCorrelation:
    def _correlator(self) -> CrossSourceCorrelator:
        return CrossSourceCorrelator(build_correlation_config())

    def test_firms_eea(self):
        dets = [
            _detection(category="wildfire", provider_id="nasa.firms", provider_class="satellite_fire_observations", lat=44.4, lng=26.1, region="Suceava"),
            _detection(category="air_quality", provider_id="eea.air_quality", provider_class="eea_air_quality", lat=44.4268, lng=26.1025, region="RO-BUC-AQ01", spatial_key="aq-station:RO-BUC-AQ01"),
        ]
        results = self._correlator().correlate(dets, _NOW)
        assert any(r.correlation_rule == "firms_eea_contextual" for r in results)

    def test_firms_cems(self):
        dets = [
            _detection(category="wildfire", provider_id="nasa.firms", provider_class="satellite_fire_observations", lat=47.6, lng=26.2, region="Suceava"),
            _detection(
                category="environmental_hazard",
                provider_id="cems.rapid_mapping",
                provider_class="cems_rapid_mapping",
                lat=47.6353,
                lng=26.259,
                region="Romania",
                spatial_key="cems-country:Romania",
                hazard_type="wildfire",
            ),
        ]
        results = self._correlator().correlate(dets, _NOW, geographic_scope="europe")
        assert any(r.correlation_rule == "firms_cems_wildfire_support" for r in results)

    def test_eea_cems(self):
        dets = [
            _detection(category="air_quality", provider_id="eea.air_quality", provider_class="eea_air_quality", lat=48.1374, lng=11.5755, region="DE-MUC-AQ01"),
            _detection(category="environmental_hazard", provider_id="cems.rapid_mapping", provider_class="cems_rapid_mapping", lat=48.1374, lng=11.5755, region="Germany", spatial_key="cems-country:Germany", hazard_type="Storm"),
        ]
        results = self._correlator().correlate(dets, _NOW, geographic_scope="europe")
        assert any(r.correlation_rule == "eea_cems_multi_source" for r in results)

    def test_firms_cems_spatial_rejection(self):
        dets = [
            _detection(category="wildfire", provider_id="nasa.firms", provider_class="satellite_fire_observations", lat=45.0, lng=25.0, region="Suceava"),
            _detection(
                category="environmental_hazard",
                provider_id="cems.rapid_mapping",
                provider_class="cems_rapid_mapping",
                lat=47.6353,
                lng=26.259,
                region="Romania",
                spatial_key="cems-country:Romania",
                hazard_type="wildfire",
            ),
        ]
        assert not any(
            r.correlation_rule == "firms_cems_wildfire_support"
            for r in self._correlator().correlate(dets, _NOW, geographic_scope="europe")
        )

    def test_firms_cems_temporal_rejection(self):
        dets = [
            _detection(
                category="wildfire",
                provider_id="nasa.firms",
                provider_class="satellite_fire_observations",
                lat=47.6,
                lng=26.2,
                region="Suceava",
                detected_at=_NOW - timedelta(hours=100),
            ),
            _detection(
                category="environmental_hazard",
                provider_id="cems.rapid_mapping",
                provider_class="cems_rapid_mapping",
                lat=47.6353,
                lng=26.259,
                region="Romania",
                spatial_key="cems-country:Romania",
                hazard_type="wildfire",
            ),
        ]
        assert not any(
            r.correlation_rule == "firms_cems_wildfire_support"
            for r in self._correlator().correlate(dets, _NOW, geographic_scope="europe")
        )

    def test_eea_cems_spatial_rejection(self):
        dets = [
            _detection(category="air_quality", provider_id="eea.air_quality", provider_class="eea_air_quality", lat=48.1374, lng=11.5755, region="DE-MUC-AQ01"),
            _detection(
                category="environmental_hazard",
                provider_id="cems.rapid_mapping",
                provider_class="cems_rapid_mapping",
                lat=41.9028,
                lng=12.4964,
                region="Italy",
                spatial_key="cems-country:Italy",
                hazard_type="Storm",
            ),
        ]
        assert not any(
            r.correlation_rule == "eea_cems_multi_source"
            for r in self._correlator().correlate(dets, _NOW, geographic_scope="europe")
        )

    def test_eea_cems_temporal_rejection(self):
        dets = [
            _detection(
                category="air_quality",
                provider_id="eea.air_quality",
                provider_class="eea_air_quality",
                lat=48.1374,
                lng=11.5755,
                region="DE-MUC-AQ01",
                detected_at=_NOW - timedelta(hours=100),
            ),
            _detection(
                category="environmental_hazard",
                provider_id="cems.rapid_mapping",
                provider_class="cems_rapid_mapping",
                lat=48.1374,
                lng=11.5755,
                region="Germany",
                spatial_key="cems-country:Germany",
                hazard_type="Storm",
            ),
        ]
        assert not any(
            r.correlation_rule == "eea_cems_multi_source"
            for r in self._correlator().correlate(dets, _NOW, geographic_scope="europe")
        )

    def test_spatial_rejection(self):
        dets = [
            _detection(category="wildfire", provider_id="nasa.firms", provider_class="satellite_fire_observations", lat=45.0, lng=25.0, region="Suceava"),
            _detection(category="air_quality", provider_id="eea.air_quality", provider_class="eea_air_quality", lat=44.4268, lng=26.1025, region="RO-BUC-AQ01"),
        ]
        assert not any(r.correlation_rule == "firms_eea_contextual" for r in self._correlator().correlate(dets, _NOW))

    def test_temporal_rejection(self):
        dets = [
            _detection(category="wildfire", provider_id="nasa.firms", provider_class="satellite_fire_observations", lat=44.4, lng=26.1, region="Suceava", detected_at=_NOW - timedelta(hours=100)),
            _detection(category="air_quality", provider_id="eea.air_quality", provider_class="eea_air_quality", lat=44.4268, lng=26.1025, region="RO-BUC-AQ01"),
        ]
        assert not any(r.correlation_rule == "firms_eea_contextual" for r in self._correlator().correlate(dets, _NOW))

    def test_category_rejection(self):
        dets = [
            _detection(category="wildfire", provider_id="nasa.firms", provider_class="satellite_fire_observations", lat=44.4, lng=26.1, region="Suceava"),
            _detection(category="wildfire", provider_id="eea.air_quality", provider_class="eea_air_quality", lat=44.4268, lng=26.1025, region="RO-BUC-AQ01"),
        ]
        assert not any(r.correlation_rule == "firms_eea_contextual" for r in self._correlator().correlate(dets, _NOW))

    def test_deterministic_strength(self):
        dets = [
            _detection(category="wildfire", provider_id="nasa.firms", provider_class="satellite_fire_observations", lat=44.4, lng=26.1, region="Suceava"),
            _detection(category="air_quality", provider_id="eea.air_quality", provider_class="eea_air_quality", lat=44.4268, lng=26.1025, region="RO-BUC-AQ01"),
        ]
        results = self._correlator().correlate(dets, _NOW)
        assert results[0].strength == self._correlator().correlate(dets, _NOW)[0].strength

    def test_deterministic_correlation_id(self):
        dets = [
            _detection(category="wildfire", provider_id="nasa.firms", provider_class="satellite_fire_observations", lat=44.4, lng=26.1, region="Suceava"),
            _detection(category="air_quality", provider_id="eea.air_quality", provider_class="eea_air_quality", lat=44.4268, lng=26.1025, region="RO-BUC-AQ01"),
        ]
        first = self._correlator().correlate(dets, _NOW)
        second = self._correlator().correlate(dets, _NOW)
        assert [r.correlation_id for r in first] == [r.correlation_id for r in second]


class TestIntelligenceCycleConsistency:
    def test_detection_fingerprint_deterministic(self):
        dets = [
            _detection(category="wildfire", provider_id="nasa.firms", provider_class="satellite_fire_observations", lat=48.1351, lng=11.582, region="Bavaria"),
            _detection(category="air_quality", provider_id="eea.air_quality", provider_class="eea_air_quality", lat=48.1374, lng=11.5755, region="DE-MUC-AQ01"),
        ]
        fp1 = detection_fingerprint(dets)
        fp2 = detection_fingerprint(dets)
        assert fp1 == fp2
        assert resolve_intelligence_cycle_id("sched-cycle-1", fp1) == "sched-cycle-1"

    def test_current_state(self):
        assert resolve_correlation_state(
            correlation_enabled=True,
            current_cycle_id="cycle-a",
            correlation_cycle_id="cycle-a",
            has_correlations=True,
        ) == "current"

    def test_stale_state(self):
        assert resolve_correlation_state(
            correlation_enabled=True,
            current_cycle_id="cycle-b",
            correlation_cycle_id="cycle-a",
            has_correlations=True,
        ) == "stale"

    def test_unavailable_state(self):
        assert resolve_correlation_state(
            correlation_enabled=True,
            current_cycle_id="cycle-a",
            correlation_cycle_id=None,
            has_correlations=False,
        ) == "unavailable"

    def test_disabled_state(self):
        assert resolve_correlation_state(
            correlation_enabled=False,
            current_cycle_id="cycle-a",
            correlation_cycle_id="cycle-a",
            has_correlations=True,
        ) == "disabled"


class TestEvidenceStates:
    def _correlation(self, relationship: str = "supporting_evidence"):
        return CorrelationResult(
            correlation_id="corr-1",
            canonical_incident_category="wildfire",
            canonical_spatial_key="Suceava",
            relationship_type=relationship,
            correlation_rule="test_rule",
            participants=(
                CorrelationParticipant(
                    incident_category="wildfire",
                    spatial_key="Suceava",
                    provider_id="nasa.firms",
                    detected_at=_NOW,
                ),
                CorrelationParticipant(
                    incident_category="air_quality",
                    spatial_key="aq-station:RO-BUC-AQ01",
                    provider_id="eea.air_quality",
                    detected_at=_NOW,
                ),
            ),
            participating_provider_ids=("nasa.firms", "eea.air_quality"),
            spatial_relationship="nearby",
            temporal_relationship="same_window",
            strength=0.87,
            created_at=_NOW,
        )

    def test_single_source(self):
        summary = build_evidence_summary(
            {"incident_category": "wildfire", "region": "Suceava", "metadata": {}},
            correlations=[],
            correlation_state="disabled",
            health_by_provider={"nasa.firms": "healthy"},
        )
        assert summary.evidence_state == "single_source"

    def test_multi_source(self):
        summary = build_evidence_summary(
            {"incident_category": "wildfire", "region": "Suceava", "metadata": {}},
            correlations=[self._correlation("supporting_evidence")],
            correlation_state="current",
            health_by_provider={"nasa.firms": "healthy", "eea.air_quality": "healthy"},
        )
        assert summary.evidence_state == "multi_source"

    def test_contextual_support(self):
        summary = build_evidence_summary(
            {"incident_category": "wildfire", "region": "Suceava", "metadata": {}},
            correlations=[self._correlation("contextual_evidence")],
            correlation_state="current",
            health_by_provider={"nasa.firms": "healthy", "eea.air_quality": "healthy"},
        )
        assert summary.evidence_state == "contextual_support"

    def test_degraded_without_negative_evidence(self):
        summary = build_evidence_summary(
            {"incident_category": "wildfire", "region": "Suceava", "metadata": {}},
            correlations=[],
            correlation_state="disabled",
            health_by_provider={"nasa.firms": "failed", "eea.air_quality": "healthy"},
        )
        assert summary.evidence_state == "degraded_source"

    def test_unavailable_correlation_state(self):
        summary = build_evidence_summary(
            {"incident_category": "wildfire", "region": "Suceava", "metadata": {}},
            correlations=[],
            correlation_state="unavailable",
            health_by_provider={"nasa.firms": "healthy"},
        )
        assert summary.correlation_state == "unavailable"
        assert summary.evidence_state == "single_source"


class TestProvenanceSafety:
    def test_provenance_off(self):
        payload = build_intelligence_evidence_payload(
            [{"id": "1", "incident_category": "wildfire", "region": "Suceava", "metadata": {"provenance": {"provider_id": "nasa.firms", "api_key": "SECRET"}}}],
            correlations=[],
            cycle_state=None,
            correlation_enabled=False,
            include_provenance=False,
            health_rows=[],
        )
        assert payload["items"][0]["provenance"] == []

    def test_provenance_on_strips_credentials(self):
        cleaned = sanitize_provenance_envelope({"provider_id": "eea.air_quality", "api_key": "SECRET"})
        assert "api_key" not in cleaned

    def test_provenance_on_bounded_fields(self):
        payload = build_intelligence_evidence_payload(
            [{
                "id": "1",
                "incident_category": "air_quality",
                "region": "DE-MUC-AQ01",
                "metadata": {
                    "provenance": {
                        "provider_id": "eea.air_quality",
                        "source_id": "eea.air_quality",
                        "dataset_id": "eea.aq.e2a",
                        "dataset_version": "Raster1",
                        "source_event_id": "DE-MUC-AQ01:PM2.5:2026-06-10",
                        "observed_at": _NOW.isoformat(),
                        "detected_at": _NOW.isoformat(),
                        "geographic_scope": "Europe",
                        "raw_payload": {"secret": True},
                    }
                },
            }],
            correlations=[],
            cycle_state=None,
            correlation_enabled=False,
            include_provenance=True,
            health_rows=[],
        )
        prov = payload["items"][0]["provenance"][0]
        assert prov["provider_id"] == "eea.air_quality"
        assert "raw_payload" not in prov


class TestEuropeanMapCoordinates:
    @pytest.mark.parametrize("country", ["Romania", "Germany", "Italy", "Spain", "France", "Poland"])
    def test_authoritative_coordinates_by_country(self, country):
        event = next(e for e in build_multi_region_events() if e["country"] == country)
        marker = forest_event_map_marker({**event, "id": f"evt-{country}"})
        assert marker["latitude"] == pytest.approx(event["latitude"])
        assert marker["longitude"] == pytest.approx(event["longitude"])
        assert [marker["latitude"], marker["longitude"]] == [event["latitude"], event["longitude"]]

    def test_non_romanian_european_marker(self):
        event = next(e for e in build_multi_region_events() if e["country"] == "Germany")
        marker = forest_event_map_marker({**event, "id": "evt-de-wf"})
        assert marker["latitude"] == pytest.approx(48.1351)

    def test_eea_station_coordinates(self):
        event = build_multi_region_events()[1]
        marker = forest_event_map_marker({**event, "id": "evt-de"})
        assert marker["coordinate_source"] == "monitoring_station"
        assert marker["latitude"] == pytest.approx(44.4268)
        assert marker["longitude"] == pytest.approx(26.1025)
        assert [marker["latitude"], marker["longitude"]] == [44.4268, 26.1025]

    def test_cems_activation_coordinates(self):
        event = next(e for e in build_multi_region_events() if e["country"] == "Germany" and e["metadata"]["incident_category"] == "environmental_hazard")
        marker = forest_event_map_marker({**event, "id": "evt-cems-de"})
        assert marker["coordinate_source"] == "activation_centroid"
        assert marker["latitude"] == pytest.approx(48.1374)

    def test_no_romania_centroid_for_european_events(self):
        fr_event = next(e for e in build_multi_region_events() if e["country"] == "France")
        marker = forest_event_map_marker({**fr_event, "id": "evt-fr"})
        contaminated = attach_region_centroid(
            marker,
            centroids={"Suceava": (47.6353, 26.259), "Romania": (45.9432, 24.9668)},
        )
        assert contaminated["latitude"] == pytest.approx(48.8566)
        assert contaminated["longitude"] == pytest.approx(2.3522)
        assert contaminated.get("coordinate_source") != "region_admin_centroid"


class TestMapIntegration:
    def test_map_overlay_european_events_no_romania_centroid_fallback(self):
        events = build_multi_region_events()
        de_wildfire = next(
            e for e in events if e["country"] == "Germany" and e["metadata"]["incident_category"] == "wildfire"
        )
        mock_analytics = MagicMock()
        mock_repo = MagicMock()
        mock_repo.list_scoped_events_for_map = AsyncMock(return_value=[{**de_wildfire, "id": "de-wf-1"}])
        mock_repo.region_event_centroids = AsyncMock(return_value={"Suceava": (47.6, 26.2)})
        mock_repo.scope_policy = GeographicScopePolicy(GeographicScope.EUROPE)
        mock_analytics.repo = mock_repo
        mock_analytics.geographic_scope = "europe"
        mock_analytics.get_anomalies = AsyncMock(return_value={"anomalies": []})

        mock_intel = MagicMock()
        mock_intel.get_events = AsyncMock(return_value={"active": []})

        mock_area_svc = MagicMock()
        mock_area_svc.list_enabled_public = AsyncMock(return_value=[])

        from app.services.aoi_enrichment_service import AoiEnrichmentService

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: MagicMock()
        app.dependency_overrides[analytics_service_dep] = lambda: mock_analytics
        app.dependency_overrides[intelligence_events_service_dep] = lambda: mock_intel
        app.dependency_overrides[monitoring_area_service_dep] = lambda: mock_area_svc
        app.dependency_overrides[aoi_enrichment_service_dep] = lambda: AoiEnrichmentService()

        async def _org_ctx():
            return OrganizationContext(
                user=MagicMock(id="test-user"),
                organization_id="org-eu",
                organization_name="EU Org",
                organization_slug="org-eu",
                membership_id="mem-eu",
                role="owner",
                membership_status="active",
            )

        app.dependency_overrides[get_organization_context] = _org_ctx
        client = TestClient(app)
        resp = client.get("/analytics/intelligence/map-overlay")
        assert resp.status_code == 200
        body = resp.json()
        assert body["allow_romania_centroid_fallback"] is False
        assert body["geographic_scope"] == "europe"
        marker = body["forest_events"][0]
        assert marker["latitude"] == pytest.approx(48.1351)
        assert marker["longitude"] == pytest.approx(11.582)

    def test_events_map_leaflet_ordering(self):
        events = build_multi_region_events()
        pl_event = next(e for e in events if e["country"] == "Poland" and e["metadata"]["incident_category"] == "wildfire")
        marker = forest_event_map_marker({**pl_event, "id": "pl-wf"})
        leaflet = [marker["latitude"], marker["longitude"]]
        assert leaflet == [52.2297, 21.0122]


class TestCommandCenterIntegration:
    @pytest.mark.anyio
    async def test_command_center_european_evidence_states(self):
        settings = MagicMock()
        settings.enable_cross_source_correlation = True
        settings.enable_intelligence_provenance = False
        health_repo = MagicMock()
        health_repo.list_all = AsyncMock(return_value=[])
        de_event = {
            "id": "evt-de",
            "incident_category": "wildfire",
            "region": "Bavaria",
            "spatial_key": "Bavaria",
            "severity": "high",
            "escalation_level": "normal",
            "trend": "new",
            "priority_score": 0.7,
            "status": "active",
            "metadata": {},
        }
        svc = EvidenceAwareCommandCenterService(
            MagicMock(find_active=AsyncMock(return_value=[de_event])),
            MagicMock(list_all=AsyncMock(return_value=[])),
            MagicMock(get_current=AsyncMock(return_value={"intelligence_cycle_id": "cycle-eu"})),
            health_repo,
            settings=settings,
        )
        payload = await svc.build_intelligence_evidence()
        assert payload["items"][0]["evidence_summary"]["evidence_state"] == "single_source"
        assert payload["correlation_state"] in {"disabled", "unavailable", "current"}

    def test_command_center_get_side_effect_free(self):
        from tests.fixtures.intelligence_write_spy import build_intelligence_read_client

        client, spy = build_intelligence_read_client()
        resp = client.get("/analytics/intelligence/command-center")
        assert resp.status_code == 200
        assert "intelligence_evidence" in resp.json()
        spy.assert_no_persistence_or_reconciliation()


class TestOperationalApi:
    def test_read_only_bounded(self):
        source_intel = MagicMock()
        source_intel.get_source_status = AsyncMock(
            return_value={
                "geographic_scope": "europe",
                "sources": [
                    {
                        "provider_id": "eea.air_quality",
                        "display_name": "EEA Air Quality",
                        "enabled": True,
                        "geographic_coverage": "Europe",
                        "incident_categories": ["air_quality"],
                    }
                ],
            }
        )
        intel_repo = MagicMock()
        intel_repo.find_active = AsyncMock(return_value=[])
        correlation_repo = MagicMock()
        correlation_repo.list_all = AsyncMock(return_value=[])
        cycle_repo = MagicMock()
        cycle_repo.get_current = AsyncMock(return_value={"intelligence_cycle_id": "cycle-1"})
        health_repo = MagicMock()
        health_repo.list_all = AsyncMock(
            return_value=[{"provider_id": "eea.air_quality", "current_status": "healthy", "last_execution_mode": "fixture"}]
        )
        runs_repo = MagicMock()
        runs_repo.list_runs = AsyncMock(return_value=[{"provider_id": "eea.air_quality", "status": "success"}])
        svc = OperationalStatusService(
            source_intel,
            intel_repo,
            correlation_repo,
            cycle_repo,
            health_repo,
            runs_repo,
            settings=_settings(geographic_scope="europe"),
        )

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: MagicMock()
        app.dependency_overrides[operational_status_service_dep] = lambda: svc
        client = TestClient(app)
        resp = client.get("/analytics/intelligence/operational-status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["geographic_scope"] == "europe"
        assert body["providers"][0]["execution_mode"] == "fixture"
        assert "token" not in str(body).lower()

    @pytest.mark.anyio
    async def test_deterministic_output(self):
        source_intel = MagicMock()
        source_intel.get_source_status = AsyncMock(
            return_value={
                "geographic_scope": "europe",
                "sources": [{
                    "provider_id": "eea.air_quality",
                    "display_name": "EEA Air Quality",
                    "enabled": True,
                    "geographic_coverage": "Europe",
                    "incident_categories": ["air_quality"],
                }],
            }
        )
        intel_repo = MagicMock()
        intel_repo.find_active = AsyncMock(return_value=[])
        correlation_repo = MagicMock()
        correlation_repo.list_all = AsyncMock(return_value=[])
        cycle_repo = MagicMock()
        cycle_repo.get_current = AsyncMock(return_value={"intelligence_cycle_id": "cycle-1"})
        health_repo = MagicMock()
        health_repo.list_all = AsyncMock(return_value=[])
        runs_repo = MagicMock()
        runs_repo.list_runs = AsyncMock(return_value=[])
        svc = OperationalStatusService(
            source_intel, intel_repo, correlation_repo, cycle_repo, health_repo, runs_repo,
            settings=_settings(geographic_scope="europe"),
        )
        first = await svc.get_operational_status()
        second = await svc.get_operational_status()
        assert first == second
        assert len(first["providers"]) <= 20


class TestPhase0Oracle:
    def test_oracle_unchanged(self):
        verify_generated_match_manifest(generate_golden_artifacts())

    def test_ten_run_determinism(self):
        first = generate_golden_artifacts()
        for _ in range(9):
            verify_generated_match_manifest(generate_golden_artifacts())
        verify_generated_match_manifest(first)


class TestValidationReport:
    def test_report_structure(self):
        report = build_validation_report()
        assert report["validation_mode"] == "fixture"
        assert report["live_external_validation"] is False
        assert "France" in report["countries_in_europe_scope"]
        assert "Poland" in report["countries_in_europe_scope"]
        assert len(report["correlation_rules"]) == 3
        assert report["phase0_oracle_preserved"] is True

    def test_report_golden_artifact_stable(self):
        verify_report_matches_golden()

    def test_report_ten_run_determinism(self):
        first = build_validation_report()
        for _ in range(9):
            assert build_validation_report() == first
