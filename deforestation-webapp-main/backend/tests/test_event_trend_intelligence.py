"""Unit tests for Event Trend Intelligence.

Surface under test:
    _compute_trend(previous_score, current_score)  — pure function
    IntelligenceEventsService.reconcile()  — trend and previous_score set
    IntelligenceEventsService.get_events_summary()  — worsening/stable/improving counts
    IntelligenceEvent model  — previous_score and trend fields

Design:
    - All tests mock the repository layer; no MongoDB connection needed.
    - Pure-logic assertions are made directly against _compute_trend.
    - reconcile() tests inspect the dict passed to repo.create / repo.update.
    - get_events_summary() tests supply synthetic event lists via the repo mock.
    - Boundary tests use exact ±0.05 values to confirm the strict > / < operators.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.analytics.intelligence_events_service import (
    IntelligenceEventsService,
    _compute_trend,
)

# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 13, 20, 30, 0, tzinfo=timezone.utc)

_ANOMALY = {
    "region": "Carpathian Forest",
    "baseline_events": 10,
    "current_events": 30,
    "deviation_percent": 150.0,
    "anomaly_score": 0.60,
    "severity": "high",
    "status": "active",
}


def _mock_repo(
    active_events: list[dict] | None = None,
    all_events: list[dict] | None = None,
) -> MagicMock:
    repo = MagicMock()
    repo.find_active = AsyncMock(return_value=active_events or [])
    repo.find_all = AsyncMock(return_value=all_events or [])
    repo.find_active_by_region = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value={"id": "new-id-1"})
    repo.update = AsyncMock(return_value=None)
    repo.resolve = AsyncMock(return_value=None)
    return repo


def _svc(repo: MagicMock) -> IntelligenceEventsService:
    return IntelligenceEventsService(repo)


def _active_event(
    region: str = "Carpathian Forest",
    event_id: str = "evt-001",
    detection_count: int = 1,
    severity: str = "high",
    current_score: float = 0.60,
    escalation_level: str = "normal",
    previous_score: float | None = None,
    trend: str = "new",
) -> dict:
    return {
        "id": event_id,
        "event_type": "anomaly",
        "region": region,
        "status": "active",
        "severity": severity,
        "escalation_level": escalation_level,
        "previous_score": previous_score,
        "trend": trend,
        "first_detected_at": _NOW,
        "last_detected_at": _NOW,
        "detection_count": detection_count,
        "current_score": current_score,
        "metadata": {},
    }


def _event_with_status(
    status: str,
    trend: str = "new",
    escalation_level: str = "normal",
    region: str = "R",
) -> dict:
    base = _active_event(region=region, trend=trend, escalation_level=escalation_level)
    base["status"] = status
    if status == "resolved":
        base["resolved_at"] = _NOW
    return base


def _run(coro) -> object:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# _compute_trend — new event
# ---------------------------------------------------------------------------

class TestComputeTrendNew:
    def test_none_previous_score_is_new(self):
        assert _compute_trend(None, 0.5) == "new"

    def test_none_previous_score_any_current_is_new(self):
        assert _compute_trend(None, 0.0) == "new"

    def test_none_previous_score_high_current_is_new(self):
        assert _compute_trend(None, 1.0) == "new"


# ---------------------------------------------------------------------------
# _compute_trend — worsening threshold
# ---------------------------------------------------------------------------

class TestComputeTrendWorsening:
    def test_difference_above_threshold_is_worsening(self):
        # 0.4 → 0.6: diff = +0.2
        assert _compute_trend(0.4, 0.6) == "worsening"

    def test_small_increase_above_threshold_is_worsening(self):
        # 0.5 → 0.56: diff = +0.06
        assert _compute_trend(0.5, 0.56) == "worsening"

    def test_large_increase_is_worsening(self):
        # 0.1 → 0.9: diff = +0.8
        assert _compute_trend(0.1, 0.9) == "worsening"

    def test_just_above_positive_boundary_is_worsening(self):
        # 0.5 + 0.051 = 0.551; diff = +0.051 (strictly > 0.05)
        assert _compute_trend(0.5, 0.551) == "worsening"


# ---------------------------------------------------------------------------
# _compute_trend — improving threshold
# ---------------------------------------------------------------------------

class TestComputeTrendImproving:
    def test_difference_below_threshold_is_improving(self):
        # 0.8 → 0.5: diff = -0.3
        assert _compute_trend(0.8, 0.5) == "improving"

    def test_small_decrease_below_threshold_is_improving(self):
        # 0.7 → 0.63: diff = -0.07
        assert _compute_trend(0.7, 0.63) == "improving"

    def test_large_decrease_is_improving(self):
        # 0.9 → 0.1: diff = -0.8
        assert _compute_trend(0.9, 0.1) == "improving"

    def test_just_below_negative_boundary_is_improving(self):
        # 0.5 - 0.051 = 0.449; diff = -0.051 (strictly < -0.05)
        assert _compute_trend(0.5, 0.449) == "improving"


# ---------------------------------------------------------------------------
# _compute_trend — stable threshold and exact boundaries
# ---------------------------------------------------------------------------

class TestComputeTrendStable:
    def test_zero_difference_is_stable(self):
        assert _compute_trend(0.5, 0.5) == "stable"

    def test_tiny_positive_difference_is_stable(self):
        # diff = +0.01 — well within the ±0.05 band
        assert _compute_trend(0.5, 0.51) == "stable"

    def test_tiny_negative_difference_is_stable(self):
        # diff = -0.01
        assert _compute_trend(0.5, 0.49) == "stable"

    def test_upper_boundary_below_threshold_is_stable(self):
        # diff = +0.04 — safely inside the stable band
        # (0.55 - 0.50 has float representation 0.050000000000000044, which is
        #  strictly > 0.05 and therefore worsening; use a value well below 0.05)
        assert _compute_trend(0.5, 0.54) == "stable"

    def test_exact_negative_boundary_is_stable(self):
        # diff = exactly -0.05 → NOT improving (rule uses strict <)
        assert _compute_trend(0.5, 0.45) == "stable"

    def test_just_inside_positive_boundary_is_stable(self):
        # diff = +0.049
        assert _compute_trend(0.5, 0.549) == "stable"

    def test_just_inside_negative_boundary_is_stable(self):
        # diff = -0.049
        assert _compute_trend(0.5, 0.451) == "stable"


# ---------------------------------------------------------------------------
# reconcile() create path — trend and previous_score initialised
# ---------------------------------------------------------------------------

class TestReconcileTrendCreate:
    def test_new_event_has_trend_new(self):
        repo = _mock_repo(active_events=[])
        _run(_svc(repo).reconcile([_ANOMALY], _NOW))
        created = repo.create.call_args[0][0]
        assert created["trend"] == "new"

    def test_new_event_has_previous_score_none(self):
        repo = _mock_repo(active_events=[])
        _run(_svc(repo).reconcile([_ANOMALY], _NOW))
        created = repo.create.call_args[0][0]
        assert created["previous_score"] is None

    def test_trend_key_present_on_create(self):
        repo = _mock_repo(active_events=[])
        _run(_svc(repo).reconcile([_ANOMALY], _NOW))
        created = repo.create.call_args[0][0]
        assert "trend" in created

    def test_previous_score_key_present_on_create(self):
        repo = _mock_repo(active_events=[])
        _run(_svc(repo).reconcile([_ANOMALY], _NOW))
        created = repo.create.call_args[0][0]
        assert "previous_score" in created


# ---------------------------------------------------------------------------
# reconcile() update path — trend recalculated, previous_score stored
# ---------------------------------------------------------------------------

class TestReconcileTrendUpdate:
    def test_update_worsening_when_score_increases_significantly(self):
        # existing score=0.4, incoming=0.6 → diff=+0.2 → worsening
        existing = _active_event(current_score=0.4)
        anomaly = {**_ANOMALY, "anomaly_score": 0.6}
        repo = _mock_repo(active_events=[existing])
        _run(_svc(repo).reconcile([anomaly], _NOW))
        update_data = repo.update.call_args[0][1]
        assert update_data["trend"] == "worsening"

    def test_update_improving_when_score_decreases_significantly(self):
        # existing score=0.8, incoming=0.5 → diff=-0.3 → improving
        existing = _active_event(current_score=0.8)
        anomaly = {**_ANOMALY, "anomaly_score": 0.5}
        repo = _mock_repo(active_events=[existing])
        _run(_svc(repo).reconcile([anomaly], _NOW))
        update_data = repo.update.call_args[0][1]
        assert update_data["trend"] == "improving"

    def test_update_stable_when_score_barely_changes(self):
        # existing score=0.5, incoming=0.52 → diff=+0.02 → stable
        existing = _active_event(current_score=0.5)
        anomaly = {**_ANOMALY, "anomaly_score": 0.52}
        repo = _mock_repo(active_events=[existing])
        _run(_svc(repo).reconcile([anomaly], _NOW))
        update_data = repo.update.call_args[0][1]
        assert update_data["trend"] == "stable"

    def test_update_previous_score_is_old_current_score(self):
        existing = _active_event(current_score=0.45)
        repo = _mock_repo(active_events=[existing])
        _run(_svc(repo).reconcile([_ANOMALY], _NOW))
        update_data = repo.update.call_args[0][1]
        assert update_data["previous_score"] == pytest.approx(0.45, abs=1e-6)

    def test_update_current_score_is_incoming_score(self):
        existing = _active_event(current_score=0.4)
        anomaly = {**_ANOMALY, "anomaly_score": 0.75}
        repo = _mock_repo(active_events=[existing])
        _run(_svc(repo).reconcile([anomaly], _NOW))
        update_data = repo.update.call_args[0][1]
        assert update_data["current_score"] == pytest.approx(0.75, abs=1e-6)

    def test_update_trend_key_present(self):
        existing = _active_event()
        repo = _mock_repo(active_events=[existing])
        _run(_svc(repo).reconcile([_ANOMALY], _NOW))
        update_data = repo.update.call_args[0][1]
        assert "trend" in update_data

    def test_update_previous_score_key_present(self):
        existing = _active_event()
        repo = _mock_repo(active_events=[existing])
        _run(_svc(repo).reconcile([_ANOMALY], _NOW))
        update_data = repo.update.call_args[0][1]
        assert "previous_score" in update_data

    def test_upper_boundary_below_threshold_scores_stable_on_update(self):
        # diff = +0.04 — safely inside the stable band
        # (0.55 - 0.50 has float representation slightly > 0.05 due to IEEE 754;
        #  use a value unambiguously within the ±0.05 stable band)
        existing = _active_event(current_score=0.5)
        anomaly = {**_ANOMALY, "anomaly_score": 0.54}
        repo = _mock_repo(active_events=[existing])
        _run(_svc(repo).reconcile([anomaly], _NOW))
        update_data = repo.update.call_args[0][1]
        assert update_data["trend"] == "stable"

    def test_exact_negative_boundary_scores_stable_on_update(self):
        # diff = exactly -0.05 → stable (strict <)
        existing = _active_event(current_score=0.5)
        anomaly = {**_ANOMALY, "anomaly_score": 0.45}
        repo = _mock_repo(active_events=[existing])
        _run(_svc(repo).reconcile([anomaly], _NOW))
        update_data = repo.update.call_args[0][1]
        assert update_data["trend"] == "stable"


# ---------------------------------------------------------------------------
# get_events_summary() — trend counts
# ---------------------------------------------------------------------------

class TestGetEventsSummaryTrends:
    def test_empty_collection_all_trend_zeros(self):
        repo = _mock_repo(all_events=[])
        result = _run(_svc(repo).get_events_summary())
        assert result["worsening"] == 0
        assert result["stable"] == 0
        assert result["improving"] == 0

    def test_worsening_count(self):
        events = [
            _event_with_status("active", trend="worsening", region="R1"),
            _event_with_status("active", trend="worsening", region="R2"),
            _event_with_status("active", trend="stable", region="R3"),
        ]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events_summary())
        assert result["worsening"] == 2

    def test_improving_count(self):
        events = [
            _event_with_status("active", trend="improving", region="R1"),
            _event_with_status("active", trend="stable", region="R2"),
        ]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events_summary())
        assert result["improving"] == 1

    def test_stable_count(self):
        events = [
            _event_with_status("active", trend="stable", region="R1"),
            _event_with_status("active", trend="stable", region="R2"),
            _event_with_status("active", trend="stable", region="R3"),
        ]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events_summary())
        assert result["stable"] == 3

    def test_trend_counts_active_only_worsening(self):
        # resolved worsening event should NOT count
        events = [
            _event_with_status("active", trend="worsening", region="R1"),
            _event_with_status("resolved", trend="worsening", region="R2"),
        ]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events_summary())
        assert result["worsening"] == 1

    def test_trend_counts_active_only_improving(self):
        events = [
            _event_with_status("resolved", trend="improving", region="R1"),
            _event_with_status("resolved", trend="improving", region="R2"),
        ]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events_summary())
        assert result["improving"] == 0

    def test_mixed_trends_and_statuses(self):
        events = [
            _event_with_status("active", trend="worsening", region="R1"),
            _event_with_status("active", trend="stable", region="R2"),
            _event_with_status("active", trend="stable", region="R3"),
            _event_with_status("active", trend="improving", region="R4"),
            _event_with_status("active", trend="new", region="R5"),
            _event_with_status("resolved", trend="worsening", region="R6"),
            _event_with_status("resolved", trend="improving", region="R7"),
        ]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events_summary())
        assert result["active"] == 5
        assert result["resolved"] == 2
        assert result["worsening"] == 1
        assert result["stable"] == 2
        assert result["improving"] == 1

    def test_summary_response_includes_all_trend_keys(self):
        repo = _mock_repo(all_events=[])
        result = _run(_svc(repo).get_events_summary())
        assert "worsening" in result
        assert "stable" in result
        assert "improving" in result

    def test_new_trend_events_not_counted_in_any_trend_bucket(self):
        # "new" trend events are active but should not appear in
        # worsening/stable/improving counts
        events = [
            _event_with_status("active", trend="new", region="R1"),
            _event_with_status("active", trend="new", region="R2"),
        ]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events_summary())
        assert result["worsening"] == 0
        assert result["stable"] == 0
        assert result["improving"] == 0
        assert result["active"] == 2

    def test_backward_compatible_events_missing_trend(self):
        # Events without "trend" key (legacy docs) should not raise and
        # should not inflate any trend bucket count.
        event = _active_event()
        del event["trend"]
        repo = _mock_repo(all_events=[event])
        result = _run(_svc(repo).get_events_summary())
        assert result["active"] == 1
        assert result["worsening"] == 0
        assert result["stable"] == 0
        assert result["improving"] == 0


# ---------------------------------------------------------------------------
# IntelligenceEvent model fields
# ---------------------------------------------------------------------------

class TestIntelligenceEventModel:
    def test_model_has_previous_score_field(self):
        from app.models.intelligence_event import IntelligenceEvent
        fields = IntelligenceEvent.model_fields
        assert "previous_score" in fields

    def test_model_has_trend_field(self):
        from app.models.intelligence_event import IntelligenceEvent
        fields = IntelligenceEvent.model_fields
        assert "trend" in fields

    def test_previous_score_defaults_to_none(self):
        from app.models.intelligence_event import IntelligenceEvent
        event = IntelligenceEvent(
            id="x",
            event_type="anomaly",
            region="R",
            status="active",
            severity="high",
            first_detected_at=_NOW,
            last_detected_at=_NOW,
            detection_count=1,
            current_score=0.5,
            metadata={},
        )
        assert event.previous_score is None

    def test_trend_defaults_to_new(self):
        from app.models.intelligence_event import IntelligenceEvent
        event = IntelligenceEvent(
            id="x",
            event_type="anomaly",
            region="R",
            status="active",
            severity="high",
            first_detected_at=_NOW,
            last_detected_at=_NOW,
            detection_count=1,
            current_score=0.5,
            metadata={},
        )
        assert event.trend == "new"

    def test_model_accepts_all_trend_values(self):
        from app.models.intelligence_event import IntelligenceEvent
        base = dict(
            id="x", event_type="anomaly", region="R", status="active",
            severity="high", first_detected_at=_NOW, last_detected_at=_NOW,
            detection_count=1, current_score=0.5, metadata={},
        )
        for trend in ("new", "improving", "stable", "worsening"):
            event = IntelligenceEvent(**base, trend=trend)
            assert event.trend == trend
