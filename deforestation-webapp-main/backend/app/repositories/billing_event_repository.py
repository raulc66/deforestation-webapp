"""MongoDB persistence for the Stripe webhook idempotency ledger.

Idempotency is enforced by the unique index on ``stripe_event_id``: the first
writer wins the insert and processes the event, every later delivery of the same
event loses the insert and is skipped.

The one exception is an event whose processing failed. Stripe retries those, and
a ledger row that blocked the retry would strand the subscription in a stale
state forever, so a failed row can be re-claimed exactly once per delivery.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.models.billing import BillingEvent
from app.repositories.base import BaseRepository


class BillingEventRepository(BaseRepository[BillingEvent]):
    collection_name = "billing_events"
    model = BillingEvent

    async def claim(
        self,
        *,
        stripe_event_id: str,
        event_type: str,
        event_created_at: datetime | None = None,
    ) -> BillingEvent | None:
        """Reserve an event for processing, or ``None`` if already claimed."""
        event = BillingEvent(
            stripe_event_id=stripe_event_id,
            event_type=event_type,
            event_created_at=event_created_at,
            status="received",
            received_at=datetime.now(timezone.utc),
        )
        try:
            return await self.insert(event)
        except DuplicateKeyError:
            return await self._reclaim_failed(stripe_event_id)

    async def _reclaim_failed(self, stripe_event_id: str) -> BillingEvent | None:
        """Take over a previously failed event when Stripe redelivers it.

        The status filter makes this atomic: only one concurrent delivery can
        move the row out of ``failed``, so a redelivery storm still results in a
        single reprocessing attempt at a time.
        """
        doc = await self.col.find_one_and_update(
            {"stripe_event_id": stripe_event_id, "status": "failed"},
            {
                "$set": {
                    "status": "received",
                    "received_at": datetime.now(timezone.utc),
                    "processed_at": None,
                },
                "$inc": {"attempt_count": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        return self.model.from_mongo(doc)

    async def find_by_stripe_event_id(self, stripe_event_id: str) -> BillingEvent | None:
        return await self.find_one({"stripe_event_id": stripe_event_id})

    async def mark_outcome(
        self,
        event_id: str,
        *,
        status: str,
        organization_id: str | None = None,
        detail: str | None = None,
    ) -> bool:
        updates: dict = {
            "status": status,
            "processed_at": datetime.now(timezone.utc),
        }
        if organization_id is not None:
            updates["organization_id"] = organization_id
        if detail is not None:
            updates["detail"] = detail
        return await self.update(event_id, updates)

    async def latest(self, *, organization_id: str | None = None) -> BillingEvent | None:
        """Newest delivery whatever its outcome — the operator's "is it moving"."""
        query: dict = {}
        if organization_id is not None:
            query["organization_id"] = organization_id
        rows = await self.find_many(query, limit=1, sort=[("received_at", -1)])
        return rows[0] if rows else None

    async def latest_processed(
        self,
        *,
        organization_id: str | None = None,
    ) -> BillingEvent | None:
        query: dict = {"status": {"$in": ["processed", "ignored"]}}
        if organization_id is not None:
            query["organization_id"] = organization_id
        rows = await self.find_many(query, limit=1, sort=[("received_at", -1)])
        return rows[0] if rows else None

    async def latest_failure(
        self,
        *,
        organization_id: str | None = None,
    ) -> BillingEvent | None:
        query: dict = {"status": "failed"}
        if organization_id is not None:
            query["organization_id"] = organization_id
        rows = await self.find_many(query, limit=1, sort=[("received_at", -1)])
        return rows[0] if rows else None

    async def count_failed(self, *, organization_id: str | None = None) -> int:
        query: dict = {"status": "failed"}
        if organization_id is not None:
            query["organization_id"] = organization_id
        return await self.count(query)
