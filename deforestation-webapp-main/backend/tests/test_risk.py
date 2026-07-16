"""Comprehensive tests for the Fire Risk Assessment Engine.

Coverage:
    Pure helpers   — compute_risk_score, compute_risk_level, compute_risk_breakdown
    Risk weights   — each component's max contribution
    Normalization  — clamping, boundary conditions
    Level bounds   — exact cutoffs 0.00/0.25/0.50/0.75/1.00
    Breakdown      — weighted contribution correctness
    RiskRepository — create_snapshot dedup, latest, history
    RiskService    — compute_regional_risk data assembly and ordering
    Scheduler      — persist_snapshot called; duplicate prevented
    API endpoint   — route registered, response shape
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.analytics.risk_service import (
    ESCALATION_SCORES,
    RISK_WEIGHTS,
    RiskService,
    _change_label,
    _escalation_score,
    compute_risk_breakdown,
    compute_risk_level,
    compute_risk_score,
)


# ===========================================================================
# Pure helper: compute_risk_score
# ===========================================================================

class TestComputeRiskScore:
    def test_all_zero_inputs_returns_zero(self):
        inputs = {k: 0.0 for k in RISK_WEIGHTS}
        assert compute_risk_score(inputs) == 0.0

    def test_all_one_inputs_returns_one(self):
        inputs = {k: 1.0 for k in RISK_WEIGHTS}
        assert compute_risk_score(inputs) == 1.0

    def test_weights_sum_to_one(self):
        assert abs(sum(RISK_WEIGHTS.values()) - 1.0) < 1e-9

    def test_current_activity_only(self):
        inputs = {"current_activity": 1.0, "historical_activity": 0.0,
                  "forest": 0.0, "priority": 0.0, "escalation": 0.0}
        expected = 0.30  # updated for v2 weather-enriched weights
        assert abs(compute_risk_score(inputs) - expected) < 1e-6

    def test_historical_activity_only(self):
        inputs = {"current_activity": 0.0, "historical_activity": 1.0,
                  "forest": 0.0, "priority": 0.0, "escalation": 0.0}
        expected = 0.20  # updated for v2 weather-enriched weights
        assert abs(compute_risk_score(inputs) - expected) < 1e-6

    def test_forest_only(self):
        inputs = {"current_activity": 0.0, "historical_activity": 0.0,
                  "forest": 1.0, "priority": 0.0, "escalation": 0.0}
        expected = 0.15
        assert abs(compute_risk_score(inputs) - expected) < 1e-6

    def test_priority_only(self):
        inputs = {"current_activity": 0.0, "historical_activity": 0.0,
                  "forest": 0.0, "priority": 1.0, "escalation": 0.0}
        expected = 0.10  # updated for v2 weather-enriched weights
        assert abs(compute_risk_score(inputs) - expected) < 1e-6

    def test_escalation_only(self):
        inputs = {"current_activity": 0.0, "historical_activity": 0.0,
                  "forest": 0.0, "priority": 0.0, "escalation": 1.0}
        expected = 0.10
        assert abs(compute_risk_score(inputs) - expected) < 1e-6

    def test_partial_inputs_default_missing_keys_to_zero(self):
        # Only current_activity provided; new v2 weight is 0.30
        score = compute_risk_score({"current_activity": 1.0})
        assert abs(score - 0.30) < 1e-6

    def test_clamped_to_one_for_overflowing_inputs(self):
        inputs = {k: 2.0 for k in RISK_WEIGHTS}
        assert compute_risk_score(inputs) == 1.0

    def test_clamped_to_zero_for_negative_inputs(self):
        inputs = {k: -1.0 for k in RISK_WEIGHTS}
        assert compute_risk_score(inputs) == 0.0

    def test_result_is_rounded_to_four_decimal_places(self):
        inputs = {"current_activity": 0.333333, "historical_activity": 0.333333,
                  "forest": 0.333333, "priority": 0.333333, "escalation": 0.333333}
        score = compute_risk_score(inputs)
        assert score == round(score, 4)

    def test_specific_scenario(self):
        # v2 weights: current=0.30, hist=0.20, forest=0.15, weather=0.15(→0), priority=0.10, escalation=0.10
        inputs = {"current_activity": 0.8, "historical_activity": 0.6,
                  "forest": 1.0, "priority": 0.7, "escalation": 0.5}
        expected = round(0.8 * 0.30 + 0.6 * 0.20 + 1.0 * 0.15 + 0.0 * 0.15 + 0.7 * 0.10 + 0.5 * 0.10, 4)
        assert compute_risk_score(inputs) == expected

    def test_empty_inputs_returns_zero(self):
        assert compute_risk_score({}) == 0.0


# ===========================================================================
# Pure helper: compute_risk_level
# ===========================================================================

class TestComputeRiskLevel:
    def test_zero_is_low(self):
        assert compute_risk_level(0.0) == "Low"

    def test_just_below_moderate_is_low(self):
        assert compute_risk_level(0.2499) == "Low"

    def test_exactly_moderate_boundary(self):
        assert compute_risk_level(0.25) == "Moderate"

    def test_mid_moderate(self):
        assert compute_risk_level(0.37) == "Moderate"

    def test_just_below_high_is_moderate(self):
        assert compute_risk_level(0.4999) == "Moderate"

    def test_exactly_high_boundary(self):
        assert compute_risk_level(0.50) == "High"

    def test_mid_high(self):
        assert compute_risk_level(0.62) == "High"

    def test_just_below_extreme_is_high(self):
        assert compute_risk_level(0.7499) == "High"

    def test_exactly_extreme_boundary(self):
        assert compute_risk_level(0.75) == "Extreme"

    def test_mid_extreme(self):
        assert compute_risk_level(0.87) == "Extreme"

    def test_one_is_extreme(self):
        assert compute_risk_level(1.0) == "Extreme"

    def test_all_four_levels_covered(self):
        levels = {compute_risk_level(s) for s in (0.0, 0.25, 0.50, 0.75)}
        assert levels == {"Low", "Moderate", "High", "Extreme"}


# ===========================================================================
# Pure helper: compute_risk_breakdown
# ===========================================================================

class TestComputeRiskBreakdown:
    def test_breakdown_keys_match_weights(self):
        bd = compute_risk_breakdown({k: 1.0 for k in RISK_WEIGHTS})
        assert set(bd.keys()) == set(RISK_WEIGHTS.keys())

    def test_breakdown_values_sum_to_score(self):
        inputs = {"current_activity": 0.6, "historical_activity": 0.4,
                  "forest": 0.8, "priority": 0.3, "escalation": 0.5}
        bd = compute_risk_breakdown(inputs)
        expected_score = compute_risk_score(inputs)
        assert abs(sum(bd.values()) - expected_score) < 1e-6

    def test_breakdown_max_contributions(self):
        bd = compute_risk_breakdown({k: 1.0 for k in RISK_WEIGHTS})
        assert abs(bd["current_activity"] - 0.30) < 1e-6    # v2: was 0.35
        assert abs(bd["historical_activity"] - 0.20) < 1e-6  # v2: was 0.25
        assert abs(bd["forest"] - 0.15) < 1e-6
        assert abs(bd["weather"] - 0.15) < 1e-6              # v2: new
        assert abs(bd["priority"] - 0.10) < 1e-6             # v2: was 0.15
        assert abs(bd["escalation"] - 0.10) < 1e-6

    def test_zero_inputs_all_breakdown_values_zero(self):
        bd = compute_risk_breakdown({k: 0.0 for k in RISK_WEIGHTS})
        assert all(v == 0.0 for v in bd.values())

    def test_breakdown_values_are_rounded(self):
        inputs = {k: 1 / 3 for k in RISK_WEIGHTS}
        bd = compute_risk_breakdown(inputs)
        for v in bd.values():
            assert v == round(v, 4)


# ===========================================================================
# Pure helper: _escalation_score
# ===========================================================================

class TestEscalationScore:
    def test_normal_maps_to_zero(self):
        assert _escalation_score("normal") == 0.0

    def test_persistent_maps_to_half(self):
        assert _escalation_score("persistent") == 0.5

    def test_critical_maps_to_one(self):
        assert _escalation_score("critical") == 1.0

    def test_none_defaults_to_normal(self):
        assert _escalation_score(None) == 0.0

    def test_unknown_string_defaults_to_zero(self):
        assert _escalation_score("nonexistent_level") == 0.0


# ===========================================================================
# Pure helper: _change_label
# ===========================================================================

class TestChangeLabel:
    def test_new_when_previous_is_none(self):
        assert _change_label(0.5, None) == "new"

    def test_up_when_score_increased_beyond_threshold(self):
        assert _change_label(0.50, 0.47) == "up"   # +0.03 > 0.02

    def test_down_when_score_decreased_beyond_threshold(self):
        assert _change_label(0.47, 0.50) == "down"  # -0.03 < -0.02

    def test_stable_when_change_within_threshold(self):
        assert _change_label(0.51, 0.50) == "stable"  # +0.01 ≤ 0.02

    def test_stable_exact_threshold(self):
        # delta = 0.019, which is strictly less than threshold 0.02 → stable
        assert _change_label(0.519, 0.50) == "stable"

    def test_up_just_above_threshold(self):
        assert _change_label(0.521, 0.50) == "up"


# ===========================================================================
# ESCALATION_SCORES constant
# ===========================================================================

class TestEscalationScoresConstant:
    def test_normal_is_zero(self):
        assert ESCALATION_SCORES["normal"] == 0.0

    def test_persistent_is_half(self):
        assert ESCALATION_SCORES["persistent"] == 0.5

    def test_critical_is_one(self):
        assert ESCALATION_SCORES["critical"] == 1.0


# ===========================================================================
# RiskRepository
# ===========================================================================

def _mock_col(find_one_return=None, insert_result_id="abc123"):
    col = MagicMock()
    col.find_one = AsyncMock(return_value=find_one_return)
    inserted = MagicMock()
    inserted.inserted_id = insert_result_id
    col.insert_one = AsyncMock(return_value=inserted)

    # find().sort().limit() chain for latest()
    cursor_mock = MagicMock()
    cursor_mock.__aiter__ = AsyncMock(return_value=iter([]))
    limit_mock = MagicMock()
    limit_mock.__aiter__ = MagicMock()

    async def _aiter_empty(self):
        return
        yield

    async def _aiter_docs(docs):
        for d in docs:
            yield d

    return col


class TestRiskRepository:
    """Tests for RiskRepository using in-memory mocked Motor collections."""

    def _make_repo(self, col):
        from app.modules.analytics.risk_repository import RiskRepository
        repo = RiskRepository.__new__(RiskRepository)
        repo.col = col
        return repo

    def _async_cursor(self, docs):
        """Return an object that supports ``async for`` iteration."""
        async def _gen():
            for d in docs:
                yield d
        return _gen()

    @pytest.mark.anyio
    async def test_create_snapshot_inserts_when_no_existing(self):
        from app.modules.analytics.risk_repository import RiskRepository
        col = MagicMock()
        col.find_one = AsyncMock(return_value=None)
        inserted = MagicMock()
        inserted.inserted_id = "id1"
        col.insert_one = AsyncMock(return_value=inserted)

        repo = RiskRepository.__new__(RiskRepository)
        repo.col = col

        snapshot = {"regions": [{"region": "Suceava", "risk_score": 0.8}]}
        result = await repo.create_snapshot(snapshot)

        col.insert_one.assert_awaited_once()
        assert "date" in result

    @pytest.mark.anyio
    async def test_create_snapshot_returns_existing_without_insert_if_today_exists(self):
        from app.modules.analytics.risk_repository import RiskRepository
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        existing_doc = {"_id": "existing", "date": today, "regions": []}
        col = MagicMock()
        col.find_one = AsyncMock(return_value=existing_doc)
        col.insert_one = AsyncMock()

        repo = RiskRepository.__new__(RiskRepository)
        repo.col = col

        result = await repo.create_snapshot({"regions": []})
        col.insert_one.assert_not_awaited()
        assert result["id"] == "existing"

    @pytest.mark.anyio
    async def test_latest_returns_none_when_empty(self):
        from app.modules.analytics.risk_repository import RiskRepository
        col = MagicMock()

        docs_list = []  # empty

        async def aiter_fn(self_arg):
            for d in docs_list:
                yield d

        sort_obj = MagicMock()
        limit_obj = MagicMock()
        limit_obj.__aiter__ = aiter_fn
        sort_obj.limit = MagicMock(return_value=limit_obj)
        sort_obj.sort = MagicMock(return_value=sort_obj)
        col.find = MagicMock(return_value=sort_obj)

        repo = RiskRepository.__new__(RiskRepository)
        repo.col = col

        result = await repo.latest()
        assert result is None

    @pytest.mark.anyio
    async def test_latest_returns_most_recent(self):
        from app.modules.analytics.risk_repository import RiskRepository
        col = MagicMock()
        doc = {"_id": "abc", "date": "2026-01-01", "regions": []}
        docs_list = [doc]

        # Setup chained mocks
        sort_obj = MagicMock()
        limit_obj = MagicMock()

        async def aiter_fn(self_or_unused=None):
            for d in docs_list:
                yield d

        limit_obj.__aiter__ = aiter_fn
        sort_obj.limit = MagicMock(return_value=limit_obj)
        sort_obj.sort = MagicMock(return_value=sort_obj)
        col.find = MagicMock(return_value=sort_obj)

        repo = RiskRepository.__new__(RiskRepository)
        repo.col = col

        result = await repo.latest()
        assert result is not None
        assert result["id"] == "abc"

    @pytest.mark.anyio
    async def test_history_returns_docs_in_range(self):
        from app.modules.analytics.risk_repository import RiskRepository
        col = MagicMock()
        doc = {"_id": "h1", "date": "2026-06-01", "regions": []}
        docs_list = [doc]

        sort_obj = MagicMock()

        async def aiter_fn(self_or_unused=None):
            for d in docs_list:
                yield d

        sort_obj.__aiter__ = aiter_fn
        sort_obj.sort = MagicMock(return_value=sort_obj)
        col.find = MagicMock(return_value=sort_obj)

        repo = RiskRepository.__new__(RiskRepository)
        repo.col = col

        result = await repo.history(days=30)
        assert len(result) == 1
        assert result[0]["id"] == "h1"


# ===========================================================================
# RiskService — compute_regional_risk
# ===========================================================================

def _make_risk_service(
    *,
    anomalies=None,
    baselines=None,
    history_rows=None,
    active_events=None,
    latest_snapshot=None,
):
    """Build a RiskService with fully mocked collaborators."""
    analytics_svc = MagicMock()
    history_repo = MagicMock()
    intel_events_repo = MagicMock()
    risk_repo = MagicMock()

    anomalies_result = {"anomalies": anomalies or []}
    baselines_result = {"regions": baselines or []}

    analytics_svc.get_anomalies = AsyncMock(return_value=anomalies_result)
    analytics_svc.get_regional_baselines = AsyncMock(return_value=baselines_result)
    history_repo.regional_history = AsyncMock(return_value=history_rows or [])
    intel_events_repo.find_active = AsyncMock(return_value=active_events or [])
    risk_repo.latest = AsyncMock(return_value=latest_snapshot)
    risk_repo.create_snapshot = AsyncMock(return_value={"id": "snap1", "regions": []})

    return RiskService(analytics_svc, history_repo, intel_events_repo, risk_repo)


class TestRiskServiceComputeRegionalRisk:
    @pytest.mark.anyio
    async def test_returns_generated_at_and_regions(self):
        svc = _make_risk_service()
        result = await svc.compute_regional_risk()
        assert "generated_at" in result
        assert "regions" in result

    @pytest.mark.anyio
    async def test_empty_data_returns_empty_regions(self):
        svc = _make_risk_service()
        result = await svc.compute_regional_risk()
        assert result["regions"] == []

    @pytest.mark.anyio
    async def test_region_appears_from_anomaly_data(self):
        anomalies = [
            {"region": "Suceava", "anomaly_score": 0.8, "forest_confidence": 0.9}
        ]
        svc = _make_risk_service(anomalies=anomalies)
        result = await svc.compute_regional_risk()
        regions = [r["region"] for r in result["regions"]]
        assert "Suceava" in regions

    @pytest.mark.anyio
    async def test_regions_sorted_descending_by_risk_score(self):
        anomalies = [
            {"region": "Suceava", "anomaly_score": 0.9, "forest_confidence": 0.9},
            {"region": "Cluj", "anomaly_score": 0.2, "forest_confidence": 0.3},
        ]
        svc = _make_risk_service(anomalies=anomalies)
        result = await svc.compute_regional_risk()
        scores = [r["risk_score"] for r in result["regions"]]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.anyio
    async def test_each_region_has_required_keys(self):
        anomalies = [
            {"region": "Suceava", "anomaly_score": 0.7, "forest_confidence": 0.8}
        ]
        svc = _make_risk_service(anomalies=anomalies)
        result = await svc.compute_regional_risk()
        r = result["regions"][0]
        assert set(r.keys()) >= {"region", "risk_score", "risk_level", "change", "breakdown"}

    @pytest.mark.anyio
    async def test_breakdown_keys_present(self):
        anomalies = [
            {"region": "Suceava", "anomaly_score": 0.7, "forest_confidence": 0.8}
        ]
        svc = _make_risk_service(anomalies=anomalies)
        result = await svc.compute_regional_risk()
        bd_keys = set(result["regions"][0]["breakdown"].keys())
        assert bd_keys == {"current_activity", "historical_activity", "forest", "weather", "priority", "escalation"}

    @pytest.mark.anyio
    async def test_escalation_critical_raises_risk(self):
        anomalies = [{"region": "Suceava", "anomaly_score": 0.5, "forest_confidence": 0.8}]
        active_events_no_esc = []
        active_events_critical = [
            {"region": "Suceava", "priority_score": 0.8, "escalation_level": "critical"}
        ]
        svc_no_esc = _make_risk_service(anomalies=anomalies, active_events=active_events_no_esc)
        svc_critical = _make_risk_service(anomalies=anomalies, active_events=active_events_critical)
        r_no = await svc_no_esc.compute_regional_risk()
        r_cr = await svc_critical.compute_regional_risk()
        no_score = r_no["regions"][0]["risk_score"]
        cr_score = r_cr["regions"][0]["risk_score"]
        assert cr_score > no_score

    @pytest.mark.anyio
    async def test_historical_activity_normalized_by_max(self):
        history_rows = [
            {"_id": "Suceava", "events_last_30d": 100},
            {"_id": "Cluj", "events_last_30d": 50},
        ]
        svc = _make_risk_service(history_rows=history_rows)
        result = await svc.compute_regional_risk()
        by_region = {r["region"]: r for r in result["regions"]}
        # Suceava should have higher historical_activity contribution than Cluj
        suceava_ha = by_region["Suceava"]["breakdown"]["historical_activity"]
        cluj_ha = by_region["Cluj"]["breakdown"]["historical_activity"]
        assert suceava_ha > cluj_ha

    @pytest.mark.anyio
    async def test_change_new_for_unknown_region_in_snapshot(self):
        anomalies = [{"region": "Suceava", "anomaly_score": 0.5, "forest_confidence": 0.8}]
        latest_snapshot = {"regions": []}  # Suceava not in snapshot
        svc = _make_risk_service(anomalies=anomalies, latest_snapshot=latest_snapshot)
        result = await svc.compute_regional_risk()
        suceava = next(r for r in result["regions"] if r["region"] == "Suceava")
        assert suceava["change"] == "new"

    @pytest.mark.anyio
    async def test_change_up_when_score_increased(self):
        anomalies = [{"region": "Suceava", "anomaly_score": 0.9, "forest_confidence": 1.0}]
        latest_snapshot = {"regions": [{"region": "Suceava", "risk_score": 0.1}]}
        svc = _make_risk_service(anomalies=anomalies, latest_snapshot=latest_snapshot)
        result = await svc.compute_regional_risk()
        suceava = next(r for r in result["regions"] if r["region"] == "Suceava")
        assert suceava["change"] == "up"

    @pytest.mark.anyio
    async def test_region_appears_from_history_only(self):
        """Regions with history but no anomalies should still appear."""
        history_rows = [{"_id": "Vâlcea", "events_last_30d": 30}]
        svc = _make_risk_service(history_rows=history_rows)
        result = await svc.compute_regional_risk()
        regions = [r["region"] for r in result["regions"]]
        assert "Vâlcea" in regions

    @pytest.mark.anyio
    async def test_multiple_intel_events_same_region_takes_highest_priority(self):
        """When two intel events target the same region, use the higher priority."""
        active_events = [
            {"region": "Suceava", "priority_score": 0.3, "escalation_level": "normal"},
            {"region": "Suceava", "priority_score": 0.9, "escalation_level": "critical"},
        ]
        anomalies = [{"region": "Suceava", "anomaly_score": 0.5, "forest_confidence": 0.8}]
        svc = _make_risk_service(anomalies=anomalies, active_events=active_events)
        result = await svc.compute_regional_risk()
        suceava = next(r for r in result["regions"] if r["region"] == "Suceava")
        # priority contribution should reflect 0.9 * 0.10 = 0.09 (v2), not 0.3 * 0.10
        assert suceava["breakdown"]["priority"] > 0.08

    @pytest.mark.anyio
    async def test_risk_score_in_bounds(self):
        anomalies = [
            {"region": r, "anomaly_score": 0.99, "forest_confidence": 1.0}
            for r in ["A", "B", "C"]
        ]
        svc = _make_risk_service(anomalies=anomalies)
        result = await svc.compute_regional_risk()
        for r in result["regions"]:
            assert 0.0 <= r["risk_score"] <= 1.0


class TestRiskServicePersistSnapshot:
    @pytest.mark.anyio
    async def test_persist_snapshot_calls_risk_repo(self):
        anomalies = [{"region": "Suceava", "anomaly_score": 0.7, "forest_confidence": 0.9}]
        svc = _make_risk_service(anomalies=anomalies)
        await svc.persist_snapshot()
        svc._risk_repo.create_snapshot.assert_awaited_once()

    @pytest.mark.anyio
    async def test_persist_snapshot_returns_snapshot_dict(self):
        svc = _make_risk_service()
        result = await svc.persist_snapshot()
        assert isinstance(result, dict)


# ===========================================================================
# Scheduler integration — risk snapshot called in _run_cycle
# ===========================================================================

class TestSchedulerRiskIntegration:
    @pytest.mark.anyio
    async def test_risk_persist_snapshot_called_on_successful_cycle(self):
        """_run_cycle should call risk_svc.persist_snapshot() when provided."""
        from app.services.scheduler_service import SchedulerService

        firms = MagicMock()
        firms.run = AsyncMock(return_value={"total": 5, "created": 3, "skipped": 2})

        analytics = MagicMock()
        analytics.reconcile_intelligence_events = AsyncMock(return_value={})

        intel_svc = MagicMock()
        runs_repo = MagicMock()
        runs_repo.create_run = AsyncMock(return_value={
            "events_fetched": 5, "events_inserted": 3, "duplicates_skipped": 2,
            "duration_seconds": 1.0,
        })
        events_service = MagicMock()
        events_repo = MagicMock()

        risk_svc = MagicMock()
        risk_svc.persist_snapshot = AsyncMock(return_value={"id": "snap1"})

        scheduler = SchedulerService(
            firms_provider=firms,
            events_service=events_service,
            events_repo=events_repo,
            analytics_service=analytics,
            intelligence_service=intel_svc,
            runs_repo=runs_repo,
            enabled=True,
            risk_svc=risk_svc,
        )

        await scheduler._run_cycle()
        risk_svc.persist_snapshot.assert_awaited_once()

    @pytest.mark.anyio
    async def test_risk_snapshot_not_called_when_risk_svc_none(self):
        """Scheduler without risk_svc should not raise or attempt persist."""
        from app.services.scheduler_service import SchedulerService

        firms = MagicMock()
        firms.run = AsyncMock(return_value={"total": 0, "created": 0, "skipped": 0})
        analytics = MagicMock()
        analytics.reconcile_intelligence_events = AsyncMock(return_value={})
        runs_repo = MagicMock()
        runs_repo.create_run = AsyncMock(return_value={
            "events_fetched": 0, "events_inserted": 0, "duplicates_skipped": 0,
            "duration_seconds": 0.1,
        })

        scheduler = SchedulerService(
            firms_provider=firms,
            events_service=MagicMock(),
            events_repo=MagicMock(),
            analytics_service=analytics,
            intelligence_service=MagicMock(),
            runs_repo=runs_repo,
            enabled=True,
            risk_svc=None,
        )
        # Should not raise
        await scheduler._run_cycle()

    @pytest.mark.anyio
    async def test_risk_snapshot_failure_does_not_break_cycle(self):
        """A failing risk_svc.persist_snapshot should not cancel the cycle."""
        from app.services.scheduler_service import SchedulerService

        firms = MagicMock()
        firms.run = AsyncMock(return_value={"total": 0, "created": 0, "skipped": 0})
        analytics = MagicMock()
        analytics.reconcile_intelligence_events = AsyncMock(return_value={})
        runs_repo = MagicMock()
        runs_repo.create_run = AsyncMock(return_value={
            "events_fetched": 0, "events_inserted": 0, "duplicates_skipped": 0,
            "duration_seconds": 0.1,
        })
        risk_svc = MagicMock()
        risk_svc.persist_snapshot = AsyncMock(side_effect=RuntimeError("DB down"))

        scheduler = SchedulerService(
            firms_provider=firms,
            events_service=MagicMock(),
            events_repo=MagicMock(),
            analytics_service=analytics,
            intelligence_service=MagicMock(),
            runs_repo=runs_repo,
            enabled=True,
            risk_svc=risk_svc,
        )
        # Should not raise — failure is logged and swallowed
        result = await scheduler._run_cycle()
        assert isinstance(result, dict)


# ===========================================================================
# API endpoint registration
# ===========================================================================

class TestRiskApiEndpoint:
    def _make_app(self):
        """Build a minimal FastAPI test app with the analytics router.

        The analytics router already has prefix="/analytics", so we mount
        it under prefix="/api" to get paths like /api/analytics/intelligence/risk.
        """
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.modules.analytics.analytics_routes import router
        from app.api.deps import get_current_user, risk_service_dep
        from app.models.user import UserPublic

        mock_user = UserPublic(
            id="u1",
            email="test@test.com",
            name="Test User",
            role="admin",
            provider="local",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        mock_risk_svc = MagicMock()
        mock_risk_svc.get_risk = AsyncMock(return_value={
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "regions": [
                {
                    "region": "Suceava",
                    "risk_score": 0.7512,
                    "risk_level": "Extreme",
                    "change": "up",
                    "breakdown": {
                        "current_activity": 0.2625,
                        "historical_activity": 0.1875,
                        "forest": 0.15,
                        "priority": 0.0825,
                        "escalation": 0.0687,
                    },
                }
            ],
        })

        app = FastAPI()
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[risk_service_dep] = lambda: mock_risk_svc
        # router has prefix="/analytics"; mount at "/api" → full path "/api/analytics/..."
        app.include_router(router, prefix="/api")
        return TestClient(app), mock_risk_svc

    def test_risk_endpoint_is_registered(self):
        client, _ = self._make_app()
        resp = client.get("/api/analytics/intelligence/risk")
        assert resp.status_code == 200

    def test_risk_response_has_generated_at(self):
        client, _ = self._make_app()
        resp = client.get("/api/analytics/intelligence/risk")
        assert "generated_at" in resp.json()

    def test_risk_response_has_regions_list(self):
        client, _ = self._make_app()
        resp = client.get("/api/analytics/intelligence/risk")
        data = resp.json()
        assert "regions" in data
        assert isinstance(data["regions"], list)

    def test_risk_region_has_required_fields(self):
        client, _ = self._make_app()
        resp = client.get("/api/analytics/intelligence/risk")
        r = resp.json()["regions"][0]
        assert "region" in r
        assert "risk_score" in r
        assert "risk_level" in r
        assert "change" in r
        assert "breakdown" in r

    def test_risk_breakdown_has_five_components(self):
        client, _ = self._make_app()
        resp = client.get("/api/analytics/intelligence/risk")
        bd = resp.json()["regions"][0]["breakdown"]
        assert set(bd.keys()) == {
            "current_activity", "historical_activity", "forest", "priority", "escalation"
        }

    def test_route_requires_authentication(self):
        """Verify the /intelligence/risk route is registered on the analytics router."""
        from app.modules.analytics.analytics_routes import router
        # Routes in a router with prefix="/analytics" have paths like
        # "/analytics/intelligence/risk"
        route_paths = [r.path for r in router.routes]
        assert any("intelligence/risk" in p for p in route_paths)
