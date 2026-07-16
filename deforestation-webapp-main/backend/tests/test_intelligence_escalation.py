"""Unit tests for Intelligence Event Escalation.

Surface under test:
    _compute_escalation_level(detection_count, severity)  — pure function
    IntelligenceEventsService.reconcile()  — escalation_level set on create/update
    IntelligenceEventsService.get_events_summary()  — aggregate counts
    GET /analytics/intelligence/events/summary  (route registration)

Design:
    - All tests mock the repository layer; no MongoDB connection needed.
    - Pure-logic assertions are made directly against _compute_escalation_level.
    - reconcile() tests inspect the dict passed to repo.create / repo.update.
    - get_events_summary() tests supply synthetic event lists via the repo mock.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.analytics.intelligence_events_service import (
    IntelligenceEventsService,
    _compute_escalation_level,
)

# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 6, 13, 20, 0, 0, tzinfo=timezone.utc)

_ANOMALY_HIGH = {
    "region": "Carpathian Forest",
    "baseline_events": 10,
    "current_events": 30,
    "deviation_percent": 150.0,
    "anomaly_score": 0.69,
    "severity": "high",
    "status": "active",
}

_ANOMALY_CRITICAL = {
    "region": "Dobrogea",
    "baseline_events": 5,
    "current_events": 25,
    "deviation_percent": 400.0,
    "anomaly_score": 0.91,
    "severity": "critical",
    "status": "active",
}

_ANOMALY_MEDIUM = {
    "region": "Transylvania",
    "baseline_events": 8,
    "current_events": 20,
    "deviation_percent": 150.0,
    "anomaly_score": 0.55,
    "severity": "medium",
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
    escalation_level: str = "normal",
    current_score: float = 0.69,
) -> dict:
    return {
        "id": event_id,
        "event_type": "anomaly",
        "region": region,
        "status": "active",
        "severity": severity,
        "escalation_level": escalation_level,
        "first_detected_at": _NOW,
        "last_detected_at": _NOW,
        "detection_count": detection_count,
        "current_score": current_score,
        "metadata": {},
    }


def _event_with_status(
    status: str,
    escalation_level: str = "normal",
    region: str = "R",
) -> dict:
    base = _active_event(region=region, escalation_level=escalation_level)
    base["status"] = status
    if status == "resolved":
        base["resolved_at"] = _NOW
    return base


def _run(coro) -> object:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# _compute_escalation_level — normal thresholds
# ---------------------------------------------------------------------------

class TestComputeEscalationLevelNormal:
    def test_count_1_medium_is_normal(self):
        assert _compute_escalation_level(1, "medium") == "normal"

    def test_count_2_low_is_normal(self):
        assert _compute_escalation_level(2, "low") == "normal"

    def test_count_2_high_is_normal(self):
        assert _compute_escalation_level(2, "high") == "normal"

    def test_count_0_medium_is_normal(self):
        assert _compute_escalation_level(0, "medium") == "normal"


# ---------------------------------------------------------------------------
# _compute_escalation_level — persistent threshold (Rule A)
# ---------------------------------------------------------------------------

class TestComputeEscalationLevelPersistent:
    def test_count_3_medium_is_persistent(self):
        # Rule A boundary
        assert _compute_escalation_level(3, "medium") == "persistent"

    def test_count_4_low_is_persistent(self):
        assert _compute_escalation_level(4, "low") == "persistent"

    def test_count_5_high_is_persistent(self):
        assert _compute_escalation_level(5, "high") == "persistent"

    def test_count_6_medium_is_persistent(self):
        # Just below critical threshold
        assert _compute_escalation_level(6, "medium") == "persistent"


# ---------------------------------------------------------------------------
# _compute_escalation_level — critical threshold (Rule B)
# ---------------------------------------------------------------------------

class TestComputeEscalationLevelCritical:
    def test_count_7_low_is_critical(self):
        # Rule B boundary
        assert _compute_escalation_level(7, "low") == "critical"

    def test_count_8_medium_is_critical(self):
        assert _compute_escalation_level(8, "medium") == "critical"

    def test_count_10_high_is_critical(self):
        assert _compute_escalation_level(10, "high") == "critical"

    def test_count_7_high_is_critical(self):
        assert _compute_escalation_level(7, "high") == "critical"


# ---------------------------------------------------------------------------
# _compute_escalation_level — severity override (Rule C)
# ---------------------------------------------------------------------------

class TestComputeEscalationLevelSeverityOverride:
    def test_severity_critical_count_1_is_persistent(self):
        # Rule C: critical severity is always >= persistent
        assert _compute_escalation_level(1, "critical") == "persistent"

    def test_severity_critical_count_2_is_persistent(self):
        assert _compute_escalation_level(2, "critical") == "persistent"

    def test_severity_critical_count_3_is_persistent(self):
        # Rule A also applies; both A and C → persistent
        assert _compute_escalation_level(3, "critical") == "persistent"

    def test_severity_critical_count_7_is_critical(self):
        # Rule B supersedes Rule C — critical level reached by count
        assert _compute_escalation_level(7, "critical") == "critical"

    def test_severity_critical_count_8_is_critical(self):
        assert _compute_escalation_level(8, "critical") == "critical"

    def test_severity_high_count_1_is_normal(self):
        # "high" severity does NOT trigger Rule C — only "critical" does
        assert _compute_escalation_level(1, "high") == "normal"

    def test_severity_low_count_2_is_normal(self):
        assert _compute_escalation_level(2, "low") == "normal"


# ---------------------------------------------------------------------------
# reconcile() create path — escalation_level initialised
# ---------------------------------------------------------------------------

class TestReconcileEscalationCreate:
    def test_new_event_normal_severity_gets_normal_escalation(self):
        repo = _mock_repo(active_events=[])
        _run(_svc(repo).reconcile([_ANOMALY_HIGH], _NOW))
        created = repo.create.call_args[0][0]
        assert created["escalation_level"] == "normal"

    def test_new_critical_severity_event_gets_persistent_escalation(self):
        repo = _mock_repo(active_events=[])
        _run(_svc(repo).reconcile([_ANOMALY_CRITICAL], _NOW))
        created = repo.create.call_args[0][0]
        assert created["escalation_level"] == "persistent"

    def test_new_medium_severity_event_gets_normal_escalation(self):
        repo = _mock_repo(active_events=[])
        _run(_svc(repo).reconcile([_ANOMALY_MEDIUM], _NOW))
        created = repo.create.call_args[0][0]
        assert created["escalation_level"] == "normal"

    def test_escalation_level_key_present_on_create(self):
        repo = _mock_repo(active_events=[])
        _run(_svc(repo).reconcile([_ANOMALY_HIGH], _NOW))
        created = repo.create.call_args[0][0]
        assert "escalation_level" in created


# ---------------------------------------------------------------------------
# reconcile() update path — escalation_level recalculated
# ---------------------------------------------------------------------------

class TestReconcileEscalationUpdate:
    def test_count_2_to_3_becomes_persistent(self):
        # existing detection_count=2 → after update detection_count=3 → persistent
        existing = _active_event(region="Carpathian Forest", detection_count=2, severity="medium")
        repo = _mock_repo(active_events=[existing])
        _run(_svc(repo).reconcile([_ANOMALY_HIGH], _NOW))
        update_data = repo.update.call_args[0][1]
        assert update_data["detection_count"] == 3
        assert update_data["escalation_level"] == "persistent"

    def test_count_6_to_7_becomes_critical(self):
        # existing detection_count=6 → after update detection_count=7 → critical
        existing = _active_event(region="Carpathian Forest", detection_count=6, severity="high")
        repo = _mock_repo(active_events=[existing])
        _run(_svc(repo).reconcile([_ANOMALY_HIGH], _NOW))
        update_data = repo.update.call_args[0][1]
        assert update_data["detection_count"] == 7
        assert update_data["escalation_level"] == "critical"

    def test_critical_severity_count_1_gets_persistent_on_update(self):
        # existing count=0 anomaly with critical severity → new count=1 → persistent
        existing = _active_event(region="Dobrogea", detection_count=0, severity="critical")
        repo = _mock_repo(active_events=[existing])
        _run(_svc(repo).reconcile([_ANOMALY_CRITICAL], _NOW))
        update_data = repo.update.call_args[0][1]
        assert update_data["escalation_level"] == "persistent"

    def test_escalation_level_key_present_on_update(self):
        existing = _active_event(detection_count=1)
        repo = _mock_repo(active_events=[existing])
        _run(_svc(repo).reconcile([_ANOMALY_HIGH], _NOW))
        update_data = repo.update.call_args[0][1]
        assert "escalation_level" in update_data

    def test_escalation_level_uses_new_count_not_old(self):
        # Count 2 → 3 triggers persistent; ensure new count is used, not old (2=normal)
        existing = _active_event(detection_count=2, severity="low")
        repo = _mock_repo(active_events=[existing])
        _run(_svc(repo).reconcile([_ANOMALY_HIGH], _NOW))
        update_data = repo.update.call_args[0][1]
        assert update_data["escalation_level"] == "persistent"
        assert update_data["escalation_level"] != "normal"

    def test_count_stays_normal_below_threshold(self):
        # Existing count=1 → new count=2 → still normal
        existing = _active_event(detection_count=1, severity="medium")
        repo = _mock_repo(active_events=[existing])
        _run(_svc(repo).reconcile([_ANOMALY_HIGH], _NOW))
        update_data = repo.update.call_args[0][1]
        assert update_data["escalation_level"] == "normal"


# ---------------------------------------------------------------------------
# get_events_summary() — aggregate counts
# ---------------------------------------------------------------------------

class TestGetEventsSummary:
    def test_empty_collection_returns_zeros(self):
        repo = _mock_repo(all_events=[])
        result = _run(_svc(repo).get_events_summary())
        assert result["active"] == 0
        assert result["resolved"] == 0
        assert result["persistent"] == 0
        assert result["critical"] == 0

    def test_active_count(self):
        events = [
            _event_with_status("active", escalation_level="normal", region="R1"),
            _event_with_status("active", escalation_level="normal", region="R2"),
            _event_with_status("resolved", region="R3"),
        ]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events_summary())
        assert result["active"] == 2

    def test_resolved_count(self):
        events = [
            _event_with_status("active", region="R1"),
            _event_with_status("resolved", region="R2"),
            _event_with_status("resolved", region="R3"),
            _event_with_status("resolved", region="R4"),
        ]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events_summary())
        assert result["resolved"] == 3

    def test_persistent_count_active_only(self):
        events = [
            _event_with_status("active", escalation_level="persistent", region="R1"),
            _event_with_status("active", escalation_level="persistent", region="R2"),
            _event_with_status("resolved", escalation_level="persistent", region="R3"),
        ]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events_summary())
        # Only active persistent events counted; resolved persistent NOT included
        assert result["persistent"] == 2

    def test_critical_count_active_only(self):
        events = [
            _event_with_status("active", escalation_level="critical", region="R1"),
            _event_with_status("resolved", escalation_level="critical", region="R2"),
            _event_with_status("resolved", escalation_level="critical", region="R3"),
        ]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events_summary())
        assert result["critical"] == 1

    def test_mixed_escalation_levels(self):
        events = [
            _event_with_status("active", escalation_level="normal", region="R1"),
            _event_with_status("active", escalation_level="persistent", region="R2"),
            _event_with_status("active", escalation_level="persistent", region="R3"),
            _event_with_status("active", escalation_level="critical", region="R4"),
            _event_with_status("resolved", region="R5"),
            _event_with_status("resolved", region="R6"),
        ]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events_summary())
        assert result["active"] == 4
        assert result["resolved"] == 2
        assert result["persistent"] == 2
        assert result["critical"] == 1

    def test_all_normal_escalation_gives_zero_persistent_critical(self):
        events = [
            _event_with_status("active", escalation_level="normal", region="R1"),
            _event_with_status("active", escalation_level="normal", region="R2"),
        ]
        repo = _mock_repo(all_events=events)
        result = _run(_svc(repo).get_events_summary())
        assert result["persistent"] == 0
        assert result["critical"] == 0

    def test_summary_response_keys_present(self):
        repo = _mock_repo(all_events=[])
        result = _run(_svc(repo).get_events_summary())
        # Core escalation keys must be present; trend keys added by Event Trend
        # Intelligence are also included but we only assert on what this module owns.
        assert {"active", "resolved", "persistent", "critical"}.issubset(result.keys())

    def test_find_all_called_once(self):
        repo = _mock_repo(all_events=[])
        _run(_svc(repo).get_events_summary())
        repo.find_all.assert_called_once()

    def test_backward_compatible_with_events_missing_escalation(self):
        # Events without escalation_level key (pre-escalation docs) should not raise.
        event = _active_event()
        del event["escalation_level"]  # simulate legacy doc without the field
        repo = _mock_repo(all_events=[event])
        result = _run(_svc(repo).get_events_summary())
        assert result["active"] == 1
        assert result["persistent"] == 0
        assert result["critical"] == 0


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

class TestSummaryRouteRegistration:
    def test_summary_endpoint_registered(self):
        from app.modules.analytics.analytics_routes import router
        paths = [r.path for r in router.routes]
        assert "/analytics/intelligence/events/summary" in paths

    def test_events_endpoint_still_registered(self):
        from app.modules.analytics.analytics_routes import router
        paths = [r.path for r in router.routes]
        assert "/analytics/intelligence/events" in paths

    def test_summary_in_module_info_capabilities(self):
        from app.modules.analytics import module_info
        caps = module_info()["capabilities"]
        assert "intelligence_events_summary" in caps

    def test_summary_in_module_info_endpoints(self):
        from app.modules.analytics import module_info
        endpoints = module_info()["endpoints"]
        assert "/api/analytics/intelligence/events/summary" in endpoints
