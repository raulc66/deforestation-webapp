"""MongoDB persistence layer for IntelligenceEvents.

This repository is the *only* layer that touches the ``intelligence_events``
collection.  All methods return plain Python dicts with ``id`` as a string
(never a raw BSON ObjectId) so the service layer stays independent of BSON.
"""
from datetime import datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


def _fmt(doc: dict) -> dict:
    """Convert a MongoDB document to a service-layer dict.

    Replaces ``_id`` (ObjectId) with ``id`` (str) so callers never handle
    BSON types directly.
    """
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


class IntelligenceEventsRepository:
    collection_name = "intelligence_events"

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        *,
        collection_name: str | None = None,
    ) -> None:
        self.col = db[collection_name or self.collection_name]

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    async def find_active(self) -> list[dict]:
        """Return all active events, newest-first by last_detected_at."""
        return [
            _fmt(doc)
            async for doc in self.col.find({"status": "active"}).sort(
                "last_detected_at", -1
            )
        ]

    async def find_all(self) -> list[dict]:
        """Return every event regardless of status, newest-first."""
        return [
            _fmt(doc)
            async for doc in self.col.find({}).sort("last_detected_at", -1)
        ]

    async def find_active_by_identity(
        self,
        incident_category: str,
        spatial_key: str,
    ) -> dict | None:
        """Return the active event matching canonical identity, or None."""
        from app.core.ecosystem.incident_categories import normalize_incident_category

        doc = await self.col.find_one(
            {
                "status": "active",
                "incident_category": normalize_incident_category(incident_category),
                "spatial_key": str(spatial_key),
            }
        )
        return _fmt(doc) if doc else None

    async def find_active_by_region(self, event_type: str, region: str) -> dict | None:
        """Return the single active event matching *event_type* + *region*, or None."""
        doc = await self.col.find_one(
            {"event_type": event_type, "region": region, "status": "active"}
        )
        return _fmt(doc) if doc else None

    async def find_by_id(self, event_id: str) -> dict | None:
        """Return a single event by string id, or None."""
        if not ObjectId.is_valid(event_id):
            return None
        doc = await self.col.find_one({"_id": ObjectId(event_id)})
        return _fmt(doc) if doc else None

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #

    async def create(self, event: dict) -> dict:
        """Insert a new intelligence event and return it with its assigned id."""
        result = await self.col.insert_one(event)
        return _fmt({**event, "_id": result.inserted_id})

    async def update(self, event_id: str, update_data: dict) -> None:
        """Apply a partial update to an existing event identified by string id."""
        await self.col.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": update_data},
        )

    async def resolve(self, event_id: str, resolved_at: datetime) -> None:
        """Mark an event as resolved at *resolved_at*."""
        await self.col.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": {"status": "resolved", "resolved_at": resolved_at}},
        )
