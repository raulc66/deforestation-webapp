"""Synchronize plan state onto existing organization entitlements.

This service is the only writer of plan-derived entitlement rows. It does not
evaluate entitlements — ``EntitlementService`` remains the single runtime
authority — and it never touches monitored areas, intelligence, or alert
history. A downgrade narrows what an organization may do next; it never removes
anything the organization already has.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.commercial.entitlement_types import (
    DEFAULT_ENTITLEMENT_SOURCE,
    EntitlementType,
)
from app.core.commercial.plan_catalog import (
    PlanCatalog,
    SubscriptionPlan,
    default_profile_entitlements,
    plan_entitlement_source,
)
from app.core.commercial.subscription_status import grants_plan_entitlements
from app.models.organization import OrganizationEntitlement
from app.repositories.organization_entitlement_repository import (
    OrganizationEntitlementRepository,
)

logger = logging.getLogger("forestwatch.billing")


@dataclass(frozen=True)
class ResolvedEntitlements:
    """Pure result of (plan, subscription status) — no persistence involved."""

    plan_key: str
    source: str
    profile: dict[str, Any]
    capability_active: bool


@dataclass(frozen=True)
class EntitlementSyncResult:
    organization_id: str
    plan_key: str
    source: str
    profile: dict[str, Any]
    capability_active: bool
    changed_types: tuple[str, ...]


def resolve_entitlements(
    catalog: PlanCatalog,
    *,
    plan: SubscriptionPlan | None,
    status: str | None,
) -> ResolvedEntitlements:
    """Deterministically map a plan and subscription status to an entitlement profile.

    A subscription that does not grant capability falls back to the unsubscribed
    baseline, so the same inputs always produce the same profile regardless of
    what the organization previously had.
    """
    if plan is not None and grants_plan_entitlements(status):
        return ResolvedEntitlements(
            plan_key=plan.key,
            source=plan_entitlement_source(plan.key),
            profile=dict(plan.entitlement_profile),
            capability_active=True,
        )
    return ResolvedEntitlements(
        plan_key=catalog.default_plan.key,
        source=DEFAULT_ENTITLEMENT_SOURCE,
        profile=default_profile_entitlements(),
        capability_active=False,
    )


class EntitlementSyncService:
    def __init__(
        self,
        entitlement_repo: OrganizationEntitlementRepository,
        catalog: PlanCatalog,
    ) -> None:
        self._entitlements = entitlement_repo
        self._catalog = catalog

    async def sync(
        self,
        organization_id: str,
        *,
        plan: SubscriptionPlan | None,
        status: str | None,
    ) -> EntitlementSyncResult:
        resolved = resolve_entitlements(self._catalog, plan=plan, status=status)
        changed = await self._write_profile(
            organization_id,
            profile=resolved.profile,
            source=resolved.source,
        )
        if changed:
            logger.info(
                "Entitlements synchronized for organization %s to plan %s (%s)",
                organization_id,
                resolved.plan_key,
                status or "no subscription",
            )
        return EntitlementSyncResult(
            organization_id=organization_id,
            plan_key=resolved.plan_key,
            source=resolved.source,
            profile=resolved.profile,
            capability_active=resolved.capability_active,
            changed_types=tuple(changed),
        )

    async def sync_from_plan_key(
        self,
        organization_id: str,
        *,
        plan_key: str | None,
        status: str | None,
    ) -> EntitlementSyncResult:
        return await self.sync(
            organization_id,
            plan=self._catalog.get(plan_key),
            status=status,
        )

    async def _write_profile(
        self,
        organization_id: str,
        *,
        profile: dict[str, Any],
        source: str,
    ) -> list[str]:
        now = datetime.now(timezone.utc)
        changed: list[str] = []
        for entitlement_type in (member.value for member in EntitlementType):
            if entitlement_type not in profile:
                continue
            value = profile[entitlement_type]
            existing = await self._entitlements.find_by_type(
                organization_id,
                entitlement_type,
            )
            if existing is None:
                await self._entitlements.insert(
                    OrganizationEntitlement(
                        organization_id=organization_id,
                        entitlement_type=entitlement_type,
                        value=value,
                        source=source,
                        effective_from=now,
                        status="active",
                        created_at=now,
                        updated_at=now,
                    )
                )
                changed.append(entitlement_type)
                continue
            if existing.value == value and existing.source == source:
                continue
            await self._entitlements.update(
                str(existing.id),
                {
                    "value": value,
                    "source": source,
                    "effective_from": now,
                    "effective_until": None,
                    "status": "active",
                    "updated_at": now,
                },
            )
            changed.append(entitlement_type)
        return changed
