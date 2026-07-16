"""MongoDB persistence for report metadata.

The ``reports`` collection stores one document per generated report::

    {
        "_id":                ObjectId,
        "type":               "daily" | "weekly" | "monthly" | "on_demand",
        "format":             "pdf" | "csv" | "json",
        "status":             "pending" | "generating" | "complete" | "failed",
        "generated_at":       datetime (UTC),
        "period_start":       datetime (UTC),
        "period_end":         datetime (UTC),
        "file_path":          str | null,
        "file_size":          int | null,
        "generation_time_ms": int | null,
        "summary":            dict | null,
        "error":              str | null,
    }
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.base import utcnow

logger = logging.getLogger("forestwatch.reports.repository")


def _shape(doc: dict) -> dict:
    """Convert a raw MongoDB document to the public representation."""
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    for field in ("generated_at", "period_start", "period_end"):
        if isinstance(doc.get(field), datetime) and doc[field].tzinfo is None:
            doc[field] = doc[field].replace(tzinfo=timezone.utc)
    return doc


class ReportRepository:
    collection_name = "reports"

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[self.collection_name]

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #

    async def create(
        self,
        *,
        report_type: str,
        report_format: str,
        period_start: datetime,
        period_end: datetime,
    ) -> dict:
        """Insert a new PENDING report record and return it."""
        doc = {
            "type": report_type,
            "format": report_format,
            "status": "pending",
            "generated_at": utcnow(),
            "period_start": period_start,
            "period_end": period_end,
            "file_path": None,
            "file_size": None,
            "generation_time_ms": None,
            "summary": None,
            "error": None,
        }
        result = await self.col.insert_one(doc)
        return _shape({**doc, "_id": result.inserted_id})

    async def update_status(self, report_id: str, status: str) -> None:
        await self.col.update_one(
            {"_id": ObjectId(report_id)},
            {"$set": {"status": status}},
        )

    async def update_complete(
        self,
        report_id: str,
        file_path: str,
        file_size: int,
        generation_time_ms: int,
        summary: dict,
    ) -> None:
        await self.col.update_one(
            {"_id": ObjectId(report_id)},
            {
                "$set": {
                    "status": "complete",
                    "file_path": file_path,
                    "file_size": file_size,
                    "generation_time_ms": generation_time_ms,
                    "summary": summary,
                    "error": None,
                }
            },
        )

    async def update_failed(self, report_id: str, error: str) -> None:
        await self.col.update_one(
            {"_id": ObjectId(report_id)},
            {"$set": {"status": "failed", "error": error}},
        )

    async def delete(self, report_id: str) -> bool:
        result = await self.col.delete_one({"_id": ObjectId(report_id)})
        return result.deleted_count > 0

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    async def get_by_id(self, report_id: str) -> dict | None:
        try:
            doc = await self.col.find_one({"_id": ObjectId(report_id)})
        except Exception:
            return None
        return _shape(doc) if doc else None

    async def list_all(self, limit: int = 100) -> list[dict]:
        cursor = self.col.find({}).sort("generated_at", -1).limit(limit)
        return [_shape(d) async for d in cursor]

    async def find_by_type_and_period_start(
        self, report_type: str, date: datetime.date
    ) -> dict | None:
        """Return the most recent report of *type* whose period_start falls on *date*."""
        day_start = datetime(date.year, date.month, date.day, tzinfo=timezone.utc)
        day_end = datetime(date.year, date.month, date.day, 23, 59, 59, tzinfo=timezone.utc)
        doc = await self.col.find_one(
            {
                "type": report_type,
                "status": {"$in": ["complete", "generating", "pending"]},
                "period_start": {"$gte": day_start, "$lte": day_end},
            },
            sort=[("generated_at", -1)],
        )
        return _shape(doc) if doc else None
