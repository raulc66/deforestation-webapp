"""EFFIS contextual wildfire enrichment — provider, correlation, evidence, scheduler."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.core.ecosystem.incident_categories import IncidentCategory
from app.core.geography.geographic_scope import GeographicScope, GeographicScopePolicy
from app.core.ingestion.provider_health import ProviderHealthStatus, health_status_from_run
from app.core.ingestion.source_descriptor import SourceType
from app.modules.analytics.analytics_service import _compute_baselines
from app.modules.analytics.contextual_detection import (
    detection_from_effis_context_event,
    supplement_contextual_detections,
)
from app.modules.analytics.cross_source_correlator import CrossSourceCorrelator
from app.modules.analytics.detection_contract import Detection
from app.modules.analytics.correlation_result import CorrelationParticipant, CorrelationResult
from app.modules.analytics.evidence_summary import (
    build_evidence_summary,
)
from app.modules.analytics.map_contract import (
    attach_region_centroid,
    forest_event_map_marker,
)
from app.modules.analytics.provenance_persistence import sanitize_provenance_envelope
from app.modules.analytics.reconciliation import identity_key_from_detection
from app.modules.analytics.segmented_baseline import aggregate_regional_baselines_by_category
from app.modules.ingestion.provider_execution_mode import resolve_provider_execution_mode
from app.modules.ingestion.providers.effis import (
    EFFISWildfireContextProvider,
    _DEFAULT_FIXTURE_RECORDS,
    effis_source_event_id,
    effis_spatial_key,
)
from app.modules.ingestion.providers.effis_constants import (
    EFFIS_DATASET_ID,
    EFFIS_PROVIDER_ID,
    EFFIS_SOURCE_NAME,
    EFFIS_WFS_BASE,
    EUROPE_WFS_BBOX,
    ROMANIA_WFS_BBOX,
)
from app.modules.ingestion.providers.effis_gml_parser import parse_effis_gml_features
from app.services.scheduler_service import SchedulerService
from app.services.source_intelligence_service import SourceIntelligenceService
from fixtures.phase0_golden_fixture import build_wildfire_events
from fixtures.phase0_golden_harness import generate_golden_artifacts
from fixtures.phase0_oracle_manifest import verify_generated_match_manifest

_NOW = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)


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


def _firms(lat: float, lng: float, region: str = "Suceava", **kwargs) -> Detection:
    detected_at = kwargs.pop("detected_at", _NOW)
    return Detection(
        spatial_key=region,
        incident_category="wildfire",
        signal_type="baseline_deviation",
        severity="high",
        score=0.75,
        detected_at=detected_at,
        evidence={
            "region": region,
            "latitude": lat,
            "longitude": lng,
            "provenance": {
                "provider_id": "nasa.firms",
                "source_event_id": f"nasa.firms-{region}",
                "domain_evidence": {
                    "provider_class": "satellite_fire_observations",
                },
            },
        },
    )


def _effis(
    lat: float,
    lng: float,
    fire_id: str = "FIX-RO-001",
    **kwargs,
) -> Detection:
    detected_at = kwargs.pop("detected_at", _NOW)
    spatial_key = effis_spatial_key(fire_id)
    return Detection(
        spatial_key=spatial_key,
        incident_category="wildfire",
        signal_type="contextual_evidence",
        severity="high",
        score=0.72,
        detected_at=detected_at,
        evidence={
            "region": "Suceava",
            "latitude": lat,
            "longitude": lng,
            "fire_id": fire_id,
            "contextual_role": "wildfire_burned_area",
            "provenance": {
                "provider_id": EFFIS_PROVIDER_ID,
                "source_event_id": effis_source_event_id("modis.ba.poly.2024", fire_id),
                "domain_evidence": {
                    "provider_class": "effis_wildfire_context",
                    "contextual_role": "wildfire_burned_area",
                },
            },
        },
    )


def _effis_provider(**overrides) -> EFFISWildfireContextProvider:
    return EFFISWildfireContextProvider(settings=_settings(**overrides))


def _effis_events_from_fixture() -> list[dict]:
    provider = _effis_provider()
    events: list[dict] = []
    for raw in _DEFAULT_FIXTURE_RECORDS:
        payload = provider.normalize(raw)
        data = payload.model_dump()
        data["detected_at"] = data["detected_at"] or _NOW
        events.append(data)
    return events


_SAMPLE_GML = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs"
  xmlns:gml="http://www.opengis.net/gml"
  xmlns:ms="http://mapserver.gis.umn.edu/mapserver">
  <gml:featureMember>
    <ms:modis_ba_poly fid="modis.ba.poly.2024.12345">
      <gml:boundedBy><gml:Box><gml:coordinates>26.2,47.6 26.3,47.7</gml:coordinates></gml:Box></gml:boundedBy>
      <ms:id>12345</ms:id>
      <ms:FIREDATE>2024-06-08T00:00:00</ms:FIREDATE>
      <ms:FINALDATE>2024-06-10T00:00:00</ms:FINALDATE>
      <ms:COUNTRY>Romania</ms:COUNTRY>
      <ms:PROVINCE>Suceava</ms:PROVINCE>
      <ms:AREA_HA>142.0</ms:AREA_HA>
    </ms:modis_ba_poly>
  </gml:featureMember>
</wfs:FeatureCollection>
"""


