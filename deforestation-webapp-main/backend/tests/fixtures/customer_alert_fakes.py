"""In-memory doubles for the customer alerting pipeline.

These fakes mirror the behavioural contract of the Mongo repositories closely
enough to test reliability semantics (dedupe, cooldown, lifecycle transitions,
organization isolation) without a database.
"""
from __future__ import annotations

import asyncio
import functools
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.commercial.entitlement_types import EntitlementType
from app.models.customer_alert import (
    DISPATCHABLE_LIFECYCLES,
    AlertDeliveryRecord,
    AlertPolicy,
    OrganizationNotificationChannel,
)
from app.models.organization import Organization, OrganizationEntitlement
from app.services.alert_policy_service import AlertPolicyService
from app.services.customer_alert_dispatcher import CustomerAlertDispatcher
from app.services.customer_alert_evaluation_service import CustomerAlertEvaluationService
from app.services.customer_alert_notification_service import CustomerAlertNotificationService
from app.services.entitlement_service import EntitlementService
from app.services.notifications.email_sender import EmailSender, EmailSendResult, FakeEmailSender
from app.services.notifications.org_webhook_sender import WebhookSendResult

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)
APP_SECRET = "test-app-secret"

_NOTIFIED = {"sent", "acknowledged", "resolved"}


