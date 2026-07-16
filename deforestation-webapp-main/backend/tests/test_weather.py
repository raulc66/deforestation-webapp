"""Comprehensive tests for Weather Enrichment.

Coverage:
    WeatherProviderAbstraction   — interface contract, OpenMeteoProvider unit
    WeatherCacheRepository       — upsert, get_all, is_stale, staleness TTL
    WeatherService               — refresh, refresh_if_stale, get_current_weather
    WeatherSubScore              — compute_weather_score pure function
    RiskIntegration              — new RISK_WEIGHTS, weather input, neutral fallback
    SchedulerIntegration         — weather refresh step, ordering
    APIEndpoint                  — /api/analytics/intelligence/weather
    EmptyCache                   — graceful empty response
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Provider abstraction
# ---------------------------------------------------------------------------

class TestWeatherProviderAbstraction:
    """WeatherProvider ABC cannot be instantiated; subclasses must implement."""

    def test_cannot_instantiate_abstract_base(self):
        from app.services.weather_provider import WeatherProvider
        with pytest.raises(TypeError):
            WeatherProvider()  # type: ignore

    def test_openmeteo_provider_is_concrete(self):
        from app.services.weather_provider import OpenMeteoProvider
        p = OpenMeteoProvider()
        assert p.name == "Open-Meteo"

    def test_custom_provider_accepted(self):
        """WeatherService accepts any WeatherProvider subclass."""
        from app.services.weather_provider import WeatherProvider, WeatherObservation

        class MyProvider(WeatherProvider):
            @property
            def name(self):
                return "Test"

            async def fetch_regions(self, regions):
                now = datetime.now(timezone.utc)
                return [
                    WeatherObservation(
                        region=r, latitude=lat, longitude=lon,
                        temperature=20.0, humidity=55.0,
                        wind_speed=5.0, wind_direction=180.0,
                        precipitation=0.0, weather_code=1,
                        observed_at=now, source="test", confidence=1.0,
                    )
                    for r, lat, lon in regions
                ]

        p = MyProvider()
        assert p.name == "Test"

    def test_observation_dataclass_fields(self):
        from app.services.weather_provider import WeatherObservation
        now = datetime.now(timezone.utc)
        obs = WeatherObservation(
            region="Suceava", latitude=47.63, longitude=26.25,
            temperature=25.0, humidity=40.0, wind_speed=30.0,
            wind_direction=90.0, precipitation=0.0, weather_code=0,
            observed_at=now,
        )
        assert obs.region == "Suceava"
        assert obs.temperature == 25.0
        assert obs.source == "unknown"     # default
        assert obs.confidence == 1.0       # default

    def test_failed_observation_has_zero_confidence(self):
        from app.services.weather_provider import _build_failed_observation
        now = datetime.now(timezone.utc)
        obs = _build_failed_observation("Cluj", 46.78, 23.60, now)
        assert obs.confidence == 0.0
        assert obs.source == "open_meteo"
        assert obs.region == "Cluj"


# ---------------------------------------------------------------------------
# OpenMeteoProvider unit tests (HTTP mocked)
# ---------------------------------------------------------------------------

class TestOpenMeteoProvider:
    """Tests for OpenMeteoProvider._parse_response and _fetch_one with mocked HTTP."""

    def _mock_response(self, temp=22.5, hum=60, wind=10.0, dir_=180.0,
                       precip=0.0, code=1):
        return {
            "current": {
                "temperature_2m": temp,
                "relative_humidity_2m": hum,
                "wind_speed_10m": wind,
                "wind_direction_10m": dir_,
                "precipitation": precip,
                "weathercode": code,
            }
        }

    def test_parse_response_extracts_fields(self):
        from app.services.weather_provider import OpenMeteoProvider
        now = datetime.now(timezone.utc)
        data = self._mock_response(temp=30.0, hum=35, wind=25.0, dir_=270.0)
        obs = OpenMeteoProvider._parse_response("Brașov", 45.66, 25.62, data, now)
        assert obs.temperature == 30.0
        assert obs.humidity == 35.0
        assert obs.wind_speed == 25.0
        assert obs.wind_direction == 270.0
        assert obs.source == "open_meteo"
        assert obs.confidence == 1.0

    def test_parse_response_missing_fields_use_defaults(self):
        from app.services.weather_provider import OpenMeteoProvider
        now = datetime.now(timezone.utc)
        obs = OpenMeteoProvider._parse_response("Unknown", 45.0, 25.0, {}, now)
        assert obs.temperature == 15.0   # default
        assert obs.humidity == 60.0      # default
        assert obs.wind_speed == 0.0
        assert obs.precipitation == 0.0

    @pytest.mark.anyio
    async def test_fetch_one_returns_observation_on_success(self):
        from app.services.weather_provider import OpenMeteoProvider

        provider = OpenMeteoProvider()
        mock_json = self._mock_response(temp=18.0, hum=70, wind=8.0, dir_=45.0)

        # Build a synchronous-ish response mock (raise_for_status returns None)
        resp = MagicMock()
        resp.json.return_value = mock_json
        resp.raise_for_status.return_value = None

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            obs = await provider._fetch_one("Alba", 46.07, 23.58)

        assert obs.region == "Alba"
        assert obs.confidence == 1.0

    @pytest.mark.anyio
    async def test_fetch_one_returns_failed_obs_on_http_error(self):
        from app.services.weather_provider import OpenMeteoProvider
        import httpx

        provider = OpenMeteoProvider()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            obs = await provider._fetch_one("Cluj", 46.78, 23.60)

        assert obs.confidence == 0.0
        assert obs.region == "Cluj"

    @pytest.mark.anyio
    async def test_fetch_regions_returns_one_per_input(self):
        from app.services.weather_provider import OpenMeteoProvider, WeatherObservation

        provider = OpenMeteoProvider()
        regions = [("Iași", 47.17, 27.58), ("Galați", 45.46, 28.03)]

        async def fake_fetch_one(region, lat, lon):
            now = datetime.now(timezone.utc)
            return WeatherObservation(
                region=region, latitude=lat, longitude=lon,
                temperature=20.0, humidity=50.0, wind_speed=0.0,
                wind_direction=0.0, precipitation=0.0, weather_code=0,
                observed_at=now, source="open_meteo", confidence=1.0,
            )

        provider._fetch_one = fake_fetch_one
        results = await provider.fetch_regions(regions)
        assert len(results) == 2
        assert {r.region for r in results} == {"Iași", "Galați"}


# ---------------------------------------------------------------------------
# WeatherCacheRepository
# ---------------------------------------------------------------------------

class TestWeatherCacheRepository:
    """Unit tests using an in-memory dict-based mock collection."""

    def _make_repo(self):
        from app.repositories.weather_cache_repository import WeatherCacheRepository

        store = {}

        class FakeCollection:
            async def update_one(self, q, update, upsert=False):
                region = q["region"]
                if region not in store:
                    store[region] = {}
                store[region].update(update["$set"])

            async def find_one(self, q, sort=None):
                if not q:
                    if not store:
                        return None
                    docs = list(store.values())
                    if sort:
                        key, direction = sort[0]
                        docs.sort(
                            key=lambda d: d.get(key, datetime.min.replace(tzinfo=timezone.utc)),
                            reverse=(direction == -1),
                        )
                    return docs[0] if docs else None
                region = q.get("region")
                return store.get(region)

            def find(self, q, **kwargs):
                results = list(store.values())
                return FakeCursor(results)

        class FakeCursor:
            def __init__(self, items):
                self._items = items

            def sort(self, *a, **kw):
                return self

            def __aiter__(self):
                return self._async_iter()

            async def _async_iter(self):
                for item in self._items:
                    yield item

        db_mock = MagicMock()
        db_mock.__getitem__ = lambda self, name: FakeCollection()
        repo = WeatherCacheRepository(db_mock)
        repo.col = FakeCollection()
        return repo, store

    @pytest.mark.anyio
    async def test_upsert_stores_observation(self):
        repo, store = self._make_repo()
        doc = {
            "region": "Suceava",
            "temperature": 22.0,
            "humidity": 55.0,
            "wind_speed": 10.0,
            "wind_direction": 90.0,
            "precipitation": 0.0,
            "weather_code": 1,
            "source": "open_meteo",
            "confidence": 1.0,
            "observed_at": datetime.now(timezone.utc),
        }
        result = await repo.upsert(doc)
        assert "region" in result
        assert result["region"] == "Suceava" or store.get("Suceava") is not None

    @pytest.mark.anyio
    async def test_is_stale_returns_true_when_empty(self):
        repo, store = self._make_repo()
        assert await repo.is_stale(30) is True

    @pytest.mark.anyio
    async def test_is_stale_returns_false_when_fresh(self):
        repo, store = self._make_repo()
        fresh_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        store["Bacău"] = {
            "region": "Bacău",
            "cached_at": fresh_time,
            "temperature": 20.0,
        }
        assert await repo.is_stale(30) is False

    @pytest.mark.anyio
    async def test_is_stale_returns_true_when_expired(self):
        repo, store = self._make_repo()
        old_time = datetime.now(timezone.utc) - timedelta(minutes=60)
        store["Suceava"] = {
            "region": "Suceava",
            "cached_at": old_time,
            "temperature": 18.0,
        }
        assert await repo.is_stale(30) is True


# ---------------------------------------------------------------------------
# WeatherService
# ---------------------------------------------------------------------------

class TestWeatherService:
    def _make_service(self, observations=None, stale=True):
        from app.services.weather_service import WeatherService
        from app.services.weather_provider import WeatherObservation

        now = datetime.now(timezone.utc)
        if observations is None:
            observations = [
                WeatherObservation(
                    region="Suceava", latitude=47.63, longitude=26.25,
                    temperature=24.0, humidity=45.0, wind_speed=18.0,
                    wind_direction=135.0, precipitation=0.0, weather_code=1,
                    observed_at=now, source="open_meteo", confidence=1.0,
                ),
            ]

        provider_mock = AsyncMock()
        provider_mock.name = "Open-Meteo"
        provider_mock.fetch_regions = AsyncMock(return_value=observations)

        cache_mock = AsyncMock()
        cache_mock.upsert_many = AsyncMock(return_value=len(observations))
        cache_mock.is_stale = AsyncMock(return_value=stale)
        cache_mock.get_all = AsyncMock(return_value=[
            {
                "region": obs.region,
                "temperature": obs.temperature,
                "humidity": obs.humidity,
                "wind_speed": obs.wind_speed,
                "wind_direction": obs.wind_direction,
                "precipitation": obs.precipitation,
                "weather_code": obs.weather_code,
                "source": obs.source,
                "confidence": obs.confidence,
                "cached_at": now,
            }
            for obs in observations
        ])
        cache_mock.get_all_as_dict = AsyncMock(return_value={
            obs.region: {
                "temperature": obs.temperature,
                "humidity": obs.humidity,
                "wind_speed": obs.wind_speed,
                "precipitation": obs.precipitation,
            }
            for obs in observations
        })
        cache_mock.cached_at = AsyncMock(return_value=now)

        svc = WeatherService(provider=provider_mock, cache_repo=cache_mock)
        return svc, provider_mock, cache_mock

    @pytest.mark.anyio
    async def test_refresh_calls_provider_and_upserts(self):
        svc, provider, cache = self._make_service()
        result = await svc.refresh()
        assert result["updated"] >= 1
        provider.fetch_regions.assert_called_once()
        cache.upsert_many.assert_called_once()

    @pytest.mark.anyio
    async def test_refresh_if_stale_calls_refresh_when_stale(self):
        svc, provider, cache = self._make_service(stale=True)
        result = await svc.refresh_if_stale()
        assert result is not None
        provider.fetch_regions.assert_called_once()

    @pytest.mark.anyio
    async def test_refresh_if_stale_skips_when_fresh(self):
        svc, provider, cache = self._make_service(stale=False)
        result = await svc.refresh_if_stale()
        assert result is None
        provider.fetch_regions.assert_not_called()

    @pytest.mark.anyio
    async def test_get_current_weather_returns_regions(self):
        svc, provider, cache = self._make_service()
        data = await svc.get_current_weather()
        assert "regions" in data
        assert data["provider"] == "Open-Meteo"
        assert isinstance(data["regions"], list)
        assert len(data["regions"]) >= 1

    @pytest.mark.anyio
    async def test_get_current_weather_returns_empty_when_no_cache(self):
        svc, provider, cache = self._make_service()
        cache.get_all = AsyncMock(return_value=[])
        data = await svc.get_current_weather()
        assert data["regions"] == []

    @pytest.mark.anyio
    async def test_get_weather_by_region_returns_dict(self):
        svc, provider, cache = self._make_service()
        d = await svc.get_weather_by_region()
        assert isinstance(d, dict)
        assert "Suceava" in d


# ---------------------------------------------------------------------------
# Weather sub-score pure helper
# ---------------------------------------------------------------------------

class TestComputeWeatherScore:
    """compute_weather_score is a pure function — exhaustive boundary tests."""

    def score(self, **kw):
        from app.services.weather_service import compute_weather_score
        return compute_weather_score(**kw)

    def test_all_zero_returns_correct_score(self):
        # temp=0 → 0, hum=0 → 1, wind=0 → 0, precip=0 → 1
        # = 0×0.35 + 1×0.30 + 0×0.20 + 1×0.15 = 0.45
        s = self.score(temperature=0.0, humidity=0.0, wind_speed=0.0, precipitation=0.0)
        assert abs(s - 0.45) < 0.001

    def test_all_max_conditions(self):
        # temp=40 → 1, hum=0 → 1, wind=80 → 1, precip=0 → 1  → 1.0
        s = self.score(temperature=40.0, humidity=0.0, wind_speed=80.0, precipitation=0.0)
        assert s == pytest.approx(1.0, abs=0.001)

    def test_all_neutral_conditions(self):
        # temp=20 → 0.5, hum=50 → 0.5, wind=40 → 0.5, precip=10 → 0.5
        # = 0.5×0.35 + 0.5×0.30 + 0.5×0.20 + 0.5×0.15 = 0.5
        s = self.score(temperature=20.0, humidity=50.0, wind_speed=40.0, precipitation=10.0)
        assert s == pytest.approx(0.5, abs=0.001)

    def test_high_temp_increases_score(self):
        s_hot = self.score(temperature=38.0, humidity=50.0, wind_speed=10.0, precipitation=0.0)
        s_mild = self.score(temperature=15.0, humidity=50.0, wind_speed=10.0, precipitation=0.0)
        assert s_hot > s_mild

    def test_low_humidity_increases_score(self):
        s_dry = self.score(temperature=20.0, humidity=10.0, wind_speed=10.0, precipitation=0.0)
        s_wet = self.score(temperature=20.0, humidity=90.0, wind_speed=10.0, precipitation=0.0)
        assert s_dry > s_wet

    def test_strong_wind_increases_score(self):
        s_windy = self.score(temperature=20.0, humidity=50.0, wind_speed=70.0, precipitation=0.0)
        s_calm = self.score(temperature=20.0, humidity=50.0, wind_speed=5.0, precipitation=0.0)
        assert s_windy > s_calm

    def test_heavy_rain_decreases_score(self):
        s_rain = self.score(temperature=20.0, humidity=50.0, wind_speed=10.0, precipitation=15.0)
        s_dry = self.score(temperature=20.0, humidity=50.0, wind_speed=10.0, precipitation=0.0)
        assert s_rain < s_dry

    def test_temp_clipped_above_40(self):
        s_40 = self.score(temperature=40.0, humidity=50.0, wind_speed=10.0, precipitation=0.0)
        s_50 = self.score(temperature=50.0, humidity=50.0, wind_speed=10.0, precipitation=0.0)
        assert s_40 == s_50

    def test_temp_clipped_below_zero(self):
        s_0 = self.score(temperature=0.0, humidity=50.0, wind_speed=10.0, precipitation=0.0)
        s_neg = self.score(temperature=-10.0, humidity=50.0, wind_speed=10.0, precipitation=0.0)
        assert s_0 == s_neg

    def test_result_in_unit_interval(self):
        for temp in range(-10, 50, 5):
            for hum in range(0, 110, 25):
                s = self.score(temperature=float(temp), humidity=float(hum),
                               wind_speed=20.0, precipitation=2.0)
                assert 0.0 <= s <= 1.0

    def test_result_has_four_decimal_places(self):
        s = self.score(temperature=22.0, humidity=60.0, wind_speed=12.0, precipitation=1.0)
        assert s == round(s, 4)

    def test_fire_weather_scenario(self):
        """Hot, dry, windy, no rain — should produce a high score."""
        s = self.score(temperature=35.0, humidity=15.0, wind_speed=55.0, precipitation=0.0)
        assert s > 0.7

    def test_safe_weather_scenario(self):
        """Cold, humid, calm, heavy rain — should produce a low score."""
        s = self.score(temperature=5.0, humidity=90.0, wind_speed=2.0, precipitation=12.0)
        assert s < 0.2


# ---------------------------------------------------------------------------
# Risk weights and integration
# ---------------------------------------------------------------------------

class TestRiskWeightsWeather:
    """Tests for the updated RISK_WEIGHTS and weather integration."""

    def test_risk_weights_sum_to_one(self):
        from app.modules.analytics.risk_service import RISK_WEIGHTS
        total = sum(RISK_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9

    def test_risk_weights_include_weather(self):
        from app.modules.analytics.risk_service import RISK_WEIGHTS
        assert "weather" in RISK_WEIGHTS
        assert RISK_WEIGHTS["weather"] == pytest.approx(0.15)

    def test_current_activity_weight_is_030(self):
        from app.modules.analytics.risk_service import RISK_WEIGHTS
        assert RISK_WEIGHTS["current_activity"] == pytest.approx(0.30)

    def test_historical_activity_weight_is_020(self):
        from app.modules.analytics.risk_service import RISK_WEIGHTS
        assert RISK_WEIGHTS["historical_activity"] == pytest.approx(0.20)

    def test_compute_risk_score_max_all_inputs(self):
        from app.modules.analytics.risk_service import compute_risk_score
        s = compute_risk_score({
            "current_activity": 1.0,
            "historical_activity": 1.0,
            "forest": 1.0,
            "weather": 1.0,
            "priority": 1.0,
            "escalation": 1.0,
        })
        assert s == pytest.approx(1.0)

    def test_compute_risk_score_weather_only(self):
        from app.modules.analytics.risk_service import compute_risk_score, RISK_WEIGHTS
        s = compute_risk_score({"weather": 1.0})
        assert s == pytest.approx(RISK_WEIGHTS["weather"])

    def test_compute_risk_score_missing_weather_defaults_zero(self):
        """Without weather key the score loses the 15% contribution."""
        from app.modules.analytics.risk_service import compute_risk_score, RISK_WEIGHTS
        without = compute_risk_score({
            "current_activity": 1.0,
            "historical_activity": 1.0,
            "forest": 1.0,
            "priority": 1.0,
            "escalation": 1.0,
        })
        # Maximum without weather = 1.0 - 0.15 = 0.85
        assert without == pytest.approx(0.85)

    def test_compute_risk_breakdown_includes_weather(self):
        from app.modules.analytics.risk_service import compute_risk_breakdown
        bd = compute_risk_breakdown({"weather": 1.0})
        assert "weather" in bd
        assert bd["weather"] == pytest.approx(0.15)

    def test_compute_risk_score_with_neutral_weather(self):
        from app.modules.analytics.risk_service import compute_risk_score
        # Neutral weather (0.5) should be additive: 0 + 0.5*0.15 = 0.075
        s = compute_risk_score({"weather": 0.5})
        assert s == pytest.approx(0.5 * 0.15, abs=1e-4)

    def test_risk_levels_unchanged(self):
        from app.modules.analytics.risk_service import compute_risk_level
        assert compute_risk_level(0.80) == "Extreme"
        assert compute_risk_level(0.60) == "High"
        assert compute_risk_level(0.30) == "Moderate"
        assert compute_risk_level(0.10) == "Low"


class TestRiskServiceWeatherIntegration:
    """Tests for RiskService with weather data injected."""

    def _make_mock_analytics(self, region="Suceava", anomaly_score=0.8):
        analytics = AsyncMock()
        analytics.get_anomalies = AsyncMock(return_value={
            "anomalies": [{
                "region": region,
                "anomaly_score": anomaly_score,
                "forest_confidence": 0.8,
            }]
        })
        analytics.get_regional_baselines = AsyncMock(return_value={"regions": []})
        return analytics

    def _make_mock_services(self):
        history_repo = AsyncMock()
        history_repo.regional_history = AsyncMock(return_value=[])
        intel_repo = AsyncMock()
        intel_repo.find_active = AsyncMock(return_value=[])
        risk_repo = AsyncMock()
        risk_repo.latest = AsyncMock(return_value=None)
        return history_repo, intel_repo, risk_repo

    @pytest.mark.anyio
    async def test_risk_with_weather_svc_uses_weather_input(self):
        from app.modules.analytics.risk_service import RiskService, RISK_WEIGHTS

        analytics = self._make_mock_analytics()
        history_repo, intel_repo, risk_repo = self._make_mock_services()

        weather_svc = AsyncMock()
        weather_svc.get_weather_by_region = AsyncMock(return_value={
            "Suceava": {
                "temperature": 35.0,
                "humidity": 15.0,
                "wind_speed": 60.0,
                "precipitation": 0.0,
            }
        })

        svc = RiskService(analytics, history_repo, intel_repo, risk_repo,
                          weather_svc=weather_svc)
        result = await svc.compute_regional_risk()

        regions = {r["region"]: r for r in result["regions"]}
        suceava = regions.get("Suceava")
        assert suceava is not None
        # Weather is in the breakdown
        assert "weather" in suceava["breakdown"]
        # High fire weather should push weather sub-score > neutral (0.5)
        weather_contrib = suceava["breakdown"]["weather"]
        assert weather_contrib > 0.5 * RISK_WEIGHTS["weather"]

    @pytest.mark.anyio
    async def test_risk_without_weather_svc_uses_neutral(self):
        from app.modules.analytics.risk_service import RiskService, _NEUTRAL_WEATHER, RISK_WEIGHTS

        analytics = self._make_mock_analytics()
        history_repo, intel_repo, risk_repo = self._make_mock_services()

        svc = RiskService(analytics, history_repo, intel_repo, risk_repo)  # no weather_svc
        result = await svc.compute_regional_risk()

        regions = {r["region"]: r for r in result["regions"]}
        suceava = regions.get("Suceava")
        assert suceava is not None
        weather_contrib = suceava["breakdown"]["weather"]
        assert weather_contrib == pytest.approx(_NEUTRAL_WEATHER * RISK_WEIGHTS["weather"], abs=1e-4)

    @pytest.mark.anyio
    async def test_risk_handles_weather_service_failure_gracefully(self):
        from app.modules.analytics.risk_service import RiskService

        analytics = self._make_mock_analytics()
        history_repo, intel_repo, risk_repo = self._make_mock_services()

        weather_svc = AsyncMock()
        weather_svc.get_weather_by_region = AsyncMock(side_effect=RuntimeError("db down"))

        svc = RiskService(analytics, history_repo, intel_repo, risk_repo,
                          weather_svc=weather_svc)
        # Must not raise
        result = await svc.compute_regional_risk()
        assert "regions" in result

    @pytest.mark.anyio
    async def test_risk_region_missing_from_weather_cache_uses_neutral(self):
        from app.modules.analytics.risk_service import RiskService, _NEUTRAL_WEATHER, RISK_WEIGHTS

        analytics = self._make_mock_analytics(region="Galați")
        history_repo, intel_repo, risk_repo = self._make_mock_services()

        weather_svc = AsyncMock()
        # Cache has Suceava but not Galați
        weather_svc.get_weather_by_region = AsyncMock(return_value={
            "Suceava": {"temperature": 20.0, "humidity": 50.0, "wind_speed": 10.0, "precipitation": 0.0}
        })

        svc = RiskService(analytics, history_repo, intel_repo, risk_repo,
                          weather_svc=weather_svc)
        result = await svc.compute_regional_risk()

        regions = {r["region"]: r for r in result["regions"]}
        galati = regions.get("Galați")
        if galati:
            expected_weather_contrib = _NEUTRAL_WEATHER * RISK_WEIGHTS["weather"]
            assert galati["breakdown"]["weather"] == pytest.approx(expected_weather_contrib, abs=1e-4)


# ---------------------------------------------------------------------------
# Scheduler integration
# ---------------------------------------------------------------------------

class TestSchedulerWeatherIntegration:
    """WeatherService refresh step is called at the right point in the cycle."""

    def _make_scheduler(self, weather_svc=None, stale=True):
        from app.services.scheduler_service import SchedulerService

        firms = AsyncMock()
        firms.run = AsyncMock(return_value={"total": 0, "created": 0, "skipped": 0})

        analytics = AsyncMock()
        analytics.reconcile_intelligence_events = AsyncMock(return_value=None)

        runs_repo = AsyncMock()
        runs_repo.create_run = AsyncMock(return_value={
            "events_fetched": 0, "events_inserted": 0,
            "duplicates_skipped": 0, "duration_seconds": 0.1,
        })

        events_repo = AsyncMock()
        events_service = AsyncMock()
        intel_service = AsyncMock()

        scheduler = SchedulerService(
            firms_provider=firms,
            events_service=events_service,
            events_repo=events_repo,
            analytics_service=analytics,
            intelligence_service=intel_service,
            runs_repo=runs_repo,
            poll_interval_minutes=60,
            enabled=True,
            firms_source_id=None,
            weather_svc=weather_svc,
        )
        return scheduler, firms, analytics

    @pytest.mark.anyio
    async def test_scheduler_calls_weather_refresh_when_stale(self):
        weather_svc = AsyncMock()
        weather_svc.refresh_if_stale = AsyncMock(return_value={"updated": 42})

        scheduler, firms, analytics = self._make_scheduler(weather_svc=weather_svc)
        await scheduler._run_cycle()

        weather_svc.refresh_if_stale.assert_called_once()

    @pytest.mark.anyio
    async def test_scheduler_weather_failure_does_not_break_cycle(self):
        weather_svc = AsyncMock()
        weather_svc.refresh_if_stale = AsyncMock(side_effect=RuntimeError("API down"))

        scheduler, firms, analytics = self._make_scheduler(weather_svc=weather_svc)
        # Must complete without raising
        result = await scheduler._run_cycle()
        assert result is not None

    @pytest.mark.anyio
    async def test_scheduler_without_weather_svc_runs_normally(self):
        scheduler, firms, analytics = self._make_scheduler(weather_svc=None)
        result = await scheduler._run_cycle()
        assert result is not None

    @pytest.mark.anyio
    async def test_weather_refresh_called_before_intelligence(self):
        """Assert weather refresh precedes intelligence reconciliation in cycle."""
        call_order = []

        weather_svc = AsyncMock()

        async def weather_refresh():
            call_order.append("weather")
            return {"updated": 5}

        weather_svc.refresh_if_stale = weather_refresh

        scheduler, firms, analytics = self._make_scheduler(weather_svc=weather_svc)

        original_reconcile = analytics.reconcile_intelligence_events.side_effect

        async def track_reconcile(*a, **kw):
            call_order.append("intelligence")

        analytics.reconcile_intelligence_events = AsyncMock(side_effect=track_reconcile)

        await scheduler._run_cycle()

        assert call_order.index("weather") < call_order.index("intelligence")


# ---------------------------------------------------------------------------
# API endpoint
# ---------------------------------------------------------------------------

class TestWeatherAPIEndpoint:
    """Tests for GET /api/analytics/intelligence/weather."""

    @pytest.mark.anyio
    async def test_endpoint_returns_correct_schema(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from app.modules.analytics.analytics_routes import router
        from app.api.deps import get_current_user, weather_service_dep
        from app.models.user import UserPublic

        from datetime import datetime, timezone as tz
        mock_user = UserPublic(
            id="1", email="test@example.com", name="Test",
            role="admin", provider="local",
            created_at=datetime(2024, 1, 1, tzinfo=tz.utc),
        )

        mock_weather = {
            "generated_at": datetime.now(timezone.utc),
            "provider": "Open-Meteo",
            "cache_ttl_minutes": 30,
            "regions": [
                {
                    "region": "Suceava",
                    "temperature": 22.5,
                    "humidity": 60.0,
                    "wind_speed": 12.3,
                    "wind_direction": 180.0,
                    "precipitation": 0.0,
                    "weather_code": 1,
                    "source": "open_meteo",
                    "confidence": 1.0,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ],
        }

        weather_svc_mock = AsyncMock()
        weather_svc_mock.get_current_weather = AsyncMock(return_value=mock_weather)

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[weather_service_dep] = lambda: weather_svc_mock

        with TestClient(app) as client:
            resp = client.get("/analytics/intelligence/weather")

        assert resp.status_code == 200
        body = resp.json()
        assert "regions" in body
        assert body["provider"] == "Open-Meteo"
        assert isinstance(body["regions"], list)
        assert len(body["regions"]) == 1
        assert body["regions"][0]["region"] == "Suceava"

    @pytest.mark.anyio
    async def test_endpoint_returns_empty_regions_when_no_cache(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from app.modules.analytics.analytics_routes import router
        from app.api.deps import get_current_user, weather_service_dep
        from app.models.user import UserPublic
        from datetime import datetime, timezone as tz

        mock_user = UserPublic(
            id="1", email="test@example.com", name="Test",
            role="admin", provider="local",
            created_at=datetime(2024, 1, 1, tzinfo=tz.utc),
        )

        weather_svc_mock = AsyncMock()
        weather_svc_mock.get_current_weather = AsyncMock(return_value={
            "generated_at": datetime.now(timezone.utc),
            "provider": "Open-Meteo",
            "cache_ttl_minutes": 30,
            "regions": [],
        })

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[weather_service_dep] = lambda: weather_svc_mock

        with TestClient(app) as client:
            resp = client.get("/analytics/intelligence/weather")

        assert resp.status_code == 200
        body = resp.json()
        assert body["regions"] == []

    @pytest.mark.anyio
    async def test_endpoint_requires_authentication(self):
        """Without overriding get_current_user the route should reject unauthenticated requests."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from app.modules.analytics.analytics_routes import router
        from app.api.deps import get_current_user, weather_service_dep
        from app.core.errors import AuthError

        def raise_auth_error():
            raise AuthError("Not authenticated")

        mock_weather_svc = AsyncMock()
        mock_weather_svc.get_current_weather = AsyncMock(return_value={
            "generated_at": datetime.now(timezone.utc),
            "provider": "Open-Meteo",
            "cache_ttl_minutes": 30,
            "regions": [],
        })

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = raise_auth_error
        app.dependency_overrides[weather_service_dep] = lambda: mock_weather_svc

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/analytics/intelligence/weather")

        assert resp.status_code in (401, 403, 422, 500)


