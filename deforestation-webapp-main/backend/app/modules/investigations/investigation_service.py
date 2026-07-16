"""Investigation service — operational workflow independent from intel generation."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.core.errors import NotFoundError, ConflictError
from app.models.base import utcnow
from app.models.investigation import (
    Investigation,
    InvestigationAssign,
    InvestigationClose,
    InvestigationCreate,
    InvestigationPriority,
    InvestigationPublic,
    InvestigationStatus,
    InvestigationTimelineEntry,
    InvestigationUpdate,
    TimelineEventType,
)

if TYPE_CHECKING:
    from app.modules.analytics.intelligence_events_repository import (
        IntelligenceEventsRepository,
    )
    from app.repositories.investigation_repository import InvestigationRepository
    from app.repositories.investigation_timeline_repository import (
        InvestigationTimelineRepository,
    )
    from app.services.intelligence_notification_service import (
        IntelligenceNotificationService,
    )

logger = logging.getLogger("forestwatch.investigations")

_PRIORITY_ORDER = {
    InvestigationPriority.LOW: 0,
    InvestigationPriority.MEDIUM: 1,
    InvestigationPriority.HIGH: 2,
    InvestigationPriority.CRITICAL: 3,
}

_OPEN_STATUSES = {
    InvestigationStatus.OPEN,
    InvestigationStatus.IN_PROGRESS,
    InvestigationStatus.WAITING,
}


def _to_public(inv: Investigation) -> InvestigationPublic:
    return InvestigationPublic(
        id=inv.id or "",
        intelligence_event_id=inv.intelligence_event_id,
        title=inv.title,
        description=inv.description,
        status=inv.status,
        priority=inv.priority,
        assigned_to=inv.assigned_to,
        organization=inv.organization,
        created_by=inv.created_by,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
        closed_at=inv.closed_at,
        resolution=inv.resolution,
        tags=inv.tags,
        recommended_actions=inv.recommended_actions,
        actual_actions=inv.actual_actions,
        outcome=inv.outcome,
        region=inv.region,
    )


class InvestigationService:
    """Manages investigation lifecycle, timeline, and statistics."""

    def __init__(
        self,
        repo: "InvestigationRepository",
        timeline_repo: "InvestigationTimelineRepository",
        intel_repo: "IntelligenceEventsRepository | None" = None,
        notification_svc: "IntelligenceNotificationService | None" = None,
    ) -> None:
        self._repo = repo
        self._timeline = timeline_repo
        self._intel_repo = intel_repo
        self._notification_svc = notification_svc

    async def _append_timeline(
        self,
        investigation_id: str,
        event_type: TimelineEventType,
        message: str,
        *,
        actor: str | None = None,
        metadata: dict | None = None,
    ) -> InvestigationTimelineEntry:
        entry = InvestigationTimelineEntry(
            investigation_id=investigation_id,
            event_type=event_type,
            message=message,
            actor=actor,
            metadata=metadata or {},
        )
        return await self._timeline.insert(entry)

    async def _get_intel_event(self, event_id: str) -> dict | None:
        if self._intel_repo is None:
            return None
        return await self._intel_repo.find_by_id(event_id)

    async def create(
        self,
        payload: InvestigationCreate,
        *,
        created_by: str,
    ) -> dict:
        region: str | None = None
        recommended = list(payload.recommended_actions)

        if payload.intelligence_event_id:
            existing = await self._repo.find_by_intelligence_event(
                payload.intelligence_event_id
            )
            if existing:
                raise ConflictError(
                    "An active investigation already exists for this intelligence event"
                )
            intel = await self._get_intel_event(payload.intelligence_event_id)
            if intel:
                region = intel.get("region")
                if not recommended and intel.get("metadata", {}).get(
                    "recommended_actions"
                ):
                    recommended = list(intel["metadata"]["recommended_actions"])

        now = utcnow()
        inv = Investigation(
            intelligence_event_id=payload.intelligence_event_id,
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            assigned_to=payload.assigned_to,
            organization=payload.organization,
            created_by=created_by,
            created_at=now,
            updated_at=now,
            tags=payload.tags,
            recommended_actions=recommended,
            region=region,
        )
        inv = await self._repo.insert(inv)
        inv_id = inv.id or ""

        if payload.intelligence_event_id and region:
            await self._append_timeline(
                inv_id,
                TimelineEventType.THREAT_DETECTED,
                f"Threat detected in {region} (linked intelligence event).",
                actor=created_by,
                metadata={"intelligence_event_id": payload.intelligence_event_id},
            )

        await self._append_timeline(
            inv_id,
            TimelineEventType.INVESTIGATION_CREATED,
            f"Investigation created: {inv.title}",
            actor=created_by,
        )

        if payload.assigned_to:
            await self._append_timeline(
                inv_id,
                TimelineEventType.ASSIGNED,
                f"Assigned to {payload.assigned_to}",
                actor=created_by,
                metadata={"assigned_to": payload.assigned_to},
            )

        public = _to_public(inv)
        await self._notify_created(public)
        return public.model_dump(mode="json")

    async def list_investigations(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        region: str | None = None,
        search: str | None = None,
    ) -> dict:
        docs = await self._repo.find_filtered(
            status=status,
            priority=priority,
            region=region,
            search=search,
        )
        items = [_to_public(d).model_dump(mode="json") for d in docs]
        return {"investigations": items, "total": len(items)}

    async def get_investigation(self, investigation_id: str) -> dict:
        inv = await self._repo.find_by_id(investigation_id)
        if not inv or inv.archived:
            raise NotFoundError("Investigation not found")
        timeline = await self._timeline.list_for_investigation(investigation_id)
        return {
            "investigation": _to_public(inv).model_dump(mode="json"),
            "timeline": [
                {
                    "id": t.id,
                    "event_type": t.event_type,
                    "message": t.message,
                    "actor": t.actor,
                    "metadata": t.metadata,
                    "created_at": t.created_at.isoformat(),
                }
                for t in timeline
            ],
        }

    async def update(
        self,
        investigation_id: str,
        payload: InvestigationUpdate,
        *,
        actor: str,
    ) -> dict:
        inv = await self._repo.find_by_id(investigation_id)
        if not inv or inv.archived:
            raise NotFoundError("Investigation not found")

        updates: dict[str, Any] = {"updated_at": utcnow()}
        data = payload.model_dump(exclude_unset=True)

        old_status = inv.status
        old_priority = inv.priority

        for key, value in data.items():
            updates[key] = value

        if "status" in data and data["status"] != old_status:
            await self._append_timeline(
                investigation_id,
                TimelineEventType.STATUS_CHANGED,
                f"Status changed: {old_status} → {data['status']}",
                actor=actor,
                metadata={"from": old_status, "to": data["status"]},
            )

        if "priority" in data and data["priority"] != old_priority:
            await self._append_timeline(
                investigation_id,
                TimelineEventType.PRIORITY_CHANGED,
                f"Priority changed: {old_priority} → {data['priority']}",
                actor=actor,
                metadata={"from": old_priority, "to": data["priority"]},
            )
            if _PRIORITY_ORDER.get(data["priority"], 0) > _PRIORITY_ORDER.get(
                old_priority, 0
            ):
                await self._notify_escalated(_to_public(inv), str(data["priority"]))

        await self._repo.update(investigation_id, updates)
        updated = await self._repo.find_by_id(investigation_id)
        return _to_public(updated).model_dump(mode="json")  # type: ignore[arg-type]

    async def assign(
        self,
        investigation_id: str,
        payload: InvestigationAssign,
        *,
        actor: str,
    ) -> dict:
        inv = await self._repo.find_by_id(investigation_id)
        if not inv or inv.archived:
            raise NotFoundError("Investigation not found")

        updates: dict[str, Any] = {
            "assigned_to": payload.assigned_to,
            "updated_at": utcnow(),
        }
        if payload.organization is not None:
            updates["organization"] = payload.organization
        if inv.status == InvestigationStatus.OPEN:
            updates["status"] = InvestigationStatus.IN_PROGRESS

        await self._repo.update(investigation_id, updates)
        await self._append_timeline(
            investigation_id,
            TimelineEventType.ASSIGNED,
            f"Assigned to {payload.assigned_to}",
            actor=actor,
            metadata={"assigned_to": payload.assigned_to},
        )

        updated = await self._repo.find_by_id(investigation_id)
        public = _to_public(updated)  # type: ignore[arg-type]
        await self._notify_assigned(public)
        return public.model_dump(mode="json")

    async def close(
        self,
        investigation_id: str,
        payload: InvestigationClose,
        *,
        actor: str,
    ) -> dict:
        inv = await self._repo.find_by_id(investigation_id)
        if not inv or inv.archived:
            raise NotFoundError("Investigation not found")

        now = utcnow()
        updates: dict[str, Any] = {
            "status": InvestigationStatus.CLOSED,
            "resolution": payload.resolution,
            "closed_at": now,
            "updated_at": now,
        }
        if payload.outcome is not None:
            updates["outcome"] = payload.outcome
        if payload.actual_actions is not None:
            updates["actual_actions"] = payload.actual_actions

        await self._repo.update(investigation_id, updates)
        await self._append_timeline(
            investigation_id,
            TimelineEventType.CLOSED,
            f"Investigation closed: {payload.resolution}",
            actor=actor,
            metadata={"resolution": payload.resolution},
        )

        updated = await self._repo.find_by_id(investigation_id)
        public = _to_public(updated)  # type: ignore[arg-type]
        await self._notify_closed(public)
        return public.model_dump(mode="json")

    async def archive(self, investigation_id: str) -> None:
        inv = await self._repo.find_by_id(investigation_id)
        if not inv or inv.archived:
            raise NotFoundError("Investigation not found")
        await self._repo.update(
            investigation_id, {"archived": True, "updated_at": utcnow()}
        )

    async def get_statistics(self) -> dict:
        open_count = await self._repo.count_filtered(
            status=InvestigationStatus.OPEN.value
        )
        in_progress = await self._repo.count_filtered(
            status=InvestigationStatus.IN_PROGRESS.value
        )
        waiting = await self._repo.count_filtered(
            status=InvestigationStatus.WAITING.value
        )
        critical = await self._repo.count_filtered(
            priority=InvestigationPriority.CRITICAL.value
        )
        by_region = await self._repo.aggregate_by_region()
        durations = await self._repo.find_closed_with_duration()
        avg_hours: float | None = None
        if durations:
            avg_seconds = sum(d["duration_seconds"] for d in durations) / len(
                durations
            )
            avg_hours = round(avg_seconds / 3600, 2)

        return {
            "open_investigations": open_count + in_progress + waiting,
            "critical_investigations": critical,
            "average_resolution_time_hours": avg_hours,
            "investigations_by_region": by_region,
        }

    async def get_summary_report(self) -> dict:
        """Compact summary for modular report sections."""
        stats = await self.get_statistics()
        recent = await self._repo.find_filtered(limit=20)
        return {
            **stats,
            "recent_investigations": [
                _to_public(d).model_dump(mode="json") for d in recent
            ],
        }

    async def _notify_created(self, inv: InvestigationPublic) -> None:
        if not self._notification_svc:
            return
        await self._notification_svc.notify_investigation_created(
            inv.model_dump(mode="json")
        )

    async def _notify_assigned(self, inv: InvestigationPublic) -> None:
        if not self._notification_svc:
            return
        await self._notification_svc.notify_investigation_assigned(
            inv.model_dump(mode="json")
        )

    async def _notify_escalated(
        self, inv: InvestigationPublic, new_priority: str
    ) -> None:
        if not self._notification_svc:
            return
        await self._notification_svc.notify_investigation_escalated(
            inv.model_dump(mode="json"), new_priority
        )

    async def _notify_closed(self, inv: InvestigationPublic) -> None:
        if not self._notification_svc:
            return
        await self._notification_svc.notify_investigation_closed(
            inv.model_dump(mode="json")
        )
