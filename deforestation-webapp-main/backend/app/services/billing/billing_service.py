"""Organization-scoped billing operations and customer-facing billing state.

This service answers "what does this organization have, and how do they change
it". It reads entitlements through ``EntitlementService`` rather than
re-deriving them, and it never accepts a Stripe price id from a caller: the
frontend submits a plan key and the catalog resolves the price.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from pymongo.errors import DuplicateKeyError

from app.core.commercial.plan_catalog import PlanCatalog, SubscriptionPlan
from app.core.commercial.subscription_status import (
    grants_plan_entitlements,
    requires_payment_attention,
    subscription_status_label,
)
from app.core.errors import AppError, ForbiddenError
from app.core.organization.organization_context import OrganizationContext
from app.core.organization.organization_roles import can_manage_billing, can_view_billing
from app.models.billing import (
    BillingCustomer,
    BillingStatusPublic,
    BillingSynchronizationPublic,
    CheckoutSessionPublic,
    OrganizationSubscription,
    PortalSessionPublic,
    SubscriptionPublic,
)
from app.repositories.billing_customer_repository import BillingCustomerRepository
from app.repositories.billing_event_repository import BillingEventRepository
from app.repositories.organization_subscription_repository import (
    OrganizationSubscriptionRepository,
)
from app.services.billing.stripe_gateway import BillingGatewayError, StripeGateway
from app.services.entitlement_service import EntitlementService

logger = logging.getLogger("forestwatch.billing")


class InvalidPlanError(AppError):
    status_code = 400
    code = "invalid_plan"


@dataclass(frozen=True)
class BillingUrls:
    success_url: str
    cancel_url: str
    portal_return_url: str

    @classmethod
    def from_settings(cls, settings: Any) -> "BillingUrls":
        frontend = str(getattr(settings, "frontend_url", "") or "").rstrip("/")
        default_billing = f"{frontend}/billing" if frontend else "/billing"

        def cfg(name: str, fallback: str) -> str:
            value = str(getattr(settings, name, "") or "").strip()
            return value or fallback

        return cls(
            success_url=cfg("billing_success_url", f"{default_billing}?checkout=success"),
            cancel_url=cfg("billing_cancel_url", f"{default_billing}?checkout=canceled"),
            portal_return_url=cfg("billing_portal_return_url", default_billing),
        )


class BillingService:
    def __init__(
        self,
        *,
        catalog: PlanCatalog,
        gateway: StripeGateway,
        customer_repo: BillingCustomerRepository,
        subscription_repo: OrganizationSubscriptionRepository,
        event_repo: BillingEventRepository,
        entitlement_svc: EntitlementService,
        urls: BillingUrls,
        organization_repo: Any | None = None,
        billing_live: bool = False,
    ) -> None:
        self._catalog = catalog
        self._gateway = gateway
        self._customers = customer_repo
        self._subscriptions = subscription_repo
        self._events = event_repo
        self._entitlements = entitlement_svc
        self._urls = urls
        self._orgs = organization_repo
        self._billing_live = billing_live

    # -- read paths --------------------------------------------------------

    async def list_plans(self, ctx: OrganizationContext) -> dict[str, Any]:
        self._require_view(ctx)
        current = await self._current_plan(ctx.organization_id)
        items = []
        for plan in self._catalog.all_plans():
            payload = plan.as_public()
            payload["current"] = plan.key == current.key
            items.append(payload)
        return {
            "items": items,
            "current_plan_key": current.key,
            "can_manage_billing": can_manage_billing(ctx.role),
        }

    async def get_status(self, ctx: OrganizationContext) -> BillingStatusPublic:
        self._require_view(ctx)
        organization_id = ctx.organization_id
        subscription = await self._subscriptions.find_by_organization(organization_id)
        plan = self._effective_plan(subscription)
        profile = await self._entitlements.get_profile(organization_id)
        area_count = await self._entitlements.count_enabled_monitoring_areas(
            organization_id
        )
        limit = profile.monitored_area_limit
        entitlements = profile.as_read_model(monitored_area_count=area_count)
        capacity = {
            "monitored_area_count": area_count,
            "monitored_area_limit": limit,
            "remaining": max(limit - area_count, 0),
            "at_limit": area_count >= limit,
            "over_limit": area_count > limit,
        }
        return BillingStatusPublic(
            organization={
                "id": organization_id,
                "name": ctx.organization_name,
                "slug": ctx.organization_slug,
                "role": ctx.role,
            },
            plan=self._plan_payload(plan, subscription),
            subscription=self._subscription_payload(subscription, plan),
            entitlements=entitlements,
            capacity=capacity,
            upgrade=self._upgrade_payload(
                plan,
                entitlements=entitlements,
                capacity=capacity,
                subscription=subscription,
            ),
            permissions={
                "can_manage_billing": can_manage_billing(ctx.role),
                "can_view_billing": True,
            },
            synchronization=await self._synchronization_payload(
                organization_id,
                subscription=subscription,
            ),
        )

    # -- write paths -------------------------------------------------------

    async def create_checkout_session(
        self,
        ctx: OrganizationContext,
        plan_key: str,
    ) -> CheckoutSessionPublic:
        await self._require_manage(ctx)
        if ctx.is_demo:
            raise ForbiddenError(
                "Create an organization to subscribe — demonstration sessions cannot purchase a plan"
            )
        plan = self._catalog.purchasable(plan_key)
        if plan is None:
            raise InvalidPlanError("Selected plan is not available for purchase")
        if not self._gateway.is_configured:
            raise BillingGatewayError("Billing is not available right now")

        customer = await self._ensure_customer(ctx)
        session = await self._gateway.create_checkout_session(
            customer_id=customer.stripe_customer_id,
            price_id=plan.stripe_price_id,
            organization_id=ctx.organization_id,
            plan_key=plan.key,
            success_url=self._urls.success_url,
            cancel_url=self._urls.cancel_url,
        )
        logger.info(
            "Checkout session created for organization %s on plan %s",
            ctx.organization_id,
            plan.key,
        )
        return CheckoutSessionPublic(checkout_url=session.url, plan_key=plan.key)

    async def create_portal_session(
        self,
        ctx: OrganizationContext,
    ) -> PortalSessionPublic:
        await self._require_manage(ctx)
        if ctx.is_demo:
            raise ForbiddenError(
                "Create an organization to manage a subscription — demonstration sessions have no billing account"
            )
        if not self._gateway.is_configured:
            raise BillingGatewayError("Billing is not available right now")
        customer = await self._customers.find_by_organization(ctx.organization_id)
        if customer is None:
            raise InvalidPlanError(
                "This organization does not have a subscription to manage yet"
            )
        session = await self._gateway.create_portal_session(
            customer_id=customer.stripe_customer_id,
            return_url=self._urls.portal_return_url,
        )
        return PortalSessionPublic(portal_url=session.url)

    # -- internals ---------------------------------------------------------

    def _require_view(self, ctx: OrganizationContext) -> None:
        if not can_view_billing(ctx.role, membership_status=ctx.membership_status):
            raise ForbiddenError("Organization access denied")

    async def _require_manage(self, ctx: OrganizationContext) -> None:
        self._require_view(ctx)
        if not can_manage_billing(ctx.role):
            raise ForbiddenError("Insufficient permissions to manage billing")
        if self._orgs is not None:
            org = await self._orgs.find_by_id(ctx.organization_id)
            if org is None or org.status != "active":
                raise ForbiddenError("Organization is suspended")

    async def _ensure_customer(self, ctx: OrganizationContext) -> BillingCustomer:
        existing = await self._customers.find_by_organization(ctx.organization_id)
        if existing is not None:
            return existing
        customer_id = await self._gateway.create_customer(
            organization_id=ctx.organization_id,
            organization_name=ctx.organization_name,
            email=getattr(ctx.user, "email", None),
        )
        try:
            return await self._customers.insert(
                BillingCustomer(
                    organization_id=ctx.organization_id,
                    stripe_customer_id=customer_id,
                    email=getattr(ctx.user, "email", None),
                )
            )
        except DuplicateKeyError:
            # Two checkouts started at once, or the webhook linked the customer
            # first. The unique index is the arbiter; whoever lost re-reads.
            linked = await self._customers.find_by_organization(ctx.organization_id)
            if linked is None:  # pragma: no cover - index guarantees a row exists
                raise
            return linked

    async def _current_plan(self, organization_id: str) -> SubscriptionPlan:
        subscription = await self._subscriptions.find_by_organization(organization_id)
        return self._effective_plan(subscription)

    def _effective_plan(
        self,
        subscription: OrganizationSubscription | None,
    ) -> SubscriptionPlan:
        """Plan whose capabilities currently apply — not merely the plan bought."""
        if subscription is not None and grants_plan_entitlements(subscription.status):
            plan = self._catalog.get(subscription.plan_key)
            if plan is not None:
                return plan
        return self._catalog.default_plan

    def _plan_payload(
        self,
        plan: SubscriptionPlan,
        subscription: OrganizationSubscription | None,
    ) -> dict[str, Any]:
        payload = plan.as_public()
        payload["current"] = True
        payload["from_subscription"] = bool(
            subscription is not None and grants_plan_entitlements(subscription.status)
        )
        return payload

    def _subscription_payload(
        self,
        subscription: OrganizationSubscription | None,
        plan: SubscriptionPlan,
    ) -> SubscriptionPublic | None:
        if subscription is None:
            return None
        subscribed_plan = self._catalog.get(subscription.plan_key) or plan
        return SubscriptionPublic(
            plan_key=subscribed_plan.key,
            plan_name=subscribed_plan.display_name,
            status=subscription.status,
            status_label=subscription_status_label(subscription.status),
            capability_active=grants_plan_entitlements(subscription.status),
            payment_attention_required=requires_payment_attention(subscription.status),
            cancel_at_period_end=subscription.cancel_at_period_end,
            current_period_end=subscription.current_period_end,
            trial_end=subscription.trial_end,
        )

    def _upgrade_candidate(
        self,
        current: SubscriptionPlan,
        *,
        entitlements: dict[str, Any],
    ) -> SubscriptionPlan | None:
        """Cheapest sellable plan that improves on what is available today."""
        current_limit = int(entitlements.get("monitored_area_limit") or 0)
        for plan in self._catalog.all_plans():
            if plan.key == current.key or not plan.is_checkout_ready:
                continue
            profile = plan.entitlement_profile
            improves_capacity = plan.monitored_area_limit > current_limit
            improves_capability = any(
                bool(profile.get(flag)) and not bool(entitlements.get(flag))
                for flag in (
                    "evidence_correlation_enabled",
                    "live_sources_enabled",
                    "alert_delivery_enabled",
                )
            )
            if improves_capacity or improves_capability:
                return plan
        return None

    def _upgrade_payload(
        self,
        plan: SubscriptionPlan,
        *,
        entitlements: dict[str, Any],
        capacity: dict[str, Any],
        subscription: OrganizationSubscription | None,
    ) -> dict[str, Any]:
        reasons: list[str] = []
        count = capacity["monitored_area_count"]
        limit = capacity["monitored_area_limit"]
        if capacity["over_limit"]:
            reasons.append(
                f"You are monitoring {count} forests on a plan that includes {limit}. "
                "Everything you already monitor stays in place."
            )
        elif capacity["at_limit"]:
            reasons.append(
                f"{count} of {limit} monitored forests in use. "
                "Upgrade to monitor additional forests."
            )
        if not entitlements.get("alert_delivery_enabled"):
            reasons.append(
                "Alert delivery is not included in your current plan. "
                "Upgrade to enable customer alerts."
            )
        if not entitlements.get("live_sources_enabled"):
            reasons.append(
                "Live environmental sources are not included. "
                "Upgrade for live environmental intelligence."
            )
        if not entitlements.get("evidence_correlation_enabled"):
            reasons.append(
                "Cross-source evidence is not included in your current plan."
            )
        candidate = self._upgrade_candidate(plan, entitlements=entitlements)
        payment_attention = subscription is not None and requires_payment_attention(
            subscription.status
        )
        return {
            "recommended": bool(reasons and candidate is not None),
            "recommended_plan_key": candidate.key if candidate else None,
            "recommended_plan_name": candidate.display_name if candidate else None,
            "reasons": reasons,
            "payment_attention_required": payment_attention,
        }

    async def _synchronization_payload(
        self,
        organization_id: str,
        *,
        subscription: OrganizationSubscription | None,
    ) -> BillingSynchronizationPublic:
        # Billing observability must never take the status endpoint down with it.
        last_event = None
        newest = None
        last_failure = None
        failed_count = 0
        try:
            last_event = await self._events.latest_processed(
                organization_id=organization_id
            )
            newest = await self._events.latest(organization_id=organization_id)
            last_failure = await self._events.latest_failure(
                organization_id=organization_id
            )
            failed_count = await self._events.count_failed(
                organization_id=organization_id
            )
        except Exception:  # pragma: no cover - degraded ledger only
            logger.warning("Billing event ledger unavailable for status read")
        synchronized = True
        if subscription is not None:
            profile_plan = self._effective_plan(subscription)
            synchronized = profile_plan.key == (
                subscription.plan_key
                if grants_plan_entitlements(subscription.status)
                else self._catalog.default_plan.key
            )
        return BillingSynchronizationPublic(
            billing_configured=self._billing_live and self._gateway.is_configured,
            last_event_type=last_event.event_type if last_event else None,
            last_event_at=last_event.received_at if last_event else None,
            last_event_status=newest.status if newest else None,
            last_failure_at=last_failure.received_at if last_failure else None,
            failed_event_count=failed_count,
            subscription_synchronized=synchronized,
        )
