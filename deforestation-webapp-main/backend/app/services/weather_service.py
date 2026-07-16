"""Weather Service — provider-agnostic weather enrichment for ForestWatch.

Responsibilities
----------------
1. Maintain a catalogue of Romanian region centroids (lat/lon).
2. Delegate fetching to a ``WeatherProvider`` (OpenMeteo by default).
3. Cache results in MongoDB via ``WeatherCacheRepository``.
4. Expose ``refresh()`` / ``refresh_if_stale()`` for the scheduler.
5. Expose ``get_current_weather()`` for the dashboard API (reads cache only).
6. Expose ``get_weather_by_region()`` for the risk engine (reads cache only).

Architecture note
-----------------
``WeatherService`` is independent of ``RiskService`` — it neither imports nor
calls it.  ``RiskService`` imports ``WeatherService`` to read weather inputs.
There are no circular dependencies.

Pure helper
-----------
``compute_weather_score(temperature, humidity, wind_speed, precipitation)``
returns a deterministic fire-weather sub-score in [0.0, 1.0].

Weather sub-score thresholds (all linear, clipped at endpoints)
----------------------------------------------------------------
    Temperature:    0°C → 0.0,   40°C → 1.0   (hot = higher fire risk)
    Humidity:     100% → 0.0,     0% → 1.0   (dry = higher fire risk)
    Wind speed:   0 km/h → 0.0, 80 km/h → 1.0 (strong wind = higher spread)
    Precipitation: 0 mm → 1.0,  20 mm → 0.0   (heavy rain = lower risk)

Internal weights within the weather sub-score:
    temperature   35 %
    humidity      30 %
    wind_speed    20 %
    precipitation 15 %
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.models.base import utcnow

if TYPE_CHECKING:
    from app.repositories.weather_cache_repository import WeatherCacheRepository
    from app.services.weather_provider import WeatherProvider

logger = logging.getLogger("forestwatch.weather")

# ---------------------------------------------------------------------------
# Romanian region centroids (WGS-84, approximate county seats / centroids)
# ---------------------------------------------------------------------------

#: Mapping of region name → (latitude, longitude).
#: Covers all 41 Romanian counties plus Bucharest/București.
ROMANIAN_REGION_CENTROIDS: dict[str, tuple[float, float]] = {
    "Alba":               (46.07, 23.58),
    "Arad":               (46.17, 21.31),
    "Argeș":              (44.85, 24.87),
    "Bacău":              (46.57, 26.91),
    "Bihor":              (47.05, 22.02),
    "Bistrița-Năsăud":   (47.14, 24.50),
    "Botoșani":           (47.75, 26.67),
    "Brașov":             (45.66, 25.62),
    "Brăila":             (45.27, 27.98),
    "Buzău":              (45.14, 26.83),
    "Caraș-Severin":      (45.20, 22.05),
    "Călărași":           (44.20, 26.33),
    "Cluj":               (46.78, 23.60),
    "Constanța":          (44.20, 28.68),
    "Covasna":            (45.87, 26.18),
    "Dâmbovița":          (44.93, 25.46),
    "Dolj":               (44.31, 23.81),
    "Galați":             (45.46, 28.03),
    "Giurgiu":            (43.90, 25.97),
    "Gorj":               (44.96, 23.28),
    "Harghita":           (46.50, 25.80),
    "Hunedoara":          (45.72, 22.92),
    "Ialomița":           (44.60, 27.38),
    "Iași":               (47.17, 27.58),
    "Ilfov":              (44.50, 26.12),
    "Maramureș":          (47.67, 24.10),
    "Mehedinți":          (44.63, 22.65),
    "Mureș":              (46.57, 24.57),
    "Neamț":              (46.93, 26.36),
    "Olt":                (44.43, 24.37),
    "Prahova":            (44.94, 26.00),
    "Satu Mare":          (47.80, 22.87),
    "Sălaj":              (47.17, 23.07),
    "Sibiu":              (45.80, 24.15),
    "Suceava":            (47.63, 26.25),
    "Teleorman":          (44.03, 25.36),
    "Timiș":              (45.75, 21.22),
    "Tulcea":             (45.18, 28.80),
    "Vâlcea":             (45.10, 24.37),
    "Vaslui":             (46.63, 27.73),
    "Vrancea":            (45.71, 27.01),
    # Bucharest appears under both spellings in the event data
    "Bucharest":          (44.43, 26.10),
    "București":          (44.43, 26.10),
}

# ---------------------------------------------------------------------------
# Pure weather sub-score helper — no I/O, fully testable in isolation
# ---------------------------------------------------------------------------

#: Internal weights for the weather sub-score components.
WEATHER_SUB_WEIGHTS: dict[str, float] = {
    "temperature":   0.35,
    "humidity":      0.30,
    "wind_speed":    0.20,
    "precipitation": 0.15,
}


def compute_weather_score(
    temperature: float = 15.0,
    humidity: float = 60.0,
    wind_speed: float = 0.0,
    precipitation: float = 0.0,
) -> float:
    """Return a deterministic fire-weather sub-score in [0.0000, 1.0000].

    Higher score = more dangerous weather conditions for wildfire spread.

    Parameters
    ----------
    temperature:    °C — range [0, 40] mapped linearly to [0, 1]
    humidity:       % — range [0, 100] mapped linearly to [1, 0] (inverted)
    wind_speed:     km/h — range [0, 80] mapped linearly to [0, 1]
    precipitation:  mm — range [0, 20] mapped linearly to [1, 0] (inverted)

    All inputs are clamped to their respective ranges before mapping.

    Example:
        30°C, 30% humidity, 50 km/h wind, 0 mm rain
        → t=0.75, h=0.70, w=0.625, p=1.0
        → 0.75×0.35 + 0.70×0.30 + 0.625×0.20 + 1.0×0.15 = 0.7
    """
    t_score = min(max(float(temperature) / 40.0, 0.0), 1.0)
    h_score = 1.0 - min(max(float(humidity) / 100.0, 0.0), 1.0)
    w_score = min(max(float(wind_speed) / 80.0, 0.0), 1.0)
    p_score = 1.0 - min(max(float(precipitation) / 20.0, 0.0), 1.0)

    raw = (
        t_score * WEATHER_SUB_WEIGHTS["temperature"]
        + h_score * WEATHER_SUB_WEIGHTS["humidity"]
        + w_score * WEATHER_SUB_WEIGHTS["wind_speed"]
        + p_score * WEATHER_SUB_WEIGHTS["precipitation"]
    )
    return round(min(max(raw, 0.0), 1.0), 4)


# ---------------------------------------------------------------------------
# WeatherService
# ---------------------------------------------------------------------------


class WeatherService:
    """Orchestrates weather fetching and caching for all Romanian regions.

    This service is independent of ``RiskService``; risk reads weather data
    from it, not the other way around.
    """

    def __init__(
        self,
        provider: WeatherProvider,
        cache_repo: WeatherCacheRepository,
        cache_ttl_minutes: int = 30,
    ) -> None:
        self._provider = provider
        self._cache = cache_repo
        self._ttl = cache_ttl_minutes

    # ------------------------------------------------------------------ #
    # Refresh (called by scheduler)
    # ------------------------------------------------------------------ #

    async def refresh(self) -> dict:
        """Fetch fresh weather for all Romanian regions and update the cache.

        Returns
        -------
        dict
            ``{"updated": int, "provider": str, "generated_at": datetime}``
        """
        regions = [
            (name, lat, lon)
            for name, (lat, lon) in ROMANIAN_REGION_CENTROIDS.items()
        ]
        observations = await self._provider.fetch_regions(regions)

        docs = [
            {
                "region":         obs.region,
                "latitude":       obs.latitude,
                "longitude":      obs.longitude,
                "temperature":    obs.temperature,
                "humidity":       obs.humidity,
                "wind_speed":     obs.wind_speed,
                "wind_direction": obs.wind_direction,
                "precipitation":  obs.precipitation,
                "weather_code":   obs.weather_code,
                "source":         obs.source,
                "confidence":     obs.confidence,
                "observed_at":    obs.observed_at,
            }
            for obs in observations
        ]

        updated = await self._cache.upsert_many(docs)
        now = utcnow()
        logger.info(
            "Weather cache refreshed — %d regions via %s",
            updated, self._provider.name,
        )
        return {
            "updated": updated,
            "provider": self._provider.name,
            "generated_at": now,
        }

    async def refresh_if_stale(self) -> dict | None:
        """Refresh only when the cache TTL has expired or is empty.

        Returns the refresh result dict, or None when the cache was fresh.
        """
        if await self._cache.is_stale(self._ttl):
            return await self.refresh()
        logger.debug("Weather cache is still fresh — skipping refresh")
        return None

    # ------------------------------------------------------------------ #
    # Reads (called by API endpoint and RiskService)
    # ------------------------------------------------------------------ #

    async def get_current_weather(self) -> dict:
        """Return cached weather for all regions, formatted for the API.

        Returns
        -------
        dict::

            {
                "generated_at": datetime,
                "provider": str,
                "cache_ttl_minutes": int,
                "regions": [
                    {
                        "region": "Suceava",
                        "temperature": 22.5,
                        "humidity": 60.0,
                        "wind_speed": 12.3,
                        "wind_direction": 180.0,
                        "precipitation": 0.0,
                        "weather_code": 1,
                        "updated_at": "..."
                    },
                    ...
                ]
            }
        """
        docs = await self._cache.get_all()
        now = utcnow()
        regions = []
        for doc in docs:
            updated_at = doc.get("cached_at") or doc.get("observed_at")
            if isinstance(updated_at, datetime):
                updated_at_str = updated_at.isoformat()
            else:
                updated_at_str = str(updated_at) if updated_at else None

            regions.append(
                {
                    "region":         doc.get("region", ""),
                    "temperature":    float(doc.get("temperature", 15.0)),
                    "humidity":       float(doc.get("humidity", 60.0)),
                    "wind_speed":     float(doc.get("wind_speed", 0.0)),
                    "wind_direction": float(doc.get("wind_direction", 0.0)),
                    "precipitation":  float(doc.get("precipitation", 0.0)),
                    "weather_code":   int(doc.get("weather_code", 0)),
                    "source":         str(doc.get("source", self._provider.name)),
                    "confidence":     float(doc.get("confidence", 1.0)),
                    "updated_at":     updated_at_str,
                }
            )

        return {
            "generated_at":     now,
            "provider":         self._provider.name,
            "cache_ttl_minutes": self._ttl,
            "regions":          regions,
        }

    async def get_weather_by_region(self) -> dict[str, dict]:
        """Return ``{region_name: weather_dict}`` mapping for the risk engine.

        Only regions present in the cache are included.  The risk engine
        defaults to a neutral score (0.5) for any region not in the result.
        """
        return await self._cache.get_all_as_dict()

    async def get_dataset_info(self) -> dict:
        """Return metadata about the weather provider and cache state."""
        cached_at = await self._cache.cached_at()
        return {
            "provider":          self._provider.name,
            "cache_ttl_minutes": self._ttl,
            "last_refresh":      cached_at.isoformat() if cached_at else None,
            "regions_monitored": len(ROMANIAN_REGION_CENTROIDS),
        }
