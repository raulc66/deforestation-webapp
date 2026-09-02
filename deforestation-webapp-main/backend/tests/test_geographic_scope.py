"""Geographic scope generalization — intelligence pipeline filtering."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import get_settings
from app.core.geography.europe import is_europe_country, is_europe_event
from app.core.geography.geographic_scope import (
    GeographicScope,
    GeographicScopePolicy,
    parse_geographic_scope,
)
from app.modules.analytics.analytics_service import AnalyticsService, _evaluate_alerts
from app.modules.analytics.map_contract import attach_region_centroid
from app.modules.analytics.segmented_baseline import aggregate_regional_baselines_by_category
from app.modules.ingestion.providers.firms import FIRMSProvider
from fixtures.phase0_golden_fixture import build_wildfire_events
from fixtures.phase0_golden_harness import (
    PHASE0_GEOGRAPHIC_SCOPE,
    Phase0FixtureAnalyticsRepository,
    generate_golden_artifacts,
)
from fixtures.phase0_oracle_manifest import verify_generated_match_manifest

_NOW = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)


def _event(
    *,
    country: str,
    region: str,
    is_romania: bool,
    incident_category: str = "wildfire",
    detected_at: datetime | None = None,
    latitude: float = 45.0,
    longitude: float = 25.0,
) -> dict:
    return {
        "country": country,
        "region": region,
        "latitude": latitude,
        "longitude": longitude,
        "detected_at": detected_at or _NOW,
        "metadata": {
            "incident_category": incident_category,
            "ingestion": {"is_romania": is_romania, "source": "test"},
        },
    }


EUROPE_FIXTURE_EVENTS = [
    _event(country="Romania", region="Suceava", is_romania=True, detected_at=_NOW),
    _event(country="Germany", region="Bavaria", is_romania=False, latitude=48.1, longitude=11.6),
    _event(country="France", region="Provence", is_romania=False, latitude=43.9, longitude=5.4),
    _event(country="Spain", region="Galicia", is_romania=False, latitude=42.8, longitude=-8.5),
    _event(country="Poland", region="Mazovia", is_romania=False, latitude=52.2, longitude=21.0),
    _event(country="Brazil", region="Amazon", is_romania=False, latitude=-3.0, longitude=-60.0),
]


class TestScopeParsing:
    def test_default_is_romania(self):
        assert parse_geographic_scope(None) is GeographicScope.ROMANIA

    @pytest.mark.parametrize(
        "raw,expected",
        [("romania", GeographicScope.ROMANIA), ("europe", GeographicScope.EUROPE), ("all", GeographicScope.ALL)],
    )
    def test_valid_values(self, raw, expected):
        assert parse_geographic_scope(raw) is expected

    def test_invalid_falls_back_to_romania(self):
        assert parse_geographic_scope("tenant-aoi") is GeographicScope.ROMANIA


class TestRomaniaScope:
    def test_romania_includes_only_romanian_events(self):
        policy = GeographicScopePolicy(GeographicScope.ROMANIA)
        rows = aggregate_regional_baselines_by_category(
            EUROPE_FIXTURE_EVENTS,
            _NOW,
            scope_policy=policy,
        )
        regions = {r["_id"]["region"] for r in rows}
        assert "Suceava" in regions
        assert "Bavaria" not in regions


class TestEuropeScope:
    def test_europe_includes_eu_countries(self):
        policy = GeographicScopePolicy(GeographicScope.EUROPE)
        rows = aggregate_regional_baselines_by_category(
            EUROPE_FIXTURE_EVENTS,
            _NOW,
            scope_policy=policy,
        )
        regions = {r["_id"]["region"] for r in rows}
        assert "Suceava" in regions
        assert "Bavaria" in regions
        assert "Amazon" not in regions

    def test_non_european_excluded(self):
        policy = GeographicScopePolicy(GeographicScope.EUROPE)
        assert policy.event_in_scope(EUROPE_FIXTURE_EVENTS[-1]) is False


class TestAllScope:
    def test_all_includes_non_european(self):
        policy = GeographicScopePolicy(GeographicScope.ALL)
        rows = aggregate_regional_baselines_by_category(
            EUROPE_FIXTURE_EVENTS,
            _NOW,
            scope_policy=policy,
        )
        regions = {r["_id"]["region"] for r in rows}
        assert "Amazon" in regions


class TestCategoryIsolationAcrossScopes:
    def test_air_quality_segmented_under_europe(self):
        events = EUROPE_FIXTURE_EVENTS + [
            _event(
                country="Germany",
                region="DE-BER-AQ01",
                is_romania=False,
                incident_category="air_quality",
                latitude=52.52,
                longitude=13.405,
            )
        ]
        policy = GeographicScopePolicy(GeographicScope.EUROPE)
        rows = aggregate_regional_baselines_by_category(events, _NOW, scope_policy=policy)
        aq = [r for r in rows if r["_id"]["incident_category"] == "air_quality"]
        assert aq
        assert aq[0]["_id"]["region"] == "DE-BER-AQ01"

    def test_environmental_hazard_segmented_under_europe(self):
        events = EUROPE_FIXTURE_EVENTS + [
            _event(
                country="France",
                region="France",
                is_romania=False,
                incident_category="environmental_hazard",
                latitude=48.85,
                longitude=2.35,
            )
        ]
        policy = GeographicScopePolicy(GeographicScope.EUROPE)
        rows = aggregate_regional_baselines_by_category(events, _NOW, scope_policy=policy)
        hz = [r for r in rows if r["_id"]["incident_category"] == "environmental_hazard"]
        assert hz


class TestEuropeClassifier:
    @pytest.mark.parametrize(
        "country",
        ["Romania", "Germany", "France", "Spain", "Poland"],
    )
    def test_european_countries(self, country):
        assert is_europe_country(country) is True

    def test_non_european_country(self):
        assert is_europe_country("Brazil") is False

    def test_romanian_event_in_europe(self):
        assert is_europe_event(EUROPE_FIXTURE_EVENTS[0]) is True


class TestScopePolicyFilters:
    def test_romania_mongo_filter(self):
        policy = GeographicScopePolicy(GeographicScope.ROMANIA)
        assert policy.mongo_match_filter() == {"metadata.ingestion.is_romania": True}

    def test_europe_mongo_filter_uses_expr(self):
        policy = GeographicScopePolicy(GeographicScope.EUROPE)
        filt = policy.mongo_match_filter()
        assert "$expr" in filt

    def test_all_scope_empty_filter(self):
        policy = GeographicScopePolicy(GeographicScope.ALL)
        assert policy.mongo_match_filter() == {}

    def test_centroid_fallback_only_romania(self):
        assert GeographicScopePolicy(GeographicScope.ROMANIA).centroids_use_romania_admin_fallback()
        assert not GeographicScopePolicy(GeographicScope.EUROPE).centroids_use_romania_admin_fallback()
        assert not GeographicScopePolicy(GeographicScope.ALL).centroids_use_romania_admin_fallback()


class TestRomanianInclusionUnderEurope:
    def test_romania_included_in_europe_scope(self):
        policy = GeographicScopePolicy(GeographicScope.EUROPE)
        assert policy.event_in_scope(EUROPE_FIXTURE_EVENTS[0]) is True


class TestMapBehavior:
    def test_no_romanian_centroid_for_activation_coordinates(self):
        payload = attach_region_centroid(
            {
                "region": "France",
                "coordinate_source": "activation_centroid",
                "latitude": 48.85,
                "longitude": 2.35,
            },
            centroids={"Suceava": (47.6, 26.2)},
        )
        assert payload["latitude"] == 48.85

    def test_no_centroid_fallback_without_coords(self):
        payload = attach_region_centroid(
            {"region": "France"},
            centroids={"Suceava": (47.6, 26.2)},
        )
        assert "latitude" not in payload

    def test_romania_centroid_fallback_when_allowed(self):
        payload = attach_region_centroid(
            {"region": "Suceava"},
            centroids={"Suceava": (47.6353, 26.259)},
        )
        assert payload["latitude"] == pytest.approx(47.6353)


class TestDefaultConfiguration:
    def test_settings_default_romania(self):
        get_settings.cache_clear()
        with patch.dict("os.environ", {"MONGO_URL": "mongodb://localhost", "DB_NAME": "t", "JWT_SECRET": "s"}, clear=False):
            get_settings.cache_clear()
            settings = get_settings()
            assert settings.geographic_scope == "romania"


class TestProviderIngestionIndependent:
    def test_firms_normalizes_global_events_without_scope_filter(self):
        provider = FIRMSProvider(api_key="")
        record = {
            "latitude": "-3.0",
            "longitude": "-60.0",
            "acq_date": "2026-06-10",
            "acq_time": "1200",
            "confidence": "80",
            "frp": "10",
            "scan": "1",
            "track": "1",
        }
        ev = provider.normalize(record)
        assert ev.metadata["ingestion"]["is_romania"] is False


class TestSchedulerScope:
    @pytest.mark.anyio
    async def test_reconciliation_uses_scoped_baselines(self):
        from app.services.scheduler_service import SchedulerService

        repo = MagicMock()
        repo.regional_baselines = AsyncMock(return_value=[])
        repo.scope_policy = GeographicScopePolicy(GeographicScope.EUROPE)
        analytics = AnalyticsService(repo)
        analytics.reconcile_intelligence_events = AsyncMock(return_value={"active": []})
        firms = MagicMock()
        firms.source_name = "NASA FIRMS"
        firms.provider_id = "nasa.firms"
        firms.describe = MagicMock(return_value={"source": "NASA FIRMS", "provider_id": "nasa.firms"})
        firms.run = AsyncMock(return_value={"total": 0, "created": 0, "skipped": 0, "errors": 0})
        runs_repo = MagicMock()
        runs_repo.create_run = AsyncMock(return_value={"status": "success", "duration_seconds": 0.1})

        scheduler = SchedulerService(
            firms_provider=firms,
            events_service=MagicMock(),
            events_repo=MagicMock(),
            analytics_service=analytics,
            intelligence_service=MagicMock(),
            runs_repo=runs_repo,
            enabled=True,
            reconciliation_lock=MagicMock(try_acquire=AsyncMock(return_value=True), release=AsyncMock()),
        )
        await scheduler._run_cycle()
        analytics.reconcile_intelligence_events.assert_awaited_once()


class TestAlertsScope:
    def test_europe_volume_uses_in_scope_count(self):
        sources = [{"source": "test", "total_events": 1, "romania_events": 0, "average_confidence": 0.8, "reliability_score": 0.5, "severity_distribution": {}}]
        alerts = _evaluate_alerts(sources, in_scope_event_count=20)
        assert any(a["type"] == "volume" for a in alerts)


class TestPhase0OracleCompatibility:
    def test_oracle_unchanged_with_explicit_romania_scope(self):
        verify_generated_match_manifest(generate_golden_artifacts())

    def test_phase0_repo_uses_explicit_scope(self):
        events = build_wildfire_events()
        repo = Phase0FixtureAnalyticsRepository(events, scope_policy=PHASE0_GEOGRAPHIC_SCOPE)
        assert repo.scope_policy.scope is GeographicScope.ROMANIA


class TestDeterminism:
    def test_repeated_europe_aggregation(self):
        policy = GeographicScopePolicy(GeographicScope.EUROPE)
        first = aggregate_regional_baselines_by_category(EUROPE_FIXTURE_EVENTS, _NOW, scope_policy=policy)
        second = aggregate_regional_baselines_by_category(EUROPE_FIXTURE_EVENTS, _NOW, scope_policy=policy)
        assert first == second


class TestWildfireEuropeInclusion:
    @pytest.mark.anyio
    async def test_european_wildfire_in_baselines(self):
        events = EUROPE_FIXTURE_EVENTS
        repo = Phase0FixtureAnalyticsRepository(
            events,
            scope_policy=GeographicScopePolicy(GeographicScope.EUROPE),
        )
        rows = await repo.regional_baselines(_NOW)
        regions = {r["_id"]["region"] for r in rows if r["_id"]["incident_category"] == "wildfire"}
        assert "Galicia" in regions
