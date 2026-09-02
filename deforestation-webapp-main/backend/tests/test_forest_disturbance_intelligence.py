"""Forest Disturbance Intelligence Foundation — Romania MVP tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.core.ecosystem.forest_disturbance_constants import (
    AuthorizationStatus,
    DisturbanceDriver,
    FORBIDDEN_ASSERTION_PHRASES,
    PRODUCT_ASSESSMENT_LABEL,
    assert_safe_assessment_language,
)
from app.core.ecosystem.incident_categories import IncidentCategory
from app.core.geography.geographic_scope import GeographicScope, GeographicScopePolicy
from app.core.ingestion.provider_health import ProviderHealthStatus, health_status_from_run
from app.core.ingestion.source_descriptor import SourceType
from app.modules.analytics.analytics_service import _compute_baselines
from app.modules.analytics.cross_source_correlator import CrossSourceCorrelator
from app.modules.analytics.detection_contract import Detection, SignalType
from app.modules.analytics.detectors.forest_disturbance_detector import ForestDisturbanceDetector
from app.modules.analytics.disturbance_assessment import assess_disturbance_context
from app.modules.analytics.disturbance_detection import (
    DISTURBANCE_SCORE_THRESHOLD,
    compute_disturbance_score,
    detection_from_disturbance_event,
    supplement_disturbance_detections,
)
from app.modules.analytics.disturbance_driver_classifier import classify_disturbance_driver
from app.modules.analytics.evidence_summary import build_evidence_summary
from app.modules.analytics.map_contract import (
    attach_region_centroid,
    forest_event_map_marker,
    intelligence_event_map_marker,
)
from app.modules.analytics.provenance_persistence import sanitize_provenance_envelope
from app.modules.analytics.reconciliation import identity_key_from_detection
from app.modules.analytics.segmented_baseline import aggregate_regional_baselines_by_category
from app.modules.ingestion.provider_execution_mode import resolve_provider_execution_mode
from app.modules.ingestion.providers.gfw_integrated_alerts import (
    GFWIntegratedAlertsProvider,
    _DEFAULT_FIXTURE_RECORDS,
    disturbance_spatial_key,
    disturbance_source_event_id,
)
from app.modules.ingestion.providers.gfw_integrated_alerts_constants import GFW_PROVIDER_ID
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


def _disturbance_events_from_fixture() -> list[dict]:
    provider = GFWIntegratedAlertsProvider(settings=_settings())
    events: list[dict] = []
    for raw in _DEFAULT_FIXTURE_RECORDS:
        payload = provider.normalize(raw)
        data = payload.model_dump()
        data["detected_at"] = data["detected_at"] or _NOW
        events.append(data)
    return events


def _disturbance(lat: float, lng: float, alert_id: str = "FIX-RO-LOG-001", **kwargs) -> Detection:
    detected_at = kwargs.pop("detected_at", _NOW)
    return Detection(
        spatial_key=disturbance_spatial_key(alert_id),
        incident_category="forest_disturbance",
        signal_type=SignalType.DISTURBANCE_SIGNAL.value,
        severity="high",
        score=0.72,
        detected_at=detected_at,
        evidence={
            "region": "Harghita",
            "latitude": lat,
            "longitude": lng,
            "affected_area_ha": 4.7,
            "provenance": {
                "provider_id": GFW_PROVIDER_ID,
                "source_event_id": disturbance_source_event_id(alert_id),
                "domain_evidence": {"provider_class": "gfw_integrated_alerts"},
            },
        },
    )


def _firms(lat: float, lng: float, region: str = "Harghita", **kwargs) -> Detection:
    return Detection(
        spatial_key=region,
        incident_category="wildfire",
        signal_type=SignalType.BASELINE_DEVIATION.value,
        severity="high",
        score=0.75,
        detected_at=kwargs.pop("detected_at", _NOW),
        evidence={
            "region": region,
            "latitude": lat,
            "longitude": lng,
            "provenance": {
                "provider_id": "nasa.firms",
                "domain_evidence": {"provider_class": "satellite_fire_observations"},
            },
        },
    )


class TestDomainModel:
    def test_forest_disturbance_category_exists(self):
        assert IncidentCategory.FOREST_DISTURBANCE.value == "forest_disturbance"

    def test_wildfire_category_unchanged(self):
        assert IncidentCategory.WILDFIRE.value == "wildfire"

    def test_canonical_identity_distinct_from_wildfire(self):
        d = _disturbance(47.12, 25.98)
        f = _firms(47.12, 25.98)
        assert identity_key_from_detection(d) != identity_key_from_detection(f)

    def test_forbidden_illegal_logging_language(self):
        for phrase in FORBIDDEN_ASSERTION_PHRASES:
            with pytest.raises(ValueError):
                assert_safe_assessment_language(phrase)

    def test_safe_assessment_label(self):
        assert_safe_assessment_language(PRODUCT_ASSESSMENT_LABEL)


class TestDriverClassification:
    def test_selective_logging_candidate(self):
        result = classify_disturbance_driver(
            alert_confidence=0.88,
            alert_intensity="moderate",
            affected_area_ha=4.7,
            forest_context={"is_forest": True, "tree_cover_density_pct": 80},
        )
        assert result["driver"] == DisturbanceDriver.SELECTIVE_LOGGING.value
        assert result["probable_driver"].endswith("_candidate")

    def test_clearcutting_large_patch(self):
        result = classify_disturbance_driver(
            alert_confidence=0.9,
            alert_intensity="high",
            affected_area_ha=55.0,
            forest_context={"is_forest": True},
        )
        assert result["driver"] == DisturbanceDriver.CLEARCUTTING.value

    def test_unknown_low_forest_intersection(self):
        result = classify_disturbance_driver(
            alert_confidence=0.7,
            alert_intensity="moderate",
            affected_area_ha=3.0,
            forest_context={"is_forest": False, "tree_cover_density_pct": 5},
        )
        assert result["driver"] in {DisturbanceDriver.UNKNOWN.value, DisturbanceDriver.SELECTIVE_LOGGING.value}


class TestInvestigationAssessment:
    def test_authorization_unknown_by_default(self):
        result = assess_disturbance_context(
            driver=DisturbanceDriver.SELECTIVE_LOGGING.value,
            driver_confidence=0.86,
            affected_area_ha=4.7,
            forest_context={"is_forest": True},
            protected_area_intersection=True,
        )
        assert result["authorization_status"] == AuthorizationStatus.UNKNOWN.value
        assert result["investigation_priority"] in {"medium", "high", "critical"}
        assert "Illegal" not in result["assessment_label"]

    def test_no_fabricated_unauthorized(self):
        result = assess_disturbance_context(
            driver=DisturbanceDriver.CLEARCUTTING.value,
            driver_confidence=0.9,
            affected_area_ha=20.0,
            authorization_status=AuthorizationStatus.POTENTIALLY_UNAUTHORIZED.value,
        )
        assert result["authorization_status"] != AuthorizationStatus.POTENTIALLY_UNAUTHORIZED.value


class TestGFWProvider:
    def test_describe_fixture_only_by_default(self):
        desc = GFWIntegratedAlertsProvider(settings=_settings()).describe()
        assert desc["provider_id"] == GFW_PROVIDER_ID
        assert desc["live_access_status"] == "fixture_only"

    @pytest.mark.anyio
    async def test_fixture_fetch(self):
        provider = GFWIntegratedAlertsProvider(settings=_settings())
        records = await provider.fetch()
        assert len(records) >= 3
        assert provider.last_execution_mode == "fixture"

    def test_normalize_metadata(self):
        payload = GFWIntegratedAlertsProvider(settings=_settings()).normalize(_DEFAULT_FIXTURE_RECORDS[0])
        meta = payload.metadata
        assert meta["incident_category"] == IncidentCategory.FOREST_DISTURBANCE.value
        assert meta["forest_disturbance"]["authorization_status"] == AuthorizationStatus.UNKNOWN.value
        assert "illegal" not in meta["forest_disturbance"]["assessment_label"].lower()

    def test_malformed_missing_alert_id(self):
        with pytest.raises(ValueError, match="alert_id"):
            GFWIntegratedAlertsProvider(settings=_settings()).normalize({"latitude": 1.0, "longitude": 2.0})

    def test_deterministic_identity(self):
        assert disturbance_spatial_key("FIX-RO-LOG-001") == "disturbance-alert:FIX-RO-LOG-001"
        assert disturbance_source_event_id("FIX-RO-LOG-001") == "gfw:integrated:FIX-RO-LOG-001"


class TestGeographicScope:
    def test_romania_fixture_in_scope(self):
        events = _disturbance_events_from_fixture()
        ro = next(e for e in events if e["country"] == "Romania")
        assert GeographicScopePolicy(GeographicScope.ROMANIA).event_in_scope(ro) is True

    def test_germany_out_of_romania_scope(self):
        events = _disturbance_events_from_fixture()
        de = next(e for e in events if e["country"] == "Germany")
        assert GeographicScopePolicy(GeographicScope.ROMANIA).event_in_scope(de) is False

    def test_europe_includes_ro_and_de(self):
        events = _disturbance_events_from_fixture()
        policy = GeographicScopePolicy(GeographicScope.EUROPE)
        countries = {e["country"] for e in events if policy.event_in_scope(e)}
        assert "Romania" in countries
        assert "Germany" in countries
        assert "Brazil" not in countries


class TestForestDisturbanceDetector:
    def test_positive_detection(self):
        regions = [
            {
                "region": "Harghita",
                "incident_category": "forest_disturbance",
                "current_events": 4,
                "baseline_events": 1,
            }
        ]
        detections = ForestDisturbanceDetector().detect(regions, _NOW)
        assert detections
        assert detections[0].incident_category == "forest_disturbance"

    def test_insufficient_evidence(self):
        regions = [
            {
                "region": "Harghita",
                "incident_category": "forest_disturbance",
                "current_events": 0,
                "baseline_events": 0,
            }
        ]
        assert ForestDisturbanceDetector().detect(regions, _NOW) == []

    def test_deterministic_score(self):
        score_a = compute_disturbance_score(confidence=0.88, affected_area_ha=4.7, forest_context={"is_forest": True})
        score_b = compute_disturbance_score(confidence=0.88, affected_area_ha=4.7, forest_context={"is_forest": True})
        assert score_a == score_b
        assert score_a >= DISTURBANCE_SCORE_THRESHOLD


class TestDisturbanceDetectionSupplement:
    @pytest.mark.anyio
    async def test_supplement_disabled(self):
        repo = MagicMock()
        base = [_firms(47.12, 25.98)]
        result = await supplement_disturbance_detections(repo, base, _NOW, enabled=False)
        assert result == base

    @pytest.mark.anyio
    async def test_supplement_appends_events(self):
        repo = MagicMock()
        repo.list_forest_disturbance_events = AsyncMock(return_value=_disturbance_events_from_fixture())
        base: list[Detection] = []
        result = await supplement_disturbance_detections(repo, base, _NOW, enabled=True)
        assert len(result) >= 2

    def test_detection_from_event(self):
        events = _disturbance_events_from_fixture()
        det = detection_from_disturbance_event(events[0], detected_at=_NOW)
        assert det.signal_type == SignalType.DISTURBANCE_SIGNAL.value
        assert det.evidence.get("authorization_status") == AuthorizationStatus.UNKNOWN.value


class TestCorrelation:
    def test_disturbance_wildfire_contextual(self):
        correlator = CrossSourceCorrelator()
        results = correlator.correlate(
            [_disturbance(47.12, 25.98), _firms(47.121, 25.981)],
            _NOW,
        )
        assert any(r.correlation_rule == "disturbance_wildfire_contextual" for r in results)

    def test_spatial_negative(self):
        correlator = CrossSourceCorrelator()
        results = correlator.correlate(
            [_disturbance(47.12, 25.98), _firms(50.0, 30.0)],
            _NOW,
        )
        assert not any(r.correlation_rule == "disturbance_wildfire_contextual" for r in results)

    def test_no_event_merging(self):
        d = _disturbance(47.12, 25.98)
        f = _firms(47.12, 25.98)
        assert identity_key_from_detection(d) != identity_key_from_detection(f)

    def test_deterministic_correlation_id(self):
        correlator = CrossSourceCorrelator()
        dets = [_disturbance(47.12, 25.98), _firms(47.121, 25.981)]
        first = correlator.correlate(dets, _NOW)
        second = correlator.correlate(list(reversed(dets)), _NOW)
        assert [r.correlation_id for r in first] == [r.correlation_id for r in second]


class TestProvenance:
    def test_credential_stripping(self):
        raw = {
            "provider_id": GFW_PROVIDER_ID,
            "api_key": "SECRET",
            "raw_payload": {"token": "SECRET"},
        }
        cleaned = sanitize_provenance_envelope(raw)
        assert "api_key" not in cleaned
        assert "raw_payload" not in cleaned


class TestMapIntegration:
    def test_authoritative_coordinates(self):
        events = _disturbance_events_from_fixture()
        ro = next(e for e in events if e["country"] == "Romania")
        marker = forest_event_map_marker(ro)
        assert marker["latitude"] == pytest.approx(ro["latitude"])
        assert marker["longitude"] == pytest.approx(ro["longitude"])
        assert marker.get("investigation_priority") is not None

    def test_no_romanian_centroid_contamination(self):
        payload = {"region": "Bavaria"}
        centroids = {"Harghita": (47.12, 25.98)}
        result = attach_region_centroid(payload, centroids=centroids)
        assert "latitude" not in result

    def test_intelligence_marker_disturbance_fields(self):
        intel = {
            "id": "evt-dist",
            "incident_category": "forest_disturbance",
            "region": "Harghita",
            "spatial_key": disturbance_spatial_key("FIX-RO-LOG-001"),
            "latitude": 47.12,
            "longitude": 25.98,
            "affected_area_ha": 4.7,
            "metadata": {
                "forest_disturbance": {
                    "investigation_priority": "high",
                    "authorization_status": "unknown",
                    "probable_driver": "selective_logging_candidate",
                    "driver_confidence": 0.86,
                }
            },
        }
        marker = intelligence_event_map_marker(intel)
        assert marker["latitude"] == pytest.approx(47.12)
        assert marker["disturbance_assessment"]["investigation_priority"] == "high"


class TestScheduler:
    def _scheduler(self, providers, reconcile):
        return SchedulerService(
            firms_provider=providers[0],
            events_service=MagicMock(),
            events_repo=MagicMock(),
            analytics_service=MagicMock(reconcile_intelligence_events=reconcile),
            intelligence_service=MagicMock(),
            runs_repo=MagicMock(create_run=AsyncMock(return_value={"status": "success"})),
            enabled=True,
            ingestion_providers=providers,
            reconciliation_lock=MagicMock(try_acquire=AsyncMock(return_value=True), release=AsyncMock()),
        )

    @pytest.mark.anyio
    async def test_gfw_failure_firms_continue(self):
        firms = MagicMock()
        firms.source_name = "NASA FIRMS"
        firms.provider_id = "nasa.firms"
        firms.describe = MagicMock(return_value={"source": "NASA FIRMS"})
        firms.run = AsyncMock(return_value={"total": 1, "created": 1, "skipped": 0, "errors": 0})
        gfw = MagicMock()
        gfw.source_name = "GFW"
        gfw.provider_id = GFW_PROVIDER_ID
        gfw.describe = MagicMock(return_value={"source": "GFW"})
        gfw.run = AsyncMock(side_effect=RuntimeError("GFW down"))
        reconcile = AsyncMock()
        scheduler = self._scheduler([firms, gfw], reconcile)
        await scheduler._run_cycle()
        firms.run.assert_awaited_once()
        reconcile.assert_awaited_once()


class TestPhase0Compatibility:
    def test_oracle_unchanged(self):
        verify_generated_match_manifest(generate_golden_artifacts())

    def test_ten_run_determinism(self):
        for _ in range(10):
            verify_generated_match_manifest(generate_golden_artifacts())

    def test_wildfire_baseline_unchanged(self):
        events = build_wildfire_events()
        rows = aggregate_regional_baselines_by_category(events, _NOW)
        baselines = _compute_baselines(rows, generated_at=_NOW)
        suceava = next((r for r in baselines["regions"] if r.get("region") == "Suceava"), None)
        assert suceava is not None


class TestProviderHealth:
    def test_disabled_mode(self):
        settings = _settings(enable_forest_disturbance=False)
        assert (
            resolve_provider_execution_mode(
                provider_id=GFW_PROVIDER_ID,
                enabled=False,
                settings=settings,
                health=None,
                last_run=None,
                describe={},
            )
            == "disabled"
        )

    def test_fixture_mode_without_key(self):
        settings = _settings(enable_forest_disturbance=True, gfw_api_key="")
        assert (
            resolve_provider_execution_mode(
                provider_id=GFW_PROVIDER_ID,
                enabled=True,
                settings=settings,
                health={"last_execution_mode": "fixture"},
                last_run={"status": "success"},
                describe={"live_access_status": "fixture_only"},
            )
            == "fixture"
        )

    def test_failure_isolated(self):
        status = health_status_from_run(
            success=False,
            observations_rejected=0,
            observations_received=0,
            consecutive_failures=3,
            enabled=True,
        )
        assert status == ProviderHealthStatus.FAILED.value