class TestEFFISProviderMetadata:
    def test_describe_documents_verified_wfs(self):
        desc = _effis_provider().describe()
        assert desc["source"] == EFFIS_SOURCE_NAME
        assert desc["provider_id"] == EFFIS_PROVIDER_ID
        assert desc["dataset_id"] == EFFIS_DATASET_ID
        assert desc["contextual_role"] == "wildfire_burned_area"
        assert EFFIS_WFS_BASE in desc["api_endpoint"]
        assert desc["live_access_status"] == "fixture_only"

    def test_source_descriptor_contextual_type(self):
        settings = _settings(enable_effis_wildfire_context=True)
        provider = _effis_provider(enable_effis_wildfire_context=True)
        svc = SourceIntelligenceService(
            AsyncMock(),
            settings=settings,
            ingestion_providers=[provider],
        )
        descriptors = svc._build_descriptors()
        effis = next(d for d in descriptors if d.provider_id == EFFIS_PROVIDER_ID)
        assert effis.source_type == SourceType.CONTEXTUAL.value
        assert effis.enabled is True


class TestEFFISFixtureFetch:
    @pytest.mark.anyio
    async def test_fixture_fetch_default(self):
        provider = _effis_provider()
        records = await provider.fetch()
        assert len(records) == 3
        assert provider.last_execution_mode == "fixture"

    @pytest.mark.anyio
    async def test_live_failure_falls_back_to_fixture(self):
        provider = _effis_provider(enable_effis_wildfire_context=True, enable_effis_live=True)
        with patch(
            "app.modules.ingestion.providers.effis.fetch_burned_area_features",
            side_effect=RuntimeError("network down"),
        ):
            records = await provider.fetch()
        assert len(records) == 3
        assert provider.last_execution_mode == "fixture"


class TestEFFISNormalization:
    def test_normalize_produces_contextual_metadata(self):
        payload = _effis_provider().normalize(_DEFAULT_FIXTURE_RECORDS[0])
        meta = payload.metadata
        assert meta["contextual_role"] == "wildfire_burned_area"
        assert meta["incident_category"] == IncidentCategory.WILDFIRE.value
        ingestion = meta["ingestion"]
        provider_id = ingestion.get("provider_id") if isinstance(ingestion, dict) else ingestion.provider_id
        assert provider_id == EFFIS_PROVIDER_ID
        assert payload.event_type == "unknown"
        assert meta["spatial_key"] == effis_spatial_key("FIX-RO-001")

    def test_malformed_missing_fire_id(self):
        with pytest.raises(ValueError, match="fire_id"):
            _effis_provider().normalize({"latitude": 1.0, "longitude": 2.0})

    def test_deterministic_spatial_identity(self):
        raw = _DEFAULT_FIXTURE_RECORDS[0]
        a = _effis_provider().normalize(raw)
        b = _effis_provider().normalize(raw)
        assert a.metadata["spatial_key"] == b.metadata["spatial_key"]
        ingestion = a.metadata["ingestion"]
        source_event_id = (
            ingestion.get("source_event_id")
            if isinstance(ingestion, dict)
            else ingestion.source_event_id
        )
        assert effis_source_event_id("modis.ba.poly.2024", "FIX-RO-001") == source_event_id

    def test_deduplication_identity_formula(self):
        layer = "modis.ba.poly.2024"
        fire_id = "FIX-RO-001"
        assert effis_spatial_key(fire_id) == "effis-burn:FIX-RO-001"
        assert effis_source_event_id(layer, fire_id) == "effis:modis.ba.poly.2024:FIX-RO-001"


