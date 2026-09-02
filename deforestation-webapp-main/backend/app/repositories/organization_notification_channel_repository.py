"""MongoDB persistence for organization notification channels."""
from __future__ import annotations

from app.models.customer_alert import OrganizationNotificationChannel
from app.repositories.base import BaseRepository


class OrganizationNotificationChannelRepository(BaseRepository[OrganizationNotificationChannel]):
    collection_name = "organization_notification_channels"
    model = OrganizationNotificationChannel

    async def list_for_organization(
        self,
        organization_id: str,
        *,
        enabled_only: bool = False,
    ) -> list[OrganizationNotificationChannel]:
        query: dict = {"organization_id": organization_id}
        if enabled_only:
            query["enabled"] = True
        return await self.find_many(query, sort=[("created_at", 1)])

    async def find_for_organization(
        self,
        organization_id: str,
        channel_id: str,
    ) -> OrganizationNotificationChannel | None:
        channel = await self.find_by_id(channel_id)
        if channel is None or channel.organization_id != organization_id:
            return None
        return channel

    async def list_by_ids(
        self,
        organization_id: str,
        channel_ids: list[str],
    ) -> list[OrganizationNotificationChannel]:
        if not channel_ids:
            return []
        from bson import ObjectId

        object_ids = [ObjectId(cid) for cid in channel_ids if ObjectId.is_valid(cid)]
        if not object_ids:
            return []
        return await self.find_many(
            {"organization_id": organization_id, "_id": {"$in": object_ids}},
            sort=[("created_at", 1)],
        )
