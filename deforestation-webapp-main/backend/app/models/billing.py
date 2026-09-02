"""Billing and subscription domain models.

ForestWatch stores only the billing metadata required to make entitlement
decisions and render customer-facing state. Card data, payment methods, and
payment credentials stay with Stripe and are never persisted here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.base import BaseDocument, utcnow


BillingEventStatus = Literal["received", "processed", "ignored", "failed"]


class BillingCustomer(BaseDocument):
    """Link between a ForestWatch organization and its Stripe customer."""

    organization_id: str
    stripe_customer_id: str
    email: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class OrganizationSubscription(BaseDocument):
    """Current subscription of record for an organization."""

    organization_id: str
    stripe_customer_id: str
    stripe_subscription_id: str | None = None
    stripe_price_id: str | None = None
    plan_key: str
    status: str
    cancel_at_period_end: bool = False
    current_period_end: datetime | None = None
    trial_end: datetime | None = None
    latest_invoice_status: str | None = None
    # Stripe event `created` timestamp of the newest event applied to this row,
    # kept for operators to see when Stripe last said anything about this row.
    last_event_at: datetime | None = None
    last_event_id: str | None = None
    # Ordering is tracked per concern. Subscription lifecycle and invoice events
    # are emitted independently and arrive in any order, so an invoice event must
    # never make a genuinely newer plan change look stale (and vice versa).
    last_lifecycle_event_at: datetime | None = None
    last_invoice_event_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class BillingEvent(BaseDocument):
    """Processed Stripe webhook event — the idempotency ledger.

    A row exists only for events whose signature already verified, so the
    lifecycle an operator can observe is: ``received`` (verified and claimed) →
    ``processed`` | ``ignored`` | ``failed``. Stripe retries a failed delivery,
    and ``attempt_count`` records how many times we have tried it.
    """

    stripe_event_id: str
    event_type: str
    organization_id: str | None = None
    status: BillingEventStatus = "received"
    detail: str | None = None
    event_created_at: datetime | None = None
    received_at: datetime = Field(default_factory=utcnow)
    processed_at: datetime | None = None
    attempt_count: int = 1


class CheckoutRequest(BaseModel):
    plan_key: str = Field(min_length=1, max_length=64)


class CheckoutSessionPublic(BaseModel):
    checkout_url: str
    plan_key: str


class PortalSessionPublic(BaseModel):
    portal_url: str


class SubscriptionPublic(BaseModel):
    """Customer-facing subscription state — no Stripe identifiers."""

    plan_key: str
    plan_name: str
    status: str
    status_label: str
    capability_active: bool
    payment_attention_required: bool
    cancel_at_period_end: bool = False
    current_period_end: datetime | None = None
    trial_end: datetime | None = None


class BillingSynchronizationPublic(BaseModel):
    """Bounded observability for billing synchronization."""

    billing_configured: bool
    last_event_type: str | None = None
    last_event_at: datetime | None = None
    # Outcome of the most recent delivery: received (verified, still in flight),
    # processed, ignored, or failed.
    last_event_status: str | None = None
    last_failure_at: datetime | None = None
    failed_event_count: int = 0
    subscription_synchronized: bool = True


class BillingStatusPublic(BaseModel):
    organization: dict[str, Any]
    plan: dict[str, Any]
    subscription: SubscriptionPublic | None = None
    entitlements: dict[str, Any]
    capacity: dict[str, Any]
    upgrade: dict[str, Any]
    permissions: dict[str, Any]
    synchronization: BillingSynchronizationPublic
