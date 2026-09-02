"""Plan catalog, entitlement mapping, and subscription status vocabulary."""
from __future__ import annotations

import pytest

from app.core.commercial.entitlement_types import EntitlementType
from app.core.commercial.plan_catalog import (
    PlanKey,
    build_plan_catalog,
    default_profile_entitlements,
    plan_entitlement_source,
)
from app.core.commercial.subscription_status import (
    SubscriptionStatus,
    grants_plan_entitlements,
    is_known_status,
    is_terminal,
    requires_payment_attention,
    subscription_status_label,
)
from fixtures.billing_fakes import (
    PRICE_FOUNDATION,
    PRICE_PROFESSIONAL,
    billing_settings,
)


@pytest.fixture
def catalog():
    return build_plan_catalog(billing_settings())


class TestCatalogShape:
    def test_three_plans_are_published(self, catalog):
        assert [plan.key for plan in catalog.all_plans()] == [
            PlanKey.FOUNDATION.value,
            PlanKey.PROFESSIONAL.value,
            PlanKey.ENTERPRISE.value,
        ]

    def test_plans_are_ordered_by_capacity(self, catalog):
        limits = [plan.monitored_area_limit for plan in catalog.all_plans()]
        assert limits == sorted(limits)

    def test_known_plan_resolves(self, catalog):
        assert catalog.get("professional").display_name == "Professional"

    def test_unknown_plan_returns_none(self, catalog):
        assert catalog.get("platinum") is None

    def test_empty_plan_key_returns_none(self, catalog):
        assert catalog.get("") is None
        assert catalog.get(None) is None

    def test_default_plan_is_foundation(self, catalog):
        assert catalog.default_plan.key == PlanKey.FOUNDATION.value

    def test_every_plan_has_customer_facing_copy(self, catalog):
        for plan in catalog.all_plans():
            assert plan.display_name
            assert plan.description
            assert plan.audience


class TestPurchasability:
    def test_configured_price_makes_plan_purchasable(self, catalog):
        assert catalog.purchasable("professional") is not None

    def test_plan_without_price_is_not_purchasable(self):
        catalog = build_plan_catalog(billing_settings(stripe_price_professional=""))
        assert catalog.purchasable("professional") is None
        assert catalog.get("professional").as_public()["contact_sales"] is True

    def test_enterprise_is_contact_sales_by_default(self, catalog):
        assert catalog.purchasable("enterprise") is None

    def test_enterprise_becomes_purchasable_from_configuration(self):
        catalog = build_plan_catalog(
            billing_settings(
                plan_enterprise_purchasable=True,
                stripe_price_enterprise="price_ent",
            )
        )
        assert catalog.purchasable("enterprise") is not None

    def test_disabled_plan_is_not_purchasable(self):
        catalog = build_plan_catalog(billing_settings(plan_professional_purchasable=False))
        assert catalog.purchasable("professional") is None

    def test_unknown_plan_is_not_purchasable(self, catalog):
        assert catalog.purchasable("enterprise-plus") is None


class TestPriceResolution:
    def test_price_id_resolves_to_plan(self, catalog):
        assert catalog.find_by_price_id(PRICE_PROFESSIONAL).key == "professional"
        assert catalog.find_by_price_id(PRICE_FOUNDATION).key == "foundation"

    def test_unknown_price_id_resolves_to_nothing(self, catalog):
        assert catalog.find_by_price_id("price_someone_elses") is None

    def test_blank_price_never_matches_an_unconfigured_plan(self, catalog):
        assert catalog.find_by_price_id("") is None
        assert catalog.find_by_price_id(None) is None


class TestEntitlementMapping:
    def test_foundation_profile_matches_the_unsubscribed_baseline(self, catalog):
        foundation = catalog.get("foundation").entitlement_profile
        baseline = default_profile_entitlements()
        assert foundation == baseline

    def test_professional_unlocks_the_commercial_capabilities(self, catalog):
        profile = catalog.get("professional").entitlement_profile
        assert profile[EntitlementType.EVIDENCE_CORRELATION_ENABLED.value] is True
        assert profile[EntitlementType.LIVE_SOURCES_ENABLED.value] is True
        assert profile[EntitlementType.ALERT_DELIVERY_ENABLED.value] is True

    def test_area_limits_come_from_configuration(self):
        catalog = build_plan_catalog(
            billing_settings(plan_professional_area_limit=25)
        )
        assert catalog.get("professional").monitored_area_limit == 25

    def test_profiles_only_use_known_entitlement_types(self, catalog):
        known = {member.value for member in EntitlementType}
        for plan in catalog.all_plans():
            assert set(plan.entitlement_profile) <= known

    def test_every_plan_enables_monitoring(self, catalog):
        for plan in catalog.all_plans():
            assert plan.entitlement_profile[EntitlementType.MONITORING_ENABLED.value] is True

    def test_negative_configured_limit_is_clamped(self):
        catalog = build_plan_catalog(billing_settings(plan_foundation_area_limit=-5))
        assert catalog.get("foundation").monitored_area_limit == 0

    def test_entitlement_source_records_the_plan(self):
        assert plan_entitlement_source("professional") == "plan:professional"


class TestPublicRepresentation:
    def test_public_payload_hides_stripe_identifiers(self, catalog):
        payload = catalog.get("professional").as_public()
        serialized = repr(payload)
        assert PRICE_PROFESSIONAL not in serialized
        assert "stripe" not in serialized.lower()

    def test_capability_lines_are_customer_language(self, catalog):
        for line in catalog.get("professional").capability_highlights():
            assert "_enabled" not in line
            assert "entitlement" not in line.lower()

    def test_capacity_line_is_singular_for_one_forest(self, catalog):
        assert "1 monitored forest" in catalog.get("foundation").capability_highlights()[0]

    def test_price_label_is_configuration_driven(self, catalog):
        assert catalog.get("professional").as_public()["price_label"] == "EUR 149 / month"

    def test_missing_price_label_is_empty_not_invented(self):
        catalog = build_plan_catalog(billing_settings(plan_professional_price_label=""))
        assert catalog.get("professional").as_public()["price_label"] == ""


class TestSubscriptionStatusVocabulary:
    @pytest.mark.parametrize(
        "status",
        ["active", "trialing", "past_due"],
    )
    def test_entitling_statuses(self, status):
        assert grants_plan_entitlements(status) is True

    @pytest.mark.parametrize(
        "status",
        ["incomplete", "incomplete_expired", "canceled", "unpaid", "paused", "", None],
    )
    def test_non_entitling_statuses(self, status):
        assert grants_plan_entitlements(status) is False

    @pytest.mark.parametrize("status", ["past_due", "unpaid", "incomplete"])
    def test_payment_attention_statuses(self, status):
        assert requires_payment_attention(status) is True

    def test_active_needs_no_payment_attention(self):
        assert requires_payment_attention("active") is False

    @pytest.mark.parametrize("status", ["canceled", "incomplete_expired", "paused"])
    def test_terminal_statuses(self, status):
        assert is_terminal(status) is True

    def test_all_enum_members_are_known(self):
        for member in SubscriptionStatus:
            assert is_known_status(member.value)

    def test_unknown_status_is_rejected(self):
        assert is_known_status("paused_by_hand") is False

    def test_labels_never_leak_raw_status_codes(self):
        for member in SubscriptionStatus:
            label = subscription_status_label(member.value)
            assert "_" not in label

    def test_missing_status_reads_as_no_subscription(self):
        assert subscription_status_label(None) == "No subscription"