def run_async(test_fn):
    """Run an ``async def`` test body without a global asyncio plugin.

    ``functools.wraps`` keeps ``__wrapped__`` so pytest still resolves fixtures
    from the original signature.
    """

    @functools.wraps(test_fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(test_fn(*args, **kwargs))

    return wrapper


def polygon_harghita() -> dict:
    """AOI covering the disturbance coordinates used by the event helpers."""
    return {
        "type": "Polygon",
        "coordinates": [
            [[25.5, 46.8], [26.5, 46.8], [26.5, 47.5], [25.5, 47.5], [25.5, 46.8]]
        ],
    }


def polygon_maramures() -> dict:
    """Disjoint AOI — used to prove organization-specific relevance."""
    return {
        "type": "Polygon",
        "coordinates": [
            [[23.0, 47.5], [24.0, 47.5], [24.0, 48.0], [23.0, 48.0], [23.0, 47.5]]
        ],
    }


def make_disturbance_event(
    event_id: str = "evt-1",
    *,
    priority: str = "high",
    severity: str = "high",
    latitude: float = 46.9,
    longitude: float = 26.0,
    status: str = "active",
    region: str = "RO-Harghita",
) -> dict[str, Any]:
    return {
        "id": event_id,
        "incident_category": "forest_disturbance",
        "status": status,
        "severity": severity,
        "region": region,
        "latitude": latitude,
        "longitude": longitude,
        "first_detected_at": NOW,
        "last_detected_at": NOW,
        "contributing_sources": ["gfw_integrated_alerts"],
        "metadata": {
            "forest_disturbance": {
                "investigation_priority": priority,
                "driver_confidence": 0.82,
                "affected_area_ha": 4.7,
                "probable_driver": "selective_logging_candidate",
                "authorization_status": "unknown",
            }
        },
    }


class FailingEmailSender(EmailSender):
    """Every send fails — proves failure isolation."""

    def __init__(self, error: str = "smtp_unavailable") -> None:
        self.attempts: list[dict] = []
        self._error = error

    async def send(self, *, recipients: list[str], subject: str, body: str) -> EmailSendResult:
        self.attempts.append({"recipients": list(recipients), "subject": subject})
        return EmailSendResult(success=False, error=self._error)


class RaisingEmailSender(EmailSender):
    """Raises instead of returning a result — proves the dispatcher contains it."""

    async def send(self, *, recipients: list[str], subject: str, body: str) -> EmailSendResult:
        raise RuntimeError("email adapter exploded")


class RecordingWebhookSender:
    def __init__(self, *, success: bool = True, error: str | None = None) -> None:
        self.calls: list[dict] = []
        self._success = success
        self._error = error

    async def send(self, *, url: str, payload: dict, secret_token: str = "") -> WebhookSendResult:
        self.calls.append({"url": url, "payload": payload, "secret_token": secret_token})
        if self._success:
            return WebhookSendResult(success=True, status_code=200)
        return WebhookSendResult(success=False, status_code=500, error=self._error or "http_500")


class InMemoryAlertStore:
    def __init__(self) -> None:
        self.orgs: dict[str, Organization] = {}
        self.areas: dict[str, dict] = {}
        self.policies: dict[str, dict] = {}
        self.channels: dict[str, dict] = {}
        self.deliveries: dict[str, dict] = {}
        self.entitlements: dict[str, dict] = {}
        self.events: dict[str, dict] = {}
        self._counter = 0

    def next_id(self, prefix: str = "id") -> str:
        self._counter += 1
        return f"{prefix}-{self._counter}"

    # --- seeding helpers ------------------------------------------------ #

    def add_organization(self, org_id: str, name: str) -> str:
        self.orgs[org_id] = Organization(
            id=org_id,
            name=name,
            slug=name.lower().replace(" ", "-"),
            created_at=NOW,
            updated_at=NOW,
        )
        return org_id

    def add_area(self, org_id: str, name: str, geometry: dict, *, enabled: bool = True) -> str:
        area_id = self.next_id("area")
        self.areas[area_id] = {
            "id": area_id,
            "organization_id": org_id,
            "name": name,
            "geometry": geometry,
            "enabled": enabled,
        }
        return area_id

    def set_alert_entitlement(self, org_id: str, value: bool) -> None:
        self._upsert_entitlement(
            org_id, EntitlementType.ALERT_DELIVERY_ENABLED.value, value
        )
        if value:
            self._upsert_entitlement(
                org_id, EntitlementType.ALERT_POLICY_LIMIT.value, 50
            )
            self._upsert_entitlement(
                org_id, EntitlementType.NOTIFICATION_CHANNEL_LIMIT.value, 50
            )

    def _upsert_entitlement(self, org_id: str, entitlement_type: str, value) -> None:
        for row in self.entitlements.values():
            if (
                row["organization_id"] == org_id
                and row["entitlement_type"] == entitlement_type
            ):
                row["value"] = value
                return
        ent_id = self.next_id("ent")
        self.entitlements[ent_id] = {
            "id": ent_id,
            "organization_id": org_id,
            "entitlement_type": entitlement_type,
            "value": value,
            "source": "test",
            "effective_from": NOW,
            "status": "active",
            "created_at": NOW,
            "updated_at": NOW,
        }


class _FakeArea:
    def __init__(self, raw: dict) -> None:
        self.id = raw["id"]
        self.name = raw["name"]
        self.geometry = raw["geometry"]
        self.enabled = raw.get("enabled", True)
        self.organization_id = raw["organization_id"]


class FakeOrgRepo:
    def __init__(self, store: InMemoryAlertStore) -> None:
        self._store = store

    async def list_all(self, *, limit: int = 500) -> list[Organization]:
        return list(self._store.orgs.values())[:limit]

    async def find_many(self, query: dict | None = None, limit: int = 200, sort=None):
        return list(self._store.orgs.values())[:limit]


class FakeAreaRepo:
    def __init__(self, store: InMemoryAlertStore) -> None:
        self._store = store

    async def list_for_organization(
        self,
        organization_id: str,
        enabled_only: bool = False,
    ) -> list[_FakeArea]:
        rows = [
            raw
            for raw in self._store.areas.values()
            if raw["organization_id"] == organization_id
        ]
        if enabled_only:
            rows = [raw for raw in rows if raw.get("enabled", True)]
        return [_FakeArea(raw) for raw in rows]


class FakePolicyRepo:
    def __init__(self, store: InMemoryAlertStore) -> None:
        self._store = store

    async def list_for_organization(
        self,
        organization_id: str,
        *,
        enabled_only: bool = False,
    ) -> list[AlertPolicy]:
        rows = [
            raw
            for raw in self._store.policies.values()
            if raw["organization_id"] == organization_id
        ]
        if enabled_only:
            rows = [raw for raw in rows if raw.get("enabled", True)]
        rows.sort(key=lambda raw: raw["created_at"])
        return [AlertPolicy(**raw) for raw in rows]

    async def find_by_id(self, policy_id: str) -> AlertPolicy | None:
        raw = self._store.policies.get(policy_id)
        return AlertPolicy(**raw) if raw else None

    async def find_for_organization(
        self,
        organization_id: str,
        policy_id: str,
    ) -> AlertPolicy | None:
        raw = self._store.policies.get(policy_id)
        if not raw or raw["organization_id"] != organization_id:
            return None
        return AlertPolicy(**raw)

    async def insert(self, policy: AlertPolicy) -> AlertPolicy:
        policy_id = self._store.next_id("policy")
        payload = policy.model_dump()
        payload["id"] = policy_id
        self._store.policies[policy_id] = payload
        return AlertPolicy(**payload)

    async def update(self, policy_id: str, updates: dict) -> bool:
        if policy_id not in self._store.policies:
            return False
        self._store.policies[policy_id].update(updates)
        return True

    async def delete(self, policy_id: str) -> bool:
        return self._store.policies.pop(policy_id, None) is not None


class FakeChannelRepo:
    def __init__(self, store: InMemoryAlertStore) -> None:
        self._store = store

    async def list_for_organization(
        self,
        organization_id: str,
        *,
        enabled_only: bool = False,
    ) -> list[OrganizationNotificationChannel]:
        rows = [
            raw
            for raw in self._store.channels.values()
            if raw["organization_id"] == organization_id
        ]
        if enabled_only:
            rows = [raw for raw in rows if raw.get("enabled", True)]
        rows.sort(key=lambda raw: raw["created_at"])
        return [OrganizationNotificationChannel(**raw) for raw in rows]

    async def list_by_ids(
        self,
        organization_id: str,
        channel_ids: list[str],
    ) -> list[OrganizationNotificationChannel]:
        return [
            OrganizationNotificationChannel(**self._store.channels[channel_id])
            for channel_id in channel_ids
            if channel_id in self._store.channels
            and self._store.channels[channel_id]["organization_id"] == organization_id
        ]

    async def find_for_organization(
        self,
        organization_id: str,
        channel_id: str,
    ) -> OrganizationNotificationChannel | None:
        raw = self._store.channels.get(channel_id)
        if not raw or raw["organization_id"] != organization_id:
            return None
        return OrganizationNotificationChannel(**raw)

    async def insert(
        self,
        channel: OrganizationNotificationChannel,
    ) -> OrganizationNotificationChannel:
        channel_id = self._store.next_id("channel")
        payload = channel.model_dump()
        payload["id"] = channel_id
        self._store.channels[channel_id] = payload
        return OrganizationNotificationChannel(**payload)

    async def update(self, channel_id: str, updates: dict) -> bool:
        if channel_id not in self._store.channels:
            return False
        self._store.channels[channel_id].update(updates)
        return True

    async def delete(self, channel_id: str) -> bool:
        return self._store.channels.pop(channel_id, None) is not None


class FakeDeliveryRepo:
    def __init__(self, store: InMemoryAlertStore) -> None:
        self._store = store

    async def find_by_dedupe_key(self, dedupe_key: str) -> dict | None:
        for row in self._store.deliveries.values():
            if row["dedupe_key"] == dedupe_key:
                return dict(row)
        return None

    async def create(self, record: AlertDeliveryRecord) -> dict:
        record_id = self._store.next_id("delivery")
        payload = record.model_dump()
        payload["id"] = record_id
        self._store.deliveries[record_id] = payload
        return dict(payload)

    async def update(self, record_id: str, updates: dict) -> bool:
        if record_id not in self._store.deliveries:
            return False
        self._store.deliveries[record_id].update(updates)
        return True

    async def list_pending(self, *, limit: int = 100) -> list[dict]:
        rows = [
            row
            for row in self._store.deliveries.values()
            if row["lifecycle"] in DISPATCHABLE_LIFECYCLES
        ]
        rows.sort(key=lambda row: row["created_at"])
        return [dict(row) for row in rows[:limit]]

    async def list_for_organization(
        self,
        organization_id: str,
        *,
        limit: int = 50,
        lifecycle: str | None = None,
        demo_visitor_session_id: str | None = None,
    ) -> list[dict]:
        rows = [
            row
            for row in self._store.deliveries.values()
            if row["organization_id"] == organization_id
            and (lifecycle is None or row["lifecycle"] == lifecycle)
        ]
        rows.sort(key=lambda row: row["created_at"], reverse=True)
        return [dict(row) for row in rows[:limit]]

    async def count_by_lifecycle(self, organization_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self._store.deliveries.values():
            if row["organization_id"] != organization_id:
                continue
            counts[row["lifecycle"]] = counts.get(row["lifecycle"], 0) + 1
        return counts

    async def latest_sent_for_event(
        self,
        *,
        organization_id: str,
        policy_id: str,
        intelligence_event_id: str,
    ) -> dict | None:
        rows = [
            row
            for row in self._store.deliveries.values()
            if row["organization_id"] == organization_id
            and row["policy_id"] == policy_id
            and row["intelligence_event_id"] == intelligence_event_id
            and row["lifecycle"] in _NOTIFIED
        ]
        if not rows:
            return None
        rows.sort(key=lambda row: row.get("sent_at") or row["created_at"], reverse=True)
        return dict(rows[0])

    async def latest_attempt_for_event(
        self,
        *,
        organization_id: str,
        policy_id: str,
        intelligence_event_id: str,
    ) -> dict | None:
        rows = [
            row
            for row in self._store.deliveries.values()
            if row["organization_id"] == organization_id
            and row["policy_id"] == policy_id
            and row["intelligence_event_id"] == intelligence_event_id
        ]
        if not rows:
            return None
        rows.sort(key=lambda row: row["created_at"], reverse=True)
        return dict(rows[0])

    async def within_cooldown(
        self,
        *,
        organization_id: str,
        policy_id: str,
        intelligence_event_id: str,
        monitored_area_ids: list[str] | None = None,
        cooldown_minutes: int,
        now: datetime | None = None,
    ) -> bool:
        if cooldown_minutes <= 0:
            return False
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(minutes=cooldown_minutes)
        areas = set(monitored_area_ids or [])
        for row in self._store.deliveries.values():
            if row["organization_id"] != organization_id or row["policy_id"] != policy_id:
                continue
            if row["created_at"] < cutoff:
                continue
            same_event = row["intelligence_event_id"] == intelligence_event_id
            overlapping_area = bool(areas & set(row.get("monitored_area_ids") or []))
            if same_event or overlapping_area:
                return True
        return False


class FakeIntelRepo:
    def __init__(self, store: InMemoryAlertStore) -> None:
        self._store = store

    async def find_by_id(self, event_id: str) -> dict | None:
        return self._store.events.get(event_id)

    async def find_active(self) -> list[dict]:
        return [e for e in self._store.events.values() if e.get("status") == "active"]


class FakeEntitlementRepo:
    def __init__(self, store: InMemoryAlertStore) -> None:
        self._store = store

    async def list_for_organization(self, organization_id: str):
        return [
            OrganizationEntitlement(**row)
            for row in self._store.entitlements.values()
            if row["organization_id"] == organization_id
        ]

    async def insert(self, row: OrganizationEntitlement):
        ent_id = self._store.next_id("ent")
        payload = row.model_dump()
        payload["id"] = ent_id
        self._store.entitlements[ent_id] = payload
        return OrganizationEntitlement(**payload)

    async def update(self, entitlement_id: str, updates: dict) -> bool:
        for key, row in self._store.entitlements.items():
            if row.get("id") == entitlement_id or key == entitlement_id:
                row.update(updates)
                return True
        return False


@dataclass
class AlertEnvironment:
    store: InMemoryAlertStore
    org_repo: FakeOrgRepo
    area_repo: FakeAreaRepo
    policy_repo: FakePolicyRepo
    channel_repo: FakeChannelRepo
    delivery_repo: FakeDeliveryRepo
    intel_repo: FakeIntelRepo
    entitlement_svc: EntitlementService
    evaluation: CustomerAlertEvaluationService
    dispatcher: CustomerAlertDispatcher
    notification: CustomerAlertNotificationService
    policy_svc: AlertPolicyService
    email: Any
    webhook: Any
    org_ids: dict[str, str] = field(default_factory=dict)
    area_ids: dict[str, str] = field(default_factory=dict)

    async def add_email_channel(
        self,
        org_id: str,
        *,
        name: str = "Operations inbox",
        enabled: bool = True,
        recipients: list[str] | None = None,
    ) -> str:
        channel = await self.channel_repo.insert(
            OrganizationNotificationChannel(
                organization_id=org_id,
                channel_type="email",
                name=name,
                enabled=enabled,
                config={"recipients": recipients or ["ops@example.com"]},
                created_at=NOW,
                updated_at=NOW,
            )
        )
        return str(channel.id)

    async def add_webhook_channel(
        self,
        org_id: str,
        *,
        name: str = "Field webhook",
        enabled: bool = True,
        url: str = "https://example.com/hook",
        secret: str = "shhh",
    ) -> str:
        from app.core.commercial.secret_storage import encrypt_secret

        channel = await self.channel_repo.insert(
            OrganizationNotificationChannel(
                organization_id=org_id,
                channel_type="webhook",
                name=name,
                enabled=enabled,
                config={
                    "url": url,
                    "secret_token_encrypted": encrypt_secret(secret, app_secret=APP_SECRET),
                },
                created_at=NOW,
                updated_at=NOW,
            )
        )
        return str(channel.id)

    async def add_policy(
        self,
        org_id: str,
        *,
        name: str = "Monitored forest disturbance",
        enabled: bool = True,
        area_ids: list[str] | None = None,
        channel_ids: list[str] | None = None,
        minimum_investigation_priority: str = "medium",
        minimum_severity: str = "medium",
        minimum_evidence_state: str | None = None,
        cooldown_minutes: int = 0,
        incident_categories: list[str] | None = None,
        created_at: datetime | None = None,
    ) -> str:
        policy = await self.policy_repo.insert(
            AlertPolicy(
                organization_id=org_id,
                name=name,
                enabled=enabled,
                monitored_area_ids=list(area_ids or []),
                incident_categories=list(incident_categories or ["forest_disturbance"]),
                minimum_investigation_priority=minimum_investigation_priority,
                minimum_severity=minimum_severity,
                minimum_evidence_state=minimum_evidence_state,
                notification_channel_ids=list(channel_ids or []),
                cooldown_minutes=cooldown_minutes,
                created_at=created_at or NOW,
                updated_at=created_at or NOW,
            )
        )
        return str(policy.id)

    def deliveries_for(self, org_id: str) -> list[dict]:
        return [
            row
            for row in self.store.deliveries.values()
            if row["organization_id"] == org_id
        ]


def build_alert_environment(
    *,
    email_sender: Any | None = None,
    webhook_sender: Any | None = None,
    organizations: tuple[tuple[str, str], ...] = (("org-a", "Northern Forestry"),),
    alert_entitlement: bool = True,
) -> AlertEnvironment:
    """Wire the real alerting services against in-memory repositories."""
    store = InMemoryAlertStore()
    org_ids: dict[str, str] = {}
    area_ids: dict[str, str] = {}
    for org_id, org_name in organizations:
        store.add_organization(org_id, org_name)
        store.set_alert_entitlement(org_id, alert_entitlement)
        org_ids[org_id] = org_id
        area_ids[org_id] = store.add_area(org_id, f"{org_name} AOI", polygon_harghita())

    store.events["evt-1"] = make_disturbance_event("evt-1")

    org_repo = FakeOrgRepo(store)
    area_repo = FakeAreaRepo(store)
    policy_repo = FakePolicyRepo(store)
    channel_repo = FakeChannelRepo(store)
    delivery_repo = FakeDeliveryRepo(store)
    intel_repo = FakeIntelRepo(store)
    entitlement_svc = EntitlementService(FakeEntitlementRepo(store), area_repo)
    email = email_sender or FakeEmailSender()
    webhook = webhook_sender or RecordingWebhookSender()

    evaluation = CustomerAlertEvaluationService(
        org_repo=org_repo,
        policy_repo=policy_repo,
        delivery_repo=delivery_repo,
        area_repo=area_repo,
        entitlement_svc=entitlement_svc,
    )
    dispatcher = CustomerAlertDispatcher(
        delivery_repo=delivery_repo,
        policy_repo=policy_repo,
        channel_repo=channel_repo,
        area_repo=area_repo,
        intel_repo=intel_repo,
        email_sender=email,
        webhook_sender=webhook,
        app_secret=APP_SECRET,
    )
    return AlertEnvironment(
        store=store,
        org_repo=org_repo,
        area_repo=area_repo,
        policy_repo=policy_repo,
        channel_repo=channel_repo,
        delivery_repo=delivery_repo,
        intel_repo=intel_repo,
        entitlement_svc=entitlement_svc,
        evaluation=evaluation,
        dispatcher=dispatcher,
        notification=CustomerAlertNotificationService(evaluation, dispatcher),
        policy_svc=AlertPolicyService(
            policy_repo,
            channel_repo,
            delivery_repo,
            entitlement_svc,
            app_secret=APP_SECRET,
            area_repo=area_repo,
        ),
        email=email,
        webhook=webhook,
        org_ids=org_ids,
        area_ids=area_ids,
    )
