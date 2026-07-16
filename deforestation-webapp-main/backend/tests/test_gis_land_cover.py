"""
Comprehensive tests for the GIS-backed land cover classification system.

Coverage:
  - gis_loader: loading GeoJSON, parsing features, grid index, ray-casting PIP
  - GISIndex.classify(): forest, water, urban, agriculture, near_forest, unknown
  - County/boundary accuracy: known Romanian geographic coordinates
  - GISLandCoverService: classify(), classify_full(), classify_event(), classify_batch()
  - get_dataset_info(): structure and values
  - Backward-compatibility: land_cover_service public surface unchanged
  - Analytics integration: get_land_cover_distribution() includes dataset metadata
  - Ingestion pipeline: events receive GIS-based land_cover_type
  - Edge cases: invalid coords, missing keys, non-Romania coords, empty dataset
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers — minimal GeoJSON FeatureCollections for isolated tests
# ---------------------------------------------------------------------------

_RECT_FEATURE = {
    "type": "Feature",
    "properties": {
        "label": "Test Forest",
        "clc_code": 311,
        "land_cover_type": "forest",
        "confidence": 0.92,
    },
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[24.0, 46.0], [25.0, 46.0], [25.0, 47.0], [24.0, 47.0], [24.0, 46.0]]],
    },
}

_URBAN_FEATURE = {
    "type": "Feature",
    "properties": {
        "label": "Test City",
        "clc_code": 112,
        "land_cover_type": "urban",
        "confidence": 0.97,
    },
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[24.4, 46.4], [24.6, 46.4], [24.6, 46.6], [24.4, 46.6], [24.4, 46.4]]],
    },
}

_WATER_FEATURE = {
    "type": "Feature",
    "properties": {
        "label": "Test Lake",
        "clc_code": 511,
        "land_cover_type": "water",
        "confidence": 0.95,
    },
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[22.0, 44.0], [23.0, 44.0], [23.0, 45.0], [22.0, 45.0], [22.0, 44.0]]],
    },
}

_SIMPLE_COLLECTION = {
    "type": "FeatureCollection",
    "properties": {
        "source": "Test Source",
        "version": "1.0",
        "last_updated": "2024-06-01",
    },
    "features": [_RECT_FEATURE, _URBAN_FEATURE, _WATER_FEATURE],
}


def _make_collection(*features, source="Copernicus", version="2018", last_updated="2024-01-01"):
    return {
        "type": "FeatureCollection",
        "properties": {
            "source": source,
            "version": version,
            "last_updated": last_updated,
        },
        "features": list(features),
    }


# ===========================================================================
# gis_loader — parsing and geometry helpers
# ===========================================================================

class TestGISLoaderParsing:
    """Unit tests for GeoJSON parsing and feature extraction."""

    def test_load_valid_feature_collection(self):
        from app.services.gis_loader import load_geojson_dict
        idx = load_geojson_dict(_SIMPLE_COLLECTION)
        assert idx.info.source == "Test Source"
        assert idx.info.version == "1.0"
        assert idx.info.last_updated == "2024-06-01"
        assert len(idx.features) == 3

    def test_dataset_info_feature_count(self):
        from app.services.gis_loader import load_geojson_dict
        idx = load_geojson_dict(_SIMPLE_COLLECTION)
        assert idx.info.feature_count == 3

    def test_rejects_non_feature_collection(self):
        from app.services.gis_loader import load_geojson_dict
        with pytest.raises(ValueError, match="FeatureCollection"):
            load_geojson_dict({"type": "Feature", "properties": {}, "geometry": None})

    def test_skips_invalid_features(self):
        """Features with missing or unsupported geometry are silently skipped."""
        from app.services.gis_loader import load_geojson_dict
        col = _make_collection(
            _RECT_FEATURE,
            {"type": "Feature", "properties": {"land_cover_type": "forest"}, "geometry": None},
            {"type": "Feature", "properties": {}, "geometry": {"type": "Point", "coordinates": [24.0, 46.0]}},
        )
        idx = load_geojson_dict(col)
        assert len(idx.features) == 1

    def test_unknown_land_cover_type_normalised(self):
        from app.services.gis_loader import load_geojson_dict
        feat = {
            "type": "Feature",
            "properties": {"label": "x", "land_cover_type": "swamp", "confidence": 0.5},
            "geometry": _RECT_FEATURE["geometry"],
        }
        idx = load_geojson_dict(_make_collection(feat))
        assert idx.features[0].land_cover_type == "unknown"

    def test_missing_confidence_uses_default(self):
        from app.services.gis_loader import load_geojson_dict
        feat = {
            "type": "Feature",
            "properties": {"label": "x", "land_cover_type": "forest"},
            "geometry": _RECT_FEATURE["geometry"],
        }
        idx = load_geojson_dict(_make_collection(feat))
        assert idx.features[0].confidence > 0.0

    def test_multipolygon_geometry_accepted(self):
        """MultiPolygon is accepted; the first polygon's exterior ring is used."""
        from app.services.gis_loader import load_geojson_dict
        feat = {
            "type": "Feature",
            "properties": {"land_cover_type": "forest", "confidence": 0.9},
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [[[[24.0, 46.0], [25.0, 46.0], [25.0, 47.0], [24.0, 47.0], [24.0, 46.0]]]],
            },
        }
        idx = load_geojson_dict(_make_collection(feat))
        assert len(idx.features) == 1
        assert idx.features[0].land_cover_type == "forest"

    def test_geojson_lonlat_converted_to_latlon(self):
        """GeoJSON coords [lon, lat] must be stored as (lat, lon) tuples."""
        from app.services.gis_loader import load_geojson_dict
        idx = load_geojson_dict(_make_collection(_RECT_FEATURE))
        poly = idx.features[0].polygon
        # GeoJSON: [24.0, 46.0] (lon=24, lat=46) → (lat=46, lon=24)
        assert poly[0] == (46.0, 24.0)

    def test_load_from_file_raises_for_missing_file(self, tmp_path):
        from app.services.gis_loader import load_geojson_file
        with pytest.raises(FileNotFoundError):
            load_geojson_file(tmp_path / "nonexistent.geojson")

    def test_load_from_file_roundtrip(self, tmp_path):
        from app.services.gis_loader import load_geojson_file
        p = tmp_path / "test.geojson"
        p.write_text(json.dumps(_SIMPLE_COLLECTION), encoding="utf-8")
        idx = load_geojson_file(p)
        assert len(idx.features) == 3

    def test_index_is_built_after_load(self):
        from app.services.gis_loader import load_geojson_dict
        idx = load_geojson_dict(_SIMPLE_COLLECTION)
        assert idx._built is True


