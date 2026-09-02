"""How billing behaves in each deployment configuration state.

A ForestWatch deployment can run with billing off, with billing on but
incompletely configured, or with Stripe temporarily unreachable. In every one of
those states the intelligence product must keep working, the stored entitlement
state must stay usable, and no half-finished purchase may be created. These are
the states an operator can actually get wrong, so each is asserted through the
real gateway factory and the real services rather than a hand-made double.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.forest_monitoring_area import ForestMonitoringAreaCreate
from app.services.billing.billing_service import InvalidPlanError
from app.services.billing.stripe_gateway import BillingGatewayError, build_stripe_gateway
from app.services.billing.stripe_signature import build_signature_header
from app.services.billing.stripe_webhook_service import LEDGER_DETAIL_LIMIT
from fixtures.billing_fakes import (
    PRICE_PROFESSIONAL,
    WEBHOOK_SECRET,
    billing_settings,
    build_environment,
    encode_event,
    romania_polygon,
    run_async,
    subscription_event,
)


def _env_for(**settings: object):
    """An environment whose gateway is the one this configuration would select."""
    gateway = build_stripe_gateway(billing_settings(**settings))
    return build_environment(gateway=gateway, **settings)


async def _deliver(env, event: dict):
    payload = encode_event(event)
    stamp = int(datetime.now(timezone.utc).timestamp())
    return await env.webhook_svc.handle(
        payload,
        build_signature_header(payload, timestamp=stamp, secret=WEBHOOK_SECRET),
    )


def _new_area(name: str, offset: float) -> ForestMonitoringAreaCreate:
    return ForestMonitoringAreaCreate(
        name=name,
        geometry=romania_polygon(offset),
        country="Romania",
    )


# --- ENABLE_BILLING=false ----------------------------------------------------


class TestBillingDisabled:
    @run_async
    async def test_status_reports_billing_as_not_configured(self):
        env = _env_for(enable_billing=False)
        org = env.add_organization("Carpathian Forestry")
        status = await env.billing_svc.get_status(env.context(org))
        assert status.synchronization.billing_configured is False

    @run_async
    async def test_the_plan_catalog_is_still_readable(self):
        env = _env_for(enable_billing=False)
        org = env.add_organization("Carpathian Forestry")
        plans = await env.billing_svc.list_plans(env.context(org))
        assert [item["key"] for item in plans["items"]] == [
            "foundation",
            "professional",
            "enterprise",
        ]

    @run_async
    async def test_a_local_checkout_never_reaches_a_stripe_domain(self):
        env = _env_for(enable_billing=False)
        org = env.add_organization("Carpathian Forestry")
        session = await env.billing_svc.create_checkout_session(
            env.context(org), "professional"
        )
        assert session.checkout_url.startswith("https://checkout.stripe.test/")

    @run_async
    async def test_a_local_checkout_grants_nothing_on_its_own(self):
        env = _env_for(enable_billing=False)
        org = env.add_organization("Carpathian Forestry")
        await env.billing_svc.create_checkout_session(env.context(org), "professional")
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 1
        assert profile.alert_delivery_enabled is False
        assert await env.subscriptions.find_by_organization(org) is None

    @run_async
    async def test_the_intelligence_product_does_not_depend_on_stripe(self):
        env = _env_for(enable_billing=False)
        org = env.add_organization("Carpathian Forestry")
        created = await env.area_svc.create_area(
            org, _new_area("First stand", 0.0), actor_role="owner"
        )
        assert created.name == "First stand"
        assert await env.entitlement_svc.can_use_forest_disturbance(org) is True


# --- ENABLE_BILLING=true with no credentials --------------------------------


class TestBillingEnabledWithoutCredentials:
    @run_async
    async def test_checkout_fails_loudly_instead_of_pretending_to_charge(self):
        env = _env_for(enable_billing=True, stripe_secret_key="")
        org = env.add_organization("Carpathian Forestry")
        with pytest.raises(BillingGatewayError) as raised:
            await env.billing_svc.create_checkout_session(
                env.context(org), "professional"
            )
        assert raised.value.status_code == 503

    @run_async
    async def test_no_stripe_customer_is_recorded_for_a_refused_checkout(self):
        env = _env_for(enable_billing=True, stripe_secret_key="")
        org = env.add_organization("Carpathian Forestry")
        with pytest.raises(BillingGatewayError):
            await env.billing_svc.create_checkout_session(
                env.context(org), "professional"
            )
        assert await env.customers.find_by_organization(org) is None

    @run_async
    async def test_the_portal_is_refused_as_well(self):
        env = _env_for(enable_billing=True, stripe_secret_key="")
        org = env.add_organization("Carpathian Forestry")
        with pytest.raises(BillingGatewayError):
            await env.billing_svc.create_portal_session(env.context(org))

    @run_async
    async def test_the_refusal_never_quotes_configuration_secrets(self):
        env = _env_for(enable_billing=True, stripe_secret_key="")
        org = env.add_organization("Carpathian Forestry")
        with pytest.raises(BillingGatewayError) as raised:
            await env.billing_svc.create_checkout_session(
                env.context(org), "professional"
            )
        message = str(raised.value)
        assert WEBHOOK_SECRET not in message
        assert PRICE_PROFESSIONAL not in message

    @run_async
    async def test_entitlements_already_granted_remain_usable(self):
        env = _env_for(enable_billing=True, stripe_secret_key="")
        org = env.add_organization("Carpathian Forestry")
        await env.entitlement_sync.sync_from_plan_key(
            org, plan_key="professional", status="active"
        )
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 5
        assert await env.entitlement_svc.can_receive_alerts(org) is True


# --- ENABLE_BILLING=true with credentials but no prices ---------------------


class TestBillingEnabledWithoutPriceConfiguration:
    @run_async
    async def test_an_unpriced_plan_cannot_be_purchased(self):
        # A live gateway is selected here, so reaching Stripe at all would raise
        # a gateway error instead: the plan check has to come first.
        env = _env_for(
            enable_billing=True,
            stripe_secret_key="sk_test_configuration",
            stripe_price_professional="",
        )
        org = env.add_organization("Carpathian Forestry")
        with pytest.raises(InvalidPlanError) as raised:
            await env.billing_svc.create_checkout_session(
                env.context(org), "professional"
            )
        assert raised.value.status_code == 400

    @run_async
    async def test_an_unpriced_plan_is_advertised_as_not_purchasable(self):
        env = _env_for(
            enable_billing=True,
            stripe_secret_key="sk_test_configuration",
            stripe_price_professional="",
        )
        org = env.add_organization("Carpathian Forestry")
        plans = await env.billing_svc.list_plans(env.context(org))
        professional = next(
            item for item in plans["items"] if item["key"] == "professional"
        )
        assert professional["purchasable"] is False

    @run_async
    async def test_no_stripe_customer_is_created_for_an_unpriced_plan(self):
        env = _env_for(
            enable_billing=True,
            stripe_secret_key="sk_test_configuration",
            stripe_price_professional="",
        )
        org = env.add_organization("Carpathian Forestry")
        with pytest.raises(InvalidPlanError):
            await env.billing_svc.create_checkout_session(
                env.context(org), "professional"
            )
        assert await env.customers.find_by_organization(org) is None


# --- Stripe reachable but failing -------------------------------------------


class TestStripeUnavailable:
    @run_async
    async def test_checkout_surfaces_a_service_unavailable(self):
        env = build_environment()
        org = env.add_organization("Carpathian Forestry")
        env.gateway.fail_next = True
        with pytest.raises(BillingGatewayError):
            await env.billing_svc.create_checkout_session(
                env.context(org), "professional"
            )

    @run_async
    async def test_a_failed_checkout_leaves_no_partial_customer_link(self):
        env = build_environment()
        org = env.add_organization("Carpathian Forestry")
        env.gateway.fail_next = True
        with pytest.raises(BillingGatewayError):
            await env.billing_svc.create_checkout_session(
                env.context(org), "professional"
            )
        assert await env.customers.find_by_organization(org) is None

    @run_async
    async def test_billing_status_stays_readable_while_stripe_is_down(self):
        env = build_environment()
        org = env.add_organization("Carpathian Forestry")
        env.gateway.fail_next = True
        with pytest.raises(BillingGatewayError):
            await env.billing_svc.create_checkout_session(
                env.context(org), "professional"
            )
        status = await env.billing_svc.get_status(env.context(org))
        assert status.entitlements["monitored_area_limit"] == 1

    @run_async
    async def test_a_retry_after_the_outage_succeeds(self):
        env = build_environment()
        org = env.add_organization("Carpathian Forestry")
        env.gateway.fail_next = True
        with pytest.raises(BillingGatewayError):
            await env.billing_svc.create_checkout_session(
                env.context(org), "professional"
            )
        session = await env.billing_svc.create_checkout_session(
            env.context(org), "professional"
        )
        assert session.plan_key == "professional"
        assert len(env.gateway.checkout_sessions) == 1


# --- Webhook failure must not corrupt state ---------------------------------


class TestWebhookFailureIsContained:
    @run_async
    async def test_a_failing_sync_does_not_change_the_stored_plan(self):
        env = build_environment()
        org = env.add_organization("Carpathian Forestry")
        await _deliver(env, subscription_event(organization_id=org))

        async def explode(*_args, **_kwargs):
            raise RuntimeError("entitlement store unavailable")

        env.entitlement_sync.sync = explode
        with pytest.raises(RuntimeError):
            await _deliver(
                env,
                subscription_event(
                    event_type="customer.subscription.updated",
                    organization_id=org,
                    status="canceled",
                    event_id="evt_sync_fails",
                    created=1_770_000_600,
                ),
            )
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 5
        assert profile.source == "plan:professional"

    @run_async
    async def test_the_event_is_retried_on_redelivery(self):
        env = build_environment()
        org = env.add_organization("Carpathian Forestry")
        original = env.entitlement_sync.sync

        async def explode(*_args, **_kwargs):
            raise RuntimeError("entitlement store unavailable")

        env.entitlement_sync.sync = explode
        event = subscription_event(
            organization_id=org,
            status="active",
            event_id="evt_retry_after_failure",
        )
        with pytest.raises(RuntimeError):
            await _deliver(env, event)

        env.entitlement_sync.sync = original
        result = await _deliver(env, event)
        assert result.status == "processed"
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 5

    @run_async
    async def test_the_ledger_records_the_failure_without_copying_the_payload(self):
        env = build_environment()
        org = env.add_organization("Carpathian Forestry")
        leak = "sub_secret_" + "x" * 4000

        async def explode(*_args, **_kwargs):
            raise RuntimeError(f"write rejected for document {leak}")

        env.entitlement_sync.sync = explode
        with pytest.raises(RuntimeError):
            await _deliver(env, subscription_event(organization_id=org))

        recorded = await env.events.latest(organization_id=org)
        assert recorded is not None
        assert recorded.status == "failed"
        assert recorded.detail is not None
        assert len(recorded.detail) <= LEDGER_DETAIL_LIMIT + 3
        assert leak not in recorded.detail

    @run_async
    async def test_a_processed_event_detail_is_bounded_too(self):
        env = build_environment()
        org = env.add_organization("Carpathian Forestry")
        result = await _deliver(env, subscription_event(organization_id=org))
        assert result.status == "processed"
        recorded = await env.events.latest(organization_id=org)
        assert recorded is not None
        assert recorded.detail is None or len(recorded.detail) <= LEDGER_DETAIL_LIMIT + 3
