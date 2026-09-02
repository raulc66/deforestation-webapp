"""MongoDB persistence for tenant forest monitoring areas."""
from __future__ import annotations

from typing import Any

from app.models.forest_monitoring_area import ForestMonitoringArea
from app.repositories.base import BaseRepository


class ForestMonitoringAreaRepository(BaseRepository[ForestMonitoringArea]):
    collection_name = "forest_monitoring_areas"
    model = ForestMonitoringArea

    async def list_for_organization(
        self,
        organization_id: str,
        *,
        enabled_only: bool = False,
        limit: int = 100,
    ) -> list[ForestMonitoringArea]:
        query: dict[str, Any] = {"organization_id": organization_id}
        if enabled_only:
            query["enabled"] = True
        return await self.find_many(query, limit=limit, sort=[("name", 1)])

    async def find_for_organization(
        self,
        organization_id: str,
        area_id: str,
    ) -> ForestMonitoringArea | None:
        doc = await self.find_by_id(area_id)
        if doc is None or doc.organization_id != organization_id:
            return None
        return doc

    async def delete_for_organization(self, organization_id: str, area_id: str) -> bool:
        doc = await self.find_for_organization(organization_id, area_id)
        if doc is None:
            return False
        return await self.delete(area_id)

    async def list_for_tenant(
        self,
        tenant_id: str,
        *,
        enabled_only: bool = False,
        limit: int = 100,
    ) -> list[ForestMonitoringArea]:
        """Legacy lookup — used only for migration from tenant_id=user.id."""
        query: dict[str, Any] = {"tenant_id": tenant_id}
        if enabled_only:
            query["enabled"] = True
        return await self.find_many(query, limit=limit, sort=[("name", 1)])

    async def find_for_tenant(self, tenant_id: str, area_id: str) -> ForestMonitoringArea | None:
        doc = await self.find_by_id(area_id)
        if doc is None or doc.tenant_id != tenant_id:
            return None
        return doc

    async def delete_for_tenant(self, tenant_id: str, area_id: str) -> bool:
        doc = await self.find_for_tenant(tenant_id, area_id)
        if doc is None:
            return False
        return await self.delete(area_id)

    async def find_containing_point(
        self,
        organization_id: str,
        longitude: float,
        latitude: float,
        *,
        enabled_only: bool = True,
    ) -> list[ForestMonitoringArea]:
        query: dict[str, Any] = {
            "organization_id": organization_id,
            "geometry": {
                "$geoIntersects": {
                    "$geometry": {
                        "type": "Point",
                        "coordinates": [longitude, latitude],
                    }
                }
            },
        }
        if enabled_only:
            query["enabled"] = True
        return await self.find_many(query, limit=100, sort=[("_id", 1)])
