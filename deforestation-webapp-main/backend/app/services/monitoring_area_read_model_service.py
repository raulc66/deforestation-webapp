"""Enriched monitoring area read model — area hectares + intelligence counts."""
from __future__ import annotations

from typing import Any

from app.models.forest_monitoring_area import ForestMonitoringAreaPublic
from app.modules.analytics.intelligence_events_repository import IntelligenceEventsRepository
from app.services.aoi_geometry import geometry_area_hectares
from app.services.aoi_intelligence_summary_service import AoiIntelligenceSummaryService
from app.services.forest_monitoring_area_service import ForestMonitoringAreaService


class MonitoringAreaReadModelService:
    """Organization-scoped monitoring area reads with bounded enrichment."""

    def __init__(
        self,
        area_svc: ForestMonitoringAreaService,
        intel_repo: IntelligenceEventsRepository,
        summary_svc: AoiIntelligenceSummaryService | None = None,
    ) -> None:
        self._areas = area_svc
        self._intel = intel_repo
        self._summary = summary_svc or AoiIntelligenceSummaryService()

    async def list_areas(self, organization_id: str) -> dict:
        payload = await self._areas.list_areas(organization_id)
        items = payload.get("items") or []
        if not items:
            return payload

        active_events = await self._intel.find_active()
        area_dicts = [
            {
                "id": item.id,
                "name": item.name,
                "geometry": item.geometry,
                "enabled": item.enabled,
            }
            for item in items
        ]
        summaries = self._summary.summarize_areas(
            organization_id=organization_id,
            areas=area_dicts,
            active_events=active_events,
        )
        enriched: list[ForestMonitoringAreaPublic] = [
            item.model_copy(
                update={
                    "area_hectares": geometry_area_hectares(item.geometry),
                    "intelligence_summary": summaries.get(item.id),
                }
            )
            for item in items
        ]
        return {"items": enriched, "total": len(enriched)}

    async def get_area(self, organization_id: str, area_id: str) -> ForestMonitoringAreaPublic:
        base = await self._areas.get_area(organization_id, area_id)
        active_events = await self._intel.find_active()
        area_dict = {
            "id": base.id,
            "name": base.name,
            "geometry": base.geometry,
            "enabled": base.enabled,
        }
        summary = self._summary.summarize_areas(
            organization_id=organization_id,
            areas=[area_dict],
            active_events=active_events,
        ).get(base.id)
        return base.model_copy(
            update={
                "area_hectares": geometry_area_hectares(base.geometry),
                "intelligence_summary": summary,
            }
        )
