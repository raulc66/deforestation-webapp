"""Seed and reset the shared demonstration organization.

The catalog is shared across demo sessions (read-mostly). Session-scoped state
(usage, simulated deliveries, investigations) is reset per visitor.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.commercial.entitlement_types import EntitlementType
from app.core.demo.catalog import (
    AREAS,
    catalog_events,
    professional_like_entitlements,
)
from app.core.demo.constants import (
    DEMO_CATALOG_FLAG,
    DEMO_ORGANIZATION_KIND,
    DEMO_ORGANIZATION_NAME,
    DEMO_ORGANIZATION_SLUG,
)
from app.models.customer_alert import AlertPolicy, OrganizationNotificationChannel
from app.models.forest_monitoring_area import ForestMonitoringArea
from app.models.organization import Organization, OrganizationEntitlement


class DemoCatalogService:
    def __init__(
        self,
        *,
        org_repo: Any,
        area_repo: Any,
        entitlement_repo: Any,
        intel_repo: Any,
        policy_repo: Any,
        channel_repo: Any,
    ) -> None:
        self._orgs = org_repo
        self._areas = area_repo
        self._entitlements = entitlement_repo
        self._intel = intel_repo
        self._policies = policy_repo
        self._channels = channel_repo

    async def ensure_seeded(self) -> Organization:
        org = await self._orgs.find_by_slug(DEMO_ORGANIZATION_SLUG)
        if org is None:
            now = datetime.now(timezone.utc)
            org = await self._orgs.insert(
                Organization(
                    name=DEMO_ORGANIZATION_NAME,
                    slug=DEMO_ORGANIZATION_SLUG,
                    status="active",
                    kind=DEMO_ORGANIZATION_KIND,
                    created_at=now,
                    updated_at=now,
                )
            )
        elif getattr(org, "kind", None) != DEMO_ORGANIZATION_KIND:
            await self._orgs.update(str(org.id), {"kind": DEMO_ORGANIZATION_KIND})
            org = await self._orgs.find_by_id(str(org.id)) or org

        await self._ensure_entitlements(str(org.id))
        await self._ensure_areas(str(org.id))
        await self._ensure_events()
        await self._ensure_alert_surface(str(org.id))
        return org

    async def reset_catalog(self) -> Organization:
        """Restore demonstration forests and events. Never touches customer orgs."""
        org = await self.ensure_seeded()
        await self._replace_events()
        return org

    async def _ensure_entitlements(self, organization_id: str) -> None:
        existing = await self._entitlements.list_for_organization(organization_id)
        by_type = {row.entitlement_type: row for row in existing}
        now = datetime.now(timezone.utc)
        for key, value in professional_like_entitlements().items():
            row = by_type.get(key)
            if row is None:
                await self._entitlements.insert(
                    OrganizationEntitlement(
                        organization_id=organization_id,
                        entitlement_type=key,
                        value=value,
                        source="demo_catalog",
                        effective_from=now,
                        status="active",
                        created_at=now,
                        updated_at=now,
                    )
                )
            elif row.value != value or row.source != "demo_catalog":
                await self._entitlements.update(
                    str(row.id),
                    {"value": value, "source": "demo_catalog", "updated_at": now},
                )
        # Guarantee the enum keys exist even if the profile dict is extended.
        _ = EntitlementType.ALERT_DELIVERY_ENABLED

    async def _ensure_areas(self, organization_id: str) -> None:
        existing = await self._areas.list_for_organization(organization_id)
        by_name = {area.name: area for area in existing}
        now = datetime.now(timezone.utc)
        for spec in AREAS:
            found = by_name.get(spec["name"])
            if found is None:
                await self._areas.insert(
                    ForestMonitoringArea(
                        organization_id=organization_id,
                        tenant_id=organization_id,
                        name=spec["name"],
                        geometry=spec["geometry"],
                        geometry_type=spec["geometry_type"],
                        country=spec["country"],
                        enabled=True,
                        created_at=now,
                        updated_at=now,
                    )
                )

    async def _ensure_events(self) -> None:
        active = await self._intel.find_active()
        if active:
            return
        await self._replace_events()

    async def _replace_events(self) -> None:
        delete = getattr(self._intel, "delete_matching", None)
        if callable(delete):
            await delete({f"metadata.demo.{DEMO_CATALOG_FLAG}": True})
        else:
            col = getattr(self._intel, "col", None)
            if col is not None:
                await col.delete_many({f"metadata.demo.{DEMO_CATALOG_FLAG}": True})
        for event in catalog_events():
            payload = dict(event)
            catalog_key = payload.pop("catalog_key", None)
            metadata = dict(payload.get("metadata") or {})
            demo_meta = dict(metadata.get("demo") or {})
            if catalog_key:
                demo_meta["catalog_key"] = catalog_key
            metadata["demo"] = demo_meta
            payload["metadata"] = metadata
            await self._intel.create(payload)

    async def _ensure_alert_surface(self, organization_id: str) -> None:
        policies = await self._policies.list_for_organization(organization_id)
        channels = await self._channels.list_for_organization(organization_id)
        now = datetime.now(timezone.utc)
        if not channels:
            await self._channels.insert(
                OrganizationNotificationChannel(
                    organization_id=organization_id,
                    channel_type="email",
                    name="Demonstration inbox",
                    enabled=True,
                    config={
                        "recipients": ["demo-inbox@forestwatch.example"],
                        "simulated": True,
                    },
                    created_at=now,
                    updated_at=now,
                )
            )
            channels = await self._channels.list_for_organization(organization_id)
        if not policies:
            channel_ids = [str(ch.id) for ch in channels]
            await self._policies.insert(
                AlertPolicy(
                    organization_id=organization_id,
                    name="High-priority forest disturbance",
                    enabled=True,
                    incident_categories=["forest_disturbance"],
                    minimum_investigation_priority="medium",
                    minimum_severity="medium",
                    notification_channel_ids=channel_ids,
                    cooldown_minutes=60,
                    created_at=now,
                    updated_at=now,
                )
            )
