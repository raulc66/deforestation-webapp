"""Organization commercial lifecycle — distinct from operational status.

``Organization.status`` remains operational (active / suspended).
``Organization.kind`` remains identity (customer / demo).

This module is the vocabulary for how an organization is commercially entitled
before, during, and after a free trial, and later a paid subscription.
Demo is never a value here: the reserved demonstration organization is
``kind="demo"``.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from app.core.commercial.plan_catalog import PLAN_ENTITLEMENT_SOURCE_PREFIX


class CommercialLifecycle(StrEnum):
    UNSUBSCRIBED = "unsubscribed"
    TRIAL = "trial"
    TRIAL_EXPIRED = "trial_expired"
    PAID = "paid"
    SUSPENDED = "suspended"


def is_plan_entitlement_source(source: str | None) -> bool:
    return str(source or "").startswith(f"{PLAN_ENTITLEMENT_SOURCE_PREFIX}:")


def resolve_commercial_lifecycle(
    *,
    kind: str,
    stored: str | None,
    trial_ends_at: datetime | None,
    entitlement_source: str | None,
    now: datetime,
) -> str:
    """Deterministic commercial status for an organization.

    Paid plan rows always win so a future Stripe sync can replace a trial
    profile without this package rewriting entitlements out from under it.
    """
    if str(kind or "") == "demo":
        return CommercialLifecycle.UNSUBSCRIBED.value
    if is_plan_entitlement_source(entitlement_source):
        return CommercialLifecycle.PAID.value
    stored_value = str(stored or CommercialLifecycle.UNSUBSCRIBED.value)
    if stored_value == CommercialLifecycle.TRIAL.value and trial_ends_at is not None:
        if now >= trial_ends_at:
            return CommercialLifecycle.TRIAL_EXPIRED.value
    if stored_value in {member.value for member in CommercialLifecycle}:
        return stored_value
    return CommercialLifecycle.UNSUBSCRIBED.value


def days_remaining(*, trial_ends_at: datetime | None, now: datetime) -> int | None:
    if trial_ends_at is None:
        return None
    remaining = trial_ends_at - now
    if remaining.total_seconds() <= 0:
        return 0
    return remaining.days
