"""Authenticated free-trial organization — lifecycle, entitlements, isolation."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "forestwatch_trial_test")
os.environ.setdefault("JWT_SECRET", "trial-test-secret-32-bytes-minimum")

from app.core.commercial.entitlement_types import DEFAULT_ENTITLEMENT_SOURCE
from app.core.commercial.lifecycle import CommercialLifecycle, resolve_commercial_lifecycle
from app.core.commercial.plan_catalog import plan_entitlement_source
from app.core.commercial.trial_profile import (
    TRIAL_ENTITLEMENT_PROFILE,
    TRIAL_ENTITLEMENT_SOURCE,
    TRIAL_EXPIRED_ENTITLEMENT_SOURCE,
)
from app.core.errors import ConflictError, ForbiddenError
from app.models.customer_alert import AlertPolicyCreate, NotificationChannelCreate
from app.models.forest_monitoring_area import ForestMonitoringAreaCreate
from app.models.organization import Organization, OrganizationCreate
from app.models.trial import TrialStartRequest
from app.models.user import UserPublic
from app.services.alert_policy_service import AlertPolicyService
from app.services.organization_service import OrganizationService
from app.services.trial_service import TrialService
from test_organization_commercial import (
    InMemoryOrgStore,
    _AreaRepo,
    _EntitlementRepo,
    _MembershipRepo,
    _OrgRepo,
    _UserRepo,
    _romania_polygon,
    _seed_user,
    _user,
    _wire_services,
)

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)


def _demo_user() -> UserPublic:
    return UserPublic(
        id="demo:session-1",
        email="demo@forestwatch.local",
        name="ForestWatch Demo",
        role="user",
        provider="demo",
        created_at=NOW,
    )


class _PolicyRepo:
    def __init__(self, store: InMemoryOrgStore) -> None:
        self._store = store
        if not hasattr(store, "policies"):
            store.policies = {}

    async def list_for_organization(self, org_id: str, *, enabled_only: bool = False):
        from app.models.customer_alert import AlertPolicy

        rows = [
            AlertPolicy.model_validate(raw)
            for raw in self._store.policies.values()
            if raw["organization_id"] == org_id and (not enabled_only or raw.get("enabled", True))
        ]
        return rows

    async def find_for_organization(self, org_id: str, policy_id: str):
        from app.models.customer_alert import AlertPolicy

        raw = self._store.policies.get(policy_id)
        if raw is None or raw["organization_id"] != org_id:
            return None
        return AlertPolicy.model_validate(raw)

    async def insert(self, doc):
        pid = self._store.nid("policy")
        payload = doc.model_dump()
        payload["id"] = pid
        self._store.policies[pid] = payload
        doc.id = pid
        return doc

    async def update(self, pid: str, updates: dict) -> bool:
        if pid not in self._store.policies:
            return False
        self._store.policies[pid].update(updates)
        return True

    async def delete(self, pid: str) -> bool:
        return self._store.policies.pop(pid, None) is not None


class _ChannelRepo:
    def __init__(self, store: InMemoryOrgStore) -> None:
        self._store = store
        if not hasattr(store, "channels"):
            store.channels = {}

    async def list_for_organization(self, org_id: str):
        from app.models.customer_alert import OrganizationNotificationChannel

        return [
            OrganizationNotificationChannel.model_validate(raw)
            for raw in self._store.channels.values()
            if raw["organization_id"] == org_id
        ]

    async def find_for_organization(self, org_id: str, channel_id: str):
        from app.models.customer_alert import OrganizationNotificationChannel

        raw = self._store.channels.get(channel_id)
        if raw is None or raw["organization_id"] != org_id:
            return None
        return OrganizationNotificationChannel.model_validate(raw)

    async def insert(self, doc):
        cid = self._store.nid("chan")
        payload = doc.model_dump()
        payload["id"] = cid
        self._store.channels[cid] = payload
        doc.id = cid
        return doc

    async def update(self, cid: str, updates: dict) -> bool:
        if cid not in self._store.channels:
            return False
        self._store.channels[cid].update(updates)
        return True

    async def delete(self, cid: str) -> bool:
        return self._store.channels.pop(cid, None) is not None


class _DeliveryRepo:
    def __init__(self, store: InMemoryOrgStore) -> None:
        self._store = store
        if not hasattr(store, "deliveries"):
            store.deliveries = {}

    async def list_for_organization(self, org_id: str, *, limit: int = 50, lifecycle=None):
        return []

    async def count_by_lifecycle(self, org_id: str) -> dict:
        return {}


def _trial_env(store: InMemoryOrgStore | None = None, *, now: datetime = NOW):
    store = store or InMemoryOrgStore()
    org_svc, area_svc, bootstrap, ctx_svc, entitlement_svc, area_repo = _wire_services(store)
    org_repo = _OrgRepo(store)
    membership_repo = _MembershipRepo(store)
    user_repo = _UserRepo(store)
    policy_repo = _PolicyRepo(store)
    channel_repo = _ChannelRepo(store)
    trial = TrialService(
        org_repo,
        membership_repo,
        user_repo,
        bootstrap,
        entitlement_svc,
        area_repo,
        policy_repo=policy_repo,
        channel_repo=channel_repo,
        duration_days=14,
        now_fn=lambda: now,
    )
    alerts = AlertPolicyService(
        policy_repo,
        channel_repo,
        _DeliveryRepo(store),
        entitlement_svc,
        app_secret="trial-test-secret-32-bytes-minimum",
        area_repo=area_repo,
    )
    return {
        "store": store,
        "trial": trial,
        "bootstrap": bootstrap,
        "area_svc": area_svc,
        "org_svc": org_svc,
        "entitlements": entitlement_svc,
        "alerts": alerts,
        "org_repo": org_repo,
        "ctx_svc": ctx_svc,
    }


@pytest.fixture
def store():
    return InMemoryOrgStore()


class TestLifecycleVocabulary:
    def test_demo_kind_is_not_a_commercial_state(self):
        status = resolve_commercial_lifecycle(
            kind="demo",
            stored="trial",
            trial_ends_at=NOW + timedelta(days=1),
            entitlement_source=TRIAL_ENTITLEMENT_SOURCE,
            now=NOW,
        )
        assert status == CommercialLifecycle.UNSUBSCRIBED.value

    def test_expiration_is_deterministic(self):
        ends = NOW + timedelta(seconds=1)
        assert (
            resolve_commercial_lifecycle(
                kind="customer",
                stored="trial",
                trial_ends_at=ends,
                entitlement_source=TRIAL_ENTITLEMENT_SOURCE,
                now=NOW,
            )
            == CommercialLifecycle.TRIAL.value
        )
        assert (
            resolve_commercial_lifecycle(
                kind="customer",
                stored="trial",
                trial_ends_at=ends,
                entitlement_source=TRIAL_ENTITLEMENT_SOURCE,
                now=ends,
            )
            == CommercialLifecycle.TRIAL_EXPIRED.value
        )

    def test_plan_source_wins_over_stored_trial(self):
        status = resolve_commercial_lifecycle(
            kind="customer",
            stored="trial",
            trial_ends_at=NOW - timedelta(days=1),
            entitlement_source=plan_entitlement_source("professional"),
            now=NOW,
        )
        assert status == CommercialLifecycle.PAID.value


class TestTrialCreation:
    @pytest.mark.anyio
    async def test_start_upgrades_personal_org_and_is_idempotent(self, store):
        env = _trial_env(store)
        user = _user("user-a", "a@test.com", "Ada")
        _seed_user(store, user)
        first = await env["trial"].start_trial(user, TrialStartRequest(organization_name="Carpathian Watch"))
        second = await env["trial"].start_trial(user)
        assert first.organization_id == second.organization_id
        assert first.commercial_lifecycle == "trial"
        assert second.commercial_lifecycle == "trial"
        assert first.trial_started_at == second.trial_started_at == NOW
        assert first.trial_ends_at == NOW + timedelta(days=14)
        assert first.originating_user_id == "user-a"
        org = await env["org_repo"].find_by_id(first.organization_id)
        assert org.kind == "customer"
        assert org.name == "Carpathian Watch"
        assert org.slug.startswith("personal-")
        profile = await env["entitlements"].get_profile(first.organization_id)
        assert profile.source == TRIAL_ENTITLEMENT_SOURCE
        assert profile.monitored_area_limit == 2
        assert profile.alert_delivery_enabled is True
        assert profile.live_sources_enabled is True
        assert profile.evidence_correlation_enabled is True
        assert profile.alert_policy_limit == 1
        trial_orgs = [
            raw
            for raw in store.orgs.values()
            if raw.get("commercial_lifecycle") == "trial"
        ]
        assert len(trial_orgs) == 1

    @pytest.mark.anyio
    async def test_demo_user_cannot_start_trial(self, store):
        env = _trial_env(store)
        with pytest.raises(ForbiddenError):
            await env["trial"].start_trial(_demo_user())

    @pytest.mark.anyio
    async def test_demo_org_cannot_become_trial(self, store):
        env = _trial_env(store)
        user = _user()
        _seed_user(store, user)
        now = NOW
        demo = Organization(
            name="ForestWatch Demonstration",
            slug="forestwatch-demo",
            kind="demo",
            status="active",
            created_at=now,
            updated_at=now,
        )
        saved = await env["org_repo"].insert(demo)
        store.orgs[str(saved.id)]["slug"] = "personal-user-a"
        store.orgs[str(saved.id)]["kind"] = "demo"
        with pytest.raises(ForbiddenError):
            await env["trial"].start_trial(user)

    @pytest.mark.anyio
    async def test_extra_organization_is_not_modified(self, store):
        env = _trial_env(store)
        user = _user()
        _seed_user(store, user)
        extra = await env["org_svc"].create_organization(
            "user-a", OrganizationCreate(name="Other Holdings")
        )
        status = await env["trial"].start_trial(user)
        assert extra.id != status.organization_id
        other = await env["org_repo"].find_by_id(extra.id)
        assert other.commercial_lifecycle == "unsubscribed"
        extra_profile = await env["entitlements"].get_profile(extra.id)
        assert extra_profile.source == DEFAULT_ENTITLEMENT_SOURCE

    @pytest.mark.anyio
    async def test_paid_plan_source_refuses_trial(self, store):
        env = _trial_env(store)
        user = _user()
        _seed_user(store, user)
        org = await env["bootstrap"].ensure_personal_organization("user-a")
        await env["entitlements"].apply_profile(
            str(org.id),
            TRIAL_ENTITLEMENT_PROFILE,
            source=plan_entitlement_source("professional"),
            now=NOW,
        )
        with pytest.raises(ConflictError):
            await env["trial"].start_trial(user)

    @pytest.mark.anyio
    async def test_forged_lifecycle_on_update_is_ignored(self, store):
        env = _trial_env(store)
        user = _user()
        _seed_user(store, user)
        org = await env["bootstrap"].ensure_personal_organization("user-a")
        from app.models.organization import OrganizationUpdate

        await env["org_svc"].update_organization(
            str(org.id),
            "user-a",
            OrganizationUpdate(name="Still Personal"),
        )
        refreshed = await env["org_repo"].find_by_id(str(org.id))
        assert refreshed.commercial_lifecycle == "unsubscribed"


class TestTrialExpirationAndLimits:
    @pytest.mark.anyio
    async def test_expiration_changes_capabilities_and_keeps_data(self, store):
        start = NOW
        env = _trial_env(store, now=start)
        user = _user()
        _seed_user(store, user)
        status = await env["trial"].start_trial(user)
        org_id = status.organization_id
        await env["area_svc"].create_area(
            org_id,
            ForestMonitoringAreaCreate(name="Stand A", geometry=_romania_polygon()),
            actor_role="owner",
        )
        later = start + timedelta(days=14)
        env["trial"]._now = lambda: later
        org = await env["org_repo"].find_by_id(org_id)
        await env["trial"].ensure_current(org, now=later)
        expired = await env["org_repo"].find_by_id(org_id)
        assert expired.commercial_lifecycle == "trial_expired"
        profile = await env["entitlements"].get_profile(org_id)
        assert profile.source == TRIAL_EXPIRED_ENTITLEMENT_SOURCE
        assert profile.alert_delivery_enabled is False
        assert profile.live_sources_enabled is False
        assert profile.monitored_area_limit == 0
        areas = await env["area_svc"].list_areas(org_id)
        assert areas["total"] == 1
        with pytest.raises(ForbiddenError):
            await env["area_svc"].create_area(
                org_id,
                ForestMonitoringAreaCreate(name="Stand B", geometry=_romania_polygon()),
                actor_role="owner",
            )
        with pytest.raises(ForbiddenError):
            await env["alerts"].create_policy(
                org_id,
                AlertPolicyCreate(name="Watch"),
                actor_role="owner",
            )
        again = await env["trial"].start_trial(user)
        assert again.organization_id == org_id
        assert again.commercial_lifecycle == "trial_expired"

    @pytest.mark.anyio
    async def test_aoi_limit_during_active_trial(self, store):
        env = _trial_env(store)
        user = _user()
        _seed_user(store, user)
        status = await env["trial"].start_trial(user)
        org_id = status.organization_id
        await env["area_svc"].create_area(
            org_id,
            ForestMonitoringAreaCreate(name="One", geometry=_romania_polygon()),
            actor_role="owner",
        )
        await env["area_svc"].create_area(
            org_id,
            ForestMonitoringAreaCreate(name="Two", geometry=_romania_polygon()),
            actor_role="owner",
        )
        with pytest.raises(ForbiddenError):
            await env["area_svc"].create_area(
                org_id,
                ForestMonitoringAreaCreate(name="Three", geometry=_romania_polygon()),
                actor_role="owner",
            )

    @pytest.mark.anyio
    async def test_alert_policy_and_email_constraints(self, store):
        env = _trial_env(store)
        user = _user()
        _seed_user(store, user)
        status = await env["trial"].start_trial(user)
        org_id = status.organization_id
        await env["alerts"].create_policy(
            org_id,
            AlertPolicyCreate(name="Disturbance watch"),
            actor_role="owner",
        )
        with pytest.raises(ForbiddenError):
            await env["alerts"].create_policy(
                org_id,
                AlertPolicyCreate(name="Second"),
                actor_role="owner",
            )
        with pytest.raises(ForbiddenError):
            await env["alerts"].create_channel(
                org_id,
                NotificationChannelCreate(
                    name="Hook",
                    channel_type="webhook",
                    config={"url": "https://example.com/hook"},
                ),
                actor_role="owner",
                actor_email="a@test.com",
            )
        with pytest.raises(ForbiddenError):
            await env["alerts"].create_channel(
                org_id,
                NotificationChannelCreate(
                    name="Mail",
                    channel_type="email",
                    config={"recipients": ["other@example.com"]},
                ),
                actor_role="owner",
                actor_email="a@test.com",
            )
        channel = await env["alerts"].create_channel(
            org_id,
            NotificationChannelCreate(
                name="Account",
                channel_type="email",
                config={"recipients": ["a@test.com"]},
            ),
            actor_role="owner",
            actor_email="a@test.com",
        )
        assert channel.channel_type == "email"
        with pytest.raises(ForbiddenError):
            await env["alerts"].create_channel(
                org_id,
                NotificationChannelCreate(
                    name="Second mail",
                    channel_type="email",
                    config={"recipients": ["a@test.com"]},
                ),
                actor_role="owner",
                actor_email="a@test.com",
            )

    @pytest.mark.anyio
    async def test_user_isolation(self, store):
        env = _trial_env(store)
        user_a = _user("user-a", "a@test.com", "A")
        user_b = _user("user-b", "b@test.com", "B")
        _seed_user(store, user_a)
        _seed_user(store, user_b)
        trial_a = await env["trial"].start_trial(user_a)
        trial_b = await env["trial"].start_trial(user_b)
        assert trial_a.organization_id != trial_b.organization_id
        with pytest.raises(ForbiddenError):
            await env["trial"].status_for_context(user_b, trial_a.organization_id)

    @pytest.mark.anyio
    async def test_paid_profile_is_not_overwritten_on_expiration(self, store):
        env = _trial_env(store)
        user = _user()
        _seed_user(store, user)
        status = await env["trial"].start_trial(user)
        org_id = status.organization_id
        await env["entitlements"].apply_profile(
            org_id,
            TRIAL_ENTITLEMENT_PROFILE,
            source=plan_entitlement_source("professional"),
            now=NOW,
        )
        org = await env["org_repo"].find_by_id(org_id)
        org.trial_ends_at = NOW - timedelta(days=1)
        await env["trial"].ensure_current(org, now=NOW)
        profile = await env["entitlements"].get_profile(org_id)
        assert profile.source == plan_entitlement_source("professional")
        refreshed = await env["org_repo"].find_by_id(org_id)
        assert refreshed.commercial_lifecycle == "trial"


class TestSchedulerSkipSemantics:
    @pytest.mark.anyio
    async def test_expired_trial_cannot_receive_alerts(self, store):
        env = _trial_env(store)
        user = _user()
        _seed_user(store, user)
        status = await env["trial"].start_trial(user)
        org_id = status.organization_id
        assert await env["entitlements"].can_receive_alerts(org_id)
        later = NOW + timedelta(days=14)
        org = await env["org_repo"].find_by_id(org_id)
        await env["trial"].ensure_current(org, now=later)
        assert not await env["entitlements"].can_receive_alerts(org_id)
