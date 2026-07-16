"""Tests for the Romania intelligence seed dataset.

Verification strategy
---------------------
The seed inserts ForestEvents with ``metadata.ingestion.is_romania = True``
spread across three Romanian regions.  These tests verify the full chain
*without* a live database by:

  1. Checking seed metadata — all inserted events carry the correct flags.
  2. Checking event distribution — enough events per region and window to
     satisfy the anomaly eligibility thresholds.
  3. Running the pure analytics pipeline (``_compute_baselines`` →
     ``_evaluate_anomalies``) on simulated aggregation rows that mirror what
     MongoDB would compute from the seeded events.
  4. Running ``IntelligenceEventsService.reconcile()`` with a mock repository
     to confirm at least one IntelligenceEvent is created.

No live MongoDB connection is required.
"""
from __future__ import annotations

import pytest
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock

from app.services.romania_seed_service import (
    _build_event_specs,
    seed_romania_intelligence,
    SEED_FLAG,
    _FIRMS,
    _CSV,
)
from app.modules.analytics.analytics_service import (
    _compute_baselines,
    _evaluate_anomalies,
    _compute_anomaly_score,
    _anomaly_severity,
    _ANOMALY_MIN_EVENTS,
    _ANOMALY_MIN_DEVIATION,
)
from app.modules.analytics.intelligence_events_service import IntelligenceEventsService

# Fixed anchor so all window calculations are deterministic.
_NOW = datetime(2024, 7, 15, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Shared helper — simulate MongoDB regional_baselines() aggregation result
# ---------------------------------------------------------------------------

def _simulated_baseline_rows(now: datetime = _NOW) -> list[dict]:
    """Replicate what ``AnalyticsRepository.regional_baselines()`` would
    aggregate from the seeded events, without touching MongoDB.

    Classification:
      days_ago <= 6  → "current" window (last 7 days)
      days_ago >= 8  → "baseline" window (8–34 days ago)
      day 7 is intentionally absent from the spec to avoid boundary ambiguity.
    """
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"current": 0, "baseline": 0})
    for region, _src, _conf, _sev, _area, days_ago in _build_event_specs():
        if days_ago <= 6:
            counts[region]["current"] += 1
        elif days_ago >= 8:
            counts[region]["baseline"] += 1
    return [
        {"_id": region, "current_events": v["current"], "baseline_raw": v["baseline"]}
        for region, v in counts.items()
    ]


# ---------------------------------------------------------------------------
# Section 1 — Seed metadata correctness
# ---------------------------------------------------------------------------

class TestSeedMetadata:
    """Verify that every inserted event carries the required metadata fields."""

    @pytest.mark.anyio
    async def test_seed_is_idempotent_when_events_exist(self):
        """When a seed event already exists the function must return 0."""
        repo = AsyncMock()
        repo.col = AsyncMock()
        repo.col.find_one = AsyncMock(return_value={"_id": "existing"})

        count = await seed_romania_intelligence(repo, ["src1"], now=_NOW)

        assert count == 0
        repo.insert.assert_not_called()

    @pytest.mark.anyio
    async def test_seed_inserts_events_on_empty_collection(self):
        """When no seed events exist, the function inserts a non-zero batch."""
        repo = AsyncMock()
        repo.col = AsyncMock()
        repo.col.find_one = AsyncMock(return_value=None)

        inserted: list = []

        async def _capture(ev):
            inserted.append(ev)
            return ev

        repo.insert = _capture

        count = await seed_romania_intelligence(repo, ["src1", "src2"], now=_NOW)

        assert count > 0
        assert count == len(inserted)

    @pytest.mark.anyio
    async def test_every_event_has_romania_seed_flag(self):
        """All seeded events must carry ``SEED_FLAG`` in metadata."""
        repo = AsyncMock()
        repo.col = AsyncMock()
        repo.col.find_one = AsyncMock(return_value=None)
        inserted: list = []

        async def _capture(ev):
            inserted.append(ev)
            return ev

        repo.insert = _capture
        await seed_romania_intelligence(repo, ["src1", "src2"], now=_NOW)

        for ev in inserted:
            assert ev.metadata.get(SEED_FLAG) is True, (
                f"Event {ev.title!r} is missing the '{SEED_FLAG}' flag"
            )

    @pytest.mark.anyio
    async def test_every_event_has_is_romania_ingestion_flag(self):
        """All seeded events must have ``metadata.ingestion.is_romania = True``."""
        repo = AsyncMock()
        repo.col = AsyncMock()
        repo.col.find_one = AsyncMock(return_value=None)
        inserted: list = []

        async def _capture(ev):
            inserted.append(ev)
            return ev

        repo.insert = _capture
        await seed_romania_intelligence(repo, ["src1", "src2"], now=_NOW)

        for ev in inserted:
            ingestion = ev.metadata.get("ingestion", {})
            assert ingestion.get("is_romania") is True, (
                f"Event {ev.title!r} has is_romania={ingestion.get('is_romania')!r}"
            )

    @pytest.mark.anyio
    async def test_every_event_has_country_romania(self):
        """All seeded events must have ``country = 'Romania'``."""
        repo = AsyncMock()
        repo.col = AsyncMock()
        repo.col.find_one = AsyncMock(return_value=None)
        inserted: list = []

        async def _capture(ev):
            inserted.append(ev)
            return ev

        repo.insert = _capture
        await seed_romania_intelligence(repo, ["src1", "src2"], now=_NOW)

        for ev in inserted:
            assert ev.country == "Romania"

    @pytest.mark.anyio
    async def test_events_use_firms_and_csv_sources(self):
        """The seed must produce events from both FIRMS and CSV sources."""
        repo = AsyncMock()
        repo.col = AsyncMock()
        repo.col.find_one = AsyncMock(return_value=None)
        inserted: list = []

        async def _capture(ev):
            inserted.append(ev)
            return ev

        repo.insert = _capture
        await seed_romania_intelligence(repo, ["src1", "src2"], now=_NOW)

        sources = {ev.metadata["ingestion"]["source"] for ev in inserted}
        assert _FIRMS in sources, "Expected NASA FIRMS events in seed"
        assert _CSV in sources, "Expected CSV events in seed"


