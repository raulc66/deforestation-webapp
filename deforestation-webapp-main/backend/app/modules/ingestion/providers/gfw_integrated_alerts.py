"""Global Forest Watch integrated disturbance alerts provider — Romania MVP foundation."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings, get_settings
from app.core.ecosystem.forest_disturbance_constants import AuthorizationStatus
from app.core.ecosystem.incident_categories import IncidentCategory
from app.core.geography.geographic_scope import GeographicScope, parse_geographic_scope
from app.core.geography.romania import is_romania_event
from app.core.ingestion.ingestion_metadata import build_ingestion_metadata
from app.core.ingestion.provider_contract import IngestionProvider
from app.models.forest_event import ForestEventCreate
from app.modules.analytics.disturbance_assessment import assess_disturbance_context
from app.modules.analytics.disturbance_driver_classifier import classify_disturbance_driver
from app.services.forest_context_service import ForestContextService

from .gfw_integrated_alerts_client import fetch_integrated_alerts
from .gfw_integrated_alerts_constants import (
    EUROPE_QUERY_POLYGON,
    GFW_API_BASE,
    GFW_DATASET_ID,
    GFW_DATASET_VERSION,
    GFW_DOCUMENTATION,
    GFW_LICENSE,
    GFW_PROVIDER_ID,
    GFW_SOURCE_NAME,
    ROMANIA_QUERY_POLYGON,
)

logger = logging.getLogger("forestwatch.ingestion.gfw")

_DEFAULT_FIXTURE_RECORDS: list[dict[str, Any]] = [
    {
        "alert_id": "FIX-RO-LOG-001",
        "latitude": 47.12,
        "longitude": 25.98,
        "alert_date": "2026-05-18T00:00:00",
        "confidence": 0.88,
        "intensity": "moderate",
        "area_ha": 4.7,
        "country": "Romania",
        "region": "Harghita",
        "alert_source": "integrated",
        "repeat_count": 2,
    },
    {
        "alert_id": "FIX-RO-CLR-002",
        "latitude": 46.78,
        "longitude": 23.58,
        "alert_date": "2026-05-22T00:00:00",
        "confidence": 0.91,
        "intensity": "high",
        "area_ha": 18.2,
        "country": "Romania",
        "region": "Cluj",
        "alert_source": "integrated",
        "repeat_count": 1,
    },
    {
        "alert_id": "FIX-DE-LOG-003",
        "latitude": 48.40,
        "longitude": 10.00,
        "alert_date": "2026-05-20T00:00:00",
        "confidence": 0.84,
        "intensity": "moderate",
        "area_ha": 6.1,
        "country": "Germany",
        "region": "Bavaria",
        "alert_source": "integrated",
        "repeat_count": 1,
    },
    {
        "alert_id": "FIX-BR-OUT-004",
        "latitude": -3.1,
        "longitude": -60.0,
        "alert_date": "2026-05-19T00:00:00",
        "confidence": 0.8,
        "intensity": "high",
        "area_ha": 22.0,
        "country": "Brazil",
        "region": "Amazonas",
        "alert_source": "integrated",
        "repeat_count": 1,
    },
]


def disturbance_spatial_key(alert_id: str) -> str:
    return f"disturbance-alert:{alert_id}"


def disturbance_source_event_id(alert_id: str) -> str:
    return f"gfw:integrated:{alert_id}"


def _parse_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    text = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def _severity_from_area(area_ha: float) -> str:
    if area_ha >= 50:
        return "critical"
    if area_ha >= 15:
        return "high"
    if area_ha >= 5:
        return "medium"
    return "low"


class GFWIntegratedAlertsProvider(IngestionProvider):
    """GFW integrated alerts — fixture-first; live when API key configured."""

    def __init__(
        self,
        records: list[dict[str, Any]] | None = None,
        *,
        settings: Settings | None = None,
        forest_context_service: ForestContextService | None = None,
    ) -> None:
        self._records = records if records is not None else list(_DEFAULT_FIXTURE_RECORDS)
        self._settings = settings or get_settings()
        self._forest_context = forest_context_service or ForestContextService()
        self._last_execution_mode: str | None = None
        self._last_fetch_at: datetime | None = None

    @property
    def last_execution_mode(self) -> str | None:
        return self._last_execution_mode

    @property
    def source_name(self) -> str:
        return GFW_SOURCE_NAME

    @property
    def provider_id(self) -> str:
        return GFW_PROVIDER_ID

    @property
    def supported_incident_categories(self) -> tuple[str, ...]:
        return (IncidentCategory.FOREST_DISTURBANCE.value,)

    def describe(self) -> dict[str, Any]:
        live_status = "token_configured" if self._settings.gfw_api_key else "fixture_only"
        return {
            "source": self.source_name,
            "provider_id": GFW_PROVIDER_ID,
            "dataset_id": GFW_DATASET_ID,
            "dataset_version": GFW_DATASET_VERSION,
            "temporal_resolution": "integrated_alert",
            "geographic_coverage": "Global (query-bounded by scope polygon)",
            "spatial_model": "alert_point_centroid",
            "update_frequency": "daily",
            "license": GFW_LICENSE,
            "live_access_status": live_status,
            "api_documentation": GFW_DOCUMENTATION,
            "api_endpoint": GFW_API_BASE,
            "last_fetch_at": self._last_fetch_at.isoformat() if self._last_fetch_at else None,
        }

    async def fetch(self) -> list[dict[str, Any]]:
        if not self._settings.gfw_api_key:
            self._last_execution_mode = "fixture"
            self._last_fetch_at = datetime.now(timezone.utc)
            return list(self._records)
        try:
            records = await self._fetch_live()
            self._last_execution_mode = "live"
            self._last_fetch_at = datetime.now(timezone.utc)
            return records
        except Exception as exc:
            logger.warning("GFW live API unavailable (%s) — using deterministic fixture", exc)
            self._last_execution_mode = "fixture"
            self._last_fetch_at = datetime.now(timezone.utc)
            return list(self._records)

    async def _fetch_live(self) -> list[dict[str, Any]]:
        scope = parse_geographic_scope(self._settings.geographic_scope)
        polygon = ROMANIA_QUERY_POLYGON if scope is GeographicScope.ROMANIA else EUROPE_QUERY_POLYGON
        geometry = {"type": "Polygon", "coordinates": polygon}
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: fetch_integrated_alerts(
                api_key=self._settings.gfw_api_key,
                geometry=geometry,
                lookback_days=self._settings.gfw_alert_lookback_days,
            ),
        )

    def normalize(self, raw: dict[str, Any]) -> ForestEventCreate:
        alert_id = str(raw.get("alert_id") or raw.get("id") or "").strip()
        if not alert_id:
            raise ValueError("GFW alert_id is required")

        lat = float(raw["latitude"])
        lng = float(raw["longitude"])
        country = str(raw.get("country") or "Unknown").strip()
        region = str(raw.get("region") or country).strip()
        area_ha = float(raw.get("area_ha") or 0.0)
        confidence = float(raw.get("confidence") or 0.75)
        observed_at = _parse_timestamp(raw.get("alert_date"))
        severity = _severity_from_area(area_ha)
        repeat_count = int(raw.get("repeat_count") or 1)

        forest_ctx = self._forest_context.resolve_context(lat, lng).to_metadata_block()
        driver_result = classify_disturbance_driver(
            alert_confidence=confidence,
            alert_intensity=str(raw.get("intensity") or ""),
            affected_area_ha=area_ha,
            forest_context=forest_ctx,
            alert_source=str(raw.get("alert_source") or ""),
            repeat_count=repeat_count,
        )
        assessment = assess_disturbance_context(
            driver=driver_result["driver"],
            driver_confidence=float(driver_result["driver_confidence"]),
            affected_area_ha=area_ha,
            forest_context=forest_ctx,
            protected_area_intersection=bool(raw.get("protected_area_intersection", False)),
            road_proximity_m=raw.get("road_proximity_m"),
            authorization_status=AuthorizationStatus.UNKNOWN.value,
            repeat_count=repeat_count,
        )

        source_event_id = disturbance_source_event_id(alert_id)
        ingestion = build_ingestion_metadata(
            source=GFW_SOURCE_NAME,
            source_event_id=source_event_id,
            is_romania=is_romania_event({"country": country, "latitude": lat, "longitude": lng}),
            confidence=confidence,
            severity=severity,
            provider_id=GFW_PROVIDER_ID,
            dataset_id=GFW_DATASET_ID,
            dataset_version=GFW_DATASET_VERSION,
            provenance_label="gfw_integrated_alert",
        )

        metadata: dict[str, Any] = {
            "incident_category": IncidentCategory.FOREST_DISTURBANCE.value,
            "spatial_key": disturbance_spatial_key(alert_id),
            "ingestion": ingestion,
            "forest_context": forest_ctx,
            "forest_disturbance": {
                "alert_id": alert_id,
                "alert_date": raw.get("alert_date"),
                "alert_confidence": confidence,
                "alert_intensity": raw.get("intensity"),
                "disturbance_signal": "integrated_alert",
                "probable_driver": driver_result["probable_driver"],
                "driver": driver_result["driver"],
                "driver_confidence": driver_result["driver_confidence"],
                "classification_reasons": driver_result["classification_reasons"],
                "authorization_status": assessment["authorization_status"],
                "investigation_priority": assessment["investigation_priority"],
                "assessment_label": assessment["assessment_label"],
                "assessment_reasons": assessment["assessment_reasons"],
                "repeat_count": repeat_count,
            },
            "provenance": {
                "provider_id": GFW_PROVIDER_ID,
                "source_id": GFW_PROVIDER_ID,
                "dataset_id": GFW_DATASET_ID,
                "dataset_version": GFW_DATASET_VERSION,
                "source_event_id": source_event_id,
                "observed_at": observed_at.isoformat(),
                "domain_evidence": {
                    "provider_class": "gfw_integrated_alerts",
                    "disturbance_signal": "integrated_alert",
                    "probable_driver": driver_result["probable_driver"],
                },
            },
        }

        return ForestEventCreate(
            title=f"Forest disturbance alert {alert_id} ({region})",
            latitude=lat,
            longitude=lng,
            region=region,
            country=country,
            event_type="unknown",
            severity=severity,
            affected_area_ha=area_ha,
            confidence=confidence,
            detected_at=observed_at,
            metadata=metadata,
        )
