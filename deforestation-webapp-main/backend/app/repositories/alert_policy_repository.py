"""MongoDB persistence for organization alert policies."""
from __future__ import annotations

from app.models.customer_alert import AlertPolicy
from app.repositories.base import BaseRepository


class AlertPolicyRepository(BaseRepository[AlertPolicy]):
    collection_name = "alert_policies"
    model = AlertPolicy

    async def list_for_organization(
        self,
        organization_id: str,
        *,
        enabled_only: bool = False,
    ) -> list[AlertPolicy]:
        query: dict = {"organization_id": organization_id}
        if enabled_only:
            query["enabled"] = True
        return await self.find_many(query, sort=[("created_at", 1)])

    async def find_for_organization(
        self,
        organization_id: str,
        policy_id: str,
    ) -> AlertPolicy | None:
        policy = await self.find_by_id(policy_id)
        if policy is None or policy.organization_id != organization_id:
            return None
        return policy
