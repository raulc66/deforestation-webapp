"""Repository for the ``notification_history`` MongoDB collection.

Schema
------
Each document records one outbound notification attempt::

    {
        "_id":        ObjectId,
        "provider":   "discord" | "generic",
        "event_type": str,          # e.g. "new_anomaly", "escalation_change"
        "region":     str,
        "sent_at":    datetime (UTC),
        "success":    bool,
        "error":      str | None,   # populated on failure
    }

Public API
----------
``create_entry(...)``   — insert one history document and return it shaped.
``latest()``            — return the most-recently-sent document or ``None``.
``list_recent(limit)``  — return the *limit* most-recent documents.
"""
from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


def _shape(doc: dict) -> dict:
    """Convert a raw MongoDB document to the public representation."""
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    # Ensure sent_at is returned as a UTC-aware datetime
    if isinstance(doc.get("sent_at"), datetime) and doc["sent_at"].tzinfo is None:
        doc["sent_at"] = doc["sent_at"].replace(tzinfo=timezone.utc)
    return doc


class NotificationHistoryRepository:
    """Read/write access to the ``notification_history`` collection."""

    collection_name = "notification_history"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db[self.collection_name]

    # ------------------------------------------------------------------ #
    # Write
    # ------------------------------------------------------------------ #

    async def create_entry(
        self,
        *,
        provider: str,
        event_type: str,
        region: str,
        success: bool,
        error: str | None = None,
        sent_at: datetime | None = None,
    ) -> dict:
        """Insert one notification history record.

        ``sent_at`` defaults to the current UTC time when omitted.
        Returns the shaped document including the generated ``id``.
        """
        now = sent_at or datetime.now(timezone.utc)
        doc = {
            "provider": provider,
            "event_type": event_type,
            "region": region,
            "sent_at": now,
            "success": success,
            "error": error,
        }
        result = await self._col.insert_one(doc)
        doc["_id"] = result.inserted_id
        return _shape(doc)

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    async def latest(self) -> dict | None:
        """Return the most-recently-sent notification, or ``None``."""
        doc = await self._col.find_one({}, sort=[("sent_at", -1)])
        return _shape(doc) if doc else None

    async def list_recent(self, limit: int = 50) -> list[dict]:
        """Return the *limit* most-recent notifications, newest first."""
        cursor = self._col.find({}, sort=[("sent_at", -1)]).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [_shape(d) for d in docs]
