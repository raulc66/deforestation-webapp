"""CLMS integration tests — deterministic fixture-based (Phases 7–10)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.ecosystem.canonical_identity import spatial_key_from_region
from app.core.ecosystem.forest_context import ForestContext, forest_context_from_lookup
from app.core.ingestion.contextual_provider_contract import ContextualDatasetProvider
from app.modules.analytics.context_enrichment import (
    enrich_detection_with_forest_context,
    forest_context_for_map_payload,
)
from app.modules.analytics.detection_adapters import detection_from_anomaly_dict
from app.modules.analytics.detection_contract import Detection
from app.modules.analytics.map_contract import forest_event_map_marker
from app.services.clms_context_provider import CLMSContextProvider, CLMS_DATASET_ID
from app.core.ingestion.clms_attributes import normalize_clms_attributes
from app.modules.ingestion.providers.firms import FIRMSProvider, MOCK_FIRMS_DATA
from app.services.forest_context_service import ForestContextService
from app.services.gis_loader import load_geojson_dict
from fixtures.phase0_golden_harness import generate_golden_artifacts
from fixtures.phase0_oracle_manifest import verify_generated_match_manifest


# Carpathian forest coordinate (bundled fixture).
_FOREST_LAT, _FOREST_LNG = 47.60, 26.00
# Bucharest urban coordinate (bundled fixture).
_URBAN_LAT, _URBAN_LNG = 44.45, 26.10

_NOW = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)


class TestCLMSProviderMetadata:
    def test_implements_contextual_contract(self):
        assert isinstance(CLMSContextProvider(), ContextualDatasetProvider)

    def test_describe_includes_required_fields(self):
        desc = CLMSContextProvider().describe()
        assert desc["source"] == "Copernicus Land Monitoring Service"
        assert desc["dataset_id"] == CLMS_DATASET_ID
        assert "dataset_version" in desc
        assert "geographic_coverage" in desc
        assert "spatial_resolution" in desc
        assert desc["license"]
        assert desc["data_policy"] == "free_and_open"
        assert desc["live_access_status"] in {"bundled_fixture", "local_file"}


class TestFixtureNormalization:
    @pytest.mark.anyio
    async def test_refresh_loads_bundled_fixture(self):
        provider = CLMSContextProvider()
        report = await provider.refresh()
        assert report["status"] == "success"
        assert report["feature_count"] > 0

    def test_lookup_returns_normalized_fields(self):
        lookup = CLMSContextProvider().lookup(_FOREST_LAT, _FOREST_LNG)
        assert lookup["land_cover_type"] == "forest"
        assert lookup["dataset_id"] == CLMS_DATASET_ID
        assert lookup["provenance"] == "point_in_polygon"


class TestForestClassification:
    def test_forest_coordinate_is_forest(self):
        ctx = ForestContextService().resolve_context(_FOREST_LAT, _FOREST_LNG)
        assert ctx.is_forest is True
        assert ctx.land_cover_type == "forest"

    def test_urban_coordinate_is_non_forest(self):
        ctx = ForestContextService().resolve_context(_URBAN_LAT, _URBAN_LNG)
        assert ctx.is_forest is False
        assert ctx.land_cover_type == "urban"


class TestTreeCoverAndForestTypeNormalization:
    def test_clc_311_broadleaved_attributes(self):
        attrs = normalize_clms_attributes(land_cover_type="forest", clc_code=311)
        assert attrs["forest_type"] == "broadleaved"
        assert attrs["tree_cover_density_pct"] == 85.0

    def test_clc_312_coniferous_attributes(self):
        attrs = normalize_clms_attributes(land_cover_type="forest", clc_code=312)
        assert attrs["forest_type"] == "coniferous"
        assert attrs["dominant_leaf_type"] == "coniferous"

    def test_non_forest_zero_density(self):
        attrs = normalize_clms_attributes(land_cover_type="urban", clc_code=112)
        assert attrs["tree_cover_density_pct"] == 0.0


class TestSpatialAssociation:
    def test_context_preserves_coordinates(self):
        ctx = ForestContextService().resolve_context(_FOREST_LAT, _FOREST_LNG)
        assert ctx.latitude == _FOREST_LAT
        assert ctx.longitude == _FOREST_LNG

    def test_enrich_observation_metadata_block(self):
        svc = ForestContextService()
        meta = svc.enrich_observation_metadata({}, latitude=_FOREST_LAT, longitude=_FOREST_LNG)
        assert "forest_context" in meta
        assert meta["forest_context"]["is_forest"] is True


class TestSpatialKeyPreservation:
    def test_detection_enrichment_preserves_identity(self):
        detection = detection_from_anomaly_dict(
            {
                "region": "Suceava",
                "baseline_events": 1,
                "current_events": 5,
                "deviation_percent": 400.0,
                "anomaly_score": 0.64,
                "severity": "high",
                "latitude": _FOREST_LAT,
                "longitude": _FOREST_LNG,
            },
            detected_at=_NOW,
        )
        enriched = enrich_detection_with_forest_context(detection)
        assert enriched.identity == detection.identity
        assert enriched.score == detection.score
        assert enriched.evidence["forest_context"]["is_forest"] is True
        assert enriched.evidence["spatial_key"] == spatial_key_from_region("Suceava")


class TestProvenancePreservation:
    def test_metadata_block_roundtrip(self):
        ctx = ForestContextService().resolve_context(_FOREST_LAT, _FOREST_LNG)
        block = ctx.to_metadata_block()
        restored = ForestContext.from_metadata_block(block)
        assert restored is not None
        assert restored.source == ctx.source
        assert restored.dataset_id == ctx.dataset_id
        assert restored.provenance == "point_in_polygon"


class TestFirmsClmsEnrichment:
    def test_firms_normalize_does_not_create_forest_event_from_clms(self):
        """CLMS context enriches observations — FIRMS still produces wildfire events only."""
        provider = FIRMSProvider()
        payload = provider.normalize(MOCK_FIRMS_DATA[0])
        assert payload.event_type == "wildfire"

    def test_firms_plus_clms_context_path(self):
        firms = FIRMSProvider().normalize(MOCK_FIRMS_DATA[0])
        svc = ForestContextService()
        meta = svc.enrich_observation_metadata(
            firms.metadata,
            latitude=firms.latitude,
            longitude=firms.longitude,
        )
        assert meta["forest_context"]["source"] == "Copernicus Land Monitoring Service"
        assert "is_forest" in meta["forest_context"]


class TestCategoryIsolation:
    def test_clms_context_does_not_set_incident_category(self):
        ctx = ForestContextService().resolve_context(_FOREST_LAT, _FOREST_LNG)
        block = ctx.to_metadata_block()
        assert "incident_category" not in block


class TestMapPayloadCompatibility:
    def test_forest_event_map_marker_includes_forest_context(self):
        marker = forest_event_map_marker(
            {
                "latitude": _FOREST_LAT,
                "longitude": _FOREST_LNG,
                "region": "Suceava",
                "event_type": "wildfire",
                "metadata": {},
            }
        )
        assert "forest_context" in marker
        assert marker["forest_context"]["is_forest"] is True

    def test_map_summary_from_coordinates(self):
        summary = forest_context_for_map_payload(latitude=_URBAN_LAT, longitude=_URBAN_LNG)
        assert summary is not None
        assert summary["is_forest"] is False


class TestInvalidMissingValues:
    def test_unknown_coordinate_returns_unknown_context(self):
        ctx = ForestContextService().resolve_context(10.0, 10.0)
        assert ctx.land_cover_type == "unknown"
        assert ctx.is_forest is False

    def test_custom_fixture_missing_properties(self):
        data = {
            "type": "FeatureCollection",
            "properties": {"source": "test", "version": "v0", "last_updated": "2024-01-01"},
            "features": [
                {
                    "type": "Feature",
                    "properties": {"land_cover_type": "forest", "confidence": 0.9},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[25.9, 47.5], [26.1, 47.5], [26.1, 47.7], [25.9, 47.7], [25.9, 47.5]]],
                    },
                }
            ],
        }
        index = load_geojson_dict(data)
        result = index.classify_detailed(47.6, 26.0)
        assert result["land_cover_type"] == "forest"


class TestDatasetVersionReproducibility:
    @pytest.mark.anyio
    async def test_refresh_report_includes_version(self):
        provider = CLMSContextProvider()
        report = await provider.refresh()
        assert "dataset_version" in report
        desc = provider.describe()
        assert desc["dataset_version"] == report["dataset_version"]


class TestPhase0WildfireCompatibility:
    def test_oracle_artifacts_match_manifest(self):
        verify_generated_match_manifest(generate_golden_artifacts())

    def test_detection_without_coords_unchanged(self):
        detection = detection_from_anomaly_dict(
            {
                "region": "Suceava",
                "baseline_events": 1,
                "current_events": 5,
                "deviation_percent": 400.0,
                "anomaly_score": 0.64,
                "severity": "high",
            },
            detected_at=_NOW,
        )
        enriched = enrich_detection_with_forest_context(detection)
        assert enriched == detection


class TestSchedulerRefreshSemantics:
    @pytest.mark.anyio
    async def test_refresh_if_stale_skips_within_interval(self):
        svc = ForestContextService(refresh_interval_days=30)
        first = await svc.refresh_if_stale()
        second = await svc.refresh_if_stale()
        assert first is not None
        assert second is None
