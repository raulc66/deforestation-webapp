"""WP0.1 — tests for the Phase 0 frozen seed fixture.

Two concerns are covered:

1. **Fixture-loader determinism** (the WP0.1 required test): repeated loads are
   identical and independent, and the time anchors are deterministic.
2. **Fixture design self-check**: using elementary window arithmetic — *not* the
   production analytics engine — prove the fixture is distributed to produce a
   non-trivial mix of active and resolved outcomes across at least two cycles.
   Capturing the authoritative engine outputs is WP0.2, not WP0.1.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from fixtures.phase0_golden_fixture import (
    CYCLE_ANCHORS,
    DESIGN_INTENT_ANOMALY_REGIONS,
    EVENT_COUNT,
    REFERENCE_NOW,
    build_wildfire_events,
    cycle_anchor,
)


# ---------------------------------------------------------------------------
# Local window arithmetic — mirrors AnalyticsRepository.regional_baselines and
# AnalyticsService gates. Duplicated here ONLY to validate fixture design; it is
# not a reimplementation of the engine under test.
# ---------------------------------------------------------------------------

def _windowed_counts(events: list[dict], anchor: datetime) -> dict[str, tuple[int, int]]:
    """Return ``{region: (current_events, baseline_raw)}`` for an anchor."""
    cutoff_7d = anchor - timedelta(days=7)
    cutoff_35d = anchor - timedelta(days=35)
    per_region: dict[str, tuple[int, int]] = {}
    for e in events:
        region = e["region"]
        detected_at = e["detected_at"]
        current, baseline = per_region.get(region, (0, 0))
        if detected_at >= cutoff_7d:
            current += 1
        elif cutoff_35d <= detected_at < cutoff_7d:
            baseline += 1
        per_region[region] = (current, baseline)
    return per_region


def _deviation(current: int, baseline_events: int) -> float:
    if baseline_events == 0:
        return 100.0 if current > 0 else 0.0
    return round((current - baseline_events) / baseline_events * 100, 2)


def _anomaly_regions(events: list[dict], anchor: datetime) -> set[str]:
    anomalies: set[str] = set()
    for region, (current, baseline_raw) in _windowed_counts(events, anchor).items():
        baseline_events = round(baseline_raw / 4)
        deviation = _deviation(current, baseline_events)
        if current >= 5 and deviation >= 50:
            anomalies.add(region)
    return anomalies


# ---------------------------------------------------------------------------
# 1. Fixture-loader determinism (required)
# ---------------------------------------------------------------------------

class TestFixtureDeterminism:
    def test_two_loads_are_equal(self):
        assert build_wildfire_events() == build_wildfire_events()

    def test_repeated_loads_are_stable(self):
        first = build_wildfire_events()
        for _ in range(10):
            assert build_wildfire_events() == first

    def test_loads_are_independent_copies(self):
        first = build_wildfire_events()
        first[0]["region"] = "MUTATED"
        first[0]["metadata"]["ingestion"]["source"] = "MUTATED"
        second = build_wildfire_events()
        assert second[0]["region"] != "MUTATED"
        assert second[0]["metadata"]["ingestion"]["source"] != "MUTATED"

    def test_event_count_is_stable(self):
        assert len(build_wildfire_events()) == EVENT_COUNT

    def test_reference_now_is_timezone_aware_utc(self):
        assert REFERENCE_NOW.tzinfo is not None
        assert REFERENCE_NOW.utcoffset() == timedelta(0)

    def test_cycle_anchors_are_ordered_and_at_least_two(self):
        assert len(CYCLE_ANCHORS) >= 2
        assert list(CYCLE_ANCHORS) == sorted(CYCLE_ANCHORS)

    def test_cycle_anchor_accessor_matches_sequence(self):
        for i, anchor in enumerate(CYCLE_ANCHORS):
            assert cycle_anchor(i) == anchor


# ---------------------------------------------------------------------------
# 2. Structural invariants
# ---------------------------------------------------------------------------

class TestFixtureStructure:
    def test_all_events_are_wildfire(self):
        assert all(e["event_type"] == "wildfire" for e in build_wildfire_events())

    def test_all_events_flagged_romania(self):
        events = build_wildfire_events()
        assert all(e["metadata"]["ingestion"]["is_romania"] is True for e in events)

    def test_all_detected_at_are_timezone_aware(self):
        assert all(e["detected_at"].tzinfo is not None for e in build_wildfire_events())

    def test_multiple_regions_present(self):
        regions = {e["region"] for e in build_wildfire_events()}
        assert {"Suceava", "Bacău", "Cluj", "Harghita"} <= regions

    def test_source_event_ids_are_unique(self):
        ids = [e["metadata"]["ingestion"]["source_event_id"] for e in build_wildfire_events()]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# 3. Fixture design self-check — active/resolved mix across cycles
# ---------------------------------------------------------------------------

class TestFixtureDesignProducesMix:
    def test_cycle1_anomaly_regions_match_design(self):
        events = build_wildfire_events()
        assert _anomaly_regions(events, CYCLE_ANCHORS[0]) == set(
            DESIGN_INTENT_ANOMALY_REGIONS[0]
        )

    def test_cycle2_anomaly_regions_match_design(self):
        events = build_wildfire_events()
        assert _anomaly_regions(events, CYCLE_ANCHORS[1]) == set(
            DESIGN_INTENT_ANOMALY_REGIONS[1]
        )

    def test_produces_non_trivial_active_and_resolved_mix(self):
        events = build_wildfire_events()
        cycle1 = _anomaly_regions(events, CYCLE_ANCHORS[0])
        cycle2 = _anomaly_regions(events, CYCLE_ANCHORS[1])

        persistent = cycle1 & cycle2          # active across both cycles
        newly_active = cycle2 - cycle1        # created in cycle 2
        resolved = cycle1 - cycle2            # active in cycle 1, gone in cycle 2

        assert persistent, "fixture must keep at least one event active across cycles"
        assert newly_active, "fixture must introduce at least one new active event"
        assert resolved, "fixture must resolve at least one event between cycles"

        assert "Suceava" in persistent
        assert "Cluj" in newly_active
        assert "Bacău" in resolved

    def test_stable_control_never_anomalous(self):
        events = build_wildfire_events()
        for anchor in CYCLE_ANCHORS:
            assert "Harghita" not in _anomaly_regions(events, anchor)


# ---------------------------------------------------------------------------
# 4. Architectural determinism guards (permanent-oracle invariants)
# ---------------------------------------------------------------------------

class TestArchitecturalDeterminismGuards:
    """Locks the invariants that qualify the fixture as the permanent Phase 0 oracle."""

    def test_detected_at_is_anchored_to_reference_now_not_wallclock(self):
        # The first event (Suceava, P=-1, idx=0) must equal an absolute value
        # derived solely from REFERENCE_NOW. Any coupling to datetime.now() would
        # break this exact equality.
        events = build_wildfire_events()
        assert events[0]["region"] == "Suceava"
        assert events[0]["detected_at"] == REFERENCE_NOW - timedelta(days=-1, minutes=0)

    def test_all_detected_at_have_zero_utc_offset(self):
        for e in build_wildfire_events():
            assert e["detected_at"].utcoffset() == timedelta(0)

    def test_ids_are_deterministic_across_loads(self):
        ids_a = [e["metadata"]["ingestion"]["source_event_id"] for e in build_wildfire_events()]
        ids_b = [e["metadata"]["ingestion"]["source_event_id"] for e in build_wildfire_events()]
        assert ids_a == ids_b

    def test_ordering_is_deterministic_across_loads(self):
        order_a = [(e["region"], e["detected_at"]) for e in build_wildfire_events()]
        order_b = [(e["region"], e["detected_at"]) for e in build_wildfire_events()]
        assert order_a == order_b

    @pytest.mark.parametrize("anchor", list(CYCLE_ANCHORS))
    def test_no_event_sits_near_a_window_boundary(self, anchor):
        # Every event must be well clear of the current cutoff (A-7d) and the
        # baseline horizon (A-35d) so the sub-day uniqueness offset can never flip
        # an event's window classification. Margin (6h) >> max offset (~64 min).
        margin = timedelta(hours=6)
        cutoff_7d = anchor - timedelta(days=7)
        cutoff_35d = anchor - timedelta(days=35)
        for e in build_wildfire_events():
            detected_at = e["detected_at"]
            assert abs(detected_at - cutoff_7d) >= margin, (e["region"], detected_at)
            assert abs(detected_at - cutoff_35d) >= margin, (e["region"], detected_at)
