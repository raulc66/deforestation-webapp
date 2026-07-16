"""Unit tests for the Temporal Intelligence layer.

The public surface under test:
    _compute_temporal_trend(last_24h, last_7d, previous_7d) -> dict
    AnalyticsService.get_temporal_summary()                  -> dict
    GET /analytics/intelligence/temporal                     (route registration)

Business rules:
    change_percent = (last_7d - previous_7d) / previous_7d * 100
    previous_7d == 0, last_7d == 0  → change = 0.0  (stable)
    previous_7d == 0, last_7d  > 0  → change = 100.0 (increasing)

    change > 10   → "increasing"
    change < -10  → "decreasing"
    otherwise     → "stable"

Romania filtering uses metadata.ingestion.is_romania (repository responsibility;
tested here via service-level mock to confirm delegation).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.analytics.analytics_service import (
    AnalyticsService,
    _compute_temporal_trend,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _service(counts: dict) -> AnalyticsService:
    """Build an AnalyticsService with temporal_romania_counts mocked."""
    repo = MagicMock()
    repo.temporal_romania_counts = AsyncMock(return_value=counts)
    return AnalyticsService(repo)


def _counts(last_24h: int = 0, last_7d: int = 0, previous_7d: int = 0) -> dict:
    return {"last_24h": last_24h, "last_7d": last_7d, "previous_7d": previous_7d}


# ---------------------------------------------------------------------------
# _compute_temporal_trend — pure function, no I/O
# ---------------------------------------------------------------------------

class TestComputeTemporalTrendSchema:
    def test_returns_dict_with_required_keys(self):
        result = _compute_temporal_trend(0, 0, 0)
        assert set(result.keys()) == {
            "last_24h", "last_7d", "previous_7d", "change_percent", "trend"
        }

    def test_last_24h_nested_shape(self):
        result = _compute_temporal_trend(5, 0, 0)
        assert result["last_24h"] == {"romania_events": 5}

    def test_last_7d_nested_shape(self):
        result = _compute_temporal_trend(0, 7, 0)
        assert result["last_7d"] == {"romania_events": 7}

    def test_previous_7d_nested_shape(self):
        result = _compute_temporal_trend(0, 0, 3)
        assert result["previous_7d"] == {"romania_events": 3}

    def test_trend_is_valid_literal(self):
        for args in [(0, 0, 0), (10, 20, 10), (5, 3, 10)]:
            assert _compute_temporal_trend(*args)["trend"] in {
                "increasing", "stable", "decreasing"
            }

    def test_change_percent_is_float(self):
        result = _compute_temporal_trend(0, 10, 5)
        assert isinstance(result["change_percent"], float)


class TestComputeTemporalTrendEmptyDataset:
    def test_all_zeros_returns_stable(self):
        result = _compute_temporal_trend(0, 0, 0)
        assert result["trend"] == "stable"

    def test_all_zeros_change_percent_is_zero(self):
        result = _compute_temporal_trend(0, 0, 0)
        assert result["change_percent"] == 0.0

    def test_all_zeros_last_24h_is_zero(self):
        result = _compute_temporal_trend(0, 0, 0)
        assert result["last_24h"]["romania_events"] == 0


class TestComputeTemporalTrendIncreasing:
    def test_large_increase_is_increasing(self):
        # last_7d = 200, previous = 100 → +100% → increasing
        result = _compute_temporal_trend(10, 200, 100)
        assert result["trend"] == "increasing"

    def test_just_above_10pct_is_increasing(self):
        # (111 - 100) / 100 * 100 = 11.0 %  > 10 → increasing
        result = _compute_temporal_trend(0, 111, 100)
        assert result["trend"] == "increasing"
        assert result["change_percent"] == pytest.approx(11.0, abs=0.01)

    def test_previous_zero_current_positive_is_increasing(self):
        result = _compute_temporal_trend(3, 5, 0)
        assert result["trend"] == "increasing"
        assert result["change_percent"] == 100.0

    def test_change_percent_value_is_correct(self):
        # (130 - 100) / 100 * 100 = 30.0
        result = _compute_temporal_trend(0, 130, 100)
        assert result["change_percent"] == pytest.approx(30.0, abs=0.01)


class TestComputeTemporalTrendDecreasing:
    def test_large_decrease_is_decreasing(self):
        # (10 - 100) / 100 * 100 = -90% → decreasing
        result = _compute_temporal_trend(2, 10, 100)
        assert result["trend"] == "decreasing"

    def test_just_below_negative_10pct_is_decreasing(self):
        # (89 - 100) / 100 * 100 = -11.0 % < -10 → decreasing
        result = _compute_temporal_trend(0, 89, 100)
        assert result["trend"] == "decreasing"
        assert result["change_percent"] == pytest.approx(-11.0, abs=0.01)

    def test_change_percent_is_negative(self):
        result = _compute_temporal_trend(0, 50, 100)
        assert result["change_percent"] < 0


class TestComputeTemporalTrendStable:
    def test_no_change_is_stable(self):
        result = _compute_temporal_trend(5, 100, 100)
        assert result["trend"] == "stable"
        assert result["change_percent"] == pytest.approx(0.0, abs=0.01)

    def test_exactly_10pct_increase_is_stable(self):
        # (110 - 100) / 100 * 100 = 10.0 — NOT > 10, so stable
        result = _compute_temporal_trend(0, 110, 100)
        assert result["trend"] == "stable"
        assert result["change_percent"] == pytest.approx(10.0, abs=0.01)

    def test_exactly_negative_10pct_is_stable(self):
        # (90 - 100) / 100 * 100 = -10.0 — NOT < -10, so stable
        result = _compute_temporal_trend(0, 90, 100)
        assert result["trend"] == "stable"
        assert result["change_percent"] == pytest.approx(-10.0, abs=0.01)

    def test_small_positive_change_within_band_is_stable(self):
        result = _compute_temporal_trend(0, 105, 100)
        assert result["trend"] == "stable"

    def test_small_negative_change_within_band_is_stable(self):
        result = _compute_temporal_trend(0, 95, 100)
        assert result["trend"] == "stable"

    def test_previous_zero_current_zero_is_stable(self):
        result = _compute_temporal_trend(0, 0, 0)
        assert result["trend"] == "stable"
        assert result["change_percent"] == 0.0


# ---------------------------------------------------------------------------
# Boundary arithmetic — strict inequalities
# ---------------------------------------------------------------------------

class TestTrendBoundaries:
    @pytest.mark.parametrize("last_7d,previous_7d,expected_trend", [
        # Increasing side
        (112, 100, "increasing"),   # 12 %  >  10 → increasing
        (111, 100, "increasing"),   # 11 %  >  10 → increasing
        (110, 100, "stable"),       # 10 %  == 10 → stable (not strictly >)
        (109, 100, "stable"),       #  9 %  <  10 → stable
        # Decreasing side
        (91,  100, "stable"),       # -9 %  > -10 → stable
        (90,  100, "stable"),       # -10 % == -10 → stable (not strictly <)
        (89,  100, "decreasing"),   # -11 % < -10 → decreasing
        (88,  100, "decreasing"),   # -12 % < -10 → decreasing
    ])
    def test_boundary(self, last_7d, previous_7d, expected_trend):
        result = _compute_temporal_trend(0, last_7d, previous_7d)
        assert result["trend"] == expected_trend

    def test_change_percent_rounded_to_2_decimal_places(self):
        # (101 - 99) / 99 * 100 ≈ 2.020202... should round to 2.02
        result = _compute_temporal_trend(0, 101, 99)
        assert result["change_percent"] == pytest.approx(2.02, abs=0.005)

    def test_large_values_do_not_overflow(self):
        result = _compute_temporal_trend(9999, 1_000_000, 500_000)
        assert result["trend"] == "increasing"


# ---------------------------------------------------------------------------
# Romania filtering — verified via service → mock repo delegation
# ---------------------------------------------------------------------------

class TestRomaniaFiltering:
    def test_repo_called_with_now_datetime(self):
        """get_temporal_summary() must pass a UTC datetime to the repo."""
        repo = MagicMock()
        repo.temporal_romania_counts = AsyncMock(return_value=_counts())
        svc = AnalyticsService(repo)
        asyncio.run(svc.get_temporal_summary())
        repo.temporal_romania_counts.assert_called_once()
        call_arg = repo.temporal_romania_counts.call_args[0][0]
        assert isinstance(call_arg, datetime)

    def test_only_romania_flagged_events_counted(self):
        """Service returns the counts provided by the repo without modification.

        The actual is_romania filtering is enforced inside
        AnalyticsRepository.temporal_romania_counts; the service must pass
        through whatever the repo returns.
        """
        body = asyncio.run(_service(_counts(last_24h=3, last_7d=7, previous_7d=4)).get_temporal_summary())
        assert body["last_24h"]["romania_events"] == 3
        assert body["last_7d"]["romania_events"] == 7
        assert body["previous_7d"]["romania_events"] == 4

    def test_non_romania_events_not_counted(self):
        # Non-Romania events → repo returns 0 for all windows
        body = asyncio.run(_service(_counts(0, 0, 0)).get_temporal_summary())
        assert body["last_24h"]["romania_events"] == 0
        assert body["last_7d"]["romania_events"] == 0


# ---------------------------------------------------------------------------
# get_temporal_summary() service method — integration
# ---------------------------------------------------------------------------

class TestGetTemporalSummary:
    def test_response_keys(self):
        body = asyncio.run(_service(_counts()).get_temporal_summary())
        assert set(body.keys()) == {
            "last_24h", "last_7d", "previous_7d", "change_percent", "trend"
        }

    def test_increasing_scenario(self):
        # previous=50, last=60 → +20 % → increasing
        body = asyncio.run(_service(_counts(5, 60, 50)).get_temporal_summary())
        assert body["trend"] == "increasing"
        assert body["change_percent"] == pytest.approx(20.0, abs=0.01)

    def test_decreasing_scenario(self):
        # previous=100, last=80 → -20 % → decreasing
        body = asyncio.run(_service(_counts(2, 80, 100)).get_temporal_summary())
        assert body["trend"] == "decreasing"

    def test_stable_scenario(self):
        body = asyncio.run(_service(_counts(3, 100, 100)).get_temporal_summary())
        assert body["trend"] == "stable"

    def test_empty_dataset_stable(self):
        body = asyncio.run(_service(_counts(0, 0, 0)).get_temporal_summary())
        assert body["trend"] == "stable"
        assert body["change_percent"] == 0.0

    def test_last_24h_value_is_forwarded(self):
        body = asyncio.run(_service(_counts(last_24h=17, last_7d=50, previous_7d=50)).get_temporal_summary())
        assert body["last_24h"]["romania_events"] == 17

    def test_change_percent_type_is_float(self):
        body = asyncio.run(_service(_counts(0, 0, 0)).get_temporal_summary())
        assert isinstance(body["change_percent"], float)


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

class TestRouteRegistration:
    def test_temporal_endpoint_path_registered(self):
        from app.modules.analytics.analytics_routes import router
        paths = [r.path for r in router.routes]
        assert "/analytics/intelligence/temporal" in paths
