"""Customer alert vocabulary — validation ranges and product-facing labels.

Single source of truth for the values an organization may configure on an
``AlertPolicy`` and for the customer-facing wording of delivery outcomes.
Internal identifiers (entitlement keys, provider ids, repository names) must
never reach the customer surface; the label maps here provide the translation.
"""
from __future__ import annotations

from app.core.ecosystem.category_registry import get_category_registry

ALERT_PRIORITY_LEVELS: tuple[str, ...] = ("low", "medium", "high", "critical")
ALERT_SEVERITY_LEVELS: tuple[str, ...] = ("low", "medium", "high", "critical")
ALERT_EVIDENCE_STATES: tuple[str, ...] = (
    "single_source",
    "contextual_support",
    "multi_source",
)

MIN_COOLDOWN_MINUTES = 0
MAX_COOLDOWN_MINUTES = 10_080  # one week
MAX_POLICY_NAME_LENGTH = 120
MAX_MONITORED_AREA_REFERENCES = 50
MAX_CHANNEL_REFERENCES = 10
MAX_EMAIL_RECIPIENTS = 20

# Suppression reasons are persisted as stable identifiers and rendered through
# these labels so the customer never sees an internal state name.
SUPPRESSION_REASON_LABELS: dict[str, str] = {
    "policy_disabled": "Alert policy was turned off before delivery",
    "no_channels": "No enabled notification channel configured",
    "event_missing": "Intelligence event is no longer available",
    "cooldown_active": "Suppressed by the policy cooldown window",
    "alert_delivery_unavailable": "Alert delivery is not enabled for this organization",
}

DELIVERY_STATE_LABELS: dict[str, str] = {
    "pending": "Queued",
    "sent": "Delivered",
    "failed": "Delivery failed",
    "suppressed": "Suppressed",
    "acknowledged": "Acknowledged",
    "resolved": "Resolved",
}

ALERT_STAGE_LABELS: dict[str, str] = {
    "initial": "Initial alert",
    "escalation": "Escalation",
    "resolution": "Resolution",
}

CHANNEL_TYPE_LABELS: dict[str, str] = {
    "email": "Email channel",
    "webhook": "Webhook channel",
}


def supported_incident_categories() -> tuple[str, ...]:
    """Categories an alert policy may watch — sourced from the central registry."""
    registry = get_category_registry()
    return registry.enabled_categories()


def category_display_name(category: str) -> str:
    definition = get_category_registry().get(category)
    return definition.display_name if definition else str(category)


def suppression_reason_label(reason: str | None) -> str | None:
    if not reason:
        return None
    return SUPPRESSION_REASON_LABELS.get(reason, "Suppressed")


def delivery_state_label(lifecycle: str | None) -> str:
    return DELIVERY_STATE_LABELS.get(str(lifecycle or ""), "Unknown")


def alert_stage_label(stage: str | None) -> str:
    return ALERT_STAGE_LABELS.get(str(stage or ""), "Alert")


def channel_type_label(channel_type: str | None) -> str:
    return CHANNEL_TYPE_LABELS.get(str(channel_type or ""), "Notification channel")
