"""Unit tests for data-quality analytics (service layer)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.modules.analytics.analytics_service import AnalyticsService
from app.core.geography.romania import ROMANIA_BBOX, is_romania_expression


def _empty_events_doc() -> dict:
    return {
        "global_totals": [],
        "global_confidence": [],
        "romania_totals": [],
        "romania_confidence": [],
    }


def _service(
    events_doc: dict | None = None,
    import_doc: dict | None = None,
) -> AnalyticsService:
    repo = MagicMock()
    repo.data_quality_events = AsyncMock(
        return_value=events_doc or _empty_events_doc()
    )
    repo.data_quality_import_totals = AsyncMock(return_value=import_doc)
    return AnalyticsService(repo)


class TestRomaniaDetection:
    def test_expression_has_country_region_and_bbox_fallback(self):
        expr = is_romania_expression()
        assert "$or" in expr
        assert len(expr["$or"]) == 3
        assert ROMANIA_BBOX["min_lat"] < ROMANIA_BBOX["max_lat"]


class TestDataQualityService:
    def test_empty_dataset_returns_safe_defaults(self):
        svc = _service()
        body = asyncio.run(svc.data_quality())

        assert body == {
            "total_events": 0,
            "romania_events": 0,
            "duplicate_prevention_rate": 0.0,
            "confidence_distribution": {"low": 0, "medium": 0, "high": 0},
            "coordinate_validity_rate": 0.0,
        }

    def test_global_fallback_when_no_romania_events(self):
        svc = _service(
            events_doc={
                "global_totals": [{"total_events": 4, "valid_coords": 3}],
                "global_confidence": [
                    {"_id": "low", "count": 1},
                    {"_id": "medium", "count": 1},
                    {"_id": "high", "count": 2},
                ],
                "romania_totals": [],
                "romania_confidence": [],
            },
            import_doc={"total_attempts": 10, "skipped_count": 2},
        )
        body = asyncio.run(svc.data_quality())

        assert body["total_events"] == 4
        assert body["romania_events"] == 0
        assert body["duplicate_prevention_rate"] == 0.2
        assert body["coordinate_validity_rate"] == 0.75
        assert body["confidence_distribution"] == {"low": 1, "medium": 1, "high": 2}

    def test_romania_subset_used_when_present(self):
        svc = _service(
            events_doc={
                "global_totals": [{"total_events": 10, "valid_coords": 9}],
                "global_confidence": [{"_id": "high", "count": 10}],
                "romania_totals": [{"total_events": 2, "valid_coords": 1}],
                "romania_confidence": [
                    {"_id": "low", "count": 1},
                    {"_id": "high", "count": 1},
                ],
            },
        )
        body = asyncio.run(svc.data_quality())

        assert body["total_events"] == 10
        assert body["romania_events"] == 2
        assert body["confidence_distribution"] == {"low": 1, "medium": 0, "high": 1}
        assert body["coordinate_validity_rate"] == 0.5

    def test_missing_import_jobs_yields_zero_dedupe_rate(self):
        svc = _service(
            events_doc={
                "global_totals": [{"total_events": 2, "valid_coords": 2}],
                "global_confidence": [{"_id": "high", "count": 2}],
                "romania_totals": [],
                "romania_confidence": [],
            },
            import_doc=None,
        )
        body = asyncio.run(svc.data_quality())

        assert body["duplicate_prevention_rate"] == 0.0
        assert body["coordinate_validity_rate"] == 1.0

    def test_missing_country_and_confidence_do_not_crash(self):
        svc = _service(
            events_doc={
                "global_totals": [{"total_events": 1, "valid_coords": 0}],
                "global_confidence": [],
                "romania_totals": [],
                "romania_confidence": [],
            },
        )
        body = asyncio.run(svc.data_quality())

        assert body["total_events"] == 1
        assert body["romania_events"] == 0
        assert body["confidence_distribution"] == {"low": 0, "medium": 0, "high": 0}

    def test_ignores_unknown_confidence_buckets(self):
        svc = _service(
            events_doc={
                "global_totals": [{"total_events": 1, "valid_coords": 1}],
                "global_confidence": [{"_id": "unknown", "count": 1}],
                "romania_totals": [],
                "romania_confidence": [],
            },
        )
        body = asyncio.run(svc.data_quality())

        assert body["confidence_distribution"] == {"low": 0, "medium": 0, "high": 0}
