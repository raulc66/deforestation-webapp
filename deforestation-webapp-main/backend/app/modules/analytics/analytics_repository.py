"""Analytics repository - raw MongoDB aggregation pipelines over forest_events.

This is the only layer that touches Mongo; it returns the *raw* aggregation
documents. The service layer shapes them into frontend-ready JSON.
"""
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase


VALID_INTERVALS = {"day", "week", "month"}


class AnalyticsRepository:
    collection_name = "forest_events"

    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db[self.collection_name]

    # ------------------------------------------------------------------ #
    # Overview - totals & averages
    # ------------------------------------------------------------------ #
    async def overview(self) -> dict | None:
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_events": {"$sum": 1},
                    "total_area": {"$sum": "$affected_area_ha"},
                    "open_events": {
                        "$sum": {"$cond": [{"$eq": ["$status", "open"]}, 1, 0]}
                    },
                    "resolved_events": {
                        "$sum": {"$cond": [{"$eq": ["$status", "resolved"]}, 1, 0]}
                    },
                    "investigating_events": {
                        "$sum": {"$cond": [{"$eq": ["$status", "investigating"]}, 1, 0]}
                    },
                    "average_confidence": {"$avg": "$confidence"},
                }
            }
        ]
        async for doc in self.col.aggregate(pipeline):
            return doc
        return None

    # ------------------------------------------------------------------ #
    # By country
    # ------------------------------------------------------------------ #
    async def by_country(self) -> list[dict]:
        pipeline = [
            {
                "$group": {
                    "_id": "$country",
                    "event_count": {"$sum": 1},
                    "affected_area_ha": {"$sum": "$affected_area_ha"},
                }
            },
            {"$sort": {"event_count": -1, "_id": 1}},
        ]
        return [doc async for doc in self.col.aggregate(pipeline)]

    # ------------------------------------------------------------------ #
    # By event type
    # ------------------------------------------------------------------ #
    async def by_event_type(self) -> list[dict]:
        pipeline = [
            {
                "$group": {
                    "_id": "$event_type",
                    "event_count": {"$sum": 1},
                    "affected_area_ha": {"$sum": "$affected_area_ha"},
                }
            },
            {"$sort": {"event_count": -1, "_id": 1}},
        ]
        return [doc async for doc in self.col.aggregate(pipeline)]

    # ------------------------------------------------------------------ #
    # By severity
    # ------------------------------------------------------------------ #
    async def by_severity(self) -> list[dict]:
        pipeline = [
            {
                "$group": {
                    "_id": "$severity",
                    "event_count": {"$sum": 1},
                    "affected_area_ha": {"$sum": "$affected_area_ha"},
                }
            }
        ]
        return [doc async for doc in self.col.aggregate(pipeline)]

    # ------------------------------------------------------------------ #
    # Trends - time-series with $dateTrunc (MongoDB 5.0+, we run 7)
    # ------------------------------------------------------------------ #
    async def trends(
        self, start: datetime, end: datetime, interval: str
    ) -> list[dict]:
        pipeline = [
            {"$match": {"detected_at": {"$gte": start, "$lte": end}}},
            {
                "$group": {
                    "_id": {
                        "$dateTrunc": {
                            "date": "$detected_at",
                            "unit": interval,
                            "timezone": "UTC",
                        }
                    },
                    "event_count": {"$sum": 1},
                    "affected_area_ha": {"$sum": "$affected_area_ha"},
                }
            },
            {"$sort": {"_id": 1}},
        ]
        return [doc async for doc in self.col.aggregate(pipeline)]
