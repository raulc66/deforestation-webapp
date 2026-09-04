"""Interactive demonstration control plane — isolation, budget, reset, alerts."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "forestwatch_demo_test")
os.environ.setdefault("JWT_SECRET", "demo-test-secret-32-bytes-minimum")

from app.core.demo.catalog import AREAS, SCENARIOS, catalog_events
from app.core.demo.constants import (
    DEFAULT_DEMO_BUDGET,
    DEMO_ORGANIZATION_SLUG,
    DEMO_REQUESTS_PER_MINUTE,
    DEMO_USER_PROVIDER,
)
from app.core.demo.errors import DemoBudgetError, DemoRateLimitError
from app.core.demo.identity import (
    create_demo_token,
    demo_public_user,
    is_demo_organization,
    is_demo_user,
)
from app.core.errors import ForbiddenError, NotFoundError
from app.core.organization.organization_context import OrganizationContext
from app.models.customer_alert import AlertStage, alert_dedupe_key
from app.models.organization import Organization
from app.models.user import UserPublic
from app.services.demo.demo_alert_simulation_service import (
    DemoAlertSimulationService,
    demo_simulation_dedupe_key,
    delivery_visible_in_demo_session,
    visitor_scope_from_delivery,
)
from app.services.alert_policy_service import AlertPolicyService
from app.services.demo.demo_rate_limit import check_demo_rate, reset_demo_rate_limiter
from app.services.organization_context_service import OrganizationContextService
from fixtures.demo_fakes import (
    FakeAreaRepo,
    FakeChannelRepo,
    FakeDeliveryRepo,
    FakeIntelRepo,
    FakeMembershipRepo,
    FakeOrgRepo,
    FakePolicyRepo,
    build_catalog_and_sessions,
    run_async,
)


NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)


def _real_user() -> UserPublic:
    return UserPublic(
        id="user-real",
        email="owner@example.com",
        name="Real Owner",
        role="user",
        provider="local",
        created_at=NOW,
    )


class TestDemoCatalog:
    @run_async
    async def test_seed_is_deterministic_and_identifiable(self):
        store, catalog, _ = build_catalog_and_sessions()
        first = await catalog.ensure_seeded()
        second = await catalog.ensure_seeded()
        assert str(first.id) == str(second.id)
        assert first.slug == DEMO_ORGANIZATION_SLUG
        assert first.kind == "demo"
        assert is_demo_organization(first)
        assert len(store.areas) == len(AREAS)
        events = await FakeIntelRepo(store).find_active()
        assert len(events) == len(catalog_events())
        for event in events:
            assert (event.get("metadata") or {}).get("demo", {}).get("demo_catalog") is True
        assert {area["name"] for area in store.areas.values()} == {spec["name"] for spec in AREAS}

    @run_async
    async def test_reset_restores_catalog_events_only(self):
        store, catalog, _ = build_catalog_and_sessions()
        await catalog.ensure_seeded()
        customer_id = "evt-customer"
        store.events[customer_id] = {
            "id": customer_id,
            "status": "active",
            "region": "Elsewhere",
            "metadata": {},
        }
        await catalog.reset_catalog()
        ids = set(store.events)
        assert customer_id in ids
        demo_events = [
            event
            for event in store.events.values()
            if (event.get("metadata") or {}).get("demo", {}).get("demo_catalog")
        ]
        assert len(demo_events) == len(catalog_events())


class TestDemoSessionBudget:
    @run_async
    async def test_start_creates_session_and_token(self):
        _, _, sessions = build_catalog_and_sessions()
        user, token, status = await sessions.start()
        assert is_demo_user(user)
        assert user.provider == DEMO_USER_PROVIDER
        assert token
        assert status.budget.remaining["investigation"] == DEFAULT_DEMO_BUDGET["investigation"]
        assert status.reset_count == 0
        assert status.focused_scenario is None
        assert [item["id"] for item in status.scenarios] == [item["id"] for item in SCENARIOS]

    @run_async
    async def test_consume_and_exhaustion(self):
        _, _, sessions = build_catalog_and_sessions()
        user, _, _ = await sessions.start()
        session_id = str(user.id).removeprefix("demo:")
        for _ in range(DEFAULT_DEMO_BUDGET["investigation"]):
            await sessions.consume(session_id, "investigation")
        with pytest.raises(DemoBudgetError) as exc:
            await sessions.consume(session_id, "investigation")
        assert exc.value.code == "demo_budget_exhausted"
        assert "Create an organization" in exc.value.message

    @run_async
    async def test_navigation_is_not_metered(self):
        _, _, sessions = build_catalog_and_sessions()
        user, _, _ = await sessions.start()
        session_id = str(user.id).removeprefix("demo:")
        status = await sessions.status_for(session_id)
        assert status.budget.remaining["investigation"] == DEFAULT_DEMO_BUDGET["investigation"]
        await sessions.set_guide_step(session_id, "changed")
        refreshed = await sessions.status_for(session_id)
        assert refreshed.budget.remaining == status.budget.remaining

    @run_async
    async def test_reset_restores_budget_for_this_session(self):
        store, _, sessions = build_catalog_and_sessions()
        user, _, _ = await sessions.start()
        session_id = str(user.id).removeprefix("demo:")
        await sessions.consume(session_id, "investigation")
        await sessions.consume(session_id, "alert_simulation")
        status = await sessions.reset(session_id)
        assert status.budget.remaining["investigation"] == DEFAULT_DEMO_BUDGET["investigation"]
        assert status.guide_step == "forests"
        assert status.focused_scenario is None
        names = [row["event_name"] for row in store.product_events]
        assert "demo_started" in names
        assert "demo_reset" in names

    @run_async
    async def test_first_investigation_succeeds_on_new_session(self):
        _, _, sessions = build_catalog_and_sessions()
        user, _, status = await sessions.start()
        session_id = str(user.id).removeprefix("demo:")
        assert status.budget.remaining["investigation"] == DEFAULT_DEMO_BUDGET["investigation"]
        assert status.budget.exhausted is False
        await sessions.consume(session_id, "investigation")
        refreshed = await sessions.status_for(session_id)
        assert refreshed.budget.remaining["investigation"] == DEFAULT_DEMO_BUDGET["investigation"] - 1

    @run_async
    async def test_investigation_exhausts_only_after_allowed_uses(self):
        _, _, sessions = build_catalog_and_sessions()
        user, _, _ = await sessions.start()
        session_id = str(user.id).removeprefix("demo:")
        limit = DEFAULT_DEMO_BUDGET["investigation"]
        for used in range(limit):
            await sessions.consume(session_id, "investigation")
            remaining = (await sessions.status_for(session_id)).budget.remaining["investigation"]
            assert remaining == limit - used - 1
        with pytest.raises(DemoBudgetError) as exc:
            await sessions.consume(session_id, "investigation")
        assert exc.value.code == "demo_budget_exhausted"
        assert exc.value.status_code == 403

    @run_async
    async def test_repeated_start_resets_existing_session_instead_of_reusing_spent_budget(self):
        _, _, sessions = build_catalog_and_sessions()
        user, _, _ = await sessions.start()
        session_id = str(user.id).removeprefix("demo:")
        for _ in range(DEFAULT_DEMO_BUDGET["investigation"]):
            await sessions.consume(session_id, "investigation")
        again_user, _, status = await sessions.start(existing_session_id=session_id)
        assert str(again_user.id).removeprefix("demo:") == session_id
        assert status.budget.remaining["investigation"] == DEFAULT_DEMO_BUDGET["investigation"]
        assert status.reset_count == 1
        await sessions.consume(session_id, "investigation")
        refreshed = await sessions.status_for(session_id)
        assert refreshed.budget.remaining["investigation"] == DEFAULT_DEMO_BUDGET["investigation"] - 1

    @run_async
    async def test_start_without_existing_id_creates_a_new_session(self):
        _, _, sessions = build_catalog_and_sessions()
        first, _, _ = await sessions.start()
        second, _, _ = await sessions.start()
        assert str(first.id) != str(second.id)

    @run_async
    async def test_status_and_catalog_seed_do_not_consume_investigation(self):
        _, catalog, sessions = build_catalog_and_sessions()
        user, _, _ = await sessions.start()
        session_id = str(user.id).removeprefix("demo:")
        await catalog.ensure_seeded()
        await sessions.status_for(session_id)
        await sessions.set_guide_step(session_id, "investigate")
        remaining = (await sessions.status_for(session_id)).budget.remaining["investigation"]
        assert remaining == DEFAULT_DEMO_BUDGET["investigation"]


class _NoBootstrap:
    async def ensure_personal_organization(self, user_id: str):
        org = Organization(
            name="Personal",
            slug=f"personal-{user_id}",
            status="active",
        )
        org.id = f"personal-{user_id}"
        return org


class TestDemoIsolation:
    @run_async
    async def test_demo_user_cannot_open_another_organization(self):
        store, catalog, _ = build_catalog_and_sessions()
        demo_org = await catalog.ensure_seeded()
        customer = await FakeOrgRepo(store).insert(
            Organization(
                name="Carpathian Forestry",
                slug="carpathian-forestry",
                status="active",
                kind="customer",
            )
        )
        ctx_svc = OrganizationContextService(
            FakeOrgRepo(store), FakeMembershipRepo(store), _NoBootstrap()
        )
        demo_user = demo_public_user("sess-1")
        ctx = await ctx_svc.resolve(demo_user)
        assert ctx.is_demo is True
        assert ctx.organization_id == str(demo_org.id)
        with pytest.raises(ForbiddenError):
            await ctx_svc.resolve(demo_user, requested_organization_id=str(customer.id))

    @run_async
    async def test_real_user_cannot_open_demo_organization(self):
        store, catalog, _ = build_catalog_and_sessions()
        demo_org = await catalog.ensure_seeded()
        ctx_svc = OrganizationContextService(
            FakeOrgRepo(store), FakeMembershipRepo(store), _NoBootstrap()
        )
        with pytest.raises(ForbiddenError):
            await ctx_svc.resolve(_real_user(), requested_organization_id=str(demo_org.id))

    @run_async
    async def test_real_user_listings_omit_demo_org(self):
        store, catalog, _ = build_catalog_and_sessions()
        await catalog.ensure_seeded()
        ctx_svc = OrganizationContextService(
            FakeOrgRepo(store), FakeMembershipRepo(store), _NoBootstrap()
        )
        listed = await ctx_svc.list_accessible_organizations(_real_user())
        assert all(item["slug"] != DEMO_ORGANIZATION_SLUG for item in listed)

    @run_async
    async def test_demo_listings_are_demo_only(self):
        store, catalog, _ = build_catalog_and_sessions()
        await catalog.ensure_seeded()
        await FakeOrgRepo(store).insert(
            Organization(
                name="Other",
                slug="other-org",
                status="active",
            )
        )
        ctx_svc = OrganizationContextService(
            FakeOrgRepo(store), FakeMembershipRepo(store), _NoBootstrap()
        )
        listed = await ctx_svc.list_accessible_organizations(demo_public_user("sess-2"))
        assert [item["slug"] for item in listed] == [DEMO_ORGANIZATION_SLUG]


def _alert_service(store, catalog, sessions, delivery_repo=None):
    return DemoAlertSimulationService(
        sessions=sessions,
        catalog=catalog,
        policy_repo=FakePolicyRepo(store),
        channel_repo=FakeChannelRepo(store),
        delivery_repo=delivery_repo or FakeDeliveryRepo(store),
        intel_repo=FakeIntelRepo(store),
    )


class TestDemoAlertSimulation:
    @run_async
    async def test_simulate_writes_labelled_delivery_without_senders(self):
        store, catalog, sessions = build_catalog_and_sessions()
        user, _, _ = await sessions.start()
        session_id = str(user.id).removeprefix("demo:")
        alerts = _alert_service(store, catalog, sessions)
        result = await alerts.simulate(session_id)
        assert result["simulated"] is True
        assert result["already_recorded"] is False
        stored = next(iter(store.deliveries.values()))
        assert stored["delivery_results"][0]["simulated"] is True
        assert stored["lifecycle"] == "sent"
        assert "notification simulated" in stored["reason"].lower()
        assert "no message was sent" not in stored["reason"].lower()
        canonical = alert_dedupe_key(
            organization_id=stored["organization_id"],
            policy_id=stored["policy_id"],
            intelligence_event_id=stored["intelligence_event_id"],
            alert_stage=AlertStage.INITIAL.value,
        )
        assert stored["dedupe_key"] == demo_simulation_dedupe_key(canonical, session_id)
        assert stored["evidence_summary"]["demo_session_id"] == session_id
        assert stored["evidence_summary"]["demo_reset_count"] == 0
        names = [row["event_name"] for row in store.product_events]
        assert "alert_simulation_used" in names

    @run_async
    async def test_repeated_simulation_returns_existing_delivery(self):
        store, catalog, sessions = build_catalog_and_sessions()
        user, _, _ = await sessions.start()
        session_id = str(user.id).removeprefix("demo:")
        alerts = _alert_service(store, catalog, sessions)
        first = await alerts.simulate(session_id)
        second = await alerts.simulate(session_id)
        assert first["already_recorded"] is False
        assert second["already_recorded"] is True
        assert second["id"] == first["id"]
        assert second["simulated"] is True
        assert len(store.deliveries) == 1
        used = [row for row in store.product_events if row["event_name"] == "alert_simulation_used"]
        assert len(used) == 1

    @run_async
    async def test_concurrent_insert_race_returns_existing_not_duplicate_error(self):
        store, catalog, sessions = build_catalog_and_sessions()
        user, _, _ = await sessions.start()
        session_id = str(user.id).removeprefix("demo:")
        inner = FakeDeliveryRepo(store)

        class RaceOnLookup(FakeDeliveryRepo):
            def __init__(self):
                super().__init__(store)
                self._miss_once = True

            async def find_by_dedupe_key(self, dedupe_key: str):
                if self._miss_once:
                    self._miss_once = False
                    return None
                return await inner.find_by_dedupe_key(dedupe_key)

        alerts = _alert_service(store, catalog, sessions)
        first = await alerts.simulate(session_id)
        raced = _alert_service(store, catalog, sessions, delivery_repo=RaceOnLookup())
        second = await raced.simulate(session_id)
        assert first["already_recorded"] is False
        assert second["already_recorded"] is True
        assert second["id"] == first["id"]
        assert len(store.deliveries) == 1

    @run_async
    async def test_repeated_simulation_still_consumes_session_budget(self):
        store, catalog, sessions = build_catalog_and_sessions()
        user, _, _ = await sessions.start()
        session_id = str(user.id).removeprefix("demo:")
        alerts = _alert_service(store, catalog, sessions)
        first = await alerts.simulate(session_id)
        await sessions.consume(session_id, "alert_simulation")
        second = await alerts.simulate(session_id)
        await sessions.consume(session_id, "alert_simulation")
        assert first["already_recorded"] is False
        assert second["already_recorded"] is True
        status = await sessions.status_for(session_id)
        assert status.budget.remaining["alert_simulation"] == 0
        with pytest.raises(DemoBudgetError) as exc:
            await sessions.consume(session_id, "alert_simulation")
        assert exc.value.code == "demo_budget_exhausted"
        assert exc.value.status_code == 403
        assert len(store.deliveries) == 1

    @run_async
    async def test_cannot_simulate_against_non_demo_event(self):
        store, catalog, sessions = build_catalog_and_sessions()
        user, _, _ = await sessions.start()
        session_id = str(user.id).removeprefix("demo:")
        store.events["real-1"] = {
            "id": "real-1",
            "status": "active",
            "region": "Elsewhere",
            "metadata": {},
        }
        alerts = _alert_service(store, catalog, sessions)
        with pytest.raises(ForbiddenError):
            await alerts.simulate(session_id, event_id="real-1")

    @run_async
    async def test_failed_simulate_does_not_consume_alert_budget(self):
        store, catalog, sessions = build_catalog_and_sessions()
        user, _, _ = await sessions.start()
        session_id = str(user.id).removeprefix("demo:")
        alerts = _alert_service(store, catalog, sessions)
        with pytest.raises(NotFoundError):
            await alerts.simulate(session_id, event_id="missing-event")
            await sessions.consume(session_id, "alert_simulation")
        remaining = (await sessions.status_for(session_id)).budget.remaining[
            "alert_simulation"
        ]
        assert remaining == DEFAULT_DEMO_BUDGET["alert_simulation"]
        assert store.deliveries == {}


class TestDemoBillingGuard:
    @run_async
    async def test_demo_context_cannot_checkout(self):
        from fixtures.billing_fakes import build_environment

        env = build_environment()
        org_id = env.add_organization("Demo Guard")
        ctx = OrganizationContext(
            user=demo_public_user("sess-bill"),
            organization_id=org_id,
            organization_name="Demo Guard",
            organization_slug="demo-guard",
            membership_id="mem-demo",
            role="owner",
            membership_status="active",
            is_demo=True,
        )
        with pytest.raises(ForbiddenError):
            await env.billing_svc.create_checkout_session(ctx, "professional")
        with pytest.raises(ForbiddenError):
            await env.billing_svc.create_portal_session(ctx)


class TestDemoRateLimit:
    def test_in_process_limit(self):
        reset_demo_rate_limiter()
        for _ in range(DEMO_REQUESTS_PER_MINUTE):
            check_demo_rate("sess-rate", now=1_000_000.0)
        with pytest.raises(DemoRateLimitError):
            check_demo_rate("sess-rate", now=1_000_000.0)
        check_demo_rate("other-session", now=1_000_000.0)
        reset_demo_rate_limiter()


class TestDemoToken:
    def test_token_round_trip_type(self):
        from app.core.security import decode_token

        token = create_demo_token("sess-token")
        payload = decode_token(token)
        assert payload["type"] == "demo"
        assert payload["sub"] == "sess-token"


class _AllowAlerts:
    async def can_receive_alerts(self, organization_id: str) -> bool:
        return True


def _history_service(store):
    return AlertPolicyService(
        FakePolicyRepo(store),
        FakeChannelRepo(store),
        FakeDeliveryRepo(store),
        _AllowAlerts(),
        app_secret="demo-test-secret",
        area_repo=FakeAreaRepo(store),
    )


class TestDemoAlertHistoryIsolation:
    @run_async
    async def test_session_b_does_not_see_session_a_simulated_delivery(self):
        store, catalog, sessions = build_catalog_and_sessions()
        user_a, _, _ = await sessions.start()
        user_b, _, _ = await sessions.start()
        sid_a = str(user_a.id).removeprefix("demo:")
        sid_b = str(user_b.id).removeprefix("demo:")
        alerts = _alert_service(store, catalog, sessions)
        await alerts.simulate(sid_a)
        org = await catalog.ensure_seeded()
        history = _history_service(store)
        seen_a = await history.list_deliveries(
            str(org.id), demo_session_id=sid_a, demo_reset_count=0
        )
        seen_b = await history.list_deliveries(
            str(org.id), demo_session_id=sid_b, demo_reset_count=0
        )
        assert seen_a["total"] == 1
        assert seen_b["total"] == 0
        overview_b = await history.alert_operations_overview(
            str(org.id), demo_session_id=sid_b, demo_reset_count=0
        )
        assert overview_b.sent_count == 0
        assert overview_b.recent_deliveries == []

    @run_async
    async def test_session_b_sees_only_its_own_interactive_simulation(self):
        store, catalog, sessions = build_catalog_and_sessions()
        user_a, _, _ = await sessions.start()
        user_b, _, _ = await sessions.start()
        sid_a = str(user_a.id).removeprefix("demo:")
        sid_b = str(user_b.id).removeprefix("demo:")
        alerts = _alert_service(store, catalog, sessions)
        first = await alerts.simulate(sid_a)
        second = await alerts.simulate(sid_b)
        org = await catalog.ensure_seeded()
        history = _history_service(store)
        seen_b = await history.list_deliveries(
            str(org.id), demo_session_id=sid_b, demo_reset_count=0
        )
        assert seen_b["total"] == 1
        assert seen_b["items"][0].id == second["id"]
        assert seen_b["items"][0].id != first["id"]

    @run_async
    async def test_restart_hides_prior_interactive_history_for_the_same_session(self):
        store, catalog, sessions = build_catalog_and_sessions()
        user, _, _ = await sessions.start()
        session_id = str(user.id).removeprefix("demo:")
        alerts = _alert_service(store, catalog, sessions)
        prior = await alerts.simulate(session_id)
        await sessions.reset(session_id)
        refreshed = await sessions.require(session_id)
        assert refreshed.reset_count == 1
        org = await catalog.ensure_seeded()
        history = _history_service(store)
        after_reset = await history.list_deliveries(
            str(org.id),
            demo_session_id=session_id,
            demo_reset_count=refreshed.reset_count,
        )
        assert after_reset["total"] == 0
        fresh = await alerts.simulate(session_id)
        after_sim = await history.list_deliveries(
            str(org.id),
            demo_session_id=session_id,
            demo_reset_count=refreshed.reset_count,
        )
        assert after_sim["total"] == 1
        assert after_sim["items"][0].id == fresh["id"]
        assert after_sim["items"][0].id != prior["id"]

    @run_async
    async def test_curated_shared_fixture_remains_visible_to_every_session(self):
        from app.models.customer_alert import AlertDeliveryRecord, AlertLifecycle

        store, catalog, sessions = build_catalog_and_sessions()
        user_a, _, _ = await sessions.start()
        user_b, _, _ = await sessions.start()
        sid_a = str(user_a.id).removeprefix("demo:")
        sid_b = str(user_b.id).removeprefix("demo:")
        org = await catalog.ensure_seeded()
        now = datetime.now(timezone.utc)
        policies = list(store.policies.values())
        await FakeDeliveryRepo(store).create(
            AlertDeliveryRecord(
                dedupe_key=f"{org.id}:seed:evt-curated:initial",
                organization_id=str(org.id),
                policy_id=str(policies[0]["id"]),
                intelligence_event_id="evt-curated",
                alert_stage=AlertStage.INITIAL.value,
                reason="Seeded demonstration fixture.",
                evidence_summary={"simulated": True, "seeded": True},
                lifecycle=AlertLifecycle.SENT.value,
                created_at=now,
                updated_at=now,
            )
        )
        alerts = _alert_service(store, catalog, sessions)
        await alerts.simulate(sid_a)
        history = _history_service(store)
        seen_b = await history.list_deliveries(
            str(org.id), demo_session_id=sid_b, demo_reset_count=0
        )
        assert seen_b["total"] == 1
        assert seen_b["items"][0].intelligence_event_id == "evt-curated"
        seen_a = await history.list_deliveries(
            str(org.id), demo_session_id=sid_a, demo_reset_count=0
        )
        assert seen_a["total"] == 2

    @run_async
    async def test_production_history_is_unscoped_by_demo_session(self):
        from fixtures.customer_alert_fakes import build_alert_environment
        from app.models.customer_alert import AlertDeliveryRecord, AlertLifecycle

        env = build_alert_environment()
        channel_id = await env.add_email_channel("org-a")
        policy_id = await env.add_policy(
            "org-a",
            area_ids=[env.area_ids["org-a"]],
            channel_ids=[channel_id],
        )
        stored = await env.delivery_repo.create(
            AlertDeliveryRecord(
                dedupe_key="org-a:policy:evt-1:initial",
                organization_id="org-a",
                policy_id=policy_id,
                intelligence_event_id="evt-1",
                alert_stage=AlertStage.INITIAL.value,
                reason="Live delivery",
                lifecycle=AlertLifecycle.SENT.value,
            )
        )
        payload = await env.policy_svc.list_deliveries("org-a")
        scoped = await env.policy_svc.list_deliveries(
            "org-a", demo_session_id="sess-other", demo_reset_count=0
        )
        assert payload["total"] == 1
        assert scoped["total"] == 1
        assert payload["items"][0].id == scoped["items"][0].id == stored["id"]

    def test_http_demo_deliveries_hide_other_visitors(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.customer_alert_routes import router as customer_alert_router
        from app.api.deps import (
            alert_policy_service_dep,
            demo_session_service_dep,
            get_organization_context,
        )

        async def _setup():
            store, catalog, sessions = build_catalog_and_sessions()
            user_a, _, _ = await sessions.start()
            user_b, _, _ = await sessions.start()
            sid_a = str(user_a.id).removeprefix("demo:")
            org = await catalog.ensure_seeded()
            alerts = _alert_service(store, catalog, sessions)
            first = await alerts.simulate(sid_a)
            history = _history_service(store)
            return sessions, user_a, user_b, org, first, history

        sessions, user_a, user_b, org, first, history = run_async(_setup)()

        def _demo_ctx(user):
            return OrganizationContext(
                user=user,
                organization_id=str(org.id),
                organization_name=org.name,
                organization_slug=org.slug,
                membership_id="mem-demo",
                role="owner",
                membership_status="active",
                is_demo=True,
            )

        app = FastAPI()
        app.include_router(customer_alert_router, prefix="/api")
        app.dependency_overrides[demo_session_service_dep] = lambda: sessions
        app.dependency_overrides[alert_policy_service_dep] = lambda: history
        app.dependency_overrides[get_organization_context] = lambda: _demo_ctx(user_b)
        client = TestClient(app)
        hidden = client.get("/api/customer-alerts/deliveries")
        assert hidden.status_code == 200
        assert hidden.json()["items"] == []
        overview = client.get("/api/customer-alerts/overview").json()
        assert overview["sent_count"] == 0

        app.dependency_overrides[get_organization_context] = lambda: _demo_ctx(user_a)
        visible = client.get("/api/customer-alerts/deliveries")
        assert visible.status_code == 200
        assert visible.json()["total"] == 1
        assert visible.json()["items"][0]["id"] == first["id"]

    def test_legacy_demo_dedupe_key_encodes_session_without_reset_count(self):
        row = {
            "dedupe_key": "org:pol:evt:initial:demo:sess-legacy",
            "evidence_summary": {"simulated": True},
        }
        assert visitor_scope_from_delivery(row) == ("sess-legacy", 0)
        assert delivery_visible_in_demo_session(
            row, session_id="sess-legacy", reset_count=0
        )
        assert not delivery_visible_in_demo_session(
            row, session_id="sess-other", reset_count=0
        )
        assert not delivery_visible_in_demo_session(
            row, session_id="sess-legacy", reset_count=1
        )
