"""Organization + commercial entitlement foundation tests."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import (
    customer_monitoring_status_service_dep,
    get_current_user,
    get_organization_context,
    monitoring_area_read_model_service_dep,
    monitoring_area_service_dep,
    organization_context_service_dep,
    organization_service_dep,
)
from app.api.monitoring_area_routes import router as monitoring_area_router
from app.api.organization_routes import router as organization_router
from app.core.commercial.entitlement_types import DEFAULT_ENTITLEMENT_PROFILE
from app.core.config import Settings
from app.core.errors import ForbiddenError, NotFoundError
from app.core.organization.organization_context import ORGANIZATION_ID_HEADER, OrganizationContext
from app.models.forest_monitoring_area import ForestMonitoringAreaCreate
from app.models.organization import Organization, OrganizationMembership
from app.models.user import UserPublic
from app.modules.analytics.analytics_routes import router as analytics_router
from app.services.aoi_enrichment_service import AoiEnrichmentService
from app.services.customer_monitoring_status_service import CustomerMonitoringStatusService
from app.services.entitlement_service import EntitlementService
from app.services.forest_monitoring_area_service import ForestMonitoringAreaService
from app.services.monitoring_area_read_model_service import MonitoringAreaReadModelService
from app.services.organization_bootstrap_service import OrganizationBootstrapService, personal_organization_slug
from app.services.organization_context_service import OrganizationContextService
from app.services.organization_service import OrganizationService
from fixtures.phase0_golden_harness import generate_golden_artifacts
from fixtures.phase0_oracle_manifest import verify_generated_match_manifest

_NOW = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)


def _settings(**overrides) -> Settings:
    base = {
        "mongo_url": "mongodb://localhost:27017",
        "db_name": "test",
        "jwt_secret": "secret",
        "admin_email": "admin@test.com",
        "admin_password": "pass",
        "frontend_url": "http://localhost:3000",
    }
    base.update(overrides)
    return Settings(**base)


def _user(user_id: str = "user-a", email: str = "a@test.com", name: str = "User") -> UserPublic:
    return UserPublic(
        id=user_id,
        email=email,
        name=name,
        role="user",
        provider="local",
        created_at=_NOW,
    )


def _romania_polygon() -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[
            [25.5, 46.8], [26.5, 46.8], [26.5, 47.5], [25.5, 47.5], [25.5, 46.8],
        ]],
    }


class InMemoryOrgStore:
    def __init__(self) -> None:
        self.orgs: dict[str, dict] = {}
        self.memberships: dict[str, dict] = {}
        self.entitlements: dict[str, dict] = {}
        self.areas: dict[str, dict] = {}
        self.users: dict[str, dict] = {}
        self._seq = 0

    def nid(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}-{self._seq}"


def _wire_services(store: InMemoryOrgStore):
    org_repo = _OrgRepo(store)
    membership_repo = _MembershipRepo(store)
    entitlement_repo = _EntitlementRepo(store)
    area_repo = _AreaRepo(store)
    user_repo = _UserRepo(store)
    entitlement_svc = EntitlementService(entitlement_repo, area_repo)
    org_svc = OrganizationService(org_repo, membership_repo, user_repo, entitlement_svc)
    area_svc = ForestMonitoringAreaService(area_repo, entitlement_svc=entitlement_svc)
    bootstrap = OrganizationBootstrapService(org_repo, membership_repo, area_repo, user_repo, entitlement_svc)
    ctx_svc = OrganizationContextService(org_repo, membership_repo, bootstrap)
    return org_svc, area_svc, bootstrap, ctx_svc, entitlement_svc, area_repo


class _OrgRepo:
    def __init__(self, store: InMemoryOrgStore) -> None:
        self._store = store

    async def insert(self, doc: Organization) -> Organization:
        oid = self._store.nid("org")
        payload = doc.model_dump()
        payload["id"] = oid
        self._store.orgs[oid] = payload
        doc.id = oid
        return doc

    async def find_by_id(self, oid: str) -> Organization | None:
        raw = self._store.orgs.get(oid)
        return Organization.model_validate(raw) if raw else None

    async def find_by_slug(self, slug: str) -> Organization | None:
        for raw in self._store.orgs.values():
            if raw["slug"] == slug:
                return Organization.model_validate(raw)
        return None

    async def update(self, oid: str, updates: dict) -> bool:
        if oid not in self._store.orgs:
            return False
        self._store.orgs[oid].update(updates)
        return True


class _MembershipRepo:
    def __init__(self, store: InMemoryOrgStore) -> None:
        self._store = store

    async def insert(self, doc: OrganizationMembership) -> OrganizationMembership:
        mid = self._store.nid("mem")
        payload = doc.model_dump()
        payload["id"] = mid
        self._store.memberships[mid] = payload
        doc.id = mid
        return doc

    async def find_membership(self, org_id: str, user_id: str) -> OrganizationMembership | None:
        for raw in self._store.memberships.values():
            if raw["organization_id"] == org_id and raw["user_id"] == user_id:
                return OrganizationMembership.model_validate(raw)
        return None

    async def find_active(self, org_id: str, user_id: str) -> OrganizationMembership | None:
        m = await self.find_membership(org_id, user_id)
        return m if m and m.status == "active" else None

    async def list_for_user(self, user_id: str, *, active_only: bool = True, limit: int = 100):
        rows = [
            OrganizationMembership.model_validate(raw)
            for raw in self._store.memberships.values()
            if raw["user_id"] == user_id and (not active_only or raw["status"] == "active")
        ]
        return rows[:limit]

    async def list_for_organization(self, org_id: str, *, limit: int = 100):
        return [
            OrganizationMembership.model_validate(raw)
            for raw in self._store.memberships.values()
            if raw["organization_id"] == org_id
        ][:limit]

    async def count_owners(self, org_id: str) -> int:
        return sum(
            1 for raw in self._store.memberships.values()
            if raw["organization_id"] == org_id and raw["role"] == "owner" and raw["status"] == "active"
        )

    async def update(self, mid: str, updates: dict) -> bool:
        if mid not in self._store.memberships:
            return False
        self._store.memberships[mid].update(updates)
        return True

    async def delete(self, mid: str) -> bool:
        return self._store.memberships.pop(mid, None) is not None


class _EntitlementRepo:
    def __init__(self, store: InMemoryOrgStore) -> None:
        self._store = store

    async def list_for_organization(self, org_id: str, *, active_only: bool = True):
        from app.models.organization import OrganizationEntitlement

        return [
            OrganizationEntitlement.model_validate(raw)
            for raw in self._store.entitlements.values()
            if raw["organization_id"] == org_id and (not active_only or raw["status"] == "active")
        ]

    async def insert(self, doc):
        eid = self._store.nid("ent")
        payload = doc.model_dump()
        payload["id"] = eid
        self._store.entitlements[eid] = payload
        doc.id = eid
        return doc

    async def find_by_type(self, org_id: str, entitlement_type: str):
        from app.models.organization import OrganizationEntitlement

        for raw in self._store.entitlements.values():
            if raw["organization_id"] == org_id and raw["entitlement_type"] == entitlement_type:
                return OrganizationEntitlement.model_validate(raw)
        return None

    async def update(self, eid: str, updates: dict) -> bool:
        if eid not in self._store.entitlements:
            return False
        self._store.entitlements[eid].update(updates)
        return True


class _AreaRepo:
    def __init__(self, store: InMemoryOrgStore) -> None:
        self._store = store

    async def list_for_organization(self, org_id: str, *, enabled_only: bool = False, limit: int = 100):
        from app.models.forest_monitoring_area import ForestMonitoringArea

        rows = [
            ForestMonitoringArea.model_validate(raw)
            for raw in self._store.areas.values()
            if raw.get("organization_id") == org_id and (not enabled_only or raw.get("enabled", True))
        ]
        return rows[:limit]

    async def list_for_tenant(self, tenant_id: str, *, enabled_only: bool = False, limit: int = 100):
        from app.models.forest_monitoring_area import ForestMonitoringArea

        rows = [
            ForestMonitoringArea.model_validate(raw)
            for raw in self._store.areas.values()
            if raw.get("tenant_id") == tenant_id and (not enabled_only or raw.get("enabled", True))
        ]
        return rows[:limit]

    async def find_for_organization(self, org_id: str, area_id: str):
        from app.models.forest_monitoring_area import ForestMonitoringArea

        raw = self._store.areas.get(area_id)
        if raw is None or raw.get("organization_id") != org_id:
            return None
        return ForestMonitoringArea.model_validate(raw)

    async def insert(self, doc):
        aid = self._store.nid("area")
        payload = doc.model_dump()
        payload["id"] = aid
        self._store.areas[aid] = payload
        doc.id = aid
        return doc

    async def update(self, aid: str, updates: dict) -> bool:
        if aid not in self._store.areas:
            return False
        self._store.areas[aid].update(updates)
        return True

    async def delete(self, aid: str) -> bool:
        return self._store.areas.pop(aid, None) is not None

    async def delete_for_organization(self, org_id: str, area_id: str) -> bool:
        raw = self._store.areas.get(area_id)
        if raw is None or raw.get("organization_id") != org_id:
            return False
        return await self.delete(area_id)


class _UserRepo:
    def __init__(self, store: InMemoryOrgStore) -> None:
        self._store = store

    async def find_by_id(self, uid: str):
        from app.models.user import User

        raw = self._store.users.get(uid)
        return User.model_validate(raw) if raw else None

    async def find_by_email(self, email: str):
        from app.models.user import User

        for raw in self._store.users.values():
            if raw["email"].lower() == email.lower():
                return User.model_validate(raw)
        return None

    async def find_many(self, query=None, limit: int = 200, sort=None):
        from app.models.user import User

        return [User.model_validate(raw) for raw in self._store.users.values()][:limit]


def _seed_user(store: InMemoryOrgStore, user: UserPublic) -> None:
    store.users[str(user.id)] = {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "provider": user.provider,
        "created_at": user.created_at,
    }


def _client(store: InMemoryOrgStore, user: UserPublic):
    org_svc, area_svc, bootstrap, ctx_svc, _, _ = _wire_services(store)

    app = FastAPI()
    app.include_router(organization_router)
    app.include_router(monitoring_area_router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[organization_service_dep] = lambda: org_svc
    app.dependency_overrides[organization_context_service_dep] = lambda: ctx_svc
    app.dependency_overrides[monitoring_area_service_dep] = lambda: area_svc

    # Monitoring area reads use the enriched read model; an empty intelligence
    # repository keeps these organization-scope assertions database-free.
    intel_repo = MagicMock()
    intel_repo.find_active = AsyncMock(return_value=[])
    read_svc = MonitoringAreaReadModelService(area_svc, intel_repo)
    app.dependency_overrides[monitoring_area_read_model_service_dep] = lambda: read_svc

    async def _resolve_ctx():
        return await ctx_svc.resolve(user)

    app.dependency_overrides[get_organization_context] = _resolve_ctx
    return TestClient(app), org_svc, area_svc, bootstrap, ctx_svc


@pytest.fixture
def store():
    return InMemoryOrgStore()


@pytest.fixture
def user_a(store):
    u = _user("user-a", "a@test.com")
    _seed_user(store, u)
    return u


@pytest.fixture
def user_b(store):
    u = _user("user-b", "b@test.com", "User B")
    _seed_user(store, u)
    return u


class TestOrganizationCrud:
    def test_create_organization(self, store, user_a):
        client, _, _, _, _ = _client(store, user_a)
        resp = client.post("/organizations", json={"name": "Forest Co"})
        assert resp.status_code == 201
        assert resp.json()["slug"]

    def test_list_organizations(self, store, user_a):
        client, _, _, _, _ = _client(store, user_a)
        client.post("/organizations", json={"name": "Alpha Forestry"})
        assert client.get("/organizations").json()["items"]

    def test_get_organization(self, store, user_a):
        client, _, _, _, _ = _client(store, user_a)
        org_id = client.post("/organizations", json={"name": "Beta"}).json()["id"]
        assert client.get(f"/organizations/{org_id}").json()["name"] == "Beta"

    def test_update_organization(self, store, user_a):
        client, _, _, _, _ = _client(store, user_a)
        org_id = client.post("/organizations", json={"name": "Old"}).json()["id"]
        assert client.put(f"/organizations/{org_id}", json={"name": "New"}).json()["name"] == "New"

    def test_non_member_cannot_get_org(self, store, user_a, user_b):
        client_a, _, _, _, _ = _client(store, user_a)
        org_id = client_a.post("/organizations", json={"name": "Private"}).json()["id"]
        client_b, _, _, _, _ = _client(store, user_b)
        assert client_b.get(f"/organizations/{org_id}").status_code == 403


class TestMembership:
    def test_add_and_list_members(self, store, user_a, user_b):
        client, _, _, _, _ = _client(store, user_a)
        org_id = client.post("/organizations", json={"name": "Team"}).json()["id"]
        assert client.post(f"/organizations/{org_id}/members", json={"email": "b@test.com", "role": "member"}).status_code == 201
        members = client.get(f"/organizations/{org_id}/members").json()["items"]
        assert len(members) == 2

    def test_duplicate_member_rejected(self, store, user_a, user_b):
        client, _, _, _, _ = _client(store, user_a)
        org_id = client.post("/organizations", json={"name": "Team"}).json()["id"]
        client.post(f"/organizations/{org_id}/members", json={"email": "b@test.com"})
        assert client.post(f"/organizations/{org_id}/members", json={"email": "b@test.com"}).status_code == 409

    def test_update_member_role(self, store, user_a, user_b):
        client, _, _, _, _ = _client(store, user_a)
        org_id = client.post("/organizations", json={"name": "Team"}).json()["id"]
        client.post(f"/organizations/{org_id}/members", json={"email": "b@test.com", "role": "member"})
        updated = client.put(
            f"/organizations/{org_id}/members/user-b",
            json={"role": "admin"},
        ).json()
        assert updated["role"] == "admin"

    def test_remove_member(self, store, user_a, user_b):
        client, _, _, _, _ = _client(store, user_a)
        org_id = client.post("/organizations", json={"name": "Team"}).json()["id"]
        client.post(f"/organizations/{org_id}/members", json={"email": "b@test.com"})
        assert client.delete(f"/organizations/{org_id}/members/user-b").status_code == 204

    @pytest.mark.anyio
    async def test_member_cannot_create_aoi(self, store, user_a, user_b):
        _, area_svc, bootstrap, ctx_svc, _, _ = _wire_services(store)
        org = await bootstrap.ensure_personal_organization("user-a")
        org_id = str(org.id)
        await bootstrap._memberships.insert(
            OrganizationMembership(
                organization_id=org_id,
                user_id="user-b",
                role="member",
                status="active",
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        ctx = await ctx_svc.resolve(user_b, requested_organization_id=org_id)
        with pytest.raises(ForbiddenError):
            await area_svc.create_area(
                org_id,
                ForestMonitoringAreaCreate(name="X", geometry=_romania_polygon()),
                actor_role=ctx.role,
            )

    @pytest.mark.anyio
    async def test_suspended_membership_denied(self, store, user_a):
        _, _, bootstrap, ctx_svc, _, _ = _wire_services(store)
        org = await bootstrap.ensure_personal_organization("user-a")
        org_id = str(org.id)
        membership = await bootstrap._memberships.find_membership(org_id, "user-a")
        await bootstrap._memberships.update(str(membership.id), {"status": "suspended"})
        with pytest.raises(ForbiddenError):
            await ctx_svc.resolve(user_a, requested_organization_id=org_id)


class TestBootstrap:
    @pytest.mark.anyio
    async def test_personal_org_created(self, store, user_a):
        _, _, bootstrap, _, _, _ = _wire_services(store)
        org = await bootstrap.ensure_personal_organization("user-a")
        assert org.slug == personal_organization_slug("user-a")

    @pytest.mark.anyio
    async def test_bootstrap_idempotent(self, store, user_a):
        _, _, bootstrap, _, _, _ = _wire_services(store)
        first = await bootstrap.ensure_personal_organization("user-a")
        second = await bootstrap.ensure_personal_organization("user-a")
        assert str(first.id) == str(second.id)
        assert len(store.orgs) == 1

    @pytest.mark.anyio
    async def test_legacy_aoi_migrated(self, store, user_a):
        store.areas["legacy"] = {
            "id": "legacy",
            "tenant_id": "user-a",
            "organization_id": "",
            "name": "Legacy",
            "geometry": _romania_polygon(),
            "geometry_type": "Polygon",
            "country": "Romania",
            "enabled": True,
            "created_at": _NOW,
            "updated_at": _NOW,
        }
        _, _, bootstrap, _, _, _ = _wire_services(store)
        org = await bootstrap.ensure_personal_organization("user-a")
        assert store.areas["legacy"]["organization_id"] == str(org.id)

    @pytest.mark.anyio
    async def test_no_duplicate_aois_on_rebootstrap(self, store, user_a):
        store.areas["legacy"] = {
            "id": "legacy",
            "tenant_id": "user-a",
            "organization_id": "",
            "name": "Legacy",
            "geometry": _romania_polygon(),
            "geometry_type": "Polygon",
            "country": "Romania",
            "enabled": True,
            "created_at": _NOW,
            "updated_at": _NOW,
        }
        _, _, bootstrap, _, _, _ = _wire_services(store)
        await bootstrap.ensure_personal_organization("user-a")
        await bootstrap.ensure_personal_organization("user-a")
        assert len(store.areas) == 1


class TestEntitlements:
    @pytest.mark.anyio
    async def test_default_profile(self, store, user_a):
        _, _, bootstrap, _, entitlement_svc, _ = _wire_services(store)
        org = await bootstrap.ensure_personal_organization("user-a")
        profile = await entitlement_svc.get_profile(str(org.id))
        assert profile.monitored_area_limit == DEFAULT_ENTITLEMENT_PROFILE["monitored_area_limit"]
        assert profile.evidence_correlation_enabled is False
        assert profile.alert_delivery_enabled is False

    @pytest.mark.anyio
    async def test_first_aoi_allowed(self, store, user_a):
        _, area_svc, bootstrap, _, _, _ = _wire_services(store)
        org = await bootstrap.ensure_personal_organization("user-a")
        created = await area_svc.create_area(
            str(org.id),
            ForestMonitoringAreaCreate(name="One", geometry=_romania_polygon()),
            actor_role="owner",
        )
        assert created.organization_id == str(org.id)

    @pytest.mark.anyio
    async def test_second_aoi_rejected_at_limit(self, store, user_a):
        _, area_svc, bootstrap, _, _, _ = _wire_services(store)
        org = await bootstrap.ensure_personal_organization("user-a")
        org_id = str(org.id)
        await area_svc.create_area(org_id, ForestMonitoringAreaCreate(name="One", geometry=_romania_polygon()), actor_role="owner")
        with pytest.raises(ForbiddenError):
            await area_svc.create_area(org_id, ForestMonitoringAreaCreate(name="Two", geometry=_romania_polygon()), actor_role="owner")

    @pytest.mark.anyio
    async def test_disabled_aoi_does_not_block_new_within_limit(self, store, user_a):
        _, area_svc, bootstrap, _, entitlement_svc, area_repo = _wire_services(store)
        org = await bootstrap.ensure_personal_organization("user-a")
        org_id = str(org.id)
        first = await area_svc.create_area(org_id, ForestMonitoringAreaCreate(name="One", geometry=_romania_polygon()), actor_role="owner")
        await area_repo.update(str(first.id), {"enabled": False})
        second = await area_svc.create_area(org_id, ForestMonitoringAreaCreate(name="Two", geometry=_romania_polygon()), actor_role="owner")
        assert second.name == "Two"
        assert await entitlement_svc.count_enabled_monitoring_areas(org_id) == 1

    @pytest.mark.anyio
    async def test_entitlement_flags(self, store, user_a):
        _, _, bootstrap, _, entitlement_svc, _ = _wire_services(store)
        org = await bootstrap.ensure_personal_organization("user-a")
        org_id = str(org.id)
        assert await entitlement_svc.can_monitor(org_id)
        assert await entitlement_svc.can_use_forest_disturbance(org_id)
        assert not await entitlement_svc.can_use_live_sources(org_id)
        assert not await entitlement_svc.can_receive_alerts(org_id)

    @pytest.mark.anyio
    async def test_correlation_entitlement_disabled_by_default(self, store, user_a):
        _, _, bootstrap, _, entitlement_svc, _ = _wire_services(store)
        org_id = str((await bootstrap.ensure_personal_organization("user-a")).id)
        assert not await entitlement_svc.can_use_cross_source_correlation(org_id)

    @pytest.mark.anyio
    async def test_monitoring_disabled_blocks_aoi_create(self, store, user_a):
        _, area_svc, bootstrap, _, entitlement_svc, _ = _wire_services(store)
        entitlement_repo = entitlement_svc._entitlements
        org_id = str((await bootstrap.ensure_personal_organization("user-a")).id)
        row = await entitlement_repo.find_by_type(org_id, "monitoring_enabled")
        assert row is not None
        await entitlement_repo.update(str(row.id), {"value": False})
        assert not (await entitlement_svc.get_profile(org_id)).monitoring_enabled
        with pytest.raises(ForbiddenError):
            await area_svc.create_area(
                org_id,
                ForestMonitoringAreaCreate(name="Blocked", geometry=_romania_polygon()),
                actor_role="owner",
            )

    @pytest.mark.anyio
    async def test_suspended_organization_denied(self, store, user_a):
        _, _, bootstrap, ctx_svc, _, _ = _wire_services(store)
        org = await bootstrap.ensure_personal_organization("user-a")
        org_id = str(org.id)
        await bootstrap._orgs.update(org_id, {"status": "suspended"})
        with pytest.raises(ForbiddenError):
            await ctx_svc.resolve(user_a, requested_organization_id=org_id)

    @pytest.mark.anyio
    async def test_personal_org_name_default(self, store, user_a):
        _, _, bootstrap, _, _, _ = _wire_services(store)
        org = await bootstrap.ensure_personal_organization("user-a")
        assert org.name.endswith("Workspace")

    @pytest.mark.anyio
    async def test_no_duplicate_personal_orgs_for_user(self, store, user_a):
        _, _, bootstrap, _, _, _ = _wire_services(store)
        await bootstrap.ensure_personal_organization("user-a")
        await bootstrap.migrate_all_users()
        personal = [o for o in store.orgs.values() if o.get("slug") == personal_organization_slug("user-a")]
        assert len(personal) == 1
    def test_create_and_list_scoped_to_org(self, store, user_a):
        client, _, _, _, _ = _client(store, user_a)
        assert client.post("/monitoring-areas", json={"name": "Forest", "geometry": _romania_polygon()}).status_code == 201
        assert client.get("/monitoring-areas").json()["total"] == 1

    def test_cross_org_read_denied(self, store, user_a, user_b):
        client_a, _, _, _, _ = _client(store, user_a)
        area_id = client_a.post("/monitoring-areas", json={"name": "Secret", "geometry": _romania_polygon()}).json()["id"]
        client_b, _, _, _, _ = _client(store, user_b)
        assert client_b.get(f"/monitoring-areas/{area_id}").status_code == 404

    def test_cross_org_update_denied(self, store, user_a, user_b):
        client_a, _, _, _, _ = _client(store, user_a)
        area_id = client_a.post("/monitoring-areas", json={"name": "Secret", "geometry": _romania_polygon()}).json()["id"]
        client_b, _, _, _, _ = _client(store, user_b)
        assert client_b.put(f"/monitoring-areas/{area_id}", json={"name": "Hacked"}).status_code == 404

    def test_cross_org_delete_denied(self, store, user_a, user_b):
        client_a, _, _, _, _ = _client(store, user_a)
        area_id = client_a.post("/monitoring-areas", json={"name": "Secret", "geometry": _romania_polygon()}).json()["id"]
        client_b, _, _, _, _ = _client(store, user_b)
        assert client_b.delete(f"/monitoring-areas/{area_id}").status_code == 404

    @pytest.mark.anyio
    async def test_header_org_switch_requires_membership(self, store, user_a, user_b):
        _, _, bootstrap, ctx_svc, _, _ = _wire_services(store)
        org_a = await bootstrap.ensure_personal_organization("user-a")
        with pytest.raises(ForbiddenError):
            await ctx_svc.resolve(user_b, requested_organization_id=str(org_a.id))


class TestMonitoringStatus:
    @pytest.mark.anyio
    async def test_monitoring_status_includes_org_and_entitlements(self, store, user_a):
        _, area_svc, bootstrap, ctx_svc, entitlement_svc, _ = _wire_services(store)
        org = await bootstrap.ensure_personal_organization("user-a")
        ctx = await ctx_svc.resolve(user_a)
        status_svc = CustomerMonitoringStatusService(
            area_svc,
            intel_repo=_IntelRepo([]),
            source_intel=_SourceIntel(),
            cycle_repo=_CycleRepo(),
            correlation_repo=_CorrRepo(),
            health_repo=_HealthRepo(),
            entitlement_svc=entitlement_svc,
            settings=_settings(),
        )
        payload = await status_svc.get_monitoring_status(ctx)
        assert payload["organization"]["id"] == str(org.id)
        assert payload["entitlements"]["monitored_area_limit"] == 1
        assert "tenant_id" not in payload


class TestIntelligenceScoping:
    def test_aoi_enrichment_organization_scoped(self):
        svc = AoiEnrichmentService()
        areas = [{
            "id": "a1",
            "name": "Forest",
            "enabled": True,
            "geometry": _romania_polygon(),
        }]
        inside = svc.enrich_disturbance_item(
            latitude=47.12,
            longitude=25.98,
            organization_id="org-a",
            areas=areas,
            disturbance_block={},
        )
        outside = svc.enrich_disturbance_item(
            latitude=44.0,
            longitude=26.0,
            organization_id="org-a",
            areas=areas,
            disturbance_block={},
        )
        assert inside["inside_monitored_area"] is True
        assert outside["inside_monitored_area"] is False

    def test_same_event_different_orgs_independent(self):
        svc = AoiEnrichmentService()
        areas_a = [{"id": "a1", "name": "A", "enabled": True, "geometry": _romania_polygon()}]
        areas_b = [{"id": "b1", "name": "B", "enabled": True, "geometry": {
            "type": "Polygon",
            "coordinates": [[[9.5, 48.0], [10.5, 48.0], [10.5, 48.8], [9.5, 48.8], [9.5, 48.0]]],
        }}]
        lat, lng = 47.12, 25.98
        rel_a = svc.enrich_disturbance_item(latitude=lat, longitude=lng, organization_id="org-a", areas=areas_a, disturbance_block={})
        rel_b = svc.enrich_disturbance_item(latitude=lat, longitude=lng, organization_id="org-b", areas=areas_b, disturbance_block={})
        assert rel_a["customer_relevance"] is True
        assert rel_b.get("customer_relevance") is not True


class _IntelRepo:
    def __init__(self, rows):
        self._rows = rows

    async def find_active(self):
        return self._rows


class _SourceIntel:
    async def get_source_status(self):
        return {"sources": []}


class _CycleRepo:
    async def get_current(self):
        return {}


class _CorrRepo:
    async def list_all(self):
        return []


class _HealthRepo:
    async def list_all(self):
        return []


class TestSecurityManipulation:
    def test_unknown_org_id_in_path_returns_403_or_404(self, store, user_a):
        client, _, _, _, _ = _client(store, user_a)
        assert client.get("/organizations/org-unknown").status_code in {403, 404}

    @pytest.mark.anyio
    async def test_body_organization_id_ignored_for_aoi_scope(self, store, user_a, user_b):
        _, area_svc, bootstrap, _, _, _ = _wire_services(store)
        org_b = await bootstrap.ensure_personal_organization("user-b")
        org_a = await bootstrap.ensure_personal_organization("user-a")
        created = await area_svc.create_area(
            str(org_a.id),
            ForestMonitoringAreaCreate(name="Mine", geometry=_romania_polygon()),
            actor_role="owner",
        )
        assert created.organization_id == str(org_a.id)
        assert created.organization_id != str(org_b.id)

    @pytest.mark.anyio
    async def test_member_cannot_add_members(self, store, user_a, user_b):
        org_svc, _, _, _, _, _ = _wire_services(store)
        from app.models.organization import OrganizationCreate, OrganizationMembershipCreate

        org = await org_svc.create_organization("user-a", OrganizationCreate(name="Team"))
        await org_svc.add_member(org.id, "user-a", OrganizationMembershipCreate(email="b@test.com", role="member"))
        with pytest.raises(ForbiddenError):
            await org_svc.add_member(org.id, "user-b", OrganizationMembershipCreate(email="a@test.com", role="member"))

    @pytest.mark.anyio
    async def test_limits_independent_per_organization(self, store, user_a, user_b):
        _, area_svc, bootstrap, _, _, _ = _wire_services(store)
        org_a = await bootstrap.ensure_personal_organization("user-a")
        org_b = await bootstrap.ensure_personal_organization("user-b")
        await area_svc.create_area(str(org_a.id), ForestMonitoringAreaCreate(name="A1", geometry=_romania_polygon()), actor_role="owner")
        await area_svc.create_area(str(org_b.id), ForestMonitoringAreaCreate(name="B1", geometry=_romania_polygon()), actor_role="owner")
        with pytest.raises(ForbiddenError):
            await area_svc.create_area(str(org_a.id), ForestMonitoringAreaCreate(name="A2", geometry=_romania_polygon()), actor_role="owner")

    @pytest.mark.anyio
    async def test_existing_aoi_preserved_when_at_limit(self, store, user_a):
        _, area_svc, bootstrap, _, _, area_repo = _wire_services(store)
        org = await bootstrap.ensure_personal_organization("user-a")
        org_id = str(org.id)
        first = await area_svc.create_area(org_id, ForestMonitoringAreaCreate(name="Keep", geometry=_romania_polygon()), actor_role="owner")
        with pytest.raises(ForbiddenError):
            await area_svc.create_area(org_id, ForestMonitoringAreaCreate(name="New", geometry=_romania_polygon()), actor_role="owner")
        preserved = await area_repo.find_for_organization(org_id, str(first.id))
        assert preserved is not None
        assert preserved.name == "Keep"

    @pytest.mark.anyio
    async def test_admin_can_manage_aoi(self, store, user_a, user_b):
        _, area_svc, bootstrap, ctx_svc, _, _ = _wire_services(store)
        org = await bootstrap.ensure_personal_organization("user-a")
        org_id = str(org.id)
        await bootstrap._memberships.insert(
            OrganizationMembership(
                organization_id=org_id,
                user_id="user-b",
                role="admin",
                status="active",
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        ctx = await ctx_svc.resolve(user_b, requested_organization_id=org_id)
        created = await area_svc.create_area(
            org_id,
            ForestMonitoringAreaCreate(name="Admin Forest", geometry=_romania_polygon()),
            actor_role=ctx.role,
        )
        assert created.name == "Admin Forest"

    @pytest.mark.anyio
    async def test_resolve_default_organization_for_user(self, store, user_a):
        _, _, bootstrap, ctx_svc, _, _ = _wire_services(store)
        await bootstrap.ensure_personal_organization("user-a")
        ctx = await ctx_svc.resolve(user_a)
        assert ctx.role == "owner"
        assert ctx.organization_name

    @pytest.mark.anyio
    async def test_entitlement_can_add_monitoring_area(self, store, user_a):
        _, area_svc, bootstrap, _, entitlement_svc, _ = _wire_services(store)
        org = await bootstrap.ensure_personal_organization("user-a")
        org_id = str(org.id)
        assert await entitlement_svc.can_add_monitoring_area(org_id)
        await area_svc.create_area(org_id, ForestMonitoringAreaCreate(name="Only", geometry=_romania_polygon()), actor_role="owner")
        assert not await entitlement_svc.can_add_monitoring_area(org_id)


class TestPhase0Safety:
    def test_oracle_unchanged(self):
        verify_generated_match_manifest(generate_golden_artifacts())

    def test_ten_run_determinism(self):
        for _ in range(10):
            verify_generated_match_manifest(generate_golden_artifacts())

    def test_wildfire_baselines_untouched(self):
        generated = generate_golden_artifacts()
        assert "Harghita" in generated["cycle_0_regional_baselines.json"]

    def test_no_forest_disturbance_in_phase0_baselines(self):
        generated = generate_golden_artifacts()
        assert "forest_disturbance" not in generated["cycle_0_regional_baselines.json"]
