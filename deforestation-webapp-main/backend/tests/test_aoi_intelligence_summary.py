"""Tests for AOI geometry area and intelligence summary read models."""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.aoi_geometry import geometry_area_hectares
from app.services.aoi_intelligence_summary_service import AoiIntelligenceSummaryService

_NOW = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)


def _romania_polygon() -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[
            [25.5, 46.8], [26.5, 46.8], [26.5, 47.5], [25.5, 47.5], [25.5, 46.8],
        ]],
    }


class TestGeometryAreaHectares:
    def test_polygon_returns_positive_hectares(self):
        area = geometry_area_hectares(_romania_polygon())
        assert area is not None
        assert area > 0

    def test_unsupported_geometry_returns_none(self):
        assert geometry_area_hectares({"type": "Point", "coordinates": [25.0, 46.0]}) is None


class TestAoiIntelligenceSummaryService:
    def test_counts_disturbance_inside_aoi(self):
        svc = AoiIntelligenceSummaryService()
        areas = [{"id": "area-1", "name": "Valea X", "geometry": _romania_polygon(), "enabled": True}]
        events = [
            {
                "id": "evt-1",
                "incident_category": "forest_disturbance",
                "status": "active",
                "severity": "high",
                "latitude": 46.9,
                "longitude": 26.0,
                "first_detected_at": _NOW,
                "last_detected_at": _NOW,
                "metadata": {
                    "forest_disturbance": {
                        "investigation_priority": "high",
                        "driver_confidence": 0.82,
                    }
                },
            }
        ]
        summaries = svc.summarize_areas(
            organization_id="org-1",
            areas=areas,
            active_events=events,
        )
        row = summaries["area-1"]
        assert row["active_intelligence_count"] == 1
        assert row["active_disturbance_count"] == 1
        assert row["high_priority_count"] == 1
        assert row["latest_relevant_detection_at"] == _NOW

    def test_outside_aoi_not_counted(self):
        svc = AoiIntelligenceSummaryService()
        areas = [{"id": "area-1", "name": "Valea X", "geometry": _romania_polygon(), "enabled": True}]
        events = [
            {
                "id": "evt-2",
                "incident_category": "forest_disturbance",
                "latitude": 44.0,
                "longitude": 20.0,
                "metadata": {"forest_disturbance": {"investigation_priority": "high"}},
            }
        ]
        summaries = svc.summarize_areas(
            organization_id="org-1",
            areas=areas,
            active_events=events,
        )
        assert summaries["area-1"]["active_intelligence_count"] == 0
