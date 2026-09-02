"""WP2 — category-segmented regional baseline tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.ecosystem.incident_categories import IncidentCategory
from app.modules.analytics.analytics_service import (
    _compute_baselines,
    _evaluate_anomalies,
)
from app.modules.analytics.anomaly_thresholds import get_anomaly_thresholds
from app.modules.analytics.segmented_baseline import (
    aggregate_regional_baselines_by_category,
    filter_baseline_regions_for_category,
    parse_segment_key,
    segment_key,
)

_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _romania_event(
    *,
    region: str,
    days_before: int,
    event_type: str = "wildfire",
    incident_category: str | None = None,
) -> dict:
    detected_at = _NOW - timedelta(days=days_before)
    event = {
        "region": region,
        "event_type": event_type,
        "detected_at": detected_at,
        "land_cover_type": "forest",
        "metadata": {"ingestion": {"is_romania": True}},
    }
    if incident_category is not None:
        event["incident_category"] = incident_category
    return event


class TestParseSegmentKey:
    def test_legacy_string_id_defaults_wildfire(self):
        assert parse_segment_key("Cluj") == ("Cluj", "wildfire")

    def test_composite_id_parses_category(self):
        key = segment_key("Cluj", "illegal_logging")
        assert parse_segment_key(key) == ("Cluj", "illegal_logging")


class TestSegmentedAggregation:
    def test_wildfire_only_matches_legacy_region_counts(self):
        events = [
            _romania_event(region="Alpha", days_before=1),
            _romania_event(region="Alpha", days_before=2),
            _romania_event(region="Alpha", days_before=10),
            _romania_event(region="Alpha", days_before=11),
        ]
        rows = aggregate_regional_baselines_by_category(events, _NOW)
        assert len(rows) == 1
        assert rows[0]["current_events"] == 2
        assert rows[0]["baseline_raw"] == 2
        assert parse_segment_key(rows[0]["_id"]) == ("Alpha", "wildfire")

    def test_two_categories_in_one_region_produce_two_rows(self):
        events = [
            _romania_event(region="Beta", days_before=1, event_type="wildfire"),
            _romania_event(region="Beta", days_before=2, event_type="logging"),
            _romania_event(region="Beta", days_before=10, event_type="wildfire"),
            _romania_event(region="Beta", days_before=11, event_type="logging"),
        ]
        rows = aggregate_regional_baselines_by_category(events, _NOW)
        categories = {parse_segment_key(row["_id"])[1] for row in rows}
        assert categories == {"wildfire", "illegal_logging"}
        by_category = {
            parse_segment_key(row["_id"])[1]: row for row in rows
        }
        assert by_category["wildfire"]["current_events"] == 1
        assert by_category["illegal_logging"]["current_events"] == 1

    def test_cross_category_isolation(self):
        """Adding category B events must not change category A baseline counts."""
        base_events = [
            _romania_event(region="Gamma", days_before=1, event_type="wildfire"),
            _romania_event(region="Gamma", days_before=10, event_type="wildfire"),
        ]
        with_extra = base_events + [
            _romania_event(region="Gamma", days_before=1, event_type="logging"),
            _romania_event(region="Gamma", days_before=2, event_type="logging"),
            _romania_event(region="Gamma", days_before=11, event_type="logging"),
        ]

        base_rows = aggregate_regional_baselines_by_category(base_events, _NOW)
        extra_rows = aggregate_regional_baselines_by_category(with_extra, _NOW)

        def wildfire_row(rows):
            for row in rows:
                if parse_segment_key(row["_id"])[1] == "wildfire":
                    return row
            raise AssertionError("wildfire row missing")

        assert wildfire_row(base_rows) == wildfire_row(extra_rows)


class TestCategoryAwareBaselineShaping:
    def test_shaped_rows_retain_incident_category(self):
        rows = [
            {
                "_id": segment_key("Delta", "illegal_logging"),
                "current_events": 4,
                "baseline_raw": 8,
            }
        ]
        shaped = _compute_baselines(rows, _NOW)["regions"][0]
        assert shaped["incident_category"] == "illegal_logging"
        assert shaped["baseline_events"] == 2

    def test_oracle_projection_omits_incident_category(self):
        rows = [
            {
                "_id": segment_key("Epsilon", "wildfire"),
                "current_events": 5,
                "baseline_raw": 20,
            }
        ]
        shaped = _compute_baselines(
            rows,
            _NOW,
            include_incident_category=False,
        )["regions"][0]
        assert "incident_category" not in shaped
        assert shaped["region"] == "Epsilon"


class TestCategoryAwareAnomalyEvaluation:
    def test_wildfire_thresholds_match_legacy_constants(self):
        thresholds = get_anomaly_thresholds("wildfire")
        assert thresholds.min_events == 5
        assert thresholds.min_deviation_percent == 50.0

    def test_synthetic_category_uses_different_thresholds(self):
        thresholds = get_anomaly_thresholds("illegal_logging")
        assert thresholds.min_events == 3
        assert thresholds.min_deviation_percent == 40.0

    def test_evaluates_only_requested_category(self):
        regions = [
            {
                "region": "Zeta",
                "incident_category": "wildfire",
                "baseline_events": 1,
                "current_events": 6,
                "deviation_percent": 500.0,
                "forest_confidence": 1.0,
            },
            {
                "region": "Zeta",
                "incident_category": "illegal_logging",
                "baseline_events": 1,
                "current_events": 4,
                "deviation_percent": 300.0,
                "forest_confidence": 1.0,
            },
        ]
        wildfire = _evaluate_anomalies(
            regions,
            _NOW,
            incident_category="wildfire",
        )
        logging = _evaluate_anomalies(
            regions,
            _NOW,
            incident_category="illegal_logging",
        )
        assert len(wildfire["anomalies"]) == 1
        assert wildfire["anomalies"][0]["region"] == "Zeta"
        assert len(logging["anomalies"]) == 1
        assert logging["anomalies"][0]["current_events"] == 4

    def test_filter_baseline_regions_for_category(self):
        regions = [
            {"region": "A", "incident_category": "wildfire"},
            {"region": "A", "incident_category": "illegal_logging"},
        ]
        filtered = filter_baseline_regions_for_category(regions, "wildfire")
        assert len(filtered) == 1
        assert filtered[0]["incident_category"] == "wildfire"


class TestWildfireOracleEquivalence:
    def test_wildfire_shaped_values_match_legacy_row_shape(self):
        """Wildfire-only segmented rows produce identical numeric baseline values."""
        legacy_row = {
            "_id": "LegacyRegion",
            "current_events": 20,
            "baseline_raw": 40,
            "lc_forest": 60,
        }
        segmented_row = {
            "_id": segment_key("LegacyRegion", "wildfire"),
            "current_events": 20,
            "baseline_raw": 40,
            "lc_forest": 60,
        }
        legacy = _compute_baselines(
            [legacy_row],
            _NOW,
            include_incident_category=False,
        )["regions"][0]
        segmented = _compute_baselines(
            [segmented_row],
            _NOW,
            include_incident_category=False,
        )["regions"][0]
        assert legacy == segmented