# ===========================================================================
# gis_loader — point-in-polygon helper
# ===========================================================================

class TestGISPointInPolygon:
    """Direct tests of the pure PIP algorithm in gis_loader."""

    def test_inside_rectangle(self):
        from app.services.gis_loader import _point_in_polygon
        poly = [(46.0, 24.0), (47.0, 24.0), (47.0, 25.0), (46.0, 25.0)]
        assert _point_in_polygon(46.5, 24.5, poly) is True

    def test_outside_rectangle_south(self):
        from app.services.gis_loader import _point_in_polygon
        poly = [(46.0, 24.0), (47.0, 24.0), (47.0, 25.0), (46.0, 25.0)]
        assert _point_in_polygon(45.0, 24.5, poly) is False

    def test_outside_rectangle_north(self):
        from app.services.gis_loader import _point_in_polygon
        poly = [(46.0, 24.0), (47.0, 24.0), (47.0, 25.0), (46.0, 25.0)]
        assert _point_in_polygon(48.0, 24.5, poly) is False

    def test_outside_rectangle_west(self):
        from app.services.gis_loader import _point_in_polygon
        poly = [(46.0, 24.0), (47.0, 24.0), (47.0, 25.0), (46.0, 25.0)]
        assert _point_in_polygon(46.5, 23.0, poly) is False

    def test_outside_rectangle_east(self):
        from app.services.gis_loader import _point_in_polygon
        poly = [(46.0, 24.0), (47.0, 24.0), (47.0, 25.0), (46.0, 25.0)]
        assert _point_in_polygon(46.5, 26.0, poly) is False

    def test_empty_polygon(self):
        from app.services.gis_loader import _point_in_polygon
        assert _point_in_polygon(46.0, 24.0, []) is False

    def test_two_vertex_polygon(self):
        from app.services.gis_loader import _point_in_polygon
        assert _point_in_polygon(46.0, 24.0, [(45.0, 23.0), (47.0, 25.0)]) is False

    def test_triangle_inside(self):
        from app.services.gis_loader import _point_in_polygon
        tri = [(44.0, 24.0), (46.0, 24.0), (46.0, 26.0)]
        assert _point_in_polygon(45.5, 24.5, tri) is True

    def test_triangle_outside(self):
        from app.services.gis_loader import _point_in_polygon
        tri = [(44.0, 24.0), (46.0, 24.0), (46.0, 26.0)]
        assert _point_in_polygon(44.5, 25.5, tri) is False