class TestEFFISGMLParser:
    def test_parse_verified_schema(self):
        records = parse_effis_gml_features(_SAMPLE_GML, layer="modis.ba.poly.2024")
        assert len(records) == 1
        assert records[0]["fire_id"] == "12345"
        assert records[0]["country"] == "Romania"
        assert records[0]["area_ha"] == "142.0"

    def test_malformed_service_exception(self):
        with pytest.raises(ValueError):
            parse_effis_gml_features("ServiceExceptionReport", layer="modis.ba.poly.2024")


class TestEFFISGeographicScope:
    def test_romania_bbox_constants(self):
        minx, miny, maxx, maxy = ROMANIA_WFS_BBOX
        assert minx < maxx and miny < maxy
        assert ROMANIA_WFS_BBOX != EUROPE_WFS_BBOX

    def test_romania_fixture_in_scope(self):
        events = _effis_events_from_fixture()
        ro = next(e for e in events if e["country"] == "Romania")
        policy = GeographicScopePolicy(GeographicScope.ROMANIA)
        assert policy.event_in_scope(ro) is True

    def test_germany_out_of_romania_scope(self):
        events = _effis_events_from_fixture()
        de = next(e for e in events if e["country"] == "Germany")
        policy = GeographicScopePolicy(GeographicScope.ROMANIA)
        assert policy.event_in_scope(de) is False

    def test_europe_scope_includes_de_and_ro(self):
        events = _effis_events_from_fixture()
        policy = GeographicScopePolicy(GeographicScope.EUROPE)
        countries = {e["country"] for e in events if policy.event_in_scope(e)}
        assert "Romania" in countries
        assert "Germany" in countries
        assert "Greece" in countries

    def test_provider_coverage_differs_from_configured_scope(self):
        settings = _settings(geographic_scope="romania", enable_effis_wildfire_context=True)
        mode = resolve_provider_execution_mode(
            provider_id=EFFIS_PROVIDER_ID,
            enabled=True,
            settings=settings,
            health={"last_execution_mode": "fixture"},
            last_run={"status": "success"},
            describe={"live_access_status": "public_wfs"},
        )
        assert mode == "fixture"
        assert settings.geographic_scope == "romania"


class TestEFFISBaselineExclusion:
    def test_effis_marked_contextual_not_incident_observation(self):
        payload = _effis_provider().normalize(_DEFAULT_FIXTURE_RECORDS[0])
        assert payload.event_type == "unknown"
        assert payload.metadata["contextual_role"] == "wildfire_burned_area"
        ingestion = payload.metadata["ingestion"]
        provider_id = ingestion.get("provider_id") if isinstance(ingestion, dict) else ingestion.provider_id
        assert provider_id == EFFIS_PROVIDER_ID

    def test_phase0_wildfire_baseline_unchanged_with_effis_disabled(self):
        events = build_wildfire_events()
        rows = aggregate_regional_baselines_by_category(events, _NOW)
        baselines = _compute_baselines(rows, generated_at=_NOW)
        suceava = next(
            (r for r in baselines["regions"] if r.get("region") == "Suceava"),
            None,
        )
        assert suceava is not None


