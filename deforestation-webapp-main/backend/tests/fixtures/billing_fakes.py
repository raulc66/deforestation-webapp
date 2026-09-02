"""In-memory doubles and payload builders for the billing subsystem.

The fakes mirror the Mongo repositories closely enough to exercise real
commercial behaviour — idempotency, organization isolation, entitlement
synchronization — with no database, no Stripe credentials, and no network.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pymongo.errors import DuplicateKeyError

from app.core.commercial.plan_catalog import PlanCatalog, build_plan_catalog
from app.core.config import Settings
from app.core.organization.organization_context import OrganizationContext
from app.models.billing import BillingCustomer, BillingEvent, OrganizationSubscription
from app.models.forest_monitoring_area import ForestMonitoringArea
from app.models.organization import Organization, OrganizationEntitlement
from app.models.user import UserPublic
from app.services.billing.billing_service import BillingService, BillingUrls
from app.services.billing.entitlement_sync_service import EntitlementSyncService
from app.services.billing.stripe_gateway import FakeStripeGateway
from app.services.billing.stripe_signature import build_signature_header
from app.services.billing.stripe_webhook_service import StripeWebhookService
from app.services.entitlement_service import EntitlementService
from app.services.forest_monitoring_area_service import ForestMonitoringAreaService
from fixtures.customer_alert_fakes import run_async  # noqa: F401 — re-exported helper

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
WEBHOOK_SECRET = "whsec_test_secret"

PRICE_FOUNDATION = "price_test_foundation"
PRICE_PROFESSIONAL = "price_test_professional"
PRICE_ENTERPRISE = "price_test_enterprise"

# Stripe renders webhook payloads with the API version pinned on the webhook
# endpoint, so both shapes are live in the wild and both must be exercised.
LEGACY_SHAPE = "legacy"
BASIL_SHAPE = "basil"
API_SHAPES = (LEGACY_SHAPE, BASIL_SHAPE)


def billing_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "mongo_url": "mongodb://localhost:27017",
        "db_name": "test",
        "jwt_secret": "secret",
        "admin_email": "admin@test.com",
        "admin_password": "pass",
        "frontend_url": "https://app.forestwatch.test",
        "stripe_webhook_secret": WEBHOOK_SECRET,
        "stripe_price_foundation": PRICE_FOUNDATION,
        "stripe_price_professional": PRICE_PROFESSIONAL,
        "plan_foundation_area_limit": 1,
        "plan_professional_area_limit": 5,
        "plan_enterprise_area_limit": 50,
        "plan_foundation_price_label": "EUR 19 / month",
        "plan_professional_price_label": "EUR 149 / month",
    }
    base.update(overrides)
    return Settings(**base)


def test_user(user_id: str = "user-a", email: str = "a@test.com") -> UserPublic:
    return UserPublic(
        id=user_id,
        email=email,
        name="Test User",
        role="user",
        provider="local",
        created_at=NOW,
    )


def romania_polygon(offset: float = 0.0) -> dict:
    lon = 25.5 + offset
    lat = 46.8 + offset
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [lon, lat],
                [lon + 0.5, lat],
                [lon + 0.5, lat + 0.5],
                [lon, lat + 0.5],
                [lon, lat],
            ]
        ],
    }


# --- store ------------------------------------------------------------------


class BillingStore:
    def __init__(self) -> None:
        self.organizations: dict[str, dict] = {}
        self.entitlements: dict[str, dict] = {}
        self.areas: dict[str, dict] = {}
        self.customers: dict[str, dict] = {}
        self.subscriptions: dict[str, dict] = {}
        self.events: dict[str, dict] = {}
        self._seq = 0

    def nid(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}-{self._seq}"


class FakeOrgRepo:
    def __init__(self, store: BillingStore) -> None:
        self._store = store

    async def find_by_id(self, org_id: str) -> Organization | None:
        raw = self._store.organizations.get(org_id)
        return Organization.model_validate(raw) if raw else None


class FakeEntitlementRepo:
    def __init__(self, store: BillingStore) -> None:
        self._store = store

    async def list_for_organization(self, org_id: str, *, active_only: bool = True):
        return [
            OrganizationEntitlement.model_validate(raw)
            for raw in self._store.entitlements.values()
            if raw["organization_id"] == org_id
            and (not active_only or raw["status"] == "active")
        ]

    async def find_by_type(self, org_id: str, entitlement_type: str):
        for raw in self._store.entitlements.values():
            if (
                raw["organization_id"] == org_id
                and raw["entitlement_type"] == entitlement_type
                and raw["status"] == "active"
            ):
                return OrganizationEntitlement.model_validate(raw)
        return None

    async def insert(self, doc: OrganizationEntitlement) -> OrganizationEntitlement:
        eid = self._store.nid("ent")
        payload = doc.model_dump()
        payload["id"] = eid
        self._store.entitlements[eid] = payload
        doc.id = eid
        return doc

    async def update(self, eid: str, updates: dict) -> bool:
        if eid not in self._store.entitlements:
            return False
        self._store.entitlements[eid].update(updates)
        return True


class FakeAreaRepo:
    def __init__(self, store: BillingStore) -> None:
        self._store = store

    async def list_for_organization(
        self,
        org_id: str,
        *,
        enabled_only: bool = False,
        limit: int = 100,
    ):
        rows = [
            ForestMonitoringArea.model_validate(raw)
            for raw in self._store.areas.values()
            if raw.get("organization_id") == org_id
            and (not enabled_only or raw.get("enabled", True))
        ]
        return rows[:limit]

    async def find_for_organization(self, org_id: str, area_id: str):
        raw = self._store.areas.get(area_id)
        if raw is None or raw.get("organization_id") != org_id:
            return None
        return ForestMonitoringArea.model_validate(raw)

    async def insert(self, doc: ForestMonitoringArea) -> ForestMonitoringArea:
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

    async def delete_for_organization(self, org_id: str, area_id: str) -> bool:
        raw = self._store.areas.get(area_id)
        if raw is None or raw.get("organization_id") != org_id:
            return False
        return self._store.areas.pop(area_id, None) is not None


class FakeBillingCustomerRepo:
    def __init__(self, store: BillingStore) -> None:
        self._store = store

    async def insert(self, doc: BillingCustomer) -> BillingCustomer:
        for raw in self._store.customers.values():
            if raw["organization_id"] == doc.organization_id:
                raise DuplicateKeyError("organization_id")
        cid = self._store.nid("bcust")
        payload = doc.model_dump()
        payload["id"] = cid
        self._store.customers[cid] = payload
        doc.id = cid
        return doc

    async def find_by_organization(self, org_id: str) -> BillingCustomer | None:
        for raw in self._store.customers.values():
            if raw["organization_id"] == org_id:
                return BillingCustomer.model_validate(raw)
        return None

    async def find_by_stripe_customer(self, customer_id: str) -> BillingCustomer | None:
        for raw in self._store.customers.values():
            if raw["stripe_customer_id"] == customer_id:
                return BillingCustomer.model_validate(raw)
        return None

    async def update(self, cid: str, updates: dict) -> bool:
        if cid not in self._store.customers:
            return False
        self._store.customers[cid].update(updates)
        return True


class FakeSubscriptionRepo:
    def __init__(self, store: BillingStore) -> None:
        self._store = store

    async def insert(self, doc: OrganizationSubscription) -> OrganizationSubscription:
        for raw in self._store.subscriptions.values():
            if raw["organization_id"] == doc.organization_id:
                raise DuplicateKeyError("organization_id")
        sid = self._store.nid("sub")
        payload = doc.model_dump()
        payload["id"] = sid
        self._store.subscriptions[sid] = payload
        doc.id = sid
        return doc

    async def find_by_organization(self, org_id: str) -> OrganizationSubscription | None:
        for raw in self._store.subscriptions.values():
            if raw["organization_id"] == org_id:
                return OrganizationSubscription.model_validate(raw)
        return None

    async def find_by_stripe_subscription(
        self,
        subscription_id: str,
    ) -> OrganizationSubscription | None:
        for raw in self._store.subscriptions.values():
            if raw.get("stripe_subscription_id") == subscription_id:
                return OrganizationSubscription.model_validate(raw)
        return None

    async def update(self, sid: str, updates: dict) -> bool:
        if sid not in self._store.subscriptions:
            return False
        self._store.subscriptions[sid].update(updates)
        return True


class FakeBillingEventRepo:
    """Mirrors the unique index on ``stripe_event_id``."""

    def __init__(self, store: BillingStore) -> None:
        self._store = store

    async def claim(
        self,
        *,
        stripe_event_id: str,
        event_type: str,
        event_created_at: datetime | None = None,
    ) -> BillingEvent | None:
        for raw in self._store.events.values():
            if raw["stripe_event_id"] != stripe_event_id:
                continue
            # Mirrors the repository: a failed event is retried when Stripe
            # redelivers it, anything else is a duplicate.
            if raw["status"] != "failed":
                return None
            raw["status"] = "received"
            raw["processed_at"] = None
            raw["attempt_count"] = int(raw.get("attempt_count") or 1) + 1
            raw["received_at"] = datetime.now(timezone.utc)
            return BillingEvent.model_validate(raw)
        eid = self._store.nid("bevt")
        event = BillingEvent(
            stripe_event_id=stripe_event_id,
            event_type=event_type,
            event_created_at=event_created_at,
            status="received",
            received_at=datetime.now(timezone.utc),
        )
        payload = event.model_dump()
        payload["id"] = eid
        self._store.events[eid] = payload
        event.id = eid
        return event

    async def find_by_stripe_event_id(self, stripe_event_id: str) -> BillingEvent | None:
        for raw in self._store.events.values():
            if raw["stripe_event_id"] == stripe_event_id:
                return BillingEvent.model_validate(raw)
        return None

    async def mark_outcome(
        self,
        event_id: str,
        *,
        status: str,
        organization_id: str | None = None,
        detail: str | None = None,
    ) -> bool:
        raw = self._store.events.get(event_id)
        if raw is None:
            return False
        raw["status"] = status
        raw["processed_at"] = datetime.now(timezone.utc)
        if organization_id is not None:
            raw["organization_id"] = organization_id
        if detail is not None:
            raw["detail"] = detail
        return True

    def _rows(self, *, organization_id: str | None) -> list[dict]:
        rows = list(self._store.events.values())
        if organization_id is not None:
            rows = [r for r in rows if r.get("organization_id") == organization_id]
        return sorted(rows, key=lambda r: r["received_at"], reverse=True)

    async def latest(self, *, organization_id: str | None = None):
        rows = self._rows(organization_id=organization_id)
        return BillingEvent.model_validate(rows[0]) if rows else None

    async def latest_processed(self, *, organization_id: str | None = None):
        for raw in self._rows(organization_id=organization_id):
            if raw["status"] in {"processed", "ignored"}:
                return BillingEvent.model_validate(raw)
        return None

    async def latest_failure(self, *, organization_id: str | None = None):
        for raw in self._rows(organization_id=organization_id):
            if raw["status"] == "failed":
                return BillingEvent.model_validate(raw)
        return None

    async def count_failed(self, *, organization_id: str | None = None) -> int:
        return sum(
            1
            for raw in self._rows(organization_id=organization_id)
            if raw["status"] == "failed"
        )


# --- environment ------------------------------------------------------------


@dataclass
class BillingEnvironment:
    store: BillingStore
    settings: Settings
    catalog: PlanCatalog
    gateway: Any
    entitlement_svc: EntitlementService
    entitlement_sync: EntitlementSyncService
    billing_svc: BillingService
    webhook_svc: StripeWebhookService
    area_svc: ForestMonitoringAreaService
    customers: FakeBillingCustomerRepo
    subscriptions: FakeSubscriptionRepo
    events: FakeBillingEventRepo
    entitlement_repo: FakeEntitlementRepo
    areas: FakeAreaRepo
    organizations: FakeOrgRepo
    users: dict[str, UserPublic] = field(default_factory=dict)

    def add_organization(
        self,
        name: str = "Forest Co",
        *,
        status: str = "active",
    ) -> str:
        org_id = self.store.nid("org")
        self.store.organizations[org_id] = {
            "id": org_id,
            "name": name,
            "slug": name.lower().replace(" ", "-") + f"-{org_id}",
            "status": status,
            "created_at": NOW,
            "updated_at": NOW,
        }
        return org_id

    def suspend_organization(self, organization_id: str) -> None:
        self.store.organizations[organization_id]["status"] = "suspended"

    def context(
        self,
        organization_id: str,
        *,
        role: str = "owner",
        membership_status: str = "active",
        user: UserPublic | None = None,
    ) -> OrganizationContext:
        org = self.store.organizations[organization_id]
        return OrganizationContext(
            user=user or test_user(),
            organization_id=organization_id,
            organization_name=org["name"],
            organization_slug=org["slug"],
            membership_id=f"mem-{organization_id}-{role}",
            role=role,
            membership_status=membership_status,
        )

    def add_area(
        self,
        organization_id: str,
        *,
        name: str = "Stand",
        enabled: bool = True,
        offset: float = 0.0,
    ) -> str:
        aid = self.store.nid("area")
        self.store.areas[aid] = {
            "id": aid,
            "organization_id": organization_id,
            "tenant_id": organization_id,
            "name": name,
            "geometry": romania_polygon(offset),
            "geometry_type": "Polygon",
            "country": "Romania",
            "enabled": enabled,
            "created_at": NOW,
            "updated_at": NOW,
        }
        return aid


def build_environment(
    *,
    gateway: Any | None = None,
    **setting_overrides: Any,
) -> BillingEnvironment:
    """Wire the billing subsystem over in-memory repositories.

    ``gateway`` lets a test supply the gateway that ``build_stripe_gateway``
    would return for a given deployment configuration, so configuration states
    are exercised through the real factory rather than a hand-made double.
    """
    store = BillingStore()
    settings = billing_settings(**setting_overrides)
    catalog = build_plan_catalog(settings)
    if gateway is None:
        gateway = FakeStripeGateway()

    org_repo = FakeOrgRepo(store)
    entitlement_repo = FakeEntitlementRepo(store)
    area_repo = FakeAreaRepo(store)
    customer_repo = FakeBillingCustomerRepo(store)
    subscription_repo = FakeSubscriptionRepo(store)
    event_repo = FakeBillingEventRepo(store)

    entitlement_svc = EntitlementService(entitlement_repo, area_repo)
    entitlement_sync = EntitlementSyncService(entitlement_repo, catalog)
    billing_svc = BillingService(
        catalog=catalog,
        gateway=gateway,
        customer_repo=customer_repo,
        subscription_repo=subscription_repo,
        event_repo=event_repo,
        entitlement_svc=entitlement_svc,
        urls=BillingUrls.from_settings(settings),
        organization_repo=org_repo,
        billing_live=settings.enable_billing,
    )
    webhook_svc = StripeWebhookService(
        event_repo=event_repo,
        customer_repo=customer_repo,
        subscription_repo=subscription_repo,
        entitlement_sync=entitlement_sync,
        catalog=catalog,
        webhook_secret=settings.stripe_webhook_secret,
        organization_repo=org_repo,
        signature_tolerance_seconds=settings.stripe_webhook_tolerance_seconds,
    )
    area_svc = ForestMonitoringAreaService(area_repo, entitlement_svc=entitlement_svc)
    return BillingEnvironment(
        store=store,
        settings=settings,
        catalog=catalog,
        gateway=gateway,
        entitlement_svc=entitlement_svc,
        entitlement_sync=entitlement_sync,
        billing_svc=billing_svc,
        webhook_svc=webhook_svc,
        area_svc=area_svc,
        customers=customer_repo,
        subscriptions=subscription_repo,
        events=event_repo,
        entitlement_repo=entitlement_repo,
        areas=area_repo,
        organizations=org_repo,
    )


# --- Stripe payload builders ------------------------------------------------


def encode_event(event: dict[str, Any]) -> bytes:
    return json.dumps(event, separators=(",", ":"), sort_keys=True).encode("utf-8")


def signed_headers(
    payload: bytes,
    *,
    secret: str = WEBHOOK_SECRET,
    timestamp: int | None = None,
) -> dict[str, str]:
    stamp = timestamp if timestamp is not None else int(datetime.now(timezone.utc).timestamp())
    return {"Stripe-Signature": build_signature_header(payload, timestamp=stamp, secret=secret)}


def checkout_completed_event(
    *,
    organization_id: str,
    customer_id: str = "cus_test_1",
    subscription_id: str = "sub_test_1",
    plan_key: str = "professional",
    event_id: str = "evt_checkout_1",
    created: int = 1_770_000_000,
    payment_status: str = "paid",
    email: str = "billing@forest.test",
) -> dict[str, Any]:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "created": created,
        "data": {
            "object": {
                "id": "cs_test_1",
                "object": "checkout.session",
                "mode": "subscription",
                "client_reference_id": organization_id,
                "customer": customer_id,
                "subscription": subscription_id,
                "payment_status": payment_status,
                "customer_details": {"email": email},
                "metadata": {
                    "organization_id": organization_id,
                    "plan_key": plan_key,
                },
            }
        },
    }


def subscription_event(
    *,
    event_type: str = "customer.subscription.created",
    organization_id: str | None = None,
    customer_id: str = "cus_test_1",
    subscription_id: str = "sub_test_1",
    price_id: str = PRICE_PROFESSIONAL,
    status: str = "active",
    event_id: str = "evt_sub_1",
    created: int = 1_770_000_100,
    cancel_at_period_end: bool = False,
    current_period_end: int | None = 1_772_600_000,
    trial_end: int | None = None,
    plan_key: str | None = None,
    api_shape: str = LEGACY_SHAPE,
) -> dict[str, Any]:
    """A ``customer.subscription.*`` event in either Stripe API shape.

    ``basil`` (2025-03-31 and later) carries the billing period on each
    subscription item; earlier versions carry it on the subscription itself.
    """
    metadata: dict[str, Any] = {}
    if organization_id:
        metadata["organization_id"] = organization_id
    if plan_key:
        metadata["plan_key"] = plan_key
    item: dict[str, Any] = {"id": "si_test_1", "price": {"id": price_id}}
    subscription: dict[str, Any] = {
        "id": subscription_id,
        "object": "subscription",
        "customer": customer_id,
        "status": status,
        "cancel_at_period_end": cancel_at_period_end,
        "trial_end": trial_end,
        "metadata": metadata,
    }
    if api_shape == BASIL_SHAPE:
        item["current_period_end"] = current_period_end
    else:
        subscription["current_period_end"] = current_period_end
    subscription["items"] = {"data": [item]}
    return {
        "id": event_id,
        "type": event_type,
        "created": created,
        "data": {"object": subscription},
    }


def invoice_event(
    *,
    event_type: str = "invoice.payment_failed",
    customer_id: str = "cus_test_1",
    subscription_id: str = "sub_test_1",
    event_id: str = "evt_inv_1",
    created: int = 1_770_000_200,
    subscription_metadata: dict[str, Any] | None = None,
    api_shape: str = LEGACY_SHAPE,
) -> dict[str, Any]:
    """An ``invoice.*`` event in either Stripe API shape.

    ``basil`` replaced the top-level ``subscription`` reference with
    ``parent.subscription_details``.
    """
    invoice: dict[str, Any] = {
        "id": "in_test_1",
        "object": "invoice",
        "customer": customer_id,
        "metadata": {},
    }
    if api_shape == BASIL_SHAPE:
        invoice["parent"] = {
            "type": "subscription_details",
            "subscription_details": {
                "subscription": subscription_id,
                "metadata": subscription_metadata or {},
            },
        }
        invoice["lines"] = {
            "data": [
                {
                    "id": "il_test_1",
                    "parent": {
                        "type": "subscription_item_details",
                        "subscription_item_details": {
                            "subscription": subscription_id,
                            "subscription_item": "si_test_1",
                        },
                    },
                }
            ]
        }
    else:
        invoice["subscription"] = subscription_id
        if subscription_metadata:
            invoice["subscription_details"] = {"metadata": subscription_metadata}
    return {
        "id": event_id,
        "type": event_type,
        "created": created,
        "data": {"object": invoice},
    }
