"""Stripe gateway abstraction.

Everything that talks to Stripe goes through :class:`StripeGateway`. The live
implementation is the production path; the fake implementation gives local
development and the test suite deterministic behaviour with no credentials and
no network access.

The gateway never returns payment instrument data and never accepts a price id
from outside the plan catalog.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.commercial.stripe_api import STRIPE_API_VERSION
from app.core.errors import AppError

logger = logging.getLogger("forestwatch.billing")


class BillingGatewayError(AppError):
    """Stripe was unreachable or rejected the request."""

    status_code = 503
    code = "billing_unavailable"


@dataclass(frozen=True)
class HostedSession:
    """A Stripe-hosted page the customer is redirected to."""

    id: str
    url: str


class StripeGateway(Protocol):
    @property
    def is_configured(self) -> bool:
        ...

    async def create_customer(
        self,
        *,
        organization_id: str,
        organization_name: str,
        email: str | None,
    ) -> str:
        ...

    async def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        organization_id: str,
        plan_key: str,
        success_url: str,
        cancel_url: str,
    ) -> HostedSession:
        ...

    async def create_portal_session(
        self,
        *,
        customer_id: str,
        return_url: str,
    ) -> HostedSession:
        ...


@dataclass
class FakeStripeGateway:
    """Deterministic in-process Stripe stand-in.

    Sequence numbers make every identifier reproducible across runs, which keeps
    billing tests and local demos free of live Stripe state.
    """

    configured: bool = True
    fail_next: bool = False
    customers: list[dict[str, Any]] = field(default_factory=list)
    checkout_sessions: list[dict[str, Any]] = field(default_factory=list)
    portal_sessions: list[dict[str, Any]] = field(default_factory=list)
    _sequence: int = 0

    @property
    def is_configured(self) -> bool:
        return self.configured

    def _next(self, prefix: str) -> str:
        self._sequence += 1
        return f"{prefix}_test_{self._sequence:04d}"

    def _guard(self) -> None:
        if self.fail_next:
            self.fail_next = False
            raise BillingGatewayError("Billing provider is temporarily unavailable")

    async def create_customer(
        self,
        *,
        organization_id: str,
        organization_name: str,
        email: str | None,
    ) -> str:
        self._guard()
        customer_id = self._next("cus")
        self.customers.append(
            {
                "id": customer_id,
                "organization_id": organization_id,
                "name": organization_name,
                "email": email,
            }
        )
        return customer_id

    async def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        organization_id: str,
        plan_key: str,
        success_url: str,
        cancel_url: str,
    ) -> HostedSession:
        self._guard()
        session_id = self._next("cs")
        self.checkout_sessions.append(
            {
                "id": session_id,
                "customer_id": customer_id,
                "price_id": price_id,
                "organization_id": organization_id,
                "plan_key": plan_key,
                "success_url": success_url,
                "cancel_url": cancel_url,
            }
        )
        return HostedSession(
            id=session_id,
            url=f"https://checkout.stripe.test/c/{session_id}",
        )

    async def create_portal_session(
        self,
        *,
        customer_id: str,
        return_url: str,
    ) -> HostedSession:
        self._guard()
        session_id = self._next("bps")
        self.portal_sessions.append(
            {
                "id": session_id,
                "customer_id": customer_id,
                "return_url": return_url,
            }
        )
        return HostedSession(
            id=session_id,
            url=f"https://billing.stripe.test/p/{session_id}",
        )


class LiveStripeGateway:
    """Production Stripe integration.

    The Stripe SDK is imported lazily and its blocking calls are executed off
    the event loop, so an unconfigured or uninstalled Stripe never affects the
    intelligence request path.
    """

    def __init__(self, secret_key: str, *, api_version: str = STRIPE_API_VERSION) -> None:
        self._secret_key = secret_key
        self._api_version = api_version or STRIPE_API_VERSION

    @property
    def is_configured(self) -> bool:
        return bool(self._secret_key)

    def _client(self):
        if not self._secret_key:
            raise BillingGatewayError("Billing is not configured")
        try:
            import stripe  # noqa: PLC0415 — optional dependency, loaded on demand
        except ImportError as exc:  # pragma: no cover - depends on deployment
            raise BillingGatewayError("Stripe client library is unavailable") from exc
        stripe.api_key = self._secret_key
        if self._api_version:
            # Pinning keeps request/response shapes stable when Stripe rolls the
            # account default forward. Webhook payload shapes are pinned
            # separately, on the webhook endpoint itself.
            stripe.api_version = self._api_version
        return stripe

    async def _call(self, fn, *args, **kwargs):
        try:
            return await asyncio.to_thread(fn, *args, **kwargs)
        except BillingGatewayError:
            raise
        except Exception as exc:  # pragma: no cover - exercised against live Stripe
            # Only the exception type is logged: Stripe error payloads can echo
            # request bodies, and nothing from that path belongs in our logs.
            logger.warning("Stripe request failed: %s", type(exc).__name__)
            raise BillingGatewayError("Billing provider request failed") from exc

    async def create_customer(
        self,
        *,
        organization_id: str,
        organization_name: str,
        email: str | None,
    ) -> str:
        stripe = self._client()
        payload: dict[str, Any] = {
            "name": organization_name,
            "metadata": {"organization_id": organization_id},
            # One Stripe customer per organization even if this call is retried
            # after a timeout: without the key a retry bills a second customer.
            "idempotency_key": f"forestwatch-customer-{organization_id}",
        }
        if email:
            payload["email"] = email
        customer = await self._call(lambda: stripe.Customer.create(**payload))
        return str(customer["id"])

    async def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        organization_id: str,
        plan_key: str,
        success_url: str,
        cancel_url: str,
    ) -> HostedSession:
        stripe = self._client()
        metadata = {"organization_id": organization_id, "plan_key": plan_key}
        session = await self._call(
            lambda: stripe.checkout.Session.create(
                mode="subscription",
                customer=customer_id,
                client_reference_id=organization_id,
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata,
                subscription_data={"metadata": metadata},
            )
        )
        url = session.get("url") if isinstance(session, dict) else getattr(session, "url", None)
        session_id = (
            session.get("id") if isinstance(session, dict) else getattr(session, "id", "")
        )
        if not url:
            raise BillingGatewayError("Stripe did not return a checkout URL")
        return HostedSession(id=str(session_id), url=str(url))

    async def create_portal_session(
        self,
        *,
        customer_id: str,
        return_url: str,
    ) -> HostedSession:
        stripe = self._client()
        session = await self._call(
            lambda: stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )
        )
        url = session.get("url") if isinstance(session, dict) else getattr(session, "url", None)
        session_id = (
            session.get("id") if isinstance(session, dict) else getattr(session, "id", "")
        )
        if not url:
            raise BillingGatewayError("Stripe did not return a portal URL")
        return HostedSession(id=str(session_id), url=str(url))


def build_stripe_gateway(settings: Any) -> StripeGateway:
    """Live gateway when Stripe is configured, deterministic fake otherwise."""
    secret_key = str(getattr(settings, "stripe_secret_key", "") or "")
    enabled = bool(getattr(settings, "enable_billing", False))
    if not enabled:
        # Development default: the whole funnel is demonstrable locally and no
        # request can ever reach a real Stripe account.
        return FakeStripeGateway(configured=True)
    if secret_key:
        return LiveStripeGateway(
            secret_key,
            api_version=str(
                getattr(settings, "stripe_api_version", "") or STRIPE_API_VERSION
            ),
        )
    # Billing was switched on without credentials — fail loudly at checkout
    # rather than silently pretending to charge.
    return FakeStripeGateway(configured=False)
