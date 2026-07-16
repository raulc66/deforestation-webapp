"""History repository — MongoDB aggregation pipelines for temporal analytics.

All methods return raw aggregation documents; shaping is done in HistoryService.
Performance notes:
  - regional_history uses a *single* aggregation with conditional sums over a 60-day
    window to avoid two round-trips.
  - All pipelines are index-friendly: they start with a $match on ``detected_at`` (indexed).
  - No client-side aggregation — every grouping/sorting happens inside MongoDB.
"""
from __future__ import annotations

from datetime import datetime, timedelta


class HistoryRepository:
    def __init__(self, db) -> None:
        self.events = db.forest_events
        self.intel_events = db.intelligence_events

    # -----------------------------------------------------------------------
    # Daily activity helpers (two small pipelines, merged in HistoryService)
    # -----------------------------------------------------------------------

    async def daily_activity_events(self, cutoff: datetime) -> list[dict]:
        """Count forest events per day since *cutoff*.

        Returns ``[{_id: 'YYYY-MM-DD', events: N}, ...]`` sorted ascending.
        """
        pipeline = [
            {"$match": {"detected_at": {"$gte": cutoff}}},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$detected_at",
                        }
                    },
                    "events": {"$sum": 1},
                }
            },
            {"$sort": {"_id": 1}},
        ]
        return [doc async for doc in self.events.aggregate(pipeline)]

    async def daily_activity_anomalies(self, cutoff: datetime) -> list[dict]:
        """Count intelligence events (anomalies) per day since *cutoff*.

        Returns ``[{_id: 'YYYY-MM-DD', anomalies: N}, ...]``.
        """
        pipeline = [
            {"$match": {"detected_at": {"$gte": cutoff}}},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$detected_at",
                        }
                    },
                    "anomalies": {"$sum": 1},
                }
            },
        ]
        return [doc async for doc in self.intel_events.aggregate(pipeline)]

    # -----------------------------------------------------------------------
    # Regional history — single aggregation, 60-day window
    # -----------------------------------------------------------------------

    async def regional_history(self, now: datetime) -> list[dict]:
        """Compute last-30d and previous-30d event counts per region in one pass.

        Splits the 60-day window with conditional sums — no N+1 lookups.
        Returns ``[{_id, events_last_30d, events_previous_30d}, ...]``
        sorted by *events_last_30d* descending.
        """
        last_30 = now - timedelta(days=30)
        prev_30 = now - timedelta(days=60)
        pipeline = [
            {"$match": {"detected_at": {"$gte": prev_30}}},
            {
                "$group": {
                    "_id": {"$ifNull": ["$region", "Unknown"]},
                    "events_last_30d": {
                        "$sum": {
                            "$cond": [{"$gte": ["$detected_at", last_30]}, 1, 0]
                        }
                    },
                    "events_previous_30d": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$gte": ["$detected_at", prev_30]},
                                        {"$lt": ["$detected_at", last_30]},
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                }
            },
            # Drop regions that had zero activity in both windows.
            {
                "$match": {
                    "$or": [
                        {"events_last_30d": {"$gt": 0}},
                        {"events_previous_30d": {"$gt": 0}},
                    ]
                }
            },
            {"$sort": {"events_last_30d": -1}},
        ]
        return [doc async for doc in self.events.aggregate(pipeline)]

    # -----------------------------------------------------------------------
    # Monthly summary helpers (two small pipelines, merged in HistoryService)
    # -----------------------------------------------------------------------

    async def monthly_events(self) -> list[dict]:
        """Group forest events by YYYY-MM with land-cover breakdown.

        Returns ``[{_id: 'YYYY-MM', events, forest_events, urban_events}, ...]``
        sorted ascending.  Uses ``$ifNull`` to treat legacy events as "unknown".
        """
        pipeline = [
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m",
                            "date": "$detected_at",
                        }
                    },
                    "events": {"$sum": 1},
                    "forest_events": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$in": [
                                        {
                                            "$ifNull": [
                                                "$land_cover_type",
                                                "unknown",
                                            ]
                                        },
                                        ["forest", "near_forest"],
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                    "urban_events": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$eq": [
                                        {
                                            "$ifNull": [
                                                "$land_cover_type",
                                                "unknown",
                                            ]
                                        },
                                        "urban",
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                }
            },
            {"$sort": {"_id": 1}},
        ]
        return [doc async for doc in self.events.aggregate(pipeline)]

    async def monthly_anomalies(self) -> list[dict]:
        """Count intelligence events per YYYY-MM.

        Returns ``[{_id: 'YYYY-MM', anomalies: N}, ...]``.
        """
        pipeline = [
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m",
                            "date": "$detected_at",
                        }
                    },
                    "anomalies": {"$sum": 1},
                }
            },
        ]
        return [doc async for doc in self.intel_events.aggregate(pipeline)]

    # -----------------------------------------------------------------------
    # Hotspot ranking helpers (two small pipelines, merged in HistoryService)
    # -----------------------------------------------------------------------

    async def hotspot_detections(self) -> list[dict]:
        """Group all-time forest events by region with per-severity counts.

        Returns ``[{_id, detections, critical, high, medium, low}, ...]``
        sorted by *detections* descending.
        """
        pipeline = [
            {
                "$group": {
                    "_id": {"$ifNull": ["$region", "Unknown"]},
                    "detections": {"$sum": 1},
                    "critical": {
                        "$sum": {
                            "$cond": [{"$eq": ["$severity", "critical"]}, 1, 0]
                        }
                    },
                    "high": {
                        "$sum": {
                            "$cond": [{"$eq": ["$severity", "high"]}, 1, 0]
                        }
                    },
                    "medium": {
                        "$sum": {
                            "$cond": [{"$eq": ["$severity", "medium"]}, 1, 0]
                        }
                    },
                    "low": {
                        "$sum": {"$cond": [{"$eq": ["$severity", "low"]}, 1, 0]}
                    },
                }
            },
            {"$sort": {"detections": -1}},
        ]
        return [doc async for doc in self.events.aggregate(pipeline)]

    async def hotspot_priorities(self) -> list[dict]:
        """Average priority_score per region from intelligence_events.

        Returns ``[{_id: region, average_priority: F}, ...]``.
        Falls back to 0.5 when priority_score is missing (legacy events).
        """
        pipeline = [
            {
                "$group": {
                    "_id": {"$ifNull": ["$region", "Unknown"]},
                    "average_priority": {
                        "$avg": {"$ifNull": ["$priority_score", 0.5]}
                    },
                }
            },
        ]
        return [doc async for doc in self.intel_events.aggregate(pipeline)]