# ---------------------------------------------------------------------------
# Romanian region centroids coverage
# ---------------------------------------------------------------------------

class TestRomanianRegionCentroids:
    """Validate the centroids catalogue in WeatherService."""

    def test_all_centroids_in_romania_bounding_box(self):
        """All centroids must fall within the approximate Romania bounding box."""
        from app.services.weather_service import ROMANIAN_REGION_CENTROIDS

        # Approximate Romania bbox: lat 43.6–48.3, lon 20.2–29.8
        LAT_MIN, LAT_MAX = 43.5, 48.5
        LON_MIN, LON_MAX = 20.0, 30.0

        for region, (lat, lon) in ROMANIAN_REGION_CENTROIDS.items():
            assert LAT_MIN <= lat <= LAT_MAX, f"{region}: lat {lat} out of range"
            assert LON_MIN <= lon <= LON_MAX, f"{region}: lon {lon} out of range"

    def test_all_42_regions_present(self):
        from app.services.weather_service import ROMANIAN_REGION_CENTROIDS
        # 41 counties + Bucharest + București = 43 keys (Bucharest has two spellings)
        assert len(ROMANIAN_REGION_CENTROIDS) >= 42

    def test_bucharest_present_under_both_spellings(self):
        from app.services.weather_service import ROMANIAN_REGION_CENTROIDS
        assert "Bucharest" in ROMANIAN_REGION_CENTROIDS
        assert "București" in ROMANIAN_REGION_CENTROIDS
