"""MongoDB persistence for organizations."""
from __future__ import annotations

from app.models.organization import Organization
from app.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    collection_name = "organizations"
    model = Organization

    async def find_by_slug(self, slug: str) -> Organization | None:
        return await self.find_one({"slug": slug})

    async def list_for_user_ids(self, organization_ids: list[str]) -> list[Organization]:
        if not organization_ids:
            return []
        return await self.find_many({"_id": {"$in": organization_ids}})

    async def list_all(self, *, limit: int = 500) -> list[Organization]:
        return await self.find_many({}, limit=limit)
