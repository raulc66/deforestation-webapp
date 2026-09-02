"""Configuration-driven commercial plan catalog.

The catalog is the single place where a plan is described. Everything else in
the billing subsystem resolves plans through here, so changing a Stripe price
id, a monitored-area allowance, or which plans are sellable is a configuration
change rather than a code change.

Plan entitlement profiles are expressed with existing
:class:`~app.core.commercial.entitlement_types.EntitlementType` keys so they can
be written straight onto ``OrganizationEntitlement`` rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable

from app.core.commercial.entitlement_types import (
    DEFAULT_ENTITLEMENT_PROFILE,
    EntitlementType,
)


class PlanKey(StrEnum):
    FOUNDATION = "foundation"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


# Entitlement source recorded on rows written from a plan. The suffix keeps the
# provenance of every entitlement row inspectable without a second table.
PLAN_ENTITLEMENT_SOURCE_PREFIX = "plan"


def plan_entitlement_source(plan_key: str) -> str:
    return f"{PLAN_ENTITLEMENT_SOURCE_PREFIX}:{plan_key}"


@dataclass(frozen=True)
class SubscriptionPlan:
    """A sellable (or contact-sales) ForestWatch plan."""

    key: str
    display_name: str
    description: str
    audience: str
    price_label: str
    stripe_price_id: str
    entitlement_profile: dict[str, Any]
    available: bool
    purchasable: bool
    sort_order: int

    @property
    def monitored_area_limit(self) -> int:
        return int(
            self.entitlement_profile.get(
                EntitlementType.MONITORED_AREA_LIMIT.value,
                1,
            )
        )

    @property
    def is_checkout_ready(self) -> bool:
        """Purchasable *and* wired to a Stripe price."""
        return self.available and self.purchasable and bool(self.stripe_price_id)

    def capability_highlights(self) -> list[str]:
        """Customer-facing capability lines — never entitlement identifiers."""
        profile = self.entitlement_profile
        limit = self.monitored_area_limit
        lines = [
            f"{limit} monitored forest{'' if limit == 1 else 's'}",
        ]
        if profile.get(EntitlementType.FOREST_DISTURBANCE_ENABLED.value):
            lines.append("Forest disturbance intelligence")
        if profile.get(EntitlementType.EVIDENCE_CORRELATION_ENABLED.value):
            lines.append("Cross-source evidence")
        else:
            lines.append("Single-source evidence")
        if profile.get(EntitlementType.LIVE_SOURCES_ENABLED.value):
            lines.append("Live environmental sources")
        if profile.get(EntitlementType.ALERT_DELIVERY_ENABLED.value):
            lines.append("Alert delivery to email and webhooks")
        return lines

    def as_public(self) -> dict[str, Any]:
        """Customer-facing plan representation — no Stripe identifiers."""
        return {
            "key": self.key,
            "display_name": self.display_name,
            "description": self.description,
            "audience": self.audience,
            "price_label": self.price_label,
            "monitored_area_limit": self.monitored_area_limit,
            "capabilities": self.capability_highlights(),
            "purchasable": self.is_checkout_ready,
            "contact_sales": self.available and not self.is_checkout_ready,
        }


class PlanCatalog:
    """Deterministic, ordered collection of plans."""

    def __init__(self, plans: Iterable[SubscriptionPlan]) -> None:
        ordered = sorted(plans, key=lambda plan: (plan.sort_order, plan.key))
        self._plans: tuple[SubscriptionPlan, ...] = tuple(ordered)
        self._by_key = {plan.key: plan for plan in self._plans}

    def all_plans(self, *, include_unavailable: bool = False) -> list[SubscriptionPlan]:
        return [
            plan for plan in self._plans if include_unavailable or plan.available
        ]

    def get(self, plan_key: str | None) -> SubscriptionPlan | None:
        if not plan_key:
            return None
        return self._by_key.get(str(plan_key))

    def purchasable(self, plan_key: str | None) -> SubscriptionPlan | None:
        plan = self.get(plan_key)
        if plan is None or not plan.is_checkout_ready:
            return None
        return plan

    def find_by_price_id(self, price_id: str | None) -> SubscriptionPlan | None:
        """Resolve the plan a Stripe price belongs to (webhook direction only)."""
        if not price_id:
            return None
        for plan in self._plans:
            if plan.stripe_price_id and plan.stripe_price_id == price_id:
                return plan
        return None

    @property
    def default_plan(self) -> SubscriptionPlan:
        """Plan applied when no subscription grants entitlements."""
        foundation = self._by_key.get(PlanKey.FOUNDATION.value)
        if foundation is not None:
            return foundation
        return self._plans[0]


def _profile(
    *,
    monitored_area_limit: int,
    disturbance: bool,
    correlation: bool,
    live_sources: bool,
    alerts: bool,
    alert_policy_limit: int = 0,
    notification_channel_limit: int = 0,
) -> dict[str, Any]:
    return {
        EntitlementType.MONITORED_AREA_LIMIT.value: max(int(monitored_area_limit), 0),
        EntitlementType.MONITORING_ENABLED.value: True,
        EntitlementType.FOREST_DISTURBANCE_ENABLED.value: bool(disturbance),
        EntitlementType.EVIDENCE_CORRELATION_ENABLED.value: bool(correlation),
        EntitlementType.LIVE_SOURCES_ENABLED.value: bool(live_sources),
        EntitlementType.ALERT_DELIVERY_ENABLED.value: bool(alerts),
        EntitlementType.ALERT_POLICY_LIMIT.value: max(int(alert_policy_limit), 0),
        EntitlementType.NOTIFICATION_CHANNEL_LIMIT.value: max(
            int(notification_channel_limit), 0
        ),
    }


def build_plan_catalog(settings: Any) -> PlanCatalog:
    """Build the catalog from application settings."""

    def cfg(name: str, default: Any) -> Any:
        value = getattr(settings, name, default)
        return default if value is None else value

    foundation = SubscriptionPlan(
        key=PlanKey.FOUNDATION.value,
        display_name="Foundation",
        description=(
            "Continuous monitoring for a single forest, with disturbance "
            "intelligence and the operational dashboard."
        ),
        audience="Individual forest owners and single-site operators",
        price_label=str(cfg("plan_foundation_price_label", "")),
        stripe_price_id=str(cfg("stripe_price_foundation", "")),
        entitlement_profile=_profile(
            monitored_area_limit=int(cfg("plan_foundation_area_limit", 1)),
            disturbance=True,
            correlation=False,
            live_sources=False,
            alerts=False,
            alert_policy_limit=0,
            notification_channel_limit=0,
        ),
        available=True,
        purchasable=bool(cfg("plan_foundation_purchasable", True)),
        sort_order=10,
    )
    professional = SubscriptionPlan(
        key=PlanKey.PROFESSIONAL.value,
        display_name="Professional",
        description=(
            "Monitor a forest portfolio with cross-source evidence, live "
            "environmental sources, and delivered alerts."
        ),
        audience="Organizations managing multiple forest assets",
        price_label=str(cfg("plan_professional_price_label", "")),
        stripe_price_id=str(cfg("stripe_price_professional", "")),
        entitlement_profile=_profile(
            monitored_area_limit=int(cfg("plan_professional_area_limit", 10)),
            disturbance=True,
            correlation=True,
            live_sources=True,
            alerts=True,
            alert_policy_limit=5,
            notification_channel_limit=2,
        ),
        available=True,
        purchasable=bool(cfg("plan_professional_purchasable", True)),
        sort_order=20,
    )
    enterprise = SubscriptionPlan(
        key=PlanKey.ENTERPRISE.value,
        display_name="Enterprise",
        description=(
            "Institutional forest monitoring capacity with the full "
            "intelligence and alerting capability set."
        ),
        audience="Forestry institutions and large operators",
        price_label=str(cfg("plan_enterprise_price_label", "")),
        stripe_price_id=str(cfg("stripe_price_enterprise", "")),
        entitlement_profile=_profile(
            monitored_area_limit=int(cfg("plan_enterprise_area_limit", 100)),
            disturbance=True,
            correlation=True,
            live_sources=True,
            alerts=True,
            alert_policy_limit=20,
            notification_channel_limit=5,
        ),
        available=True,
        # Enterprise is contact-sales until a price id is configured.
        purchasable=bool(cfg("plan_enterprise_purchasable", False)),
        sort_order=30,
    )
    return PlanCatalog([foundation, professional, enterprise])


def default_profile_entitlements() -> dict[str, Any]:
    """Unsubscribed baseline — the existing foundation defaults."""
    return dict(DEFAULT_ENTITLEMENT_PROFILE)
