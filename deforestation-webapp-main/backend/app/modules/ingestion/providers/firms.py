"""NASA FIRMS wildfire ingestion provider.

Fetches active fire detections from the NASA FIRMS Near Real-Time API and
normalizes them into ForestEventCreate records inserted via the shared
persistence layer (dedupe + ForestEventService).

API reference: https://firms.modaps.eosdis.nasa.gov/api/

Behaviour:
- When FIRMS_API_KEY is set in the environment, the provider calls the live
  FIRMS CSV endpoint for the configured world-area over the last N days.
- When FIRMS_API_KEY is absent (local dev / CI), a bundled mock dataset
  that mirrors the real CSV format is returned instead.  The mock contains
  both Romanian and non-Romanian records to exercise the full classification
  path.

Public surface (used by manual trigger routes or future scheduler):
    provider = FIRMSProvider()
    result   = await provider.run(events_service, events_repo)
    # result -> {"created": int, "skipped": int, "errors": int}
"""
from __future__ import annotations

import asyncio
import csv
import io
import logging
import os
from datetime import datetime, timezone
from typing import Any

from app.core.geography.romania import ROMANIA_BBOX, is_romania_event
from app.core.ingestion.ingestion_metadata import build_ingestion_metadata
from app.core.ingestion.provider_contract import IngestionProvider
from app.core.ecosystem.incident_categories import IncidentCategory
from app.models.forest_event import ForestEventCreate
from app.modules.ingestion.persist import persist_import_event
from app.repositories.forest_event_repository import ForestEventRepository
from app.services.forest_event_service import ForestEventService

logger = logging.getLogger("forestwatch.ingestion.firms")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FIRMS_SOURCE_NAME = "NASA FIRMS"
FIRMS_PROVIDER_ID = "nasa.firms"
FIRMS_DATASET_ID = "firms.viirs_snpp_nrt"
FIRMS_DATASET_VERSION = "viirs-snpp-nrt-v1"

# VIIRS S-NPP NRT product, global area query, last 1 day.
# Full format: /api/area/csv/{key}/VIIRS_SNPP_NRT/{W,S,E,N}/{days}
_FIRMS_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
_PRODUCT = "VIIRS_SNPP_NRT"
_DAYS = 1

# World bounding box (fetches global data; narrow for production use).
_WORLD_BBOX = "-180,-90,180,90"

# Confidence string → float mapping for VIIRS categorical confidence field.
_CONFIDENCE_MAP: dict[str, float] = {
    "l": 0.3,
    "low": 0.3,
    "n": 0.7,
    "nominal": 0.7,
    "h": 0.9,
    "high": 0.9,
}

# ---------------------------------------------------------------------------
# Mock dataset — mirrors actual FIRMS VIIRS_SNPP CSV columns.
# Includes Romania coords (bbox hit), a Romanian region name, and a
# global (non-Romania) record to exercise fallback behaviour.
# ---------------------------------------------------------------------------

