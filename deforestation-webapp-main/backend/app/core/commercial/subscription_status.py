"""Subscription lifecycle vocabulary.

Two distinct concepts live here and must not be conflated:

* **Stripe subscription state** — what Stripe says about the payment agreement.
* **ForestWatch entitlement state** — whether the paid plan's capabilities apply.

Only :func:`grants_plan_entitlements` maps one onto the other, so the rule is
stated exactly once.
"""
from __future__ import annotations

from enum import StrEnum


class SubscriptionStatus(StrEnum):
    """Stripe subscription statuses ForestWatch understands."""

    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    UNPAID = "unpaid"
    # Dahlia (2026-05-27): pausing stops billing and service. ForestWatch treats
    # this as non-entitling — the customer is not paying for the period.
    PAUSED = "paused"


# A paid plan applies while the customer is paying or inside a grace period.
# ``past_due`` keeps capability so a single failed charge does not silently
# switch a customer's monitoring off; ``unpaid`` is Stripe's terminal dunning
# state and does not.
ENTITLING_STATUSES: frozenset[str] = frozenset(
    {
        SubscriptionStatus.TRIALING.value,
        SubscriptionStatus.ACTIVE.value,
        SubscriptionStatus.PAST_DUE.value,
    }
)

# States where the customer must act before the subscription can bill again.
PAYMENT_ATTENTION_STATUSES: frozenset[str] = frozenset(
    {
        SubscriptionStatus.PAST_DUE.value,
        SubscriptionStatus.UNPAID.value,
        SubscriptionStatus.INCOMPLETE.value,
    }
)

TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        SubscriptionStatus.CANCELED.value,
        SubscriptionStatus.INCOMPLETE_EXPIRED.value,
        SubscriptionStatus.PAUSED.value,
    }
)

SUBSCRIPTION_STATUS_LABELS: dict[str, str] = {
    SubscriptionStatus.INCOMPLETE.value: "Awaiting payment confirmation",
    SubscriptionStatus.INCOMPLETE_EXPIRED.value: "Checkout expired",
    SubscriptionStatus.TRIALING.value: "Trial",
    SubscriptionStatus.ACTIVE.value: "Active",
    SubscriptionStatus.PAST_DUE.value: "Payment overdue",
    SubscriptionStatus.CANCELED.value: "Canceled",
    SubscriptionStatus.UNPAID.value: "Unpaid",
    SubscriptionStatus.PAUSED.value: "Paused",
}


def is_known_status(status: str | None) -> bool:
    return str(status or "") in {member.value for member in SubscriptionStatus}


def grants_plan_entitlements(status: str | None) -> bool:
    """Whether a subscription in this state should apply its plan's capabilities."""
    return str(status or "") in ENTITLING_STATUSES


def requires_payment_attention(status: str | None) -> bool:
    return str(status or "") in PAYMENT_ATTENTION_STATUSES


def is_terminal(status: str | None) -> bool:
    return str(status or "") in TERMINAL_STATUSES


def subscription_status_label(status: str | None) -> str:
    return SUBSCRIPTION_STATUS_LABELS.get(str(status or ""), "No subscription")
