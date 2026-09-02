"""MongoDB persistence for the intelligence reconciliation advisory lock (WP7).

Each lock is a single document keyed by a fixed ``_id``.  Acquisition uses
atomic ``find_one_and_update`` / ``insert_one`` so only one process holder can
own the lock at a time across application instances.

Document schema::

    {
        "_id":        str   (fixed lock name, e.g. "intelligence_reconciliation"),
        "holder_id":  str   (unique scheduler instance identifier),
        "acquired_at": datetime (UTC),
        "expires_at":  datetime (UTC, lease boundary for stale-lock recovery)
    }
"""
from __future__ import annotations

from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError


class ReconciliationLockRepository:
    collection_name = "reconciliation_locks"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[self.collection_name]

    async def try_acquire(
        self,
        *,
        lock_id: str,
        holder_id: str,
        acquired_at: datetime,
        expires_at: datetime,
    ) -> bool:
        """Attempt to acquire *lock_id* for *holder_id*.

        Succeeds when the lock is absent, expired, or already held by the same
        *holder_id* (idempotent re-acquire within the same process).
        """
        doc = await self.col.find_one_and_update(
            {
                "_id": lock_id,
                "$or": [
                    {"expires_at": {"$lte": acquired_at}},
                    {"holder_id": holder_id},
                ],
            },
            {
                "$set": {
                    "holder_id": holder_id,
                    "acquired_at": acquired_at,
                    "expires_at": expires_at,
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        if doc is not None and doc.get("holder_id") == holder_id:
            return True

        try:
            await self.col.insert_one(
                {
                    "_id": lock_id,
                    "holder_id": holder_id,
                    "acquired_at": acquired_at,
                    "expires_at": expires_at,
                }
            )
            return True
        except DuplicateKeyError:
            return False

    async def release(
        self,
        *,
        lock_id: str,
        holder_id: str,
        released_at: datetime,
    ) -> bool:
        """Release *lock_id* when held by *holder_id*.

        Sets ``expires_at`` to *released_at* so another instance can acquire
        immediately without waiting for lease expiry.
        """
        doc = await self.col.find_one_and_update(
            {"_id": lock_id, "holder_id": holder_id},
            {"$set": {"expires_at": released_at}},
            return_document=ReturnDocument.AFTER,
        )
        return doc is not None

    async def get_lock(self, lock_id: str) -> dict | None:
        """Return the raw lock document (used in tests/diagnostics)."""
        return await self.col.find_one({"_id": lock_id})
