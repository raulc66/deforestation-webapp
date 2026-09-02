"""Persistence for demonstration sessions and product events."""
from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.demo.constants import (
    DEMO_PRODUCT_EVENT_COLLECTION,
    DEMO_SESSION_COLLECTION,
)
from app.models.demo import DemoProductEvent, DemoSession


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class DemoSessionRepository:
    collection_name = DEMO_SESSION_COLLECTION
    model = DemoSession

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[self.collection_name]
        self._events = db[DEMO_PRODUCT_EVENT_COLLECTION]

    async def insert(self, doc: DemoSession) -> DemoSession:
        payload = doc.to_mongo()
        payload.pop("_id", None)
        result = await self.col.insert_one(payload)
        doc.id = str(result.inserted_id)
        return doc

    async def find_by_id(self, session_id: str) -> DemoSession | None:
        if not ObjectId.is_valid(session_id):
            return None
        raw = await self.col.find_one({"_id": ObjectId(session_id)})
        return DemoSession.from_mongo(raw)

    async def update(self, session_id: str, updates: dict) -> bool:
        if not ObjectId.is_valid(session_id):
            return False
        result = await self.col.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": updates},
        )
        return result.matched_count > 0

    async def record_product_event(self, event: DemoProductEvent) -> DemoProductEvent:
        payload = event.to_mongo()
        payload.pop("_id", None)
        result = await self._events.insert_one(payload)
        event.id = str(result.inserted_id)
        return event

    async def list_product_events(
        self,
        session_id: str,
        *,
        limit: int = 50,
    ) -> list[DemoProductEvent]:
        cursor = (
            self._events.find({"session_id": session_id})
            .sort("created_at", -1)
            .limit(limit)
        )
        return [DemoProductEvent.from_mongo(doc) for doc in await cursor.to_list(limit)]
