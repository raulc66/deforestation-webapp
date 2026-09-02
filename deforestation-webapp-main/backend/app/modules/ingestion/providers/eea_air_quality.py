"""EEA Air Quality e-Reporting provider (E2a/UTD monitoring stations).

Source
------
European Environment Agency Air Quality Download Service for verified (E1a)
and up-to-date (E2a/UTD) monitoring-station time series.

Documented access (verified public documentation):
  - Portal: https://aqportal.discomap.eea.europa.eu/download-data/
  - API Swagger: https://eeadmz1-downloads-api-appservice.azurewebsites.net/swagger/index.html
  - Token required: contact EEA (see UTD Air Quality Download Guide)

Live activation requires ``EEA_AQ_API_TOKEN`` — not committed to source control.
Without a token, a deterministic Romanian station fixture is used.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings, get_settings
from app.core.ecosystem.air_quality_constants import (
    is_missing_value,
    normalize_pollutant,
    normalize_unit,
)
from app.core.ecosystem.environmental_observation import EnvironmentalObservation
from app.core.ecosystem.incident_categories import IncidentCategory
from app.core.geography.romania import is_romania_event
from app.core.ingestion.ingestion_metadata import build_ingestion_metadata
from app.core.ingestion.provider_contract import IngestionProvider
from app.models.forest_event import ForestEventCreate

from .eea_aq_client import EEAAQDownloadClient
from .eea_aq_parquet import extract_parquet_rows, normalize_parquet_rows
from .eea_aq_station_metadata import EEAAQStationMetadata
from .eea_aq_validation import EEAAQValidationError

logger = logging.getLogger("forestwatch.ingestion.eea_aq")

EEA_AQ_SOURCE_NAME = "EEA Air Quality"
EEA_AQ_PROVIDER_ID = "eea.air_quality"
EEA_AQ_DATASET_ID = "eea.aq.e2a"
EEA_AQ_DATASET_VERSION = "fixture-v1"
EEA_AQ_LIVE_DATASET_VERSION = "e2a-live"
EEA_AQ_LICENSE = "EEA standard data policy — free and open for public use"
EEA_AQ_API_BASE = "https://eeadmz1-downloads-api-appservice.azurewebsites.net"

# Verified station metadata (Romania — deterministic fixture coordinates).
STATION_REGISTRY: dict[str, dict[str, Any]] = {
    "RO-BUC-AQ01": {
        "station_name": "Bucharest Urucu",
        "latitude": 44.4268,
        "longitude": 26.1025,
        "country": "Romania",
        "admin_region": "Bucharest",
    },
    "RO-CLJ-AQ01": {
        "station_name": "Cluj Napoca",
        "latitude": 46.7712,
        "longitude": 23.6236,
        "country": "Romania",
        "admin_region": "Cluj",
    },
    "RO-TM-AQ01": {
        "station_name": "Timișoara",
        "latitude": 45.7489,
        "longitude": 21.2087,
        "country": "Romania",
        "admin_region": "Timiș",
    },
}


def _severity_from_exceedance(pollutant: str, value: float) -> str:
    """Map concentration to severity bands (isolated configuration)."""
    limits = {"PM2.5": 25.0, "PM10": 50.0, "NO2": 40.0, "O3": 100.0, "SO2": 20.0}
    limit = limits.get(pollutant, 50.0)
    if value >= limit * 2:
        return "critical"
    if value >= limit * 1.5:
        return "high"
    if value >= limit:
        return "medium"
    return "low"


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for record in sorted(
        records,
        key=lambda item: (
            str(item.get("station_id")),
            str(item.get("pollutant")),
            str(item.get("observed_at")),
        ),
    ):
        identity = (
            f"{record.get('station_id')}:{record.get('pollutant')}:{record.get('observed_at')}"
        )
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(record)
    return deduped


class EEAAirQualityProvider(IngestionProvider):
    """EEA monitoring-station air quality observation provider."""

    def __init__(
        self,
        records: list[dict[str, Any]] | None = None,
        *,
        settings: Settings | None = None,
        download_client: EEAAQDownloadClient | None = None,
        station_metadata: EEAAQStationMetadata | None = None,
    ) -> None:
        self._records = records if records is not None else list(_DEFAULT_FIXTURE_RECORDS)
        self._settings = settings
        self._download_client = download_client
        self._station_metadata = station_metadata or EEAAQStationMetadata()
        self._last_fetch_at: datetime | None = None
        self._last_rejected_count: int = 0
        self._last_execution_mode: str | None = None

    @property
    def last_execution_mode(self) -> str | None:
        return self._last_execution_mode

    def _token(self) -> str:
        if self._settings is not None:
            return (self._settings.eea_aq_api_token or "").strip()
        return os.environ.get("EEA_AQ_API_TOKEN", "").strip()

    def _resolve_settings(self) -> Settings:
        if self._settings is not None:
            return self._settings
        return get_settings()

    @property
    def source_name(self) -> str:
        return EEA_AQ_SOURCE_NAME

    @property
    def provider_id(self) -> str:
        return EEA_AQ_PROVIDER_ID

    @property
    def supported_incident_categories(self) -> tuple[str, ...]:
        return (IncidentCategory.AIR_QUALITY.value,)

    @property
    def last_rejected_count(self) -> int:
        return self._last_rejected_count

    def describe(self) -> dict[str, Any]:
        return {
            "source": self.source_name,
            "provider_id": EEA_AQ_PROVIDER_ID,
            "dataset_id": EEA_AQ_DATASET_ID,
            "dataset_version": EEA_AQ_DATASET_VERSION,
            "temporal_resolution": "hourly",
            "geographic_coverage": "Europe (E2a/UTD monitoring stations)",
            "spatial_model": "monitoring_station",
            "update_frequency": "hourly (E2a/UTD)",
            "license": EEA_AQ_LICENSE,
            "live_access_status": self._live_access_status(),
            "api_documentation": f"{EEA_AQ_API_BASE}/swagger/index.html",
            "last_fetch_at": self._last_fetch_at.isoformat() if self._last_fetch_at else None,
        }

    def _live_access_status(self) -> str:
        if self._token():
            return "token_configured"
        return "fixture_only"

    async def fetch(self) -> list[dict[str, Any]]:
        token = self._token()
        if token:
            records = await self._fetch_live(token)
            self._last_execution_mode = "live"
            self._last_fetch_at = datetime.now(timezone.utc)
            return records

        self._last_execution_mode = "fixture"
        self._last_fetch_at = datetime.now(timezone.utc)
        return list(self._records)

    async def _fetch_live(self, token: str) -> list[dict[str, Any]]:
        client = self._download_client or EEAAQDownloadClient(settings=self._resolve_settings())
        owns_client = self._download_client is None
        try:
            zip_bytes = await client.download_parquet_zip(token=token)
            dataset_version = await client.fetch_dataset_version()
            await self._station_metadata.ensure_loaded()
            parquet_rows = extract_parquet_rows(zip_bytes)
            records, rejected = normalize_parquet_rows(
                parquet_rows,
                station_lookup=self._station_metadata.as_dict(),
                dataset_version=dataset_version or EEA_AQ_LIVE_DATASET_VERSION,
            )
            self._last_rejected_count = rejected
            if not records and rejected > 0:
                raise RuntimeError("EEA live dataset contained no valid observations")
            return _dedupe_records(records)
        finally:
            if owns_client:
                await client.aclose()

    def normalize(self, raw: dict[str, Any]) -> ForestEventCreate:
        pollutant = normalize_pollutant(raw.get("pollutant") or raw.get("Pollutant"))
        if not pollutant:
            raise ValueError("pollutant is required")

        value_raw = raw.get("value") if "value" in raw else raw.get("Value")
        if is_missing_value(value_raw):
            raise ValueError("missing or invalid measurement value")

        value = float(value_raw)
        unit = normalize_unit(pollutant, raw.get("unit") or raw.get("Unit"))

        station_id = str(raw.get("station_id") or raw.get("Station") or "UNKNOWN")
        station = STATION_REGISTRY.get(station_id, {})
        lat_raw = raw.get("latitude", station.get("latitude"))
        lng_raw = raw.get("longitude", station.get("longitude"))
        if lat_raw is None or lng_raw is None:
            raise EEAAQValidationError("missing station coordinates")
        lat = float(lat_raw)
        lng = float(lng_raw)
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
            raise EEAAQValidationError("invalid coordinates")

        observed_raw = raw.get("observed_at") or raw.get("datetime") or raw.get("DateTime")
        if isinstance(observed_raw, datetime):
            observed_at = observed_raw
        elif observed_raw:
            observed_at = datetime.fromisoformat(str(observed_raw).replace("Z", "+00:00"))
        else:
            observed_at = datetime.now(timezone.utc)

        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)

        country = str(raw.get("country") or station.get("country") or "Unknown")
        dataset_version = str(
            raw.get("dataset_version")
            or (EEA_AQ_LIVE_DATASET_VERSION if self._token() else EEA_AQ_DATASET_VERSION)
        )
        geographic_scope = "Romania" if country.lower() == "romania" else "Europe"

        observation = EnvironmentalObservation(
            pollutant=pollutant,
            value=value,
            unit=unit,
            observed_at=observed_at,
            latitude=lat,
            longitude=lng,
            station_id=station_id,
            station_name=str(raw.get("station_name") or station.get("station_name") or station_id),
            source=EEA_AQ_SOURCE_NAME,
            dataset_id=EEA_AQ_DATASET_ID,
            dataset_version=dataset_version,
            geographic_scope=geographic_scope,
            provenance="monitoring_station",
            validity=str(raw.get("validity") or "valid"),
        )

        severity = _severity_from_exceedance(pollutant, value)
        confidence = 0.95 if severity in {"high", "critical"} else 0.85

        event_stub = {
            "country": country,
            "region": station_id,
            "latitude": lat,
            "longitude": lng,
            "metadata": {"ingestion": {"is_romania": country.lower() == "romania"}},
        }
        is_romania = is_romania_event(event_stub) or country.lower() == "romania"

        ingestion_meta = build_ingestion_metadata(
            source=EEA_AQ_SOURCE_NAME,
            source_event_id=f"{station_id}:{pollutant}:{observed_at.isoformat()}",
            is_romania=is_romania,
            confidence=confidence,
            severity=severity,
            provider_id=EEA_AQ_PROVIDER_ID,
            dataset_id=EEA_AQ_DATASET_ID,
            dataset_version=dataset_version,
            provenance_label="monitoring_station",
        )

        return ForestEventCreate(
            title=f"{pollutant} {value:.1f} {unit} @ {station_id}",
            country=country,
            region=station_id,
            latitude=lat,
            longitude=lng,
            event_type="unknown",
            severity=severity,
            affected_area_ha=0.0,
            confidence=confidence,
            source_id=EEA_AQ_SOURCE_NAME,
            detected_at=observed_at,
            metadata={
                "incident_category": IncidentCategory.AIR_QUALITY.value,
                "observation": observation.to_metadata_block(),
                "ingestion": ingestion_meta.model_dump(),
            },
        )


# Deterministic fixture — Bucharest PM2.5 spike pattern for baseline tests.
_DEFAULT_FIXTURE_RECORDS: list[dict[str, Any]] = [
    {
        "station_id": "RO-BUC-AQ01",
        "pollutant": "PM2.5",
        "value": 18.0,
        "unit": "ug/m3",
        "observed_at": "2026-06-03T10:00:00+00:00",
        "latitude": STATION_REGISTRY["RO-BUC-AQ01"]["latitude"],
        "longitude": STATION_REGISTRY["RO-BUC-AQ01"]["longitude"],
        "country": "Romania",
    },
    {
        "station_id": "RO-BUC-AQ01",
        "pollutant": "PM2.5",
        "value": 20.0,
        "unit": "ug/m3",
        "observed_at": "2026-06-04T10:00:00+00:00",
        "latitude": STATION_REGISTRY["RO-BUC-AQ01"]["latitude"],
        "longitude": STATION_REGISTRY["RO-BUC-AQ01"]["longitude"],
        "country": "Romania",
    },
    {
        "station_id": "RO-BUC-AQ01",
        "pollutant": "PM2.5",
        "value": 22.0,
        "unit": "ug/m3",
        "observed_at": "2026-06-05T10:00:00+00:00",
        "latitude": STATION_REGISTRY["RO-BUC-AQ01"]["latitude"],
        "longitude": STATION_REGISTRY["RO-BUC-AQ01"]["longitude"],
        "country": "Romania",
    },
    {
        "station_id": "RO-BUC-AQ01",
        "pollutant": "PM2.5",
        "value": 55.0,
        "unit": "ug/m3",
        "observed_at": "2026-06-08T10:00:00+00:00",
        "latitude": STATION_REGISTRY["RO-BUC-AQ01"]["latitude"],
        "longitude": STATION_REGISTRY["RO-BUC-AQ01"]["longitude"],
        "country": "Romania",
    },
    {
        "station_id": "RO-BUC-AQ01",
        "pollutant": "PM2.5",
        "value": 60.0,
        "unit": "ug/m3",
        "observed_at": "2026-06-09T10:00:00+00:00",
        "latitude": STATION_REGISTRY["RO-BUC-AQ01"]["latitude"],
        "longitude": STATION_REGISTRY["RO-BUC-AQ01"]["longitude"],
        "country": "Romania",
    },
    {
        "station_id": "RO-BUC-AQ01",
        "pollutant": "PM2.5",
        "value": 58.0,
        "unit": "ug/m3",
        "observed_at": "2026-06-10T10:00:00+00:00",
        "latitude": STATION_REGISTRY["RO-BUC-AQ01"]["latitude"],
        "longitude": STATION_REGISTRY["RO-BUC-AQ01"]["longitude"],
        "country": "Romania",
    },
    {
        "station_id": "RO-CLJ-AQ01",
        "pollutant": "NO2",
        "value": 30.0,
        "unit": "ug/m3",
        "observed_at": "2026-06-10T11:00:00+00:00",
        "latitude": STATION_REGISTRY["RO-CLJ-AQ01"]["latitude"],
        "longitude": STATION_REGISTRY["RO-CLJ-AQ01"]["longitude"],
        "country": "Romania",
    },
    {
        "station_id": "RO-TM-AQ01",
        "pollutant": "O3",
        "value": 45.0,
        "unit": "ug/m3",
        "observed_at": "2026-06-10T12:00:00+00:00",
        "latitude": STATION_REGISTRY["RO-TM-AQ01"]["latitude"],
        "longitude": STATION_REGISTRY["RO-TM-AQ01"]["longitude"],
        "country": "Romania",
    },
]
