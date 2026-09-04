"""Simulated alert delivery for demonstration sessions.

Never calls email or webhook adapters. Writes a clearly labelled delivery
record against the demonstration organization only.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo.errors import DuplicateKeyError

from app.core.demo.catalog import catalog_events
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.customer_alert import (
    AlertDeliveryRecord,
    AlertLifecycle,
    AlertStage,
    alert_dedupe_key,
)


def demo_simulation_dedupe_key(
    canonical: str, session_id: str, reset_count: int = 0
) -> str:
    """Per-session, per-restart demo identity. Unique index still applies."""
    return f"{canonical}:demo:{session_id}:{int(reset_count)}"


def visitor_scope_from_delivery(row: dict[str, Any]) -> tuple[str, int] | None:
    """Return (session_id, reset_count) for visitor-generated demo simulations.

    Curated fixtures and production deliveries have no visitor scope.
    Older rows stored ``:demo:{session_id}`` without a reset count.
    """
    evidence = row.get("evidence_summary") or {}
    explicit = evidence.get("demo_session_id")
    if explicit:
        raw_reset = evidence.get("demo_reset_count")
        return str(explicit), int(raw_reset or 0)
    key = str(row.get("dedupe_key") or "")
    marker = ":demo:"
    if marker not in key or evidence.get("simulated") is not True:
        return None
    rest = key.rsplit(marker, 1)[-1]
    if not rest:
        return None
    if ":" in rest:
        session_part, maybe_reset = rest.rsplit(":", 1)
        if maybe_reset.isdigit():
            return session_part, int(maybe_reset)
    return rest, 0


def delivery_visible_in_demo_session(
    row: dict[str, Any], *, session_id: str, reset_count: int
) -> bool:
    scope = visitor_scope_from_delivery(row)
    if scope is None:
        return True
    visitor_id, visitor_reset = scope
    return visitor_id == session_id and visitor_reset == int(reset_count)


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
        session = await self._sessions.require(session_id)
        reset_count = int(session.reset_count)
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
        canonical = alert_dedupe_key(
            organization_id=organization_id,
            policy_id=str(policy.id),
            intelligence_event_id=str(event["id"]),
            alert_stage=AlertStage.INITIAL.value,
        )
        demo_key = demo_simulation_dedupe_key(canonical, session_id, reset_count)
        existing = await self._deliveries.find_by_dedupe_key(demo_key)
        if existing is not None:
            return self._public(existing, simulated=True, already=True)

        record = AlertDeliveryRecord(
            dedupe_key=demo_key,
            organization_id=organization_id,
            policy_id=str(policy.id),
            intelligence_event_id=str(event["id"]),
            alert_stage=AlertStage.INITIAL.value,
            monitored_area_ids=[],
            reason="Demonstration notification simulated.",
            priority=str(
                ((event.get("metadata") or {}).get("forest_disturbance") or {}).get(
                    "investigation_priority"
                )
                or "high"
            ),
            evidence_summary={
                "simulated": True,
                "demo_session_id": session_id,
                "demo_reset_count": reset_count,
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
        try:
            stored = await self._deliveries.create(record)
        except DuplicateKeyError:
            raced = await self._deliveries.find_by_dedupe_key(demo_key)
            if raced is not None:
                return self._public(raced, simulated=True, already=True)
            raise ConflictError("Demonstration notification was already recorded")
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