# ---------------------------------------------------------------------------
# Section 2 — Event distribution by region and time window
# ---------------------------------------------------------------------------

class TestSeedEventDistribution:
    """Verify per-region counts in the current and baseline windows."""

    def _categorise(self, now: datetime = _NOW):
        """Group inserted events by region and window."""
        current_cutoff = now - timedelta(days=7)
        by_region: dict[str, dict[str, int]] = defaultdict(
            lambda: {"current": 0, "baseline": 0, "last_24h": 0}
        )
        h24_cutoff = now - timedelta(hours=24)
        for region, _src, _conf, _sev, _area, days_ago in _build_event_specs():
            detected = now - timedelta(days=days_ago)
            if detected >= current_cutoff:
                by_region[region]["current"] += 1
            else:
                by_region[region]["baseline"] += 1
            if detected >= h24_cutoff:
                by_region[region]["last_24h"] += 1
        return by_region

    def test_suceava_current_meets_anomaly_minimum(self):
        dist = self._categorise()
        assert dist["Suceava"]["current"] >= _ANOMALY_MIN_EVENTS, (
            f"Suceava needs >= {_ANOMALY_MIN_EVENTS} current events; "
            f"got {dist['Suceava']['current']}"
        )

    def test_bacau_current_meets_anomaly_minimum(self):
        dist = self._categorise()
        assert dist["Bacău"]["current"] >= _ANOMALY_MIN_EVENTS

    def test_suceava_has_last_24h_events(self):
        """At least 5 Suceava events must fall within the last 24 h for
        temporal intelligence queries."""
        dist = self._categorise()
        assert dist["Suceava"]["last_24h"] >= 5

    def test_harghita_has_large_baseline(self):
        """Harghita needs enough baseline events to keep deviation < 50%."""
        dist = self._categorise()
        baseline_raw = dist["Harghita"]["baseline"]
        current = dist["Harghita"]["current"]
        baseline_events = round(baseline_raw / 4)
        # deviation must be < 50 for Harghita to remain stable
        if baseline_events > 0:
            deviation = (current - baseline_events) / baseline_events * 100
            assert deviation < _ANOMALY_MIN_DEVIATION, (
                f"Harghita deviation={deviation:.1f}% exceeds stable threshold"
            )

    def test_three_regions_are_seeded(self):
        dist = self._categorise()
        assert len(dist) == 3
        assert "Suceava" in dist
        assert "Bacău" in dist
        assert "Harghita" in dist


# ---------------------------------------------------------------------------
# Section 3 — Analytics pipeline produces anomalies from seeded data
# ---------------------------------------------------------------------------

