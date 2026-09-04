"""Organization-scoped alert policy, delivery, and notification channel models."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from .base import BaseDocument, utcnow


class AlertStage(StrEnum):
    INITIAL = "initial"
    ESCALATION = "escalation"
    RESOLUTION = "resolution"


class AlertLifecycle(StrEnum):
    """Delivery-record lifecycle — distinct from the IntelligenceEvent lifecycle.

    ``pending`` means "created by evaluation, not yet dispatched". ``failed``
    means "dispatch was attempted and every channel failed" and is terminal for
    the current package (single bounded attempt, no retry queue).
    """

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


# Records the dispatcher may pick up. Terminal states are never re-attempted.
DISPATCHABLE_LIFECYCLES: frozenset[str] = frozenset({AlertLifecycle.PENDING.value})


NotificationChannelType = Literal["email", "webhook"]


def alert_dedupe_key(
    *,
    organization_id: str,
    policy_id: str,
    intelligence_event_id: str,
    alert_stage: str,
) -> str:
    """Deterministic alert identity — org + policy + event + stage."""
    return f"{organization_id}:{policy_id}:{intelligence_event_id}:{alert_stage}"


class AlertPolicy(BaseDocument):
    organization_id: str
    name: str
    enabled: bool = True
    monitored_area_ids: list[str] = Field(default_factory=list)
    incident_categories: list[str] = Field(default_factory=lambda: ["forest_disturbance"])
    minimum_investigation_priority: str = "medium"
    minimum_severity: str = "medium"
    minimum_evidence_state: str | None = None
    notification_channel_ids: list[str] = Field(default_factory=list)
    cooldown_minutes: int = 60
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class OrganizationNotificationChannel(BaseDocument):
    organization_id: str
    channel_type: NotificationChannelType
    name: str
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class AlertDeliveryRecord(BaseDocument):
    dedupe_key: str
    organization_id: str
    policy_id: str
    intelligence_event_id: str
    alert_stage: str
    monitored_area_ids: list[str] = Field(default_factory=list)
    reason: str = ""
    priority: str = "medium"
    evidence_summary: dict[str, Any] = Field(default_factory=dict)
    lifecycle: str = AlertLifecycle.PENDING.value
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    sent_at: datetime | None = None
    dispatch_attempt_count: int = 0
    last_attempt_at: datetime | None = None
    delivery_results: list[dict[str, Any]] = Field(default_factory=list)
    suppression_reason: str | None = None
    last_error: str | None = None


class AlertPolicyCreate(BaseModel):
    name: str
    enabled: bool = True
    monitored_area_ids: list[str] = Field(default_factory=list)
    incident_categories: list[str] = Field(default_factory=lambda: ["forest_disturbance"])
    minimum_investigation_priority: str = "medium"
    minimum_severity: str = "medium"
    minimum_evidence_state: str | None = None
    notification_channel_ids: list[str] = Field(default_factory=list)
    cooldown_minutes: int = 60


class AlertPolicyUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    monitored_area_ids: list[str] | None = None
    incident_categories: list[str] | None = None
    minimum_investigation_priority: str | None = None
    minimum_severity: str | None = None
    minimum_evidence_state: str | None = None
    notification_channel_ids: list[str] | None = None
    cooldown_minutes: int | None = None


class NotificationChannelCreate(BaseModel):
    channel_type: NotificationChannelType
    name: str
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class NotificationChannelUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    config: dict[str, Any] | None = None


class AlertPolicyPublic(BaseModel):
    id: str
    organization_id: str
    name: str
    enabled: bool
    monitored_area_ids: list[str]
    incident_categories: list[str]
    minimum_investigation_priority: str
    minimum_severity: str
    minimum_evidence_state: str | None
    notification_channel_ids: list[str]
    cooldown_minutes: int
    created_at: datetime
    updated_at: datetime


class NotificationChannelPublic(BaseModel):
    id: str
    organization_id: str
    channel_type: NotificationChannelType
    name: str
    enabled: bool
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AlertDeliveryChannelOutcome(BaseModel):
    """Per-channel dispatch outcome — no secret material, no raw provider ids."""

    channel_id: str
    channel_type: NotificationChannelType | str
    channel_type_label: str
    channel_name: str | None = None
    delivered: bool
    failure_reason: str | None = None
    simulated: bool = False


class AlertDeliveryPublic(BaseModel):
    id: str
    dedupe_key: str
    organization_id: str
    policy_id: str
    policy_name: str | None = None
    intelligence_event_id: str
    incident_category: str | None = None
    incident_category_label: str | None = None
    alert_stage: str
    alert_stage_label: str
    monitored_area_ids: list[str]
    monitored_area_names: list[str] = Field(default_factory=list)
    reason: str
    priority: str
    evidence_summary: dict[str, Any]
    lifecycle: str
    delivery_state_label: str
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None
    dispatch_attempt_count: int = 0
    last_attempt_at: datetime | None = None
    channel_outcomes: list[AlertDeliveryChannelOutcome] = Field(default_factory=list)
    suppression_reason: str | None = None
    suppression_reason_label: str | None = None
    last_error: str | None = None
    simulated: bool = False


class AlertOperationsOverview(BaseModel):
    """Compact alert operations projection for the Command Center."""

    alert_delivery_available: bool
    can_manage: bool
    policy_count: int
    active_policy_count: int
    channel_count: int
    enabled_channel_count: int
    channel_states: list[dict[str, Any]] = Field(default_factory=list)
    pending_count: int
    sent_count: int
    failed_count: int
    suppressed_count: int
    attention_count: int
    recent_deliveries: list[AlertDeliveryPublic] = Field(default_factory=list)
