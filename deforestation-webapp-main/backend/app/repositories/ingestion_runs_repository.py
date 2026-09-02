"""MongoDB persistence for background ingestion run history.

Each scheduler cycle (FIRMS ingestion + intelligence refresh) produces one
document in the ``ingestion_runs`` collection.  Documents are lightweight
— they exist only to power the ``GET /api/analytics/intelligence/ingestion-status``
endpoint and give operators a lightweight audit trail.

Document schema::

    {
        "_id":               ObjectId,
        "started_at":        datetime (UTC),
        "completed_at":      datetime (UTC),
        "duration_seconds":  float,
        "source":            str  ("NASA FIRMS"),
        "status":            str  ("success" | "failed"),
        "events_fetched":    int,
        "events_inserted":   int,
        "duplicates_skipped":int,
        "error":             str | null
    }
"""
from __future__ import annotations

from datetime import datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


def _fmt(doc: dict) -> dict:
    """Convert a raw MongoDB document to a service-layer dict with a string id."""
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


class IngestionRunsRepository:
    collection_name = "ingestion_runs"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[self.collection_name]

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #

    async def create_run(
        self,
        *,
        started_at: datetime,
        completed_at: datetime,
        source: str,
        status: str,
        events_fetched: int = 0,
        events_inserted: int = 0,
        duplicates_skipped: int = 0,
        error: str | None = None,
        provider_id: str | None = None,
        observations_rejected: int = 0,
        cycle_id: str | None = None,
    ) -> dict:
        """Insert one ingestion run record and return it with its assigned id.

        ``duration_seconds`` is computed from the supplied timestamps so
        callers never need to calculate it manually.
        """
        duration = (completed_at - started_at).total_seconds()
        doc = {
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_seconds": round(duration, 3),
            "source": source,
            "status": status,
            "events_fetched": events_fetched,
            "events_inserted": events_inserted,
            "duplicates_skipped": duplicates_skipped,
            "error": error,
        }
        if provider_id is not None:
            doc["provider_id"] = provider_id
        if observations_rejected:
            doc["observations_rejected"] = observations_rejected
        if cycle_id is not None:
            doc["cycle_id"] = cycle_id
        result = await self.col.insert_one(doc)
        return _fmt({**doc, "_id": result.inserted_id})

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    async def list_runs(self, limit: int = 50) -> list[dict]:
        """Return the most recent runs, newest-first."""
        cursor = self.col.find({}).sort("started_at", -1).limit(limit)
        return [_fmt(d) async for d in cursor]

    async def latest_run(self) -> dict | None:
        """Return the single most-recent run document, or ``None``."""
        doc = await self.col.find_one({}, sort=[("started_at", -1)])
        return _fmt(doc) if doc else None
