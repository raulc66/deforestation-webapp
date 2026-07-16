"""Weather provider abstraction layer.

Abstract contract
-----------------
``WeatherProvider``       — the only interface WeatherService depends on.

Bundled implementations
-----------------------
``OpenMeteoProvider``     — free, no API key required (https://open-meteo.com).

Extensibility
-------------
Add a new provider (OpenWeatherMap, WeatherAPI, custom IoT sensor, …) by:
  1. Subclassing ``WeatherProvider``.
  2. Implementing ``fetch_regions()``.
  3. Passing the new instance to ``WeatherService.__init__()``.

No business logic or MongoDB code lives here.

Open-Meteo API notes
--------------------
* Endpoint: ``GET https://api.open-meteo.com/v1/forecast``
* Required params: ``latitude``, ``longitude``
* ``current=temperature_2m,relative_humidity_2m,wind_speed_10m,
       wind_direction_10m,precipitation,weathercode``
* ``timezone=Europe/Bucharest`` (returns local time strings; we parse UTC offset).
* Free tier: no rate limit stated; we apply a soft semaphore of 5 concurrent
  requests to be a good citizen.
* On any HTTP error or timeout the provider logs a warning and returns a
  ``WeatherObservation`` with ``source="open_meteo"`` and ``confidence=0.0``,
  so the risk engine can fall back to the neutral weather score gracefully.
"""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence

logger = logging.getLogger("forestwatch.weather_provider")

# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------


@dataclass
class WeatherObservation:
    """One weather snapshot for a single monitored region.

    All numeric fields follow SI/meteorological conventions:
        temperature     °C
        humidity        % (0–100)
        wind_speed      km/h
        wind_direction  degrees clockwise from north (0–360)
        precipitation   mm (accumulated since last hour)
        weather_code    WMO Weather Interpretation Code (integer)
    """

    region: str
    latitude: float
    longitude: float
    temperature: float
    humidity: float
    wind_speed: float
    wind_direction: float
    precipitation: float
    weather_code: int
    observed_at: datetime
    source: str = "unknown"
    confidence: float = 1.0  # 0.0 = failed fetch; 1.0 = successful


# ---------------------------------------------------------------------------
# Abstract provider contract
# ---------------------------------------------------------------------------


class WeatherProvider(ABC):
    """Abstract base for any weather data source."""

    @abstractmethod
    async def fetch_regions(
        self,
        regions: Sequence[tuple[str, float, float]],
    ) -> list[WeatherObservation]:
        """Fetch current weather for one or more (region, lat, lon) triples.

        Implementers must:
        * Return one ``WeatherObservation`` per input region (same order is
          recommended but not required; WeatherService matches by region name).
        * On individual-region failure: return a low-confidence observation
          rather than raising.  Only raise on catastrophic errors (e.g. invalid
          API key) that affect the entire batch.

        Parameters
        ----------
        regions:
            Iterable of ``(region_name, latitude, longitude)`` tuples.

        Returns
        -------
        list[WeatherObservation]
        """
        ...

    @property
    def name(self) -> str:
        """Human-readable provider name for logging and API metadata."""
        return type(self).__name__


# ---------------------------------------------------------------------------
# Open-Meteo implementation
# ---------------------------------------------------------------------------

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
_OPEN_METEO_CURRENT_FIELDS = (
    "temperature_2m,"
    "relative_humidity_2m,"
    "wind_speed_10m,"
    "wind_direction_10m,"
    "precipitation,"
    "weathercode"
)
_DEFAULT_TIMEOUT = 10.0   # seconds per request
_MAX_CONCURRENCY = 5      # simultaneous HTTP requests


def _build_failed_observation(
    region: str,
    lat: float,
    lon: float,
    now: datetime,
) -> WeatherObservation:
    """Return a zero-confidence observation used when a fetch fails."""
    return WeatherObservation(
        region=region,
        latitude=lat,
        longitude=lon,
        temperature=15.0,   # temperate neutral value
        humidity=60.0,      # moderate neutral value
        wind_speed=0.0,
        wind_direction=0.0,
        precipitation=0.0,
        weather_code=0,
        observed_at=now,
        source="open_meteo",
        confidence=0.0,     # signals fetch failure to consumers
    )


class OpenMeteoProvider(WeatherProvider):
    """Fetch current conditions from the free Open-Meteo forecast API.

    No API key required.  Concurrent requests are throttled by a semaphore
    to avoid overwhelming the endpoint when many regions are queried at once.
    """

    def __init__(
        self,
        timeout: float = _DEFAULT_TIMEOUT,
        max_concurrency: int = _MAX_CONCURRENCY,
    ) -> None:
        self._timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrency)

    @property
    def name(self) -> str:
        return "Open-Meteo"

    async def fetch_regions(
        self,
        regions: Sequence[tuple[str, float, float]],
    ) -> list[WeatherObservation]:
        """Fetch all regions concurrently, respecting the semaphore limit."""
        tasks = [
            self._fetch_one(region, lat, lon)
            for region, lat, lon in regions
        ]
        return list(await asyncio.gather(*tasks))

    async def _fetch_one(
        self,
        region: str,
        lat: float,
        lon: float,
    ) -> WeatherObservation:
        """Fetch one region; return a zero-confidence stub on any error."""
        now = datetime.now(timezone.utc)
        async with self._semaphore:
            try:
                import httpx
                params = {
                    "latitude": lat,
                    "longitude": lon,
                    "current": _OPEN_METEO_CURRENT_FIELDS,
                    "timezone": "Europe/Bucharest",
                    "wind_speed_unit": "kmh",
                }
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.get(_OPEN_METEO_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
                return self._parse_response(region, lat, lon, data, now)
            except Exception as exc:
                logger.warning(
                    "Open-Meteo fetch failed for region %r (%.4f, %.4f): %s",
                    region, lat, lon, exc,
                )
                return _build_failed_observation(region, lat, lon, now)

    @staticmethod
    def _parse_response(
        region: str,
        lat: float,
        lon: float,
        data: dict,
        fallback_time: datetime,
    ) -> WeatherObservation:
        """Parse a single Open-Meteo ``/v1/forecast`` JSON response."""
        current = data.get("current") or {}

        # Open-Meteo returns a local time string; use UTC arrival time as
        # observed_at to keep everything in UTC.
        observed_at = fallback_time

        return WeatherObservation(
            region=region,
            latitude=lat,
            longitude=lon,
            temperature=float(current.get("temperature_2m", 15.0)),
            humidity=float(current.get("relative_humidity_2m", 60.0)),
            wind_speed=float(current.get("wind_speed_10m", 0.0)),
            wind_direction=float(current.get("wind_direction_10m", 0.0)),
            precipitation=float(current.get("precipitation", 0.0)),
            weather_code=int(current.get("weathercode", 0)),
            observed_at=observed_at,
            source="open_meteo",
            confidence=1.0,
        )
