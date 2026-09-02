"""Persistence for the current intelligence reconciliation cycle."""
from __future__ import annotations

from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

_CURRENT_DOC_ID = "current"


def _fmt(doc: dict) -> dict:
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


class IntelligenceCycleRepository:
    collection_name = "intelligence_cycle_state"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[self.collection_name]

    async def get_current(self) -> dict | None:
        doc = await self.col.find_one({"_id": _CURRENT_DOC_ID})
        return _fmt(doc) if doc else None

    async def set_current(
        self,
        *,
        intelligence_cycle_id: str,
        detection_fingerprint: str,
        correlation_cycle_id: str | None,
        reconciled_at: datetime,
    ) -> dict:
        record = {
            "_id": _CURRENT_DOC_ID,
            "intelligence_cycle_id": intelligence_cycle_id,
            "detection_fingerprint": detection_fingerprint,
            "correlation_cycle_id": correlation_cycle_id,
            "reconciled_at": reconciled_at,
        }
        await self.col.replace_one({"_id": _CURRENT_DOC_ID}, record, upsert=True)
        return _fmt(record)
