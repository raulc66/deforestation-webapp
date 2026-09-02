"""Stripe webhook processing.

Pipeline for every delivery:

    verified signature
    -> idempotent claim on the Stripe event id
    -> subscription state persisted from Stripe (the authority)
    -> plan resolved from the Stripe price via the plan catalog
    -> entitlements synchronized

Client-supplied subscription state is never trusted, the same Stripe event is
never applied twice, and an event older than the state already stored is
recorded but not applied.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.commercial.plan_catalog import PlanCatalog, SubscriptionPlan
from app.core.commercial.subscription_status import (
    SubscriptionStatus,
    is_known_status,
)
from app.core.errors import AppError
from app.models.billing import BillingCustomer, OrganizationSubscription
from app.repositories.billing_customer_repository import BillingCustomerRepository
from app.repositories.billing_event_repository import BillingEventRepository
from app.repositories.organization_subscription_repository import (
    OrganizationSubscriptionRepository,
)
from app.services.billing.entitlement_sync_service import EntitlementSyncService
from app.services.billing.stripe_payloads import (
    as_dict,
    epoch_to_datetime,
    invoice_metadata,
    invoice_subscription_id,
    stripe_id,
    subscription_period_end,
    subscription_price_id,
)
from app.services.billing.stripe_signature import (
    WebhookVerificationError,
    verify_webhook_signature,
)

logger = logging.getLogger("forestwatch.billing")


SUPPORTED_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "checkout.session.completed",
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
        "customer.subscription.paused",
        "customer.subscription.resumed",
        "invoice.paid",
        "invoice.payment_failed",
    }
)

# Stripe emits subscription lifecycle and invoice events independently and
# guarantees no ordering between them, so each concern keeps its own clock.
LIFECYCLE_CLOCK = "last_lifecycle_event_at"
INVOICE_CLOCK = "last_invoice_event_at"

# Staleness is deliberately asymmetric, because the two concerns do not carry
# equal authority. A subscription event *is* Stripe's own state, so it only has
# to be newer than the last subscription event: a later invoice must never make
# a real plan change look stale. An invoice event only *infers* a status, so it
# has to be newer than everything already applied — otherwise a late-delivered
# failed payment could drag an already-recovered subscription back to past_due.
LIFECYCLE_GUARD = (LIFECYCLE_CLOCK,)
INVOICE_GUARD = (LIFECYCLE_CLOCK, INVOICE_CLOCK)

# The ledger records what happened to an event, not the event. Driver and
# validation errors can quote the document that failed, so an unbounded message
# would turn the ledger into an accidental copy of Stripe payloads.
LEDGER_DETAIL_LIMIT = 200


def _ledger_detail(value: Any) -> str:
    collapsed = " ".join(str(value).split())
    if len(collapsed) <= LEDGER_DETAIL_LIMIT:
        return collapsed
    return collapsed[:LEDGER_DETAIL_LIMIT] + "..."


class WebhookPayloadError(AppError):
    status_code = 400
    code = "invalid_webhook_payload"


class WebhookSignatureError(AppError):
    status_code = 400
    code = "invalid_webhook_signature"


@dataclass
class _Attribution:
    """Organization an in-flight event belongs to.

    Carried alongside the handlers so that a delivery which fails part-way is
    still recorded against its organization: an unattributed failure would be
    invisible on that organization's billing status, which is precisely when
    someone needs to see it.
    """

    organization_id: str | None = None


@dataclass(frozen=True)
class WebhookResult:
    received: bool
    status: str
    event_type: str | None = None
    event_id: str | None = None
    organization_id: str | None = None
    plan_key: str | None = None
    subscription_status: str | None = None
    detail: str | None = None


class StripeWebhookService:
    def __init__(
        self,
        *,
        event_repo: BillingEventRepository,
        customer_repo: BillingCustomerRepository,
        subscription_repo: OrganizationSubscriptionRepository,
        entitlement_sync: EntitlementSyncService,
        catalog: PlanCatalog,
        webhook_secret: str,
        organization_repo: Any | None = None,
        signature_tolerance_seconds: int = 300,
    ) -> None:
        self._events = event_repo
        self._customers = customer_repo
        self._subscriptions = subscription_repo
        self._sync = entitlement_sync
        self._catalog = catalog
        self._secret = webhook_secret
        self._orgs = organization_repo
        self._tolerance = signature_tolerance_seconds

    # -- entry point -------------------------------------------------------

    async def handle(
        self,
        payload: bytes,
        signature_header: str | None,
        *,
        now: datetime | None = None,
    ) -> WebhookResult:
        try:
            verify_webhook_signature(
                payload,
                signature_header,
                self._secret,
                tolerance_seconds=self._tolerance,
                now=now,
            )
        except WebhookVerificationError as exc:
            logger.warning("Rejected Stripe webhook: %s", exc)
            raise WebhookSignatureError(str(exc)) from exc

        event = self._parse_event(payload)
        event_id = str(event.get("id") or "")
        event_type = str(event.get("type") or "")
        if not event_id or not event_type:
            raise WebhookPayloadError("Webhook payload is missing an event id or type")
        event_created = epoch_to_datetime(event.get("created"))

        if event_type not in SUPPORTED_EVENT_TYPES:
            return WebhookResult(
                received=True,
                status="ignored",
                event_type=event_type,
                event_id=event_id,
                detail="Event type is not handled",
            )

        claim = await self._events.claim(
            stripe_event_id=event_id,
            event_type=event_type,
            event_created_at=event_created,
        )
        if claim is None:
            logger.info("Stripe event %s already processed", event_id)
            return WebhookResult(
                received=True,
                status="duplicate",
                event_type=event_type,
                event_id=event_id,
                detail="Event already processed",
            )

        attribution = _Attribution()
        try:
            result = await self._apply(
                event_type=event_type,
                event_id=event_id,
                event_created=event_created,
                data_object=as_dict(as_dict(event.get("data")).get("object")),
                attribution=attribution,
            )
        except Exception as exc:
            # Failures stay observable through the ledger; the intelligence
            # system is unaffected either way.
            await self._events.mark_outcome(
                str(claim.id),
                status="failed",
                organization_id=attribution.organization_id,
                detail=_ledger_detail(f"{type(exc).__name__}: {exc}"),
            )
            logger.exception("Stripe event %s processing failed", event_id)
            raise

        await self._events.mark_outcome(
            str(claim.id),
            status=result.status if result.status in {"processed", "ignored"} else "processed",
            organization_id=result.organization_id,
            detail=_ledger_detail(result.detail) if result.detail else None,
        )
        return result

    def _parse_event(self, payload: bytes) -> dict[str, Any]:
        try:
            parsed = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WebhookPayloadError("Webhook payload is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise WebhookPayloadError("Webhook payload is not a Stripe event")
        return parsed

    # -- event handling ----------------------------------------------------

    async def _apply(
        self,
        *,
        event_type: str,
        event_id: str,
        event_created: datetime | None,
        data_object: dict[str, Any],
        attribution: _Attribution,
    ) -> WebhookResult:
        if event_type == "checkout.session.completed":
            return await self._handle_checkout_completed(
                data_object,
                event_type=event_type,
                event_id=event_id,
                event_created=event_created,
                attribution=attribution,
            )
        if event_type.startswith("customer.subscription."):
            return await self._handle_subscription_event(
                data_object,
                event_type=event_type,
                event_id=event_id,
                event_created=event_created,
                attribution=attribution,
            )
        return await self._handle_invoice_event(
            data_object,
            event_type=event_type,
            event_id=event_id,
            event_created=event_created,
            attribution=attribution,
        )

    async def _handle_checkout_completed(
        self,
        session: dict[str, Any],
        *,
        event_type: str,
        event_id: str,
        event_created: datetime | None,
        attribution: _Attribution,
    ) -> WebhookResult:
        metadata = as_dict(session.get("metadata"))
        organization_id = str(
            session.get("client_reference_id") or metadata.get("organization_id") or ""
        )
        customer_id = stripe_id(session.get("customer"))
        if not organization_id or not customer_id:
            return WebhookResult(
                received=True,
                status="ignored",
                event_type=event_type,
                event_id=event_id,
                detail="Checkout session is not linked to an organization",
            )
        if not await self._organization_exists(organization_id):
            return WebhookResult(
                received=True,
                status="ignored",
                event_type=event_type,
                event_id=event_id,
                detail="Unknown organization",
            )
        attribution.organization_id = organization_id

        await self._link_customer(
            organization_id=organization_id,
            customer_id=customer_id,
            email=str(as_dict(session.get("customer_details")).get("email") or "") or None,
        )

        subscription_id = stripe_id(session.get("subscription"))
        plan = self._catalog.get(metadata.get("plan_key"))
        # A completed subscription checkout with a settled payment is treated as
        # active so the funnel works even if the subscription events are delayed;
        # any later subscription event overwrites this with Stripe's own state.
        paid = str(session.get("payment_status") or "") in {"paid", "no_payment_required"}
        status = (
            SubscriptionStatus.ACTIVE.value if paid else SubscriptionStatus.INCOMPLETE.value
        )
        return await self._persist_subscription(
            organization_id=organization_id,
            customer_id=customer_id,
            subscription_id=subscription_id,
            price_id=plan.stripe_price_id if plan else None,
            plan=plan,
            status=status,
            cancel_at_period_end=False,
            current_period_end=None,
            trial_end=None,
            event_type=event_type,
            event_id=event_id,
            event_created=event_created,
            clock=LIFECYCLE_CLOCK,
        )

    async def _handle_subscription_event(
        self,
        subscription: dict[str, Any],
        *,
        event_type: str,
        event_id: str,
        event_created: datetime | None,
        attribution: _Attribution,
    ) -> WebhookResult:
        customer_id = stripe_id(subscription.get("customer"))
        subscription_id = stripe_id(subscription.get("id"))
        organization_id = await self._resolve_organization(
            metadata=as_dict(subscription.get("metadata")),
            customer_id=customer_id,
            subscription_id=subscription_id,
        )
        if not organization_id:
            return WebhookResult(
                received=True,
                status="ignored",
                event_type=event_type,
                event_id=event_id,
                detail="Subscription is not linked to a known organization",
            )
        attribution.organization_id = organization_id

        price_id = subscription_price_id(subscription)
        # A price we do not sell never grants a plan. Metadata is only a fallback
        # when Stripe has not yet attached items (early checkout completion).
        plan = self._catalog.find_by_price_id(price_id)
        if plan is None and not price_id:
            plan = self._catalog.get(
                as_dict(subscription.get("metadata")).get("plan_key")
            )
        raw_status = str(subscription.get("status") or "")
        if event_type == "customer.subscription.deleted":
            status = SubscriptionStatus.CANCELED.value
        elif event_type == "customer.subscription.paused":
            status = SubscriptionStatus.PAUSED.value
        elif is_known_status(raw_status):
            status = raw_status
        else:
            return WebhookResult(
                received=True,
                status="ignored",
                event_type=event_type,
                event_id=event_id,
                organization_id=organization_id,
                detail=f"Unsupported subscription status '{raw_status}'",
            )

        return await self._persist_subscription(
            organization_id=organization_id,
            customer_id=customer_id,
            subscription_id=subscription_id,
            price_id=price_id,
            plan=plan,
            status=status,
            cancel_at_period_end=bool(subscription.get("cancel_at_period_end")),
            current_period_end=subscription_period_end(subscription),
            trial_end=epoch_to_datetime(subscription.get("trial_end")),
            event_type=event_type,
            event_id=event_id,
            event_created=event_created,
            clock=LIFECYCLE_CLOCK,
        )

    async def _handle_invoice_event(
        self,
        invoice: dict[str, Any],
        *,
        event_type: str,
        event_id: str,
        event_created: datetime | None,
        attribution: _Attribution,
    ) -> WebhookResult:
        customer_id = stripe_id(invoice.get("customer"))
        subscription_id = invoice_subscription_id(invoice)
        organization_id = await self._resolve_organization(
            metadata=invoice_metadata(invoice),
            customer_id=customer_id,
            subscription_id=subscription_id,
        )
        if not organization_id:
            return WebhookResult(
                received=True,
                status="ignored",
                event_type=event_type,
                event_id=event_id,
                detail="Invoice is not linked to a known organization",
            )
        attribution.organization_id = organization_id

        existing = await self._subscriptions.find_by_organization(organization_id)
        if existing is None:
            return WebhookResult(
                received=True,
                status="ignored",
                event_type=event_type,
                event_id=event_id,
                organization_id=organization_id,
                detail="No subscription of record for this invoice",
            )
        if self._is_stale(existing, event_created, guard=INVOICE_GUARD):
            return self._stale_result(event_type, event_id, organization_id, existing)

        paid = event_type == "invoice.paid"
        # A recovered payment restores active billing; a failed charge moves an
        # otherwise-good subscription into the past-due grace state. Stripe's own
        # subscription events remain authoritative for anything beyond that.
        if paid:
            status = (
                SubscriptionStatus.ACTIVE.value
                if existing.status
                in {
                    SubscriptionStatus.PAST_DUE.value,
                    SubscriptionStatus.UNPAID.value,
                    SubscriptionStatus.INCOMPLETE.value,
                }
                else existing.status
            )
        elif existing.status in {
            SubscriptionStatus.ACTIVE.value,
            SubscriptionStatus.TRIALING.value,
        }:
            status = SubscriptionStatus.PAST_DUE.value
        else:
            status = existing.status

        return await self._persist_subscription(
            organization_id=organization_id,
            customer_id=customer_id or existing.stripe_customer_id,
            subscription_id=subscription_id or existing.stripe_subscription_id,
            price_id=existing.stripe_price_id,
            plan=self._catalog.get(existing.plan_key),
            status=status,
            cancel_at_period_end=existing.cancel_at_period_end,
            current_period_end=existing.current_period_end,
            trial_end=existing.trial_end,
            latest_invoice_status="paid" if paid else "payment_failed",
            event_type=event_type,
            event_id=event_id,
            event_created=event_created,
            clock=INVOICE_CLOCK,
        )

    # -- persistence -------------------------------------------------------

    async def _persist_subscription(
        self,
        *,
        organization_id: str,
        customer_id: str | None,
        subscription_id: str | None,
        price_id: str | None,
        plan: SubscriptionPlan | None,
        status: str,
        cancel_at_period_end: bool,
        current_period_end: datetime | None,
        trial_end: datetime | None,
        event_type: str,
        event_id: str,
        event_created: datetime | None,
        clock: str,
        latest_invoice_status: str | None = None,
    ) -> WebhookResult:
        existing = await self._subscriptions.find_by_organization(organization_id)
        guard = INVOICE_GUARD if clock == INVOICE_CLOCK else LIFECYCLE_GUARD
        if existing is not None and self._is_stale(existing, event_created, guard=guard):
            return self._stale_result(event_type, event_id, organization_id, existing)

        resolved_plan = plan or (
            self._catalog.get(existing.plan_key) if existing else None
        )
        plan_key = resolved_plan.key if resolved_plan else self._catalog.default_plan.key
        now = datetime.now(timezone.utc)
        payload = {
            "organization_id": organization_id,
            "stripe_customer_id": customer_id
            or (existing.stripe_customer_id if existing else ""),
            "stripe_subscription_id": subscription_id
            or (existing.stripe_subscription_id if existing else None),
            "stripe_price_id": price_id or (existing.stripe_price_id if existing else None),
            "plan_key": plan_key,
            "status": status,
            "cancel_at_period_end": bool(cancel_at_period_end),
            "current_period_end": current_period_end,
            "trial_end": trial_end,
            "latest_invoice_status": latest_invoice_status
            or (existing.latest_invoice_status if existing else None),
            # An undated event is applied but must not erase the watermark it was
            # never compared against, or the next genuinely stale event would be
            # free to revert this state.
            "last_event_at": event_created or (existing.last_event_at if existing else None),
            "last_event_id": event_id,
            # Only this event's own concern advances, so the two orderings stay
            # independent of each other.
            clock: event_created or (getattr(existing, clock, None) if existing else None),
            "updated_at": now,
        }
        if existing is None:
            await self._subscriptions.insert(
                OrganizationSubscription(created_at=now, **payload)
            )
        else:
            await self._subscriptions.update(str(existing.id), payload)

        sync = await self._sync.sync(
            organization_id,
            plan=resolved_plan,
            status=status,
        )
        return WebhookResult(
            received=True,
            status="processed",
            event_type=event_type,
            event_id=event_id,
            organization_id=organization_id,
            plan_key=sync.plan_key,
            subscription_status=status,
            detail=f"Subscription {status}",
        )

    async def _link_customer(
        self,
        *,
        organization_id: str,
        customer_id: str,
        email: str | None,
    ) -> None:
        now = datetime.now(timezone.utc)
        existing = await self._customers.find_by_organization(organization_id)
        if existing is None:
            await self._customers.insert(
                BillingCustomer(
                    organization_id=organization_id,
                    stripe_customer_id=customer_id,
                    email=email,
                    created_at=now,
                    updated_at=now,
                )
            )
            return
        updates: dict[str, Any] = {"updated_at": now}
        if existing.stripe_customer_id != customer_id:
            updates["stripe_customer_id"] = customer_id
        if email and existing.email != email:
            updates["email"] = email
        await self._customers.update(str(existing.id), updates)

    # -- helpers -----------------------------------------------------------

    def _is_stale(
        self,
        existing: OrganizationSubscription,
        event_created: datetime | None,
        *,
        guard: tuple[str, ...],
    ) -> bool:
        """Is this event older than the state it would overwrite?

        Stripe stamps ``created`` to the second and several events of one
        transaction routinely share a second, so only a strictly older event is
        stale — otherwise the second half of a same-second pair would be dropped.
        """
        if event_created is None:
            return False
        newest: datetime | None = None
        for clock in guard:
            stored = getattr(existing, clock, None)
            if stored is None:
                continue
            if stored.tzinfo is None:
                stored = stored.replace(tzinfo=timezone.utc)
            if newest is None or stored > newest:
                newest = stored
        if newest is None:
            return False
        return event_created < newest

    def _stale_result(
        self,
        event_type: str,
        event_id: str,
        organization_id: str,
        existing: OrganizationSubscription,
    ) -> WebhookResult:
        logger.info(
            "Skipped out-of-order Stripe event %s for organization %s",
            event_id,
            organization_id,
        )
        return WebhookResult(
            received=True,
            status="ignored",
            event_type=event_type,
            event_id=event_id,
            organization_id=organization_id,
            plan_key=existing.plan_key,
            subscription_status=existing.status,
            detail="Event is older than the stored subscription state",
        )

    async def _organization_exists(self, organization_id: str) -> bool:
        if self._orgs is None:
            return True
        try:
            return await self._orgs.find_by_id(organization_id) is not None
        except Exception:  # pragma: no cover - malformed identifiers
            return False

    async def _resolve_organization(
        self,
        *,
        metadata: dict[str, Any],
        customer_id: str | None,
        subscription_id: str | None,
    ) -> str | None:
        """Resolve the owning organization from Stripe-side references only."""
        candidate = str(metadata.get("organization_id") or "")
        if candidate and await self._organization_exists(candidate):
            return candidate
        if customer_id:
            customer = await self._customers.find_by_stripe_customer(customer_id)
            if customer is not None:
                return customer.organization_id
        if subscription_id:
            subscription = await self._subscriptions.find_by_stripe_subscription(
                subscription_id
            )
            if subscription is not None:
                return subscription.organization_id
        return None
