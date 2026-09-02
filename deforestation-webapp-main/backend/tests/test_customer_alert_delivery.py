"""Customer alert reliability: dedupe, cooldown, escalation, resolution, isolation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.customer_alert import (
    AlertDeliveryRecord,
    AlertLifecycle,
    AlertStage,
    alert_dedupe_key,
)
from fixtures.customer_alert_fakes import (
    NOW,
    FailingEmailSender,
    RaisingEmailSender,
    RecordingWebhookSender,
    build_alert_environment,
    make_disturbance_event,
    polygon_harghita,
    polygon_maramures,
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


async def _configured_policy(environment, org_id="org-a", **policy_kwargs):
    channel_id = await environment.add_email_channel(org_id)
    policy_id = await environment.add_policy(
        org_id,
        area_ids=[environment.area_ids[org_id]],
        channel_ids=[channel_id],
        **policy_kwargs,
    )
    return policy_id, channel_id


class TestAlertIdentity:
    def test_dedupe_key_is_org_policy_event_stage(self):
        assert (
            alert_dedupe_key(
                organization_id="org-a",
                policy_id="policy-1",
                intelligence_event_id="evt-1",
                alert_stage=AlertStage.INITIAL.value,
            )
            == "org-a:policy-1:evt-1:initial"
        )

    def test_dedupe_key_differs_per_stage(self):
        base = {
            "organization_id": "org-a",
            "policy_id": "policy-1",
            "intelligence_event_id": "evt-1",
        }
        keys = {
            alert_dedupe_key(**base, alert_stage=stage.value) for stage in AlertStage
        }
        assert len(keys) == 3

    def test_dedupe_key_differs_per_organization(self):
        first = alert_dedupe_key(
            organization_id="org-a",
            policy_id="policy-1",
            intelligence_event_id="evt-1",
            alert_stage=AlertStage.INITIAL.value,
        )
        second = alert_dedupe_key(
            organization_id="org-b",
            policy_id="policy-1",
            intelligence_event_id="evt-1",
            alert_stage=AlertStage.INITIAL.value,
        )
        assert first != second

    def test_failed_is_not_dispatchable(self):
        from app.models.customer_alert import DISPATCHABLE_LIFECYCLES

        assert AlertLifecycle.PENDING.value in DISPATCHABLE_LIFECYCLES
        assert AlertLifecycle.FAILED.value not in DISPATCHABLE_LIFECYCLES
        assert AlertLifecycle.SENT.value not in DISPATCHABLE_LIFECYCLES


class TestInitialAlert:
    @run_async
    async def test_qualifying_event_creates_one_initial_delivery(self, env):
        policy_id, _ = await _configured_policy(env)
        stats = await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])

        assert stats["initial_created"] == 1
        assert await env.delivery_repo.find_by_dedupe_key(
            alert_dedupe_key(
                organization_id="org-a",
                policy_id=policy_id,
                intelligence_event_id="evt-1",
                alert_stage=AlertStage.INITIAL.value,
            )
        )

    @run_async
    async def test_initial_delivery_starts_pending(self, env):
        await _configured_policy(env)
        await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        record = env.deliveries_for("org-a")[0]
        assert record["lifecycle"] == AlertLifecycle.PENDING.value
        assert record["sent_at"] is None
        assert record["dispatch_attempt_count"] == 0

    @run_async
    async def test_initial_delivery_records_monitored_area(self, env):
        await _configured_policy(env)
        await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        record = env.deliveries_for("org-a")[0]
        assert record["monitored_area_ids"] == [env.area_ids["org-a"]]

    @run_async
    async def test_event_outside_monitored_area_creates_nothing(self, env):
        await _configured_policy(env)
        stats = await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event(latitude=10.0, longitude=10.0)]
        )
        assert stats["candidates_created"] == 0
        assert env.deliveries_for("org-a") == []

    @run_async
    async def test_priority_below_threshold_creates_nothing(self, env):
        await _configured_policy(env, minimum_investigation_priority="critical")
        stats = await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event(priority="medium")]
        )
        assert stats["candidates_created"] == 0

    @run_async
    async def test_severity_below_threshold_creates_nothing(self, env):
        await _configured_policy(env, minimum_severity="critical")
        stats = await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event(severity="medium")]
        )
        assert stats["candidates_created"] == 0

    @run_async
    async def test_category_outside_policy_creates_nothing(self, env):
        await _configured_policy(env, incident_categories=["wildfire"])
        stats = await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        assert stats["candidates_created"] == 0

    @run_async
    async def test_policy_scoped_to_other_area_creates_nothing(self, env):
        other_area = env.store.add_area("org-a", "Unrelated AOI", polygon_maramures())
        channel_id = await env.add_email_channel("org-a")
        await env.add_policy("org-a", area_ids=[other_area], channel_ids=[channel_id])
        stats = await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        assert stats["candidates_created"] == 0

    @run_async
    async def test_policy_without_area_filter_matches_any_monitored_area(self, env):
        channel_id = await env.add_email_channel("org-a")
        await env.add_policy("org-a", area_ids=[], channel_ids=[channel_id])
        stats = await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        assert stats["initial_created"] == 1


class TestDuplicateSchedulerCycles:
    @run_async
    async def test_repeated_cycles_create_one_delivery(self, env):
        await _configured_policy(env)
        event = make_disturbance_event()
        first = await env.evaluation.evaluate_cycle(active_events=[event])
        second = await env.evaluation.evaluate_cycle(active_events=[event])
        third = await env.evaluation.evaluate_cycle(active_events=[event])

        assert first["initial_created"] == 1
        assert second["candidates_created"] == 0
        assert third["candidates_created"] == 0
        assert len(env.deliveries_for("org-a")) == 1

    @run_async
    async def test_ten_repeated_cycles_are_deterministic(self, env):
        await _configured_policy(env)
        event = make_disturbance_event()
        created = [
            (await env.evaluation.evaluate_cycle(active_events=[event]))["candidates_created"]
            for _ in range(10)
        ]
        assert created == [1] + [0] * 9

    @run_async
    async def test_dispatch_is_not_repeated_after_send(self, env):
        await _configured_policy(env)
        await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        first = await env.dispatcher.dispatch_pending()
        second = await env.dispatcher.dispatch_pending()
        assert first["sent"] == 1
        assert second["attempted"] == 0
        assert len(env.email.sent) == 1

    @run_async
    async def test_failed_delivery_is_not_retried(self, env):
        environment = build_alert_environment(email_sender=FailingEmailSender())
        await _configured_policy(environment)
        await environment.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])

        first = await environment.dispatcher.dispatch_pending()
        second = await environment.dispatcher.dispatch_pending()
        assert first["failed"] == 1
        assert second["attempted"] == 0
        assert len(environment.email.attempts) == 1


class TestCooldown:
    """Monitored-area enrichment raises priority one level, so a policy-visible
    escalation means the raw event moved from ``medium`` to ``high``."""

    @run_async
    async def test_escalation_inside_cooldown_is_suppressed(self, env):
        await _configured_policy(env, cooldown_minutes=60)
        await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event(priority="medium")]
        )
        await env.dispatcher.dispatch_pending()

        stats = await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event(priority="high")]
        )
        assert stats["suppressed_cooldown"] == 1
        assert stats["escalation_created"] == 0

    @run_async
    async def test_escalation_after_cooldown_is_created(self, env):
        await _configured_policy(env, cooldown_minutes=60)
        await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event(priority="medium")],
            now=NOW,
        )
        await env.dispatcher.dispatch_pending()

        stats = await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event(priority="high")],
            now=NOW + timedelta(minutes=90),
        )
        assert stats["escalation_created"] == 1

    @run_async
    async def test_zero_cooldown_never_suppresses(self, env):
        await _configured_policy(env, cooldown_minutes=0)
        await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event(priority="medium")]
        )
        await env.dispatcher.dispatch_pending()

        stats = await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event(priority="high")]
        )
        assert stats["suppressed_cooldown"] == 0
        assert stats["escalation_created"] == 1

    @run_async
    async def test_new_event_in_same_area_is_suppressed_inside_cooldown(self, env):
        await _configured_policy(env, cooldown_minutes=600)
        env.store.events["evt-2"] = make_disturbance_event("evt-2")
        await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event("evt-1")], now=NOW
        )
        stats = await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event("evt-2")],
            now=NOW + timedelta(minutes=5),
        )
        assert stats["suppressed_cooldown"] == 1
        assert stats["initial_created"] == 0

    @run_async
    async def test_new_event_in_same_area_is_delivered_after_cooldown(self, env):
        await _configured_policy(env, cooldown_minutes=60)
        env.store.events["evt-2"] = make_disturbance_event("evt-2")
        await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event("evt-1")], now=NOW
        )
        stats = await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event("evt-2")],
            now=NOW + timedelta(minutes=90),
        )
        assert stats["initial_created"] == 1

    @run_async
    async def test_cooldown_does_not_leak_between_policies(self, env):
        channel_id = await env.add_email_channel("org-a")
        await env.add_policy(
            "org-a",
            name="Policy one",
            area_ids=[env.area_ids["org-a"]],
            channel_ids=[channel_id],
            cooldown_minutes=600,
        )
        await env.add_policy(
            "org-a",
            name="Policy two",
            area_ids=[env.area_ids["org-a"]],
            channel_ids=[channel_id],
            cooldown_minutes=600,
        )
        stats = await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event()], now=NOW
        )
        assert stats["initial_created"] == 2
        assert stats["suppressed_cooldown"] == 0

    @run_async
    async def test_cooldown_does_not_leak_between_organizations(self, two_orgs):
        for org_id in ("org-a", "org-b"):
            await _configured_policy(two_orgs, org_id=org_id, cooldown_minutes=600)
        stats = await two_orgs.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event()], now=NOW
        )
        assert stats["initial_created"] == 2
        assert stats["suppressed_cooldown"] == 0


class TestEscalation:
    @run_async
    async def test_priority_increase_creates_escalation(self, env):
        policy_id, _ = await _configured_policy(env)
        await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event(priority="medium")]
        )
        await env.dispatcher.dispatch_pending()

        stats = await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event(priority="high")]
        )
        assert stats["escalation_created"] == 1
        assert await env.delivery_repo.find_by_dedupe_key(
            alert_dedupe_key(
                organization_id="org-a",
                policy_id=policy_id,
                intelligence_event_id="evt-1",
                alert_stage=AlertStage.ESCALATION.value,
            )
        )

    @run_async
    async def test_duplicate_escalation_is_prevented(self, env):
        await _configured_policy(env)
        await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event(priority="medium")]
        )
        await env.dispatcher.dispatch_pending()
        escalated = make_disturbance_event(priority="high")

        first = await env.evaluation.evaluate_cycle(active_events=[escalated])
        second = await env.evaluation.evaluate_cycle(active_events=[escalated])
        assert first["escalation_created"] == 1
        assert second["escalation_created"] == 0

    @run_async
    async def test_unchanged_priority_creates_no_escalation(self, env):
        await _configured_policy(env)
        event = make_disturbance_event(priority="high")
        await env.evaluation.evaluate_cycle(active_events=[event])
        await env.dispatcher.dispatch_pending()

        stats = await env.evaluation.evaluate_cycle(active_events=[event])
        assert stats["escalation_created"] == 0

    @run_async
    async def test_priority_decrease_creates_no_escalation(self, env):
        await _configured_policy(env)
        await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event(priority="high")]
        )
        await env.dispatcher.dispatch_pending()

        stats = await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event(priority="medium")]
        )
        assert stats["escalation_created"] == 0

    @run_async
    async def test_escalation_requires_a_delivered_initial(self, env):
        """An initial alert that was never delivered must not escalate."""
        environment = build_alert_environment(email_sender=FailingEmailSender())
        await _configured_policy(environment)
        await environment.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event(priority="medium")]
        )
        await environment.dispatcher.dispatch_pending()

        stats = await environment.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event(priority="high")]
        )
        assert stats["escalation_created"] == 0

    @run_async
    async def test_escalation_carries_the_higher_priority(self, env):
        await _configured_policy(env)
        await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event(priority="medium")]
        )
        await env.dispatcher.dispatch_pending()
        await env.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event(priority="high")]
        )
        escalations = [
            row
            for row in env.deliveries_for("org-a")
            if row["alert_stage"] == AlertStage.ESCALATION.value
        ]
        assert len(escalations) == 1
        assert escalations[0]["priority"] == "critical"
        assert escalations[0]["reason"] == "priority_escalation"


class TestResolution:
    @run_async
    async def test_resolution_follows_a_delivered_alert(self, env):
        policy_id, _ = await _configured_policy(env)
        await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        await env.dispatcher.dispatch_pending()

        stats = await env.evaluation.evaluate_cycle(
            active_events=[],
            resolved_events=[make_disturbance_event(status="resolved")],
        )
        assert stats["resolution_created"] == 1
        assert await env.delivery_repo.find_by_dedupe_key(
            alert_dedupe_key(
                organization_id="org-a",
                policy_id=policy_id,
                intelligence_event_id="evt-1",
                alert_stage=AlertStage.RESOLUTION.value,
            )
        )

    @run_async
    async def test_duplicate_resolution_is_prevented(self, env):
        await _configured_policy(env)
        await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        await env.dispatcher.dispatch_pending()
        resolved = make_disturbance_event(status="resolved")

        first = await env.evaluation.evaluate_cycle(active_events=[], resolved_events=[resolved])
        second = await env.evaluation.evaluate_cycle(active_events=[], resolved_events=[resolved])
        assert first["resolution_created"] == 1
        assert second["resolution_created"] == 0

    @run_async
    async def test_resolution_without_prior_delivery_is_skipped(self, env):
        await _configured_policy(env)
        stats = await env.evaluation.evaluate_cycle(
            active_events=[],
            resolved_events=[make_disturbance_event(status="resolved")],
        )
        assert stats["resolution_created"] == 0

    @run_async
    async def test_non_resolved_status_is_ignored(self, env):
        await _configured_policy(env)
        await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        await env.dispatcher.dispatch_pending()

        stats = await env.evaluation.evaluate_cycle(
            active_events=[],
            resolved_events=[make_disturbance_event(status="active")],
        )
        assert stats["resolution_created"] == 0

    @run_async
    async def test_resolution_bypasses_cooldown(self, env):
        await _configured_policy(env, cooldown_minutes=600)
        await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()], now=NOW)
        await env.dispatcher.dispatch_pending()

        stats = await env.evaluation.evaluate_cycle(
            active_events=[],
            resolved_events=[make_disturbance_event(status="resolved")],
            now=NOW + timedelta(minutes=1),
        )
        assert stats["resolution_created"] == 1


class TestEntitlementEnforcement:
    @run_async
    async def test_no_delivery_without_alert_entitlement(self, env):
        await _configured_policy(env)
        env.store.set_alert_entitlement("org-a", False)
        stats = await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        assert stats["candidates_created"] == 0
        assert env.deliveries_for("org-a") == []

    @run_async
    async def test_entitlement_off_counts_as_skipped(self, env):
        await _configured_policy(env)
        env.store.set_alert_entitlement("org-a", False)
        stats = await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        assert stats["skipped"] == 1
        assert stats["organizations"] == 0

    @run_async
    async def test_re_enabling_entitlement_restores_deterministic_behavior(self, env):
        await _configured_policy(env)
        env.store.set_alert_entitlement("org-a", False)
        await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])

        env.store.set_alert_entitlement("org-a", True)
        first = await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        second = await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        assert first["initial_created"] == 1
        assert second["candidates_created"] == 0


class TestDisabledConfiguration:
    @run_async
    async def test_disabled_policy_creates_no_delivery(self, env):
        channel_id = await env.add_email_channel("org-a")
        await env.add_policy(
            "org-a",
            enabled=False,
            area_ids=[env.area_ids["org-a"]],
            channel_ids=[channel_id],
        )
        stats = await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        assert stats["candidates_created"] == 0

    @run_async
    async def test_policy_disabled_after_evaluation_suppresses_dispatch(self, env):
        policy_id, _ = await _configured_policy(env)
        await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        await env.policy_repo.update(policy_id, {"enabled": False})

        stats = await env.dispatcher.dispatch_pending()
        record = env.deliveries_for("org-a")[0]
        assert stats["suppressed"] == 1
        assert record["lifecycle"] == AlertLifecycle.SUPPRESSED.value
        assert record["suppression_reason"] == "policy_disabled"
        assert env.email.sent == []

    @run_async
    async def test_disabled_channel_receives_nothing(self, env):
        channel_id = await env.add_email_channel("org-a", enabled=False)
        await env.add_policy(
            "org-a",
            area_ids=[env.area_ids["org-a"]],
            channel_ids=[channel_id],
        )
        await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        stats = await env.dispatcher.dispatch_pending()

        record = env.deliveries_for("org-a")[0]
        assert stats["suppressed"] == 1
        assert record["suppression_reason"] == "no_channels"
        assert env.email.sent == []

    @run_async
    async def test_policy_without_channels_is_suppressed(self, env):
        await env.add_policy("org-a", area_ids=[env.area_ids["org-a"]], channel_ids=[])
        await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        await env.dispatcher.dispatch_pending()
        assert env.deliveries_for("org-a")[0]["suppression_reason"] == "no_channels"

    @run_async
    async def test_missing_intelligence_event_is_suppressed(self, env):
        await _configured_policy(env)
        await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        env.store.events.pop("evt-1")

        await env.dispatcher.dispatch_pending()
        assert env.deliveries_for("org-a")[0]["suppression_reason"] == "event_missing"

    @run_async
    async def test_one_disabled_channel_does_not_block_the_other(self, env):
        enabled = await env.add_email_channel("org-a", name="Active inbox")
        disabled = await env.add_webhook_channel("org-a", enabled=False)
        await env.add_policy(
            "org-a",
            area_ids=[env.area_ids["org-a"]],
            channel_ids=[enabled, disabled],
        )
        await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        stats = await env.dispatcher.dispatch_pending()

        assert stats["sent"] == 1
        assert len(env.email.sent) == 1
        assert env.webhook.calls == []


class TestOrganizationIsolation:
    @run_async
    async def test_each_organization_gets_its_own_delivery(self, two_orgs):
        for org_id in ("org-a", "org-b"):
            await _configured_policy(two_orgs, org_id=org_id)
        await two_orgs.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])

        assert len(two_orgs.deliveries_for("org-a")) == 1
        assert len(two_orgs.deliveries_for("org-b")) == 1

    @run_async
    async def test_shared_global_event_is_not_duplicated(self, two_orgs):
        for org_id in ("org-a", "org-b"):
            await _configured_policy(two_orgs, org_id=org_id)
        await two_orgs.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])

        assert len(two_orgs.store.events) == 1
        assert two_orgs.store.events["evt-1"]["status"] == "active"
        event_ids = {row["intelligence_event_id"] for row in two_orgs.store.deliveries.values()}
        assert event_ids == {"evt-1"}

    @run_async
    async def test_delivery_records_never_reference_another_organization(self, two_orgs):
        for org_id in ("org-a", "org-b"):
            await _configured_policy(two_orgs, org_id=org_id)
        await two_orgs.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])

        for row in two_orgs.deliveries_for("org-a"):
            policy = await two_orgs.policy_repo.find_by_id(row["policy_id"])
            assert policy.organization_id == "org-a"
            assert row["monitored_area_ids"] == [two_orgs.area_ids["org-a"]]

    @run_async
    async def test_organization_without_policies_receives_nothing(self, two_orgs):
        await _configured_policy(two_orgs, org_id="org-a")
        await two_orgs.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        assert two_orgs.deliveries_for("org-b") == []

    @run_async
    async def test_relevance_is_specific_to_each_organizations_areas(self, two_orgs):
        two_orgs.store.areas.clear()
        two_orgs.area_ids["org-a"] = two_orgs.store.add_area(
            "org-a", "Harghita AOI", polygon_maramures()
        )
        two_orgs.area_ids["org-b"] = two_orgs.store.add_area(
            "org-b", "Carpathian AOI", polygon_harghita()
        )
        for org_id in ("org-a", "org-b"):
            await _configured_policy(two_orgs, org_id=org_id)
        await two_orgs.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])

        assert two_orgs.deliveries_for("org-a") == []
        assert len(two_orgs.deliveries_for("org-b")) == 1

    @run_async
    async def test_entitlement_is_evaluated_per_organization(self, two_orgs):
        for org_id in ("org-a", "org-b"):
            await _configured_policy(two_orgs, org_id=org_id)
        two_orgs.store.set_alert_entitlement("org-b", False)
        await two_orgs.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])

        assert len(two_orgs.deliveries_for("org-a")) == 1
        assert two_orgs.deliveries_for("org-b") == []

    @run_async
    async def test_dispatch_ignores_channels_from_another_organization(self, two_orgs):
        foreign_channel = await two_orgs.add_email_channel("org-b", name="Other org inbox")
        await two_orgs.add_policy(
            "org-a",
            area_ids=[two_orgs.area_ids["org-a"]],
            channel_ids=[foreign_channel],
        )
        await two_orgs.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        await two_orgs.dispatcher.dispatch_pending()

        assert two_orgs.email.sent == []
        assert two_orgs.deliveries_for("org-a")[0]["suppression_reason"] == "no_channels"


class TestDeliveryOutcomeSemantics:
    @run_async
    async def test_email_success_marks_sent_with_timestamp(self, env):
        await _configured_policy(env)
        await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        await env.dispatcher.dispatch_pending()

        record = env.deliveries_for("org-a")[0]
        assert record["lifecycle"] == AlertLifecycle.SENT.value
        assert record["sent_at"] is not None
        assert record["dispatch_attempt_count"] == 1
        assert record["last_error"] is None

    @run_async
    async def test_total_failure_marks_failed_not_pending(self, env):
        environment = build_alert_environment(email_sender=FailingEmailSender())
        await _configured_policy(environment)
        await environment.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        await environment.dispatcher.dispatch_pending()

        record = environment.deliveries_for("org-a")[0]
        assert record["lifecycle"] == AlertLifecycle.FAILED.value
        assert record["sent_at"] is None
        assert record["last_error"] == "smtp_unavailable"
        assert record["suppression_reason"] is None

    @run_async
    async def test_suppression_is_distinct_from_failure(self, env):
        policy_id, _ = await _configured_policy(env)
        await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        await env.policy_repo.update(policy_id, {"enabled": False})
        await env.dispatcher.dispatch_pending()

        record = env.deliveries_for("org-a")[0]
        assert record["lifecycle"] == AlertLifecycle.SUPPRESSED.value
        assert record["last_error"] is None
        assert record["suppression_reason"] == "policy_disabled"

    @run_async
    async def test_partial_failure_still_marks_sent(self, env):
        environment = build_alert_environment(
            webhook_sender=RecordingWebhookSender(success=False, error="http_500")
        )
        email_channel = await environment.add_email_channel("org-a")
        webhook_channel = await environment.add_webhook_channel("org-a")
        await environment.add_policy(
            "org-a",
            area_ids=[environment.area_ids["org-a"]],
            channel_ids=[email_channel, webhook_channel],
        )
        await environment.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        stats = await environment.dispatcher.dispatch_pending()

        record = environment.deliveries_for("org-a")[0]
        assert stats["sent"] == 1
        assert record["lifecycle"] == AlertLifecycle.SENT.value
        assert record["last_error"] == "http_500"
        outcomes = {r["channel_type"]: r["success"] for r in record["delivery_results"]}
        assert outcomes == {"email": True, "webhook": False}

    @run_async
    async def test_webhook_receives_signed_payload_with_decrypted_secret(self, env):
        webhook_channel = await env.add_webhook_channel("org-a", secret="top-secret")
        await env.add_policy(
            "org-a",
            area_ids=[env.area_ids["org-a"]],
            channel_ids=[webhook_channel],
        )
        await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        await env.dispatcher.dispatch_pending()

        call = env.webhook.calls[0]
        assert call["secret_token"] == "top-secret"
        assert call["url"] == "https://example.com/hook"
        assert call["payload"]["organization_id"] == "org-a"

    @run_async
    async def test_raising_sender_is_contained_and_recorded(self, env):
        environment = build_alert_environment(email_sender=RaisingEmailSender())
        await _configured_policy(environment)
        await environment.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        stats = await environment.dispatcher.dispatch_pending()

        record = environment.deliveries_for("org-a")[0]
        assert stats["failed"] == 1
        assert record["lifecycle"] == AlertLifecycle.FAILED.value
        assert record["last_error"] == "dispatch_error"

    @run_async
    async def test_unknown_policy_reference_is_suppressed(self, env):
        await env.delivery_repo.create(
            AlertDeliveryRecord(
                dedupe_key="org-a:ghost:evt-1:initial",
                organization_id="org-a",
                policy_id="ghost",
                intelligence_event_id="evt-1",
                alert_stage=AlertStage.INITIAL.value,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        stats = await env.dispatcher.dispatch_pending()
        assert stats["suppressed"] == 1

    @run_async
    async def test_dispatch_batch_continues_after_one_failure(self, env):
        environment = build_alert_environment(email_sender=FailingEmailSender())
        environment.store.events["evt-2"] = make_disturbance_event("evt-2")
        await _configured_policy(environment)
        await environment.evaluation.evaluate_cycle(
            active_events=[make_disturbance_event("evt-1"), make_disturbance_event("evt-2")]
        )
        stats = await environment.dispatcher.dispatch_pending()
        assert stats["attempted"] == 2
        assert stats["failed"] == 2


class TestPipelineNeverRaises:
    @run_async
    async def test_evaluation_swallows_repository_errors(self, env):
        class ExplodingPolicyRepo:
            async def list_for_organization(self, *args, **kwargs):
                raise RuntimeError("mongo down")

        env.evaluation._policies = ExplodingPolicyRepo()
        stats = await env.evaluation.evaluate_cycle(active_events=[make_disturbance_event()])
        assert stats["candidates_created"] == 0

    @run_async
    async def test_pipeline_returns_stats_when_dispatch_fails(self, env):
        class ExplodingDispatcher:
            async def dispatch_pending(self, *args, **kwargs):
                raise RuntimeError("network down")

        await _configured_policy(env)
        env.notification._dispatcher = ExplodingDispatcher()
        result = await env.notification.run_post_reconciliation(
            active_events=[make_disturbance_event()]
        )
        assert result["evaluation"]["initial_created"] == 1
        assert result["dispatch"]["sent"] == 0

    @run_async
    async def test_end_to_end_pipeline_delivers(self, env):
        await _configured_policy(env)
        result = await env.notification.run_post_reconciliation(
            active_events=[make_disturbance_event()]
        )
        assert result["evaluation"]["initial_created"] == 1
        assert result["dispatch"]["sent"] == 1

    @run_async
    async def test_alert_body_preserves_safe_language(self, env):
        from app.core.ecosystem.forest_disturbance_constants import (
            FORBIDDEN_ASSERTION_PHRASES,
        )

        await _configured_policy(env)
        await env.notification.run_post_reconciliation(
            active_events=[make_disturbance_event()]
        )
        body = env.email.sent[0]["body"].lower()
        for phrase in FORBIDDEN_ASSERTION_PHRASES:
            assert phrase.lower() not in body

    @run_async
    async def test_alert_body_reports_unverified_authorization(self, env):
        await _configured_policy(env)
        await env.notification.run_post_reconciliation(
            active_events=[make_disturbance_event()]
        )
        body = env.email.sent[0]["body"]
        assert "Valea" in body or "AOI" in body
        assert "unknown" in body.lower() or "verification" in body.lower()


class TestCooldownRepositoryContract:
    def test_within_cooldown_uses_created_at(self):
        """The repository query keys on ``created_at``, not ``sent_at``."""
        import inspect

        from app.repositories.alert_delivery_repository import AlertDeliveryRepository

        source = inspect.getsource(AlertDeliveryRepository.within_cooldown)
        assert '"created_at": {"$gte": cutoff}' in source
        assert '"sent_at"' not in source

    def test_list_pending_excludes_terminal_states(self):
        import inspect

        from app.repositories.alert_delivery_repository import AlertDeliveryRepository

        source = inspect.getsource(AlertDeliveryRepository.list_pending)
        assert "DISPATCHABLE_LIFECYCLES" in source

    def test_utc_timestamps_are_timezone_aware(self):
        assert NOW.tzinfo == timezone.utc
        assert datetime.now(timezone.utc).tzinfo is not None
