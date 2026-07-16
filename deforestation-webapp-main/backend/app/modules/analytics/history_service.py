"""History service — pure helpers + MongoDB-to-frontend translation.

Pure functions (no I/O, easily testable in isolation):
    compute_change_percent(current, previous) → float
    compute_trend(change_percent)             → "increasing" | "stable" | "decreasing"
    rank_hotspots(rows)                       → sorted list (by detections desc)
    _highest_severity(row)                    → "critical" | "high" | "medium" | "low"

HistoryService wraps HistoryRepository and shapes responses for the four
history endpoints.  It uses asyncio.gather to run paired sub-queries in
parallel, avoiding sequential round-trips.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from app.models.base import utcnow

from .history_repository import HistoryRepository

logger = logging.getLogger("forestwatch.history")

# ---------------------------------------------------------------------------
# Pure helpers — independent of MongoDB (testable without any mocks)
# ---------------------------------------------------------------------------


def compute_change_percent(current: float, previous: float) -> float:
    """Return the percent change from *previous* to *current*, 1 d.p.

    Edge cases:
        previous == 0 and current > 0 → +100.0  (new activity appeared)
        previous == 0 and current == 0 →   0.0  (both zero, no change)
        previous  > 0 and current == 0 → -100.0 (all activity disappeared)
    """
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round((current - previous) / previous * 100, 1)


def compute_trend(change_percent: float) -> str:
    """Classify *change_percent* into one of three trend labels.

    Rules:
        > +10 % → "increasing"
        < -10 % → "decreasing"
        else    → "stable"
    """
    if change_percent > 10:
        return "increasing"
    if change_percent < -10:
        return "decreasing"
    return "stable"


def rank_hotspots(rows: list[dict]) -> list[dict]:
    """Return *rows* sorted by ``detections`` descending.  Pure — no mutation."""
    return sorted(rows, key=lambda h: h.get("detections", 0), reverse=True)


def _highest_severity(row: dict) -> str:
    """Return the highest severity label present in a hotspot aggregation row."""
    for level in ("critical", "high", "medium", "low"):
        if row.get(level, 0) > 0:
            return level
    return "low"


# ---------------------------------------------------------------------------
# HistoryService
# ---------------------------------------------------------------------------


class HistoryService:
    def __init__(self, repo: HistoryRepository) -> None:
        self._repo = repo

    # --- Daily activity -------------------------------------------------------

    async def daily_activity(self, days: int) -> dict:
        """Return per-day event + anomaly counts for the last *days* days.

        Zero-fills dates that have no events so the frontend gets a complete
        contiguous series without needing client-side gap logic.
        """
        now = utcnow()
        cutoff = now - timedelta(days=days)

        events_rows, anomaly_rows = await asyncio.gather(
            self._repo.daily_activity_events(cutoff),
            self._repo.daily_activity_anomalies(cutoff),
        )

        events_by_day: dict[str, int] = {
            r["_id"]: int(r.get("events", 0)) for r in events_rows
        }
        anomalies_by_day: dict[str, int] = {
            r["_id"]: int(r.get("anomalies", 0)) for r in anomaly_rows
        }

        days_list = []
        for offset in range(days):
            date_str = (cutoff + timedelta(days=offset + 1)).strftime("%Y-%m-%d")
            days_list.append(
                {
                    "date": date_str,
                    "events": events_by_day.get(date_str, 0),
                    "anomalies": anomalies_by_day.get(date_str, 0),
                }
            )

        return {"generated_at": now, "days": days_list}

    # --- Regional history -----------------------------------------------------

    async def regional_history(self) -> list[dict]:
        """Return per-region comparison of last-30d vs previous-30d activity.

        Adds *change_percent* and *trend* derived from the pure helpers above.
        """
        now = utcnow()
        rows = await self._repo.regional_history(now)

        result = []
        for row in rows:
            last = int(row.get("events_last_30d", 0))
            prev = int(row.get("events_previous_30d", 0))
            change = compute_change_percent(last, prev)
            result.append(
                {
                    "region": str(row["_id"]) if row.get("_id") else "Unknown",
                    "events_last_30d": last,
                    "events_previous_30d": prev,
                    "change_percent": change,
                    "trend": compute_trend(change),
                }
            )
        return result

    # --- Hotspot ranking ------------------------------------------------------

    async def hotspot_history(self) -> list[dict]:
        """Return regions ranked by all-time detection count.

        Merges per-region priority scores from intelligence_events using a
        lookup dict — single pass, no N+1 queries.
        """
        detections_rows, priority_rows = await asyncio.gather(
            self._repo.hotspot_detections(),
            self._repo.hotspot_priorities(),
        )

        priority_by_region: dict[str, float] = {
            str(r["_id"]): round(float(r.get("average_priority", 0.5)), 3)
            for r in priority_rows
            if r.get("_id")
        }

        hotspots = [
            {
                "region": str(row["_id"]) if row.get("_id") else "Unknown",
                "detections": int(row.get("detections", 0)),
                "average_priority": priority_by_region.get(
                    str(row["_id"]) if row.get("_id") else "Unknown",
                    0.5,
                ),
                "highest_severity": _highest_severity(row),
            }
            for row in detections_rows
        ]

        return rank_hotspots(hotspots)

    # --- Monthly summary ------------------------------------------------------

    async def monthly_summary(self) -> dict:
        """Return per-month totals: events, anomalies, forest/urban breakdown.

        Merges forest_events rows with intelligence_events anomaly counts
        using a lookup dict — no N+1 queries.
        """
        events_rows, anomaly_rows = await asyncio.gather(
            self._repo.monthly_events(),
            self._repo.monthly_anomalies(),
        )

        anomalies_by_month: dict[str, int] = {
            str(r["_id"]): int(r.get("anomalies", 0))
            for r in anomaly_rows
            if r.get("_id")
        }

        months = [
            {
                "month": str(row["_id"]) if row.get("_id") else "unknown",
                "events": int(row.get("events", 0)),
                "anomalies": anomalies_by_month.get(
                    str(row["_id"]) if row.get("_id") else "unknown", 0
                ),
                "forest_events": int(row.get("forest_events", 0)),
                "urban_events": int(row.get("urban_events", 0)),
            }
            for row in events_rows
        ]

        return {"months": months}
