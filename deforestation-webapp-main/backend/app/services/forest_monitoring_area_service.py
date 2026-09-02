"""CRUD service for organization-owned forest monitoring areas."""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.errors import ForbiddenError, NotFoundError
from app.core.organization.organization_roles import can_manage_monitoring_areas
from app.models.forest_monitoring_area import (
    ForestMonitoringArea,
    ForestMonitoringAreaCreate,
    ForestMonitoringAreaPublic,
    ForestMonitoringAreaUpdate,
)
from app.models.geo import validate_geojson_geometry
from app.repositories.forest_monitoring_area_repository import ForestMonitoringAreaRepository
from app.services.entitlement_service import EntitlementService


def _to_public(area: ForestMonitoringArea) -> ForestMonitoringAreaPublic:
    return ForestMonitoringAreaPublic(
        id=str(area.id),
        organization_id=area.organization_id,
        tenant_id=area.tenant_id,
        name=area.name,
        geometry=area.geometry,
        geometry_type=area.geometry_type,
        country=area.country,
        enabled=area.enabled,
        created_at=area.created_at,
        updated_at=area.updated_at,
    )


class ForestMonitoringAreaService:
    def __init__(
        self,
        repo: ForestMonitoringAreaRepository,
        entitlement_svc: EntitlementService | None = None,
    ) -> None:
        self._repo = repo
        self._entitlements = entitlement_svc

    async def list_areas(self, organization_id: str) -> dict:
        areas = await self._repo.list_for_organization(organization_id)
        return {"items": [_to_public(area) for area in areas], "total": len(areas)}

    async def get_area(self, organization_id: str, area_id: str) -> ForestMonitoringAreaPublic:
        area = await self._repo.find_for_organization(organization_id, area_id)
        if area is None:
            raise NotFoundError(f"Monitoring area {area_id} not found")
        return _to_public(area)

    async def create_area(
        self,
        organization_id: str,
        payload: ForestMonitoringAreaCreate,
        *,
        actor_role: str,
    ) -> ForestMonitoringAreaPublic:
        if not can_manage_monitoring_areas(actor_role):
            raise ForbiddenError("Insufficient permissions to manage monitoring areas")
        if self._entitlements is not None:
            if not await self._entitlements.can_monitor(organization_id):
                raise ForbiddenError("Monitoring is not enabled for this organization")
            if not await self._entitlements.can_add_monitoring_area(organization_id):
                raise ForbiddenError("Monitored area limit reached for this organization")
        geometry = validate_geojson_geometry(payload.geometry)
        now = datetime.now(timezone.utc)
        area = ForestMonitoringArea(
            organization_id=organization_id,
            tenant_id=organization_id,
            name=payload.name.strip(),
            geometry=geometry,
            geometry_type=str(geometry["type"]),
            country=payload.country.strip() or "Romania",
            enabled=payload.enabled,
            created_at=now,
            updated_at=now,
        )
        saved = await self._repo.insert(area)
        return _to_public(saved)

    async def update_area(
        self,
        organization_id: str,
        area_id: str,
        payload: ForestMonitoringAreaUpdate,
        *,
        actor_role: str,
    ) -> ForestMonitoringAreaPublic:
        if not can_manage_monitoring_areas(actor_role):
            raise ForbiddenError("Insufficient permissions to manage monitoring areas")
        area = await self._repo.find_for_organization(organization_id, area_id)
        if area is None:
            raise NotFoundError(f"Monitoring area {area_id} not found")
        updates: dict = {"updated_at": datetime.now(timezone.utc)}
        if payload.name is not None:
            updates["name"] = payload.name.strip()
        if payload.country is not None:
            updates["country"] = payload.country.strip()
        if payload.enabled is not None:
            if payload.enabled and not area.enabled and self._entitlements is not None:
                if not await self._entitlements.can_add_monitoring_area(organization_id):
                    raise ForbiddenError(
                        "Monitored area limit reached for this organization"
                    )
            updates["enabled"] = payload.enabled
        if payload.geometry is not None:
            geometry = validate_geojson_geometry(payload.geometry)
            updates["geometry"] = geometry
            updates["geometry_type"] = geometry["type"]
        await self._repo.update(area_id, updates)
        refreshed = await self._repo.find_for_organization(organization_id, area_id)
        assert refreshed is not None
        return _to_public(refreshed)

    async def delete_area(
        self,
        organization_id: str,
        area_id: str,
        *,
        actor_role: str,
    ) -> None:
        if not can_manage_monitoring_areas(actor_role):
            raise ForbiddenError("Insufficient permissions to manage monitoring areas")
        deleted = await self._repo.delete_for_organization(organization_id, area_id)
        if not deleted:
            raise NotFoundError(f"Monitoring area {area_id} not found")

    async def list_enabled_public(self, organization_id: str) -> list[dict]:
        areas = await self._repo.list_for_organization(organization_id, enabled_only=True)
        return [
            {
                "id": str(area.id),
                "organization_id": area.organization_id,
                "tenant_id": area.tenant_id,
                "name": area.name,
                "geometry": area.geometry,
                "geometry_type": area.geometry_type,
                "country": area.country,
                "enabled": area.enabled,
            }
            for area in areas
        ]
