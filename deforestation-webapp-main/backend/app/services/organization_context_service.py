"""Resolve trusted organization context for authenticated users."""
from __future__ import annotations

from typing import Any

from app.core.demo.constants import DEMO_ORGANIZATION_SLUG
from app.core.demo.identity import is_demo_organization, is_demo_user
from app.core.errors import ForbiddenError, NotFoundError
from app.core.organization.organization_context import OrganizationContext
from app.core.organization.organization_roles import OrganizationRole, can_read_monitoring
from app.models.organization import Organization
from app.models.user import UserPublic
from app.repositories.organization_membership_repository import OrganizationMembershipRepository
from app.repositories.organization_repository import OrganizationRepository
from app.services.organization_bootstrap_service import OrganizationBootstrapService


class OrganizationContextService:
    """Resolve organization membership — never trust client-supplied IDs blindly."""

    def __init__(
        self,
        org_repo: OrganizationRepository,
        membership_repo: OrganizationMembershipRepository,
        bootstrap_svc: OrganizationBootstrapService,
        trial_svc: Any | None = None,
    ) -> None:
        self._orgs = org_repo
        self._memberships = membership_repo
        self._bootstrap = bootstrap_svc
        self._trial = trial_svc

    async def resolve(
        self,
        user: UserPublic,
        *,
        requested_organization_id: str | None = None,
    ) -> OrganizationContext:
        if is_demo_user(user):
            return await self._resolve_demo(user, requested_organization_id)

        if requested_organization_id:
            return await self._resolve_explicit(user, requested_organization_id)

        personal = await self._bootstrap.ensure_personal_organization(str(user.id))
        await self._ensure_trial(personal)
        membership = await self._memberships.find_active(str(personal.id), str(user.id))
        if membership is None:
            raise ForbiddenError("No active organization membership")
        return OrganizationContext(
            user=user,
            organization_id=str(personal.id),
            organization_name=personal.name,
            organization_slug=personal.slug,
            membership_id=str(membership.id),
            role=membership.role,
            membership_status=membership.status,
        )

    async def _resolve_explicit(
        self,
        user: UserPublic,
        organization_id: str,
    ) -> OrganizationContext:
        org = await self._orgs.find_by_id(organization_id)
        if org is None:
            raise NotFoundError("Organization not found")
        if is_demo_organization(org):
            raise ForbiddenError("Organization access denied")
        membership = await self._memberships.find_membership(organization_id, str(user.id))
        if membership is None or membership.status != "active":
            raise ForbiddenError("Organization access denied")
        if org.status != "active":
            raise ForbiddenError("Organization is suspended")
        if not can_read_monitoring(membership.role, membership_status=membership.status):
            raise ForbiddenError("Organization access denied")
        await self._ensure_trial(org)
        return OrganizationContext(
            user=user,
            organization_id=str(org.id),
            organization_name=org.name,
            organization_slug=org.slug,
            membership_id=str(membership.id),
            role=membership.role,
            membership_status=membership.status,
        )

    async def _resolve_demo(
        self,
        user: UserPublic,
        requested_organization_id: str | None,
    ) -> OrganizationContext:
        org = await self._orgs.find_by_slug(DEMO_ORGANIZATION_SLUG)
        if org is None:
            raise ForbiddenError("Demonstration is not available")
        if requested_organization_id and requested_organization_id != str(org.id):
            raise ForbiddenError("Organization access denied")
        return OrganizationContext(
            user=user,
            organization_id=str(org.id),
            organization_name=org.name,
            organization_slug=org.slug,
            membership_id=f"demo-membership-{user.id}",
            role=OrganizationRole.ADMIN,
            membership_status="active",
            is_demo=True,
        )

    async def list_accessible_organizations(self, user: UserPublic) -> list[dict]:
        if is_demo_user(user):
            org = await self._orgs.find_by_slug(DEMO_ORGANIZATION_SLUG)
            if org is None:
                return []
            return [
                {
                    "id": str(org.id),
                    "name": org.name,
                    "slug": org.slug,
                    "role": OrganizationRole.ADMIN,
                    "status": org.status,
                }
            ]
        await self._bootstrap.ensure_personal_organization(str(user.id))
        memberships = await self._memberships.list_for_user(str(user.id), active_only=True)
        results: list[dict] = []
        for membership in memberships:
            org = await self._orgs.find_by_id(membership.organization_id)
            if org is None or org.status != "active":
                continue
            if is_demo_organization(org):
                continue
            results.append(
                {
                    "id": str(org.id),
                    "name": org.name,
                    "slug": org.slug,
                    "role": membership.role,
                    "status": org.status,
                    "commercial_lifecycle": org.commercial_lifecycle,
                    "trial_ends_at": org.trial_ends_at.isoformat()
                    if org.trial_ends_at
                    else None,
                }
            )
        results.sort(key=lambda item: item["name"].lower())
        return results

    async def _ensure_trial(self, org: Organization) -> None:
        if self._trial is None or is_demo_organization(org):
            return
        await self._trial.ensure_current(org)