class TestSeedProducesAnomalies:
    """Run the pure analytics pipeline against simulated aggregation rows and
    verify that the seed yields the expected anomalies."""

    def _anomalies(self):
        rows = _simulated_baseline_rows()
        baselines = _compute_baselines(rows, _NOW)
        result = _evaluate_anomalies(baselines["regions"], _NOW)
        return result["anomalies"]

    def test_at_least_one_anomaly_is_detected(self):
        assert len(self._anomalies()) >= 1

    def test_suceava_is_detected_as_anomaly(self):
        regions = {a["region"] for a in self._anomalies()}
        assert "Suceava" in regions

    def test_bacau_is_detected_as_anomaly(self):
        regions = {a["region"] for a in self._anomalies()}
        assert "Bacău" in regions

    def test_harghita_is_not_an_anomaly(self):
        regions = {a["region"] for a in self._anomalies()}
        assert "Harghita" not in regions

    def test_anomalies_have_high_or_critical_severity(self):
        severities = {a["severity"] for a in self._anomalies()}
        assert severities & {"high", "critical"}, (
            f"Expected at least one high/critical anomaly; got {severities}"
        )

    def test_anomaly_scores_are_in_valid_range(self):
        for a in self._anomalies():
            assert 0.0 <= a["anomaly_score"] <= 1.0, (
                f"anomaly_score={a['anomaly_score']!r} out of [0, 1]"
            )

    def test_suceava_anomaly_score_matches_formula(self):
        """Verify Suceava's score against the documented formula.

        current=10, baseline_raw=8 → baseline_events=2, deviation=400%
        score = 0.4 * (10/50) + 0.6 * min(400/200, 1.0)
              = 0.08 + 0.60 = 0.68
        """
        rows = _simulated_baseline_rows()
        baselines = _compute_baselines(rows, _NOW)
        suceava = next(r for r in baselines["regions"] if r["region"] == "Suceava")

        assert suceava["current_events"] == 10
        assert suceava["baseline_events"] == 2
        assert suceava["deviation_percent"] == pytest.approx(400.0, rel=0.01)

        score = _compute_anomaly_score(
            suceava["current_events"],
            suceava["baseline_events"],
            suceava["deviation_percent"],
        )
        assert score == pytest.approx(0.68, abs=0.001)
        assert _anomaly_severity(score) == "high"

    def test_bacau_anomaly_score_matches_formula(self):
        """Verify Bacău's score.

        current=6, baseline_raw=8 → baseline_events=2, deviation=200%
        score = 0.4 * (6/50) + 0.6 * min(200/200, 1.0)
              = 0.048 + 0.60 = 0.648
        """
        rows = _simulated_baseline_rows()
        baselines = _compute_baselines(rows, _NOW)
        bacau = next(r for r in baselines["regions"] if r["region"] == "Bacău")

        assert bacau["current_events"] == 6
        assert bacau["baseline_events"] == 2
        assert bacau["deviation_percent"] == pytest.approx(200.0, rel=0.01)

        score = _compute_anomaly_score(
            bacau["current_events"],
            bacau["baseline_events"],
            bacau["deviation_percent"],
        )
        assert score == pytest.approx(0.648, abs=0.001)
        assert _anomaly_severity(score) == "high"

    def test_anomalies_are_sorted_by_score_descending(self):
        anomalies = self._anomalies()
        scores = [a["anomaly_score"] for a in anomalies]
        assert scores == sorted(scores, reverse=True), (
            "Anomalies must be sorted descending by anomaly_score"
        )

    def test_all_anomalies_have_status_active(self):
        for a in self._anomalies():
            assert a["status"] == "active"

    def test_all_anomalies_have_required_fields(self):
        required = {"region", "baseline_events", "current_events",
                    "deviation_percent", "anomaly_score", "severity", "status"}
        for a in self._anomalies():
            missing = required - a.keys()
            assert not missing, f"Anomaly {a.get('region')!r} missing fields: {missing}"


# ---------------------------------------------------------------------------
# Section 4 — Intelligence event creation from seeded anomalies
# ---------------------------------------------------------------------------

