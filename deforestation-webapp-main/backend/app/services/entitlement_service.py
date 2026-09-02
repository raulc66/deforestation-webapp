"""Authoritative commercial entitlement evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.commercial.entitlement_types import (
    DEFAULT_ENTITLEMENT_PROFILE,
    DEFAULT_ENTITLEMENT_SOURCE,
    EntitlementType,
)
from app.repositories.forest_monitoring_area_repository import ForestMonitoringAreaRepository
from app.repositories.organization_entitlement_repository import OrganizationEntitlementRepository


@dataclass(frozen=True)
class EntitlementProfile:
    organization_id: str
    monitored_area_limit: int
    monitoring_enabled: bool
    forest_disturbance_enabled: bool
    evidence_correlation_enabled: bool
    live_sources_enabled: bool
    alert_delivery_enabled: bool
    source: str
    alert_policy_limit: int = 0
    notification_channel_limit: int = 0

    def as_read_model(self, *, monitored_area_count: int) -> dict[str, Any]:
        return {
            "monitored_area_limit": self.monitored_area_limit,
            "monitored_area_count": monitored_area_count,
            "monitoring_enabled": self.monitoring_enabled,
            "forest_disturbance_enabled": self.forest_disturbance_enabled,
            "evidence_correlation_enabled": self.evidence_correlation_enabled,
            "live_sources_enabled": self.live_sources_enabled,
            "alert_delivery_enabled": self.alert_delivery_enabled,
            "alert_policy_limit": self.alert_policy_limit,
            "notification_channel_limit": self.notification_channel_limit,
        }


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class EntitlementService:
    """Single authoritative entitlement evaluation service."""

    def __init__(
        self,
        entitlement_repo: OrganizationEntitlementRepository,
        area_repo: ForestMonitoringAreaRepository,
    ) -> None:
        self._entitlements = entitlement_repo
        self._areas = area_repo

    async def ensure_default_entitlements(self, organization_id: str) -> None:
        existing = await self._entitlements.list_for_organization(organization_id)
        if existing:
            return
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        for entitlement_type, value in DEFAULT_ENTITLEMENT_PROFILE.items():
            from app.models.organization import OrganizationEntitlement

            await self._entitlements.insert(
                OrganizationEntitlement(
                    organization_id=organization_id,
                    entitlement_type=entitlement_type,
                    value=value,
                    source=DEFAULT_ENTITLEMENT_SOURCE,
                    effective_from=now,
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )

    async def get_profile(self, organization_id: str) -> EntitlementProfile:
        rows = await self._entitlements.list_for_organization(organization_id)
        values = dict(DEFAULT_ENTITLEMENT_PROFILE)
        source = DEFAULT_ENTITLEMENT_SOURCE
        for row in rows:
            values[row.entitlement_type] = row.value
            source = row.source or source
        return EntitlementProfile(
            organization_id=organization_id,
            monitored_area_limit=_coerce_int(
                values.get(EntitlementType.MONITORED_AREA_LIMIT.value), 1
            ),
            monitoring_enabled=_coerce_bool(
                values.get(EntitlementType.MONITORING_ENABLED.value), True
            ),
            forest_disturbance_enabled=_coerce_bool(
                values.get(EntitlementType.FOREST_DISTURBANCE_ENABLED.value), True
            ),
            evidence_correlation_enabled=_coerce_bool(
                values.get(EntitlementType.EVIDENCE_CORRELATION_ENABLED.value), False
            ),
            live_sources_enabled=_coerce_bool(
                values.get(EntitlementType.LIVE_SOURCES_ENABLED.value), False
            ),
            alert_delivery_enabled=_coerce_bool(
                values.get(EntitlementType.ALERT_DELIVERY_ENABLED.value), False
            ),
            alert_policy_limit=_coerce_int(
                values.get(EntitlementType.ALERT_POLICY_LIMIT.value), 0
            ),
            notification_channel_limit=_coerce_int(
                values.get(EntitlementType.NOTIFICATION_CHANNEL_LIMIT.value), 0
            ),
            source=source,
        )

    async def count_enabled_monitoring_areas(self, organization_id: str) -> int:
        areas = await self._areas.list_for_organization(
            organization_id,
            enabled_only=True,
        )
        return len(areas)

    async def can_monitor(self, organization_id: str) -> bool:
        profile = await self.get_profile(organization_id)
        return profile.monitoring_enabled

    async def can_add_monitoring_area(self, organization_id: str) -> bool:
        profile = await self.get_profile(organization_id)
        if not profile.monitoring_enabled:
            return False
        count = await self.count_enabled_monitoring_areas(organization_id)
        return count < profile.monitored_area_limit

    async def can_use_forest_disturbance(self, organization_id: str) -> bool:
        profile = await self.get_profile(organization_id)
        return profile.forest_disturbance_enabled and profile.monitoring_enabled

    async def can_use_cross_source_correlation(self, organization_id: str) -> bool:
        profile = await self.get_profile(organization_id)
        return profile.evidence_correlation_enabled

    async def can_use_live_sources(self, organization_id: str) -> bool:
        profile = await self.get_profile(organization_id)
        return profile.live_sources_enabled

    async def can_receive_alerts(self, organization_id: str) -> bool:
        profile = await self.get_profile(organization_id)
        return profile.alert_delivery_enabled

    async def apply_profile(
        self,
        organization_id: str,
        profile: dict[str, Any],
        *,
        source: str,
        now: datetime | None = None,
    ) -> list[str]:
        """Write entitlement rows for a static profile. Does not evaluate them."""
        from datetime import timezone

        from app.models.organization import OrganizationEntitlement

        stamped = now or datetime.now(timezone.utc)
        changed: list[str] = []
        for entitlement_type in (member.value for member in EntitlementType):
            if entitlement_type not in profile:
                continue
            value = profile[entitlement_type]
            existing = await self._entitlements.find_by_type(
                organization_id,
                entitlement_type,
            )
            if existing is None:
                await self._entitlements.insert(
                    OrganizationEntitlement(
                        organization_id=organization_id,
                        entitlement_type=entitlement_type,
                        value=value,
                        source=source,
                        effective_from=stamped,
                        status="active",
                        created_at=stamped,
                        updated_at=stamped,
                    )
                )
                changed.append(entitlement_type)
                continue
            if existing.value == value and existing.source == source:
                continue
            await self._entitlements.update(
                str(existing.id),
                {
                    "value": value,
                    "source": source,
                    "effective_from": stamped,
                    "effective_until": None,
                    "status": "active",
                    "updated_at": stamped,
                },
            )
            changed.append(entitlement_type)
        return changed
