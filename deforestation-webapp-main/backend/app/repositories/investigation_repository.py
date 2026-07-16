"""MongoDB persistence for investigations."""
from __future__ import annotations

import re
from typing import Any

from app.models.investigation import Investigation
from app.repositories.base import BaseRepository


class InvestigationRepository(BaseRepository[Investigation]):
    collection_name = "investigations"
    model = Investigation

    async def find_filtered(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        region: str | None = None,
        search: str | None = None,
        include_archived: bool = False,
        limit: int = 200,
    ) -> list[Investigation]:
        query: dict[str, Any] = {}
        if not include_archived:
            query["archived"] = {"$ne": True}
        if status:
            query["status"] = status
        if priority:
            query["priority"] = priority
        if region:
            query["region"] = region
        if search:
            pattern = re.compile(re.escape(search), re.IGNORECASE)
            query["$or"] = [
                {"title": pattern},
                {"description": pattern},
                {"region": pattern},
                {"tags": pattern},
            ]
        return await self.find_many(query, limit=limit, sort=[("updated_at", -1)])

    async def count_filtered(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        include_archived: bool = False,
    ) -> int:
        query: dict[str, Any] = {}
        if not include_archived:
            query["archived"] = {"$ne": True}
        if status:
            query["status"] = status
        if priority:
            query["priority"] = priority
        return await self.count(query)

    async def find_by_intelligence_event(
        self, intelligence_event_id: str
    ) -> Investigation | None:
        return await self.find_one(
            {
                "intelligence_event_id": intelligence_event_id,
                "archived": {"$ne": True},
            }
        )

    async def aggregate_by_region(self) -> dict[str, int]:
        pipeline = [
            {"$match": {"archived": {"$ne": True}}},
            {"$group": {"_id": "$region", "count": {"$sum": 1}}},
        ]
        counts: dict[str, int] = {}
        async for doc in self.col.aggregate(pipeline):
            region = doc["_id"] or "Unknown"
            counts[region] = doc["count"]
        return counts

    async def find_closed_with_duration(self, limit: int = 500) -> list[dict]:
        """Return closed investigations with resolution duration in seconds."""
        cursor = self.col.find(
            {
                "archived": {"$ne": True},
                "closed_at": {"$ne": None},
                "created_at": {"$ne": None},
            }
        ).limit(limit)
        results = []
        async for doc in cursor:
            created = doc.get("created_at")
            closed = doc.get("closed_at")
            if created and closed:
                duration = (closed - created).total_seconds()
                results.append({"duration_seconds": duration})
        return results
