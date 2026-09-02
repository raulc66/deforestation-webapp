"""In-memory doubles for the interactive demonstration control plane."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.demo.constants import DEMO_INTEL_COLLECTION
from app.models.customer_alert import (
    AlertDeliveryRecord,
    AlertPolicy,
    OrganizationNotificationChannel,
)
from app.models.demo import DemoProductEvent, DemoSession
from app.models.forest_monitoring_area import ForestMonitoringArea
from app.models.organization import Organization, OrganizationEntitlement
from fixtures.customer_alert_fakes import run_async  # noqa: F401

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)


class DemoStore:
    def __init__(self) -> None:
        self.organizations: dict[str, dict] = {}
        self.entitlements: dict[str, dict] = {}
        self.areas: dict[str, dict] = {}
        self.events: dict[str, dict] = {}
        self.policies: dict[str, dict] = {}
        self.channels: dict[str, dict] = {}
        self.deliveries: dict[str, dict] = {}
        self.sessions: dict[str, dict] = {}
        self.product_events: list[dict] = []
        self.memberships: dict[str, dict] = {}
        self._seq = 0

    def nid(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}-{self._seq}"


class _Col:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeOrgRepo:
    def __init__(self, store: DemoStore) -> None:
        self._store = store

    async def insert(self, doc: Organization) -> Organization:
        oid = self._store.nid("org")
        payload = doc.model_dump()
        payload["id"] = oid
        self._store.organizations[oid] = payload
        doc.id = oid
        return doc

    async def find_by_id(self, oid: str) -> Organization | None:
        raw = self._store.organizations.get(oid)
        return Organization.model_validate(raw) if raw else None

    async def find_by_slug(self, slug: str) -> Organization | None:
        for raw in self._store.organizations.values():
            if raw["slug"] == slug:
                return Organization.model_validate(raw)
        return None

    async def update(self, oid: str, updates: dict) -> bool:
        if oid not in self._store.organizations:
            return False
        self._store.organizations[oid].update(updates)
        return True

    async def list_all(self, *, limit: int = 500) -> list[Organization]:
        return [
            Organization.model_validate(raw)
            for raw in list(self._store.organizations.values())[:limit]
        ]


class FakeEntitlementRepo:
    def __init__(self, store: DemoStore) -> None:
        self._store = store

    async def list_for_organization(self, organization_id: str):
        return [
            OrganizationEntitlement.model_validate(raw)
            for raw in self._store.entitlements.values()
            if raw["organization_id"] == organization_id
        ]

    async def insert(self, row: OrganizationEntitlement) -> OrganizationEntitlement:
        eid = self._store.nid("ent")
        payload = row.model_dump()
        payload["id"] = eid
        self._store.entitlements[eid] = payload
        row.id = eid
        return row

    async def update(self, eid: str, updates: dict) -> bool:
        if eid not in self._store.entitlements:
            return False
        self._store.entitlements[eid].update(updates)
        return True


class FakeAreaRepo:
    def __init__(self, store: DemoStore) -> None:
        self._store = store

    async def list_for_organization(self, organization_id: str, enabled_only: bool = False):
        rows = [
            ForestMonitoringArea.model_validate(raw)
            for raw in self._store.areas.values()
            if raw["organization_id"] == organization_id
            and (not enabled_only or raw.get("enabled", True))
        ]
        return rows

    async def insert(self, doc: ForestMonitoringArea) -> ForestMonitoringArea:
        aid = self._store.nid("area")
        payload = doc.model_dump()
        payload["id"] = aid
        self._store.areas[aid] = payload
        doc.id = aid
        return doc


class FakeIntelRepo:
    def __init__(self, store: DemoStore, *, collection_name: str = DEMO_INTEL_COLLECTION) -> None:
        self._store = store
        self.col = _Col(collection_name)

    async def find_active(self) -> list[dict]:
        return [dict(row) for row in self._store.events.values() if row.get("status") == "active"]

    async def find_by_id(self, event_id: str) -> dict | None:
        raw = self._store.events.get(event_id)
        return dict(raw) if raw else None

    async def create(self, event: dict) -> dict:
        eid = self._store.nid("evt")
        payload = dict(event)
        payload["id"] = eid
        self._store.events[eid] = payload
        return dict(payload)

    async def delete_matching(self, query: dict) -> int:
        keys = list(self._store.events)
        removed = 0
        for key in keys:
            meta = (self._store.events[key].get("metadata") or {}).get("demo") or {}
            if query.get("metadata.demo.demo_catalog") and meta.get("demo_catalog"):
                del self._store.events[key]
                removed += 1
        return removed


class FakePolicyRepo:
    def __init__(self, store: DemoStore) -> None:
        self._store = store

    async def list_for_organization(self, organization_id: str, *, enabled_only: bool = False):
        rows = [
            AlertPolicy.model_validate(raw)
            for raw in self._store.policies.values()
            if raw["organization_id"] == organization_id
            and (not enabled_only or raw.get("enabled", True))
        ]
        return rows

    async def insert(self, policy: AlertPolicy) -> AlertPolicy:
        pid = self._store.nid("policy")
        payload = policy.model_dump()
        payload["id"] = pid
        self._store.policies[pid] = payload
        policy.id = pid
        return policy


class FakeChannelRepo:
    def __init__(self, store: DemoStore) -> None:
        self._store = store

    async def list_for_organization(self, organization_id: str, *, enabled_only: bool = False):
        rows = [
            OrganizationNotificationChannel.model_validate(raw)
            for raw in self._store.channels.values()
            if raw["organization_id"] == organization_id
            and (not enabled_only or raw.get("enabled", True))
        ]
        return rows

    async def insert(self, channel: OrganizationNotificationChannel) -> OrganizationNotificationChannel:
        cid = self._store.nid("channel")
        payload = channel.model_dump()
        payload["id"] = cid
        self._store.channels[cid] = payload
        channel.id = cid
        return channel


class FakeDeliveryRepo:
    def __init__(self, store: DemoStore) -> None:
        self._store = store

    async def find_by_dedupe_key(self, dedupe_key: str) -> dict | None:
        for row in self._store.deliveries.values():
            if row["dedupe_key"] == dedupe_key:
                return dict(row)
        return None

    async def create(self, record: AlertDeliveryRecord) -> dict:
        did = self._store.nid("delivery")
        payload = record.model_dump()
        payload["id"] = did
        self._store.deliveries[did] = payload
        return dict(payload)


class FakeSessionRepo:
    def __init__(self, store: DemoStore) -> None:
        self._store = store

    async def insert(self, doc: DemoSession) -> DemoSession:
        sid = self._store.nid("sess")
        payload = doc.model_dump()
        payload["id"] = sid
        self._store.sessions[sid] = payload
        doc.id = sid
        return doc

    async def find_by_id(self, session_id: str) -> DemoSession | None:
        raw = self._store.sessions.get(session_id)
        return DemoSession.model_validate(raw) if raw else None

    async def update(self, session_id: str, updates: dict) -> bool:
        if session_id not in self._store.sessions:
            return False
        self._store.sessions[session_id].update(updates)
        return True

    async def record_product_event(self, event: DemoProductEvent) -> DemoProductEvent:
        eid = self._store.nid("pe")
        payload = event.model_dump()
        payload["id"] = eid
        self._store.product_events.append(payload)
        event.id = eid
        return event

    async def list_product_events(self, session_id: str, *, limit: int = 50):
        rows = [row for row in self._store.product_events if row["session_id"] == session_id]
        return [DemoProductEvent.model_validate(row) for row in rows[:limit]]


class FakeMembershipRepo:
    def __init__(self, store: DemoStore) -> None:
        self._store = store

    async def find_membership(self, organization_id: str, user_id: str):
        return None

    async def find_active(self, organization_id: str, user_id: str):
        return None

    async def list_for_user(self, user_id: str, *, active_only: bool = True, limit: int = 100):
        return []


def build_catalog_and_sessions(store: DemoStore | None = None):
    from app.services.demo.demo_catalog_service import DemoCatalogService
    from app.services.demo.demo_session_service import DemoSessionService

    store = store or DemoStore()
    catalog = DemoCatalogService(
        org_repo=FakeOrgRepo(store),
        area_repo=FakeAreaRepo(store),
        entitlement_repo=FakeEntitlementRepo(store),
        intel_repo=FakeIntelRepo(store),
        policy_repo=FakePolicyRepo(store),
        channel_repo=FakeChannelRepo(store),
    )
    sessions = DemoSessionService(FakeSessionRepo(store), catalog)
    return store, catalog, sessions