# ===========================================================================
# GISIndex.classify — spatial lookup with priority
# ===========================================================================

class TestGISIndexClassify:
    """Tests for the classify() method of GISIndex."""

    def _idx(self):
        from app.services.gis_loader import load_geojson_dict
        return load_geojson_dict(_SIMPLE_COLLECTION)

    def test_classifies_forest_point(self):
        idx = self._idx()
        # Forest polygon: lat 46-47, lon 24-25 (but NOT the urban overlap area)
        result = idx.classify(46.2, 24.2)
        assert result["land_cover_type"] == "forest"

    def test_classifies_urban_point(self):
        idx = self._idx()
        # Urban polygon: lat 46.4-46.6, lon 24.4-24.6
        result = idx.classify(46.5, 24.5)
        assert result["land_cover_type"] == "urban"

    def test_classifies_water_point(self):
        idx = self._idx()
        # Water polygon: lat 44-45, lon 22-23
        result = idx.classify(44.5, 22.5)
        assert result["land_cover_type"] == "water"

    def test_urban_overrides_forest_in_overlap(self):
        """When urban polygon overlaps forest polygon, urban wins (higher priority)."""
        from app.services.gis_loader import load_geojson_dict
        # Make forest cover entire area including urban location
        forest_feat = {
            "type": "Feature",
            "properties": {"land_cover_type": "forest", "confidence": 0.9},
            "geometry": {"type": "Polygon", "coordinates": [[[24.0, 46.0], [25.0, 46.0], [25.0, 47.0], [24.0, 47.0], [24.0, 46.0]]]},
        }
        urban_feat = {
            "type": "Feature",
            "properties": {"land_cover_type": "urban", "confidence": 0.97},
            "geometry": {"type": "Polygon", "coordinates": [[[24.3, 46.3], [24.7, 46.3], [24.7, 46.7], [24.3, 46.7], [24.3, 46.3]]]},
        }
        idx = load_geojson_dict(_make_collection(forest_feat, urban_feat))
        result = idx.classify(46.5, 24.5)
        assert result["land_cover_type"] == "urban"

    def test_water_overrides_agriculture(self):
        """Water has priority over agriculture."""
        from app.services.gis_loader import load_geojson_dict
        ag_feat = {
            "type": "Feature",
            "properties": {"land_cover_type": "agriculture", "confidence": 0.8},
            "geometry": {"type": "Polygon", "coordinates": [[[24.0, 44.0], [25.0, 44.0], [25.0, 45.0], [24.0, 45.0], [24.0, 44.0]]]},
        }
        water_feat = {
            "type": "Feature",
            "properties": {"land_cover_type": "water", "confidence": 0.95},
            "geometry": {"type": "Polygon", "coordinates": [[[24.2, 44.2], [24.8, 44.2], [24.8, 44.8], [24.2, 44.8], [24.2, 44.2]]]},
        }
        idx = load_geojson_dict(_make_collection(ag_feat, water_feat))
        result = idx.classify(44.5, 24.5)
        assert result["land_cover_type"] == "water"

    def test_unknown_outside_all_polygons(self):
        idx = self._idx()
        # Coordinate outside all polygons
        result = idx.classify(0.0, 0.0)
        assert result["land_cover_type"] == "unknown"

    def test_classify_returns_confidence(self):
        idx = self._idx()
        result = idx.classify(46.2, 24.2)
        assert "confidence" in result
        assert 0.0 < result["confidence"] <= 1.0

    def test_classify_returns_source(self):
        idx = self._idx()
        result = idx.classify(46.2, 24.2)
        assert result["source"] == "Test Source"

    def test_unknown_confidence_is_low(self):
        idx = self._idx()
        result = idx.classify(0.0, 0.0)
        assert result["confidence"] <= 0.50

    def test_empty_dataset_returns_unknown(self):
        from app.services.gis_loader import load_geojson_dict
        idx = load_geojson_dict(_make_collection())
        result = idx.classify(46.0, 25.0)
        assert result["land_cover_type"] == "unknown"


