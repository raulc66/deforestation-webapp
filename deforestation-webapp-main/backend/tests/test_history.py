"""Tests for Historical Intelligence — history_repository.py + history_service.py.

Coverage:
    Pure helpers:
        compute_change_percent — normal, zero previous, both zero, negative
        compute_trend          — boundary values (10%, -10%), over/under
        rank_hotspots          — correct ordering
        _highest_severity      — all levels + empty row

    HistoryRepository (aggregation pipeline structure via AsyncMock):
        daily_activity_events  — returns correct docs
        daily_activity_anomalies
        regional_history       — single aggregation call
        monthly_events
        monthly_anomalies
        hotspot_detections
        hotspot_priorities

    HistoryService (shaping + merging):
        daily_activity         — zero-fills missing dates, correct length
        regional_history       — change_percent and trend derived
        hotspot_history        — merged priority, sorted correctly
        monthly_summary        — anomaly merge, field presence

    API endpoints (structure smoke tests via HistoryService mock):
        GET /intelligence/history/daily
        GET /intelligence/history/regions
        GET /intelligence/history/hotspots
        GET /intelligence/history/monthly
"""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.analytics.history_service import (
    HistoryService,
    _highest_severity,
    compute_change_percent,
    compute_trend,
    rank_hotspots,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def _async_iter(items):
    """Return an object whose __aiter__ yields items — simulates Motor cursor."""
    class _Cursor:
        def __aiter__(self):
            return self._gen()
        async def _gen(self):
            for item in items:
                yield item
    return _Cursor()


def _make_repo(
    events_rows=None,
    anomaly_rows=None,
    region_rows=None,
    monthly_event_rows=None,
    monthly_anomaly_rows=None,
    hotspot_det_rows=None,
    hotspot_prio_rows=None,
):
    """Return a HistoryRepository-shaped mock with configurable return values."""
    repo = MagicMock()
    repo.daily_activity_events = AsyncMock(return_value=events_rows or [])
    repo.daily_activity_anomalies = AsyncMock(return_value=anomaly_rows or [])
    repo.regional_history = AsyncMock(return_value=region_rows or [])
    repo.monthly_events = AsyncMock(return_value=monthly_event_rows or [])
    repo.monthly_anomalies = AsyncMock(return_value=monthly_anomaly_rows or [])
    repo.hotspot_detections = AsyncMock(return_value=hotspot_det_rows or [])
    repo.hotspot_priorities = AsyncMock(return_value=hotspot_prio_rows or [])
    return repo


# ===========================================================================
# Pure helpers
# ===========================================================================


class TestComputeChangePercent:
    def test_positive_change(self):
        assert compute_change_percent(54, 38) == pytest.approx(42.1, abs=0.05)

    def test_negative_change(self):
        assert compute_change_percent(20, 40) == -50.0

    def test_no_change(self):
        assert compute_change_percent(10, 10) == 0.0

    def test_zero_previous_positive_current(self):
        # New activity appeared — treat as +100 %
        assert compute_change_percent(5, 0) == 100.0

    def test_zero_previous_zero_current(self):
        assert compute_change_percent(0, 0) == 0.0

    def test_positive_previous_zero_current(self):
        assert compute_change_percent(0, 100) == -100.0

    def test_rounds_to_one_decimal(self):
        # 1/3 = 33.333… → rounded to 33.3
        result = compute_change_percent(4, 3)
        assert result == pytest.approx(33.3, abs=0.05)

    def test_large_increase(self):
        assert compute_change_percent(1000, 100) == 900.0


class TestComputeTrend:
    def test_above_ten_percent_is_increasing(self):
        assert compute_trend(10.1) == "increasing"

    def test_exactly_ten_percent_is_stable(self):
        assert compute_trend(10.0) == "stable"

    def test_below_minus_ten_is_decreasing(self):
        assert compute_trend(-10.1) == "decreasing"

    def test_exactly_minus_ten_is_stable(self):
        assert compute_trend(-10.0) == "stable"

    def test_zero_is_stable(self):
        assert compute_trend(0.0) == "stable"

    def test_high_positive_is_increasing(self):
        assert compute_trend(100.0) == "increasing"

    def test_high_negative_is_decreasing(self):
        assert compute_trend(-100.0) == "decreasing"

    def test_small_positive_is_stable(self):
        assert compute_trend(5.0) == "stable"

    def test_small_negative_is_stable(self):
        assert compute_trend(-5.0) == "stable"


class TestRankHotspots:
    def test_sorted_descending_by_detections(self):
        rows = [
            {"region": "A", "detections": 10},
            {"region": "B", "detections": 50},
            {"region": "C", "detections": 30},
        ]
        result = rank_hotspots(rows)
        assert [r["region"] for r in result] == ["B", "C", "A"]

    def test_already_sorted_unchanged(self):
        rows = [
            {"region": "X", "detections": 100},
            {"region": "Y", "detections": 50},
        ]
        result = rank_hotspots(rows)
        assert result[0]["region"] == "X"

    def test_empty_list(self):
        assert rank_hotspots([]) == []

    def test_does_not_mutate_input(self):
        rows = [{"region": "A", "detections": 1}, {"region": "B", "detections": 2}]
        original = list(rows)
        rank_hotspots(rows)
        assert rows == original


class TestHighestSeverity:
    def test_critical_wins(self):
        row = {"critical": 1, "high": 2, "medium": 3, "low": 4}
        assert _highest_severity(row) == "critical"

    def test_high_when_no_critical(self):
        row = {"critical": 0, "high": 5, "medium": 1, "low": 0}
        assert _highest_severity(row) == "high"

    def test_medium_when_no_critical_or_high(self):
        row = {"critical": 0, "high": 0, "medium": 2, "low": 1}
        assert _highest_severity(row) == "medium"

    def test_low_when_only_low(self):
        row = {"critical": 0, "high": 0, "medium": 0, "low": 3}
        assert _highest_severity(row) == "low"

    def test_empty_row_returns_low(self):
        assert _highest_severity({}) == "low"


# ===========================================================================
# HistoryRepository — aggregation pipeline smoke tests
# ===========================================================================


class TestHistoryRepositoryMocked:
    """Test that repository methods call the correct aggregation pipelines
    and return the cursor output. We mock the Motor collection to avoid
    a real MongoDB connection."""

    def _make_collection(self, docs):
        """Return a mock collection whose .aggregate() yields *docs*."""
        col = MagicMock()
        col.aggregate = MagicMock(return_value=_async_iter(docs))
        return col

    def _make_db(self, event_docs=None, intel_docs=None):
        db = SimpleNamespace(
            forest_events=self._make_collection(event_docs or []),
            intelligence_events=self._make_collection(intel_docs or []),
        )
        return db

    @pytest.mark.anyio
    async def test_daily_activity_events_returns_docs(self):
        from app.modules.analytics.history_repository import HistoryRepository
        docs = [{"_id": "2026-06-01", "events": 5}]
        repo = HistoryRepository(self._make_db(event_docs=docs))
        result = await repo.daily_activity_events(utc(2026, 5, 1))
        assert result == docs

    @pytest.mark.anyio
    async def test_daily_activity_anomalies_returns_docs(self):
        from app.modules.analytics.history_repository import HistoryRepository
        docs = [{"_id": "2026-06-01", "anomalies": 2}]
        repo = HistoryRepository(self._make_db(intel_docs=docs))
        result = await repo.daily_activity_anomalies(utc(2026, 5, 1))
        assert result == docs

    @pytest.mark.anyio
    async def test_regional_history_returns_docs(self):
        from app.modules.analytics.history_repository import HistoryRepository
        docs = [{"_id": "Suceava", "events_last_30d": 54, "events_previous_30d": 38}]
        repo = HistoryRepository(self._make_db(event_docs=docs))
        result = await repo.regional_history(utc(2026, 6, 1))
        assert result == docs

    @pytest.mark.anyio
    async def test_monthly_events_returns_docs(self):
        from app.modules.analytics.history_repository import HistoryRepository
        docs = [{"_id": "2026-05", "events": 88, "forest_events": 52, "urban_events": 7}]
        repo = HistoryRepository(self._make_db(event_docs=docs))
        result = await repo.monthly_events()
        assert result == docs

    @pytest.mark.anyio
    async def test_monthly_anomalies_returns_docs(self):
        from app.modules.analytics.history_repository import HistoryRepository
        docs = [{"_id": "2026-05", "anomalies": 3}]
        repo = HistoryRepository(self._make_db(intel_docs=docs))
        result = await repo.monthly_anomalies()
        assert result == docs

    @pytest.mark.anyio
    async def test_hotspot_detections_returns_docs(self):
        from app.modules.analytics.history_repository import HistoryRepository
        docs = [{"_id": "Bacău", "detections": 125, "critical": 3, "high": 10, "medium": 5, "low": 2}]
        repo = HistoryRepository(self._make_db(event_docs=docs))
        result = await repo.hotspot_detections()
        assert result == docs

    @pytest.mark.anyio
    async def test_hotspot_priorities_returns_docs(self):
        from app.modules.analytics.history_repository import HistoryRepository
        docs = [{"_id": "Bacău", "average_priority": 0.83}]
        repo = HistoryRepository(self._make_db(intel_docs=docs))
        result = await repo.hotspot_priorities()
        assert result == docs

    @pytest.mark.anyio
    async def test_empty_collections_return_empty_lists(self):
        from app.modules.analytics.history_repository import HistoryRepository
        repo = HistoryRepository(self._make_db())
        assert await repo.daily_activity_events(utc(2026, 1, 1)) == []
        assert await repo.monthly_events() == []
        assert await repo.hotspot_detections() == []


# ===========================================================================
# HistoryService — shaping logic
# ===========================================================================


class TestHistoryServiceDailyActivity:
    @pytest.mark.anyio
    async def test_zero_fills_missing_dates(self):
        """When some days have no events, they appear as zeros in the result."""
        repo = _make_repo(
            events_rows=[{"_id": "2026-06-03", "events": 5}],
            anomaly_rows=[],
        )
        svc = HistoryService(repo)
        # Use 3-day window; cutoff = now - 3d.  We patch utcnow so the
        # logic is deterministic.
        with patch(
            "app.modules.analytics.history_service.utcnow",
            return_value=utc(2026, 6, 4),
        ):
            result = await svc.daily_activity(3)

        assert result["generated_at"] == utc(2026, 6, 4)
        days = result["days"]
        assert len(days) == 3
        dates = [d["date"] for d in days]
        assert "2026-06-02" in dates
        assert "2026-06-03" in dates
        assert "2026-06-04" in dates

        june_3 = next(d for d in days if d["date"] == "2026-06-03")
        assert june_3["events"] == 5
        assert june_3["anomalies"] == 0

        june_2 = next(d for d in days if d["date"] == "2026-06-02")
        assert june_2["events"] == 0

    @pytest.mark.anyio
    async def test_returns_correct_length_for_requested_days(self):
        repo = _make_repo()
        svc = HistoryService(repo)
        with patch(
            "app.modules.analytics.history_service.utcnow",
            return_value=utc(2026, 6, 30),
        ):
            result = await svc.daily_activity(7)
        assert len(result["days"]) == 7

    @pytest.mark.anyio
    async def test_anomaly_counts_merged_correctly(self):
        repo = _make_repo(
            events_rows=[{"_id": "2026-06-10", "events": 8}],
            anomaly_rows=[{"_id": "2026-06-10", "anomalies": 2}],
        )
        svc = HistoryService(repo)
        with patch(
            "app.modules.analytics.history_service.utcnow",
            return_value=utc(2026, 6, 11),
        ):
            result = await svc.daily_activity(2)
        june_10 = next(d for d in result["days"] if d["date"] == "2026-06-10")
        assert june_10["events"] == 8
        assert june_10["anomalies"] == 2

    @pytest.mark.anyio
    async def test_empty_repo_returns_zero_filled_series(self):
        repo = _make_repo()
        svc = HistoryService(repo)
        with patch(
            "app.modules.analytics.history_service.utcnow",
            return_value=utc(2026, 6, 5),
        ):
            result = await svc.daily_activity(5)
        assert all(d["events"] == 0 and d["anomalies"] == 0 for d in result["days"])


class TestHistoryServiceRegionalHistory:
    @pytest.mark.anyio
    async def test_change_percent_and_trend_included(self):
        repo = _make_repo(
            region_rows=[
                {"_id": "Suceava", "events_last_30d": 54, "events_previous_30d": 38},
            ]
        )
        svc = HistoryService(repo)
        result = await svc.regional_history()
        assert len(result) == 1
        row = result[0]
        assert row["region"] == "Suceava"
        assert row["events_last_30d"] == 54
        assert row["events_previous_30d"] == 38
        assert row["change_percent"] == pytest.approx(42.1, abs=0.05)
        assert row["trend"] == "increasing"

    @pytest.mark.anyio
    async def test_decreasing_trend(self):
        repo = _make_repo(
            region_rows=[{"_id": "Cluj", "events_last_30d": 10, "events_previous_30d": 50}]
        )
        svc = HistoryService(repo)
        result = await svc.regional_history()
        assert result[0]["trend"] == "decreasing"

    @pytest.mark.anyio
    async def test_stable_trend(self):
        # 10/10 = 0% change → stable
        repo = _make_repo(
            region_rows=[{"_id": "Iași", "events_last_30d": 10, "events_previous_30d": 10}]
        )
        svc = HistoryService(repo)
        result = await svc.regional_history()
        assert result[0]["trend"] == "stable"

    @pytest.mark.anyio
    async def test_zero_previous_events_is_handled(self):
        repo = _make_repo(
            region_rows=[{"_id": "Harghita", "events_last_30d": 5, "events_previous_30d": 0}]
        )
        svc = HistoryService(repo)
        result = await svc.regional_history()
        assert result[0]["change_percent"] == 100.0
        assert result[0]["trend"] == "increasing"

    @pytest.mark.anyio
    async def test_null_id_becomes_unknown(self):
        repo = _make_repo(
            region_rows=[{"_id": None, "events_last_30d": 1, "events_previous_30d": 0}]
        )
        svc = HistoryService(repo)
        result = await svc.regional_history()
        assert result[0]["region"] == "Unknown"

    @pytest.mark.anyio
    async def test_empty_returns_empty_list(self):
        svc = HistoryService(_make_repo())
        result = await svc.regional_history()
        assert result == []


class TestHistoryServiceHotspotHistory:
    @pytest.mark.anyio
    async def test_priority_merged_from_intel_events(self):
        repo = _make_repo(
            hotspot_det_rows=[
                {"_id": "Bacău", "detections": 125, "critical": 3, "high": 10, "medium": 5, "low": 2},
            ],
            hotspot_prio_rows=[
                {"_id": "Bacău", "average_priority": 0.83},
            ],
        )
        svc = HistoryService(repo)
        result = await svc.hotspot_history()
        assert result[0]["region"] == "Bacău"
        assert result[0]["detections"] == 125
        assert result[0]["average_priority"] == pytest.approx(0.83, abs=0.001)
        assert result[0]["highest_severity"] == "critical"

    @pytest.mark.anyio
    async def test_missing_priority_defaults_to_half(self):
        repo = _make_repo(
            hotspot_det_rows=[
                {"_id": "Covasna", "detections": 30, "critical": 0, "high": 2, "medium": 1, "low": 0},
            ],
        )
        svc = HistoryService(repo)
        result = await svc.hotspot_history()
        assert result[0]["average_priority"] == 0.5

    @pytest.mark.anyio
    async def test_sorted_by_detections_descending(self):
        repo = _make_repo(
            hotspot_det_rows=[
                {"_id": "A", "detections": 10, "critical": 0, "high": 1, "medium": 0, "low": 0},
                {"_id": "B", "detections": 50, "critical": 1, "high": 0, "medium": 0, "low": 0},
                {"_id": "C", "detections": 30, "critical": 0, "high": 0, "medium": 1, "low": 0},
            ],
        )
        svc = HistoryService(repo)
        result = await svc.hotspot_history()
        assert [r["region"] for r in result] == ["B", "C", "A"]

    @pytest.mark.anyio
    async def test_empty_returns_empty_list(self):
        svc = HistoryService(_make_repo())
        result = await svc.hotspot_history()
        assert result == []


class TestHistoryServiceMonthlySummary:
    @pytest.mark.anyio
    async def test_anomalies_merged_by_month(self):
        repo = _make_repo(
            monthly_event_rows=[
                {"_id": "2026-05", "events": 88, "forest_events": 52, "urban_events": 7},
                {"_id": "2026-06", "events": 50, "forest_events": 30, "urban_events": 3},
            ],
            monthly_anomaly_rows=[
                {"_id": "2026-05", "anomalies": 3},
            ],
        )
        svc = HistoryService(repo)
        result = await svc.monthly_summary()

        months = result["months"]
        assert len(months) == 2

        may = next(m for m in months if m["month"] == "2026-05")
        assert may["events"] == 88
        assert may["anomalies"] == 3
        assert may["forest_events"] == 52
        assert may["urban_events"] == 7

        june = next(m for m in months if m["month"] == "2026-06")
        assert june["anomalies"] == 0

    @pytest.mark.anyio
    async def test_all_required_fields_present(self):
        repo = _make_repo(
            monthly_event_rows=[
                {"_id": "2026-01", "events": 10, "forest_events": 5, "urban_events": 1},
            ],
        )
        svc = HistoryService(repo)
        result = await svc.monthly_summary()
        month = result["months"][0]
        assert set(month.keys()) == {"month", "events", "anomalies", "forest_events", "urban_events"}

    @pytest.mark.anyio
    async def test_empty_returns_empty_months_list(self):
        svc = HistoryService(_make_repo())
        result = await svc.monthly_summary()
        assert result == {"months": []}


# ===========================================================================
# API endpoint smoke tests (via dependency override pattern)
# ===========================================================================


class TestHistoryEndpoints:
    """Verify that the four history endpoints return the expected top-level keys."""

    def _make_app(self):
        """Build a minimal FastAPI test client with the history service overridden."""
        from fastapi.testclient import TestClient
        from app.modules.analytics.analytics_routes import router
        from app.api.deps import get_current_user, history_service_dep
        from app.models.user import UserPublic
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/api")

        from datetime import timezone
        mock_user = UserPublic(
            id="u1",
            email="test@example.com",
            name="Test User",
            role="admin",
            provider="local",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        app.dependency_overrides[get_current_user] = lambda: mock_user

        daily_result = {
            "generated_at": utc(2026, 6, 4).isoformat(),
            "days": [{"date": "2026-06-04", "events": 5, "anomalies": 1}],
        }
        regions_result = [
            {
                "region": "Suceava",
                "events_last_30d": 54,
                "events_previous_30d": 38,
                "change_percent": 42.1,
                "trend": "increasing",
            }
        ]
        hotspots_result = [
            {
                "region": "Bacău",
                "detections": 125,
                "average_priority": 0.83,
                "highest_severity": "critical",
            }
        ]
        monthly_result = {
            "months": [
                {
                    "month": "2026-05",
                    "events": 88,
                    "anomalies": 3,
                    "forest_events": 52,
                    "urban_events": 7,
                }
            ]
        }

        mock_svc = MagicMock(spec=HistoryService)
        mock_svc.daily_activity = AsyncMock(return_value=daily_result)
        mock_svc.regional_history = AsyncMock(return_value=regions_result)
        mock_svc.hotspot_history = AsyncMock(return_value=hotspots_result)
        mock_svc.monthly_summary = AsyncMock(return_value=monthly_result)
        app.dependency_overrides[history_service_dep] = lambda: mock_svc

        return TestClient(app)

    def test_daily_returns_correct_shape(self):
        client = self._make_app()
        resp = client.get("/api/analytics/intelligence/history/daily?days=7")
        assert resp.status_code == 200
        body = resp.json()
        assert "generated_at" in body
        assert "days" in body
        assert isinstance(body["days"], list)
        assert body["days"][0]["date"] == "2026-06-04"

    def test_daily_accepts_days_param(self):
        client = self._make_app()
        resp = client.get("/api/analytics/intelligence/history/daily?days=90")
        assert resp.status_code == 200

    def test_daily_rejects_days_above_365(self):
        client = self._make_app()
        resp = client.get("/api/analytics/intelligence/history/daily?days=366")
        assert resp.status_code == 422

    def test_regions_returns_list(self):
        client = self._make_app()
        resp = client.get("/api/analytics/intelligence/history/regions")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert body[0]["region"] == "Suceava"
        assert "trend" in body[0]
        assert "change_percent" in body[0]

    def test_hotspots_returns_list(self):
        client = self._make_app()
        resp = client.get("/api/analytics/intelligence/history/hotspots")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert body[0]["region"] == "Bacău"
        assert "detections" in body[0]
        assert "average_priority" in body[0]
        assert "highest_severity" in body[0]

    def test_monthly_returns_months_key(self):
        client = self._make_app()
        resp = client.get("/api/analytics/intelligence/history/monthly")
        assert resp.status_code == 200
        body = resp.json()
        assert "months" in body
        month = body["months"][0]
        assert set(month.keys()) == {"month", "events", "anomalies", "forest_events", "urban_events"}

    def test_all_four_endpoints_are_registered(self):
        """Verify all four history routes are registered on the analytics router."""
        from app.modules.analytics.analytics_routes import router

        history_paths = {
            "/analytics/intelligence/history/daily",
            "/analytics/intelligence/history/regions",
            "/analytics/intelligence/history/hotspots",
            "/analytics/intelligence/history/monthly",
        }
        registered = {
            getattr(route, "path", None)
            for route in router.routes
        }
        for path in history_paths:
            assert path in registered, f"Route not registered: {path}"


# ===========================================================================
# Edge cases & percent-change boundary conditions
# ===========================================================================


class TestPercentChangeBoundaries:
    def test_100_percent_increase_from_zero(self):
        # Edge: no previous data, new activity appears
        assert compute_change_percent(1, 0) == 100.0

    def test_exactly_10_percent_is_stable(self):
        # +10.0 % must NOT trigger "increasing" (> 10, not >=)
        # 110/100 - 1 = 0.10 exactly
        cp = compute_change_percent(110, 100)
        assert cp == 10.0
        assert compute_trend(cp) == "stable"

    def test_exactly_minus_10_percent_is_stable(self):
        cp = compute_change_percent(90, 100)
        assert cp == -10.0
        assert compute_trend(cp) == "stable"

    def test_fractional_just_above_10_is_increasing(self):
        # 111 / 100 - 1 = 0.11 → 11.0 %
        cp = compute_change_percent(111, 100)
        assert cp == 11.0
        assert compute_trend(cp) == "increasing"

    def test_negative_just_below_minus_10_is_decreasing(self):
        # 89 / 100 - 1 = -0.11 → -11.0 %
        cp = compute_change_percent(89, 100)
        assert cp == -11.0
        assert compute_trend(cp) == "decreasing"
