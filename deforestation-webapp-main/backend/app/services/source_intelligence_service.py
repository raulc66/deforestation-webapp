"""Source intelligence aggregation for operational visibility."""
from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.core.ingestion.provider_health import ProviderHealthStatus
from app.core.ingestion.source_descriptor import (
    SourceDescriptor,
    SourceType,
    source_descriptor_from_describe,
)
from app.core.ingestion.source_reliability import (
    SourceReliabilityInput,
    compute_baseline_reliability_score,
)
from app.repositories.provider_health_repository import ProviderHealthRepository


class SourceIntelligenceService:
    """Read-only aggregation of source descriptors, health, and reliability."""

    def __init__(
        self,
        health_repo: ProviderHealthRepository,
        *,
        settings: Settings | None = None,
        ingestion_providers: list[Any] | None = None,
        contextual_providers: list[Any] | None = None,
    ) -> None:
        self._health = health_repo
        self._settings = settings or get_settings()
        self._ingestion_providers = ingestion_providers or []
        self._contextual_providers = contextual_providers or []

    async def get_source_status(self) -> dict[str, Any]:
        descriptors = self._build_descriptors()
        health_rows = {row["provider_id"]: row for row in await self._health.list_all()}
        sources: list[dict[str, Any]] = []
        for descriptor in descriptors:
            health = health_rows.get(descriptor.provider_id)
            entry = descriptor.model_dump(mode="json")
            if health:
                entry["health"] = _public_health(health)
                entry["reliability_status"] = health.get(
                    "current_status", ProviderHealthStatus.UNKNOWN.value
                )
            sources.append(entry)
        return {
            "sources": sources,
            "geographic_scope": self._settings.geographic_scope,
        }

    async def get_health_summary(self) -> list[dict[str, Any]]:
        status = await self.get_source_status()
        return [
            {
                "provider_id": src["provider_id"],
                "display_name": src["display_name"],
                "current_status": src.get("reliability_status", ProviderHealthStatus.UNKNOWN.value),
                "incident_categories": list(src.get("incident_categories") or []),
                "last_success_at": (src.get("health") or {}).get("last_success_at"),
                "last_failure_at": (src.get("health") or {}).get("last_failure_at"),
                "enabled": src.get("enabled", True),
            }
            for src in status["sources"]
        ]

    async def get_degraded_sources(self) -> list[dict[str, Any]]:
        """Deterministic degraded/failed provider indicator — no fabricated evidence."""
        rows = await self._health.list_all()
        return [
            {
                "provider_id": row["provider_id"],
                "display_name": row.get("display_name", row["provider_id"]),
                "current_status": row.get("current_status", ProviderHealthStatus.UNKNOWN.value),
                "last_success_at": row.get("last_success_at"),
                "last_failure_at": row.get("last_failure_at"),
            }
            for row in rows
            if row.get("current_status")
            in {
                ProviderHealthStatus.DEGRADED.value,
                ProviderHealthStatus.FAILED.value,
            }
        ]

    def _build_descriptors(self) -> list[SourceDescriptor]:
        descriptors: list[SourceDescriptor] = []
        for provider in self._ingestion_providers:
            describe = provider.describe()
            enabled = _provider_enabled(provider, self._settings)
            source_type = (
                SourceType.CONTEXTUAL.value
                if getattr(provider, "provider_id", "") == "effis.wildfire_context"
                else SourceType.OBSERVATION.value
            )
            descriptors.append(
                source_descriptor_from_describe(
                    describe,
                    source_type=source_type,
                    incident_categories=tuple(provider.supported_incident_categories),
                    enabled=enabled,
                )
            )
        for provider in self._contextual_providers:
            describe = provider.describe()
            descriptors.append(
                source_descriptor_from_describe(
                    describe,
                    source_type=(
                        SourceType.METEOROLOGICAL.value
                        if "meteo" in getattr(provider, "provider_id", "").lower()
                        else SourceType.CONTEXTUAL.value
                    ),
                    enabled=True,
                )
            )
        descriptors.append(_open_meteo_descriptor())
        return descriptors


def _open_meteo_descriptor() -> SourceDescriptor:
    return SourceDescriptor(
        source_id="open_meteo.weather",
        provider_id="open_meteo.weather",
        display_name="Open-Meteo",
        source_type=SourceType.METEOROLOGICAL.value,
        geographic_coverage="Romania regional centroids (weather cache)",
        temporal_coverage="hourly_forecast",
        update_cadence="scheduler_refresh",
        access_type="live",
        license_provenance="Open-Meteo free API — https://open-meteo.com",
        dataset_id="open_meteo.forecast",
        enabled=True,
    )


def reliability_from_source_row(row: dict, *, in_scope_field: str = "romania_events") -> float:
    """Compute reliability score from an analytics ``by_source`` shaped row."""
    severity_distribution = {
        "low": int(row.get("sev_low", 0)),
        "medium": int(row.get("sev_medium", 0)),
        "high": int(row.get("sev_high", 0)),
        "critical": int(row.get("sev_critical", 0)),
    }
    return compute_baseline_reliability_score(
        SourceReliabilityInput(
            average_confidence=float(row.get("average_confidence") or 0.0),
            total_events=int(row.get("total_events") or 0),
            in_scope_events=int(row.get(in_scope_field) or 0),
            severity_distribution=severity_distribution,
        )
    )


def _provider_enabled(provider: Any, settings: Settings) -> bool:
    provider_id = getattr(provider, "provider_id", "")
    if provider_id == "eea.air_quality":
        return settings.enable_eea_air_quality
    if provider_id == "cems.rapid_mapping":
        return settings.enable_cems_rapid_mapping
    if provider_id == "effis.wildfire_context":
        return settings.enable_effis_wildfire_context
    if provider_id == "gfw.integrated_alerts":
        return settings.enable_forest_disturbance
    return True


def _public_health(health: dict[str, Any]) -> dict[str, Any]:
    """Strip internal fields; never expose credentials."""
    allowed = {
        "provider_id",
        "display_name",
        "current_status",
        "last_attempt_at",
        "last_success_at",
        "last_failure_at",
        "consecutive_failures",
        "observations_received",
        "observations_rejected",
        "observations_persisted",
        "last_fetch_duration_seconds",
        "last_error",
        "updated_at",
    }
    return {k: health[k] for k in allowed if k in health}
