"""Billing API: status, plans, checkout, portal, and the webhook endpoint."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.billing_routes import router as billing_router
from app.api.deps import (
    billing_service_dep,
    get_organization_context,
    stripe_webhook_service_dep,
)
from app.core.errors import ForbiddenError
from app.services.billing.billing_service import InvalidPlanError
from app.services.billing.stripe_gateway import BillingGatewayError
from fixtures.billing_fakes import (
    PRICE_PROFESSIONAL,
    WEBHOOK_SECRET,
    build_environment,
    encode_event,
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


def _client(env, ctx):
    app = FastAPI()
    app.include_router(billing_router)
    app.dependency_overrides[get_organization_context] = lambda: ctx
    app.dependency_overrides[billing_service_dep] = lambda: env.billing_svc
    app.dependency_overrides[stripe_webhook_service_dep] = lambda: env.webhook_svc
    return TestClient(app)


async def _activate_professional(env, org):
    event = subscription_event(organization_id=org, price_id=PRICE_PROFESSIONAL)
    payload = encode_event(event)
    return await env.webhook_svc.handle(payload, signed_headers(payload)["Stripe-Signature"])


class TestPlansEndpoint:
    def test_plans_are_listed(self, env, org):
        client = _client(env, env.context(org))
        body = client.get("/billing/plans").json()
        assert [item["key"] for item in body["items"]] == [
            "foundation",
            "professional",
            "enterprise",
        ]

    def test_baseline_organization_is_on_foundation(self, env, org):
        client = _client(env, env.context(org))
        assert client.get("/billing/plans").json()["current_plan_key"] == "foundation"

    def test_current_plan_is_flagged(self, env, org):
        client = _client(env, env.context(org))
        items = client.get("/billing/plans").json()["items"]
        assert [item["key"] for item in items if item["current"]] == ["foundation"]

    def test_plans_never_expose_stripe_price_ids(self, env, org):
        client = _client(env, env.context(org))
        assert PRICE_PROFESSIONAL not in client.get("/billing/plans").text

    def test_members_may_view_plans(self, env, org):
        client = _client(env, env.context(org, role="member"))
        body = client.get("/billing/plans").json()
        assert body["can_manage_billing"] is False

    def test_owner_may_manage_billing(self, env, org):
        client = _client(env, env.context(org))
        assert client.get("/billing/plans").json()["can_manage_billing"] is True

    def test_suspended_membership_cannot_view_plans(self, env, org):
        client = _client(env, env.context(org, membership_status="suspended"))
        assert client.get("/billing/plans").status_code == 403


class TestStatusEndpoint:
    def test_status_reports_the_organization(self, env, org):
        client = _client(env, env.context(org))
        body = client.get("/billing/status").json()
        assert body["organization"]["name"] == "Carpathian Forestry"
        assert body["organization"]["role"] == "owner"

    def test_baseline_status_has_no_subscription(self, env, org):
        client = _client(env, env.context(org))
        body = client.get("/billing/status").json()
        assert body["subscription"] is None
        assert body["plan"]["key"] == "foundation"
        assert body["plan"]["from_subscription"] is False

    def test_status_includes_the_entitlement_summary(self, env, org):
        client = _client(env, env.context(org))
        entitlements = client.get("/billing/status").json()["entitlements"]
        assert entitlements["monitored_area_limit"] == 1
        assert entitlements["alert_delivery_enabled"] is False

    def test_status_reports_capacity(self, env, org):
        env.add_area(org, name="Only stand")
        client = _client(env, env.context(org))
        capacity = client.get("/billing/status").json()["capacity"]
        assert capacity == {
            "monitored_area_count": 1,
            "monitored_area_limit": 1,
            "remaining": 0,
            "at_limit": True,
            "over_limit": False,
        }

    def test_status_recommends_an_upgrade_when_capability_is_missing(self, env, org):
        client = _client(env, env.context(org))
        upgrade = client.get("/billing/status").json()["upgrade"]
        assert upgrade["recommended"] is True
        assert upgrade["recommended_plan_key"] == "professional"
        assert any("Alert delivery" in reason for reason in upgrade["reasons"])

    def test_upgrade_reasons_use_customer_language(self, env, org):
        client = _client(env, env.context(org))
        for reason in client.get("/billing/status").json()["upgrade"]["reasons"]:
            assert "entitlement" not in reason.lower()
            assert "_enabled" not in reason

    @run_async
    async def test_subscribed_status_reports_the_plan(self, env, org):
        await _activate_professional(env, org)
        client = _client(env, env.context(org))
        body = client.get("/billing/status").json()
        assert body["plan"]["key"] == "professional"
        assert body["plan"]["from_subscription"] is True
        assert body["subscription"]["status_label"] == "Active"
        assert body["subscription"]["capability_active"] is True

    @run_async
    async def test_subscribed_status_hides_stripe_identifiers(self, env, org):
        await _activate_professional(env, org)
        client = _client(env, env.context(org))
        text = client.get("/billing/status").text
        assert "sub_test_1" not in text
        assert "cus_test_1" not in text
        assert PRICE_PROFESSIONAL not in text

    @run_async
    async def test_professional_status_stops_recommending_upgrades(self, env, org):
        await _activate_professional(env, org)
        client = _client(env, env.context(org))
        upgrade = client.get("/billing/status").json()["upgrade"]
        assert upgrade["recommended"] is False
        assert upgrade["reasons"] == []

    @run_async
    async def test_over_limit_is_surfaced_after_a_downgrade(self, env, org):
        await _activate_professional(env, org)
        for index in range(3):
            env.add_area(org, name=f"Stand {index}", offset=index * 0.1)
        await env.entitlement_sync.sync_from_plan_key(
            org,
            plan_key="foundation",
            status="active",
        )
        client = _client(env, env.context(org))
        body = client.get("/billing/status").json()
        assert body["capacity"]["over_limit"] is True
        assert any("stays in place" in reason for reason in body["upgrade"]["reasons"])

    @run_async
    async def test_payment_attention_is_surfaced(self, env, org):
        await _activate_professional(env, org)
        subscription = await env.subscriptions.find_by_organization(org)
        await env.subscriptions.update(str(subscription.id), {"status": "past_due"})
        client = _client(env, env.context(org))
        body = client.get("/billing/status").json()
        assert body["subscription"]["payment_attention_required"] is True
        assert body["subscription"]["status_label"] == "Payment overdue"

    def test_status_reports_permissions(self, env, org):
        client = _client(env, env.context(org, role="member"))
        permissions = client.get("/billing/status").json()["permissions"]
        assert permissions == {"can_manage_billing": False, "can_view_billing": True}

    def test_status_reports_synchronization_state(self, env, org):
        client = _client(env, env.context(org))
        sync = client.get("/billing/status").json()["synchronization"]
        assert sync["billing_configured"] is False
        assert sync["failed_event_count"] == 0
        assert sync["subscription_synchronized"] is True

    @run_async
    async def test_synchronization_reports_the_last_billing_event(self, env, org):
        await _activate_professional(env, org)
        client = _client(env, env.context(org))
        sync = client.get("/billing/status").json()["synchronization"]
        assert sync["last_event_type"] == "customer.subscription.created"
        assert sync["last_event_at"] is not None

    def test_status_survives_an_unavailable_billing_provider(self, env, org):
        env.gateway.fail_next = True
        client = _client(env, env.context(org))
        assert client.get("/billing/status").status_code == 200


class TestOrganizationIsolation:
    @run_async
    async def test_status_never_leaks_another_organizations_plan(self, env, org):
        other = env.add_organization("Other Forestry")
        await _activate_professional(env, org)
        client = _client(env, env.context(other))
        body = client.get("/billing/status").json()
        assert body["plan"]["key"] == "foundation"
        assert body["subscription"] is None

    @run_async
    async def test_checkout_uses_the_resolved_organization_only(self, env, org):
        other = env.add_organization("Other Forestry")
        client = _client(env, env.context(other))
        client.post(
            "/billing/checkout",
            json={"plan_key": "professional"},
            headers={"X-Organization-Id": org},
        )
        session = env.gateway.checkout_sessions[-1]
        assert session["organization_id"] == other

    @run_async
    async def test_each_organization_gets_its_own_stripe_customer(self, env, org):
        other = env.add_organization("Other Forestry")
        for organization in (org, other):
            _client(env, env.context(organization)).post(
                "/billing/checkout",
                json={"plan_key": "professional"},
            )
        customer_ids = {
            record["stripe_customer_id"] for record in env.store.customers.values()
        }
        assert len(customer_ids) == 2


class TestCheckout:
    def test_valid_plan_returns_a_checkout_url(self, env, org):
        client = _client(env, env.context(org))
        body = client.post("/billing/checkout", json={"plan_key": "professional"}).json()
        assert body["plan_key"] == "professional"
        assert body["checkout_url"].startswith("https://")

    def test_checkout_uses_the_catalog_price(self, env, org):
        client = _client(env, env.context(org))
        client.post("/billing/checkout", json={"plan_key": "professional"})
        assert env.gateway.checkout_sessions[-1]["price_id"] == PRICE_PROFESSIONAL

    def test_checkout_urls_come_from_configuration(self, env, org):
        client = _client(env, env.context(org))
        client.post("/billing/checkout", json={"plan_key": "professional"})
        session = env.gateway.checkout_sessions[-1]
        assert session["success_url"].startswith("https://app.forestwatch.test/billing")
        assert "canceled" in session["cancel_url"]

    def test_unknown_plan_is_rejected(self, env, org):
        client = _client(env, env.context(org))
        assert client.post("/billing/checkout", json={"plan_key": "platinum"}).status_code == 400

    def test_contact_sales_plan_is_not_purchasable(self, env, org):
        client = _client(env, env.context(org))
        assert client.post("/billing/checkout", json={"plan_key": "enterprise"}).status_code == 400

    def test_stripe_price_id_is_not_accepted_as_a_plan_key(self, env, org):
        client = _client(env, env.context(org))
        resp = client.post("/billing/checkout", json={"plan_key": PRICE_PROFESSIONAL})
        assert resp.status_code == 400
        assert env.gateway.checkout_sessions == []

    def test_missing_plan_key_is_rejected(self, env, org):
        client = _client(env, env.context(org))
        assert client.post("/billing/checkout", json={}).status_code == 422

    def test_member_cannot_start_checkout(self, env, org):
        client = _client(env, env.context(org, role="member"))
        assert (
            client.post("/billing/checkout", json={"plan_key": "professional"}).status_code
            == 403
        )

    def test_admin_can_start_checkout(self, env, org):
        client = _client(env, env.context(org, role="admin"))
        assert (
            client.post("/billing/checkout", json={"plan_key": "professional"}).status_code
            == 200
        )

    def test_suspended_organization_cannot_start_checkout(self, env, org):
        env.suspend_organization(org)
        client = _client(env, env.context(org))
        assert (
            client.post("/billing/checkout", json={"plan_key": "professional"}).status_code
            == 403
        )

    def test_existing_stripe_customer_is_reused(self, env, org):
        client = _client(env, env.context(org))
        client.post("/billing/checkout", json={"plan_key": "professional"})
        client.post("/billing/checkout", json={"plan_key": "professional"})
        assert len(env.store.customers) == 1
        assert len(env.gateway.customers) == 1

    def test_unavailable_provider_returns_service_unavailable(self, env, org):
        env.gateway.configured = False
        client = _client(env, env.context(org))
        assert (
            client.post("/billing/checkout", json={"plan_key": "professional"}).status_code
            == 503
        )

    def test_provider_failure_is_reported_as_unavailable(self, env, org):
        env.gateway.fail_next = True
        client = _client(env, env.context(org))
        assert (
            client.post("/billing/checkout", json={"plan_key": "professional"}).status_code
            == 503
        )

    @run_async
    async def test_service_rejects_an_unpurchasable_plan(self, env, org):
        with pytest.raises(InvalidPlanError):
            await env.billing_svc.create_checkout_session(
                env.context(org),
                "enterprise",
            )

    @run_async
    async def test_service_rejects_a_member(self, env, org):
        with pytest.raises(ForbiddenError):
            await env.billing_svc.create_checkout_session(
                env.context(org, role="member"),
                "professional",
            )


class TestPortal:
    def test_portal_requires_an_existing_customer(self, env, org):
        client = _client(env, env.context(org))
        assert client.post("/billing/portal").status_code == 400

    def test_portal_returns_a_url_once_a_customer_exists(self, env, org):
        client = _client(env, env.context(org))
        client.post("/billing/checkout", json={"plan_key": "professional"})
        body = client.post("/billing/portal").json()
        assert body["portal_url"].startswith("https://")

    def test_portal_return_url_comes_from_configuration(self, env, org):
        client = _client(env, env.context(org))
        client.post("/billing/checkout", json={"plan_key": "professional"})
        client.post("/billing/portal")
        assert env.gateway.portal_sessions[-1]["return_url"].endswith("/billing")

    def test_member_cannot_open_the_portal(self, env, org):
        client_owner = _client(env, env.context(org))
        client_owner.post("/billing/checkout", json={"plan_key": "professional"})
        client_member = _client(env, env.context(org, role="member"))
        assert client_member.post("/billing/portal").status_code == 403

    def test_suspended_organization_cannot_open_the_portal(self, env, org):
        client = _client(env, env.context(org))
        client.post("/billing/checkout", json={"plan_key": "professional"})
        env.suspend_organization(org)
        assert client.post("/billing/portal").status_code == 403

    def test_portal_uses_the_organizations_own_customer(self, env, org):
        other = env.add_organization("Other Forestry")
        _client(env, env.context(org)).post(
            "/billing/checkout", json={"plan_key": "professional"}
        )
        _client(env, env.context(other)).post(
            "/billing/checkout", json={"plan_key": "professional"}
        )
        _client(env, env.context(other)).post("/billing/portal")
        expected = (
            env.store.customers[
                next(
                    key
                    for key, raw in env.store.customers.items()
                    if raw["organization_id"] == other
                )
            ]["stripe_customer_id"]
        )
        assert env.gateway.portal_sessions[-1]["customer_id"] == expected

    def test_unavailable_provider_blocks_the_portal(self, env, org):
        client = _client(env, env.context(org))
        client.post("/billing/checkout", json={"plan_key": "professional"})
        env.gateway.configured = False
        assert client.post("/billing/portal").status_code == 503

    @run_async
    async def test_service_raises_when_provider_is_down(self, env, org):
        env.gateway.configured = False
        with pytest.raises(BillingGatewayError):
            await env.billing_svc.create_portal_session(env.context(org))


class TestWebhookEndpoint:
    def test_signed_event_is_accepted(self, env, org):
        client = _client(env, env.context(org))
        payload = encode_event(subscription_event(organization_id=org))
        resp = client.post(
            "/billing/webhook/stripe",
            content=payload,
            headers=signed_headers(payload),
        )
        assert resp.status_code == 200
        assert resp.json() == {
            "received": True,
            "status": "processed",
            "event_type": "customer.subscription.created",
        }

    def test_unsigned_event_is_rejected(self, env, org):
        client = _client(env, env.context(org))
        payload = encode_event(subscription_event(organization_id=org))
        assert client.post("/billing/webhook/stripe", content=payload).status_code == 400

    def test_wrong_secret_is_rejected(self, env, org):
        client = _client(env, env.context(org))
        payload = encode_event(subscription_event(organization_id=org))
        resp = client.post(
            "/billing/webhook/stripe",
            content=payload,
            headers=signed_headers(payload, secret="whsec_attacker"),
        )
        assert resp.status_code == 400
        assert env.store.subscriptions == {}

    def test_duplicate_delivery_is_reported_as_duplicate(self, env, org):
        client = _client(env, env.context(org))
        payload = encode_event(subscription_event(organization_id=org))
        headers = signed_headers(payload)
        client.post("/billing/webhook/stripe", content=payload, headers=headers)
        resp = client.post("/billing/webhook/stripe", content=payload, headers=headers)
        assert resp.json()["status"] == "duplicate"

    def test_malformed_body_is_rejected(self, env, org):
        client = _client(env, env.context(org))
        payload = b"{not-json"
        resp = client.post(
            "/billing/webhook/stripe",
            content=payload,
            headers=signed_headers(payload),
        )
        assert resp.status_code == 400

    def test_webhook_response_reveals_nothing_sensitive(self, env, org):
        client = _client(env, env.context(org))
        payload = encode_event(subscription_event(organization_id=org))
        resp = client.post(
            "/billing/webhook/stripe",
            content=payload,
            headers=signed_headers(payload),
        )
        assert WEBHOOK_SECRET not in resp.text
        assert org not in resp.text

    def test_webhook_activates_capability_end_to_end(self, env, org):
        client = _client(env, env.context(org))
        payload = encode_event(subscription_event(organization_id=org))
        client.post("/billing/webhook/stripe", content=payload, headers=signed_headers(payload))
        body = client.get("/billing/status").json()
        assert body["plan"]["key"] == "professional"
        assert body["entitlements"]["alert_delivery_enabled"] is True
        assert body["capacity"]["monitored_area_limit"] == 5
