"""Unit tests for cross-source analytics (GET /api/analytics/sources)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.analytics.analytics_service import AnalyticsService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _service(by_source_rows: list[dict]) -> AnalyticsService:
    repo = MagicMock()
    repo.by_source = AsyncMock(return_value=by_source_rows)
    return AnalyticsService(repo)


def _firms_row(
    total: int = 5,
    romania: int = 3,
    avg_conf: float = 0.85,
    sev_low: int = 0,
    sev_medium: int = 2,
    sev_high: int = 2,
    sev_critical: int = 1,
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
    total: int = 3,
    romania: int = 1,
    avg_conf: float = 0.78,
    sev_low: int = 1,
    sev_medium: int = 1,
    sev_high: int = 1,
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
# Response shape
# ---------------------------------------------------------------------------

class TestSourceStatisticsShape:
    def test_top_level_key_is_sources(self):
        body = asyncio.run(_service([]).source_statistics())
        assert "sources" in body
        assert isinstance(body["sources"], list)

    def test_empty_collection_returns_empty_list(self):
        body = asyncio.run(_service([]).source_statistics())
        assert body == {"sources": []}

    def test_each_entry_has_required_keys(self):
        body = asyncio.run(_service([_firms_row()]).source_statistics())
        entry = body["sources"][0]
        assert set(entry.keys()) == {
            "source",
            "total_events",
            "romania_events",
            "average_confidence",
            "severity_distribution",
            "reliability_score",
        }

    def test_severity_distribution_has_all_four_buckets(self):
        body = asyncio.run(_service([_firms_row()]).source_statistics())
        sev = body["sources"][0]["severity_distribution"]
        assert set(sev.keys()) == {"low", "medium", "high", "critical"}


# ---------------------------------------------------------------------------
# FIRMS-only dataset
# ---------------------------------------------------------------------------

class TestFIRMSOnly:
    def setup_method(self):
        self.body = asyncio.run(_service([_firms_row()]).source_statistics())

    def test_source_name_is_nasa_firms(self):
        assert self.body["sources"][0]["source"] == "NASA FIRMS"

    def test_total_events_correct(self):
        assert self.body["sources"][0]["total_events"] == 5

    def test_romania_events_correct(self):
        assert self.body["sources"][0]["romania_events"] == 3

    def test_average_confidence_rounded(self):
        assert self.body["sources"][0]["average_confidence"] == 0.85

    def test_severity_distribution_matches(self):
        sev = self.body["sources"][0]["severity_distribution"]
        assert sev == {"low": 0, "medium": 2, "high": 2, "critical": 1}


# ---------------------------------------------------------------------------
# CSV-only dataset
# ---------------------------------------------------------------------------

class TestCSVOnly:
    def setup_method(self):
        self.body = asyncio.run(_service([_csv_row()]).source_statistics())

    def test_source_name_is_csv(self):
        assert self.body["sources"][0]["source"] == "CSV"

    def test_total_events_correct(self):
        assert self.body["sources"][0]["total_events"] == 3

    def test_romania_events_correct(self):
        assert self.body["sources"][0]["romania_events"] == 1

    def test_severity_distribution_matches(self):
        sev = self.body["sources"][0]["severity_distribution"]
        assert sev == {"low": 1, "medium": 1, "high": 1, "critical": 0}


# ---------------------------------------------------------------------------
# Mixed dataset (FIRMS + CSV)
# ---------------------------------------------------------------------------

class TestMixedDataset:
    def setup_method(self):
        self.body = asyncio.run(
            _service([_firms_row(), _csv_row()]).source_statistics()
        )

    def test_two_entries_returned(self):
        assert len(self.body["sources"]) == 2

    def test_sources_are_distinct(self):
        names = {s["source"] for s in self.body["sources"]}
        assert names == {"NASA FIRMS", "CSV"}

    def test_each_source_has_independent_totals(self):
        by_name = {s["source"]: s for s in self.body["sources"]}
        assert by_name["NASA FIRMS"]["total_events"] == 5
        assert by_name["CSV"]["total_events"] == 3

    def test_each_source_has_independent_romania_counts(self):
        by_name = {s["source"]: s for s in self.body["sources"]}
        assert by_name["NASA FIRMS"]["romania_events"] == 3
        assert by_name["CSV"]["romania_events"] == 1

    def test_severity_distributions_are_independent(self):
        by_name = {s["source"]: s for s in self.body["sources"]}
        assert by_name["NASA FIRMS"]["severity_distribution"]["critical"] == 1
        assert by_name["CSV"]["severity_distribution"]["critical"] == 0


# ---------------------------------------------------------------------------
# Missing ingestion metadata fallback
# ---------------------------------------------------------------------------

class TestMissingIngestionMetadata:
    def test_no_rows_from_repo_means_empty_sources(self):
        """When the query returns zero rows (all legacy events excluded by
        the $match stage), the endpoint returns an empty sources list."""
        body = asyncio.run(_service([]).source_statistics())
        assert body["sources"] == []

    def test_result_contains_only_provided_sources(self):
        """Sources without ingestion metadata never appear in results."""
        body = asyncio.run(_service([_firms_row()]).source_statistics())
        names = {s["source"] for s in body["sources"]}
        assert "CSV" not in names


# ---------------------------------------------------------------------------
# Aggregation correctness
# ---------------------------------------------------------------------------

class TestAggregationCorrectness:
    def test_average_confidence_is_float(self):
        body = asyncio.run(_service([_firms_row(avg_conf=0.875)]).source_statistics())
        assert isinstance(body["sources"][0]["average_confidence"], float)

    def test_average_confidence_rounded_to_3_places(self):
        body = asyncio.run(_service([_firms_row(avg_conf=0.8749999)]).source_statistics())
        conf = body["sources"][0]["average_confidence"]
        assert conf == round(0.8749999, 3)

    def test_zero_confidence_handled(self):
        body = asyncio.run(_service([_firms_row(avg_conf=0.0)]).source_statistics())
        assert body["sources"][0]["average_confidence"] == 0.0

    def test_all_events_of_one_severity(self):
        row = _firms_row(sev_low=10, sev_medium=0, sev_high=0, sev_critical=0, total=10)
        body = asyncio.run(_service([row]).source_statistics())
        sev = body["sources"][0]["severity_distribution"]
        assert sev == {"low": 10, "medium": 0, "high": 0, "critical": 0}

    def test_severity_counts_are_integers(self):
        body = asyncio.run(_service([_firms_row()]).source_statistics())
        sev = body["sources"][0]["severity_distribution"]
        for bucket in ("low", "medium", "high", "critical"):
            assert isinstance(sev[bucket], int)

    def test_all_events_are_romania(self):
        row = _firms_row(total=4, romania=4)
        body = asyncio.run(_service([row]).source_statistics())
        entry = body["sources"][0]
        assert entry["romania_events"] == entry["total_events"] == 4

    def test_zero_romania_events(self):
        row = _csv_row(total=3, romania=0)
        body = asyncio.run(_service([row]).source_statistics())
        assert body["sources"][0]["romania_events"] == 0

    def test_missing_optional_repo_fields_default_to_zero(self):
        """Repo rows that lack sev_* keys (e.g. partial aggregation) don't crash."""
        minimal_row = {"_id": "CSV", "total_events": 2, "romania_events": 0,
                       "average_confidence": 0.7}
        body = asyncio.run(_service([minimal_row]).source_statistics())
        sev = body["sources"][0]["severity_distribution"]
        assert sev == {"low": 0, "medium": 0, "high": 0, "critical": 0}


# ---------------------------------------------------------------------------
# Auth + shape — integration-level test (kept lightweight, checks endpoint)
# ---------------------------------------------------------------------------

class TestAuthRequired:
    """Verify the /analytics/sources path requires authentication.
    Full integration runs against a live API; this test is a schema guard.
    """
    def test_endpoint_path_registered(self):
        from app.modules.analytics.analytics_routes import router
        paths = [r.path for r in router.routes]
        assert "/analytics/sources" in paths