MOCK_FIRMS_DATA: list[dict[str, str]] = [
    # Inside Romania bounding box — bbox detection path
    {
        "latitude": "45.8560",
        "longitude": "24.9745",
        "brightness": "332.4",
        "scan": "0.40",
        "track": "0.37",
        "acq_date": "2026-06-10",
        "acq_time": "0845",
        "satellite": "N",
        "confidence": "nominal",
        "version": "2.0NRT",
        "bright_t31": "295.3",
        "frp": "12.8",
        "daynight": "D",
    },
    # Also inside Romania bbox — different location to test dedup distinctness
    {
        "latitude": "46.7700",
        "longitude": "23.5900",
        "brightness": "361.2",
        "scan": "0.41",
        "track": "0.38",
        "acq_date": "2026-06-10",
        "acq_time": "0847",
        "satellite": "N",
        "confidence": "high",
        "version": "2.0NRT",
        "bright_t31": "299.1",
        "frp": "87.5",
        "daynight": "D",
    },
    # Global record (Amazon, Brazil) — non-Romania path
    {
        "latitude": "-3.5120",
        "longitude": "-62.2480",
        "brightness": "342.0",
        "scan": "0.39",
        "track": "0.36",
        "acq_date": "2026-06-10",
        "acq_time": "1423",
        "satellite": "N",
        "confidence": "high",
        "version": "2.0NRT",
        "bright_t31": "288.7",
        "frp": "43.2",
        "daynight": "D",
    },
    # Low-confidence record — exercises low confidence path
    {
        "latitude": "44.3300",
        "longitude": "26.0500",
        "brightness": "305.1",
        "scan": "0.38",
        "track": "0.35",
        "acq_date": "2026-06-10",
        "acq_time": "0850",
        "satellite": "N",
        "confidence": "low",
        "version": "2.0NRT",
        "bright_t31": "291.2",
        "frp": "4.1",
        "daynight": "D",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_confidence(raw: str) -> float:
    """Map FIRMS confidence string or 0-100 integer to a 0.0-1.0 float."""
    s = raw.strip().lower()
    if s in _CONFIDENCE_MAP:
        return _CONFIDENCE_MAP[s]
    try:
        pct = float(s)
        return max(0.0, min(1.0, pct / 100.0))
    except ValueError:
        return 0.7  # VIIRS nominal default


def _parse_detected_at(acq_date: str, acq_time: str) -> datetime:
    """Combine FIRMS acq_date (YYYY-MM-DD) and acq_time (HHMM) into UTC datetime."""
    try:
        hour = int(acq_time[:2])
        minute = int(acq_time[2:])
        date = datetime.strptime(acq_date.strip(), "%Y-%m-%d").replace(
            hour=hour, minute=minute, tzinfo=timezone.utc
        )
        return date
    except (ValueError, IndexError):
        return datetime.now(timezone.utc)


def _severity_from_frp(frp_str: str) -> str:
    """Infer severity from Fire Radiative Power (megawatts)."""
    try:
        frp = float(frp_str)
    except (ValueError, TypeError):
        return "medium"
    if frp < 10:
        return "low"
    if frp < 50:
        return "medium"
    if frp < 200:
        return "high"
    return "critical"


def _affected_area_from_scan_track(scan_str: str, track_str: str) -> float:
    """Estimate affected area in hectares from FIRMS pixel size (km × km)."""
    try:
        scan = float(scan_str)
        track = float(track_str)
        return round(scan * track * 100, 2)  # km² × 100 = ha
    except (ValueError, TypeError):
        return 1.0


def _country_region_from_event(lat: float, lng: float) -> tuple[str, str]:
    """Infer country and region from coordinates using geography utilities."""
    candidate = {"latitude": lat, "longitude": lng}
    if is_romania_event(candidate):
        return "Romania", "Carpathian Forest"
    return "Unknown", "Unknown"


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class FIRMSProvider(IngestionProvider):
    """NASA FIRMS active fire data provider.

    Designed to be instantiated per-run (stateless across calls).
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key: str = (
            api_key if api_key is not None else os.environ.get("FIRMS_API_KEY", "")
        ).strip()
        self._last_execution_mode: str | None = None

    @property
    def last_execution_mode(self) -> str | None:
        return self._last_execution_mode

    @property
    def source_name(self) -> str:
        return FIRMS_SOURCE_NAME

    @property
    def provider_id(self) -> str:
        return FIRMS_PROVIDER_ID

    @property
    def supported_incident_categories(self) -> tuple[str, ...]:
        return (IncidentCategory.WILDFIRE.value,)

    def describe(self) -> dict[str, Any]:
        access = "live" if self._api_key else "fixture"
        return {
            "source": FIRMS_SOURCE_NAME,
            "provider_id": FIRMS_PROVIDER_ID,
            "dataset_id": FIRMS_DATASET_ID,
            "dataset_version": FIRMS_DATASET_VERSION,
            "temporal_resolution": "near_real_time",
            "geographic_coverage": "Global (VIIRS SNPP NRT)",
            "spatial_model": "point_detection",
            "update_frequency": "daily_poll",
            "license": "NASA FIRMS open data policy",
            "live_access_status": access,
        }

    # ------------------------------------------------------------------
    # fetch — I/O layer
    # ------------------------------------------------------------------

    async def fetch(self) -> list[dict[str, Any]]:
        """Return raw FIRMS records as a list of dicts.

        Uses live API when FIRMS_API_KEY is configured, otherwise returns
        the bundled mock dataset.
        """
        if not self._api_key:
            logger.info(
                "FIRMS_API_KEY not configured — using mock dataset (%d records)",
                len(MOCK_FIRMS_DATA),
            )
            self._last_execution_mode = "fixture"
            return list(MOCK_FIRMS_DATA)

        url = f"{_FIRMS_BASE}/{self._api_key}/{_PRODUCT}/{_WORLD_BBOX}/{_DAYS}"
        logger.info("Fetching FIRMS data from %s", url)
        loop = asyncio.get_event_loop()
        try:
            raw_csv = await loop.run_in_executor(None, self._http_get, url)
            self._last_execution_mode = "live"
            return self._parse_csv(raw_csv)
        except Exception as exc:
            logger.error("FIRMS fetch failed: %s — falling back to mock data", exc)
            self._last_execution_mode = "fixture"
            return list(MOCK_FIRMS_DATA)

    @staticmethod
    def _http_get(url: str) -> str:
        import requests  # already in requirements.txt

        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text

    @staticmethod
    def _parse_csv(text: str) -> list[dict[str, Any]]:
        reader = csv.DictReader(io.StringIO(text))
        return [dict(row) for row in reader]

    # ------------------------------------------------------------------
    # normalize — mapping layer
    # ------------------------------------------------------------------

    def normalize(self, raw: dict[str, Any]) -> ForestEventCreate:
        """Map a single FIRMS row to a ForestEventCreate.

        Required FIRMS fields: latitude, longitude, acq_date, acq_time,
        confidence, frp, scan, track.
        """
        lat = float(raw["latitude"])
        lng = float(raw["longitude"])
        detected_at = _parse_detected_at(raw.get("acq_date", ""), raw.get("acq_time", "0000"))
        confidence = _parse_confidence(raw.get("confidence", "nominal"))
        severity = _severity_from_frp(raw.get("frp", "0"))
        affected_area_ha = _affected_area_from_scan_track(
            raw.get("scan", "0"), raw.get("track", "0")
        )
        country, region = _country_region_from_event(lat, lng)

        acq_date = raw.get("acq_date", "")
        title = f"FIRMS Fire {lat:.4f},{lng:.4f} {acq_date}"

        romania_flag = is_romania_event({"latitude": lat, "longitude": lng, "country": country})

        ingestion_meta = build_ingestion_metadata(
            source=FIRMS_SOURCE_NAME,
            source_event_id=None,
            is_romania=romania_flag,
            confidence=confidence,
            severity=severity,
            provider_id=FIRMS_PROVIDER_ID,
            dataset_id=FIRMS_DATASET_ID,
            dataset_version=FIRMS_DATASET_VERSION,
            provenance_label="nasa_firms_viirs",
        )

        return ForestEventCreate(
            title=title,
            country=country,
            region=region,
            latitude=lat,
            longitude=lng,
            event_type="wildfire",
            severity=severity,
            affected_area_ha=affected_area_ha,
            confidence=confidence,
            source_id=FIRMS_SOURCE_NAME,  # resolved to real ID in run()
            detected_at=detected_at,
            metadata={
                # Source-specific fields (kept for backward compat)
                "provider": "nasa_firms",
                "satellite": raw.get("satellite", ""),
                "product": _PRODUCT,
                "frp_mw": raw.get("frp", ""),
                "brightness_k": raw.get("brightness", ""),
                "daynight": raw.get("daynight", ""),
                "is_romania": romania_flag,
                # Standardized cross-source block
                "ingestion": ingestion_meta.model_dump(),
            },
        )

    # ------------------------------------------------------------------
    # run — orchestration layer
    # ------------------------------------------------------------------

    async def run(
        self,
        events_service: ForestEventService,
        events_repo: ForestEventRepository,
        source_id: str | None = None,
    ) -> dict[str, int]:
        """Fetch, normalize, and persist FIRMS events.

        Args:
            events_service: ForestEventService for insertion.
            events_repo: ForestEventRepository for dedupe queries.
            source_id: DataSource.id for "NASA FIRMS"; if None, falls back
                       to FIRMS_SOURCE_NAME string (test / offline use).

        Returns:
            {"created": int, "skipped": int, "errors": int, "total": int}
        """
        raw_records = await self.fetch()
        created = skipped = errors = 0
        seen_keys: set[str] = set()

        for raw in raw_records:
            try:
                payload = self.normalize(raw)
                if source_id:
                    payload = payload.model_copy(update={"source_id": source_id})

                result = await persist_import_event(
                    events_service, events_repo, payload, seen_keys=seen_keys
                )
                if result == "created":
                    created += 1
                else:
                    skipped += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("FIRMS record skipped due to error: %s | raw=%s", exc, raw)
                errors += 1

        total = len(raw_records)
        logger.info(
            "FIRMS run complete: %d created / %d skipped / %d errors / %d total",
            created, skipped, errors, total,
        )
        return {"created": created, "skipped": skipped, "errors": errors, "total": total}
