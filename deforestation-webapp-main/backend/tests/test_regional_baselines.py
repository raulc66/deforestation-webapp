"""Unit tests for the Regional Baseline Intelligence layer.

Surface under test:
    _compute_deviation(current_events, baseline_events)  → float
    _compute_baselines(rows, generated_at)               → dict
    AnalyticsService.get_regional_baselines()            → dict
    GET /analytics/intelligence/baselines                (route registration)

Baseline definition:
    baseline_events = round(baseline_raw / 4)
        where baseline_raw is the total Romania event count in the 28 days
        (weeks -1 through -4) preceding the current 7-day window.

Deviation rules (applied to the rounded int baseline):
    baseline == 0, current == 0  →   0.0
    baseline == 0, current  > 0  → 100.0
    otherwise                    → (current - baseline) / baseline * 100
                                   rounded to 2 decimal places.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.analytics.analytics_service import (
    AnalyticsService,
    _compute_baselines,
    _compute_deviation,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 13, 15, 0, 0, tzinfo=timezone.utc)


def _row(region: str, current: int, baseline_raw: int) -> dict:
    """Build a raw aggregation row as returned by regional_baselines()."""
    return {"_id": region, "current_events": current, "baseline_raw": baseline_raw}


def _service(rows: list[dict]) -> AnalyticsService:
    repo = MagicMock()
    repo.regional_baselines = AsyncMock(return_value=rows)
    return AnalyticsService(repo)


def _run(svc: AnalyticsService) -> dict:
    return asyncio.run(svc.get_regional_baselines())


# ---------------------------------------------------------------------------
# _compute_deviation — pure function
# ---------------------------------------------------------------------------

class TestComputeDeviation:
    def test_both_zero_returns_zero(self):
        assert _compute_deviation(0, 0) == 0.0

    def test_baseline_zero_current_positive_returns_100(self):
        assert _compute_deviation(5, 0) == 100.0

    def test_baseline_zero_current_zero_returns_zero(self):
        assert _compute_deviation(0, 0) == 0.0

    def test_positive_deviation(self):
        # (20 - 10) / 10 * 100 = 100 %
        assert _compute_deviation(20, 10) == pytest.approx(100.0, abs=0.01)

    def test_negative_deviation(self):
        # (10 - 20) / 20 * 100 = -50 %
        assert _compute_deviation(10, 20) == pytest.approx(-50.0, abs=0.01)

    def test_no_change_returns_zero(self):
        assert _compute_deviation(10, 10) == 0.0

    def test_result_rounded_to_2_decimal_places(self):
        # (101 - 99) / 99 * 100 ≈ 2.020202…  → 2.02
        result = _compute_deviation(101, 99)
        assert result == pytest.approx(2.02, abs=0.005)

    def test_large_positive_deviation(self):
        assert _compute_deviation(1000, 100) == pytest.approx(900.0, abs=0.01)

    def test_large_negative_deviation(self):
        assert _compute_deviation(0, 100) == pytest.approx(-100.0, abs=0.01)

    def test_returns_float(self):
        assert isinstance(_compute_deviation(5, 0), float)
        assert isinstance(_compute_deviation(10, 5), float)


# ---------------------------------------------------------------------------
# _compute_baselines — pure function (no I/O)
# ---------------------------------------------------------------------------

class TestComputeBaselinesSchema:
    def test_returns_generated_at_and_regions_keys(self):
        result = _compute_baselines([], _NOW)
        assert set(result.keys()) == {"generated_at", "regions"}

    def test_generated_at_is_forwarded(self):
        result = _compute_baselines([], _NOW)
        assert result["generated_at"] == _NOW

    def test_each_region_has_required_keys(self):
        rows = [_row("Carpathian Forest", 10, 40)]
        entry = _compute_baselines(rows, _NOW)["regions"][0]
        assert set(entry.keys()) == {
            "region", "baseline_events", "current_events", "deviation_percent",
            "forest_confidence",
        }

    def test_baseline_events_is_int(self):
        rows = [_row("Test", 5, 20)]
        entry = _compute_baselines(rows, _NOW)["regions"][0]
        assert isinstance(entry["baseline_events"], int)

    def test_current_events_is_int(self):
        rows = [_row("Test", 7, 20)]
        entry = _compute_baselines(rows, _NOW)["regions"][0]
        assert isinstance(entry["current_events"], int)

    def test_deviation_percent_is_float(self):
        rows = [_row("Test", 10, 40)]
        entry = _compute_baselines(rows, _NOW)["regions"][0]
        assert isinstance(entry["deviation_percent"], float)


class TestComputeBaselinesEmptyDataset:
    def test_empty_rows_returns_empty_regions_list(self):
        result = _compute_baselines([], _NOW)
        assert result["regions"] == []

    def test_empty_generated_at_still_present(self):
        result = _compute_baselines([], _NOW)
        assert result["generated_at"] == _NOW


class TestComputeBaselinesBaselineCalculation:
    def test_baseline_events_is_baseline_raw_divided_by_4_rounded(self):
        # baseline_raw=40 → 40/4 = 10.0 → 10
        rows = [_row("Carpathian Forest", 0, 40)]
        entry = _compute_baselines(rows, _NOW)["regions"][0]
        assert entry["baseline_events"] == 10

    def test_fractional_baseline_rounded_to_nearest_int(self):
        # baseline_raw=7 → 7/4 = 1.75 → round → 2
        rows = [_row("Test", 0, 7)]
        entry = _compute_baselines(rows, _NOW)["regions"][0]
        assert entry["baseline_events"] == 2

    def test_zero_baseline_raw_gives_zero_baseline_events(self):
        rows = [_row("Test", 0, 0)]
        entry = _compute_baselines(rows, _NOW)["regions"][0]
        assert entry["baseline_events"] == 0

    def test_current_events_forwarded_unchanged(self):
        rows = [_row("Maramures", 17, 40)]
        entry = _compute_baselines(rows, _NOW)["regions"][0]
        assert entry["current_events"] == 17


class TestComputeBaselinesDeviationCases:
    def test_no_baseline_no_current_deviation_zero(self):
        rows = [_row("Test", 0, 0)]
        entry = _compute_baselines(rows, _NOW)["regions"][0]
        assert entry["deviation_percent"] == 0.0

    def test_no_baseline_with_current_deviation_100(self):
        rows = [_row("Test", 5, 0)]
        entry = _compute_baselines(rows, _NOW)["regions"][0]
        assert entry["deviation_percent"] == 100.0

    def test_positive_deviation_spec_example(self):
        # baseline=10 (raw=40), current=20 → deviation=100%
        rows = [_row("Carpathian Forest", 20, 40)]
        entry = _compute_baselines(rows, _NOW)["regions"][0]
        assert entry["baseline_events"] == 10
        assert entry["deviation_percent"] == pytest.approx(100.0, abs=0.01)

    def test_negative_deviation_spec_example(self):
        # baseline=20 (raw=80), current=10 → deviation=-50%
        rows = [_row("Transylvania", 10, 80)]
        entry = _compute_baselines(rows, _NOW)["regions"][0]
        assert entry["baseline_events"] == 20
        assert entry["deviation_percent"] == pytest.approx(-50.0, abs=0.01)

    def test_no_change_deviation_zero(self):
        # baseline=5 (raw=20), current=5 → 0%
        rows = [_row("Dobrogea", 5, 20)]
        entry = _compute_baselines(rows, _NOW)["regions"][0]
        assert entry["deviation_percent"] == pytest.approx(0.0, abs=0.01)


class TestComputeBaselinesNullRegion:
    def test_null_region_id_mapped_to_unknown(self):
        rows = [{"_id": None, "current_events": 5, "baseline_raw": 20}]
        entry = _compute_baselines(rows, _NOW)["regions"][0]
        assert entry["region"] == "Unknown"


class TestComputeBaselinesMultipleRegions:
    def _multi_rows(self) -> list[dict]:
        return [
            _row("Bucovina",          current=5,  baseline_raw=20),   # dev=0%
            _row("Carpathian Forest", current=20, baseline_raw=40),   # dev=100%
            _row("Dobrogea",          current=10, baseline_raw=80),   # dev=-50%
            _row("Maramures",         current=0,  baseline_raw=0),    # dev=0%
        ]

    def test_all_regions_present(self):
        regions = _compute_baselines(self._multi_rows(), _NOW)["regions"]
        names = {r["region"] for r in regions}
        assert {"Bucovina", "Carpathian Forest", "Dobrogea", "Maramures"} == names

    def test_sorted_descending_by_deviation(self):
        regions = _compute_baselines(self._multi_rows(), _NOW)["regions"]
        deviations = [r["deviation_percent"] for r in regions]
        assert deviations == sorted(deviations, reverse=True)

    def test_highest_deviation_first(self):
        regions = _compute_baselines(self._multi_rows(), _NOW)["regions"]
        assert regions[0]["region"] == "Carpathian Forest"  # dev=100%

    def test_lowest_deviation_last(self):
        regions = _compute_baselines(self._multi_rows(), _NOW)["regions"]
        assert regions[-1]["deviation_percent"] == pytest.approx(-50.0, abs=0.01)

    def test_each_region_has_correct_values(self):
        rows = [
            _row("Alpha", current=20, baseline_raw=40),  # baseline=10, dev=100%
            _row("Beta",  current=10, baseline_raw=80),  # baseline=20, dev=-50%
        ]
        regions = _compute_baselines(rows, _NOW)["regions"]
        by_name = {r["region"]: r for r in regions}
        assert by_name["Alpha"]["baseline_events"] == 10
        assert by_name["Alpha"]["deviation_percent"] == pytest.approx(100.0, abs=0.01)
        assert by_name["Beta"]["baseline_events"] == 20
        assert by_name["Beta"]["deviation_percent"] == pytest.approx(-50.0, abs=0.01)


# ---------------------------------------------------------------------------
# Romania filtering — delegation to repository
# ---------------------------------------------------------------------------

class TestRomaniaFiltering:
    def test_repo_called_with_datetime(self):
        repo = MagicMock()
        repo.regional_baselines = AsyncMock(return_value=[])
        svc = AnalyticsService(repo)
        asyncio.run(svc.get_regional_baselines())
        repo.regional_baselines.assert_called_once()
        call_arg = repo.regional_baselines.call_args[0][0]
        assert isinstance(call_arg, datetime)

    def test_non_romania_events_not_counted(self):
        # Repository returns empty list when no Romania events exist
        body = _run(_service([]))
        assert body["regions"] == []

    def test_only_romania_rows_forwarded(self):
        # Repository already filters; service must not re-filter
        rows = [_row("Transylvania", 7, 28)]
        body = _run(_service(rows))
        assert len(body["regions"]) == 1
        assert body["regions"][0]["region"] == "Transylvania"


# ---------------------------------------------------------------------------
# get_regional_baselines() — service integration
# ---------------------------------------------------------------------------

class TestGetRegionalBaselines:
    def test_empty_dataset(self):
        body = _run(_service([]))
        assert body["regions"] == []

    def test_generated_at_is_datetime(self):
        body = _run(_service([]))
        assert isinstance(body["generated_at"], datetime)

    def test_response_keys(self):
        body = _run(_service([]))
        assert set(body.keys()) == {"generated_at", "regions"}

    def test_single_region_positive_deviation(self):
        # baseline_raw=40 → baseline=10; current=20 → dev=100%
        body = _run(_service([_row("Carpathian Forest", 20, 40)]))
        region = body["regions"][0]
        assert region["region"] == "Carpathian Forest"
        assert region["baseline_events"] == 10
        assert region["current_events"] == 20
        assert region["deviation_percent"] == pytest.approx(100.0, abs=0.01)

    def test_single_region_negative_deviation(self):
        body = _run(_service([_row("Transylvania", 10, 80)]))
        region = body["regions"][0]
        assert region["deviation_percent"] == pytest.approx(-50.0, abs=0.01)

    def test_multiple_regions_sorted_by_deviation_descending(self):
        rows = [
            _row("A", current=20, baseline_raw=40),   # dev=100%
            _row("B", current=10, baseline_raw=80),   # dev=-50%
            _row("C", current=5,  baseline_raw=20),   # dev=0%
        ]
        regions = _run(_service(rows))["regions"]
        deviations = [r["deviation_percent"] for r in regions]
        assert deviations == sorted(deviations, reverse=True)

    def test_region_no_baseline_no_current(self):
        body = _run(_service([_row("Empty Region", 0, 0)]))
        region = body["regions"][0]
        assert region["baseline_events"] == 0
        assert region["current_events"] == 0
        assert region["deviation_percent"] == 0.0

    def test_region_baseline_zero_current_positive(self):
        body = _run(_service([_row("New Region", 5, 0)]))
        assert body["regions"][0]["deviation_percent"] == 100.0


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

class TestRouteRegistration:
    def test_baselines_endpoint_path_registered(self):
        from app.modules.analytics.analytics_routes import router
        paths = [r.path for r in router.routes]
        assert "/analytics/intelligence/baselines" in paths
