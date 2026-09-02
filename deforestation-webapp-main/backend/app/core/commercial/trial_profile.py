"""Deterministic free-trial entitlement profiles.

These profiles are written onto the existing ``OrganizationEntitlement`` rows
so a later paid plan can replace them through ``EntitlementSyncService``
without changing AOI, intelligence, alert, or Command Center architecture.
"""
from __future__ import annotations

from typing import Any

from app.core.commercial.entitlement_types import EntitlementType

TRIAL_ENTITLEMENT_SOURCE = "trial_profile"
TRIAL_EXPIRED_ENTITLEMENT_SOURCE = "trial_expired_profile"
DEFAULT_TRIAL_DURATION_DAYS = 14

# Enough of ForestWatch to demonstrate commercial value: two forests, the
# disturbance + evidence + live-source intelligence path, and one alert policy
# delivering only to the account email. Not unlimited production capacity.
TRIAL_ENTITLEMENT_PROFILE: dict[str, Any] = {
    EntitlementType.MONITORED_AREA_LIMIT.value: 2,
    EntitlementType.MONITORING_ENABLED.value: True,
    EntitlementType.FOREST_DISTURBANCE_ENABLED.value: True,
    EntitlementType.EVIDENCE_CORRELATION_ENABLED.value: True,
    EntitlementType.LIVE_SOURCES_ENABLED.value: True,
    EntitlementType.ALERT_DELIVERY_ENABLED.value: True,
    EntitlementType.ALERT_POLICY_LIMIT.value: 1,
    EntitlementType.NOTIFICATION_CHANNEL_LIMIT.value: 1,
}

# Historical intelligence and existing AOIs remain readable. New monitoring,
# live-source capability, and new alert delivery stop.
TRIAL_EXPIRED_ENTITLEMENT_PROFILE: dict[str, Any] = {
    EntitlementType.MONITORED_AREA_LIMIT.value: 0,
    EntitlementType.MONITORING_ENABLED.value: True,
    EntitlementType.FOREST_DISTURBANCE_ENABLED.value: True,
    EntitlementType.EVIDENCE_CORRELATION_ENABLED.value: True,
    EntitlementType.LIVE_SOURCES_ENABLED.value: False,
    EntitlementType.ALERT_DELIVERY_ENABLED.value: False,
    EntitlementType.ALERT_POLICY_LIMIT.value: 0,
    EntitlementType.NOTIFICATION_CHANNEL_LIMIT.value: 0,
}


def is_trial_entitlement_source(source: str | None) -> bool:
    return str(source or "") in {
        TRIAL_ENTITLEMENT_SOURCE,
        TRIAL_EXPIRED_ENTITLEMENT_SOURCE,
    }
