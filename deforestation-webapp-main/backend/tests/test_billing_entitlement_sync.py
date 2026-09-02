"""Plan -> OrganizationEntitlement synchronization.

Covers the commercially important guarantee: a plan change alters what an
organization may do next and never removes what it already has.
"""
from __future__ import annotations

import pytest

from app.core.commercial.entitlement_types import DEFAULT_ENTITLEMENT_SOURCE, EntitlementType
from app.core.errors import ForbiddenError
from app.models.forest_monitoring_area import ForestMonitoringAreaCreate
from app.services.billing.entitlement_sync_service import resolve_entitlements
from fixtures.billing_fakes import build_environment, romania_polygon, run_async


@pytest.fixture
def env():
    return build_environment()


@pytest.fixture
def org(env):
    return env.add_organization("Carpathian Forestry")


async def _sync(env, org, plan_key, status):
    return await env.entitlement_sync.sync_from_plan_key(
        org,
        plan_key=plan_key,
        status=status,
    )


class TestDeterministicResolution:
    def test_same_inputs_always_resolve_identically(self, env):
        plan = env.catalog.get("professional")
        first = resolve_entitlements(env.catalog, plan=plan, status="active")
        second = resolve_entitlements(env.catalog, plan=plan, status="active")
        assert first == second

    def test_entitling_status_uses_the_plan_profile(self, env):
        plan = env.catalog.get("professional")
        resolved = resolve_entitlements(env.catalog, plan=plan, status="trialing")
        assert resolved.profile == plan.entitlement_profile
        assert resolved.capability_active is True

    def test_non_entitling_status_falls_back_to_the_baseline(self, env):
        plan = env.catalog.get("professional")
        resolved = resolve_entitlements(env.catalog, plan=plan, status="canceled")
        assert resolved.plan_key == "foundation"
        assert resolved.source == DEFAULT_ENTITLEMENT_SOURCE
        assert resolved.capability_active is False

    def test_missing_plan_falls_back_to_the_baseline(self, env):
        resolved = resolve_entitlements(env.catalog, plan=None, status="active")
        assert resolved.plan_key == "foundation"
        assert resolved.capability_active is False

    def test_past_due_retains_plan_capability(self, env):
        plan = env.catalog.get("professional")
        resolved = resolve_entitlements(env.catalog, plan=plan, status="past_due")
        assert resolved.capability_active is True

    def test_unpaid_removes_plan_capability(self, env):
        plan = env.catalog.get("professional")
        resolved = resolve_entitlements(env.catalog, plan=plan, status="unpaid")
        assert resolved.capability_active is False


class TestPersistedSynchronization:
    @run_async
    async def test_activation_writes_the_plan_profile(self, env, org):
        await _sync(env, org, "professional", "active")
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 5
        assert profile.evidence_correlation_enabled is True
        assert profile.live_sources_enabled is True
        assert profile.alert_delivery_enabled is True

    @run_async
    async def test_activation_records_plan_provenance(self, env, org):
        await _sync(env, org, "professional", "active")
        rows = await env.entitlement_repo.list_for_organization(org)
        assert {row.source for row in rows} == {"plan:professional"}

    @run_async
    async def test_all_entitlement_types_are_written(self, env, org):
        result = await _sync(env, org, "professional", "active")
        assert len(result.changed_types) == len(EntitlementType)

    @run_async
    async def test_repeated_sync_changes_nothing(self, env, org):
        await _sync(env, org, "professional", "active")
        second = await _sync(env, org, "professional", "active")
        assert second.changed_types == ()

    @run_async
    async def test_repeated_sync_does_not_duplicate_rows(self, env, org):
        await _sync(env, org, "professional", "active")
        await _sync(env, org, "professional", "active")
        rows = await env.entitlement_repo.list_for_organization(org)
        assert len(rows) == len(EntitlementType)

    @run_async
    async def test_upgrade_raises_the_limit(self, env, org):
        await _sync(env, org, "foundation", "active")
        await _sync(env, org, "professional", "active")
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 5

    @run_async
    async def test_downgrade_lowers_the_limit(self, env, org):
        await _sync(env, org, "professional", "active")
        await _sync(env, org, "foundation", "active")
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 1
        assert profile.alert_delivery_enabled is False

    @run_async
    async def test_cancellation_returns_the_baseline(self, env, org):
        await _sync(env, org, "professional", "active")
        await _sync(env, org, "professional", "canceled")
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.monitored_area_limit == 1
        assert profile.live_sources_enabled is False
        assert profile.source == DEFAULT_ENTITLEMENT_SOURCE

    @run_async
    async def test_payment_failure_keeps_capability_during_grace(self, env, org):
        await _sync(env, org, "professional", "active")
        await _sync(env, org, "professional", "past_due")
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.alert_delivery_enabled is True

    @run_async
    async def test_dunning_exhausted_removes_capability(self, env, org):
        await _sync(env, org, "professional", "active")
        await _sync(env, org, "professional", "unpaid")
        profile = await env.entitlement_svc.get_profile(org)
        assert profile.alert_delivery_enabled is False

    @run_async
    async def test_synchronization_is_organization_scoped(self, env, org):
        other = env.add_organization("Other Forestry")
        await _sync(env, org, "professional", "active")
        other_profile = await env.entitlement_svc.get_profile(other)
        assert other_profile.monitored_area_limit == 1
        assert other_profile.alert_delivery_enabled is False

    @run_async
    async def test_state_and_plan_alone_determine_the_result(self, env, org):
        other = env.add_organization("Twin Forestry")
        # Different histories, same (plan, status) endpoint.
        await _sync(env, org, "foundation", "active")
        await _sync(env, org, "professional", "active")
        await _sync(env, other, "professional", "active")
        first = await env.entitlement_svc.get_profile(org)
        second = await env.entitlement_svc.get_profile(other)
        assert first.as_read_model(monitored_area_count=0) == second.as_read_model(
            monitored_area_count=0
        )


