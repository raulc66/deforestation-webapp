"""Unit tests for the first Anomaly Detection layer.

Surface under test:
    _compute_anomaly_score(current_events, baseline_events, deviation_percent)
    _anomaly_severity(score)
    _evaluate_anomalies(regions, generated_at)
    AnalyticsService.get_anomalies()
    GET /analytics/intelligence/anomalies   (route registration)

Eligibility for anomaly candidacy:
    current_events  >= 5    (volume gate)
    deviation_percent >= 50 (signal gate)

Score formula:
    volume_component    = min(current_events / 50, 1.0)
    deviation_component = min(deviation_percent / 200, 1.0)
    score = 0.4 * volume_component + 0.6 * deviation_component

Severity boundaries (inclusive >=):
    >= 0.80 → critical
    >= 0.60 → high
    >= 0.40 → medium
         else low
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.analytics.analytics_service import (
    AnalyticsService,
    _anomaly_severity,
    _compute_anomaly_score,
    _evaluate_anomalies,
)

# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 13, 18, 0, 0, tzinfo=timezone.utc)


def _region(
    name: str,
    current: int,
    deviation: float,
    baseline: int = 10,
) -> dict:
    """Build a pre-shaped baseline region dict (output of _compute_baselines)."""
    return {
        "region": name,
        "baseline_events": baseline,
        "current_events": current,
        "deviation_percent": float(deviation),
    }


def _raw_row(
    region: str,
    current: int,
    baseline_raw: int,
    incident_category: str = "wildfire",
) -> dict:
    """Raw aggregation row as returned by repo.regional_baselines()."""
    return {
        "_id": {"region": region, "incident_category": incident_category},
        "current_events": current,
        "baseline_raw": baseline_raw,
    }


def _service(raw_rows: list[dict]) -> AnalyticsService:
    repo = MagicMock()
    repo.regional_baselines = AsyncMock(return_value=raw_rows)
    return AnalyticsService(repo)


def _run(svc: AnalyticsService) -> dict:
    return asyncio.run(svc.get_anomalies())


# ---------------------------------------------------------------------------
# _compute_anomaly_score — pure function
# ---------------------------------------------------------------------------

class TestComputeAnomalyScore:
    def test_returns_float(self):
        assert isinstance(_compute_anomaly_score(10, 5, 100.0), float)

    def test_rounded_to_4_decimal_places(self):
        # Use values that produce a repeating decimal to verify rounding.
        score = _compute_anomaly_score(10, 3, 100.0)
        # volume = 10/50 = 0.2; deviation = 100/200 = 0.5
        # score = 0.4*0.2 + 0.6*0.5 = 0.08 + 0.30 = 0.38 (exact)
        assert score == pytest.approx(0.38, abs=1e-4)

    def test_max_score_is_one(self):
        score = _compute_anomaly_score(50, 0, 200.0)
        # volume = min(50/50,1)=1.0; deviation = min(200/200,1)=1.0
        # score = 0.4+0.6 = 1.0
        assert score == pytest.approx(1.0, abs=1e-4)

    def test_volume_capped_at_one(self):
        # current=100 → volume = min(100/50,1) = 1.0
        uncapped = _compute_anomaly_score(100, 0, 200.0)
        capped    = _compute_anomaly_score(50,  0, 200.0)
        assert uncapped == pytest.approx(capped, abs=1e-4)

    def test_deviation_capped_at_one(self):
        # deviation=400 → deviation_component = min(400/200,1) = 1.0
        uncapped = _compute_anomaly_score(50, 0, 400.0)
        capped    = _compute_anomaly_score(50, 0, 200.0)
        assert uncapped == pytest.approx(capped, abs=1e-4)

    def test_minimum_eligible_inputs(self):
        # current=5, deviation=50 (minimum eligible values)
        score = _compute_anomaly_score(5, 10, 50.0)
        # volume = 5/50 = 0.1; deviation = 50/200 = 0.25
        # score = 0.4*0.1 + 0.6*0.25 = 0.04 + 0.15 = 0.19
        assert score == pytest.approx(0.19, abs=1e-4)

    def test_baseline_events_not_used_in_current_formula(self):
        # Changing baseline should not affect the score (formula uses only
        # current_events and deviation_percent in the current implementation).
        score_a = _compute_anomaly_score(20, 5, 100.0)
        score_b = _compute_anomaly_score(20, 999, 100.0)
        assert score_a == pytest.approx(score_b, abs=1e-4)

    def test_score_in_valid_range(self):
        for current in (5, 25, 50, 100):
            for deviation in (50.0, 100.0, 200.0, 500.0):
                score = _compute_anomaly_score(current, 10, deviation)
                assert 0.0 <= score <= 1.0, f"{current=} {deviation=} → {score}"

    def test_known_values(self):
        # volume=0.6, deviation=0.75 → 0.4*0.6+0.6*0.75 = 0.24+0.45 = 0.69
        score = _compute_anomaly_score(30, 12, 150.0)
        assert score == pytest.approx(0.69, abs=1e-4)


# ---------------------------------------------------------------------------
# _anomaly_severity — pure function
# ---------------------------------------------------------------------------

class TestAnomalySeverity:
    @pytest.mark.parametrize("score,expected", [
        (0.0,   "low"),
        (0.39,  "low"),
        (0.40,  "medium"),   # boundary — inclusive
        (0.59,  "medium"),
        (0.60,  "high"),     # boundary — inclusive
        (0.79,  "high"),
        (0.80,  "critical"), # boundary — inclusive
        (0.99,  "critical"),
        (1.0,   "critical"),
    ])
    def test_boundaries(self, score, expected):
        assert _anomaly_severity(score) == expected

    def test_returns_string(self):
        assert isinstance(_anomaly_severity(0.5), str)

    def test_valid_labels_only(self):
        for score in (0.0, 0.39, 0.40, 0.60, 0.80, 1.0):
            assert _anomaly_severity(score) in {"low", "medium", "high", "critical"}


# ---------------------------------------------------------------------------
# _evaluate_anomalies — pure function
# ---------------------------------------------------------------------------

class TestEvaluateAnomaliesSchema:
    def test_returns_generated_at_and_anomalies_keys(self):
        result = _evaluate_anomalies([], _NOW)
        assert set(result.keys()) == {"generated_at", "anomalies"}

    def test_generated_at_forwarded(self):
        result = _evaluate_anomalies([], _NOW)
        assert result["generated_at"] == _NOW

    def test_each_anomaly_has_required_keys(self):
        regions = [_region("Carpathian Forest", current=30, deviation=150.0)]
        anomaly = _evaluate_anomalies(regions, _NOW)["anomalies"][0]
        assert set(anomaly.keys()) == {
            "region", "baseline_events", "current_events",
            "deviation_percent", "anomaly_score", "severity", "status",
            "forest_confidence",
        }

    def test_status_is_always_active(self):
        regions = [_region("Test", current=10, deviation=100.0)]
        anomaly = _evaluate_anomalies(regions, _NOW)["anomalies"][0]
        assert anomaly["status"] == "active"

    def test_region_name_forwarded(self):
        regions = [_region("Maramures", current=10, deviation=100.0)]
        anomaly = _evaluate_anomalies(regions, _NOW)["anomalies"][0]
        assert anomaly["region"] == "Maramures"


class TestEvaluateAnomaliesEmptyDataset:
    def test_empty_regions_returns_empty_anomalies(self):
        result = _evaluate_anomalies([], _NOW)
        assert result["anomalies"] == []


class TestEvaluateAnomaliesEligibility:
    def test_excluded_when_current_below_5(self):
        regions = [_region("Test", current=4, deviation=200.0)]
        assert _evaluate_anomalies(regions, _NOW)["anomalies"] == []

    def test_excluded_when_current_exactly_4(self):
        assert _evaluate_anomalies([_region("T", 4, 100.0)], _NOW)["anomalies"] == []

    def test_included_when_current_exactly_5(self):
        regions = [_region("Test", current=5, deviation=50.0)]
        anomalies = _evaluate_anomalies(regions, _NOW)["anomalies"]
        assert len(anomalies) == 1

    def test_excluded_when_deviation_below_50(self):
        regions = [_region("Test", current=10, deviation=49.99)]
        assert _evaluate_anomalies(regions, _NOW)["anomalies"] == []

    def test_excluded_when_deviation_exactly_49(self):
        assert _evaluate_anomalies([_region("T", 10, 49.0)], _NOW)["anomalies"] == []

    def test_included_when_deviation_exactly_50(self):
        regions = [_region("Test", current=10, deviation=50.0)]
        anomalies = _evaluate_anomalies(regions, _NOW)["anomalies"]
        assert len(anomalies) == 1

    def test_included_on_exact_thresholds(self):
        # Both gates at their minimum: current=5, deviation=50
        regions = [_region("Boundary", current=5, deviation=50.0)]
        anomalies = _evaluate_anomalies(regions, _NOW)["anomalies"]
        assert len(anomalies) == 1
        assert anomalies[0]["region"] == "Boundary"

    def test_excluded_when_current_zero_and_deviation_zero(self):
        regions = [_region("Dead", current=0, deviation=0.0)]
        assert _evaluate_anomalies(regions, _NOW)["anomalies"] == []

    def test_excluded_when_current_ok_but_negative_deviation(self):
        # Declining regions are not anomalies in the current model.
        regions = [_region("Quiet", current=10, deviation=-60.0)]
        assert _evaluate_anomalies(regions, _NOW)["anomalies"] == []


class TestEvaluateAnomaliesScore:
    def test_score_computed_correctly(self):
        # current=30, deviation=150 → vol=0.6, dev=0.75 → 0.4*0.6+0.6*0.75=0.69
        regions = [_region("R", current=30, deviation=150.0)]
        anomaly = _evaluate_anomalies(regions, _NOW)["anomalies"][0]
        assert anomaly["anomaly_score"] == pytest.approx(0.69, abs=1e-4)

    def test_severity_derived_from_score(self):
        # score=0.69 → "high"
        regions = [_region("R", current=30, deviation=150.0)]
        anomaly = _evaluate_anomalies(regions, _NOW)["anomalies"][0]
        assert anomaly["severity"] == "high"

    def test_baseline_and_current_forwarded(self):
        regions = [_region("R", current=20, deviation=100.0, baseline=10)]
        anomaly = _evaluate_anomalies(regions, _NOW)["anomalies"][0]
        assert anomaly["baseline_events"] == 10
        assert anomaly["current_events"] == 20

    def test_deviation_percent_forwarded(self):
        regions = [_region("R", current=20, deviation=100.0)]
        anomaly = _evaluate_anomalies(regions, _NOW)["anomalies"][0]
        assert anomaly["deviation_percent"] == pytest.approx(100.0, abs=0.01)


class TestEvaluateAnomaliesMultipleRegions:
    def _multi(self) -> list[dict]:
        return [
            # high deviation, high volume → highest score
            _region("Carpathian Forest", current=50, deviation=200.0),
            # medium deviation, medium volume
            _region("Transylvania",      current=20, deviation=100.0),
            # just on thresholds → lowest score among anomalies
            _region("Dobrogea",          current=5,  deviation=50.0),
            # below volume → excluded
            _region("Bucovina",          current=4,  deviation=200.0),
            # below deviation → excluded
            _region("Maramures",         current=20, deviation=30.0),
        ]

    def test_only_eligible_regions_returned(self):
        anomalies = _evaluate_anomalies(self._multi(), _NOW)["anomalies"]
        names = {a["region"] for a in anomalies}
        assert names == {"Carpathian Forest", "Transylvania", "Dobrogea"}

    def test_sorted_descending_by_score(self):
        anomalies = _evaluate_anomalies(self._multi(), _NOW)["anomalies"]
        scores = [a["anomaly_score"] for a in anomalies]
        assert scores == sorted(scores, reverse=True)

    def test_highest_score_first(self):
        anomalies = _evaluate_anomalies(self._multi(), _NOW)["anomalies"]
        assert anomalies[0]["region"] == "Carpathian Forest"

    def test_all_have_active_status(self):
        anomalies = _evaluate_anomalies(self._multi(), _NOW)["anomalies"]
        assert all(a["status"] == "active" for a in anomalies)


class TestEvaluateAnomaliesSeverityBoundaries:
    @pytest.mark.parametrize("current,deviation,expected_severity", [
        # Score ≈ 0.39 → low
        # vol=5/50=0.1, dev=50/200=0.25 → 0.04+0.15=0.19 (low)
        (5,  50.0,  "low"),
        # Score = 0.40: need 0.4*vol + 0.6*dev = 0.40
        # e.g. current=25→vol=0.5, dev=x: 0.4*0.5+0.6*x=0.40 → x=(0.40-0.20)/0.6=1/3≈0.333 → deviation=66.67
        # Let's use current=50(vol=1.0), deviation=0: 0.4→medium; verify:
        (50, 50.0,  "medium"),   # vol=1.0, dev=0.25 → 0.4*1.0+0.6*0.25=0.55 → medium
        # Score ≥ 0.60: current=50, deviation=100 → vol=1.0, dev=0.5 → 0.4+0.30=0.70 → high
        (50, 100.0, "high"),
        # Score ≥ 0.80: current=50, deviation=200 → vol=1.0, dev=1.0 → 0.4+0.60=1.0 → critical
        (50, 200.0, "critical"),
    ])
    def test_severity_from_score(self, current, deviation, expected_severity):
        regions = [_region("R", current=current, deviation=deviation)]
        anomaly = _evaluate_anomalies(regions, _NOW)["anomalies"][0]
        assert anomaly["severity"] == expected_severity

    @pytest.mark.parametrize("score,expected", [
        (0.39, "low"),
        (0.40, "medium"),
        (0.59, "medium"),
        (0.60, "high"),
        (0.79, "high"),
        (0.80, "critical"),
    ])
    def test_severity_boundary_values_via_pure_function(self, score, expected):
        assert _anomaly_severity(score) == expected


# ---------------------------------------------------------------------------
# get_anomalies() — service integration
# ---------------------------------------------------------------------------

class TestGetAnomalies:
    def test_empty_dataset_returns_empty_anomalies(self):
        body = _run(_service([]))
        assert body["anomalies"] == []

    def test_response_keys(self):
        body = _run(_service([]))
        assert set(body.keys()) == {"generated_at", "anomalies", "geographic_scope"}

    def test_generated_at_is_datetime(self):
        body = _run(_service([]))
        assert isinstance(body["generated_at"], datetime)

    def test_repo_called_once_with_datetime(self):
        repo = MagicMock()
        repo.regional_baselines = AsyncMock(return_value=[])
        svc = AnalyticsService(repo)
        asyncio.run(svc.get_anomalies())
        repo.regional_baselines.assert_called_once()
        arg = repo.regional_baselines.call_args[0][0]
        assert isinstance(arg, datetime)

    def test_single_eligible_region_appears(self):
        # baseline_raw=20 → baseline_events=5; current=10; deviation=(10-5)/5*100=100%
        rows = [_raw_row("Carpathian Forest", current=10, baseline_raw=20)]
        body = _run(_service(rows))
        assert len(body["anomalies"]) == 1
        assert body["anomalies"][0]["region"] == "Carpathian Forest"

    def test_ineligible_region_excluded(self):
        # current=2 < 5 → excluded regardless of deviation
        rows = [_raw_row("Quiet Region", current=2, baseline_raw=0)]
        body = _run(_service(rows))
        assert body["anomalies"] == []

    def test_anomaly_score_and_severity_present(self):
        rows = [_raw_row("Test", current=10, baseline_raw=20)]
        anomaly = _run(_service(rows))["anomalies"][0]
        assert "anomaly_score" in anomaly
        assert "severity" in anomaly
        assert anomaly["severity"] in {"low", "medium", "high", "critical"}

    def test_status_is_active(self):
        rows = [_raw_row("Test", current=10, baseline_raw=20)]
        anomaly = _run(_service(rows))["anomalies"][0]
        assert anomaly["status"] == "active"

    def test_multiple_anomalies_sorted_by_score(self):
        rows = [
            _raw_row("A", current=50, baseline_raw=40),  # high score
            _raw_row("B", current=5,  baseline_raw=0),   # low score
        ]
        anomalies = _run(_service(rows))["anomalies"]
        # B: baseline=0, current=5 → deviation=100% → score=0.4*(5/50)+0.6*(100/200)=0.04+0.30=0.34 → low
        # A: baseline=10, current=50 → deviation=400% → vol=1.0, dev=1.0 → 1.0 → critical
        scores = [a["anomaly_score"] for a in anomalies]
        assert scores == sorted(scores, reverse=True)

    def test_no_repo_duplication(self):
        """regional_baselines is called exactly once — no second aggregation."""
        repo = MagicMock()
        repo.regional_baselines = AsyncMock(return_value=[])
        svc = AnalyticsService(repo)
        asyncio.run(svc.get_anomalies())
        assert repo.regional_baselines.call_count == 1


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

class TestRouteRegistration:
    def test_anomalies_endpoint_registered(self):
        from app.modules.analytics.analytics_routes import router
        paths = [r.path for r in router.routes]
        assert "/analytics/intelligence/anomalies" in paths