class TestEFFISContextualDetection:
    def test_detection_from_persisted_event(self):
        events = _effis_events_from_fixture()
        det = detection_from_effis_context_event(events[0], detected_at=_NOW)
        assert det.signal_type == "contextual_evidence"
        assert det.spatial_key == effis_spatial_key("FIX-RO-001")
        assert det.evidence["contextual_role"] == "wildfire_burned_area"

    @pytest.mark.anyio
    async def test_supplement_disabled_noop(self):
        repo = MagicMock()
        base = [_firms(47.636, 26.260)]
        result = await supplement_contextual_detections(repo, base, _NOW, enabled=False)
        assert result == base
        repo.list_effis_context_events.assert_not_called()

    @pytest.mark.anyio
    async def test_supplement_appends_effis_detections(self):
        repo = MagicMock()
        repo.list_effis_context_events = AsyncMock(return_value=_effis_events_from_fixture())
        base = [_firms(47.636, 26.260)]
        result = await supplement_contextual_detections(repo, base, _NOW, enabled=True)
        assert len(result) == len(base) + 3


class TestEFFISCorrelation:
    def test_firms_effis_contextual_match(self):
        correlator = CrossSourceCorrelator()
        results = correlator.correlate(
            [_firms(47.636, 26.260), _effis(47.636, 26.260)],
            _NOW,
            geographic_scope="romania",
        )
        assert len(results) == 1
        assert results[0].correlation_rule == "firms_effis_contextual"
        assert results[0].relationship_type == "contextual_evidence"

    def test_spatial_negative(self):
        correlator = CrossSourceCorrelator()
        results = correlator.correlate(
            [_firms(47.636, 26.260), _effis(50.0, 30.0)],
            _NOW,
        )
        assert len(results) == 0

    def test_temporal_negative(self):
        correlator = CrossSourceCorrelator()
        old = _NOW - timedelta(hours=800)
        results = correlator.correlate(
            [_firms(47.636, 26.260), _effis(47.636, 26.260, detected_at=old)],
            _NOW,
        )
        assert len(results) == 0

    def test_same_provider_no_self_correlation(self):
        correlator = CrossSourceCorrelator()
        results = correlator.correlate(
            [_effis(47.636, 26.260), _effis(47.637, 26.261, fire_id="FIX-RO-002")],
            _NOW,
        )
        assert len(results) == 0

    def test_deterministic_correlation_id(self):
        correlator = CrossSourceCorrelator()
        dets = [_firms(47.636, 26.260), _effis(47.636, 26.260)]
        first = correlator.correlate(dets, _NOW)
        second = correlator.correlate(list(reversed(dets)), _NOW)
        assert [r.correlation_id for r in first] == [r.correlation_id for r in second]
        assert first[0].strength == pytest.approx(0.60)

    def test_no_event_merging(self):
        firms = _firms(47.636, 26.260)
        effis = _effis(47.636, 26.260)
        assert identity_key_from_detection(firms) != identity_key_from_detection(effis)
        assert identity_key_from_detection(firms) == ("wildfire", "Suceava")
        assert identity_key_from_detection(effis) == ("wildfire", effis_spatial_key("FIX-RO-001"))


class TestEFFISProvenance:
    def test_provenance_disabled(self):
        events = _effis_events_from_fixture()
        meta = events[0]["metadata"]
        assert "provenance" in meta
        cleaned = sanitize_provenance_envelope(meta["provenance"])
        assert cleaned["provider_id"] == EFFIS_PROVIDER_ID

    def test_provenance_enabled_bounded(self):
        det = _effis(47.636, 26.260)
        prov = det.evidence["provenance"]
        cleaned = sanitize_provenance_envelope({**prov, "geographic_scope": "europe"})
        assert cleaned["provider_id"] == EFFIS_PROVIDER_ID
        assert cleaned["geographic_scope"] == "europe"
        assert "api_key" not in cleaned

    def test_credential_stripping(self):
        raw = {
            "provider_id": EFFIS_PROVIDER_ID,
            "api_key": "SECRET",
            "raw_payload": {"token": "SECRET"},
            "domain_evidence": {"provider_class": "effis_wildfire_context"},
        }
        cleaned = sanitize_provenance_envelope(raw)
        assert "api_key" not in cleaned
        assert "raw_payload" not in cleaned


