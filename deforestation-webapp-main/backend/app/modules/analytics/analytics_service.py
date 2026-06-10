"""Analytics service - shapes raw aggregation results into frontend-ready JSON.

No ML or predictions here; just deterministic rollups.
"""
import logging
from datetime import datetime, timedelta

from app.core.errors import AppError
from app.models.base import ensure_utc, utcnow
from app.models.enums import EVENT_TYPES

from .analytics_repository import VALID_INTERVALS, AnalyticsRepository

logger = logging.getLogger("forestwatch.analytics")

SEVERITY_ORDER = ("low", "medium", "high", "critical")


def _r(value: float | None, places: int = 2) -> float:
    return round(value, places) if value is not None else 0.0


class AnalyticsService:
    def __init__(self, repo: AnalyticsRepository):
        self.repo = repo

    # ------------------------------------------------------------------ #
    # Overview
    # ------------------------------------------------------------------ #
    async def overview(self) -> dict:
        doc = await self.repo.overview()
        if doc is None:
            return {
                "total_events": 0,
                "total_area_affected": 0.0,
                "open_events": 0,
                "resolved_events": 0,
                "investigating_events": 0,
                "average_confidence": 0.0,
            }
        return {
            "total_events": int(doc.get("total_events", 0)),
            "total_area_affected": _r(doc.get("total_area")),
            "open_events": int(doc.get("open_events", 0)),
            "resolved_events": int(doc.get("resolved_events", 0)),
            "investigating_events": int(doc.get("investigating_events", 0)),
            "average_confidence": _r(doc.get("average_confidence"), 3),
        }

    # ------------------------------------------------------------------ #
    # By country
    # ------------------------------------------------------------------ #
    async def by_country(self) -> list[dict]:
        rows = await self.repo.by_country()
        return [
            {
                "country": r["_id"],
                "event_count": int(r["event_count"]),
                "affected_area_ha": _r(r["affected_area_ha"]),
            }
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    # By event type — always returns ALL taxonomy entries (zero-filled)
    # so charts have a stable axis.
    # ------------------------------------------------------------------ #
    async def by_event_type(self) -> list[dict]:
        rows = await self.repo.by_event_type()
        by_type = {
            r["_id"]: {
                "event_count": int(r["event_count"]),
                "affected_area_ha": _r(r["affected_area_ha"]),
            }
            for r in rows
        }
        out: list[dict] = []
        for et in EVENT_TYPES:
            data = by_type.get(et, {"event_count": 0, "affected_area_ha": 0.0})
            out.append({"event_type": et, **data})
        # Sort by event_count DESC for chart readability
        out.sort(key=lambda x: (-x["event_count"], x["event_type"]))
        return out

    # ------------------------------------------------------------------ #
    # By severity — always returns the 4 buckets, zero-filled
    # ------------------------------------------------------------------ #
    async def by_severity(self) -> dict:
        rows = await self.repo.by_severity()
        by_sev = {
            r["_id"]: {
                "count": int(r["event_count"]),
                "area_ha": _r(r["affected_area_ha"]),
            }
            for r in rows
        }
        return {
            sev: by_sev.get(sev, {"count": 0, "area_ha": 0.0})
            for sev in SEVERITY_ORDER
        }

    # ------------------------------------------------------------------ #
    # Trends — time series
    # ------------------------------------------------------------------ #
    async def trends(
        self, start_date: datetime | None, end_date: datetime | None, interval: str
    ) -> dict:
        if interval not in VALID_INTERVALS:
            raise AppError(
                f"interval must be one of {sorted(VALID_INTERVALS)}",
                status_code=400,
                code="invalid_interval",
            )
        end_utc = ensure_utc(end_date) if end_date else utcnow()
        start_utc = (
            ensure_utc(start_date) if start_date else end_utc - timedelta(days=30)
        )
        if start_utc > end_utc:
            raise AppError(
                "start_date must be earlier than or equal to end_date",
                status_code=400,
                code="invalid_range",
            )
        rows = await self.repo.trends(start_utc, end_utc, interval)
        series = [
            {
                "bucket": r["_id"],
                "event_count": int(r["event_count"]),
                "affected_area_ha": _r(r["affected_area_ha"]),
            }
            for r in rows
        ]
        return {
            "interval": interval,
            "start_date": start_utc,
            "end_date": end_utc,
            "series": series,
        }
