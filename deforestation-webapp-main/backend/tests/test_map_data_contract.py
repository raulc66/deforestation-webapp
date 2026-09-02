"""Map data contract and coordinate correctness tests (Package E)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.ecosystem.canonical_identity import spatial_key_from_region
from app.modules.analytics.map_contract import (
    anomaly_map_marker,
    attach_region_centroid,
    forest_event_map_marker,
    intelligence_event_map_marker,
)


class TestForestEventMapMarker:
    def test_canonical_fields(self):
        event = {
            "_id": "evt-1",
            "latitude": 46.42,
            "longitude": 25.65,
            "severity": "high",
            "confidence": 0.88,
            "detected_at": datetime(2026, 6, 10, 8, 0, tzinfo=timezone.utc),
            "region": "Harghita",
            "event_type": "wildfire",
            "land_cover_type": "forest",
            "source_id": "NASA FIRMS",
            "metadata": {"ingestion": {"source_event_id": "firms-001"}},
        }
        marker = forest_event_map_marker(event)

        assert marker["latitude"] == 46.42
        assert marker["longitude"] == 25.65
        assert marker["spatial_key"] == spatial_key_from_region("Harghita")
        assert marker["incident_category"] == "wildfire"
        assert marker["severity"] == "high"
        assert marker["confidence"] == 0.88
        assert marker["source_event_id"] == "firms-001"
        assert marker["event_type"] == "wildfire"

    def test_logging_event_maps_to_illegal_logging_category(self):
        event = {
            "latitude": 46.5,
            "longitude": 26.0,
            "region": "Bacău",
            "event_type": "logging",
            "metadata": {},
        }
        marker = forest_event_map_marker(event)
        assert marker["incident_category"] == "illegal_logging"


class TestRegionCentroidAttachment:
    def test_prefers_existing_coordinates(self):
        payload = {"latitude": 47.1, "longitude": 25.2, "region": "Suceava"}
        result = attach_region_centroid(payload, centroids={"Suceava": (47.6, 26.2)})
        assert result["latitude"] == 47.1
        assert result["longitude"] == 25.2
        assert "coordinate_source" not in result

    def test_attaches_event_centroid_when_missing(self):
        payload = {"region": "Suceava"}
        result = attach_region_centroid(payload, centroids={"Suceava": (47.68, 25.72)})
        assert result["latitude"] == 47.68
        assert result["longitude"] == 25.72
        assert result["coordinate_source"] == "region_event_centroid"

    def test_leaflet_coordinate_order_is_lat_lng(self):
        """Regression: GeoJSON stores [lng, lat]; Leaflet markers use [lat, lng]."""
        marker = forest_event_map_marker(
            {"latitude": 45.85, "longitude": 24.97, "region": "Sibiu", "event_type": "wildfire"}
        )
        leaflet_coords = [marker["latitude"], marker["longitude"]]
        assert leaflet_coords == [45.85, 24.97]


class TestIntelligenceAndAnomalyMarkers:
    def test_intelligence_marker_includes_category(self):
        marker = intelligence_event_map_marker(
            {
                "id": "intel-1",
                "region": "Suceava",
                "incident_category": "wildfire",
                "severity": "high",
                "priority_score": 0.71,
            },
            centroids={"Suceava": (47.68, 25.72)},
        )
        assert marker["incident_category"] == "wildfire"
        assert marker["latitude"] == 47.68

    def test_anomaly_marker_uses_centroid_not_city_default(self):
        marker = anomaly_map_marker(
            {"region": "Suceava", "severity": "high", "anomaly_score": 0.64},
            centroids={"Suceava": (47.68, 25.72)},
        )
        assert marker["latitude"] == 47.68
        assert marker["longitude"] == 25.72
        assert marker["incident_category"] == "wildfire"
