"""Unit tests for Intelligence Priority Scoring.

Surface under test:
    _compute_priority_score(severity, escalation_level, trend, current_score)
    IntelligenceEventsService.reconcile()  — priority_score set on create/update
    IntelligenceEventsService.get_events() — active events sorted by priority DESC
    IntelligenceEventsService.get_events_summary() — highest_priority_score/region
    IntelligenceEvent model — priority_score field

Design:
    - All tests mock the repository layer; no MongoDB connection needed.
    - Formula correctness is verified with manual arithmetic.
    - Sorting tests use events with deliberately different priority scores.
    - Backward-compatibility tests confirm old docs without priority_score are safe.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.analytics.intelligence_events_service import (
    IntelligenceEventsService,
    _compute_priority_score,
)

# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 13, 21, 0, 0, tzinfo=timezone.utc)


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
    escalation_level: str = "normal",
    trend: str = "new",
    previous_score: float | None = None,
    current_score: float = 0.60,
    priority_score: float = 0.0,
    offset_hours: int = 0,
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
        "priority_score": priority_score,
        "first_detected_at": _NOW,
        "last_detected_at": _NOW + timedelta(hours=offset_hours),
        "detection_count": detection_count,
        "current_score": current_score,
        "metadata": {},
    }


def _anomaly(
    region: str = "Carpathian Forest",
    severity: str = "high",
    anomaly_score: float = 0.60,
) -> dict:
    return {
        "region": region,
        "baseline_events": 10,
        "current_events": 30,
        "deviation_percent": 150.0,
        "anomaly_score": anomaly_score,
        "severity": severity,
        "status": "active",
    }


def _run(coro) -> object:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# _compute_priority_score — formula correctness
# ---------------------------------------------------------------------------

class TestComputePriorityScoreFormula:
    def test_maximum_inputs_give_score_one(self):
        # severity=critical(1.0), escalation=critical(1.0),
        # trend=worsening(1.0), score=1.0
        # = 0.40*1.0 + 0.30*1.0 + 0.20*1.0 + 0.10*1.0 = 1.0
        assert _compute_priority_score("critical", "critical", "worsening", 1.0) == pytest.approx(1.0, abs=1e-4)

    def test_known_combination_high_persistent_worsening(self):
        # 0.40*0.75 + 0.30*0.60 + 0.20*1.00 + 0.10*0.80
        # = 0.30 + 0.18 + 0.20 + 0.08 = 0.76
        result = _compute_priority_score("high", "persistent", "worsening", 0.80)
        assert result == pytest.approx(0.76, abs=1e-4)

    def test_known_combination_medium_normal_stable(self):
        # 0.40*0.50 + 0.30*0.25 + 0.20*0.50 + 0.10*0.50
        # = 0.20 + 0.075 + 0.10 + 0.05 = 0.425
        result = _compute_priority_score("medium", "normal", "stable", 0.50)
        assert result == pytest.approx(0.425, abs=1e-4)

    def test_known_combination_low_normal_improving(self):
        # 0.40*0.25 + 0.30*0.25 + 0.20*0.20 + 0.10*0.0
        # = 0.10 + 0.075 + 0.04 + 0.0 = 0.215
        result = _compute_priority_score("low", "normal", "improving", 0.0)
        assert result == pytest.approx(0.215, abs=1e-4)

    def test_result_is_rounded_to_4_decimals(self):
        # Any result should have at most 4 decimal places
        result = _compute_priority_score("medium", "normal", "stable", 0.333)
        assert result == round(result, 4)

    def test_result_between_0_and_1(self):
        for severity in ("low", "medium", "high", "critical"):
            for escalation in ("normal", "persistent", "critical"):
                for trend in ("improving", "stable", "worsening", "new"):
                    score = _compute_priority_score(severity, escalation, trend, 0.5)
                    assert 0.0 <= score <= 1.0, (
                        f"Out of range for {severity}/{escalation}/{trend}: {score}"
                    )


# ---------------------------------------------------------------------------
# _compute_priority_score — individual dimension influence
# ---------------------------------------------------------------------------

class TestComputePriorityScoreSeverityInfluence:
    """Higher severity → higher priority (all other inputs held constant)."""

    def _score(self, severity: str) -> float:
        return _compute_priority_score(severity, "normal", "stable", 0.5)

    def test_critical_higher_than_high(self):
        assert self._score("critical") > self._score("high")

    def test_high_higher_than_medium(self):
        assert self._score("high") > self._score("medium")

    def test_medium_higher_than_low(self):
        assert self._score("medium") > self._score("low")


class TestComputePriorityScoreEscalationInfluence:
    """Higher escalation → higher priority (all other inputs held constant)."""

    def _score(self, escalation: str) -> float:
        return _compute_priority_score("medium", escalation, "stable", 0.5)

    def test_critical_higher_than_persistent(self):
        assert self._score("critical") > self._score("persistent")

    def test_persistent_higher_than_normal(self):
        assert self._score("persistent") > self._score("normal")


class TestComputePriorityScoreTrendInfluence:
    """Worsening trend → highest urgency; improving → lowest."""

    def _score(self, trend: str) -> float:
        return _compute_priority_score("medium", "normal", trend, 0.5)

    def test_worsening_highest_trend_score(self):
        assert self._score("worsening") > self._score("new")
        assert self._score("worsening") > self._score("stable")
        assert self._score("worsening") > self._score("improving")

    def test_improving_lowest_trend_score(self):
        assert self._score("improving") < self._score("new")
        assert self._score("improving") < self._score("stable")

    def test_new_higher_than_stable(self):
        assert self._score("new") > self._score("stable")


class TestComputePriorityScoreCurrentScoreInfluence:
    """Higher current_score → slightly higher priority (0.10 weight)."""

    def test_higher_current_score_increases_priority(self):
        low = _compute_priority_score("medium", "normal", "stable", 0.0)
        high = _compute_priority_score("medium", "normal", "stable", 1.0)
        assert high > low

    def test_current_score_delta_matches_weight(self):
        s0 = _compute_priority_score("medium", "normal", "stable", 0.0)
        s1 = _compute_priority_score("medium", "normal", "stable", 1.0)
        # 0.10 weight × (1.0 - 0.0) = 0.10 difference
        assert (s1 - s0) == pytest.approx(0.10, abs=1e-4)


class TestComputePriorityScoreUnknownKeys:
    """Unknown keys fall back to 0.0 weight (graceful degradation)."""

    def test_unknown_severity_gives_zero_contribution(self):
        result = _compute_priority_score("unknown", "normal", "stable", 0.5)
        expected = 0.40 * 0.0 + 0.30 * 0.25 + 0.20 * 0.50 + 0.10 * 0.5
        assert result == pytest.approx(expected, abs=1e-4)

    def test_unknown_escalation_gives_zero_contribution(self):
        result = _compute_priority_score("medium", "unknown", "stable", 0.5)
        expected = 0.40 * 0.50 + 0.30 * 0.0 + 0.20 * 0.50 + 0.10 * 0.5
        assert result == pytest.approx(expected, abs=1e-4)

    def test_unknown_trend_gives_zero_contribution(self):
        result = _compute_priority_score("medium", "normal", "unknown", 0.5)
        expected = 0.40 * 0.50 + 0.30 * 0.25 + 0.20 * 0.0 + 0.10 * 0.5
        assert result == pytest.approx(expected, abs=1e-4)


# ---------------------------------------------------------------------------
# reconcile() create path — priority_score initialised
# ---------------------------------------------------------------------------

class TestReconcilePriorityCreate:
    def test_priority_score_key_present_on_create(self):
        repo = _mock_repo(active_events=[])
        _run(_svc(repo).reconcile([_anomaly()], _NOW))
        created = repo.create.call_args[0][0]
        assert "priority_score" in created

    def test_priority_score_uses_computed_escalation_and_new_trend(self):
        # New event: escalation = _compute_escalation_level(1, "high") = "normal"
        #            trend = "new"
        # Expected: 0.40*0.75 + 0.30*0.25 + 0.20*0.60 + 0.10*0.60
        #         = 0.30 + 0.075 + 0.12 + 0.06 = 0.555
        repo = _mock_repo(active_events=[])
        _run(_svc(repo).reconcile([_anomaly(severity="high", anomaly_score=0.60)], _NOW))
        created = repo.create.call_args[0][0]
        assert created["priority_score"] == pytest.approx(0.555, abs=1e-4)

    def test_priority_score_for_critical_severity_new_event(self):
        # escalation = _compute_escalation_level(1, "critical") = "persistent"
        # trend = "new"
        # 0.40*1.0 + 0.30*0.60 + 0.20*0.60 + 0.10*0.9
        # = 0.40 + 0.18 + 0.12 + 0.09 = 0.79
        repo = _mock_repo(active_events=[])
        _run(_svc(repo).reconcile([_anomaly(severity="critical", anomaly_score=0.9)], _NOW))
        created = repo.create.call_args[0][0]
        assert created["priority_score"] == pytest.approx(0.79, abs=1e-4)

    def test_priority_score_is_float(self):
        repo = _mock_repo(active_events=[])
        _run(_svc(repo).reconcile([_anomaly()], _NOW))
        created = repo.create.call_args[0][0]
        assert isinstance(created["priority_score"], float)


# ---------------------------------------------------------------------------
# reconcile() update path — priority_score recalculated
# ---------------------------------------------------------------------------

class TestReconcilePriorityUpdate:
    def test_priority_score_key_present_on_update(self):
        existing = _active_event(current_score=0.5)
        repo = _mock_repo(active_events=[existing])
        _run(_svc(repo).reconcile([_anomaly()], _NOW))
        update_data = repo.update.call_args[0][1]
        assert "priority_score" in update_data

    def test_priority_score_uses_new_escalation_and_trend(self):
        # existing count=2, incoming count=3 → escalation="persistent"
        # existing score=0.4, incoming=0.7 → diff=+0.3 → trend="worsening"
        # severity="high"
        # 0.40*0.75 + 0.30*0.60 + 0.20*1.00 + 0.10*0.7
        # = 0.30 + 0.18 + 0.20 + 0.07 = 0.75
        existing = _active_event(detection_count=2, current_score=0.4, severity="high")
        anomaly = _anomaly(severity="high", anomaly_score=0.7)
        repo = _mock_repo(active_events=[existing])
        _run(_svc(repo).reconcile([anomaly], _NOW))
        update_data = repo.update.call_args[0][1]
        assert update_data["priority_score"] == pytest.approx(0.75, abs=1e-4)

    def test_improving_trend_lowers_priority_vs_new(self):
        # New event: trend="new" — update event: trend="improving"
        # All else equal, "new"(0.60) > "improving"(0.20) weight → lower priority
        existing_new = _active_event(region="R1", event_id="e1", current_score=0.7, detection_count=1)
        existing_update = _active_event(region="R2", event_id="e2", current_score=0.7, detection_count=1)

        # R1: create path → trend="new"
        repo1 = _mock_repo(active_events=[])
        _run(_svc(repo1).reconcile([_anomaly(region="R1", anomaly_score=0.7)], _NOW))
        new_score = repo1.create.call_args[0][0]["priority_score"]

        # R2: update path, score stays same → trend="stable"
        repo2 = _mock_repo(active_events=[existing_update])
        _run(_svc(repo2).reconcile([_anomaly(region="R2", anomaly_score=0.7)], _NOW))
        update_score = repo2.update.call_args[0][1]["priority_score"]

        # "new" weight(0.60) > "stable" weight(0.50), so new path gives higher score
        assert new_score > update_score

    def test_priority_score_is_float_on_update(self):
        existing = _active_event()
        repo = _mock_repo(active_events=[existing])
        _run(_svc(repo).reconcile([_anomaly()], _NOW))
        update_data = repo.update.call_args[0][1]
        assert isinstance(update_data["priority_score"], float)


# ---------------------------------------------------------------------------
# get_events() — active events sorted by priority DESC, then last_detected_at DESC
# ---------------------------------------------------------------------------

class TestGetEventsSorting:
    def test_active_events_sorted_by_priority_desc(self):
        events = [
            {**_active_event(region="R1", priority_score=0.30), "status": "active"},
            {**_active_event(region="R2", priority_score=0.90), "status": "active"},
            {**_active_event(region="R3", priority_score=0.60), "status": "active"},
        ]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events())
        priorities = [e["priority_score"] for e in result["active"]]
        assert priorities == sorted(priorities, reverse=True)

    def test_first_active_event_has_highest_priority(self):
        events = [
            {**_active_event(region="Low", priority_score=0.20), "status": "active"},
            {**_active_event(region="High", priority_score=0.95), "status": "active"},
            {**_active_event(region="Mid", priority_score=0.55), "status": "active"},
        ]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events())
        assert result["active"][0]["region"] == "High"

    def test_tiebreak_by_last_detected_at_desc(self):
        # Same priority score; more recent event should come first
        events = [
            {**_active_event(region="Older", priority_score=0.70, offset_hours=0), "status": "active"},
            {**_active_event(region="Newer", priority_score=0.70, offset_hours=2), "status": "active"},
        ]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events())
        assert result["active"][0]["region"] == "Newer"

    def test_resolved_events_not_re_sorted(self):
        # Resolved events keep their original repository order (most-recent-first)
        resolved_first = {
            **_active_event(region="R_recent", priority_score=0.10, offset_hours=5),
            "status": "resolved",
            "resolved_at": _NOW,
        }
        resolved_second = {
            **_active_event(region="R_old", priority_score=0.90, offset_hours=0),
            "status": "resolved",
            "resolved_at": _NOW,
        }
        # Repository returns them in this order; service must NOT re-sort resolved
        repo = _mock_repo(all_events=[resolved_first, resolved_second])
        result = _run(_svc(repo).get_events())
        assert result["resolved"][0]["region"] == "R_recent"
        assert result["resolved"][1]["region"] == "R_old"

    def test_empty_active_returns_empty_list(self):
        repo = _mock_repo(all_events=[])
        result = _run(_svc(repo).get_events())
        assert result["active"] == []

    def test_single_active_event_returned_correctly(self):
        events = [{**_active_event(region="Solo", priority_score=0.55), "status": "active"}]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events())
        assert len(result["active"]) == 1
        assert result["active"][0]["region"] == "Solo"

    def test_backward_compat_events_without_priority_score_sort_last(self):
        event_no_score = _active_event(region="Legacy")
        del event_no_score["priority_score"]
        event_with_score = _active_event(region="Modern", priority_score=0.50)
        event_no_score["status"] = "active"
        event_with_score["status"] = "active"
        repo = _mock_repo(all_events=[event_no_score, event_with_score])
        result = _run(_svc(repo).get_events())
        assert result["active"][0]["region"] == "Modern"


# ---------------------------------------------------------------------------
# get_events_summary() — highest_priority_score and highest_priority_region
# ---------------------------------------------------------------------------

class TestGetEventsSummaryPriority:
    def test_empty_active_gives_none_priority_fields(self):
        repo = _mock_repo(all_events=[])
        result = _run(_svc(repo).get_events_summary())
        assert result["highest_priority_score"] is None
        assert result["highest_priority_region"] is None

    def test_highest_priority_score_is_max_of_active(self):
        events = [
            {**_active_event(region="R1", priority_score=0.40), "status": "active"},
            {**_active_event(region="R2", priority_score=0.85), "status": "active"},
            {**_active_event(region="R3", priority_score=0.60), "status": "active"},
        ]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events_summary())
        assert result["highest_priority_score"] == pytest.approx(0.85, abs=1e-4)

    def test_highest_priority_region_matches_score(self):
        events = [
            {**_active_event(region="Carpathian", priority_score=0.40), "status": "active"},
            {**_active_event(region="Dobrogea", priority_score=0.95), "status": "active"},
        ]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events_summary())
        assert result["highest_priority_region"] == "Dobrogea"

    def test_resolved_events_excluded_from_priority_fields(self):
        # Resolved event has higher score — must NOT appear in highest
        active_event = {**_active_event(region="Active", priority_score=0.40), "status": "active"}
        resolved_event = {
            **_active_event(region="Resolved", priority_score=0.99),
            "status": "resolved",
            "resolved_at": _NOW,
        }
        repo = _mock_repo(all_events=[active_event, resolved_event])
        result = _run(_svc(repo).get_events_summary())
        assert result["highest_priority_score"] == pytest.approx(0.40, abs=1e-4)
        assert result["highest_priority_region"] == "Active"

    def test_summary_has_priority_fields(self):
        repo = _mock_repo(all_events=[])
        result = _run(_svc(repo).get_events_summary())
        assert "highest_priority_score" in result
        assert "highest_priority_region" in result

    def test_single_active_event_is_highest(self):
        events = [{**_active_event(region="Solo", priority_score=0.73), "status": "active"}]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events_summary())
        assert result["highest_priority_score"] == pytest.approx(0.73, abs=1e-4)
        assert result["highest_priority_region"] == "Solo"

    def test_backward_compat_events_without_priority_score(self):
        # Legacy events without priority_score default to 0.0
        event = _active_event(region="Legacy")
        del event["priority_score"]
        event["status"] = "active"
        repo = _mock_repo(all_events=[event])
        result = _run(_svc(repo).get_events_summary())
        assert result["highest_priority_score"] == pytest.approx(0.0, abs=1e-4)
        assert result["highest_priority_region"] == "Legacy"


# ---------------------------------------------------------------------------
# IntelligenceEvent model — priority_score field
# ---------------------------------------------------------------------------

class TestIntelligenceEventModelPriority:
    def test_model_has_priority_score_field(self):
        from app.models.intelligence_event import IntelligenceEvent
        assert "priority_score" in IntelligenceEvent.model_fields

    def test_priority_score_defaults_to_zero(self):
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
        assert event.priority_score == 0.0

    def test_model_accepts_priority_score(self):
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
            priority_score=0.76,
            metadata={},
        )
        assert event.priority_score == pytest.approx(0.76, abs=1e-6)
