"""Unit tests for the intelligence alert evaluation layer.

Alert type taxonomy:
  "volume"      — fires when total Romania events across all sources exceed 10.
  "reliability" — fires when FIRMS reliability_score > 0.65 AND FIRMS
                  contributes > 30 % of all events.

Both may be present in the same response when both conditions are satisfied.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.geography.geographic_scope import GeographicScope, GeographicScopePolicy
from app.modules.analytics.analytics_service import (
    AnalyticsService,
    _SEVERITY_RANK,
    _alert_message,
    _alert_severity,
    _evaluate_alerts,
)


# ---------------------------------------------------------------------------
# Raw-row factories (mirror what MongoDB by_source() returns)
# ---------------------------------------------------------------------------

def _firms_row(
    total: int = 20,
    romania: int = 12,
    avg_conf: float = 0.85,
    sev_low: int = 0,
    sev_medium: int = 5,
    sev_high: int = 10,
    sev_critical: int = 5,
) -> dict:
    return {
        "_id": "NASA FIRMS",
        "total_events": total,
        "romania_events": romania,
        "average_confidence": avg_conf,
        "sev_low": sev_low,
        "sev_medium": sev_medium,
        "sev_high": sev_high,
        "sev_critical": sev_critical,
    }


def _csv_row(
    total: int = 10,
    romania: int = 5,
    avg_conf: float = 0.72,
    sev_low: int = 2,
    sev_medium: int = 5,
    sev_high: int = 3,
    sev_critical: int = 0,
) -> dict:
    return {
        "_id": "CSV",
        "total_events": total,
        "romania_events": romania,
        "average_confidence": avg_conf,
        "sev_low": sev_low,
        "sev_medium": sev_medium,
        "sev_high": sev_high,
        "sev_critical": sev_critical,
    }


# ---------------------------------------------------------------------------
# Shaped-row helpers (shaped = raw row processed by _shape_source_rows)
# ---------------------------------------------------------------------------

def _shaped_firms(**kwargs) -> dict:
    from app.modules.analytics.analytics_service import _shape_source_rows
    return _shape_source_rows([_firms_row(**kwargs)])[0]


def _shaped_csv(**kwargs) -> dict:
    from app.modules.analytics.analytics_service import _shape_source_rows
    return _shape_source_rows([_csv_row(**kwargs)])[0]


def _low_reliability_firms(**kwargs) -> dict:
    """FIRMS-shaped row guaranteed to have reliability_score < 0.65.

    Uses avg_conf=0.3 and all-low severity.  Max possible score:
        0.4*0.3 + 0.3*1.0 + 0.3*(n*0.2/n) = 0.12 + 0.30 + 0.06 = 0.48
    """
    defaults = dict(avg_conf=0.3, sev_low=20, sev_medium=0, sev_high=0, sev_critical=0)
    defaults.update(kwargs)
    return _shaped_firms(**defaults)


def _high_reliability_firms(**kwargs) -> dict:
    """FIRMS-shaped row guaranteed to have reliability_score > 0.65.

    Uses avg_conf=0.95, high+critical severity dominating.
    """
    defaults = dict(
        total=40, romania=8, avg_conf=0.95,
        sev_low=0, sev_medium=0, sev_high=10, sev_critical=30,
    )
    defaults.update(kwargs)
    return _shaped_firms(**defaults)


def _service(by_source_rows: list[dict]) -> AnalyticsService:
    repo = MagicMock()
    repo.by_source = AsyncMock(return_value=by_source_rows)
    repo.scope_policy = GeographicScopePolicy(GeographicScope.ROMANIA)
    return AnalyticsService(repo)


# ---------------------------------------------------------------------------
# _alert_severity — pure function (no alert type dependency)
# ---------------------------------------------------------------------------

class TestAlertSeverity:
    @pytest.mark.parametrize("count,expected", [
        (0,   "low"),
        (5,   "low"),
        (10,  "low"),
        (11,  "low"),    # first value above volume trigger threshold
        (15,  "low"),
        (16,  "medium"),
        (40,  "medium"),
        (41,  "high"),
        (80,  "high"),
        (81,  "critical"),
        (200, "critical"),
    ])
    def test_thresholds(self, count, expected):
        assert _alert_severity(count) == expected

    def test_boundary_exactly_10_is_low(self):
        assert _alert_severity(10) == "low"

    def test_boundary_exactly_11_is_low(self):
        # severity scale starts at 5–15 = "low"; 11 still falls in that band
        assert _alert_severity(11) == "low"


# ---------------------------------------------------------------------------
# _alert_message — pure function, now parameterised by alert_type
# ---------------------------------------------------------------------------

class TestAlertMessageVolume:
    def test_critical_message(self):
        msg = _alert_message("volume", "critical", ["NASA FIRMS"])
        assert "Critical" in msg and "Romania" in msg

    def test_high_message(self):
        msg = _alert_message("volume", "high", ["NASA FIRMS"])
        assert "wildfire" in msg.lower() or "high" in msg.lower()

    def test_medium_firms_and_csv_uses_convergence(self):
        msg = _alert_message("volume", "medium", ["NASA FIRMS", "CSV"])
        assert "FIRMS" in msg and "CSV" in msg

    def test_medium_firms_only_omits_csv(self):
        msg = _alert_message("volume", "medium", ["NASA FIRMS"])
        assert "CSV" not in msg

    def test_low_with_firms_mentions_satellite(self):
        msg = _alert_message("volume", "low", ["NASA FIRMS"])
        assert "satellite" in msg.lower()

    def test_low_without_firms_still_mentions_romania(self):
        msg = _alert_message("volume", "low", ["CSV"])
        assert "Romania" in msg

    def test_all_combinations_non_empty(self):
        for sev in ("low", "medium", "high", "critical"):
            for sources in ([], ["NASA FIRMS"], ["CSV"], ["NASA FIRMS", "CSV"]):
                msg = _alert_message("volume", sev, sources)
                assert isinstance(msg, str) and len(msg) > 0


class TestAlertMessageReliability:
    def test_all_severities_non_empty(self):
        for sev in ("low", "medium", "high", "critical"):
            msg = _alert_message("reliability", sev, ["NASA FIRMS"])
            assert isinstance(msg, str) and len(msg) > 0

    def test_reliability_message_distinct_from_volume(self):
        for sev in ("low", "medium", "high", "critical"):
            vol = _alert_message("volume", sev, ["NASA FIRMS"])
            rel = _alert_message("reliability", sev, ["NASA FIRMS"])
            assert vol != rel, f"Messages should differ for severity={sev}"

    def test_reliability_message_references_firms(self):
        for sev in ("low", "medium", "high", "critical"):
            msg = _alert_message("reliability", sev, ["NASA FIRMS"])
            assert "FIRMS" in msg

    def test_reliability_messages_are_deterministic(self):
        msg_a = _alert_message("reliability", "high", ["NASA FIRMS"])
        msg_b = _alert_message("reliability", "high", ["NASA FIRMS"])
        assert msg_a == msg_b


# ---------------------------------------------------------------------------
# _evaluate_alerts — no trigger cases
# ---------------------------------------------------------------------------

class TestEvaluateAlertsNoTrigger:
    def test_empty_source_data_returns_no_alerts(self):
        assert _evaluate_alerts([]) == []

    def test_zero_romania_events_no_alert(self):
        # No Romania events → neither volume nor reliability fires
        # (reliability score includes romania_ratio, so it stays low too)
        firms = _shaped_firms(total=10, romania=0, avg_conf=0.9,
                               sev_low=0, sev_medium=2, sev_high=5, sev_critical=3)
        csv = _shaped_csv(total=5, romania=0)
        assert _evaluate_alerts([firms, csv]) == []

    def test_exactly_10_romania_events_no_volume_alert(self):
        # Volume threshold is strict: >10, not ≥10.
        firms = _low_reliability_firms(total=15, romania=10)
        alerts = _evaluate_alerts([firms])
        volume_alerts = [a for a in alerts if a["type"] == "volume"]
        assert volume_alerts == []

    def test_exactly_10_romania_events_no_reliability_alert_when_low_reliability(self):
        # Confirm low-reliability fixture produces no reliability alert either.
        firms = _low_reliability_firms(total=15, romania=10)
        reliability_alerts = [a for a in _evaluate_alerts([firms]) if a["type"] == "reliability"]
        assert reliability_alerts == []

    def test_low_volume_low_reliability_no_alerts(self):
        # romania=5 ≤ 10; reliability forced low → nothing fires
        firms = _low_reliability_firms(total=20, romania=5)
        assert _evaluate_alerts([firms]) == []

    def test_reliability_does_not_fire_when_firms_share_below_30pct(self):
        # High-reliability FIRMS, but CSV dominates → share < 30 %
        # total_events = 5 + 200 = 205; FIRMS share ≈ 2.4 %
        # total_romania = 3 + 3 = 6 ≤ 10
        firms = _high_reliability_firms(total=5, romania=3)
        csv_big = _shaped_csv(total=200, romania=3)
        assert _evaluate_alerts([firms, csv_big]) == []


# ---------------------------------------------------------------------------
# _evaluate_alerts — volume-only alerts
# ---------------------------------------------------------------------------

class TestEvaluateAlertsVolumeOnly:
    """Volume trigger fires; reliability trigger deliberately suppressed via
    low-reliability fixture so alert type semantics can be verified cleanly."""

    def test_volume_alert_fires_when_romania_exceeds_10(self):
        firms = _low_reliability_firms(total=20, romania=11)
        alerts = _evaluate_alerts([firms])
        assert any(a["type"] == "volume" for a in alerts)

    def test_volume_alert_type_field(self):
        firms = _low_reliability_firms(total=20, romania=11)
        volume_alerts = [a for a in _evaluate_alerts([firms]) if a["type"] == "volume"]
        assert len(volume_alerts) == 1
        assert volume_alerts[0]["type"] == "volume"

    def test_volume_alert_has_all_required_keys(self):
        firms = _low_reliability_firms(total=20, romania=12)
        alert = next(a for a in _evaluate_alerts([firms]) if a["type"] == "volume")
        assert set(alert.keys()) == {
            "type", "severity", "confidence", "reliability_score",
            "source_breakdown", "message",
        }

    def test_volume_alert_source_breakdown_contains_firms(self):
        firms = _low_reliability_firms(total=20, romania=12)
        breakdown = next(
            a for a in _evaluate_alerts([firms]) if a["type"] == "volume"
        )["source_breakdown"]
        assert breakdown["NASA FIRMS"] == 12

    def test_csv_only_volume_trigger(self):
        csv = _shaped_csv(total=20, romania=11, avg_conf=0.2,
                          sev_low=20, sev_medium=0, sev_high=0, sev_critical=0)
        volume_alerts = [a for a in _evaluate_alerts([csv]) if a["type"] == "volume"]
        assert len(volume_alerts) == 1

    def test_csv_volume_alert_source_breakdown(self):
        csv = _shaped_csv(total=20, romania=11, avg_conf=0.2,
                          sev_low=20, sev_medium=0, sev_high=0, sev_critical=0)
        alert = next(a for a in _evaluate_alerts([csv]) if a["type"] == "volume")
        assert alert["source_breakdown"]["CSV"] == 11

    def test_combined_sources_volume_trigger(self):
        # Each source alone is ≤10; together they exceed the threshold.
        firms = _low_reliability_firms(total=10, romania=6)
        csv = _shaped_csv(total=10, romania=6, avg_conf=0.2,
                          sev_low=10, sev_medium=0, sev_high=0, sev_critical=0)
        volume_alerts = [a for a in _evaluate_alerts([firms, csv]) if a["type"] == "volume"]
        assert len(volume_alerts) == 1

    def test_volume_confidence_is_weighted_average(self):
        firms = _low_reliability_firms(total=10, romania=11, avg_conf=0.9)
        csv = _shaped_csv(total=10, romania=0, avg_conf=0.5,
                          sev_low=10, sev_medium=0, sev_high=0, sev_critical=0)
        alert = next(a for a in _evaluate_alerts([firms, csv]) if a["type"] == "volume")
        expected = round((0.9 * 10 + 0.5 * 10) / 20, 3)
        assert alert["confidence"] == pytest.approx(expected, abs=1e-3)

    def test_volume_reliability_score_is_max_across_sources(self):
        firms = _low_reliability_firms(total=15, romania=12, avg_conf=0.3)
        csv = _shaped_csv(total=10, romania=0, avg_conf=0.2,
                          sev_low=10, sev_medium=0, sev_high=0, sev_critical=0)
        alert = next(a for a in _evaluate_alerts([firms, csv]) if a["type"] == "volume")
        expected = max(firms["reliability_score"], csv["reliability_score"])
        assert alert["reliability_score"] == pytest.approx(expected, abs=1e-4)


# ---------------------------------------------------------------------------
# _evaluate_alerts — reliability-only alerts
# ---------------------------------------------------------------------------

class TestEvaluateAlertsReliabilityOnly:
    """Reliability trigger fires; volume trigger deliberately suppressed by
    keeping total Romania events ≤ 10."""

    def test_reliability_alert_fires_when_firms_dominant_and_high_score(self):
        firms = _high_reliability_firms()  # romania=8 ≤ 10; reliability verified > 0.65
        alerts = _evaluate_alerts([firms])
        assert any(a["type"] == "reliability" for a in alerts)

    def test_reliability_alert_type_field(self):
        firms = _high_reliability_firms()
        rel_alerts = [a for a in _evaluate_alerts([firms]) if a["type"] == "reliability"]
        assert len(rel_alerts) == 1
        assert rel_alerts[0]["type"] == "reliability"

    def test_no_volume_alert_when_romania_at_or_below_10(self):
        firms = _high_reliability_firms()  # romania=8
        volume_alerts = [a for a in _evaluate_alerts([firms]) if a["type"] == "volume"]
        assert volume_alerts == []

    def test_reliability_alert_has_all_required_keys(self):
        firms = _high_reliability_firms()
        alert = next(a for a in _evaluate_alerts([firms]) if a["type"] == "reliability")
        assert set(alert.keys()) == {
            "type", "severity", "confidence", "reliability_score",
            "source_breakdown", "message",
        }

    def test_reliability_alert_confidence_is_firms_specific(self):
        # Reliability alert uses FIRMS confidence, not global weighted average.
        firms = _high_reliability_firms(avg_conf=0.91)
        alert = next(a for a in _evaluate_alerts([firms]) if a["type"] == "reliability")
        assert alert["confidence"] == pytest.approx(0.91, abs=1e-3)

    def test_reliability_alert_reliability_score_is_firms_specific(self):
        firms = _high_reliability_firms()
        alert = next(a for a in _evaluate_alerts([firms]) if a["type"] == "reliability")
        assert alert["reliability_score"] == pytest.approx(firms["reliability_score"], abs=1e-4)

    def test_reliability_alert_message_differs_from_volume_message(self):
        firms = _high_reliability_firms()
        rel_alert = next(a for a in _evaluate_alerts([firms]) if a["type"] == "reliability")
        # Cross-check: volume message for same severity would be different
        vol_msg = _alert_message("volume", rel_alert["severity"], [])
        assert rel_alert["message"] != vol_msg


# ---------------------------------------------------------------------------
# _evaluate_alerts — both triggers fire simultaneously
# ---------------------------------------------------------------------------

class TestEvaluateAlertsBothTriggers:
    """Verifies that when both conditions are met, two distinct alerts appear."""

    @staticmethod
    def _both_trigger_firms() -> dict:
        # total_romania=12 > 10 → volume; reliability forced high via critical severity
        return _shaped_firms(
            total=40, romania=12, avg_conf=0.95,
            sev_low=0, sev_medium=0, sev_high=10, sev_critical=30,
        )

    def test_both_alerts_present(self):
        firms = self._both_trigger_firms()
        alerts = _evaluate_alerts([firms])
        types = {a["type"] for a in alerts}
        assert "volume" in types
        assert "reliability" in types

    def test_exactly_two_alerts_returned(self):
        firms = self._both_trigger_firms()
        assert len(_evaluate_alerts([firms])) == 2

    def test_volume_alert_is_first(self):
        # Deterministic ordering: volume before reliability.
        firms = self._both_trigger_firms()
        alerts = _evaluate_alerts([firms])
        assert alerts[0]["type"] == "volume"
        assert alerts[1]["type"] == "reliability"

    def test_volume_and_reliability_share_same_severity(self):
        firms = self._both_trigger_firms()
        alerts = _evaluate_alerts([firms])
        assert alerts[0]["severity"] == alerts[1]["severity"]

    def test_volume_and_reliability_share_same_source_breakdown(self):
        firms = self._both_trigger_firms()
        alerts = _evaluate_alerts([firms])
        assert alerts[0]["source_breakdown"] == alerts[1]["source_breakdown"]

    def test_confidence_differs_between_alert_types(self):
        # Volume: weighted avg; Reliability: FIRMS-specific (same when single source,
        # but distinct fields conceptually — no assertion on equality required).
        csv_extra = _shaped_csv(
            total=10, romania=0, avg_conf=0.4,
            sev_low=10, sev_medium=0, sev_high=0, sev_critical=0,
        )
        firms = self._both_trigger_firms()
        alerts = _evaluate_alerts([firms, csv_extra])
        vol = next(a for a in alerts if a["type"] == "volume")
        rel = next(a for a in alerts if a["type"] == "reliability")
        # With two sources having different avg_conf, the aggregates differ.
        total_events = firms["total_events"] + csv_extra["total_events"]
        expected_vol_conf = round(
            (firms["average_confidence"] * firms["total_events"]
             + csv_extra["average_confidence"] * csv_extra["total_events"])
            / total_events,
            3,
        )
        assert vol["confidence"] == pytest.approx(expected_vol_conf, abs=1e-3)
        assert rel["confidence"] == pytest.approx(firms["average_confidence"], abs=1e-3)


# ---------------------------------------------------------------------------
# Severity classification correctness
# ---------------------------------------------------------------------------

class TestSeverityClassification:
    @pytest.mark.parametrize("romania,expected_sev", [
        (11, "low"),      # just above volume trigger
        (16, "medium"),
        (41, "high"),
        (81, "critical"),
    ])
    def test_volume_alert_severity_from_romania_count(self, romania, expected_sev):
        # Use low-reliability params to isolate severity assertion to volume alerts.
        total = max(romania + 5, 20)
        firms = _low_reliability_firms(total=total, romania=romania)
        volume_alert = next(
            a for a in _evaluate_alerts([firms]) if a["type"] == "volume"
        )
        assert volume_alert["severity"] == expected_sev

    def test_reliability_alert_inherits_same_severity_scale(self):
        # Reliability alert uses the same _alert_severity(total_romania) function.
        firms = _high_reliability_firms(total=40, romania=8)  # severity = "low"
        rel_alert = next(a for a in _evaluate_alerts([firms]) if a["type"] == "reliability")
        assert rel_alert["severity"] == _alert_severity(8)

    def test_highest_severity_in_summary_is_critical(self):
        body = asyncio.run(
            _service([_firms_row(total=100, romania=85)]).get_alerts()
        )
        assert body["summary"]["highest_severity"] == "critical"

    def test_severity_rank_ordering(self):
        assert _SEVERITY_RANK["low"] < _SEVERITY_RANK["medium"]
        assert _SEVERITY_RANK["medium"] < _SEVERITY_RANK["high"]
        assert _SEVERITY_RANK["high"] < _SEVERITY_RANK["critical"]


# ---------------------------------------------------------------------------
# Medium severity convergence message
# ---------------------------------------------------------------------------

class TestConvergenceMessage:
    def test_volume_medium_both_sources_uses_convergence_text(self):
        # total_romania = 10 + 10 = 20 → medium; use low-reliability to isolate
        firms = _low_reliability_firms(total=20, romania=10, avg_conf=0.3)
        csv = _shaped_csv(total=20, romania=10, avg_conf=0.2,
                          sev_low=20, sev_medium=0, sev_high=0, sev_critical=0)
        alert = next(a for a in _evaluate_alerts([firms, csv]) if a["type"] == "volume")
        assert alert["severity"] == "medium"
        assert "FIRMS" in alert["message"]
        assert "CSV" in alert["message"]


# ---------------------------------------------------------------------------
# get_alerts() service method
# ---------------------------------------------------------------------------

class TestGetAlerts:
    def test_no_alerts_returns_empty_list(self):
        body = asyncio.run(_service([]).get_alerts())
        assert body["alerts"] == []

    def test_summary_total_alerts_zero_when_no_alerts(self):
        body = asyncio.run(_service([]).get_alerts())
        assert body["summary"]["total_alerts"] == 0

    def test_summary_highest_severity_none_when_no_alerts(self):
        body = asyncio.run(_service([]).get_alerts())
        assert body["summary"]["highest_severity"] is None

    def test_response_has_alerts_and_summary_keys(self):
        body = asyncio.run(_service([]).get_alerts())
        assert set(body.keys()) == {"alerts", "summary", "geographic_scope"}

    def test_volume_only_produces_one_alert(self):
        # Low-reliability params: only volume trigger fires.
        row = _firms_row(total=20, romania=12, avg_conf=0.3,
                         sev_low=20, sev_medium=0, sev_high=0, sev_critical=0)
        body = asyncio.run(_service([row]).get_alerts())
        assert body["summary"]["total_alerts"] == 1
        assert body["alerts"][0]["type"] == "volume"

    def test_both_triggers_produce_two_alerts(self):
        row = _firms_row(total=40, romania=12, avg_conf=0.95,
                         sev_low=0, sev_medium=0, sev_high=10, sev_critical=30)
        body = asyncio.run(_service([row]).get_alerts())
        assert body["summary"]["total_alerts"] == 2
        types = {a["type"] for a in body["alerts"]}
        assert types == {"volume", "reliability"}

    def test_highest_severity_across_all_alerts(self):
        # With total=50, romania=20: verify only volume fires (reliability stays < 0.65)
        # and highest_severity reflects that single alert.
        body = asyncio.run(
            _service([_firms_row(total=50, romania=20)]).get_alerts()
        )
        severities = [a["severity"] for a in body["alerts"]]
        expected_highest = max(severities, key=lambda s: _SEVERITY_RANK[s])
        assert body["summary"]["highest_severity"] == expected_highest

    def test_endpoint_path_registered(self):
        from app.modules.analytics.analytics_routes import router
        paths = [r.path for r in router.routes]
        assert "/analytics/intelligence/alerts" in paths
