"""Map scope contract — geographic scope, coordinates, and endpoint semantics."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import (
    analytics_service_dep,
    aoi_enrichment_service_dep,
    forest_event_service_dep,
    get_current_user,
    get_organization_context,
    intelligence_events_service_dep,
    monitoring_area_service_dep,
)
from app.core.organization.organization_context import OrganizationContext
from app.api.event_routes import router as events_router
from app.core.geography.geographic_scope import GeographicScope, GeographicScopePolicy
from app.modules.analytics.analytics_routes import router as analytics_router
from app.modules.analytics.map_contract import forest_event_map_marker
from fixtures.multi_region_operational_fixture import build_multi_region_events, events_in_scope


def _event_with_id(event: dict, event_id: str) -> dict:
    return {**event, "id": event_id}


def _scoped_forest_events(scope: str) -> list[dict]:
    return [
        _event_with_id(e, f"evt-{e['country']}-{e['region']}")
        for e in events_in_scope(build_multi_region_events(), scope)
    ]


def _map_overlay_client(*, scope: str, forest_events: list[dict] | None = None):
    events = forest_events if forest_events is not None else _scoped_forest_events(scope)
    policy = GeographicScopePolicy(GeographicScope(scope))
    mock_analytics = MagicMock()
    mock_repo = MagicMock()
    mock_repo.list_scoped_events_for_map = AsyncMock(return_value=events)
    mock_repo.region_event_centroids = AsyncMock(return_value={"Suceava": (47.6353, 26.259)})
    mock_repo.scope_policy = policy
    mock_analytics.repo = mock_repo
    mock_analytics.geographic_scope = scope
    mock_analytics.get_anomalies = AsyncMock(return_value={"anomalies": []})

    mock_intel = MagicMock()
    mock_intel.get_events = AsyncMock(return_value={"active": []})

    mock_area_svc = MagicMock()
    mock_area_svc.list_enabled_public = AsyncMock(return_value=[])

    app = FastAPI()
    app.include_router(analytics_router)
    app.dependency_overrides[get_current_user] = lambda: MagicMock()
    app.dependency_overrides[analytics_service_dep] = lambda: mock_analytics
    app.dependency_overrides[intelligence_events_service_dep] = lambda: mock_intel
    app.dependency_overrides[monitoring_area_service_dep] = lambda: mock_area_svc
    from app.services.aoi_enrichment_service import AoiEnrichmentService

    async def _org_ctx():
        return OrganizationContext(
            user=MagicMock(id="test-user"),
            organization_id="org-test",
            organization_name="Test Org",
            organization_slug="org-test",
            membership_id="mem-test",
            role="owner",
            membership_status="active",
        )

    app.dependency_overrides[get_organization_context] = _org_ctx
    app.dependency_overrides[aoi_enrichment_service_dep] = lambda: AoiEnrichmentService()
    return TestClient(app), events


def _events_map_client(all_events: list[dict]):
    mock_svc = MagicMock()
    mock_svc.list_events = AsyncMock(return_value=all_events)
    app = FastAPI()
    app.include_router(events_router)
    app.dependency_overrides[get_current_user] = lambda: MagicMock()
    app.dependency_overrides[forest_event_service_dep] = lambda: mock_svc
    return TestClient(app)


class TestEventsMapGenericContract:
    def test_events_map_returns_unscoped_events(self):
        all_events = build_multi_region_events()
        client = _events_map_client(all_events)
        resp = client.get("/events/map")
        assert resp.status_code == 200
        countries = {m.get("region") for m in resp.json()["events"]}
        assert "Amazon" in countries or any(
            e["country"] == "Brazil" for e in all_events
        )
        assert len(resp.json()["events"]) == len(all_events)


class TestMapOverlayScopeContract:
    def test_romania_scope_includes_ro_excludes_de(self):
        client, _ = _map_overlay_client(scope="romania")
        body = client.get("/analytics/intelligence/map-overlay").json()
        regions = {m["region"] for m in body["forest_events"]}
        assert "Suceava" in regions or "RO-BUC-AQ01" in regions
        assert "Bavaria" not in regions
        assert "Galicia" not in regions
        assert "FR-PAR-AQ01" not in regions
        assert "PL-WAW-AQ01" not in regions
        assert "Amazon" not in regions

    def test_europe_scope_includes_all_european_countries_excludes_brazil(self):
        client, events = _map_overlay_client(scope="europe")
        body = client.get("/analytics/intelligence/map-overlay").json()
        assert body["geographic_scope"] == "europe"
        fixture_regions = {m["region"] for m in body["forest_events"]}
        europe_fixture = events_in_scope(build_multi_region_events(), "europe")
        expected_regions = {e["region"] for e in europe_fixture}
        assert fixture_regions == expected_regions
        assert "Amazon" not in fixture_regions

    def test_all_scope_includes_brazil_control(self):
        client, _ = _map_overlay_client(scope="all")
        body = client.get("/analytics/intelligence/map-overlay").json()
        assert body["geographic_scope"] == "all"
        regions = {m["region"] for m in body["forest_events"]}
        assert "Amazon" in regions

    def test_europe_scope_includes_fr_pl(self):
        client, _ = _map_overlay_client(scope="europe")
        body = client.get("/analytics/intelligence/map-overlay").json()
        fixture_regions = {m["region"] for m in body["forest_events"]}
        assert "FR-PAR-AQ01" in fixture_regions
        assert "PL-WAW-AQ01" in fixture_regions or "Mazovia" in fixture_regions


class TestMapOverlayCoordinateIntegrity:
    @pytest.mark.parametrize(
        "country, lat, lng",
        [
            ("Germany", 48.1351, 11.582),
            ("Poland", 52.2297, 21.0122),
            ("France", 48.8566, 2.3522),
        ],
    )
    def test_authoritative_country_coordinates(self, country, lat, lng):
        event = next(e for e in build_multi_region_events() if e["country"] == country)
        client, _ = _map_overlay_client(scope="europe", forest_events=[_event_with_id(event, f"evt-{country}")])
        marker = client.get("/analytics/intelligence/map-overlay").json()["forest_events"][0]
        assert marker["latitude"] == pytest.approx(lat)
        assert marker["longitude"] == pytest.approx(lng)
        assert [marker["latitude"], marker["longitude"]] == [lat, lng]

    def test_eea_station_coordinates(self):
        event = next(
            e for e in build_multi_region_events()
            if e["country"] == "Germany" and e["metadata"]["incident_category"] == "air_quality"
        )
        client, _ = _map_overlay_client(scope="europe", forest_events=[_event_with_id(event, "de-aq")])
        marker = client.get("/analytics/intelligence/map-overlay").json()["forest_events"][0]
        assert marker["coordinate_source"] == "monitoring_station"
        assert marker["latitude"] == pytest.approx(48.1374)

    def test_cems_activation_coordinates(self):
        event = next(
            e for e in build_multi_region_events()
            if e["country"] == "France" and e["metadata"]["incident_category"] == "environmental_hazard"
        )
        client, _ = _map_overlay_client(scope="europe", forest_events=[_event_with_id(event, "fr-cems")])
        marker = client.get("/analytics/intelligence/map-overlay").json()["forest_events"][0]
        assert marker["coordinate_source"] == "activation_centroid"
        assert marker["latitude"] == pytest.approx(48.8566)

    def test_firms_event_coordinates(self):
        event = next(
            e for e in build_multi_region_events()
            if e["country"] == "Spain" and e["metadata"]["incident_category"] == "wildfire"
        )
        client, _ = _map_overlay_client(scope="europe", forest_events=[_event_with_id(event, "es-wf")])
        marker = client.get("/analytics/intelligence/map-overlay").json()["forest_events"][0]
        assert marker["incident_category"] == "wildfire"
        assert marker["latitude"] == pytest.approx(42.8805)


class TestMapOverlayRomaniaCentroidProtection:
    def test_europe_scope_disables_romania_centroid_fallback(self):
        client, _ = _map_overlay_client(scope="europe")
        body = client.get("/analytics/intelligence/map-overlay").json()
        assert body["allow_romania_centroid_fallback"] is False

    def test_romania_scope_allows_centroid_fallback(self):
        client, _ = _map_overlay_client(scope="romania")
        body = client.get("/analytics/intelligence/map-overlay").json()
        assert body["allow_romania_centroid_fallback"] is True

    def test_german_event_not_at_romanian_centroid(self):
        de_event = next(
            e for e in build_multi_region_events()
            if e["country"] == "Germany" and e["metadata"]["incident_category"] == "wildfire"
        )
        marker = forest_event_map_marker(_event_with_id(de_event, "de-wf"))
        assert marker["latitude"] == pytest.approx(48.1351)
        assert marker["latitude"] != pytest.approx(44.4268)  # Bucharest station lat in fixture


class TestMapOverlayCategoryIsolation:
    def test_categories_preserved_in_markers(self):
        events = [
            _event_with_id(e, f"evt-{i}")
            for i, e in enumerate(build_multi_region_events()[:3])
        ]
        client, _ = _map_overlay_client(scope="europe", forest_events=events)
        markers = client.get("/analytics/intelligence/map-overlay").json()["forest_events"]
        categories = {m["incident_category"] for m in markers}
        assert "wildfire" in categories
        assert "air_quality" in categories
        assert "environmental_hazard" in categories

    def test_wildfire_marker_has_canonical_fields(self):
        event = next(e for e in build_multi_region_events() if e["metadata"]["incident_category"] == "wildfire")
        marker = forest_event_map_marker(_event_with_id(event, "wf-1"))
        for field in ("incident_category", "spatial_key", "latitude", "longitude", "severity", "confidence", "source_event_id", "event_type"):
            assert field in marker


class TestRegionCentroidMatchStage:
    def test_valid_coords_match_uses_expr_not_query_operators(self):
        from app.modules.analytics.analytics_repository import _valid_coords_match_stage

        stage = _valid_coords_match_stage()
        assert "$expr" in stage["$match"]
        assert "$gte" not in stage["$match"]
        assert "$and" in stage["$match"]["$expr"]
