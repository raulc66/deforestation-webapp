"""Organization bootstrap and legacy tenant migration."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from app.models.organization import Organization, OrganizationMembership
from app.repositories.forest_monitoring_area_repository import ForestMonitoringAreaRepository
from app.repositories.organization_membership_repository import OrganizationMembershipRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.services.entitlement_service import EntitlementService

logger = logging.getLogger("forestwatch.organization.bootstrap")

PERSONAL_ORG_NAME = "Personal Workspace"


def personal_organization_slug(user_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "-", str(user_id)).strip("-").lower() or "user"
    return f"personal-{safe}"


class OrganizationBootstrapService:
    """Idempotent personal organization creation and AOI migration."""

    def __init__(
        self,
        org_repo: OrganizationRepository,
        membership_repo: OrganizationMembershipRepository,
        area_repo: ForestMonitoringAreaRepository,
        user_repo: UserRepository,
        entitlement_svc: EntitlementService,
    ) -> None:
        self._orgs = org_repo
        self._memberships = membership_repo
        self._areas = area_repo
        self._users = user_repo
        self._entitlements = entitlement_svc

    async def ensure_personal_organization(self, user_id: str) -> Organization:
        slug = personal_organization_slug(user_id)
        existing = await self._orgs.find_by_slug(slug)
        if existing is not None:
            await self._entitlements.ensure_default_entitlements(str(existing.id))
            await self._migrate_user_aois(user_id, str(existing.id))
            return existing

        now = datetime.now(timezone.utc)
        user = await self._users.find_by_id(user_id)
        name = PERSONAL_ORG_NAME
        if user and user.name:
            name = f"{user.name}'s Workspace" if user.name != "Personal Workspace" else PERSONAL_ORG_NAME

        org = Organization(
            name=name,
            slug=slug,
            status="active",
            created_at=now,
            updated_at=now,
        )
        saved = await self._orgs.insert(org)

        membership = OrganizationMembership(
            organization_id=str(saved.id),
            user_id=user_id,
            role="owner",
            status="active",
            created_at=now,
            updated_at=now,
        )
        await self._memberships.insert(membership)
        await self._entitlements.ensure_default_entitlements(str(saved.id))
        await self._migrate_user_aois(user_id, str(saved.id))
        logger.info("Created personal organization for user %s", user_id)
        return saved

    async def migrate_all_users(self) -> int:
        """Ensure every user has a personal organization and migrated AOIs."""
        users = await self._users.find_many({}, limit=10_000)
        count = 0
        for user in users:
            if user.id:
                await self.ensure_personal_organization(str(user.id))
                count += 1
        return count

    async def _migrate_user_aois(self, user_id: str, organization_id: str) -> int:
        """Associate legacy tenant_id=user.id AOIs with the personal organization."""
        migrated = 0
        legacy_areas = await self._areas.list_for_tenant(user_id, enabled_only=False)
        for area in legacy_areas:
            area_id = str(area.id)
            updates: dict = {}
            if not getattr(area, "organization_id", None):
                updates["organization_id"] = organization_id
            if area.tenant_id == user_id:
                updates["organization_id"] = organization_id
            if updates:
                updates["updated_at"] = datetime.now(timezone.utc)
                await self._areas.update(area_id, updates)
                migrated += 1
        if migrated:
            logger.info(
                "Migrated %d monitoring area(s) for user %s -> org %s",
                migrated,
                user_id,
                organization_id,
            )
        return migrated
