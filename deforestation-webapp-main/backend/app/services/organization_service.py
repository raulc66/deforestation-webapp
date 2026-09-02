"""Organization and membership management."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.organization.organization_roles import (
    OrganizationRole,
    can_manage_members,
    can_update_organization,
)
from app.models.organization import (
    Organization,
    OrganizationCreate,
    OrganizationMembership,
    OrganizationMembershipCreate,
    OrganizationMembershipPublic,
    OrganizationMembershipUpdate,
    OrganizationPublic,
    OrganizationUpdate,
)
from app.repositories.organization_membership_repository import OrganizationMembershipRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.services.entitlement_service import EntitlementService


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "organization"


class OrganizationService:
    def __init__(
        self,
        org_repo: OrganizationRepository,
        membership_repo: OrganizationMembershipRepository,
        user_repo: UserRepository,
        entitlement_svc: EntitlementService,
    ) -> None:
        self._orgs = org_repo
        self._memberships = membership_repo
        self._users = user_repo
        self._entitlements = entitlement_svc

    def _to_public(self, org: Organization) -> OrganizationPublic:
        return OrganizationPublic(
            id=str(org.id),
            name=org.name,
            slug=org.slug,
            status=org.status,
            kind=org.kind,
            commercial_lifecycle=org.commercial_lifecycle,
            trial_ends_at=org.trial_ends_at,
            created_at=org.created_at,
            updated_at=org.updated_at,
        )

    async def _unique_slug(self, base: str) -> str:
        slug = _slugify(base)
        candidate = slug
        suffix = 1
        while await self._orgs.find_by_slug(candidate) is not None:
            candidate = f"{slug}-{suffix}"
            suffix += 1
        return candidate

    async def create_organization(
        self,
        user_id: str,
        payload: OrganizationCreate,
    ) -> OrganizationPublic:
        now = datetime.now(timezone.utc)
        slug = await self._unique_slug(payload.name)
        org = Organization(
            name=payload.name.strip(),
            slug=slug,
            status="active",
            created_at=now,
            updated_at=now,
        )
        saved = await self._orgs.insert(org)
        membership = OrganizationMembership(
            organization_id=str(saved.id),
            user_id=user_id,
            role=OrganizationRole.OWNER,
            status="active",
            created_at=now,
            updated_at=now,
        )
        await self._memberships.insert(membership)
        await self._entitlements.ensure_default_entitlements(str(saved.id))
        return self._to_public(saved)

    async def get_organization(
        self,
        organization_id: str,
        *,
        user_id: str,
    ) -> OrganizationPublic:
        membership = await self._memberships.find_membership(organization_id, user_id)
        if membership is None or membership.status != "active":
            raise ForbiddenError("Organization access denied")
        org = await self._orgs.find_by_id(organization_id)
        if org is None:
            raise NotFoundError("Organization not found")
        return self._to_public(org)

    async def update_organization(
        self,
        organization_id: str,
        user_id: str,
        payload: OrganizationUpdate,
    ) -> OrganizationPublic:
        membership = await self._memberships.find_membership(organization_id, user_id)
        if membership is None or membership.status != "active":
            raise ForbiddenError("Organization access denied")
        if not can_update_organization(membership.role):
            raise ForbiddenError("Only organization owners can update organization settings")
        org = await self._orgs.find_by_id(organization_id)
        if org is None:
            raise NotFoundError("Organization not found")
        updates: dict = {"updated_at": datetime.now(timezone.utc)}
        if payload.name is not None:
            updates["name"] = payload.name.strip()
        if payload.status is not None:
            updates["status"] = payload.status
        await self._orgs.update(organization_id, updates)
        refreshed = await self._orgs.find_by_id(organization_id)
        assert refreshed is not None
        return self._to_public(refreshed)

    async def list_members(
        self,
        organization_id: str,
        *,
        user_id: str,
    ) -> dict:
        membership = await self._memberships.find_membership(organization_id, user_id)
        if membership is None or membership.status != "active":
            raise ForbiddenError("Organization access denied")
        rows = await self._memberships.list_for_organization(organization_id)
        items: list[OrganizationMembershipPublic] = []
        for row in rows:
            user = await self._users.find_by_id(row.user_id)
            items.append(
                OrganizationMembershipPublic(
                    id=str(row.id),
                    organization_id=row.organization_id,
                    user_id=row.user_id,
                    user_email=user.email if user else None,
                    user_name=user.name if user else None,
                    role=row.role,
                    status=row.status,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
            )
        return {"items": items, "total": len(items)}

    async def add_member(
        self,
        organization_id: str,
        actor_user_id: str,
        payload: OrganizationMembershipCreate,
    ) -> OrganizationMembershipPublic:
        actor = await self._memberships.find_membership(organization_id, actor_user_id)
        if actor is None or actor.status != "active":
            raise ForbiddenError("Organization access denied")
        if not can_manage_members(actor.role):
            raise ForbiddenError("Insufficient permissions to manage members")
        target = await self._users.find_by_email(payload.email.strip())
        if target is None:
            raise NotFoundError("User not found")
        existing = await self._memberships.find_membership(organization_id, str(target.id))
        if existing is not None:
            raise ConflictError("User is already a member of this organization")
        now = datetime.now(timezone.utc)
        membership = OrganizationMembership(
            organization_id=organization_id,
            user_id=str(target.id),
            role=payload.role,
            status="active",
            created_at=now,
            updated_at=now,
        )
        saved = await self._memberships.insert(membership)
        return OrganizationMembershipPublic(
            id=str(saved.id),
            organization_id=saved.organization_id,
            user_id=saved.user_id,
            user_email=target.email,
            user_name=target.name,
            role=saved.role,
            status=saved.status,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )

    async def update_member(
        self,
        organization_id: str,
        target_user_id: str,
        actor_user_id: str,
        payload: OrganizationMembershipUpdate,
    ) -> OrganizationMembershipPublic:
        actor = await self._memberships.find_membership(organization_id, actor_user_id)
        if actor is None or actor.status != "active":
            raise ForbiddenError("Organization access denied")
        if not can_manage_members(actor.role):
            raise ForbiddenError("Insufficient permissions to manage members")
        target = await self._memberships.find_membership(organization_id, target_user_id)
        if target is None:
            raise NotFoundError("Membership not found")
        if target.role == OrganizationRole.OWNER and payload.role not in (None, OrganizationRole.OWNER):
            owners = await self._memberships.count_owners(organization_id)
            if owners <= 1:
                raise ForbiddenError("Cannot change role of the sole organization owner")
        updates: dict = {"updated_at": datetime.now(timezone.utc)}
        if payload.role is not None:
            updates["role"] = payload.role
        if payload.status is not None:
            updates["status"] = payload.status
        await self._memberships.update(str(target.id), updates)
        refreshed = await self._memberships.find_membership(organization_id, target_user_id)
        assert refreshed is not None
        user = await self._users.find_by_id(target_user_id)
        return OrganizationMembershipPublic(
            id=str(refreshed.id),
            organization_id=refreshed.organization_id,
            user_id=refreshed.user_id,
            user_email=user.email if user else None,
            user_name=user.name if user else None,
            role=refreshed.role,
            status=refreshed.status,
            created_at=refreshed.created_at,
            updated_at=refreshed.updated_at,
        )

    async def remove_member(
        self,
        organization_id: str,
        target_user_id: str,
        actor_user_id: str,
    ) -> None:
        actor = await self._memberships.find_membership(organization_id, actor_user_id)
        if actor is None or actor.status != "active":
            raise ForbiddenError("Organization access denied")
        if not can_manage_members(actor.role):
            raise ForbiddenError("Insufficient permissions to manage members")
        target = await self._memberships.find_membership(organization_id, target_user_id)
        if target is None:
            raise NotFoundError("Membership not found")
        if target.role == OrganizationRole.OWNER:
            owners = await self._memberships.count_owners(organization_id)
            if owners <= 1:
                raise ForbiddenError("Cannot remove the sole organization owner")
        await self._memberships.delete(str(target.id))
