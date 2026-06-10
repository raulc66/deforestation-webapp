"""One-shot migrations run on startup.

Idempotent. Each function reports the number of documents it migrated so the
startup log shows zero on subsequent runs.
"""
import logging
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger("forestwatch.migrations")

# Per-collection date fields to coerce from str -> datetime
DATE_FIELDS: dict[str, tuple[str, ...]] = {
    "users": ("created_at",),
    "data_sources": ("created_at", "updated_at"),
    "forest_events": ("detected_at",),
    "notifications": ("created_at", "delivered_at", "read_at"),
}


def _parse(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def migrate_datetime_strings(db: AsyncIOMotorDatabase) -> int:
    total = 0
    for col_name, fields in DATE_FIELDS.items():
        for field in fields:
            updated = 0
            cursor = db[col_name].find({field: {"$type": "string"}}, {field: 1})
            async for doc in cursor:
                parsed = _parse(doc[field])
                if parsed is None:
                    continue
                await db[col_name].update_one(
                    {"_id": doc["_id"]},
                    {"$set": {field: parsed}},
                )
                updated += 1
            if updated:
                logger.info("Migrated %d %s.%s str->datetime", updated, col_name, field)
                total += updated
    return total


async def backfill_geojson_location(db: AsyncIOMotorDatabase) -> int:
    """Add GeoJSON `location` Point to forest_events that lack one.

    Reads `longitude` and `latitude` and writes:
        location = {"type": "Point", "coordinates": [longitude, latitude]}
    """
    cursor = db.forest_events.find(
        {"location": {"$exists": False}},
        {"latitude": 1, "longitude": 1},
    )
    updated = 0
    async for doc in cursor:
        if "latitude" not in doc or "longitude" not in doc:
            continue
        loc = {"type": "Point", "coordinates": [doc["longitude"], doc["latitude"]]}
        await db.forest_events.update_one({"_id": doc["_id"]}, {"$set": {"location": loc}})
        updated += 1
    if updated:
        logger.info("Backfilled %d forest_events with GeoJSON location", updated)
    return updated
