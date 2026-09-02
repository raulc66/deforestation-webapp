"""Simulated alert delivery for demonstration sessions.

Never calls email or webhook adapters. Writes a clearly labelled delivery
record against the demonstration organization only.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.demo.catalog import catalog_events
from app.core.errors import ForbiddenError, NotFoundError
from app.models.customer_alert import (
    AlertDeliveryRecord,
    AlertLifecycle,
    AlertStage,
    alert_dedupe_key,
)


class DemoAlertSimulationService:
    def __init__(
        self,
        *,
        sessions: Any,
        catalog: Any,
        policy_repo: Any,
        channel_repo: Any,
        delivery_repo: Any,
        intel_repo: Any,
    ) -> None:
        self._sessions = sessions
        self._catalog = catalog
        self._policies = policy_repo
        self._channels = channel_repo
        self._deliveries = delivery_repo
        self._intel = intel_repo

    async def simulate(
        self,
        session_id: str,
        *,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        org = await self._catalog.ensure_seeded()
        organization_id = str(org.id)
        policies = await self._policies.list_for_organization(
            organization_id, enabled_only=True
        )
        if not policies:
            raise NotFoundError("Demonstration alert policy is not available")
        policy = policies[0]
        channels = await self._channels.list_for_organization(
            organization_id, enabled_only=True
        )
        event = await self._resolve_event(event_id)
        now = datetime.now(timezone.utc)
        dedupe = alert_dedupe_key(
            organization_id=organization_id,
            policy_id=str(policy.id),
            intelligence_event_id=str(event["id"]),
            alert_stage=AlertStage.INITIAL.value,
        )
        existing = await self._deliveries.find_by_dedupe_key(dedupe)
        if existing is not None:
            return self._public(existing, simulated=True, already=True)

        record = AlertDeliveryRecord(
            dedupe_key=f"{dedupe}:demo:{session_id}",
            organization_id=organization_id,
            policy_id=str(policy.id),
            intelligence_event_id=str(event["id"]),
            alert_stage=AlertStage.INITIAL.value,
            monitored_area_ids=[],
            reason="Demonstration simulated match — no message was sent.",
            priority=str(
                ((event.get("metadata") or {}).get("forest_disturbance") or {}).get(
                    "investigation_priority"
                )
                or "high"
            ),
            evidence_summary={
                "simulated": True,
                "region": event.get("region"),
                "incident_category": event.get("incident_category"),
            },
            lifecycle=AlertLifecycle.SENT.value,
            created_at=now,
            updated_at=now,
            sent_at=now,
            dispatch_attempt_count=1,
            last_attempt_at=now,
            delivery_results=[
                {
                    "channel_type": "email",
                    "channel_name": channels[0].name if channels else "Demonstration inbox",
                    "status": "simulated",
                    "simulated": True,
                }
            ],
        )
        stored = await self._deliveries.create(record)
        await self._sessions.record(session_id, "alert_simulation_used", {
            "event_id": str(event["id"]),
        })
        return self._public(stored, simulated=True, already=False)

    async def _resolve_event(self, event_id: str | None) -> dict[str, Any]:
        if event_id:
            found = await self._intel.find_by_id(event_id)
            if found is None:
                raise NotFoundError("Demonstration event was not found")
            meta = found.get("metadata") or {}
            if not (meta.get("demo") or {}).get("demo_catalog") and not (
                meta.get("ingestion") or {}
            ).get("is_demo"):
                raise ForbiddenError("Demonstration alerts can only use demonstration events")
            return found
        catalog = {item["catalog_key"]: item for item in catalog_events()}
        wanted = catalog["evt-demo-high-priority"]
        active = await self._intel.find_active()
        for event in active:
            if event.get("region") == wanted["region"]:
                return event
        if active:
            return active[0]
        raise NotFoundError("Demonstration intelligence is not available")

    @staticmethod
    def _public(record: dict[str, Any], *, simulated: bool, already: bool) -> dict[str, Any]:
        return {
            "id": record.get("id"),
            "lifecycle": record.get("lifecycle"),
            "reason": record.get("reason"),
            "priority": record.get("priority"),
            "intelligence_event_id": record.get("intelligence_event_id"),
            "simulated": simulated,
            "already_recorded": already,
            "delivery_results": record.get("delivery_results") or [],
        }
