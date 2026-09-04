"""Alert history read models, operations overview, HTTP scope, scheduler isolation."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.customer_alert_routes import router as customer_alert_router
from app.api.deps import alert_policy_service_dep, get_current_user, get_organization_context
from app.core.organization.organization_context import OrganizationContext
from app.models.customer_alert import (
    AlertDeliveryRecord,
    AlertLifecycle,
    AlertStage,
)
from app.models.user import UserPublic
from fixtures.customer_alert_fakes import (
    NOW,
    FailingEmailSender,
    build_alert_environment,
    make_disturbance_event,
    run_async,
)


@pytest.fixture
def env():
    return build_alert_environment()


@pytest.fixture
def two_orgs():
    return build_alert_environment(
        organizations=(("org-a", "Northern Forestry"), ("org-b", "Carpathian Trust"))
    )


def _user(user_id: str = "user-a") -> UserPublic:
    return UserPublic(
        id=user_id,
        email=f"{user_id}@example.com",
        name="Test User",
        role="admin",
        provider="local",
        created_at=NOW,
    )


def _org_ctx(org_id: str, role: str = "owner") -> OrganizationContext:
    return OrganizationContext(
        user=_user(),
        organization_id=org_id,
        organization_name="Northern Forestry",
        organization_slug="northern-forestry",
        membership_id="mem-1",
        role=role,
        membership_status="active",
    )


def _client(environment, *, org_id: str = "org-a", role: str = "owner") -> TestClient:
    app = FastAPI()
    app.include_router(customer_alert_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_organization_context] = lambda: _org_ctx(org_id, role)
    app.dependency_overrides[alert_policy_service_dep] = lambda: environment.policy_svc
    return TestClient(app)


async def _delivered_alert(environment, org_id: str = "org-a", **policy_kwargs):
    channel_id = await environment.add_email_channel(org_id)
    policy_id = await environment.add_policy(
        org_id,
        area_ids=[environment.area_ids[org_id]],
        channel_ids=[channel_id],
        **policy_kwargs,
    )
    await environment.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
    await environment.dispatcher.dispatch_pending()
    return policy_id, channel_id


class TestDeliveryHistoryReadModel:
    @run_async
    async def test_history_contains_the_delivered_alert(self, env):
        await _delivered_alert(env)
        payload = await env.policy_svc.list_deliveries("org-a")
        assert payload["total"] == 1
        assert payload["items"][0].lifecycle == AlertLifecycle.SENT.value

    @run_async
    async def test_history_resolves_the_policy_name(self, env):
        await _delivered_alert(env, name="Harghita watch")
        item = (await env.policy_svc.list_deliveries("org-a"))["items"][0]
        assert item.policy_name == "Harghita watch"

    @run_async
    async def test_history_resolves_monitored_area_names(self, env):
        await _delivered_alert(env)
        item = (await env.policy_svc.list_deliveries("org-a"))["items"][0]
        assert item.monitored_area_names == ["Northern Forestry AOI"]

    @run_async
    async def test_history_labels_the_stage(self, env):
        await _delivered_alert(env)
        item = (await env.policy_svc.list_deliveries("org-a"))["items"][0]
        assert item.alert_stage == AlertStage.INITIAL.value
        assert item.alert_stage_label == "Initial alert"

    @run_async
    async def test_history_labels_the_delivery_state(self, env):
        await _delivered_alert(env)
        item = (await env.policy_svc.list_deliveries("org-a"))["items"][0]
        assert item.delivery_state_label == "Delivered"

    @run_async
    async def test_history_reports_channel_outcomes(self, env):
        await _delivered_alert(env)
        item = (await env.policy_svc.list_deliveries("org-a"))["items"][0]
        assert len(item.channel_outcomes) == 1
        outcome = item.channel_outcomes[0]
        assert outcome.delivered is True
        assert outcome.simulated is False
        assert outcome.channel_type_label == "Email channel"
        assert outcome.channel_name == "Operations inbox"

    @run_async
    async def test_simulated_demo_delivery_is_not_mapped_as_channel_failure(self, env):
        channel_id = await env.add_email_channel("org-a")
        policy_id = await env.add_policy(
            "org-a",
            area_ids=[env.area_ids["org-a"]],
            channel_ids=[channel_id],
        )
        await env.delivery_repo.create(
            AlertDeliveryRecord(
                dedupe_key="org-a:demo:evt-demo:initial",
                organization_id="org-a",
                policy_id=policy_id,
                intelligence_event_id="evt-demo",
                alert_stage=AlertStage.INITIAL.value,
                reason="Demonstration notification simulated.",
                evidence_summary={
                    "simulated": True,
                    "incident_category": "forest_disturbance",
                },
                lifecycle=AlertLifecycle.SENT.value,
                created_at=NOW,
                updated_at=NOW,
                sent_at=NOW,
                delivery_results=[
                    {
                        "channel_type": "email",
                        "channel_name": "Demonstration inbox",
                        "status": "simulated",
                        "simulated": True,
                    }
                ],
            )
        )
        item = (await env.policy_svc.list_deliveries("org-a"))["items"][0]
        assert item.lifecycle == AlertLifecycle.SENT.value
        assert item.delivery_state_label == "Delivered"
        assert item.simulated is True
        assert item.channel_outcomes[0].simulated is True
        assert item.channel_outcomes[0].delivered is False
        assert item.channel_outcomes[0].failure_reason is None
        assert item.channel_outcomes[0].channel_name == "Demonstration inbox"

    @run_async
    async def test_history_reports_sent_timestamp_and_attempt_count(self, env):
        await _delivered_alert(env)
        item = (await env.policy_svc.list_deliveries("org-a"))["items"][0]
        assert item.sent_at is not None
        assert item.dispatch_attempt_count == 1
        assert item.last_attempt_at is not None

    @run_async
    async def test_failed_history_entry_has_no_sent_time(self, env):
        environment = build_alert_environment(email_sender=FailingEmailSender())
        await _delivered_alert(environment)
        item = (await environment.policy_svc.list_deliveries("org-a"))["items"][0]
        assert item.lifecycle == AlertLifecycle.FAILED.value
        assert item.sent_at is None
        assert item.delivery_state_label == "Delivery failed"
        assert item.simulated is False
        assert item.channel_outcomes[0].simulated is False
        assert item.channel_outcomes[0].failure_reason == "smtp_unavailable"

    @run_async
    async def test_suppressed_history_entry_explains_the_reason(self, env):
        policy_id, _ = await _delivered_alert(env)
        env.store.events["evt-2"] = make_disturbance_event("evt-2")
        await env.delivery_repo.create(
            AlertDeliveryRecord(
                dedupe_key=f"org-a:{policy_id}:evt-2:initial",
                organization_id="org-a",
                policy_id=policy_id,
                intelligence_event_id="evt-2",
                alert_stage=AlertStage.INITIAL.value,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        await env.policy_repo.update(policy_id, {"enabled": False})
        await env.dispatcher.dispatch_pending()

        suppressed = [
            item
            for item in (await env.policy_svc.list_deliveries("org-a"))["items"]
            if item.lifecycle == AlertLifecycle.SUPPRESSED.value
        ]
        assert len(suppressed) == 1
        assert suppressed[0].suppression_reason_label == (
            "Alert policy was turned off before delivery"
        )

    @run_async
    async def test_history_is_filtered_by_delivery_state(self, env):
        await _delivered_alert(env)
        sent = await env.policy_svc.list_deliveries("org-a", lifecycle="sent")
        failed = await env.policy_svc.list_deliveries("org-a", lifecycle="failed")
        assert sent["total"] == 1
        assert failed["total"] == 0

    @run_async
    async def test_history_limit_is_bounded(self, env):
        await _delivered_alert(env)
        payload = await env.policy_svc.list_deliveries("org-a", limit=10_000)
        assert payload["total"] == 1

    @run_async
    async def test_history_never_returns_evidence_of_another_organization(self, two_orgs):
        await _delivered_alert(two_orgs, "org-a")
        await _delivered_alert(two_orgs, "org-b")
        org_a = await two_orgs.policy_svc.list_deliveries("org-a")
        assert all(item.organization_id == "org-a" for item in org_a["items"])
        assert len(org_a["items"]) == 1

    @run_async
    async def test_history_of_organization_without_alerts_is_empty(self, two_orgs):
        await _delivered_alert(two_orgs, "org-a")
        payload = await two_orgs.policy_svc.list_deliveries("org-b")
        assert payload["items"] == []

    @run_async
    async def test_history_never_contains_secret_material(self, env):
        webhook = await env.add_webhook_channel("org-a", secret="plain-secret")
        await env.add_policy(
            "org-a", area_ids=[env.area_ids["org-a"]], channel_ids=[webhook]
        )
        await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        await env.dispatcher.dispatch_pending()

        payload = await env.policy_svc.list_deliveries("org-a")
        serialized = payload["items"][0].model_dump_json()
        assert "plain-secret" not in serialized


class TestAlertOperationsOverview:
    @run_async
    async def test_overview_counts_policies_and_channels(self, env):
        await _delivered_alert(env)
        overview = await env.policy_svc.alert_operations_overview("org-a", actor_role="owner")
        assert overview.policy_count == 1
        assert overview.active_policy_count == 1
        assert overview.channel_count == 1
        assert overview.enabled_channel_count == 1

    @run_async
    async def test_overview_counts_delivery_states(self, env):
        await _delivered_alert(env)
        overview = await env.policy_svc.alert_operations_overview("org-a", actor_role="owner")
        assert overview.sent_count == 1
        assert overview.failed_count == 0
        assert overview.attention_count == 0

    @run_async
    async def test_overview_flags_failed_deliveries_as_attention(self, env):
        environment = build_alert_environment(email_sender=FailingEmailSender())
        await _delivered_alert(environment)
        overview = await environment.policy_svc.alert_operations_overview(
            "org-a", actor_role="owner"
        )
        assert overview.failed_count == 1
        assert overview.attention_count == 1

    @run_async
    async def test_overview_reports_channel_states(self, env):
        await env.add_email_channel("org-a", name="Primary inbox")
        await env.add_webhook_channel("org-a", enabled=False)
        overview = await env.policy_svc.alert_operations_overview("org-a", actor_role="owner")
        states = {state["name"]: state for state in overview.channel_states}
        assert states["Primary inbox"]["enabled"] is True
        assert states["Primary inbox"]["channel_type_label"] == "Email channel"
        assert states["Field webhook"]["enabled"] is False
        assert states["Field webhook"]["configured"] is True

    @run_async
    async def test_overview_reports_entitlement_as_availability(self, env):
        env.store.set_alert_entitlement("org-a", False)
        overview = await env.policy_svc.alert_operations_overview("org-a", actor_role="owner")
        assert overview.alert_delivery_available is False

    @run_async
    async def test_overview_reports_read_only_for_members(self, env):
        overview = await env.policy_svc.alert_operations_overview("org-a", actor_role="member")
        assert overview.can_manage is False

    @run_async
    async def test_overview_includes_recent_deliveries(self, env):
        await _delivered_alert(env)
        overview = await env.policy_svc.alert_operations_overview("org-a", actor_role="owner")
        assert len(overview.recent_deliveries) == 1
        assert overview.recent_deliveries[0].policy_name is not None

    @run_async
    async def test_overview_is_organization_scoped(self, two_orgs):
        await _delivered_alert(two_orgs, "org-a")
        overview = await two_orgs.policy_svc.alert_operations_overview(
            "org-b", actor_role="owner"
        )
        assert overview.policy_count == 0
        assert overview.sent_count == 0
        assert overview.recent_deliveries == []

    @run_async
    async def test_overview_counts_disabled_policy_separately(self, env):
        policy_id, _ = await _delivered_alert(env)
        await env.policy_repo.update(policy_id, {"enabled": False})
        overview = await env.policy_svc.alert_operations_overview("org-a", actor_role="owner")
        assert overview.policy_count == 1
        assert overview.active_policy_count == 0


class TestCustomerAlertRoutes:
    def test_options_endpoint_exposes_configurable_vocabulary(self, env):
        body = _client(env).get("/api/customer-alerts/options").json()
        categories = {item["value"] for item in body["incident_categories"]}
        assert "forest_disturbance" in categories
        assert body["channel_types"] == ["email", "webhook"]
        assert "unknown" not in categories

    def test_options_labels_are_display_names(self, env):
        body = _client(env).get("/api/customer-alerts/options").json()
        labels = {item["value"]: item["label"] for item in body["incident_categories"]}
        assert labels["forest_disturbance"] == "Forest Disturbance"

    def test_policy_list_is_scoped_to_the_request_organization(self, two_orgs):
        client_a = _client(two_orgs, org_id="org-a")
        client_b = _client(two_orgs, org_id="org-b")
        created = client_a.post(
            "/api/customer-alerts/policies", json={"name": "Org A watch"}
        )
        assert created.status_code == 201

        assert client_a.get("/api/customer-alerts/policies").json()["total"] == 1
        assert client_b.get("/api/customer-alerts/policies").json()["total"] == 0

    def test_member_receives_forbidden_on_policy_create(self, env):
        response = _client(env, role="member").post(
            "/api/customer-alerts/policies", json={"name": "Nope"}
        )
        assert response.status_code == 403

    def test_member_policy_list_reports_read_only(self, env):
        body = _client(env, role="member").get("/api/customer-alerts/policies").json()
        assert body["can_manage"] is False

    def test_invalid_policy_payload_returns_422(self, env):
        response = _client(env).post(
            "/api/customer-alerts/policies",
            json={"name": "Bad", "incident_categories": ["not_a_category"]},
        )
        assert response.status_code == 422

    def test_policy_activation_toggle(self, env):
        client = _client(env)
        policy_id = client.post(
            "/api/customer-alerts/policies", json={"name": "Watch"}
        ).json()["id"]
        response = client.post(
            f"/api/customer-alerts/policies/{policy_id}/activation",
            params={"enabled": False},
        )
        assert response.status_code == 200
        assert response.json()["enabled"] is False

    def test_policy_delete_returns_no_content(self, env):
        client = _client(env)
        policy_id = client.post(
            "/api/customer-alerts/policies", json={"name": "Watch"}
        ).json()["id"]
        assert client.delete(f"/api/customer-alerts/policies/{policy_id}").status_code == 204

    def test_unknown_policy_returns_404(self, env):
        assert _client(env).get("/api/customer-alerts/policies/missing").status_code == 404

    def test_channel_create_never_echoes_the_secret(self, env):
        response = _client(env).post(
            "/api/customer-alerts/channels",
            json={
                "channel_type": "webhook",
                "name": "Hook",
                "config": {"url": "https://example.com/hook", "secret_token": "plain-secret"},
            },
        )
        assert response.status_code == 201
        assert "plain-secret" not in response.text
        assert response.json()["config"]["secret_configured"] is True

    def test_channel_list_is_organization_scoped(self, two_orgs):
        client_a = _client(two_orgs, org_id="org-a")
        client_b = _client(two_orgs, org_id="org-b")
        client_a.post(
            "/api/customer-alerts/channels",
            json={
                "channel_type": "email",
                "name": "Ops",
                "config": {"recipients": ["ops@example.com"]},
            },
        )
        assert client_a.get("/api/customer-alerts/channels").json()["total"] == 1
        assert client_b.get("/api/customer-alerts/channels").json()["total"] == 0

    def test_channel_activation_toggle(self, env):
        client = _client(env)
        channel_id = client.post(
            "/api/customer-alerts/channels",
            json={
                "channel_type": "email",
                "name": "Ops",
                "config": {"recipients": ["ops@example.com"]},
            },
        ).json()["id"]
        response = client.post(
            f"/api/customer-alerts/channels/{channel_id}/activation",
            params={"enabled": False},
        )
        assert response.json()["enabled"] is False

    def test_insecure_webhook_url_returns_422(self, env):
        response = _client(env).post(
            "/api/customer-alerts/channels",
            json={
                "channel_type": "webhook",
                "name": "Hook",
                "config": {"url": "http://example.com/hook"},
            },
        )
        assert response.status_code == 422

    def test_deliveries_endpoint_rejects_unknown_status_filter(self, env):
        response = _client(env).get(
            "/api/customer-alerts/deliveries", params={"lifecycle": "exploded"}
        )
        assert response.status_code == 422

    def test_deliveries_endpoint_accepts_known_status_filter(self, env):
        response = _client(env).get(
            "/api/customer-alerts/deliveries", params={"lifecycle": "sent"}
        )
        assert response.status_code == 200
        assert response.json()["items"] == []

    def test_overview_endpoint_returns_operational_projection(self, env):
        body = _client(env).get("/api/customer-alerts/overview").json()
        assert body["alert_delivery_available"] is True
        assert body["can_manage"] is True
        assert body["attention_count"] == 0

    def test_overview_endpoint_reports_unavailable_delivery(self, env):
        env.store.set_alert_entitlement("org-a", False)
        body = _client(env).get("/api/customer-alerts/overview").json()
        assert body["alert_delivery_available"] is False

    def test_no_response_leaks_internal_entitlement_keys(self, env):
        client = _client(env)
        for path in ("/api/customer-alerts/overview", "/api/customer-alerts/policies"):
            assert "alert_delivery_enabled" not in client.get(path).text


class TestSchedulerFailureIsolation:
    @run_async
    async def test_customer_alerting_never_raises_into_the_cycle(self, env):
        class ExplodingEvaluation:
            async def evaluate_cycle(self, **kwargs):
                raise RuntimeError("evaluation blew up")

        env.notification._evaluation = ExplodingEvaluation()
        result = await env.notification.run_post_reconciliation(
            active_events=[make_disturbance_event()]
        )
        assert result["evaluation"]["candidates_created"] == 0
        assert result["dispatch"]["attempted"] == 0

    @run_async
    async def test_email_failure_leaves_other_organizations_unaffected(self, two_orgs):
        environment = build_alert_environment(
            email_sender=FailingEmailSender(),
            organizations=(("org-a", "Northern Forestry"), ("org-b", "Carpathian Trust")),
        )
        for org_id in ("org-a", "org-b"):
            channel_id = await environment.add_email_channel(org_id)
            await environment.add_policy(
                org_id,
                area_ids=[environment.area_ids[org_id]],
                channel_ids=[channel_id],
            )
        stats = await environment.notification.run_post_reconciliation(
            active_events=[make_disturbance_event()]
        )
        assert stats["dispatch"]["attempted"] == 2
        assert stats["dispatch"]["failed"] == 2
        assert len(environment.deliveries_for("org-a")) == 1
        assert len(environment.deliveries_for("org-b")) == 1

    @run_async
    async def test_scheduler_owns_resolution_snapshot(self):
        """The scheduler tracks its own previous-cycle events for resolutions."""
        from app.services.scheduler_service import SchedulerService

        assert "_prev_customer_alert_active" in SchedulerService.__init__.__code__.co_names

    @run_async
    async def test_alerting_does_not_write_intelligence_events(self, env):
        await _delivered_alert(env)
        assert set(env.store.events) == {"evt-1"}
        assert env.store.events["evt-1"]["status"] == "active"

    @run_async
    async def test_alerting_does_not_mutate_monitored_areas(self, env):
        before = {k: dict(v) for k, v in env.store.areas.items()}
        await _delivered_alert(env)
        assert env.store.areas == before

    def test_timestamps_are_timezone_aware(self):
        assert NOW.tzinfo is timezone.utc
        assert datetime.now(timezone.utc).utcoffset() is not None


class TestPolicyCreateThroughApiRemainsDeterministic:
    def test_repeated_creation_produces_distinct_policies(self, env):
        client = _client(env)
        first = client.post("/api/customer-alerts/policies", json={"name": "Watch"}).json()
        second = client.post("/api/customer-alerts/policies", json={"name": "Watch"}).json()
        assert first["id"] != second["id"]
        assert client.get("/api/customer-alerts/policies").json()["total"] == 2

    def test_created_policy_is_returned_by_list(self, env):
        client = _client(env)
        created = client.post(
            "/api/customer-alerts/policies",
            json={"name": "Harghita", "cooldown_minutes": 30},
        ).json()
        listed = client.get("/api/customer-alerts/policies").json()["items"]
        assert listed[0]["id"] == created["id"]
        assert listed[0]["cooldown_minutes"] == 30

    def test_policy_create_defaults_to_forest_disturbance(self, env):
        created = _client(env).post(
            "/api/customer-alerts/policies", json={"name": "Default"}
        ).json()
        assert created["incident_categories"] == ["forest_disturbance"]