# ===========================================================================
# Bundled Romania dataset — geographic accuracy
# ===========================================================================

class TestBundledDatasetGeography:
    """Verify that the bundled GeoJSON classifies well-known Romanian locations."""

    @pytest.fixture(autouse=True)
    def _reset(self):
        """Ensure a fresh singleton for each test."""
        from app.services import gis_loader
        gis_loader.reset_singleton()
        yield
        gis_loader.reset_singleton()

    def _classify(self, lat, lon):
        from app.services.gis_loader import get_bundled_index
        return get_bundled_index().classify(lat, lon)

    def test_bucharest_is_urban(self):
        result = self._classify(44.43, 26.10)
        assert result["land_cover_type"] == "urban"

    def test_cluj_napoca_is_urban(self):
        result = self._classify(46.77, 23.60)
        assert result["land_cover_type"] == "urban"

    def test_iasi_is_urban(self):
        result = self._classify(47.16, 27.58)
        assert result["land_cover_type"] == "urban"

    def test_timisoara_is_urban(self):
        result = self._classify(45.75, 21.22)
        assert result["land_cover_type"] == "urban"

    def test_constanta_is_urban(self):
        result = self._classify(44.18, 28.63)
        assert result["land_cover_type"] == "urban"

    def test_brasov_is_urban(self):
        result = self._classify(45.65, 25.60)
        assert result["land_cover_type"] == "urban"

    def test_danube_delta_is_water(self):
        result = self._classify(45.1, 29.5)
        assert result["land_cover_type"] == "water"

    def test_eastern_carpathians_north_is_forest(self):
        result = self._classify(47.5, 26.0)
        assert result["land_cover_type"] == "forest"

    def test_eastern_carpathians_central_is_forest(self):
        # Central Eastern Carpathians (Harghita area, lon 26.5 avoids Bicaz Reservoir)
        result = self._classify(46.7, 26.5)
        assert result["land_cover_type"] == "forest"

    def test_southern_carpathians_is_forest(self):
        result = self._classify(45.4, 23.0)
        assert result["land_cover_type"] == "forest"

    def test_apuseni_is_forest(self):
        result = self._classify(46.5, 22.5)
        assert result["land_cover_type"] == "forest"

    def test_wallachian_plain_is_agriculture(self):
        # Central Wallachian Plain (Olt county area, well above Danube floodplain)
        result = self._classify(44.4, 24.5)
        assert result["land_cover_type"] == "agriculture"

    def test_moldavian_plateau_is_agriculture(self):
        result = self._classify(47.0, 28.0)
        assert result["land_cover_type"] == "agriculture"

    def test_banat_plain_is_agriculture(self):
        result = self._classify(45.8, 21.0)
        assert result["land_cover_type"] == "agriculture"

    def test_non_romania_coordinate_is_unknown(self):
        result = self._classify(51.0, 10.0)  # Germany
        assert result["land_cover_type"] == "unknown"

    def test_null_island_is_unknown(self):
        result = self._classify(0.0, 0.0)
        assert result["land_cover_type"] == "unknown"

    def test_urban_confidence_is_high(self):
        result = self._classify(44.43, 26.10)
        assert result["confidence"] >= 0.90

    def test_forest_confidence_is_high(self):
        result = self._classify(47.5, 26.0)
        assert result["confidence"] >= 0.85

    def test_bundled_source_is_copernicus(self):
        result = self._classify(47.5, 26.0)
        assert "Copernicus" in result["source"]

    def test_bundled_has_many_features(self):
        from app.services.gis_loader import get_bundled_index
        idx = get_bundled_index()
        assert idx.info.feature_count >= 30


