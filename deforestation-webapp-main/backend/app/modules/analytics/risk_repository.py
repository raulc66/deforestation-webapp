"""Risk repository — MongoDB persistence for daily regional risk snapshots.

Methods:
    create_snapshot(snapshot) — insert today's risk snapshot (idempotent per UTC day)
    latest()                  — most recent stored snapshot
    history(days)             — snapshots from the last N UTC days, newest first

Collection schema (risk_history)::

    {
        "date":       "YYYY-MM-DD",   # UTC date string — deduplication key
        "created_at": datetime,
        "regions": [
            {
                "region":     str,
                "risk_score": float,      # 0.0000–1.0000
                "risk_level": str,        # Low | Moderate | High | Extreme
                "change":     str,        # up | down | stable | new
                "breakdown": {
                    "current_activity":  float,
                    "historical_activity": float,
                    "forest":            float,
                    "priority":          float,
                    "escalation":        float
                }
            }
        ]
    }
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _fmt(doc: dict) -> dict:
    """Convert a MongoDB document: replace ``_id`` with ``id`` as a string."""
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


class RiskRepository:
    collection_name = "risk_history"

    def __init__(self, db) -> None:
        self.col = db[self.collection_name]

    async def create_snapshot(self, snapshot: dict) -> dict:
        """Persist a risk snapshot for today (UTC).

        Idempotent: if a snapshot already exists for the current UTC date,
        the existing document is returned unchanged.  This prevents duplicate
        snapshots when ``persist_snapshot`` is called multiple times within
        the same day (e.g. during development restarts).
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        existing = await self.col.find_one({"date": today})
        if existing:
            return _fmt(existing)
        doc = {
            **snapshot,
            "date": today,
            "created_at": datetime.now(timezone.utc),
        }
        result = await self.col.insert_one(doc)
        return _fmt({**doc, "_id": result.inserted_id})

    async def latest(self) -> dict | None:
        """Return the most recent snapshot, or ``None`` if collection is empty."""
        cursor = self.col.find().sort("created_at", -1).limit(1)
        docs = [doc async for doc in cursor]
        return _fmt(docs[0]) if docs else None

    async def history(self, days: int = 30) -> list[dict]:
        """Return all snapshots from the last *days* UTC days, newest first."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cursor = (
            self.col.find({"created_at": {"$gte": cutoff}}).sort("created_at", -1)
        )
        return [_fmt(doc) async for doc in cursor]
