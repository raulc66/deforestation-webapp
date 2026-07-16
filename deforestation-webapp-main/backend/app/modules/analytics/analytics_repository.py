"""Analytics repository - raw MongoDB aggregation pipelines over forest_events.

This is the only layer that touches Mongo; it returns the *raw* aggregation
documents. The service layer shapes them into frontend-ready JSON.
"""
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.geography.romania import is_romania_expression


VALID_INTERVALS = {"day", "week", "month"}


def _valid_coords_condition() -> dict:
    return {
        "$and": [
            {"$gte": [{"$ifNull": ["$latitude", 999]}, -90]},
            {"$lte": [{"$ifNull": ["$latitude", 999]}, 90]},
            {"$gte": [{"$ifNull": ["$longitude", 999]}, -180]},
            {"$lte": [{"$ifNull": ["$longitude", 999]}, 180]},
        ]
    }


def _confidence_bucket_switch() -> dict:
    return {
        "$switch": {
            "branches": [
                {
                    "case": {
                        "$in": ["$confidence", ["low", "medium", "high"]],
                    },
                    "then": "$confidence",
                },
                {
                    "case": {"$lt": [{"$ifNull": ["$confidence", -1]}, 0.5]},
                    "then": "low",
                },
                {
                    "case": {"$lt": [{"$ifNull": ["$confidence", -1]}, 0.8]},
                    "then": "medium",
                },
            ],
            "default": "high",
        }
    }


def _totals_group_stage() -> dict:
    return {
        "$group": {
            "_id": None,
            "total_events": {"$sum": 1},
            "valid_coords": {
                "$sum": {
                    "$cond": [_valid_coords_condition(), 1, 0],
                }
            },
        }
    }


def _confidence_pipeline_stages() -> list[dict]:
    return [
        {"$addFields": {"_conf_bucket": _confidence_bucket_switch()}},
        {"$group": {"_id": "$_conf_bucket", "count": {"$sum": 1}}},
    ]