class TestSeedProducesIntelligenceEvents:
    """Run IntelligenceEventsService.reconcile() against the simulated anomalies
    and assert that at least one IntelligenceEvent is created."""

    def _get_anomalies(self):
        rows = _simulated_baseline_rows()
        baselines = _compute_baselines(rows, _NOW)
        return _evaluate_anomalies(baselines["regions"], _NOW)["anomalies"]

    @pytest.mark.anyio
    async def test_reconcile_creates_at_least_one_intelligence_event(self):
        anomalies = self._get_anomalies()
        assert anomalies, "Precondition: seed must produce anomalies"

        repo = AsyncMock()
        repo.find_active = AsyncMock(return_value=[])

        svc = IntelligenceEventsService(repo)
        await svc.reconcile(anomalies, _NOW)

        assert repo.create.call_count >= 1, (
            "reconcile() must call repo.create() at least once"
        )

    @pytest.mark.anyio
    async def test_reconcile_creates_one_event_per_anomaly(self):
        anomalies = self._get_anomalies()
        repo = AsyncMock()
        repo.find_active = AsyncMock(return_value=[])

        svc = IntelligenceEventsService(repo)
        await svc.reconcile(anomalies, _NOW)

        assert repo.create.call_count == len(anomalies), (
            f"Expected {len(anomalies)} created events; "
            f"got {repo.create.call_count}"
        )

    @pytest.mark.anyio
    async def test_created_events_have_correct_regions(self):
        anomalies = self._get_anomalies()
        anomaly_regions = {a["region"] for a in anomalies}

        repo = AsyncMock()
        repo.find_active = AsyncMock(return_value=[])

        svc = IntelligenceEventsService(repo)
        await svc.reconcile(anomalies, _NOW)

        created_regions = {
            call.args[0]["region"] for call in repo.create.call_args_list
        }
        assert created_regions == anomaly_regions

    @pytest.mark.anyio
    async def test_created_events_are_typed_as_anomaly(self):
        anomalies = self._get_anomalies()
        repo = AsyncMock()
        repo.find_active = AsyncMock(return_value=[])

        svc = IntelligenceEventsService(repo)
        await svc.reconcile(anomalies, _NOW)

        for call in repo.create.call_args_list:
            doc = call.args[0]
            assert doc["event_type"] == "anomaly"

    @pytest.mark.anyio
    async def test_created_events_have_status_active(self):
        anomalies = self._get_anomalies()
        repo = AsyncMock()
        repo.find_active = AsyncMock(return_value=[])

        svc = IntelligenceEventsService(repo)
        await svc.reconcile(anomalies, _NOW)

        for call in repo.create.call_args_list:
            doc = call.args[0]
            assert doc["status"] == "active"

    @pytest.mark.anyio
    async def test_created_events_have_detection_count_one(self):
        """First reconciliation always starts with detection_count = 1."""
        anomalies = self._get_anomalies()
        repo = AsyncMock()
        repo.find_active = AsyncMock(return_value=[])

        svc = IntelligenceEventsService(repo)
        await svc.reconcile(anomalies, _NOW)

        for call in repo.create.call_args_list:
            doc = call.args[0]
            assert doc["detection_count"] == 1

    @pytest.mark.anyio
    async def test_created_events_have_trend_new(self):
        """First reconciliation must set trend='new' and previous_score=None."""
        anomalies = self._get_anomalies()
        repo = AsyncMock()
        repo.find_active = AsyncMock(return_value=[])

        svc = IntelligenceEventsService(repo)
        await svc.reconcile(anomalies, _NOW)

        for call in repo.create.call_args_list:
            doc = call.args[0]
            assert doc["trend"] == "new"
            assert doc["previous_score"] is None

    @pytest.mark.anyio
    async def test_created_events_have_priority_score(self):
        """Each created event must carry a non-negative priority_score."""
        anomalies = self._get_anomalies()
        repo = AsyncMock()
        repo.find_active = AsyncMock(return_value=[])

        svc = IntelligenceEventsService(repo)
        await svc.reconcile(anomalies, _NOW)

        for call in repo.create.call_args_list:
            doc = call.args[0]
            assert "priority_score" in doc
            assert doc["priority_score"] >= 0.0

    @pytest.mark.anyio
    async def test_no_stale_events_resolved_on_first_run(self):
        """When there are no pre-existing active events, resolve is never called."""
        anomalies = self._get_anomalies()
        repo = AsyncMock()
        repo.find_active = AsyncMock(return_value=[])

        svc = IntelligenceEventsService(repo)
        await svc.reconcile(anomalies, _NOW)

        repo.resolve.assert_not_called()