class TestDowngradeRetention:
    @run_async
    async def test_existing_areas_survive_a_downgrade(self, env, org):
        await _sync(env, org, "professional", "active")
        for index in range(5):
            env.add_area(org, name=f"Stand {index}", offset=index * 0.1)
        await _sync(env, org, "foundation", "active")
        areas = await env.areas.list_for_organization(org)
        assert len(areas) == 5

    @run_async
    async def test_over_limit_organization_cannot_add_areas(self, env, org):
        await _sync(env, org, "professional", "active")
        for index in range(5):
            env.add_area(org, name=f"Stand {index}", offset=index * 0.1)
        await _sync(env, org, "professional", "canceled")
        assert await env.entitlement_svc.can_add_monitoring_area(org) is False

    @run_async
    async def test_area_creation_is_refused_after_downgrade(self, env, org):
        await _sync(env, org, "professional", "active")
        env.add_area(org, name="Existing")
        await _sync(env, org, "professional", "canceled")
        with pytest.raises(ForbiddenError):
            await env.area_svc.create_area(
                org,
                ForestMonitoringAreaCreate(
                    name="New stand",
                    geometry=romania_polygon(1.0),
                    country="Romania",
                ),
                actor_role="owner",
            )

    @run_async
    async def test_upgrade_reopens_area_creation(self, env, org):
        env.add_area(org, name="Existing")
        assert await env.entitlement_svc.can_add_monitoring_area(org) is False
        await _sync(env, org, "professional", "active")
        created = await env.area_svc.create_area(
            org,
            ForestMonitoringAreaCreate(
                name="Second stand",
                geometry=romania_polygon(1.0),
                country="Romania",
            ),
            actor_role="owner",
        )
        assert created.name == "Second stand"

    @run_async
    async def test_alert_capability_follows_the_plan(self, env, org):
        assert await env.entitlement_svc.can_receive_alerts(org) is False
        await _sync(env, org, "professional", "active")
        assert await env.entitlement_svc.can_receive_alerts(org) is True
        await _sync(env, org, "professional", "canceled")
        assert await env.entitlement_svc.can_receive_alerts(org) is False

    @run_async
    async def test_live_source_capability_follows_the_plan(self, env, org):
        await _sync(env, org, "professional", "active")
        assert await env.entitlement_svc.can_use_live_sources(org) is True
        await _sync(env, org, "foundation", "active")
        assert await env.entitlement_svc.can_use_live_sources(org) is False

    @run_async
    async def test_cross_source_evidence_follows_the_plan(self, env, org):
        await _sync(env, org, "professional", "active")
        assert await env.entitlement_svc.can_use_cross_source_correlation(org) is True
        await _sync(env, org, "foundation", "active")
        assert await env.entitlement_svc.can_use_cross_source_correlation(org) is False

    @run_async
    async def test_disturbance_intelligence_survives_cancellation(self, env, org):
        await _sync(env, org, "professional", "active")
        await _sync(env, org, "professional", "canceled")
        assert await env.entitlement_svc.can_use_forest_disturbance(org) is True

    @run_async
    async def test_monitoring_stays_enabled_after_cancellation(self, env, org):
        await _sync(env, org, "professional", "canceled")
        assert await env.entitlement_svc.can_monitor(org) is True
