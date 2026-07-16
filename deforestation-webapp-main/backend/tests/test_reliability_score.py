"""Unit tests for the cross-source reliability score heuristic."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.analytics.analytics_service import AnalyticsService, _reliability_score


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sev(low=0, medium=0, high=0, critical=0) -> dict[str, int]:
    return {"low": low, "medium": medium, "high": high, "critical": critical}


def _service(rows: list[dict]) -> AnalyticsService:
    repo = MagicMock()
    repo.by_source = AsyncMock(return_value=rows)
    return AnalyticsService(repo)


def _row(
    source: str = "TEST",
    total: int = 10,
    romania: int = 5,
    avg_conf: float = 0.8,
    sev_low: int = 2,
    sev_medium: int = 3,
    sev_high: int = 3,
    sev_critical: int = 2,
) -> dict:
    return {
        "_id": source,
        "total_events": total,
        "romania_events": romania,
        "average_confidence": avg_conf,
        "sev_low": sev_low,
        "sev_medium": sev_medium,
        "sev_high": sev_high,
        "sev_critical": sev_critical,
    }


def _expected(avg_conf, total, romania, sev_dist) -> float:
    """Reference implementation that mirrors _reliability_score exactly."""
    if total == 0:
        return 0.0
    weights = {"low": 0.2, "medium": 0.5, "high": 0.8, "critical": 1.0}
    sev_w = sum(sev_dist.get(s, 0) * w for s, w in weights.items()) / total
    return round(0.4 * avg_conf + 0.3 * (romania / total) + 0.3 * sev_w, 4)


# ---------------------------------------------------------------------------
# Pure function: _reliability_score
# ---------------------------------------------------------------------------

class TestReliabilityScoreFunction:
    def test_zero_events_returns_zero(self):
        assert _reliability_score(0.9, 0, 0, _sev()) == 0.0

    def test_known_values_match_formula(self):
        """Manually computed expected value."""
        # avg_conf=0.78, total=10, romania=6, sev: med=2, high=5, crit=3
        # romania_ratio = 0.6
        # sev_weight = (2*0.5 + 5*0.8 + 3*1.0) / 10 = (1.0+4.0+3.0)/10 = 0.8
        # score = 0.4*0.78 + 0.3*0.6 + 0.3*0.8 = 0.312+0.18+0.24 = 0.732
        result = _reliability_score(0.78, 10, 6, _sev(medium=2, high=5, critical=3))
        assert result == pytest.approx(0.732, abs=1e-4)

    def test_all_low_severity_produces_lower_score(self):
        all_low = _reliability_score(0.5, 10, 5, _sev(low=10))
        all_crit = _reliability_score(0.5, 10, 5, _sev(critical=10))
        assert all_low < all_crit

    def test_all_critical_severity(self):
        # avg_conf=0.8, total=5, romania=5, all critical
        # sev_weight = (5*1.0)/5 = 1.0
        # score = 0.4*0.8 + 0.3*1.0 + 0.3*1.0 = 0.32+0.3+0.3 = 0.92
        result = _reliability_score(0.8, 5, 5, _sev(critical=5))
        assert result == pytest.approx(0.92, abs=1e-4)

    def test_all_low_severity(self):
        # avg_conf=0.8, total=5, romania=0, all low
        # sev_weight = (5*0.2)/5 = 0.2
        # score = 0.4*0.8 + 0.3*0 + 0.3*0.2 = 0.32+0+0.06 = 0.38
        result = _reliability_score(0.8, 5, 0, _sev(low=5))
        assert result == pytest.approx(0.38, abs=1e-4)

    def test_maximum_possible_score(self):
        """confidence=1.0, all romania, all critical → 1.0."""
        result = _reliability_score(1.0, 10, 10, _sev(critical=10))
        assert result == pytest.approx(1.0, abs=1e-4)

    def test_minimum_possible_score(self):
        """confidence=0.0, no romania, all low → 0.3*0.2 = 0.06."""
        result = _reliability_score(0.0, 10, 0, _sev(low=10))
        assert result == pytest.approx(0.06, abs=1e-4)

    def test_confidence_zero(self):
        result = _reliability_score(0.0, 10, 5, _sev(medium=10))
        expected = _expected(0.0, 10, 5, _sev(medium=10))
        assert result == pytest.approx(expected, abs=1e-4)

    def test_confidence_one(self):
        result = _reliability_score(1.0, 10, 5, _sev(medium=10))
        expected = _expected(1.0, 10, 5, _sev(medium=10))
        assert result == pytest.approx(expected, abs=1e-4)

    def test_romania_heavy_scores_higher_than_romania_light(self):
        base = dict(average_confidence=0.7, total_events=10,
                    severity_distribution=_sev(medium=5, high=5))
        heavy = _reliability_score(**base, romania_events=9)
        light = _reliability_score(**base, romania_events=1)
        assert heavy > light

    def test_result_in_0_to_1_range_for_valid_inputs(self):
        for total in (1, 5, 100):
            for romania in (0, total // 2, total):
                for conf in (0.0, 0.5, 1.0):
                    r = _reliability_score(
                        conf, total, romania, _sev(low=total // 4, medium=total // 4,
                                                    high=total // 4, critical=total // 4)
                    )
                    assert 0.0 <= r <= 1.0, f"out of range: {r}"

    def test_result_is_rounded_to_4_decimal_places(self):
        result = _reliability_score(0.123456, 7, 3, _sev(low=2, medium=3, high=2))
        assert result == round(result, 4)

    def test_matches_reference_formula(self):
        """Cross-check against the independent _expected() reference."""
        cases = [
            (0.9, 20, 15, _sev(low=2, medium=6, high=8, critical=4)),
            (0.65, 1, 0, _sev(high=1)),
            (0.5, 50, 25, _sev(low=10, medium=20, high=15, critical=5)),
        ]
        for conf, total, ro, sev in cases:
            assert _reliability_score(conf, total, ro, sev) == pytest.approx(
                _expected(conf, total, ro, sev), abs=1e-4
            )


# ---------------------------------------------------------------------------
# Integration: reliability_score appears in source_statistics()
# ---------------------------------------------------------------------------

class TestReliabilityScoreInSourceStatistics:
    def test_score_present_in_each_source_entry(self):
        body = asyncio.run(_service([_row()]).source_statistics())
        assert "reliability_score" in body["sources"][0]

    def test_score_is_float(self):
        body = asyncio.run(_service([_row()]).source_statistics())
        assert isinstance(body["sources"][0]["reliability_score"], float)

    def test_score_in_valid_range(self):
        body = asyncio.run(_service([_row()]).source_statistics())
        score = body["sources"][0]["reliability_score"]
        assert 0.0 <= score <= 1.0

    def test_zero_event_source_has_zero_score(self):
        zero_row = _row(total=0, romania=0, sev_low=0, sev_medium=0, sev_high=0, sev_critical=0)
        body = asyncio.run(_service([zero_row]).source_statistics())
        assert body["sources"][0]["reliability_score"] == 0.0

    def test_scores_are_independent_per_source(self):
        firms = _row("NASA FIRMS", total=10, romania=8, avg_conf=0.9,
                     sev_low=0, sev_medium=1, sev_high=5, sev_critical=4)
        csv = _row("CSV", total=10, romania=1, avg_conf=0.5,
                   sev_low=5, sev_medium=3, sev_high=2, sev_critical=0)
        body = asyncio.run(_service([firms, csv]).source_statistics())
        by_name = {s["source"]: s["reliability_score"] for s in body["sources"]}
        assert by_name["NASA FIRMS"] > by_name["CSV"]

    def test_high_confidence_source_scores_higher(self):
        high_conf = _row("A", avg_conf=1.0, total=10, romania=5,
                         sev_low=0, sev_medium=5, sev_high=5, sev_critical=0)
        low_conf = _row("B", avg_conf=0.0, total=10, romania=5,
                        sev_low=0, sev_medium=5, sev_high=5, sev_critical=0)
        body = asyncio.run(_service([high_conf, low_conf]).source_statistics())
        by_name = {s["source"]: s["reliability_score"] for s in body["sources"]}
        assert by_name["A"] > by_name["B"]

    def test_score_consistent_with_function_directly(self):
        """score in response must equal _reliability_score() called with same args."""
        r = _row(total=8, romania=4, avg_conf=0.75,
                 sev_low=1, sev_medium=3, sev_high=3, sev_critical=1)
        body = asyncio.run(_service([r]).source_statistics())
        entry = body["sources"][0]
        expected = _reliability_score(
            average_confidence=entry["average_confidence"],
            total_events=entry["total_events"],
            romania_events=entry["romania_events"],
            severity_distribution=entry["severity_distribution"],
        )
        assert entry["reliability_score"] == pytest.approx(expected, abs=1e-6)