class AnalyticsRepository:
    collection_name = "forest_events"
    import_jobs_collection_name = "import_jobs"

    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db[self.collection_name]
        self.import_jobs = db[self.import_jobs_collection_name]

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

    # ------------------------------------------------------------------ #
    # Data quality — event metrics + import dedupe totals
    # ------------------------------------------------------------------ #
    async def data_quality_events(self) -> dict:
        """Aggregate global + Romania-scoped quality metrics in one pass."""
        pipeline = [
            {"$addFields": {"_is_romania": is_romania_expression()}},
            {
                "$facet": {
                    "global_totals": [_totals_group_stage()],
                    "global_confidence": _confidence_pipeline_stages(),
                    "romania_totals": [
                        {"$match": {"_is_romania": True}},
                        _totals_group_stage(),
                    ],
                    "romania_confidence": [
                        {"$match": {"_is_romania": True}},
                        *_confidence_pipeline_stages(),
                    ],
                }
            },
        ]
        async for doc in self.col.aggregate(pipeline):
            return doc
        return {
            "global_totals": [],
            "global_confidence": [],
            "romania_totals": [],
            "romania_confidence": [],
        }

    # ------------------------------------------------------------------ #
    # By source — cross-provider comparison using ingestion metadata
    # ------------------------------------------------------------------ #
    async def by_source(self) -> list[dict]:
        """Group events by metadata.ingestion.source.

        Only events that carry the standardized ingestion metadata block are
        counted.  Legacy events (no metadata.ingestion) are excluded so that
        numbers reflect the new metadata layer exclusively.
        """
        pipeline = [
            # Restrict to events that have the ingestion metadata block.
            {"$match": {
                "metadata.ingestion.source": {"$exists": True, "$ne": None}
            }},
            {
                "$group": {
                    "_id": "$metadata.ingestion.source",
                    "total_events": {"$sum": 1},
                    "romania_events": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$metadata.ingestion.is_romania", True]},
                                1,
                                0,
                            ]
                        }
                    },
                    # Use ingestion.confidence as the source of truth for this
                    # source-level view; falls back to event-level field if null.
                    "average_confidence": {
                        "$avg": {
                            "$ifNull": [
                                "$metadata.ingestion.confidence",
                                "$confidence",
                            ]
                        }
                    },
                    # Severity from the canonical ForestEvent field.
                    "sev_low": {
                        "$sum": {"$cond": [{"$eq": ["$severity", "low"]}, 1, 0]}
                    },
                    "sev_medium": {
                        "$sum": {"$cond": [{"$eq": ["$severity", "medium"]}, 1, 0]}
                    },
                    "sev_high": {
                        "$sum": {"$cond": [{"$eq": ["$severity", "high"]}, 1, 0]}
                    },
                    "sev_critical": {
                        "$sum": {"$cond": [{"$eq": ["$severity", "critical"]}, 1, 0]}
                    },
                }
            },
            {"$sort": {"total_events": -1, "_id": 1}},
        ]
        return [doc async for doc in self.col.aggregate(pipeline)]

    # ------------------------------------------------------------------ #
    # Temporal Romania counts — rolling window aggregation
    # ------------------------------------------------------------------ #
    async def temporal_romania_counts(self, now: datetime) -> dict:
        """Return Romania event counts for three rolling windows.

        All windows filter on ``metadata.ingestion.is_romania == True`` so
        that only events enriched with the standardized ingestion metadata
        block are included.

        Returns a dict with keys:
            last_24h    — events in the 24 hours ending at *now*
            last_7d     — events in the 7 days ending at *now*
            previous_7d — events in the 7-day window immediately before last_7d
        """
        cutoff_24h = now - timedelta(hours=24)
        cutoff_7d = now - timedelta(days=7)
        cutoff_14d = now - timedelta(days=14)

        pipeline = [
            # Pre-filter to the widest window (14 days) to minimise scanned docs.
            {
                "$match": {
                    "metadata.ingestion.is_romania": True,
                    "detected_at": {"$gte": cutoff_14d},
                }
            },
            {
                "$facet": {
                    "last_24h": [
                        {"$match": {"detected_at": {"$gte": cutoff_24h}}},
                        {"$count": "count"},
                    ],
                    "last_7d": [
                        {"$match": {"detected_at": {"$gte": cutoff_7d}}},
                        {"$count": "count"},
                    ],
                    "previous_7d": [
                        {
                            "$match": {
                                "detected_at": {
                                    "$gte": cutoff_14d,
                                    "$lt": cutoff_7d,
                                }
                            }
                        },
                        {"$count": "count"},
                    ],
                }
            },
        ]

        async for doc in self.col.aggregate(pipeline):
            return {
                "last_24h": doc["last_24h"][0]["count"] if doc["last_24h"] else 0,
                "last_7d": doc["last_7d"][0]["count"] if doc["last_7d"] else 0,
                "previous_7d": doc["previous_7d"][0]["count"] if doc["previous_7d"] else 0,
            }
        return {"last_24h": 0, "last_7d": 0, "previous_7d": 0}

    # ------------------------------------------------------------------ #
    # Regional baselines — per-region current vs. historical averages
    # ------------------------------------------------------------------ #
    async def regional_baselines(self, now: datetime) -> list[dict]:
        """Aggregate per-region Romania event counts for two time windows.

        Returns one document per distinct ``region`` value, each containing:

            current_events  — count in the 7 days ending at *now*
            baseline_raw    — count in the 28 days immediately before that
                              window (weeks -1 through -4)
            lc_*            — land-cover counts across both windows, used by the
                              service layer to compute per-region forest_confidence.

        Dividing ``baseline_raw`` by 4 in the service layer yields the average
        weekly baseline.

        Only events with ``metadata.ingestion.is_romania == True`` are counted.
        The ``now - 35d`` pre-filter limits scanned documents to the relevant
        5-week horizon.
        """
        cutoff_7d = now - timedelta(days=7)
        cutoff_35d = now - timedelta(days=35)

        # Helper: conditional sum for a land-cover type.
        # Uses $ifNull to treat null land_cover_type as "unknown" so legacy
        # events (without the field) contribute to the unknown bucket.
        def _lc_sum(label: str) -> dict:
            return {
                "$sum": {
                    "$cond": [
                        {
                            "$eq": [
                                {"$ifNull": ["$land_cover_type", "unknown"]},
                                label,
                            ]
                        },
                        1,
                        0,
                    ]
                }
            }

        pipeline = [
            {
                "$match": {
                    "metadata.ingestion.is_romania": True,
                    "detected_at": {"$gte": cutoff_35d},
                }
            },
            {
                "$group": {
                    "_id": "$region",
                    "current_events": {
                        "$sum": {
                            "$cond": [{"$gte": ["$detected_at", cutoff_7d]}, 1, 0]
                        }
                    },
                    "baseline_raw": {
                        "$sum": {
                            "$cond": [{"$lt": ["$detected_at", cutoff_7d]}, 1, 0]
                        }
                    },
                    # Land-cover distribution (all events in the 35-day window)
                    "lc_forest":       _lc_sum("forest"),
                    "lc_near_forest":  _lc_sum("near_forest"),
                    "lc_agriculture":  _lc_sum("agriculture"),
                    "lc_urban":        _lc_sum("urban"),
                    "lc_water":        _lc_sum("water"),
                    "lc_unknown":      _lc_sum("unknown"),
                }
            },
            {"$sort": {"_id": 1}},
        ]
        return [doc async for doc in self.col.aggregate(pipeline)]

    # ------------------------------------------------------------------ #
    # Land-cover distribution — global per-type event counts
    # ------------------------------------------------------------------ #
    async def land_cover_distribution(self) -> list[dict]:
        """Count all events grouped by ``land_cover_type``.

        Returns a list of ``{"_id": "<type>", "events": N}`` documents sorted
        by event count descending.  Null / missing ``land_cover_type`` values
        are counted under ``"unknown"``.
        """
        pipeline = [
            {
                "$group": {
                    "_id": {"$ifNull": ["$land_cover_type", "unknown"]},
                    "events": {"$sum": 1},
                }
            },
            {"$sort": {"events": -1, "_id": 1}},
        ]
        return [doc async for doc in self.col.aggregate(pipeline)]

    async def data_quality_import_totals(self) -> dict | None:
        """Sum ingestion attempts and skipped rows across all ImportJobs."""
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_attempts": {
                        "$sum": {
                            "$add": [
                                {"$ifNull": ["$success_count", 0]},
                                {"$ifNull": ["$skipped_count", 0]},
                                {"$ifNull": ["$error_count", 0]},
                            ]
                        }
                    },
                    "skipped_count": {"$sum": {"$ifNull": ["$skipped_count", 0]}},
                }
            }
        ]
        async for doc in self.import_jobs.aggregate(pipeline):
            return doc
        return None
