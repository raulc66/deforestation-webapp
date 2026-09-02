"""MongoDB persistence for organization memberships."""
from __future__ import annotations

from typing import Any

from app.models.organization import OrganizationMembership
from app.repositories.base import BaseRepository


class OrganizationMembershipRepository(BaseRepository[OrganizationMembership]):
    collection_name = "organization_memberships"
    model = OrganizationMembership

    async def find_active(
        self,
        organization_id: str,
        user_id: str,
    ) -> OrganizationMembership | None:
        doc = await self.find_one(
            {
                "organization_id": organization_id,
                "user_id": user_id,
                "status": "active",
            }
        )
        return doc

    async def find_membership(
        self,
        organization_id: str,
        user_id: str,
    ) -> OrganizationMembership | None:
        return await self.find_one(
            {"organization_id": organization_id, "user_id": user_id}
        )

    async def list_for_organization(
        self,
        organization_id: str,
        *,
        limit: int = 100,
    ) -> list[OrganizationMembership]:
        return await self.find_many(
            {"organization_id": organization_id},
            limit=limit,
            sort=[("role", 1), ("created_at", 1)],
        )

    async def list_for_user(
        self,
        user_id: str,
        *,
        active_only: bool = True,
        limit: int = 100,
    ) -> list[OrganizationMembership]:
        query: dict[str, Any] = {"user_id": user_id}
        if active_only:
            query["status"] = "active"
        return await self.find_many(query, limit=limit, sort=[("created_at", 1)])

    async def count_owners(self, organization_id: str) -> int:
        return await self.count(
            {
                "organization_id": organization_id,
                "role": "owner",
                "status": "active",
            }
        )
