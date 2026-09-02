"""Customer monitoring status read model — organization AOI + disturbance relevance."""
from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.core.ecosystem.forest_disturbance_constants import InvestigationPriority
from app.core.geography.geographic_scope import GeographicScopePolicy, parse_geographic_scope
from app.core.ingestion.provider_health import ProviderHealthStatus
from app.core.organization.organization_context import OrganizationContext
from app.modules.analytics.evidence_summary import resolve_correlation_state
from app.modules.analytics.intelligence_events_repository import IntelligenceEventsRepository
from app.repositories.correlation_repository import CorrelationRepository
from app.repositories.intelligence_cycle_repository import IntelligenceCycleRepository
from app.repositories.provider_health_repository import ProviderHealthRepository
from app.services.aoi_enrichment_service import AoiEnrichmentService
from app.services.entitlement_service import EntitlementService
from app.services.forest_monitoring_area_service import ForestMonitoringAreaService
from app.services.source_intelligence_service import SourceIntelligenceService


class CustomerMonitoringStatusService:
    """Read-only organization monitoring summary — no ingestion or reconciliation."""

    def __init__(
        self,
        area_service: ForestMonitoringAreaService,
        intel_repo: IntelligenceEventsRepository,
        source_intel: SourceIntelligenceService,
        cycle_repo: IntelligenceCycleRepository,
        correlation_repo: CorrelationRepository,
        health_repo: ProviderHealthRepository,
        entitlement_svc: EntitlementService,
        *,
        settings: Settings | None = None,
        aoi_enrichment: AoiEnrichmentService | None = None,
    ) -> None:
        self._areas = area_service
        self._intel_repo = intel_repo
        self._source_intel = source_intel
        self._cycle_repo = cycle_repo
        self._correlation_repo = correlation_repo
        self._health_repo = health_repo
        self._entitlements = entitlement_svc
        self._settings = settings or get_settings()
        self._aoi = aoi_enrichment or AoiEnrichmentService()

    async def get_monitoring_status(self, org_ctx: OrganizationContext) -> dict[str, Any]:
        organization_id = org_ctx.organization_id
        scope_policy = GeographicScopePolicy(parse_geographic_scope(self._settings.geographic_scope))
        areas = await self._areas.list_enabled_public(organization_id)
        profile = await self._entitlements.get_profile(organization_id)
        area_count = len(areas)
        active_events = await self._intel_repo.find_active()
        cycle_state = await self._cycle_repo.get_current() or {}
        correlations = await self._correlation_repo.list_all()
        health_rows = await self._health_repo.list_all()
        source_status = await self._source_intel.get_source_status()

        inside_count = 0
        high_critical = 0
        if profile.forest_disturbance_enabled:
            for event in active_events:
                if event.get("incident_category") != "forest_disturbance":
                    continue
                lat = event.get("latitude")
                lng = event.get("longitude")
                if lat is None or lng is None:
                    meta = event.get("metadata") or {}
                    lat = meta.get("latitude", lat)
                    lng = meta.get("longitude", lng)
                disturbance = (event.get("metadata") or {}).get("forest_disturbance") or {}
                enriched = self._aoi.enrich_disturbance_item(
                    latitude=float(lat) if lat is not None else None,
                    longitude=float(lng) if lng is not None else None,
                    organization_id=organization_id,
                    areas=areas,
                    disturbance_block=disturbance,
                )
                if not enriched.get("inside_monitored_area"):
                    continue
                inside_count += 1
                priority = str(enriched.get("investigation_priority") or "")
                if priority in {
                    InvestigationPriority.HIGH.value,
                    InvestigationPriority.CRITICAL.value,
                }:
                    high_critical += 1

        degraded = [
            row for row in health_rows
            if row.get("current_status") in {
                ProviderHealthStatus.DEGRADED.value,
                ProviderHealthStatus.FAILED.value,
            }
        ]

        correlation_state = resolve_correlation_state(
            correlation_enabled=self._settings.enable_cross_source_correlation,
            current_cycle_id=cycle_state.get("intelligence_cycle_id"),
            correlation_cycle_id=cycle_state.get("correlation_cycle_id"),
            has_correlations=bool(correlations),
        )

        return {
            "geographic_scope": self._settings.geographic_scope,
            "organization": {
                "id": org_ctx.organization_id,
                "name": org_ctx.organization_name,
                "role": org_ctx.role,
            },
            "entitlements": profile.as_read_model(monitored_area_count=area_count),
            "monitored_areas": {
                "enabled_count": area_count,
                "items": [
                    {
                        "id": area["id"],
                        "name": area["name"],
                        "country": area["country"],
                        "geometry_type": area["geometry_type"],
                    }
                    for area in areas[:20]
                ],
            },
            "intelligence_cycle": {
                "intelligence_cycle_id": cycle_state.get("intelligence_cycle_id"),
                "correlation_cycle_id": cycle_state.get("correlation_cycle_id"),
            },
            "disturbance_summary": {
                "inside_monitored_area_count": inside_count,
                "high_critical_investigation_count": high_critical,
                "authorization_status_default": "unknown",
            },
            "sources": {
                "available_count": len(source_status.get("sources", [])),
                "degraded_count": len(degraded),
                "degraded_providers": [
                    row.get("provider_id") for row in degraded[:5]
                ],
            },
            "correlation_state": correlation_state,
            "scope_policy": {
                "configured_scope": self._settings.geographic_scope,
                "centroids_use_romania_admin_fallback": scope_policy.centroids_use_romania_admin_fallback(),
            },
        }