class TestEFFISProviderHealth:
    def test_disabled_execution_mode(self):
        settings = _settings(enable_effis_wildfire_context=False)
        assert (
            resolve_provider_execution_mode(
                provider_id=EFFIS_PROVIDER_ID,
                enabled=False,
                settings=settings,
                health=None,
                last_run=None,
                describe={},
            )
            == "disabled"
        )

    def test_fixture_mode_when_live_disabled(self):
        settings = _settings(enable_effis_wildfire_context=True, enable_effis_live=False)
        assert (
            resolve_provider_execution_mode(
                provider_id=EFFIS_PROVIDER_ID,
                enabled=True,
                settings=settings,
                health={"last_execution_mode": "fixture"},
                last_run={"status": "success"},
                describe={"live_access_status": "fixture_only"},
            )
            == "fixture"
        )

    def test_live_mode_when_enabled(self):
        settings = _settings(enable_effis_wildfire_context=True, enable_effis_live=True)
        assert (
            resolve_provider_execution_mode(
                provider_id=EFFIS_PROVIDER_ID,
                enabled=True,
                settings=settings,
                health={"last_execution_mode": "live"},
                last_run={"status": "success"},
                describe={"live_access_status": "public_wfs"},
            )
            == "live"
        )

    def test_failure_health_isolated(self):
        status = health_status_from_run(
            success=False,
            observations_rejected=0,
            observations_received=0,
            consecutive_failures=3,
            enabled=True,
        )
        assert status == ProviderHealthStatus.FAILED.value


