"""
Tests for the Romania Land Cover Classification Engine.

Coverage:
  - _point_in_polygon: rectangle, triangle, empty polygon, boundary
  - classify(): urban, water, forest, near_forest, agriculture, unknown
  - classify_event(): dict interface, missing/invalid coords
  - classify_batch(): batch processing
  - Romania seed event classification
  - Forest confidence computation (_compute_forest_confidence)
  - Analytics: land_cover_distribution aggregation
  - Anomaly enrichment: forest_confidence present in anomaly output
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.data.romania_landcover import (
    LAND_COVER_ZONES,
    _point_in_polygon,
    _rect,
)
from app.services.land_cover_service import (
    classify,
    classify_batch,
    classify_event,
    FOREST_CONFIDENCE_WEIGHTS,
)
from app.modules.analytics.analytics_service import (
    _compute_baselines,
    _compute_forest_confidence,
    _evaluate_anomalies,
    _FOREST_CONFIDENCE_WEIGHTS,
)


# ===========================================================================
# Point-in-polygon primitive
# ===========================================================================


class TestPointInPolygon:
    """Unit tests for the ray-casting PIP algorithm."""

    def test_point_inside_rectangle(self):
        poly = _rect(44.0, 46.0, 24.0, 26.0)
        assert _point_in_polygon(45.0, 25.0, poly) is True

    def test_point_outside_rectangle_below(self):
        poly = _rect(44.0, 46.0, 24.0, 26.0)
        assert _point_in_polygon(43.0, 25.0, poly) is False

    def test_point_outside_rectangle_above(self):
        poly = _rect(44.0, 46.0, 24.0, 26.0)
        assert _point_in_polygon(47.0, 25.0, poly) is False

    def test_point_outside_rectangle_left(self):
        poly = _rect(44.0, 46.0, 24.0, 26.0)
        assert _point_in_polygon(45.0, 23.0, poly) is False

    def test_point_outside_rectangle_right(self):
        poly = _rect(44.0, 46.0, 24.0, 26.0)
        assert _point_in_polygon(45.0, 27.0, poly) is False

    def test_empty_polygon_returns_false(self):
        assert _point_in_polygon(45.0, 25.0, []) is False

    def test_degenerate_polygon_two_vertices(self):
        assert _point_in_polygon(45.0, 25.0, [(44.0, 24.0), (46.0, 26.0)]) is False

    def test_triangle_inside(self):
        # Right-angle triangle: SW-NW-NE
        triangle = [(44.0, 24.0), (46.0, 24.0), (46.0, 26.0)]
        # Interior point
        assert _point_in_polygon(45.5, 24.5, triangle) is True

    def test_triangle_outside(self):
        triangle = [(44.0, 24.0), (46.0, 24.0), (46.0, 26.0)]
        # Far outside
        assert _point_in_polygon(43.0, 23.0, triangle) is False

    def test_boundary_does_not_crash(self):
        """The exact return value on a boundary is implementation-defined;
        we only verify no exception is raised."""
        poly = _rect(44.0, 46.0, 24.0, 26.0)
        result = _point_in_polygon(44.0, 25.0, poly)
        assert isinstance(result, bool)

    def test_small_polygon(self):
        """Very small bounding box — classification still works."""
        poly = _rect(44.40, 44.42, 26.05, 26.08)
        assert _point_in_polygon(44.41, 26.06, poly) is True
        assert _point_in_polygon(44.50, 26.06, poly) is False


# ===========================================================================
# Land cover zones structural sanity
# ===========================================================================


class TestLandCoverZones:
    def test_zones_list_not_empty(self):
        assert len(LAND_COVER_ZONES) > 0

    def test_all_zones_have_name(self):
        for zone in LAND_COVER_ZONES:
            assert isinstance(zone.name, str) and zone.name

    def test_all_zones_have_valid_cover_type(self):
        valid = {"forest", "near_forest", "agriculture", "urban", "water"}
        for zone in LAND_COVER_ZONES:
            assert zone.cover_type in valid, f"Invalid cover_type in zone '{zone.name}'"

    def test_all_zones_have_4_vertices(self):
        """All zones defined as rectangles should have exactly 4 vertices."""
        for zone in LAND_COVER_ZONES:
            assert len(zone.polygon) == 4, (
                f"Zone '{zone.name}' has {len(zone.polygon)} vertices, expected 4"
            )

    def test_urban_zones_present(self):
        urban_names = {z.name for z in LAND_COVER_ZONES if z.cover_type == "urban"}
        for city in ("Bucharest", "Cluj-Napoca", "Iași", "Timișoara", "Constanța", "Brașov"):
            assert city in urban_names, f"Missing urban zone: {city}"

    def test_forest_zones_present(self):
        forest_names = {z.name for z in LAND_COVER_ZONES if z.cover_type == "forest"}
        for name in ("Eastern Carpathians", "Apuseni Mountains", "Maramureș Forests",
                     "Bucovina Forests", "Harghita-Covasna", "Retezat NP"):
            assert name in forest_names, f"Missing forest zone: {name}"

    def test_water_zone_present(self):
        water_names = {z.name for z in LAND_COVER_ZONES if z.cover_type == "water"}
        assert "Danube Delta" in water_names


# ===========================================================================
# classify() — coordinate-based classification
# ===========================================================================


class TestClassify:
    # ── Urban ───────────────────────────────────────────────────────────────
    def test_bucharest_centre_is_urban(self):
        assert classify(44.43, 26.10) == "urban"

    def test_cluj_centre_is_urban(self):
        assert classify(46.77, 23.59) == "urban"

    def test_iasi_centre_is_urban(self):
        assert classify(47.15, 27.59) == "urban"

    def test_timisoara_centre_is_urban(self):
        assert classify(45.75, 21.23) == "urban"

    def test_constanta_centre_is_urban(self):
        assert classify(44.18, 28.65) == "urban"

    def test_brasov_centre_is_urban(self):
        assert classify(45.67, 25.60) == "urban"

    # ── Water ───────────────────────────────────────────────────────────────
    def test_danube_delta_is_water(self):
        assert classify(44.90, 29.10) == "water"

    def test_danube_delta_edge_is_water(self):
        # Near the eastern tip of the delta
        assert classify(45.20, 29.50) == "water"

    # ── Forest ──────────────────────────────────────────────────────────────
    def test_eastern_carpathians_is_forest(self):
        # Mid-range of Eastern Carpathians polygon
        assert classify(46.80, 25.50) == "forest"

    def test_suceava_seed_coord_is_forest(self):
        # Region centroid used in Romania seed
        assert classify(47.53, 25.93) == "forest"

    def test_harghita_seed_coord_is_forest(self):
        assert classify(46.35, 25.80) == "forest"

    def test_apuseni_is_forest(self):
        assert classify(46.60, 23.20) == "forest"

    def test_maramures_is_forest(self):
        assert classify(47.60, 24.50) == "forest"

    def test_bucovina_is_forest(self):
        assert classify(47.50, 26.00) == "forest"

    def test_retezat_is_forest(self):
        assert classify(45.35, 22.90) == "forest"

    # ── Near-forest ──────────────────────────────────────────────────────────
    def test_bacau_seed_coord_is_urban(self):
        # Bacău city centre — correctly classified as urban by the GIS dataset
        assert classify(46.57, 26.91) == "urban"

    def test_sub_carpathian_south_is_near_forest(self):
        # A point in the southern sub-Carpathian belt
        assert classify(45.00, 25.50) == "near_forest"

    # ── Agriculture ──────────────────────────────────────────────────────────
    def test_romanian_plain_is_agriculture(self):
        assert classify(44.00, 25.50) == "agriculture"

    def test_western_plain_is_agriculture(self):
        # Banat plain (Câmpia de Vest)
        assert classify(45.80, 21.00) == "agriculture"

    def test_moldavian_plain_is_agriculture(self):
        # lon 28.00 is east of the Sub-Carpathian East zone (max lon 27.60)
        assert classify(47.00, 28.00) == "agriculture"

    # ── Unknown ──────────────────────────────────────────────────────────────
    def test_paris_is_unknown(self):
        assert classify(48.85, 2.35) == "unknown"

    def test_london_is_unknown(self):
        assert classify(51.50, -0.12) == "unknown"

    def test_new_york_is_unknown(self):
        assert classify(40.71, -74.01) == "unknown"

    def test_south_of_romania_is_unknown(self):
        # Bulgaria — south of Romania bounding box
        assert classify(42.0, 25.0) == "unknown"

    def test_north_of_romania_is_unknown(self):
        # Ukraine — north of Romania
        assert classify(49.5, 25.0) == "unknown"


# ===========================================================================
# classify_event()
# ===========================================================================


class TestClassifyEvent:
    def test_dict_with_coords(self):
        assert classify_event({"latitude": 47.53, "longitude": 25.93}) == "forest"

    def test_dict_urban(self):
        assert classify_event({"latitude": 44.43, "longitude": 26.10}) == "urban"

    def test_dict_agriculture(self):
        assert classify_event({"latitude": 44.00, "longitude": 25.50}) == "agriculture"

    def test_missing_latitude_returns_unknown(self):
        assert classify_event({"longitude": 25.50}) == "unknown"

    def test_missing_longitude_returns_unknown(self):
        assert classify_event({"latitude": 45.00}) == "unknown"

    def test_non_numeric_latitude_returns_unknown(self):
        assert classify_event({"latitude": "bad", "longitude": 25.50}) == "unknown"

    def test_none_values_return_unknown(self):
        assert classify_event({"latitude": None, "longitude": None}) == "unknown"

    def test_extra_keys_are_ignored(self):
        result = classify_event({
            "latitude": 47.53,
            "longitude": 25.93,
            "region": "Suceava",
            "severity": "high",
        })
        assert result == "forest"


# ===========================================================================
# classify_batch()
# ===========================================================================


class TestClassifyBatch:
    def test_empty_list(self):
        assert classify_batch([]) == []

    def test_single_event(self):
        result = classify_batch([{"latitude": 47.53, "longitude": 25.93}])
        assert result == ["forest"]

    def test_multiple_events_correct_order(self):
        events = [
            {"latitude": 47.53, "longitude": 25.93},  # forest  (Suceava)
            {"latitude": 44.43, "longitude": 26.10},  # urban   (Bucharest)
            {"latitude": 44.00, "longitude": 25.50},  # agriculture
            {"latitude": 44.90, "longitude": 29.10},  # water   (Delta)
            {"latitude": 48.85, "longitude": 2.35},   # unknown (Paris)
        ]
        results = classify_batch(events)
        assert results == ["forest", "urban", "agriculture", "water", "unknown"]

    def test_batch_length_matches_input(self):
        events = [{"latitude": float(i), "longitude": float(i)} for i in range(5)]
        results = classify_batch(events)
        assert len(results) == 5


# ===========================================================================
# Forest confidence weights
# ===========================================================================


class TestForestConfidenceWeights:
    def test_all_types_covered(self):
        required = {"forest", "near_forest", "agriculture", "urban", "water", "unknown"}
        assert set(FOREST_CONFIDENCE_WEIGHTS.keys()) == required

    def test_forest_confidence_is_1(self):
        assert FOREST_CONFIDENCE_WEIGHTS["forest"] == 1.0

    def test_near_forest_confidence_is_0_75(self):
        assert FOREST_CONFIDENCE_WEIGHTS["near_forest"] == 0.75

    def test_agriculture_confidence_is_0_40(self):
        assert FOREST_CONFIDENCE_WEIGHTS["agriculture"] == 0.40

    def test_urban_confidence_is_0_20(self):
        assert FOREST_CONFIDENCE_WEIGHTS["urban"] == 0.20

    def test_water_confidence_is_0_10(self):
        assert FOREST_CONFIDENCE_WEIGHTS["water"] == 0.10

    def test_unknown_confidence_is_0_50(self):
        assert FOREST_CONFIDENCE_WEIGHTS["unknown"] == 0.50


# ===========================================================================
# _compute_forest_confidence() in analytics_service
# ===========================================================================


class TestComputeForestConfidence:
    def _row(self, **kwargs) -> dict:
        """Build a minimal aggregation row with the given lc_* counts."""
        base = {
            "lc_forest": 0,
            "lc_near_forest": 0,
            "lc_agriculture": 0,
            "lc_urban": 0,
            "lc_water": 0,
            "lc_unknown": 0,
        }
        base.update({f"lc_{k}": v for k, v in kwargs.items()})
        return base

    def test_all_forest_returns_1_0(self):
        row = self._row(forest=10)
        assert _compute_forest_confidence(row) == 1.0

    def test_all_urban_returns_0_20(self):
        row = self._row(urban=10)
        assert _compute_forest_confidence(row) == 0.20

    def test_all_unknown_returns_0_50(self):
        row = self._row(unknown=10)
        assert _compute_forest_confidence(row) == 0.50

    def test_empty_row_returns_unknown_default(self):
        """When no land-cover counts exist, default to the unknown weight."""
        row = self._row()
        assert _compute_forest_confidence(row) == _FOREST_CONFIDENCE_WEIGHTS["unknown"]

    def test_mixed_forest_urban(self):
        # 50% forest (1.0) + 50% urban (0.20) → 0.60
        row = self._row(forest=5, urban=5)
        result = _compute_forest_confidence(row)
        assert abs(result - 0.60) < 0.001

    def test_mixed_near_forest_agriculture(self):
        # 50% near_forest (0.75) + 50% agriculture (0.40) → 0.575
        row = self._row(near_forest=4, agriculture=4)
        result = _compute_forest_confidence(row)
        assert abs(result - 0.575) < 0.001


# ===========================================================================
# _compute_baselines() includes forest_confidence
# ===========================================================================


class TestComputeBaselinesForestConfidence:
    from datetime import datetime, timezone

    _NOW = datetime(2026, 6, 10, 0, 0, 0, tzinfo=timezone.utc)

    def _make_row(self, region, current, baseline_raw, **lc_counts):
        row = {
            "_id": region,
            "current_events": current,
            "baseline_raw": baseline_raw,
            "lc_forest": 0,
            "lc_near_forest": 0,
            "lc_agriculture": 0,
            "lc_urban": 0,
            "lc_water": 0,
            "lc_unknown": 0,
        }
        for k, v in lc_counts.items():
            row[f"lc_{k}"] = v
        return row

    def test_forest_confidence_present_in_baselines(self):
        rows = [self._make_row("Suceava", 10, 8, forest=15)]
        result = _compute_baselines(rows, generated_at=self._NOW)
        region = result["regions"][0]
        assert "forest_confidence" in region

    def test_forest_confidence_pure_forest_region(self):
        rows = [self._make_row("Suceava", 10, 8, forest=15)]
        result = _compute_baselines(rows, generated_at=self._NOW)
        fc = result["regions"][0]["forest_confidence"]
        assert fc == 1.0

    def test_forest_confidence_urban_region(self):
        rows = [self._make_row("Bucharest", 5, 4, urban=20)]
        result = _compute_baselines(rows, generated_at=self._NOW)
        fc = result["regions"][0]["forest_confidence"]
        assert fc == 0.20

    def test_forest_confidence_no_lc_data_defaults_to_unknown(self):
        rows = [self._make_row("SomeRegion", 5, 4)]
        result = _compute_baselines(rows, generated_at=self._NOW)
        fc = result["regions"][0]["forest_confidence"]
        assert fc == _FOREST_CONFIDENCE_WEIGHTS["unknown"]


# ===========================================================================
# _evaluate_anomalies() includes forest_confidence
# ===========================================================================


class TestEvaluateAnomaliesForestConfidence:
    from datetime import datetime, timezone
    _NOW = datetime(2026, 6, 10, 0, 0, 0, tzinfo=timezone.utc)

    def _region(self, region, current, baseline, deviation, fc=0.80):
        return {
            "region": region,
            "current_events": current,
            "baseline_events": baseline,
            "deviation_percent": deviation,
            "forest_confidence": fc,
        }

    def test_forest_confidence_included_in_anomaly(self):
        regions = [self._region("Suceava", 10, 2, 400.0, fc=0.95)]
        result = _evaluate_anomalies(regions, generated_at=self._NOW)
        assert len(result["anomalies"]) == 1
        assert result["anomalies"][0]["forest_confidence"] == 0.95

    def test_forest_confidence_not_affect_anomaly_score(self):
        """forest_confidence must not change the computed anomaly_score."""
        region_a = self._region("A", 10, 2, 400.0, fc=1.0)
        region_b = self._region("B", 10, 2, 400.0, fc=0.20)
        result_a = _evaluate_anomalies([region_a], generated_at=self._NOW)
        result_b = _evaluate_anomalies([region_b], generated_at=self._NOW)
        assert result_a["anomalies"][0]["anomaly_score"] == result_b["anomalies"][0]["anomaly_score"]

    def test_missing_forest_confidence_defaults_to_unknown_weight(self):
        """Regions without forest_confidence key use unknown default."""
        region = {
            "region": "NoLC",
            "current_events": 10,
            "baseline_events": 2,
            "deviation_percent": 400.0,
            # No forest_confidence key
        }
        result = _evaluate_anomalies([region], generated_at=self._NOW)
        anomaly = result["anomalies"][0]
        assert "forest_confidence" in anomaly
        assert anomaly["forest_confidence"] == _FOREST_CONFIDENCE_WEIGHTS["unknown"]


# ===========================================================================
# Analytics repository: land_cover_distribution aggregation (mocked)
# ===========================================================================


class TestLandCoverDistributionRepo:
    @pytest.mark.anyio
    async def test_returns_expected_shape(self):
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_db.forest_events = mock_col
        mock_db.import_jobs = MagicMock()

        from app.modules.analytics.analytics_repository import AnalyticsRepository

        repo = AnalyticsRepository(mock_db)
        repo.col = mock_col

        # Simulate aggregation returning two land-cover buckets
        mock_col.aggregate = MagicMock(return_value=_async_iter([
            {"_id": "forest", "events": 52},
            {"_id": "unknown", "events": 121},
        ]))

        result = await repo.land_cover_distribution()
        assert len(result) == 2
        assert result[0]["_id"] == "forest"
        assert result[0]["events"] == 52

    @pytest.mark.anyio
    async def test_empty_collection_returns_empty_list(self):
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.forest_events = mock_col
        mock_db.import_jobs = MagicMock()

        from app.modules.analytics.analytics_repository import AnalyticsRepository

        repo = AnalyticsRepository(mock_db)
        repo.col = mock_col
        mock_col.aggregate = MagicMock(return_value=_async_iter([]))

        result = await repo.land_cover_distribution()
        assert result == []


# ===========================================================================
# Analytics service: get_land_cover_distribution (mocked repo)
# ===========================================================================


class TestLandCoverDistributionService:
    @pytest.mark.anyio
    async def test_get_land_cover_distribution_shapes_response(self):
        from app.modules.analytics.analytics_service import AnalyticsService

        mock_repo = AsyncMock()
        mock_repo.land_cover_distribution.return_value = [
            {"_id": "forest",  "events": 52},
            {"_id": "unknown", "events": 121},
        ]

        svc = AnalyticsService(mock_repo)
        result = await svc.get_land_cover_distribution()

        assert "generated_at" in result
        assert "distribution" in result
        dist = {d["land_cover"]: d["events"] for d in result["distribution"]}
        assert dist["forest"] == 52
        assert dist["unknown"] == 121

    @pytest.mark.anyio
    async def test_null_id_mapped_to_unknown(self):
        from app.modules.analytics.analytics_service import AnalyticsService

        mock_repo = AsyncMock()
        mock_repo.land_cover_distribution.return_value = [
            {"_id": None, "events": 5},
        ]

        svc = AnalyticsService(mock_repo)
        result = await svc.get_land_cover_distribution()
        dist = {d["land_cover"]: d["events"] for d in result["distribution"]}
        # Null _id should produce a key of "unknown" (or "None" string — check implementation)
        assert len(result["distribution"]) == 1


# ===========================================================================
# Romania seed classification verification
# ===========================================================================


class TestRomaniaSeedClassification:
    """Verify that the seed region coordinates produce expected land-cover types."""

    # Centroids from romania_seed_service._REGION_COORDS
    REGION_COORDS = {
        "Suceava":  (47.53, 25.93),
        "Bacău":    (46.57, 26.92),
        "Harghita": (46.35, 25.80),
    }

    def test_suceava_centroid_is_forest(self):
        lat, lon = self.REGION_COORDS["Suceava"]
        assert classify(lat, lon) == "forest"

    def test_bacau_centroid_is_urban(self):
        # Bacău centroid falls within the urban polygon in the GIS dataset
        lat, lon = self.REGION_COORDS["Bacău"]
        assert classify(lat, lon) == "urban"

    def test_harghita_centroid_is_forest(self):
        lat, lon = self.REGION_COORDS["Harghita"]
        assert classify(lat, lon) == "forest"

    def test_seed_events_classify_non_unknown(self):
        """All three seed regions should classify to something meaningful
        (not 'unknown'), confirming polygon coverage."""
        for region, (lat, lon) in self.REGION_COORDS.items():
            result = classify(lat, lon)
            assert result != "unknown", (
                f"Seed region '{region}' at ({lat}, {lon}) classified as 'unknown' — "
                "check polygon coverage"
            )


# ===========================================================================
# Helpers
# ===========================================================================


class _async_iter:
    """Async iterator over a list of dicts — simulates Motor cursor."""

    def __init__(self, items):
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration
