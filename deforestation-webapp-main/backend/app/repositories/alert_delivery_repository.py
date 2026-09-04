"""MongoDB persistence for customer alert delivery records."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.customer_alert import (
    DISPATCHABLE_LIFECYCLES,
    AlertDeliveryRecord,
    AlertLifecycle,
)

# Lifecycles that count as "the organization was actually notified".
_NOTIFIED_LIFECYCLES = (
    AlertLifecycle.SENT.value,
    AlertLifecycle.ACKNOWLEDGED.value,
    AlertLifecycle.RESOLVED.value,
)


def _shape(doc: dict) -> dict:
    shaped = dict(doc)
    if "_id" in shaped:
        shaped["id"] = str(shaped.pop("_id"))
    return shaped


class AlertDeliveryRepository:
    collection_name = "alert_deliveries"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db[self.collection_name]

    async def find_by_dedupe_key(self, dedupe_key: str) -> dict | None:
        doc = await self._col.find_one({"dedupe_key": dedupe_key})
        return _shape(doc) if doc else None

    async def create(self, record: AlertDeliveryRecord) -> dict:
        payload = record.to_mongo()
        payload.pop("_id", None)
        result = await self._col.insert_one(payload)
        return _shape({**payload, "_id": result.inserted_id})

    async def update(self, record_id: str, updates: dict) -> bool:
        if not ObjectId.is_valid(record_id):
            return False
        result = await self._col.update_one({"_id": ObjectId(record_id)}, {"$set": updates})
        return result.modified_count > 0

    async def list_pending(self, *, limit: int = 100) -> list[dict]:
        """Records awaiting a first dispatch attempt.

        Terminal states (``sent`` / ``failed`` / ``suppressed``) are excluded so a
        failed delivery is never silently re-attempted every scheduler cycle.
        """
        cursor = (
            self._col.find({"lifecycle": {"$in": list(DISPATCHABLE_LIFECYCLES)}})
            .sort("created_at", 1)
            .limit(limit)
        )
        return [_shape(doc) for doc in await cursor.to_list(length=limit)]

    async def list_for_organization(
        self,
        organization_id: str,
        *,
        limit: int = 50,
        lifecycle: str | None = None,
        demo_visitor_session_id: str | None = None,
    ) -> list[dict]:
        query: dict = {"organization_id": organization_id}
        if lifecycle:
            query["lifecycle"] = lifecycle
        if demo_visitor_session_id:
            # Keep curated/shared rows and this visitor's simulations; drop other
            # visitors' session-tagged rows at the source. Legacy rows without
            # evidence.demo_session_id are still filtered in the read model.
            query["$or"] = [
                {"evidence_summary.demo_session_id": demo_visitor_session_id},
                {"evidence_summary.demo_session_id": {"$exists": False}},
                {"evidence_summary.demo_session_id": None},
            ]
        cursor = self._col.find(query).sort("created_at", -1).limit(limit)
        return [_shape(doc) for doc in await cursor.to_list(length=limit)]

    async def count_by_lifecycle(self, organization_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        cursor = self._col.aggregate(
            [
                {"$match": {"organization_id": organization_id}},
                {"$group": {"_id": "$lifecycle", "total": {"$sum": 1}}},
            ]
        )
        for row in await cursor.to_list(length=50):
            counts[str(row.get("_id") or "unknown")] = int(row.get("total") or 0)
        return counts

    async def latest_sent_for_event(
        self,
        *,
        organization_id: str,
        policy_id: str,
        intelligence_event_id: str,
    ) -> dict | None:
        doc = await self._col.find_one(
            {
                "organization_id": organization_id,
                "policy_id": policy_id,
                "intelligence_event_id": intelligence_event_id,
                "lifecycle": {"$in": list(_NOTIFIED_LIFECYCLES)},
            },
            sort=[("sent_at", -1)],
        )
        return _shape(doc) if doc else None

    async def latest_attempt_for_event(
        self,
        *,
        organization_id: str,
        policy_id: str,
        intelligence_event_id: str,
    ) -> dict | None:
        """Most recent delivery record for the identity, regardless of outcome."""
        doc = await self._col.find_one(
            {
                "organization_id": organization_id,
                "policy_id": policy_id,
                "intelligence_event_id": intelligence_event_id,
            },
            sort=[("created_at", -1)],
        )
        return _shape(doc) if doc else None

    async def within_cooldown(
        self,
        *,
        organization_id: str,
        policy_id: str,
        intelligence_event_id: str,
        monitored_area_ids: list[str] | None = None,
        cooldown_minutes: int,
        now: datetime | None = None,
    ) -> bool:
        """Deterministic cooldown for one policy over one monitored area.

        The window is consumed by *any* recent delivery the policy produced for
        the same event or for an overlapping monitored area, which is what the
        customer-facing setting promises: "do not notify me about this forest
        more than once per interval".

        Record creation time is used rather than ``sent_at`` so a failed or
        suppressed dispatch still consumes the window; otherwise a broken channel
        would let the same alert be re-created on every scheduler cycle.
        """
        if cooldown_minutes <= 0:
            return False
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(minutes=cooldown_minutes)
        scopes: list[dict] = [{"intelligence_event_id": intelligence_event_id}]
        if monitored_area_ids:
            scopes.append({"monitored_area_ids": {"$in": list(monitored_area_ids)}})
        doc = await self._col.find_one(
            {
                "organization_id": organization_id,
                "policy_id": policy_id,
                "created_at": {"$gte": cutoff},
                "$or": scopes,
            }
        )
        return doc is not None