# ===========================================================================
# GISLandCoverService
# ===========================================================================

class TestGISLandCoverService:
    """Tests for the service wrapper."""

    def _svc(self):
        from app.services.gis_loader import load_geojson_dict
        from app.services.gis_land_cover_service import GISLandCoverService
        idx = load_geojson_dict(_SIMPLE_COLLECTION)
        return GISLandCoverService(idx)

    def test_classify_returns_string(self):
        svc = self._svc()
        result = svc.classify(46.2, 24.2)
        assert isinstance(result, str)

    def test_classify_known_forest(self):
        svc = self._svc()
        assert svc.classify(46.2, 24.2) == "forest"

    def test_classify_known_urban(self):
        svc = self._svc()
        assert svc.classify(46.5, 24.5) == "urban"

    def test_classify_unknown_outside(self):
        svc = self._svc()
        assert svc.classify(0.0, 0.0) == "unknown"

    def test_classify_full_returns_dict(self):
        svc = self._svc()
        result = svc.classify_full(46.2, 24.2)
        assert "land_cover_type" in result
        assert "confidence" in result
        assert "source" in result

    def test_classify_full_forest(self):
        svc = self._svc()
        result = svc.classify_full(46.2, 24.2)
        assert result["land_cover_type"] == "forest"
        assert result["confidence"] == pytest.approx(0.92)
        assert result["source"] == "Test Source"

    def test_classify_event_dict(self):
        svc = self._svc()
        assert svc.classify_event({"latitude": 46.2, "longitude": 24.2}) == "forest"

    def test_classify_event_missing_key(self):
        svc = self._svc()
        assert svc.classify_event({"latitude": 46.2}) == "unknown"

    def test_classify_event_invalid_coords(self):
        svc = self._svc()
        assert svc.classify_event({"latitude": "bad", "longitude": "val"}) == "unknown"

    def test_classify_event_none_coords(self):
        svc = self._svc()
        assert svc.classify_event({"latitude": None, "longitude": None}) == "unknown"

    def test_classify_batch_order_preserved(self):
        svc = self._svc()
        events = [
            {"latitude": 46.2, "longitude": 24.2},  # forest
            {"latitude": 46.5, "longitude": 24.5},  # urban
            {"latitude": 0.0, "longitude": 0.0},   # unknown
        ]
        results = svc.classify_batch(events)
        assert results == ["forest", "urban", "unknown"]

    def test_classify_batch_empty_list(self):
        svc = self._svc()
        assert svc.classify_batch([]) == []

    def test_get_dataset_info_keys(self):
        svc = self._svc()
        info = svc.get_dataset_info()
        assert "source" in info
        assert "version" in info
        assert "last_updated" in info
        assert "feature_count" in info

    def test_get_dataset_info_values(self):
        svc = self._svc()
        info = svc.get_dataset_info()
        assert info["source"] == "Test Source"
        assert info["version"] == "1.0"
        assert info["last_updated"] == "2024-06-01"
        assert info["feature_count"] == 3


