"""Copernicus EMS Rapid Mapping activation provider.

Source
------
Copernicus Emergency Management Service — Rapid Mapping public activations API.

Verified public access (no authentication):
  - Documentation: https://mapping.emergency.copernicus.eu/about/how-to-harvest-cems-mapping-data/emergency-response-data/
  - List endpoint: https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations-info/

Each activation is an authoritative European emergency mapping event — not a static
context layer. Hazard type (flood, wildfire, earthquake, etc.) is carried in evidence,
not as a separate incident category per hazard.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.core.ecosystem.environmental_hazard_constants import (
    normalize_hazard_type,
    severity_from_activation,
)
from app.core.ecosystem.incident_categories import IncidentCategory
from app.core.ingestion.ingestion_metadata import build_ingestion_metadata
from app.core.ingestion.provider_contract import IngestionProvider
from app.models.forest_event import ForestEventCreate

logger = logging.getLogger("forestwatch.ingestion.cems")

CEMS_SOURCE_NAME = "Copernicus EMS Rapid Mapping"
CEMS_PROVIDER_ID = "cems.rapid_mapping"
CEMS_DATASET_ID = "copernicus.ems.rapid_mapping"
CEMS_DATASET_VERSION = "public-activations-info-v1"
CEMS_LICENSE = "Copernicus data policy — free and open; attribution EMS/EU"
CEMS_API_BASE = (
    "https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations-info/"
)
CEMS_MAX_LIVE_RECORDS = 50
CEMS_REQUEST_TIMEOUT_SECONDS = 30

_POINT_RE = re.compile(
    r"POINT\s*\(\s*([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s*\)",
    re.IGNORECASE,
)

from app.core.geography.europe import is_europe_country


def parse_wkt_point(centroid: str | None) -> tuple[float, float] | None:
    if not centroid:
        return None
    match = _POINT_RE.search(str(centroid))
    if not match:
        return None
    lng, lat = float(match.group(1)), float(match.group(2))
    return lat, lng


def primary_country(countries: list[str] | None) -> str:
    if not countries:
        return "Unknown"
    return str(countries[0])


def is_european_activation(countries: list[str] | None) -> bool:
    if not countries:
        return False
    return any(is_europe_country(c) for c in countries)


class CEMSRapidMappingProvider(IngestionProvider):
    """Copernicus EMS Rapid Mapping emergency activation provider."""

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self._records = records if records is not None else list(_DEFAULT_FIXTURE_RECORDS)
        self._last_fetch_at: datetime | None = None
        self._last_execution_mode: str | None = None

    @property
    def last_execution_mode(self) -> str | None:
        return self._last_execution_mode

    @property
    def source_name(self) -> str:
        return CEMS_SOURCE_NAME

    @property
    def provider_id(self) -> str:
        return CEMS_PROVIDER_ID

    @property
    def supported_incident_categories(self) -> tuple[str, ...]:
        return (IncidentCategory.ENVIRONMENTAL_HAZARD.value,)

    def describe(self) -> dict[str, Any]:
        return {
            "source": self.source_name,
            "provider_id": CEMS_PROVIDER_ID,
            "dataset_id": CEMS_DATASET_ID,
            "dataset_version": CEMS_DATASET_VERSION,
            "temporal_resolution": "activation_event",
            "geographic_coverage": "Global activations (Europe-filtered in fixture)",
            "spatial_model": "activation_centroid",
            "update_frequency": "near_real_time",
            "license": CEMS_LICENSE,
            "live_access_status": "public_api",
            "api_documentation": (
                "https://mapping.emergency.copernicus.eu/about/how-to-harvest-cems-mapping-data/"
            ),
            "api_endpoint": CEMS_API_BASE,
            "last_fetch_at": self._last_fetch_at.isoformat() if self._last_fetch_at else None,
        }

    async def fetch(self) -> list[dict[str, Any]]:
        try:
            records = await self._fetch_live()
            self._last_execution_mode = "live"
            self._last_fetch_at = datetime.now(timezone.utc)
            return records
        except Exception as exc:
            logger.warning(
                "CEMS live fetch unavailable (%s) — using deterministic fixture",
                exc,
            )
            self._last_execution_mode = "fixture"
            self._last_fetch_at = datetime.now(timezone.utc)
            return list(self._records)

    async def _fetch_live(self) -> list[dict[str, Any]]:
        loop = asyncio.get_event_loop()
        payload = await loop.run_in_executor(None, self._http_get_json, CEMS_API_BASE)
        results = payload.get("results") or []
        european = [row for row in results if is_european_activation(row.get("countries"))]
        return european[:CEMS_MAX_LIVE_RECORDS]

    @staticmethod
    def _http_get_json(url: str) -> dict[str, Any]:
        import requests

        resp = requests.get(
            url,
            params={"limit": CEMS_MAX_LIVE_RECORDS, "closed": "false"},
            timeout=CEMS_REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()

    def normalize(self, raw: dict[str, Any]) -> ForestEventCreate:
        code = str(raw.get("code") or raw.get("activation_code") or "").strip()
        if not code:
            raise ValueError("activation code is required")

        countries = list(raw.get("countries") or [])
        country = primary_country(countries)
        hazard_type = normalize_hazard_type(raw.get("category"))
        coords = parse_wkt_point(raw.get("centroid"))
        if coords is None:
            lat = float(raw.get("latitude") or 0.0)
            lng = float(raw.get("longitude") or 0.0)
        else:
            lat, lng = coords

        event_time = raw.get("eventTime") or raw.get("event_time")
        activation_time = raw.get("activationTime") or raw.get("activation_time")
        observed_at = _parse_datetime(activation_time or event_time)

        n_products = int(raw.get("n_products") or raw.get("nProducts") or 0)
        closed = bool(raw.get("closed", False))
        severity = severity_from_activation(
            n_products=n_products,
            closed=closed,
            hazard_type=hazard_type,
        )
        confidence = 0.95 if not closed and n_products > 0 else 0.75

        activation_block = {
            "activation_code": code,
            "hazard_type": hazard_type,
            "cems_category": str(raw.get("category") or hazard_type),
            "name": str(raw.get("name") or code),
            "countries": countries,
            "event_time": _iso_or_none(event_time),
            "activation_time": _iso_or_none(activation_time),
            "latitude": lat,
            "longitude": lng,
            "gdacs_id": raw.get("gdacsId"),
            "n_aois": int(raw.get("n_aois") or raw.get("nAois") or 0),
            "n_products": n_products,
            "closed": closed,
            "source": CEMS_SOURCE_NAME,
            "dataset_id": CEMS_DATASET_ID,
            "provenance": "copernicus_ems_activation",
        }

        ingestion_meta = build_ingestion_metadata(
            source=CEMS_SOURCE_NAME,
            source_event_id=code,
            is_romania=country == "Romania",
            confidence=confidence,
            severity=severity,
            provider_id=CEMS_PROVIDER_ID,
            dataset_id=CEMS_DATASET_ID,
            dataset_version=CEMS_DATASET_VERSION,
            provenance_label="copernicus_ems_activation",
        )

        return ForestEventCreate(
            title=str(raw.get("name") or f"{hazard_type.title()} activation {code}"),
            country=country,
            region=country,
            latitude=lat,
            longitude=lng,
            event_type="unknown",
            severity=severity,
            affected_area_ha=0.0,
            confidence=confidence,
            source_id=CEMS_SOURCE_NAME,
            detected_at=observed_at,
            metadata={
                "incident_category": IncidentCategory.ENVIRONMENTAL_HAZARD.value,
                "emergency_activation": activation_block,
                "ingestion": ingestion_meta.model_dump(),
            },
        )


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif value:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    else:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _iso_or_none(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


# Deterministic fixture — Romania + neighbouring European activations for baseline tests.
_DEFAULT_FIXTURE_RECORDS: list[dict[str, Any]] = [
    {
        "code": "EMSR-FIX-RO-01",
        "name": "Flood in Suceava county, Romania",
        "countries": ["Romania"],
        "category": "Flood",
        "centroid": "POINT (26.259 47.6353)",
        "eventTime": "2026-05-20T08:00:00",
        "activationTime": "2026-05-20T14:00:00",
        "closed": True,
        "n_aois": 2,
        "n_products": 2,
    },
    {
        "code": "EMSR-FIX-RO-02",
        "name": "Flood in Bacău county, Romania",
        "countries": ["Romania"],
        "category": "Flood",
        "centroid": "POINT (26.9146 46.567)",
        "eventTime": "2026-05-25T09:00:00",
        "activationTime": "2026-05-25T15:00:00",
        "closed": True,
        "n_aois": 1,
        "n_products": 1,
    },
    {
        "code": "EMSR-FIX-RO-03",
        "name": "Wildfire in Harghita, Romania",
        "countries": ["Romania"],
        "category": "Wildfire",
        "centroid": "POINT (25.7979 46.3548)",
        "eventTime": "2026-06-05T10:00:00",
        "activationTime": "2026-06-05T16:00:00",
        "closed": False,
        "n_aois": 2,
        "n_products": 3,
    },
    {
        "code": "EMSR-FIX-RO-04",
        "name": "Storm impact in Cluj, Romania",
        "countries": ["Romania"],
        "category": "Storm",
        "centroid": "POINT (23.6236 46.7712)",
        "eventTime": "2026-06-08T11:00:00",
        "activationTime": "2026-06-08T17:00:00",
        "closed": False,
        "n_aois": 1,
        "n_products": 2,
    },
    {
        "code": "EMSR-FIX-RO-05",
        "name": "Landslide in Brașov, Romania",
        "countries": ["Romania"],
        "category": "Landslide",
        "centroid": "POINT (25.601 45.657)",
        "eventTime": "2026-06-09T07:00:00",
        "activationTime": "2026-06-09T13:00:00",
        "closed": False,
        "n_aois": 1,
        "n_products": 1,
    },
    {
        "code": "EMSR-FIX-AL-01",
        "name": "Wildfire in Albania",
        "countries": ["Albania"],
        "category": "Wildfire",
        "centroid": "POINT (20.175944339073325 40.92481764445288)",
        "eventTime": "2026-06-10T06:00:00",
        "activationTime": "2026-06-10T07:38:00",
        "closed": False,
        "n_aois": 1,
        "n_products": 2,
    },
]
