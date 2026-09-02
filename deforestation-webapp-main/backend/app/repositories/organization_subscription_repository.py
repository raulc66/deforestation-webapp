"""MongoDB persistence for organization subscriptions of record."""
from __future__ import annotations

from app.models.billing import OrganizationSubscription
from app.repositories.base import BaseRepository


class OrganizationSubscriptionRepository(BaseRepository[OrganizationSubscription]):
    collection_name = "organization_subscriptions"
    model = OrganizationSubscription

    async def find_by_organization(
        self,
        organization_id: str,
    ) -> OrganizationSubscription | None:
        return await self.find_one({"organization_id": organization_id})

    async def find_by_stripe_subscription(
        self,
        stripe_subscription_id: str,
    ) -> OrganizationSubscription | None:
        return await self.find_one({"stripe_subscription_id": stripe_subscription_id})
