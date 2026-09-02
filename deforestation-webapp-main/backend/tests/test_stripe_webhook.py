"""Stripe webhook verification, idempotency, and subscription lifecycle."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.billing.stripe_signature import (
    WebhookVerificationError,
    build_signature_header,
    compute_signature,
    verify_webhook_signature,
)
from app.services.billing.stripe_webhook_service import (
    SUPPORTED_EVENT_TYPES,
    WebhookPayloadError,
    WebhookSignatureError,
)
from fixtures.billing_fakes import (
    PRICE_FOUNDATION,
    PRICE_PROFESSIONAL,
    WEBHOOK_SECRET,
    build_environment,
    checkout_completed_event,
    encode_event,
    invoice_event,
    run_async,
    signed_headers,
    subscription_event,
)


@pytest.fixture
def env():
    return build_environment()


@pytest.fixture
def org(env):
    return env.add_organization("Carpathian Forestry")


def _signature(payload: bytes, *, secret: str = WEBHOOK_SECRET, offset: int = 0) -> str:
    stamp = int(datetime.now(timezone.utc).timestamp()) + offset
    return build_signature_header(payload, timestamp=stamp, secret=secret)


async def _deliver(env, event: dict, *, secret: str = WEBHOOK_SECRET):
    payload = encode_event(event)
    return await env.webhook_svc.handle(payload, _signature(payload, secret=secret))


async def _activate(env, org, *, price_id: str = PRICE_PROFESSIONAL, created: int = 1_770_000_100):
    return await _deliver(
        env,
        subscription_event(
            organization_id=org,
            price_id=price_id,
            status="active",
            created=created,
        ),
    )


class TestSignatureVerification:
    def test_valid_signature_passes(self):
        payload = b'{"id":"evt_1"}'
        header = _signature(payload)
        verify_webhook_signature(payload, header, WEBHOOK_SECRET)

    def test_wrong_secret_is_rejected(self):
        payload = b'{"id":"evt_1"}'
        header = _signature(payload, secret="whsec_other")
        with pytest.raises(WebhookVerificationError):
            verify_webhook_signature(payload, header, WEBHOOK_SECRET)

    def test_tampered_payload_is_rejected(self):
        header = _signature(b'{"id":"evt_1"}')
        with pytest.raises(WebhookVerificationError):
            verify_webhook_signature(b'{"id":"evt_2"}', header, WEBHOOK_SECRET)

    def test_missing_header_is_rejected(self):
        with pytest.raises(WebhookVerificationError):
            verify_webhook_signature(b"{}", None, WEBHOOK_SECRET)

    def test_malformed_header_is_rejected(self):
        with pytest.raises(WebhookVerificationError):
            verify_webhook_signature(b"{}", "not-a-signature", WEBHOOK_SECRET)

    def test_header_without_timestamp_is_rejected(self):
        payload = b"{}"
        signature = compute_signature(payload, timestamp=1_770_000_000, secret=WEBHOOK_SECRET)
        with pytest.raises(WebhookVerificationError):
            verify_webhook_signature(payload, f"v1={signature}", WEBHOOK_SECRET)

    def test_header_without_v1_scheme_is_rejected(self):
        with pytest.raises(WebhookVerificationError):
            verify_webhook_signature(b"{}", "t=1770000000,v0=abc", WEBHOOK_SECRET)

    def test_unconfigured_secret_rejects_everything(self):
        payload = b"{}"
        with pytest.raises(WebhookVerificationError):
            verify_webhook_signature(payload, _signature(payload), "")

    def test_old_timestamp_is_rejected(self):
        payload = b"{}"
        stamp = int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp())
        header = build_signature_header(payload, timestamp=stamp, secret=WEBHOOK_SECRET)
        with pytest.raises(WebhookVerificationError):
            verify_webhook_signature(payload, header, WEBHOOK_SECRET)

    def test_tolerance_can_be_disabled_for_replay_fixtures(self):
        payload = b"{}"
        stamp = 1_600_000_000
        header = build_signature_header(payload, timestamp=stamp, secret=WEBHOOK_SECRET)
        verify_webhook_signature(payload, header, WEBHOOK_SECRET, tolerance_seconds=0)

    def test_multiple_signatures_accepts_the_matching_one(self):
        payload = b"{}"
        stamp = int(datetime.now(timezone.utc).timestamp())
        good = compute_signature(payload, timestamp=stamp, secret=WEBHOOK_SECRET)
        verify_webhook_signature(
            payload,
            f"t={stamp},v1=deadbeef,v1={good}",
            WEBHOOK_SECRET,
        )


class TestWebhookRejection:
    @run_async
    async def test_invalid_signature_never_reaches_processing(self, env, org):
        event = subscription_event(organization_id=org)
        payload = encode_event(event)
        with pytest.raises(WebhookSignatureError):
            await env.webhook_svc.handle(payload, _signature(payload, secret="whsec_bad"))
        assert env.store.events == {}
        assert env.store.subscriptions == {}

    @run_async
    async def test_missing_signature_is_rejected(self, env, org):
        payload = encode_event(subscription_event(organization_id=org))
        with pytest.raises(WebhookSignatureError):
            await env.webhook_svc.handle(payload, None)

    @run_async
    async def test_malformed_json_is_rejected(self, env):
        payload = b"not json at all"
        with pytest.raises(WebhookPayloadError):
            await env.webhook_svc.handle(payload, _signature(payload))

    @run_async
    async def test_non_object_payload_is_rejected(self, env):
        payload = b"[1,2,3]"
        with pytest.raises(WebhookPayloadError):
            await env.webhook_svc.handle(payload, _signature(payload))

    @run_async
    async def test_event_without_id_is_rejected(self, env):
        payload = encode_event({"type": "invoice.paid"})
        with pytest.raises(WebhookPayloadError):
            await env.webhook_svc.handle(payload, _signature(payload))

    @run_async
    async def test_unhandled_event_type_is_ignored_without_a_ledger_row(self, env):
        result = await _deliver(env, {"id": "evt_x", "type": "charge.refunded", "created": 1})
        assert result.status == "ignored"
        assert env.store.events == {}

    @run_async
    async def test_supported_event_types_are_bounded(self, env):
        assert len(SUPPORTED_EVENT_TYPES) == 8


class TestIdempotency:
    @run_async
    async def test_duplicate_delivery_is_not_processed_twice(self, env, org):
        event = subscription_event(organization_id=org)
        first = await _deliver(env, event)
        second = await _deliver(env, event)
        assert first.status == "processed"
        assert second.status == "duplicate"
        assert len(env.store.events) == 1

    @run_async
    async def test_duplicate_delivery_does_not_change_state(self, env, org):
        event = subscription_event(organization_id=org, status="active")
        await _deliver(env, event)
        await _deliver(
            env,
            subscription_event(
                organization_id=org,
                status="canceled",
                event_type="customer.subscription.updated",
                event_id="evt_sub_2",
                created=1_770_000_200,
            ),
        )
        # Replaying the original activation must not resurrect the old state.
        await _deliver(env, event)
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.status == "canceled"

    @run_async
    async def test_ledger_records_the_processed_event(self, env, org):
        await _activate(env, org)
        stored = await env.events.find_by_stripe_event_id("evt_sub_1")
        assert stored.status == "processed"
        assert stored.organization_id == org

    @run_async
    async def test_ledger_records_the_event_type(self, env, org):
        await _activate(env, org)
        stored = await env.events.find_by_stripe_event_id("evt_sub_1")
        assert stored.event_type == "customer.subscription.created"

    @run_async
    async def test_processing_failure_is_recorded_as_failed(self, env, org):
        async def _explode(*args, **kwargs):
            raise RuntimeError("entitlement store offline")

        env.entitlement_sync.sync = _explode
        with pytest.raises(RuntimeError):
            await _activate(env, org)
        stored = await env.events.find_by_stripe_event_id("evt_sub_1")
        assert stored.status == "failed"
        assert await env.events.count_failed() == 1


class TestSubscriptionLifecycle:
    @run_async
    async def test_checkout_completion_links_the_stripe_customer(self, env, org):
        await _deliver(env, checkout_completed_event(organization_id=org))
        customer = await env.customers.find_by_organization(org)
        assert customer.stripe_customer_id == "cus_test_1"

    @run_async
    async def test_checkout_completion_activates_the_plan(self, env, org):
        await _deliver(env, checkout_completed_event(organization_id=org))
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.plan_key == "professional"
        assert subscription.status == "active"
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.alert_delivery_enabled is True

    @run_async
    async def test_unpaid_checkout_does_not_grant_capability(self, env, org):
        await _deliver(
            env,
            checkout_completed_event(organization_id=org, payment_status="unpaid"),
        )
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.status == "incomplete"
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.alert_delivery_enabled is False

    @run_async
    async def test_checkout_without_organization_reference_is_ignored(self, env):
        event = checkout_completed_event(organization_id="")
        event["data"]["object"]["metadata"] = {}
        result = await _deliver(env, event)
        assert result.status == "ignored"

    @run_async
    async def test_checkout_for_unknown_organization_is_ignored(self, env):
        result = await _deliver(env, checkout_completed_event(organization_id="org-999"))
        assert result.status == "ignored"
        assert env.store.customers == {}

    @run_async
    async def test_subscription_created_resolves_plan_from_the_price(self, env, org):
        result = await _activate(env, org)
        assert result.plan_key == "professional"
        assert result.subscription_status == "active"

    @run_async
    async def test_subscription_activation_synchronizes_entitlements(self, env, org):
        await _activate(env, org)
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 5
        assert profile.live_sources_enabled is True

    @run_async
    async def test_subscription_stores_renewal_state(self, env, org):
        await _deliver(
            env,
            subscription_event(
                organization_id=org,
                cancel_at_period_end=True,
                current_period_end=1_772_600_000,
            ),
        )
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.cancel_at_period_end is True
        assert subscription.current_period_end is not None

    @run_async
    async def test_trialing_subscription_grants_capability(self, env, org):
        await _deliver(
            env,
            subscription_event(organization_id=org, status="trialing", trial_end=1_772_000_000),
        )
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.alert_delivery_enabled is True

    @run_async
    async def test_upgrade_updates_the_plan_and_limit(self, env, org):
        await _activate(env, org, price_id=PRICE_FOUNDATION)
        await _deliver(
            env,
            subscription_event(
                event_type="customer.subscription.updated",
                organization_id=org,
                price_id=PRICE_PROFESSIONAL,
                event_id="evt_sub_upgrade",
                created=1_770_000_300,
            ),
        )
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.plan_key == "professional"
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 5

    @run_async
    async def test_downgrade_lowers_the_limit_but_keeps_areas(self, env, org):
        await _activate(env, org)
        for index in range(4):
            env.add_area(org, name=f"Stand {index}", offset=index * 0.1)
        await _deliver(
            env,
            subscription_event(
                event_type="customer.subscription.updated",
                organization_id=org,
                price_id=PRICE_FOUNDATION,
                event_id="evt_sub_downgrade",
                created=1_770_000_400,
            ),
        )
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 1
        assert len(await env.areas.list_for_organization(org)) == 4

    @run_async
    async def test_cancellation_removes_paid_capability(self, env, org):
        await _activate(env, org)
        await _deliver(
            env,
            subscription_event(
                event_type="customer.subscription.deleted",
                organization_id=org,
                status="canceled",
                event_id="evt_sub_deleted",
                created=1_770_000_500,
            ),
        )
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.status == "canceled"
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.alert_delivery_enabled is False
        assert profile.monitored_area_limit == 1

    @run_async
    async def test_cancellation_preserves_monitored_areas(self, env, org):
        await _activate(env, org)
        env.add_area(org, name="Kept stand")
        await _deliver(
            env,
            subscription_event(
                event_type="customer.subscription.deleted",
                organization_id=org,
                status="canceled",
                event_id="evt_sub_deleted",
                created=1_770_000_500,
            ),
        )
        assert len(await env.areas.list_for_organization(org)) == 1

    @run_async
    async def test_paused_subscription_revokes_paid_capability(self, env, org):
        await _activate(env, org)
        result = await _deliver(
            env,
            subscription_event(
                event_type="customer.subscription.paused",
                organization_id=org,
                status="paused",
                event_id="evt_sub_paused",
                created=1_770_000_600,
            ),
        )
        assert result.status == "processed"
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.status == "paused"
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 1
        assert profile.alert_delivery_enabled is False

    @run_async
    async def test_unsupported_stripe_status_is_ignored(self, env, org):
        await _activate(env, org)
        result = await _deliver(
            env,
            subscription_event(
                event_type="customer.subscription.updated",
                organization_id=org,
                status="something_stripe_invented",
                event_id="evt_sub_unknown_status",
                created=1_770_000_600,
            ),
        )
        assert result.status == "ignored"
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.status == "active"

    @run_async
    async def test_subscription_without_known_organization_is_ignored(self, env):
        result = await _deliver(env, subscription_event(organization_id=None))
        assert result.status == "ignored"
        assert env.store.subscriptions == {}

    @run_async
    async def test_organization_resolves_through_the_linked_customer(self, env, org):
        await _deliver(env, checkout_completed_event(organization_id=org))
        result = await _deliver(
            env,
            subscription_event(
                event_type="customer.subscription.updated",
                organization_id=None,
                event_id="evt_sub_via_customer",
                created=1_770_000_700,
            ),
        )
        assert result.organization_id == org

    @run_async
    async def test_forged_organization_metadata_is_not_trusted(self, env, org):
        await _deliver(env, checkout_completed_event(organization_id=org))
        result = await _deliver(
            env,
            subscription_event(
                event_type="customer.subscription.updated",
                organization_id="org-does-not-exist",
                event_id="evt_sub_forged",
                created=1_770_000_800,
            ),
        )
        # Falls back to the Stripe customer link rather than the forged id.
        assert result.organization_id == org


class TestPaymentEvents:
    @run_async
    async def test_payment_failure_moves_the_subscription_past_due(self, env, org):
        await _activate(env, org)
        await _deliver(env, invoice_event(event_type="invoice.payment_failed"))
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.status == "past_due"
        assert subscription.latest_invoice_status == "payment_failed"

    @run_async
    async def test_past_due_organization_keeps_working(self, env, org):
        await _activate(env, org)
        await _deliver(env, invoice_event(event_type="invoice.payment_failed"))
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.alert_delivery_enabled is True

    @run_async
    async def test_successful_payment_restores_active_billing(self, env, org):
        await _activate(env, org)
        await _deliver(env, invoice_event(event_type="invoice.payment_failed"))
        await _deliver(
            env,
            invoice_event(
                event_type="invoice.paid",
                event_id="evt_inv_2",
                created=1_770_000_300,
            ),
        )
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.status == "active"
        assert subscription.latest_invoice_status == "paid"

    @run_async
    async def test_payment_failure_does_not_revive_a_canceled_subscription(self, env, org):
        await _activate(env, org)
        await _deliver(
            env,
            subscription_event(
                event_type="customer.subscription.deleted",
                organization_id=org,
                status="canceled",
                event_id="evt_sub_deleted",
                created=1_770_000_500,
            ),
        )
        await _deliver(
            env,
            invoice_event(event_type="invoice.payment_failed", created=1_770_000_600),
        )
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.status == "canceled"

    @run_async
    async def test_invoice_without_a_subscription_of_record_is_ignored(self, env, org):
        await _deliver(env, checkout_completed_event(organization_id=org))
        env.store.subscriptions.clear()
        result = await _deliver(
            env,
            invoice_event(event_type="invoice.paid", created=1_770_000_900),
        )
        assert result.status == "ignored"

    @run_async
    async def test_invoice_for_unknown_customer_is_ignored(self, env):
        result = await _deliver(
            env,
            invoice_event(event_type="invoice.paid", customer_id="cus_unknown"),
        )
        assert result.status == "ignored"


class TestOutOfOrderEvents:
    @run_async
    async def test_stale_event_does_not_overwrite_newer_state(self, env, org):
        await _deliver(
            env,
            subscription_event(
                event_type="customer.subscription.updated",
                organization_id=org,
                status="canceled",
                event_id="evt_new",
                created=1_770_005_000,
            ),
        )
        result = await _deliver(
            env,
            subscription_event(
                event_type="customer.subscription.updated",
                organization_id=org,
                status="active",
                event_id="evt_old",
                created=1_770_001_000,
            ),
        )
        assert result.status == "ignored"
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.status == "canceled"

    @run_async
    async def test_stale_event_leaves_entitlements_alone(self, env, org):
        await _deliver(
            env,
            subscription_event(
                organization_id=org,
                status="canceled",
                event_id="evt_new",
                created=1_770_005_000,
            ),
        )
        await _deliver(
            env,
            subscription_event(
                event_type="customer.subscription.updated",
                organization_id=org,
                status="active",
                event_id="evt_old",
                created=1_770_001_000,
            ),
        )
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.alert_delivery_enabled is False

    @run_async
    async def test_stale_event_is_still_recorded_in_the_ledger(self, env, org):
        await _deliver(
            env,
            subscription_event(
                organization_id=org,
                event_id="evt_new",
                created=1_770_005_000,
            ),
        )
        await _deliver(
            env,
            subscription_event(
                event_type="customer.subscription.updated",
                organization_id=org,
                event_id="evt_old",
                created=1_770_001_000,
            ),
        )
        stored = await env.events.find_by_stripe_event_id("evt_old")
        assert stored.status == "ignored"

    @run_async
    async def test_newer_event_is_applied(self, env, org):
        await _activate(env, org, created=1_770_001_000)
        await _deliver(
            env,
            subscription_event(
                event_type="customer.subscription.updated",
                organization_id=org,
                status="past_due",
                event_id="evt_newer",
                created=1_770_009_000,
            ),
        )
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.status == "past_due"
        assert subscription.last_event_id == "evt_newer"

    @run_async
    async def test_stale_invoice_event_is_ignored(self, env, org):
        await _activate(env, org, created=1_770_005_000)
        result = await _deliver(
            env,
            invoice_event(event_type="invoice.payment_failed", created=1_770_001_000),
        )
        assert result.status == "ignored"
        subscription = await env.subscriptions.find_by_organization(org)
        assert subscription.status == "active"


class TestOrganizationIsolation:
    @run_async
    async def test_subscription_events_only_affect_their_organization(self, env, org):
        other = env.add_organization("Other Forestry")
        await _activate(env, org)
        profile = await env.entitlement_svc.get_profile(other)
        assert profile.monitored_area_limit == 1
        assert await env.subscriptions.find_by_organization(other) is None

    @run_async
    async def test_two_organizations_hold_independent_subscriptions(self, env, org):
        other = env.add_organization("Other Forestry")
        await _activate(env, org)
        await _deliver(
            env,
            subscription_event(
                organization_id=other,
                customer_id="cus_test_2",
                subscription_id="sub_test_2",
                price_id=PRICE_FOUNDATION,
                event_id="evt_sub_other",
                created=1_770_000_200,
            ),
        )
        assert (await env.subscriptions.find_by_organization(org)).plan_key == "professional"
        assert (await env.subscriptions.find_by_organization(other)).plan_key == "foundation"

    @run_async
    async def test_ledger_scopes_events_per_organization(self, env, org):
        other = env.add_organization("Other Forestry")
        await _activate(env, org)
        assert await env.events.latest_processed(organization_id=org) is not None
        assert await env.events.latest_processed(organization_id=other) is None


class TestSecretHygiene:
    @run_async
    async def test_webhook_result_carries_no_secret_material(self, env, org):
        result = await _activate(env, org)
        assert WEBHOOK_SECRET not in repr(result)

    @run_async
    async def test_ledger_does_not_store_the_raw_payload(self, env, org):
        await _activate(env, org)
        stored = await env.events.find_by_stripe_event_id("evt_sub_1")
        serialized = stored.model_dump_json()
        assert WEBHOOK_SECRET not in serialized
        assert "items" not in serialized