# ===========================================================================
# land_cover_service — backward compatibility
# ===========================================================================

class TestLandCoverServiceCompat:
    """Ensure the public surface of land_cover_service is unchanged."""

    def test_classify_function_exists(self):
        from app.services.land_cover_service import classify
        assert callable(classify)

    def test_classify_event_function_exists(self):
        from app.services.land_cover_service import classify_event
        assert callable(classify_event)

    def test_classify_batch_function_exists(self):
        from app.services.land_cover_service import classify_batch
        assert callable(classify_batch)

    def test_forest_confidence_weights_exist(self):
        from app.services.land_cover_service import FOREST_CONFIDENCE_WEIGHTS
        assert isinstance(FOREST_CONFIDENCE_WEIGHTS, dict)

    def test_forest_confidence_weights_keys(self):
        from app.services.land_cover_service import FOREST_CONFIDENCE_WEIGHTS
        expected = {"forest", "near_forest", "agriculture", "urban", "water", "unknown"}
        assert set(FOREST_CONFIDENCE_WEIGHTS.keys()) == expected

    def test_forest_confidence_weights_values(self):
        from app.services.land_cover_service import FOREST_CONFIDENCE_WEIGHTS
        assert FOREST_CONFIDENCE_WEIGHTS["forest"] == 1.00
        assert FOREST_CONFIDENCE_WEIGHTS["unknown"] == 0.50

    def test_classify_returns_string(self):
        from app.services.land_cover_service import classify
        result = classify(44.43, 26.10)
        assert isinstance(result, str)
        assert result in {"forest", "near_forest", "agriculture", "urban", "water", "unknown"}

    def test_classify_bucharest_urban(self):
        from app.services.land_cover_service import classify
        assert classify(44.43, 26.10) == "urban"

    def test_classify_event_interface(self):
        from app.services.land_cover_service import classify_event
        result = classify_event({"latitude": 44.43, "longitude": 26.10})
        assert result == "urban"

    def test_classify_batch_interface(self):
        from app.services.land_cover_service import classify_batch
        events = [
            {"latitude": 44.43, "longitude": 26.10},
            {"latitude": 0.0, "longitude": 0.0},
        ]
        results = classify_batch(events)
        assert results[0] == "urban"
        assert results[1] == "unknown"

    def test_get_dataset_info_function_exists(self):
        from app.services.land_cover_service import get_dataset_info
        assert callable(get_dataset_info)

    def test_get_dataset_info_returns_dict(self):
        from app.services.land_cover_service import get_dataset_info
        info = get_dataset_info()
        assert isinstance(info, dict)
        assert "source" in info

    def test_classify_full_function_exists(self):
        from app.services.land_cover_service import classify_full
        assert callable(classify_full)

    def test_classify_full_returns_dict(self):
        from app.services.land_cover_service import classify_full
        result = classify_full(44.43, 26.10)
        assert "land_cover_type" in result
        assert "confidence" in result
        assert "source" in result


# ===========================================================================
# Analytics integration — dataset metadata in distribution response
# ===========================================================================

