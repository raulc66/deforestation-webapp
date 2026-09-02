"""Readers for Stripe webhook object shapes.

Stripe renders webhook payloads with the API version configured on the webhook
endpoint, not the version our SDK requests. A ForestWatch deployment therefore
has to read whatever shape the customer's Stripe account is pinned to, and the
2025-03-31 "basil" release moved two fields we depend on:

- ``invoice.subscription`` became ``invoice.parent.subscription_details.subscription``
- ``subscription.current_period_end`` became ``subscription.items.data[].current_period_end``

Every reader here accepts both the pre-basil and basil shapes, so the same
deployment keeps working across a Stripe API upgrade. These are pure functions
over decoded JSON: no SDK types, no network, no I/O.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SUBSCRIPTION_PARENT_TYPE = "subscription_details"


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def stripe_id(value: Any) -> str | None:
    """Stripe references are either an id string or an expanded object."""
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        candidate = value.get("id")
        return str(candidate) if candidate else None
    return None


def epoch_to_datetime(value: Any) -> datetime | None:
    try:
        if value in (None, ""):
            return None
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def subscription_price_id(subscription: dict[str, Any]) -> str | None:
    """Price the subscription bills on, from the first item that carries one."""
    for item in as_list(as_dict(subscription.get("items")).get("data")):
        price = as_dict(as_dict(item).get("price"))
        if price.get("id"):
            return str(price["id"])
        # `plan` predates `price` and is still populated on older API versions.
        plan = as_dict(as_dict(item).get("plan"))
        if plan.get("id"):
            return str(plan["id"])
    return None


def subscription_period_end(subscription: dict[str, Any]) -> datetime | None:
    """End of the current billing period.

    Basil moved the period onto each subscription item so a subscription can mix
    billing intervals. The latest item period is the date the customer should be
    shown, because that is when their access is paid through.
    """
    latest: datetime | None = None
    for item in as_list(as_dict(subscription.get("items")).get("data")):
        candidate = epoch_to_datetime(as_dict(item).get("current_period_end"))
        if candidate is not None and (latest is None or candidate > latest):
            latest = candidate
    if latest is not None:
        return latest
    return epoch_to_datetime(subscription.get("current_period_end"))


def _invoice_parent_details(invoice: dict[str, Any]) -> dict[str, Any]:
    parent = as_dict(invoice.get("parent"))
    if parent.get("type") not in (None, "", SUBSCRIPTION_PARENT_TYPE):
        # A quote- or invoice-item-generated invoice says nothing about a
        # subscription, so it must not be read as if it did.
        return {}
    return as_dict(parent.get(SUBSCRIPTION_PARENT_TYPE))


def invoice_subscription_id(invoice: dict[str, Any]) -> str | None:
    """Subscription an invoice belongs to, across both API shapes."""
    details = _invoice_parent_details(invoice)
    from_parent = stripe_id(details.get("subscription"))
    if from_parent:
        return from_parent
    legacy = stripe_id(invoice.get("subscription"))
    if legacy:
        return legacy
    for line in as_list(as_dict(invoice.get("lines")).get("data")):
        line_parent = as_dict(as_dict(line).get("parent"))
        item_details = as_dict(line_parent.get("subscription_item_details"))
        from_line = stripe_id(item_details.get("subscription"))
        if from_line:
            return from_line
        from_legacy_line = stripe_id(as_dict(line).get("subscription"))
        if from_legacy_line:
            return from_legacy_line
    return None


def invoice_metadata(invoice: dict[str, Any]) -> dict[str, Any]:
    """Metadata usable for organization resolution.

    The invoice's own metadata is not the subscription's. Basil exposes the
    subscription metadata captured at invoice creation under ``parent``, and it
    is the more specific of the two, so it wins.
    """
    merged = dict(as_dict(invoice.get("metadata")))
    merged.update(as_dict(as_dict(invoice.get("subscription_details")).get("metadata")))
    merged.update(as_dict(_invoice_parent_details(invoice).get("metadata")))
    return merged
