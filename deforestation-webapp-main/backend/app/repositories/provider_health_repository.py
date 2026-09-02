"""MongoDB persistence for provider health state."""
from __future__ import annotations

from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase


def _fmt(doc: dict) -> dict:
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


class ProviderHealthRepository:
    collection_name = "provider_health"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[self.collection_name]

    async def upsert(self, provider_id: str, record: dict) -> dict:
        await self.col.update_one(
            {"provider_id": provider_id},
            {"$set": record},
            upsert=True,
        )
        doc = await self.col.find_one({"provider_id": provider_id})
        return _fmt(doc) if doc else record

    async def get(self, provider_id: str) -> dict | None:
        doc = await self.col.find_one({"provider_id": provider_id})
        return _fmt(doc) if doc else None

    async def list_all(self) -> list[dict]:
        cursor = self.col.find({}).sort("provider_id", 1)
        return [_fmt(doc) async for doc in cursor]

    async def record_run_outcome(
        self,
        *,
        provider_id: str,
        display_name: str,
        success: bool,
        started_at: datetime,
        completed_at: datetime,
        observations_received: int,
        observations_persisted: int,
        observations_rejected: int,
        current_status: str,
        error: str | None = None,
        last_execution_mode: str | None = None,
    ) -> dict:
        existing = await self.get(provider_id) or {}
        consecutive = 0 if success else int(existing.get("consecutive_failures", 0)) + 1
        record = {
            "provider_id": provider_id,
            "display_name": display_name,
            "current_status": current_status,
            "last_attempt_at": started_at,
            "last_success_at": completed_at if success else existing.get("last_success_at"),
            "last_failure_at": completed_at if not success else existing.get("last_failure_at"),
            "consecutive_failures": consecutive,
            "observations_received": observations_received,
            "observations_rejected": observations_rejected,
            "observations_persisted": observations_persisted,
            "last_fetch_duration_seconds": round(
                (completed_at - started_at).total_seconds(), 3
            ),
            "last_error": error,
            "updated_at": completed_at,
        }
        if last_execution_mode:
            record["last_execution_mode"] = last_execution_mode
        return await self.upsert(provider_id, record)
