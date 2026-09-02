"""MongoDB persistence for organization entitlements."""
from __future__ import annotations

from app.models.organization import OrganizationEntitlement
from app.repositories.base import BaseRepository


class OrganizationEntitlementRepository(BaseRepository[OrganizationEntitlement]):
    collection_name = "organization_entitlements"
    model = OrganizationEntitlement

    async def list_for_organization(
        self,
        organization_id: str,
        *,
        active_only: bool = True,
    ) -> list[OrganizationEntitlement]:
        query: dict = {"organization_id": organization_id}
        if active_only:
            query["status"] = "active"
        return await self.find_many(query, limit=50, sort=[("entitlement_type", 1)])

    async def find_by_type(
        self,
        organization_id: str,
        entitlement_type: str,
    ) -> OrganizationEntitlement | None:
        return await self.find_one(
            {
                "organization_id": organization_id,
                "entitlement_type": entitlement_type,
                "status": "active",
            }
        )
