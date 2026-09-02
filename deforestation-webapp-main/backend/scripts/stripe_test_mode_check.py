"""Stripe test-mode validation helper.

Two read-only commands that support the manual validation runbook in
``docs/engineering/STRIPE_TEST_MODE_VALIDATION.md``:

    python scripts/stripe_test_mode_check.py verify-config
    python scripts/stripe_test_mode_check.py inspect-org <organization_id>

``verify-config`` asks Stripe whether the configured plan catalog is real: that
each price exists, is active, is recurring, and belongs to the plan we think it
does. ``inspect-org`` prints what the webhook actually did to an organization,
which is how each step of the funnel is confirmed.

Deliberate constraints:

- It refuses to run against a live key. Validation happens in test mode only.
- It never prints a secret, a signing secret, or payment data.
- It lives outside ``tests/`` and is never imported by the suite, so the
  deterministic offline run stays free of Stripe and of network access.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_ROOT / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from app.core.commercial.plan_catalog import build_plan_catalog  # noqa: E402
from app.core.commercial.subscription_status import (  # noqa: E402
    grants_plan_entitlements,
    subscription_status_label,
)
from app.core.config import get_settings  # noqa: E402
from app.repositories.billing_customer_repository import (  # noqa: E402
    BillingCustomerRepository,
)
from app.repositories.billing_event_repository import BillingEventRepository  # noqa: E402
from app.repositories.forest_monitoring_area_repository import (  # noqa: E402
    ForestMonitoringAreaRepository,
)
from app.repositories.organization_entitlement_repository import (  # noqa: E402
    OrganizationEntitlementRepository,
)
from app.repositories.organization_repository import OrganizationRepository  # noqa: E402
from app.repositories.organization_subscription_repository import (  # noqa: E402
    OrganizationSubscriptionRepository,
)
from app.services.entitlement_service import EntitlementService  # noqa: E402

OK = "  ok   "
BAD = " FAIL  "
INFO = " info  "


class ValidationError(RuntimeError):
    pass


def _require_test_mode(settings) -> str:
    secret = str(settings.stripe_secret_key or "")
    if not settings.enable_billing:
        raise ValidationError(
            "ENABLE_BILLING is false. Set it to true in backend/.env with test-mode "
            "keys before validating."
        )
    if not secret:
        raise ValidationError("STRIPE_SECRET_KEY is not set.")
    if not secret.startswith("sk_test_") and not secret.startswith("rk_test_"):
        raise ValidationError(
            "Refusing to run: STRIPE_SECRET_KEY is not a test-mode key. This "
            "helper is for Stripe test mode only."
        )
    if not settings.stripe_webhook_secret:
        raise ValidationError(
            "STRIPE_WEBHOOK_SECRET is not set. Take it from `stripe listen` or "
            "from the webhook endpoint in the Stripe dashboard."
        )
    return secret


def _stripe_client(secret: str, api_version: str):
    try:
        import stripe
    except ImportError as exc:  # pragma: no cover - deployment dependent
        raise ValidationError(
            "The stripe package is not installed. Run: pip install -r requirements.txt"
        ) from exc
    stripe.api_key = secret
    if api_version:
        stripe.api_version = api_version
    return stripe


def verify_config() -> int:
    settings = get_settings()
    secret = _require_test_mode(settings)
    stripe = _stripe_client(secret, settings.stripe_api_version)
    catalog = build_plan_catalog(settings)

    print("Stripe test-mode configuration")
    print(f"{INFO} api version: {settings.stripe_api_version or 'account default'}")
    print(f"{INFO} success url: {settings.billing_success_url or '(derived)'}")
    print(f"{INFO} cancel url:  {settings.billing_cancel_url or '(derived)'}")
    print(f"{INFO} portal url:  {settings.billing_portal_return_url or '(derived)'}")
    print()

    failures = 0
    for plan in catalog.all_plans():
        label = f"{plan.display_name:<13}"
        if not plan.stripe_price_id:
            state = OK if not plan.purchasable else BAD
            if plan.purchasable:
                failures += 1
            print(
                f"{state} {label} no price configured — "
                f"{'contact sales, not purchasable' if not plan.purchasable else 'purchasable but unsellable'}"
            )
            continue
        try:
            price = stripe.Price.retrieve(plan.stripe_price_id, expand=["product"])
        except Exception as exc:
            failures += 1
            print(f"{BAD} {label} price not retrievable ({type(exc).__name__})")
            continue

        problems = []
        if not price.get("active"):
            problems.append("price is archived")
        recurring = price.get("recurring") or {}
        if not recurring:
            problems.append("price is one-off, not a subscription price")
        if price.get("livemode"):
            problems.append("price belongs to live mode")
        product = price.get("product")
        product_name = (
            product.get("name") if isinstance(product, dict) else str(product or "")
        )
        interval = recurring.get("interval", "?")
        amount = price.get("unit_amount")
        currency = str(price.get("currency", "")).upper()
        money = f"{amount / 100:.2f} {currency}" if amount is not None else "metered"
        summary = f"{money} / {interval} — {product_name}"
        if problems:
            failures += 1
            print(f"{BAD} {label} {summary} :: {'; '.join(problems)}")
        else:
            print(f"{OK} {label} {summary}")
            print(
                f"        grants {plan.monitored_area_limit} monitored areas; "
                f"{', '.join(plan.capability_highlights()) or 'no extra capabilities'}"
            )

    print()
    if failures:
        print(f"{BAD} {failures} plan(s) are not usable. Fix these before selling.")
        return 1
    print(f"{OK} plan catalog matches Stripe test mode.")
    return 0


async def _inspect(organization_id: str) -> int:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongo_url)
    db = client[settings.db_name]
    try:
        org = await OrganizationRepository(db).find_by_id(organization_id)
        if org is None:
            print(f"{BAD} no organization {organization_id}")
            return 1
        entitlement_svc = EntitlementService(
            OrganizationEntitlementRepository(db),
            ForestMonitoringAreaRepository(db),
        )
        subscription = await OrganizationSubscriptionRepository(db).find_by_organization(
            organization_id
        )
        customer = await BillingCustomerRepository(db).find_by_organization(
            organization_id
        )
        profile = await entitlement_svc.get_profile(organization_id)
        area_count = await entitlement_svc.count_enabled_monitoring_areas(
            organization_id
        )
        events = await BillingEventRepository(db).find_many(
            {"organization_id": organization_id},
            limit=10,
            sort=[("received_at", -1)],
        )

        print(f"Organization  {org.name} ({org.status})")
        print(f"Billing link  {'yes' if customer else 'none yet'}")
        if subscription is None:
            print("Subscription  none — organization is on foundation defaults")
        else:
            print(
                f"Subscription  {subscription.plan_key} / "
                f"{subscription_status_label(subscription.status)} "
                f"({subscription.status})"
            )
            print(
                f"              capability active: "
                f"{grants_plan_entitlements(subscription.status)}; "
                f"cancel at period end: {subscription.cancel_at_period_end}"
            )
            print(
                f"              period end: {subscription.current_period_end}; "
                f"last invoice: {subscription.latest_invoice_status}"
            )
            print(
                f"              lifecycle clock: {subscription.last_lifecycle_event_at}; "
                f"invoice clock: {subscription.last_invoice_event_at}"
            )
        print(
            f"Capacity      {area_count} / {profile.monitored_area_limit} monitored areas"
            f"{'  OVER LIMIT' if area_count > profile.monitored_area_limit else ''}"
        )
        print(
            "Capabilities  "
            f"disturbance={profile.forest_disturbance_enabled} "
            f"evidence={profile.evidence_correlation_enabled} "
            f"live_sources={profile.live_sources_enabled} "
            f"alerts={profile.alert_delivery_enabled}"
        )
        print("Recent events")
        if not events:
            print("              none recorded for this organization")
        for event in events:
            print(
                f"              {event.received_at:%Y-%m-%d %H:%M:%S} "
                f"{event.event_type:<34} {event.status:<9} "
                f"attempt {event.attempt_count}"
            )
        return 0
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify-config", help="check the plan catalog against Stripe")
    inspect = sub.add_parser("inspect-org", help="print local billing state")
    inspect.add_argument("organization_id")
    args = parser.parse_args()

    try:
        if args.command == "verify-config":
            return verify_config()
        return asyncio.run(_inspect(args.organization_id))
    except ValidationError as exc:
        print(f"{BAD} {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