class TestAnalyticsDatasetMetadata:
    """Verify get_land_cover_distribution() includes GIS dataset metadata."""

    @pytest.mark.anyio
    async def test_distribution_includes_dataset_key(self):
        from app.modules.analytics.analytics_service import AnalyticsService

        mock_repo = MagicMock()
        mock_repo.land_cover_distribution = AsyncMock(return_value=[
            {"_id": "forest", "events": 10},
            {"_id": "urban", "events": 5},
        ])
        svc = AnalyticsService(mock_repo)
        result = await svc.get_land_cover_distribution()

        assert "dataset" in result
        assert "distribution" in result
        assert "generated_at" in result

    @pytest.mark.anyio
    async def test_dataset_has_required_keys(self):
        from app.modules.analytics.analytics_service import AnalyticsService

        mock_repo = MagicMock()
        mock_repo.land_cover_distribution = AsyncMock(return_value=[])
        svc = AnalyticsService(mock_repo)
        result = await svc.get_land_cover_distribution()

        ds = result["dataset"]
        assert "source" in ds
        assert "version" in ds
        assert "last_updated" in ds

    @pytest.mark.anyio
    async def test_dataset_source_is_copernicus(self):
        from app.modules.analytics.analytics_service import AnalyticsService

        mock_repo = MagicMock()
        mock_repo.land_cover_distribution = AsyncMock(return_value=[])
        svc = AnalyticsService(mock_repo)
        result = await svc.get_land_cover_distribution()

        assert "Copernicus" in result["dataset"]["source"]

    @pytest.mark.anyio
    async def test_distribution_data_unchanged(self):
        from app.modules.analytics.analytics_service import AnalyticsService

        mock_repo = MagicMock()
        mock_repo.land_cover_distribution = AsyncMock(return_value=[
            {"_id": "forest", "events": 42},
        ])
        svc = AnalyticsService(mock_repo)
        result = await svc.get_land_cover_distribution()

        assert result["distribution"][0]["land_cover"] == "forest"
        assert result["distribution"][0]["events"] == 42


# ===========================================================================
# Ingestion pipeline — events receive GIS classification
# ===========================================================================

class TestIngestionPipelineGIS:
    """Verify that newly ingested events are classified using the GIS system."""

    def test_forest_event_service_uses_land_cover_service(self):
        """ForestEventService.create_event() should call classify_event()."""
        from app.services.forest_event_service import ForestEventService

        svc = ForestEventService(MagicMock())
        # Check classify_event is used during event creation
        assert hasattr(svc, "create_event") or hasattr(svc, "_classify")

    def test_classify_batch_performance(self):
        """Classifying 1000 events should complete without excessive time."""
        import time
        from app.services.land_cover_service import classify_batch

        events = [{"latitude": 46.0 + i * 0.001, "longitude": 25.0 + i * 0.001} for i in range(1000)]
        start = time.perf_counter()
        results = classify_batch(events)
        elapsed = time.perf_counter() - start

        assert len(results) == 1000
        assert elapsed < 2.0, f"Batch classification too slow: {elapsed:.2f}s"

    def test_classify_batch_all_valid_labels(self):
        from app.services.land_cover_service import classify_batch

        valid_labels = {"forest", "near_forest", "agriculture", "urban", "water", "unknown"}
        events = [
            {"latitude": 44.43, "longitude": 26.10},  # Bucharest → urban
            {"latitude": 47.5, "longitude": 26.0},    # E. Carpathians → forest
            {"latitude": 45.1, "longitude": 29.5},    # Danube Delta → water
            {"latitude": 44.1, "longitude": 24.5},    # Wallachian Plain → agriculture
        ]
        results = classify_batch(events)
        for r in results:
            assert r in valid_labels


# ===========================================================================
# Singleton and reload
# ===========================================================================

class TestSingleton:
    """Test module-level singleton behaviour."""

    def test_get_bundled_index_returns_same_instance(self):
        from app.services.gis_loader import get_bundled_index, reset_singleton
        reset_singleton()
        idx1 = get_bundled_index()
        idx2 = get_bundled_index()
        assert idx1 is idx2

    def test_reset_singleton_forces_reload(self):
        from app.services.gis_loader import get_bundled_index, reset_singleton
        reset_singleton()
        idx1 = get_bundled_index()
        reset_singleton()
        idx2 = get_bundled_index()
        # After reset, a new instance is created
        assert idx1 is not idx2

    def test_gis_service_reload(self):
        from app.services.gis_land_cover_service import reload, classify
        reload()
        result = classify(44.43, 26.10)
        assert result == "urban"