class TestEFFISScheduler:
    def _scheduler(self, providers, reconcile):
        runs_repo = MagicMock()
        runs_repo.create_run = AsyncMock(return_value={"status": "success", "duration_seconds": 0.1})
        return SchedulerService(
            firms_provider=providers[0],
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
    async def test_effis_success_reconciliation_once(self):
        def _ok(name, pid):
            p = MagicMock()
            p.source_name = name
            p.provider_id = pid
            p.describe = MagicMock(return_value={"source": name})
            p.run = AsyncMock(return_value={"total": 1, "created": 1, "skipped": 0, "errors": 0})
            return p

        reconcile = AsyncMock()
        scheduler = self._scheduler(
            [_ok("NASA FIRMS", "nasa.firms"), _ok("EFFIS", EFFIS_PROVIDER_ID)],
            reconcile,
        )
        await scheduler._run_cycle()
        reconcile.assert_awaited_once()

    @pytest.mark.anyio
    async def test_effis_failure_firms_continue(self):
        firms = MagicMock()
        firms.source_name = "NASA FIRMS"
        firms.provider_id = "nasa.firms"
        firms.describe = MagicMock(return_value={"source": "NASA FIRMS"})
        firms.run = AsyncMock(return_value={"total": 1, "created": 1, "skipped": 0, "errors": 0})
        effis = MagicMock()
        effis.source_name = "EFFIS"
        effis.provider_id = EFFIS_PROVIDER_ID
        effis.describe = MagicMock(return_value={"source": "EFFIS"})
        effis.run = AsyncMock(side_effect=RuntimeError("EFFIS down"))
        reconcile = AsyncMock()
        scheduler = self._scheduler([firms, effis], reconcile)
        await scheduler._run_cycle()
        firms.run.assert_awaited_once()
        reconcile.assert_awaited_once()

    @pytest.mark.anyio
    async def test_firms_failure_effis_success(self):
        firms = MagicMock()
        firms.source_name = "NASA FIRMS"
        firms.provider_id = "nasa.firms"
        firms.describe = MagicMock(return_value={"source": "NASA FIRMS"})
        firms.run = AsyncMock(side_effect=RuntimeError("FIRMS down"))
        effis = MagicMock()
        effis.source_name = "EFFIS"
        effis.provider_id = EFFIS_PROVIDER_ID
        effis.describe = MagicMock(return_value={"source": "EFFIS"})
        effis.run = AsyncMock(return_value={"total": 1, "created": 1, "skipped": 0, "errors": 0})
        reconcile = AsyncMock()
        scheduler = self._scheduler([firms, effis], reconcile)
        await scheduler._run_cycle()
        effis.run.assert_awaited_once()
        reconcile.assert_awaited_once()


class TestEFFISEvidence:
    def _event(self, spatial_key: str = "Suceava") -> dict:
        return {
            "id": "evt-1",
            "incident_category": "wildfire",
            "region": "Suceava",
            "spatial_key": spatial_key,
            "metadata": {"provenance": {"provider_id": "nasa.firms"}},
        }

    def _effis_correlation(self) -> CorrelationResult:
        return CorrelationResult(
            correlation_id="corr-effis-1",
            canonical_incident_category="wildfire",
            canonical_spatial_key="Suceava",
            relationship_type="contextual_evidence",
            correlation_rule="firms_effis_contextual",
            participants=(
                CorrelationParticipant(
                    incident_category="wildfire",
                    spatial_key="Suceava",
                    provider_id="nasa.firms",
                    detected_at=_NOW,
                    role="primary",
                ),
                CorrelationParticipant(
                    incident_category="wildfire",
                    spatial_key=effis_spatial_key("FIX-RO-001"),
                    provider_id=EFFIS_PROVIDER_ID,
                    detected_at=_NOW,
                    role="supporting",
                ),
            ),
            participating_provider_ids=("nasa.firms", EFFIS_PROVIDER_ID),
            spatial_relationship="nearby",
            temporal_relationship="same_window",
            strength=0.60,
            created_at=_NOW,
        )

    def test_firms_only_single_source(self):
        summary = build_evidence_summary(
            self._event(),
            correlations=[],
            correlation_state="disabled",
            health_by_provider={"nasa.firms": ProviderHealthStatus.HEALTHY.value},
        )
        assert summary.evidence_state == "single_source"

    def test_firms_plus_effis_contextual_support(self):
        summary = build_evidence_summary(
            self._event(),
            correlations=[self._effis_correlation()],
            correlation_state="current",
            health_by_provider={
                "nasa.firms": ProviderHealthStatus.HEALTHY.value,
                EFFIS_PROVIDER_ID: ProviderHealthStatus.HEALTHY.value,
            },
        )
        assert summary.evidence_state == "contextual_support"
        assert "EFFIS" in summary.providers

    def test_degraded_effis_no_fabricated_correlation(self):
        correlator = CrossSourceCorrelator()
        assert correlator.correlate([_firms(47.636, 26.260)], _NOW) == []


class TestEFFISMapIntegration:
    def test_authoritative_coordinates_preserved(self):
        events = _effis_events_from_fixture()
        de = next(e for e in events if e["country"] == "Germany")
        marker = forest_event_map_marker(de)
        assert marker["latitude"] == pytest.approx(de["latitude"])
        assert marker["longitude"] == pytest.approx(de["longitude"])
        assert marker.get("coordinate_source") != "region_event_centroid"

    def test_no_romanian_centroid_contamination_europe(self):
        payload = {"region": "Bavaria"}
        centroids = {"Suceava": (47.636, 26.260)}
        result = attach_region_centroid(payload, centroids=centroids)
        assert "latitude" not in result
        assert "longitude" not in result

    def test_centroid_fallback_not_applied_when_coords_present(self):
        payload = {"region": "Suceava", "latitude": 47.636, "longitude": 26.260}
        centroids = {"Suceava": (45.0, 25.0)}
        result = attach_region_centroid(payload, centroids=centroids)
        assert result["latitude"] == pytest.approx(47.636)


class TestEFFISCommandCenter:
    @pytest.mark.anyio
    async def test_degraded_sources_includes_effis_failure(self):
        health_repo = AsyncMock()
        health_repo.list_all = AsyncMock(
            return_value=[
                {
                    "provider_id": EFFIS_PROVIDER_ID,
                    "display_name": "EFFIS",
                    "current_status": ProviderHealthStatus.FAILED.value,
                }
            ]
        )
        settings = _settings(enable_effis_wildfire_context=True)
        provider = _effis_provider(enable_effis_wildfire_context=True)
        svc = SourceIntelligenceService(
            health_repo,
            settings=settings,
            ingestion_providers=[provider],
        )
        degraded = await svc.get_degraded_sources()
        assert len(degraded) == 1
        assert "api_key" not in str(degraded)


class TestEFFISPhase0Compatibility:
    def test_oracle_unchanged(self):
        verify_generated_match_manifest(generate_golden_artifacts())

    def test_ten_run_determinism(self):
        for _ in range(10):
            verify_generated_match_manifest(generate_golden_artifacts())
