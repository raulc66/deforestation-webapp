"""Behaviour against the payload shapes real Stripe accounts actually send.

Stripe renders webhook payloads with the API version pinned on the webhook
endpoint, so a deployment can receive either the pre-2025-03-31 shape or the
"basil" shape. Two fields ForestWatch depends on moved in basil, and the whole
purchase funnel is driven by them, so both shapes are exercised end to end here
through the real HTTP webhook route.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.billing_routes import router as billing_router
from app.api.deps import stripe_webhook_service_dep
from app.models.billing import BillingCustomer
from app.services.billing.stripe_gateway import (
    FakeStripeGateway,
    LiveStripeGateway,
    build_stripe_gateway,
)
from app.services.billing.stripe_payloads import (
    invoice_metadata,
    invoice_subscription_id,
    subscription_period_end,
    subscription_price_id,
)
from app.services.billing.stripe_signature import build_signature_header
from fixtures.billing_fakes import (
    API_SHAPES,
    BASIL_SHAPE,
    LEGACY_SHAPE,
    PRICE_ENTERPRISE,
    PRICE_FOUNDATION,
    PRICE_PROFESSIONAL,
    WEBHOOK_SECRET,
    billing_settings,
    build_environment,
    checkout_completed_event,
    encode_event,
    invoice_event,
    run_async,
    subscription_event,
)

PERIOD_END_EPOCH = 1_772_600_000
PERIOD_END = datetime.fromtimestamp(PERIOD_END_EPOCH, tz=timezone.utc)


@pytest.fixture
def env():
    return build_environment()


@pytest.fixture
def org(env):
    return env.add_organization("Carpathian Forestry")


def _webhook_client(env):
    """Drives the real route, so nothing here bypasses signature verification."""
    app = FastAPI()
    app.include_router(billing_router)
    app.dependency_overrides[stripe_webhook_service_dep] = lambda: env.webhook_svc
    return TestClient(app)


def _post(client, event: dict, *, secret: str = WEBHOOK_SECRET):
    payload = encode_event(event)
    stamp = int(datetime.now(timezone.utc).timestamp())
    return client.post(
        "/billing/webhook/stripe",
        content=payload,
        headers={
            "Stripe-Signature": build_signature_header(
                payload, timestamp=stamp, secret=secret
            ),
            "Content-Type": "application/json",
        },
    )


async def _deliver(env, event: dict):
    payload = encode_event(event)
    stamp = int(datetime.now(timezone.utc).timestamp())
    return await env.webhook_svc.handle(
        payload,
        build_signature_header(payload, timestamp=stamp, secret=WEBHOOK_SECRET),
    )


# --- payload readers ---------------------------------------------------------


class TestSubscriptionPeriodReader:
    def test_basil_reads_the_period_from_the_subscription_item(self):
        event = subscription_event(api_shape=BASIL_SHAPE)
        subscription = event["data"]["object"]
        assert "current_period_end" not in subscription
        assert subscription_period_end(subscription) == PERIOD_END

    def test_legacy_reads_the_period_from_the_subscription(self):
        subscription = subscription_event(api_shape=LEGACY_SHAPE)["data"]["object"]
        assert subscription_period_end(subscription) == PERIOD_END

    def test_the_latest_item_period_wins(self):
        subscription = {
            "items": {
                "data": [
                    {"current_period_end": 1_772_000_000},
                    {"current_period_end": 1_775_000_000},
                ]
            }
        }
        expected = datetime.fromtimestamp(1_775_000_000, tz=timezone.utc)
        assert subscription_period_end(subscription) == expected

    def test_missing_period_is_absent_rather_than_wrong(self):
        assert subscription_period_end({"items": {"data": [{}]}}) is None

    def test_price_is_read_from_items(self):
        subscription = subscription_event(price_id=PRICE_PROFESSIONAL)["data"]["object"]
        assert subscription_price_id(subscription) == PRICE_PROFESSIONAL

    def test_legacy_plan_field_still_resolves_a_price(self):
        subscription = {"items": {"data": [{"plan": {"id": PRICE_FOUNDATION}}]}}
        assert subscription_price_id(subscription) == PRICE_FOUNDATION


class TestInvoiceSubscriptionReader:
    def test_basil_reads_the_subscription_from_parent(self):
        invoice = invoice_event(api_shape=BASIL_SHAPE)["data"]["object"]
        assert "subscription" not in invoice
        assert invoice_subscription_id(invoice) == "sub_test_1"

    def test_legacy_reads_the_top_level_subscription(self):
        invoice = invoice_event(api_shape=LEGACY_SHAPE)["data"]["object"]
        assert invoice_subscription_id(invoice) == "sub_test_1"

    def test_line_items_are_a_last_resort(self):
        invoice = {
            "lines": {
                "data": [
                    {
                        "parent": {
                            "type": "subscription_item_details",
                            "subscription_item_details": {"subscription": "sub_line"},
                        }
                    }
                ]
            }
        }
        assert invoice_subscription_id(invoice) == "sub_line"

    def test_a_non_subscription_invoice_reports_no_subscription(self):
        invoice = {
            "parent": {
                "type": "quote_details",
                "quote_details": {"quote": "qt_1"},
                "subscription_details": {"subscription": "sub_should_be_ignored"},
            }
        }
        assert invoice_subscription_id(invoice) is None

    def test_expanded_objects_are_accepted(self):
        invoice = {
            "parent": {
                "type": "subscription_details",
                "subscription_details": {"subscription": {"id": "sub_expanded"}},
            }
        }
        assert invoice_subscription_id(invoice) == "sub_expanded"

    def test_subscription_metadata_is_visible_for_organization_resolution(self):
        invoice = invoice_event(
            api_shape=BASIL_SHAPE,
            subscription_metadata={"organization_id": "org-7"},
        )["data"]["object"]
        assert invoice_metadata(invoice)["organization_id"] == "org-7"

    def test_legacy_subscription_details_metadata_is_visible(self):
        invoice = invoice_event(
            api_shape=LEGACY_SHAPE,
            subscription_metadata={"organization_id": "org-7"},
        )["data"]["object"]
        assert invoice_metadata(invoice)["organization_id"] == "org-7"


# --- the funnel, in both shapes ---------------------------------------------


@pytest.mark.parametrize("shape", API_SHAPES)
class TestPurchaseFunnelAcrossApiShapes:
    @run_async
    async def test_activation_grants_professional_capabilities(self, env, org, shape):
        client = _webhook_client(env)
        response = _post(
            client,
            subscription_event(organization_id=org, api_shape=shape),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "processed"
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 5
        assert profile.alert_delivery_enabled is True
        assert profile.live_sources_enabled is True
        assert profile.evidence_correlation_enabled is True

    @run_async
    async def test_renewal_date_reaches_the_customer(self, env, org, shape):
        _post(
            _webhook_client(env),
            subscription_event(organization_id=org, api_shape=shape),
        )
        status = await env.billing_svc.get_status(env.context(org))
        assert status.subscription.current_period_end == PERIOD_END

    @run_async
    async def test_payment_failure_moves_the_subscription_to_past_due(
        self,
        env,
        org,
        shape,
    ):
        client = _webhook_client(env)
        _post(client, subscription_event(organization_id=org, api_shape=shape))
        _post(
            client,
            invoice_event(
                event_type="invoice.payment_failed",
                event_id="evt_inv_failed",
                created=1_770_000_300,
                api_shape=shape,
            ),
        )
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.status == "past_due"
        assert subscription.latest_invoice_status == "payment_failed"

    @run_async
    async def test_recovered_payment_restores_active_billing(self, env, org, shape):
        client = _webhook_client(env)
        _post(client, subscription_event(organization_id=org, api_shape=shape))
        _post(
            client,
            invoice_event(
                event_type="invoice.payment_failed",
                event_id="evt_inv_failed",
                created=1_770_000_300,
                api_shape=shape,
            ),
        )
        _post(
            client,
            invoice_event(
                event_type="invoice.paid",
                event_id="evt_inv_paid",
                created=1_770_000_400,
                api_shape=shape,
            ),
        )
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.status == "active"

    @run_async
    async def test_an_invoice_resolves_its_organization_from_stripe_references(
        self,
        env,
        org,
        shape,
    ):
        """Checkout may not have run, so there is no billing customer to join on."""
        client = _webhook_client(env)
        _post(client, subscription_event(organization_id=org, api_shape=shape))
        assert await env.customers.find_by_organization(org) is None

        response = _post(
            client,
            invoice_event(
                event_type="invoice.payment_failed",
                event_id="evt_inv_ref",
                created=1_770_000_300,
                subscription_metadata={"organization_id": org},
                api_shape=shape,
            ),
        )
        assert response.json()["status"] == "processed"

    @run_async
    async def test_an_invoice_for_an_unknown_subscription_changes_nothing(
        self,
        env,
        org,
        shape,
    ):
        client = _webhook_client(env)
        _post(client, subscription_event(organization_id=org, api_shape=shape))
        response = _post(
            client,
            invoice_event(
                event_type="invoice.payment_failed",
                customer_id="cus_someone_else",
                subscription_id="sub_someone_else",
                event_id="evt_inv_foreign",
                created=1_770_000_300,
                api_shape=shape,
            ),
        )
        assert response.json()["status"] == "ignored"
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.status == "active"


class TestRealStripeEventSequence:
    """The order Stripe actually produces for a Checkout purchase."""

    @run_async
    async def test_checkout_then_subscription_then_invoice_settles_on_professional(
        self,
        env,
        org,
    ):
        client = _webhook_client(env)
        # Basil postpones subscription creation until after payment, so these
        # three events arrive within the same second in practice.
        _post(
            client,
            checkout_completed_event(organization_id=org, created=1_770_000_100),
        )
        _post(
            client,
            subscription_event(
                organization_id=org,
                event_id="evt_sub_created",
                created=1_770_000_100,
                api_shape=BASIL_SHAPE,
            ),
        )
        _post(
            client,
            invoice_event(
                event_type="invoice.paid",
                event_id="evt_inv_first",
                created=1_770_000_100,
                api_shape=BASIL_SHAPE,
            ),
        )
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.status == "active"
        assert subscription.plan_key == "professional"
        assert subscription.stripe_subscription_id == "sub_test_1"
        assert subscription.current_period_end == PERIOD_END
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 5

    @run_async
    async def test_same_second_events_are_all_applied(self, env, org):
        """Stripe stamps `created` to the second; equal is not stale."""
        client = _webhook_client(env)
        _post(
            client,
            subscription_event(
                organization_id=org,
                event_id="evt_a",
                created=1_770_000_100,
                api_shape=BASIL_SHAPE,
            ),
        )
        response = _post(
            client,
            subscription_event(
                event_type="customer.subscription.updated",
                organization_id=org,
                event_id="evt_b",
                created=1_770_000_100,
                status="past_due",
                api_shape=BASIL_SHAPE,
            ),
        )
        assert response.json()["status"] == "processed"
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.status == "past_due"


class TestOrderingIsTrackedPerConcern:
    """Invoice traffic must not silence a real plan change, and vice versa."""

    @run_async
    async def test_a_plan_change_survives_a_newer_invoice_event(self, env, org):
        client = _webhook_client(env)
        _post(
            client,
            subscription_event(
                organization_id=org,
                event_id="evt_activate",
                created=1_770_000_100,
            ),
        )
        # Renewal invoice lands first...
        _post(
            client,
            invoice_event(
                event_type="invoice.paid",
                event_id="evt_inv_late",
                created=1_770_009_000,
            ),
        )
        # ...then the downgrade that Stripe emitted before it.
        response = _post(
            client,
            subscription_event(
                event_type="customer.subscription.updated",
                organization_id=org,
                price_id=PRICE_FOUNDATION,
                event_id="evt_downgrade",
                created=1_770_005_000,
            ),
        )
        assert response.json()["status"] == "processed"
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.plan_key == "foundation"
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 1

    @run_async
    async def test_an_old_invoice_cannot_undo_newer_subscription_state(self, env, org):
        client = _webhook_client(env)
        _post(
            client,
            subscription_event(
                organization_id=org,
                event_id="evt_activate",
                created=1_770_005_000,
            ),
        )
        response = _post(
            client,
            invoice_event(
                event_type="invoice.payment_failed",
                event_id="evt_inv_stale",
                created=1_770_001_000,
            ),
        )
        assert response.json()["status"] == "ignored"
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.status == "active"

    @run_async
    async def test_an_older_subscription_event_is_still_rejected(self, env, org):
        client = _webhook_client(env)
        _post(
            client,
            subscription_event(
                organization_id=org,
                event_id="evt_new",
                created=1_770_009_000,
            ),
        )
        response = _post(
            client,
            subscription_event(
                event_type="customer.subscription.updated",
                organization_id=org,
                price_id=PRICE_FOUNDATION,
                event_id="evt_old",
                created=1_770_001_000,
            ),
        )
        assert response.json()["status"] == "ignored"
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.plan_key == "professional"

    @run_async
    async def test_each_concern_records_its_own_clock(self, env, org):
        client = _webhook_client(env)
        _post(
            client,
            subscription_event(
                organization_id=org,
                event_id="evt_life",
                created=1_770_000_100,
            ),
        )
        _post(
            client,
            invoice_event(
                event_type="invoice.paid",
                event_id="evt_inv",
                created=1_770_000_500,
            ),
        )
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.last_lifecycle_event_at == datetime.fromtimestamp(
            1_770_000_100, tz=timezone.utc
        )
        assert subscription.last_invoice_event_at == datetime.fromtimestamp(
            1_770_000_500, tz=timezone.utc
        )


class TestUndatedEventsStayDeterministic:
    """Stripe always stamps ``created``; a payload without one must still be safe.

    An undated event cannot be compared against the stored watermark, so it is
    applied on arrival — but it must not erase the watermark, or the next
    genuinely stale event would be free to revert the state.
    """

    @staticmethod
    def _undated(**kwargs) -> dict:
        event = subscription_event(**kwargs)
        event.pop("created")
        return event

    @run_async
    async def test_an_undated_event_is_applied_on_arrival(self, env, org):
        client = _webhook_client(env)
        response = _post(client, self._undated(organization_id=org, event_id="evt_undated"))
        assert response.json()["status"] == "processed"
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.plan_key == "professional"

    @run_async
    async def test_an_undated_event_does_not_erase_the_watermark(self, env, org):
        client = _webhook_client(env)
        _post(
            client,
            subscription_event(
                organization_id=org,
                event_id="evt_activate",
                created=1_770_009_000,
            ),
        )
        _post(
            client,
            self._undated(
                event_type="customer.subscription.updated",
                organization_id=org,
                event_id="evt_undated",
                status="past_due",
            ),
        )
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.last_lifecycle_event_at == datetime.fromtimestamp(
            1_770_009_000, tz=timezone.utc
        )
        response = _post(
            client,
            subscription_event(
                event_type="customer.subscription.updated",
                organization_id=org,
                price_id=PRICE_FOUNDATION,
                event_id="evt_old",
                created=1_770_001_000,
            ),
        )
        assert response.json()["status"] == "ignored"
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.plan_key == "professional"

    @run_async
    async def test_arrival_order_decides_between_two_undated_events(self, env, org):
        client = _webhook_client(env)
        _post(
            client,
            self._undated(organization_id=org, event_id="evt_undated_a"),
        )
        response = _post(
            client,
            self._undated(
                event_type="customer.subscription.updated",
                organization_id=org,
                price_id=PRICE_FOUNDATION,
                event_id="evt_undated_b",
            ),
        )
        assert response.json()["status"] == "processed"
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.plan_key == "foundation"
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 1


class TestFailedEventsAreRetried:
    """Stripe redelivers a 5xx; the ledger must not turn that into a no-op."""

    @staticmethod
    def _break_sync(env):
        async def explode(*_args, **_kwargs):
            raise RuntimeError("entitlement store unavailable")

        original = env.entitlement_sync.sync
        env.entitlement_sync.sync = explode
        return original

    @run_async
    async def test_a_processing_failure_is_recorded_and_surfaced(self, env, org):
        self._break_sync(env)
        client = _webhook_client(env)
        with pytest.raises(RuntimeError):
            _post(client, subscription_event(organization_id=org))
        stored = await env.events.find_by_stripe_event_id("evt_sub_1")
        assert stored.status == "failed"
        assert stored.attempt_count == 1

    @run_async
    async def test_redelivery_reprocesses_a_failed_event(self, env, org):
        original = self._break_sync(env)
        client = _webhook_client(env)
        event = subscription_event(organization_id=org)
        with pytest.raises(RuntimeError):
            _post(client, event)

        env.entitlement_sync.sync = original
        response = _post(client, event)
        assert response.json()["status"] == "processed"

        stored = await env.events.find_by_stripe_event_id("evt_sub_1")
        assert stored.status == "processed"
        assert stored.attempt_count == 2
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 5

    @run_async
    async def test_a_successful_event_is_never_reprocessed(self, env, org):
        client = _webhook_client(env)
        event = subscription_event(organization_id=org)
        _post(client, event)
        response = _post(client, event)
        assert response.json()["status"] == "duplicate"
        stored = await env.events.find_by_stripe_event_id("evt_sub_1")
        assert stored.attempt_count == 1

    @run_async
    async def test_one_subscription_row_survives_repeated_delivery(self, env, org):
        client = _webhook_client(env)
        event = subscription_event(organization_id=org)
        for _ in range(4):
            _post(client, event)
        assert len(env.store.subscriptions) == 1
        assert len(env.store.events) == 1


class TestWebhookOperability:
    @run_async
    async def test_the_newest_delivery_outcome_is_visible(self, env, org):
        await _deliver(env, subscription_event(organization_id=org))
        status = await env.billing_svc.get_status(env.context(org))
        assert status.synchronization.last_event_status == "processed"
        assert status.synchronization.last_event_type == "customer.subscription.created"
        assert status.synchronization.failed_event_count == 0

    @run_async
    async def test_a_failed_delivery_is_visible(self, env, org):
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
                    event_id="evt_fails",
                    created=1_770_000_500,
                ),
            )
        status = await env.billing_svc.get_status(env.context(org))
        assert status.synchronization.last_event_status == "failed"
        assert status.synchronization.failed_event_count == 1
        assert status.synchronization.last_failure_at is not None

    @run_async
    async def test_billing_status_never_leaks_the_ledger_detail_of_another_org(
        self,
        env,
        org,
    ):
        other = env.add_organization("Other Forestry")
        await _deliver(env, subscription_event(organization_id=org))
        status = await env.billing_svc.get_status(env.context(other))
        assert status.synchronization.last_event_type is None
        assert status.synchronization.last_event_status is None


class _FakeCustomerResource:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return {"id": "cus_live_1"}


class _FakeStripeModule:
    """Stands in for the Stripe SDK: records configuration, performs no I/O."""

    def __init__(self) -> None:
        self.api_key: str | None = None
        self.api_version: str | None = None
        self.Customer = _FakeCustomerResource()


@pytest.fixture
def fake_stripe(monkeypatch):
    """Install a stand-in ``stripe`` module so the real lazy import runs."""
    module = _FakeStripeModule()
    monkeypatch.setitem(sys.modules, "stripe", module)
    return module


class TestGatewayConfiguration:
    def test_billing_disabled_never_reaches_stripe(self):
        gateway = build_stripe_gateway(billing_settings(enable_billing=False))
        assert isinstance(gateway, FakeStripeGateway)
        assert gateway.is_configured is True

    def test_enabling_billing_without_a_key_fails_loudly(self):
        gateway = build_stripe_gateway(
            billing_settings(enable_billing=True, stripe_secret_key="")
        )
        assert isinstance(gateway, FakeStripeGateway)
        assert gateway.is_configured is False

    def test_a_configured_key_selects_the_live_gateway(self):
        gateway = build_stripe_gateway(
            billing_settings(enable_billing=True, stripe_secret_key="sk_test_123")
        )
        assert isinstance(gateway, LiveStripeGateway)
        assert gateway.is_configured is True

    def test_the_api_version_is_pinned_when_configured(self, fake_stripe):
        gateway = LiveStripeGateway("sk_test_123", api_version="2025-03-31.basil")
        assert gateway._client() is fake_stripe
        assert fake_stripe.api_key == "sk_test_123"
        assert fake_stripe.api_version == "2025-03-31.basil"

    def test_the_forestwatch_pin_is_applied_when_no_version_is_passed(
        self,
        fake_stripe,
    ):
        from app.core.commercial.stripe_api import STRIPE_API_VERSION

        LiveStripeGateway("sk_test_123")._client()
        assert fake_stripe.api_version == STRIPE_API_VERSION

    def test_build_gateway_pins_the_documented_api_version(self, fake_stripe):
        from app.core.commercial.stripe_api import STRIPE_API_VERSION

        gateway = build_stripe_gateway(
            billing_settings(enable_billing=True, stripe_secret_key="sk_test_123")
        )
        assert isinstance(gateway, LiveStripeGateway)
        gateway._client()
        assert fake_stripe.api_version == STRIPE_API_VERSION

    @run_async
    async def test_customer_creation_is_idempotent_per_organization(self, fake_stripe):
        """A retried create must not leave the organization with two customers."""
        customer_id = await LiveStripeGateway("sk_test_123").create_customer(
            organization_id="org-1",
            organization_name="Carpathian Forestry",
            email="billing@forest.test",
        )
        assert customer_id == "cus_live_1"
        call = fake_stripe.Customer.calls[0]
        assert call["idempotency_key"] == "forestwatch-customer-org-1"
        assert call["metadata"] == {"organization_id": "org-1"}


class TestBillingCustomerRace:
    @run_async
    async def test_a_concurrent_checkout_reuses_the_linked_customer(self, env, org):
        """Two checkouts at once must not fight over the unique index."""
        await env.customers.insert(
            BillingCustomer(
                organization_id=org,
                stripe_customer_id="cus_from_webhook",
                email="billing@forest.test",
            )
        )
        original_find = env.customers.find_by_organization
        reads = {"count": 0}

        async def find_after_the_race(organization_id: str):
            # The first read happens before the competing writer commits.
            reads["count"] += 1
            if reads["count"] == 1:
                return None
            return await original_find(organization_id)

        env.customers.find_by_organization = find_after_the_race
        session = await env.billing_svc.create_checkout_session(
            env.context(org),
            "professional",
        )
        assert session.checkout_url
        assert len(env.store.customers) == 1
        assert env.gateway.checkout_sessions[0]["customer_id"] == "cus_from_webhook"


class TestCurrentStripeContract:
    """Gaps that only show up against the pinned Dahlia-era payloads."""

    @run_async
    async def test_unknown_price_does_not_grant_professional_from_metadata(
        self,
        env,
        org,
    ):
        client = _webhook_client(env)
        response = _post(
            client,
            subscription_event(
                organization_id=org,
                price_id="price_not_in_catalog",
                plan_key="professional",
                event_id="evt_unknown_price",
                api_shape=BASIL_SHAPE,
            ),
        )
        assert response.json()["status"] == "processed"
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.plan_key == "foundation"
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 1
        assert profile.alert_delivery_enabled is False

    @run_async
    async def test_missing_price_may_use_metadata_when_items_are_absent(
        self,
        env,
        org,
    ):
        event = subscription_event(
            organization_id=org,
            plan_key="professional",
            event_id="evt_no_items",
            api_shape=BASIL_SHAPE,
        )
        event["data"]["object"]["items"] = {"data": []}
        client = _webhook_client(env)
        _post(client, event)
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.plan_key == "professional"

    @run_async
    async def test_incomplete_checkout_does_not_grant_paid_capability(self, env, org):
        client = _webhook_client(env)
        _post(
            client,
            subscription_event(
                organization_id=org,
                status="incomplete",
                event_id="evt_incomplete",
                api_shape=BASIL_SHAPE,
            ),
        )
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 1
        assert profile.alert_delivery_enabled is False

    @run_async
    async def test_incomplete_expired_falls_back_to_foundation(self, env, org):
        client = _webhook_client(env)
        _post(
            client,
            subscription_event(
                organization_id=org,
                event_id="evt_active_first",
                api_shape=BASIL_SHAPE,
            ),
        )
        _post(
            client,
            subscription_event(
                event_type="customer.subscription.updated",
                organization_id=org,
                status="incomplete_expired",
                event_id="evt_expired",
                created=1_770_000_400,
                api_shape=BASIL_SHAPE,
            ),
        )
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 1

    @run_async
    async def test_enterprise_price_grants_enterprise_capacity(self):
        env = build_environment(
            stripe_price_enterprise=PRICE_ENTERPRISE,
            plan_enterprise_purchasable=True,
        )
        org = env.add_organization("Institution")
        _post(
            _webhook_client(env),
            subscription_event(
                organization_id=org,
                price_id=PRICE_ENTERPRISE,
                event_id="evt_ent",
                api_shape=BASIL_SHAPE,
            ),
        )
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 50
        assert profile.alert_delivery_enabled is True
        assert profile.live_sources_enabled is True
        assert profile.evidence_correlation_enabled is True

    @run_async
    async def test_identical_subscription_update_does_not_duplicate_rows(
        self,
        env,
        org,
    ):
        client = _webhook_client(env)
        first = subscription_event(
            organization_id=org,
            event_id="evt_same_a",
            created=1_770_000_100,
            api_shape=BASIL_SHAPE,
        )
        second = subscription_event(
            event_type="customer.subscription.updated",
            organization_id=org,
            event_id="evt_same_b",
            created=1_770_000_200,
            api_shape=BASIL_SHAPE,
        )
        _post(client, first)
        _post(client, second)
        assert len(env.store.subscriptions) == 1
        entitlement_types = {
            raw["entitlement_type"]
            for raw in env.store.entitlements.values()
            if raw["organization_id"] == org
        }
        assert len(entitlement_types) == len(env.store.entitlements)

    @run_async
    async def test_pause_then_resume_restores_professional(self, env, org):
        client = _webhook_client(env)
        _post(
            client,
            subscription_event(
                organization_id=org,
                event_id="evt_on",
                api_shape=BASIL_SHAPE,
            ),
        )
        _post(
            client,
            subscription_event(
                event_type="customer.subscription.paused",
                organization_id=org,
                status="paused",
                event_id="evt_pause",
                created=1_770_000_300,
                api_shape=BASIL_SHAPE,
            ),
        )
        paused = await env.entitlement_svc.get_profile(org)
        assert paused.alert_delivery_enabled is False
        _post(
            client,
            subscription_event(
                event_type="customer.subscription.resumed",
                organization_id=org,
                status="active",
                event_id="evt_resume",
                created=1_770_000_400,
                api_shape=BASIL_SHAPE,
            ),
        )
        resumed = await env.entitlement_svc.get_profile(org)
        assert resumed.monitored_area_limit == 5
        assert resumed.alert_delivery_enabled is True

    @run_async
    async def test_downgrade_to_foundation_price_lowers_limit_without_deleting_areas(
        self,
        env,
        org,
    ):
        env.add_area(org, name="Stand A")
        env.add_area(org, name="Stand B", offset=0.6)
        client = _webhook_client(env)
        _post(
            client,
            subscription_event(
                organization_id=org,
                event_id="evt_pro",
                api_shape=BASIL_SHAPE,
            ),
        )
        _post(
            client,
            subscription_event(
                event_type="customer.subscription.updated",
                organization_id=org,
                price_id=PRICE_FOUNDATION,
                event_id="evt_down",
                created=1_770_000_500,
                api_shape=BASIL_SHAPE,
            ),
        )
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 1
        assert len(await env.areas.list_for_organization(org)) == 2
        status = await env.billing_svc.get_status(env.context(org))
        assert status.capacity["over_limit"] is True

