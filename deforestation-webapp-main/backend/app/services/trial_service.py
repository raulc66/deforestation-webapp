"""Authenticated free-trial organization — real product architecture, limited profile.

Trial state lives on the user's personal organization. The reserved demo
organization is never converted, and extra organizations the user created are
left untouched. Entitlements are the existing ``OrganizationEntitlement`` rows
so a later paid plan can replace this profile without a second product stack.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.core.commercial.lifecycle import (
    CommercialLifecycle,
    days_remaining,
    is_plan_entitlement_source,
    resolve_commercial_lifecycle,
)
from app.core.commercial.trial_profile import (
    DEFAULT_TRIAL_DURATION_DAYS,
    TRIAL_ENTITLEMENT_PROFILE,
    TRIAL_ENTITLEMENT_SOURCE,
    TRIAL_EXPIRED_ENTITLEMENT_PROFILE,
    TRIAL_EXPIRED_ENTITLEMENT_SOURCE,
)
from app.core.demo.identity import is_demo_organization, is_demo_user
from app.core.errors import ConflictError, ForbiddenError
from app.core.organization.organization_roles import OrganizationRole
from app.models.organization import Organization
from app.models.trial import TrialStartRequest, TrialStatusPublic
from app.models.user import UserPublic
from app.repositories.alert_policy_repository import AlertPolicyRepository
from app.repositories.forest_monitoring_area_repository import ForestMonitoringAreaRepository
from app.repositories.organization_membership_repository import OrganizationMembershipRepository
from app.repositories.organization_notification_channel_repository import (
    OrganizationNotificationChannelRepository,
)
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.services.entitlement_service import EntitlementService
from app.services.organization_bootstrap_service import OrganizationBootstrapService

Clock = Callable[[], datetime]


class TrialService:
    def __init__(
        self,
        org_repo: OrganizationRepository,
        membership_repo: OrganizationMembershipRepository,
        user_repo: UserRepository,
        bootstrap_svc: OrganizationBootstrapService,
        entitlement_svc: EntitlementService,
        area_repo: ForestMonitoringAreaRepository,
        *,
        policy_repo: AlertPolicyRepository | None = None,
        channel_repo: OrganizationNotificationChannelRepository | None = None,
        duration_days: int = DEFAULT_TRIAL_DURATION_DAYS,
        now_fn: Clock | None = None,
    ) -> None:
        self._orgs = org_repo
        self._memberships = membership_repo
        self._users = user_repo
        self._bootstrap = bootstrap_svc
        self._entitlements = entitlement_svc
        self._areas = area_repo
        self._policies = policy_repo
        self._channels = channel_repo
        self._duration_days = max(int(duration_days), 1)
        self._now = now_fn or (lambda: datetime.now(timezone.utc))

    async def start_trial(
        self,
        user: UserPublic,
        payload: TrialStartRequest | None = None,
    ) -> TrialStatusPublic:
        if is_demo_user(user):
            raise ForbiddenError(
                "Sign out of the demonstration and create a real account to start a trial"
            )
        user_id = str(user.id)
        now = self._now()
        existing = await self._find_existing_trial_organization(user_id)
        if existing is not None:
            await self.ensure_current(existing, now=now)
            refreshed = await self._orgs.find_by_id(str(existing.id))
            assert refreshed is not None
            return await self.build_status(refreshed, user_id=user_id, now=now)

        personal = await self._bootstrap.ensure_personal_organization(user_id)
        if is_demo_organization(personal):
            raise ForbiddenError("The demonstration organization cannot become a trial")
        if personal.status != "active":
            raise ForbiddenError("Organization is suspended")
        membership = await self._memberships.find_active(str(personal.id), user_id)
        if membership is None or membership.role != OrganizationRole.OWNER:
            raise ForbiddenError("Only the organization owner can start a trial")

        profile = await self._entitlements.get_profile(str(personal.id))
        lifecycle = resolve_commercial_lifecycle(
            kind=personal.kind,
            stored=personal.commercial_lifecycle,
            trial_ends_at=personal.trial_ends_at,
            entitlement_source=profile.source,
            now=now,
        )
        if lifecycle == CommercialLifecycle.PAID.value or is_plan_entitlement_source(
            profile.source
        ):
            raise ConflictError("This organization already has a paid plan")
        if lifecycle == CommercialLifecycle.SUSPENDED.value:
            raise ForbiddenError("This organization cannot start a trial")

        trial_ends = now + timedelta(days=self._duration_days)
        updates: dict[str, Any] = {
            "commercial_lifecycle": CommercialLifecycle.TRIAL.value,
            "trial_started_at": now,
            "trial_ends_at": trial_ends,
            "trial_originating_user_id": user_id,
            "updated_at": now,
        }
        requested_name = (payload.organization_name if payload else None) or None
        if requested_name and requested_name.strip():
            updates["name"] = requested_name.strip()
        await self._orgs.update(str(personal.id), updates)
        await self._entitlements.apply_profile(
            str(personal.id),
            TRIAL_ENTITLEMENT_PROFILE,
            source=TRIAL_ENTITLEMENT_SOURCE,
            now=now,
        )
        refreshed = await self._orgs.find_by_id(str(personal.id))
        assert refreshed is not None
        return await self.build_status(refreshed, user_id=user_id, now=now)

    async def ensure_current_by_id(self, organization_id: str) -> Organization | None:
        org = await self._orgs.find_by_id(organization_id)
        if org is None:
            return None
        return await self.ensure_current(org)

    async def ensure_current(
        self,
        org: Organization,
        *,
        now: datetime | None = None,
    ) -> Organization:
        """Persist trial expiration when ``now >= trial_ends_at``. Never deletes data."""
        if is_demo_organization(org):
            return org
        stamped = now or self._now()
        profile = await self._entitlements.get_profile(str(org.id))
        if is_plan_entitlement_source(profile.source):
            return org
        lifecycle = resolve_commercial_lifecycle(
            kind=org.kind,
            stored=org.commercial_lifecycle,
            trial_ends_at=org.trial_ends_at,
            entitlement_source=profile.source,
            now=stamped,
        )
        if (
            org.commercial_lifecycle == CommercialLifecycle.TRIAL.value
            and lifecycle == CommercialLifecycle.TRIAL_EXPIRED.value
        ):
            await self._orgs.update(
                str(org.id),
                {
                    "commercial_lifecycle": CommercialLifecycle.TRIAL_EXPIRED.value,
                    "updated_at": stamped,
                },
            )
            await self._entitlements.apply_profile(
                str(org.id),
                TRIAL_EXPIRED_ENTITLEMENT_PROFILE,
                source=TRIAL_EXPIRED_ENTITLEMENT_SOURCE,
                now=stamped,
            )
            refreshed = await self._orgs.find_by_id(str(org.id))
            return refreshed or org
        return org

    async def status_for_context(
        self,
        user: UserPublic,
        organization_id: str,
    ) -> TrialStatusPublic:
        if is_demo_user(user):
            raise ForbiddenError("Trial status is not available in the demonstration")
        org = await self._orgs.find_by_id(organization_id)
        if org is None or is_demo_organization(org):
            raise ForbiddenError("Organization access denied")
        membership = await self._memberships.find_active(organization_id, str(user.id))
        if membership is None:
            raise ForbiddenError("Organization access denied")
        await self.ensure_current(org)
        refreshed = await self._orgs.find_by_id(organization_id)
        assert refreshed is not None
        return await self.build_status(refreshed, user_id=str(user.id), now=self._now())

    async def build_status(
        self,
        org: Organization,
        *,
        user_id: str,
        now: datetime,
    ) -> TrialStatusPublic:
        profile = await self._entitlements.get_profile(str(org.id))
        lifecycle = resolve_commercial_lifecycle(
            kind=org.kind,
            stored=org.commercial_lifecycle,
            trial_ends_at=org.trial_ends_at,
            entitlement_source=profile.source,
            now=now,
        )
        area_count = await self._entitlements.count_enabled_monitoring_areas(str(org.id))
        policy_count = 0
        channel_count = 0
        if self._policies is not None:
            policy_count = len(await self._policies.list_for_organization(str(org.id)))
        if self._channels is not None:
            channel_count = len(await self._channels.list_for_organization(str(org.id)))

        origin_id = org.trial_originating_user_id
        origin_email = None
        if origin_id:
            origin = await self._users.find_by_id(origin_id)
            origin_email = origin.email if origin else None

        has_area = area_count > 0
        has_policy = policy_count > 0
        is_trial = lifecycle == CommercialLifecycle.TRIAL.value
        is_expired = lifecycle == CommercialLifecycle.TRIAL_EXPIRED.value

        if is_expired:
            cta = {
                "visible": True,
                "moment": "expired",
                "label": "Continue monitoring",
            }
        elif is_trial and area_count >= profile.monitored_area_limit > 0:
            cta = {
                "visible": True,
                "moment": "area_limit",
                "label": "Add more monitored forests with Professional",
            }
        elif is_trial:
            cta = {"visible": False, "moment": None, "label": None}
        else:
            cta = {"visible": False, "moment": None, "label": None}

        alert_mode = "none"
        if is_trial and profile.alert_delivery_enabled:
            alert_mode = "account_email"

        return TrialStatusPublic(
            organization_id=str(org.id),
            organization_name=org.name,
            organization_slug=org.slug,
            commercial_lifecycle=lifecycle,
            trial_started_at=org.trial_started_at,
            trial_ends_at=org.trial_ends_at,
            days_remaining=days_remaining(trial_ends_at=org.trial_ends_at, now=now)
            if is_trial or is_expired
            else None,
            originating_user_id=origin_id,
            originating_user_email=origin_email,
            entitlements=profile.as_read_model(monitored_area_count=area_count),
            usage={
                "monitored_areas": area_count,
                "monitored_area_limit": profile.monitored_area_limit,
                "alert_policies": policy_count,
                "alert_policy_limit": profile.alert_policy_limit,
                "notification_channels": channel_count,
                "notification_channel_limit": profile.notification_channel_limit,
            },
            onboarding={
                "has_monitored_area": has_area,
                "has_alert_policy": has_policy,
                "complete": has_area,
            },
            alert_delivery_mode=alert_mode,
            upgrade_cta=cta,
        )

    async def _find_existing_trial_organization(self, user_id: str) -> Organization | None:
        memberships = await self._memberships.list_for_user(user_id, active_only=True)
        found: Organization | None = None
        for membership in memberships:
            if membership.role != OrganizationRole.OWNER:
                continue
            org = await self._orgs.find_by_id(membership.organization_id)
            if org is None or is_demo_organization(org):
                continue
            stored = str(org.commercial_lifecycle or "")
            if stored in {
                CommercialLifecycle.TRIAL.value,
                CommercialLifecycle.TRIAL_EXPIRED.value,
            }:
                found = org
                break
        return found
