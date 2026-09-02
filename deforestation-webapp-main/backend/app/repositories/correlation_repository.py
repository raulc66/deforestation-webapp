"""MongoDB persistence for cross-source correlation results."""
from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase


def _fmt(doc: dict) -> dict:
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


class CorrelationRepository:
    collection_name = "intelligence_correlations"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[self.collection_name]

    async def replace_all(
        self,
        records: list[dict],
        *,
        intelligence_cycle_id: str | None = None,
    ) -> None:
        """Replace the full correlation snapshot for the latest reconciliation cycle."""
        await self.col.delete_many({})
        if records:
            stamped = []
            for record in records:
                doc = dict(record)
                if intelligence_cycle_id:
                    doc["intelligence_cycle_id"] = intelligence_cycle_id
                stamped.append(doc)
            await self.col.insert_many(stamped)

    async def get_snapshot_cycle_id(self) -> str | None:
        doc = await self.col.find_one({}, sort=[("correlation_id", 1)])
        if not doc:
            return None
        value = doc.get("intelligence_cycle_id")
        return str(value) if value else None

    async def list_all(self) -> list[dict]:
        cursor = self.col.find({}).sort("correlation_id", 1)
        return [_fmt(doc) async for doc in cursor]

    async def count(self) -> int:
        return await self.col.count_documents({})
