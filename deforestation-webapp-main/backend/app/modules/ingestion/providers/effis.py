"""EFFIS burned-area contextual wildfire enrichment provider.

Verified source
---------------
European Forest Fire Information System (Copernicus/JRC) public WFS:
  - Base: https://maps.effis.emergency.copernicus.eu/effis
  - Layer: modis.ba.poly.{year} (MODIS/VIIRS burned-area polygons)
  - Schema fields: id, FIREDATE, FINALDATE, COUNTRY, PROVINCE, AREA_HA, msGeometry
  - License: EU Copernicus/EFFIS open data policy
  - Authentication: none required for WFS GetFeature

Semantic role
-------------
EFFIS burned-area perimeters are **contextual wildfire evidence** — they confirm
historical burn scars near active FIRMS detections. They are NOT duplicate FIRMS
incident observations and are excluded from wildfire baseline aggregation.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings, get_settings
from app.core.ecosystem.incident_categories import IncidentCategory
from app.core.geography.geographic_scope import GeographicScope, parse_geographic_scope
from app.core.geography.romania import is_romania_event
from app.core.ingestion.ingestion_metadata import build_ingestion_metadata
from app.core.ingestion.provider_contract import IngestionProvider
from app.models.forest_event import ForestEventCreate

from .effis_constants import (
    EFFIS_DATASET_ID,
    EFFIS_DATASET_VERSION,
    EFFIS_DOCUMENTATION,
    EFFIS_LICENSE,
    EFFIS_PROVIDER_ID,
    EFFIS_SOURCE_NAME,
    EFFIS_WFS_BASE,
    EUROPE_WFS_BBOX,
    ROMANIA_WFS_BBOX,
)
from .effis_wfs_client import fetch_burned_area_features

logger = logging.getLogger("forestwatch.ingestion.effis")

_DEFAULT_FIXTURE_RECORDS: list[dict[str, Any]] = [
    {
        "id": "FIX-RO-001",
        "fire_id": "FIX-RO-001",
        "fire_date": "2024-06-08T00:00:00",
        "final_date": "2024-06-10T00:00:00",
        "country": "Romania",
        "province": "Suceava",
        "area_ha": "142.0",
        "latitude": 47.636,
        "longitude": 26.260,
        "layer": "modis.ba.poly.2024",
    },
    {
        "id": "FIX-DE-001",
        "fire_id": "FIX-DE-001",
        "fire_date": "2024-07-15T00:00:00",
        "final_date": "2024-07-18T00:00:00",
        "country": "Germany",
        "province": "Bavaria",
        "area_ha": "88.5",
        "latitude": 48.136,
        "longitude": 11.580,
        "layer": "modis.ba.poly.2024",
    },
    {
        "id": "FIX-GR-001",
        "fire_id": "FIX-GR-001",
        "fire_date": "2024-08-01T00:00:00",
        "final_date": "2024-08-05T00:00:00",
        "country": "Greece",
        "province": "Attica",
        "area_ha": "210.0",
        "latitude": 35.286,
        "longitude": 24.683,
        "layer": "modis.ba.poly.2024",
    },
]


def effis_spatial_key(fire_id: str) -> str:
    return f"effis-burn:{fire_id}"


def effis_source_event_id(layer: str, fire_id: str) -> str:
    return f"effis:{layer}:{fire_id}"


def _parse_effis_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    text = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def _severity_from_area_ha(area_ha: str | None) -> str:
    try:
        area = float(area_ha or 0)
    except ValueError:
        return "medium"
    if area >= 500:
        return "critical"
    if area >= 100:
        return "high"
    if area >= 20:
        return "medium"
    return "low"


class EFFISWildfireContextProvider(IngestionProvider):
    """EFFIS burned-area contextual provider — fixture-first, optional live WFS."""

    def __init__(
        self,
        records: list[dict[str, Any]] | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._records = records if records is not None else list(_DEFAULT_FIXTURE_RECORDS)
        self._settings = settings or get_settings()
        self._last_fetch_at: datetime | None = None
        self._last_execution_mode: str | None = None

    @property
    def last_execution_mode(self) -> str | None:
        return self._last_execution_mode

    @property
    def source_name(self) -> str:
        return EFFIS_SOURCE_NAME

    @property
    def provider_id(self) -> str:
        return EFFIS_PROVIDER_ID

    @property
    def supported_incident_categories(self) -> tuple[str, ...]:
        return (IncidentCategory.WILDFIRE.value,)

    def describe(self) -> dict[str, Any]:
        live_status = "public_wfs" if self._settings.enable_effis_live else "fixture_only"
        return {
            "source": self.source_name,
            "provider_id": EFFIS_PROVIDER_ID,
            "dataset_id": EFFIS_DATASET_ID,
            "dataset_version": EFFIS_DATASET_VERSION,
            "temporal_resolution": "burn_scar_perimeter",
            "geographic_coverage": "Europe (MODIS/VIIRS burned-area polygons)",
            "spatial_model": "burned_area_centroid",
            "update_frequency": "daily_layer_refresh",
            "license": EFFIS_LICENSE,
            "live_access_status": live_status,
            "api_documentation": EFFIS_DOCUMENTATION,
            "api_endpoint": EFFIS_WFS_BASE,
            "contextual_role": "wildfire_burned_area",
            "last_fetch_at": self._last_fetch_at.isoformat() if self._last_fetch_at else None,
        }

    async def fetch(self) -> list[dict[str, Any]]:
        if not self._settings.enable_effis_live:
            self._last_execution_mode = "fixture"
            self._last_fetch_at = datetime.now(timezone.utc)
            return list(self._records)
        try:
            records = await self._fetch_live()
            self._last_execution_mode = "live"
            self._last_fetch_at = datetime.now(timezone.utc)
            return records
        except Exception as exc:
            logger.warning("EFFIS live WFS unavailable (%s) — using deterministic fixture", exc)
            self._last_execution_mode = "fixture"
            self._last_fetch_at = datetime.now(timezone.utc)
            return list(self._records)

    async def _fetch_live(self) -> list[dict[str, Any]]:
        scope = parse_geographic_scope(self._settings.geographic_scope)
        bbox = ROMANIA_WFS_BBOX if scope is GeographicScope.ROMANIA else EUROPE_WFS_BBOX
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: fetch_burned_area_features(bbox=bbox),
        )

    def normalize(self, raw: dict[str, Any]) -> ForestEventCreate:
        fire_id = str(raw.get("fire_id") or raw.get("id") or "").strip()
        if not fire_id:
            raise ValueError("EFFIS fire_id is required")

        lat = float(raw["latitude"])
        lng = float(raw["longitude"])
        country = str(raw.get("country") or "Unknown").strip()
        province = str(raw.get("province") or country).strip()
        layer = str(raw.get("layer") or "modis.ba.poly")
        area_ha = raw.get("area_ha")
        fire_date = _parse_effis_timestamp(raw.get("fire_date"))
        severity = _severity_from_area_ha(area_ha)
        is_romania = is_romania_event({"country": country, "latitude": lat, "longitude": lng})

        source_event_id = effis_source_event_id(layer, fire_id)
        ingestion = build_ingestion_metadata(
            source=EFFIS_SOURCE_NAME,
            source_event_id=source_event_id,
            is_romania=is_romania,
            confidence=0.85,
            severity=severity,
            provider_id=EFFIS_PROVIDER_ID,
            dataset_id=EFFIS_DATASET_ID,
            dataset_version=EFFIS_DATASET_VERSION,
            provenance_label="effis_burned_area",
        )

        metadata: dict[str, Any] = {
            "incident_category": IncidentCategory.WILDFIRE.value,
            "contextual_role": "wildfire_burned_area",
            "spatial_key": effis_spatial_key(fire_id),
            "ingestion": ingestion,
            "effis_context": {
                "fire_id": fire_id,
                "fire_date": raw.get("fire_date"),
                "final_date": raw.get("final_date"),
                "area_ha": area_ha,
                "country": country,
                "province": province,
                "layer": layer,
                "dataset_id": EFFIS_DATASET_ID,
            },
            "provenance": {
                "provider_id": EFFIS_PROVIDER_ID,
                "source_id": EFFIS_PROVIDER_ID,
                "dataset_id": EFFIS_DATASET_ID,
                "dataset_version": EFFIS_DATASET_VERSION,
                "source_event_id": source_event_id,
                "observed_at": fire_date.isoformat(),
                "domain_evidence": {
                    "provider_class": "effis_wildfire_context",
                    "contextual_role": "wildfire_burned_area",
                    "country": country,
                },
            },
        }

        area_value = 0.0
        try:
            area_value = float(area_ha or 0)
        except (TypeError, ValueError):
            area_value = 0.0

        return ForestEventCreate(
            title=f"EFFIS burned area {fire_id} ({country})",
            latitude=lat,
            longitude=lng,
            region=province,
            country=country,
            event_type="unknown",
            severity=severity,
            affected_area_ha=area_value,
            confidence=0.85,
            detected_at=fire_date,
            metadata=metadata,
        )
