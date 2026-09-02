"""Commercial entitlement types and default profile values."""
from __future__ import annotations

from enum import StrEnum
from typing import Any


class EntitlementType(StrEnum):
    MONITORED_AREA_LIMIT = "monitored_area_limit"
    MONITORING_ENABLED = "monitoring_enabled"
    FOREST_DISTURBANCE_ENABLED = "forest_disturbance_enabled"
    EVIDENCE_CORRELATION_ENABLED = "evidence_correlation_enabled"
    LIVE_SOURCES_ENABLED = "live_sources_enabled"
    ALERT_DELIVERY_ENABLED = "alert_delivery_enabled"
    ALERT_POLICY_LIMIT = "alert_policy_limit"
    NOTIFICATION_CHANNEL_LIMIT = "notification_channel_limit"


class EntitlementStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


# Default foundation profile — enforcement mechanics, not final pricing.
DEFAULT_ENTITLEMENT_PROFILE: dict[str, Any] = {
    EntitlementType.MONITORED_AREA_LIMIT.value: 1,
    EntitlementType.MONITORING_ENABLED.value: True,
    EntitlementType.FOREST_DISTURBANCE_ENABLED.value: True,
    EntitlementType.EVIDENCE_CORRELATION_ENABLED.value: False,
    EntitlementType.LIVE_SOURCES_ENABLED.value: False,
    EntitlementType.ALERT_DELIVERY_ENABLED.value: False,
    EntitlementType.ALERT_POLICY_LIMIT.value: 0,
    EntitlementType.NOTIFICATION_CHANNEL_LIMIT.value: 0,
}

DEFAULT_ENTITLEMENT_SOURCE = "foundation_profile"
