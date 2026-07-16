"""Immutable timeline persistence for investigations — insert-only."""
from __future__ import annotations

from app.models.investigation import InvestigationTimelineEntry
from app.repositories.base import BaseRepository


class InvestigationTimelineRepository(BaseRepository[InvestigationTimelineEntry]):
    collection_name = "investigation_timeline"
    model = InvestigationTimelineEntry

    async def list_for_investigation(
        self, investigation_id: str, limit: int = 200
    ) -> list[InvestigationTimelineEntry]:
        return await self.find_many(
            {"investigation_id": investigation_id},
            limit=limit,
            sort=[("created_at", 1)],
        )
