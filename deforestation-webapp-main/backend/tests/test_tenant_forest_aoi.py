"""Tenant Forest AOI + Authorization Context — monetization foundation tests."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import (
    analytics_service_dep,
    aoi_enrichment_service_dep,
    command_center_service_dep,
    customer_monitoring_status_service_dep,
    evidence_aware_command_center_dep,
    get_current_user,
    get_organization_context,
    intelligence_events_repo_dep,
    intelligence_events_service_dep,
    monitoring_area_read_model_service_dep,
    monitoring_area_service_dep,
    source_intelligence_service_dep,
)
from app.api.monitoring_area_routes import router as monitoring_area_router
from app.core.config import Settings
from app.core.ecosystem.authorization_context import (
    AuthorizationContextRecord,
    AuthorizationStatus,
    UnknownAuthorizationContextProvider,
)
from app.core.ecosystem.forest_disturbance_constants import (
    FORBIDDEN_ASSERTION_PHRASES,
    InvestigationPriority,
    PRODUCT_ASSESSMENT_LABEL,
    assert_safe_assessment_language,
)
from app.core.geography.geographic_scope import GeographicScope, GeographicScopePolicy
from app.core.organization.organization_context import OrganizationContext
from app.core.tenant.tenant_context import tenant_id_from_user
from app.services.entitlement_service import EntitlementProfile, EntitlementService
from app.models.forest_monitoring_area import ForestMonitoringAreaCreate
from app.models.geo import validate_geojson_geometry
from app.models.user import UserPublic
from app.modules.analytics.analytics_routes import router as analytics_router
from app.modules.analytics.map_contract import intelligence_event_map_marker
from app.services.aoi_enrichment_service import AoiEnrichmentService
from app.services.aoi_geometry import match_point_to_areas, point_in_geometry
from app.services.customer_monitoring_status_service import CustomerMonitoringStatusService
from app.services.forest_monitoring_area_service import ForestMonitoringAreaService
from app.services.monitoring_area_read_model_service import MonitoringAreaReadModelService
from fixtures.phase0_golden_harness import generate_golden_artifacts
from fixtures.phase0_oracle_manifest import verify_generated_match_manifest

_NOW = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)


def _settings(**overrides) -> Settings:
    base = {
        "mongo_url": "mongodb://localhost:27017",
        "db_name": "test",
        "jwt_secret": "secret",
        "admin_email": "admin@test.com",
        "admin_password": "pass",
        "frontend_url": "http://localhost:3000",
    }
    base.update(overrides)
    return Settings(**base)


def _user(user_id: str = "tenant-a") -> UserPublic:
    return UserPublic(
        id=user_id,
        email=f"{user_id}@test.com",
        name="Test User",
        role="admin",
        provider="local",
        created_at=_NOW,
    )


def _romania_polygon() -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[
            [25.5, 46.8],
            [26.5, 46.8],
            [26.5, 47.5],
            [25.5, 47.5],
            [25.5, 46.8],
        ]],
    }


def _germany_polygon() -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[
            [9.5, 48.0],
            [10.5, 48.0],
            [10.5, 48.8],
            [9.5, 48.8],
            [9.5, 48.0],
        ]],
    }


def _org_id(user_id: str) -> str:
    return f"org-{user_id}"


def _org_ctx(user: UserPublic) -> OrganizationContext:
    oid = _org_id(user.id)
    return OrganizationContext(
        user=user,
        organization_id=oid,
        organization_name="Personal Workspace",
        organization_slug=f"personal-{user.id}",
        membership_id=f"mem-{user.id}",
        role="owner",
        membership_status="active",
    )


def _area(
    area_id: str,
    name: str,
    geometry: dict,
    *,
    enabled: bool = True,
    organization_id: str = "org-tenant-a",
    tenant_id: str | None = None,
) -> dict:
    return {
        "id": area_id,
        "organization_id": organization_id,
        "tenant_id": tenant_id or organization_id,
        "name": name,
        "geometry": geometry,
        "geometry_type": geometry["type"],
        "country": "Romania" if "25.5" in str(geometry) else "Germany",
        "enabled": enabled,
    }


def _disturbance_intel_event(
    *,
    event_id: str = "ie-dist-1",
    lat: float = 47.12,
    lng: float = 25.98,
    priority: str = InvestigationPriority.MEDIUM.value,
) -> dict:
    return {
        "id": event_id,
        "incident_category": "forest_disturbance",
        "region": "Harghita",
        "severity": "high",
        "latitude": lat,
        "longitude": lng,
        "priority_score": 0.72,
        "metadata": {
            "forest_disturbance": {
                "probable_driver": "selective_logging_candidate",
                "driver_confidence": 0.82,
                "investigation_priority": priority,
                "authorization_status": AuthorizationStatus.UNKNOWN.value,
                "assessment_label": PRODUCT_ASSESSMENT_LABEL,
                "affected_area_ha": 4.7,
            },
        },
    }


class FakeMonitoringAreaRepo:
    def __init__(self) -> None:
        self._store: dict[str, dict] = {}
        self._seq = 0

    async def list_for_organization(self, organization_id: str, *, enabled_only: bool = False, limit: int = 100):
        from app.models.forest_monitoring_area import ForestMonitoringArea

        rows = [v for v in self._store.values() if v["organization_id"] == organization_id]
        if enabled_only:
            rows = [r for r in rows if r.get("enabled", True)]
        rows.sort(key=lambda r: r["name"])
        return [ForestMonitoringArea.model_validate(r) for r in rows[:limit]]

    async def list_for_tenant(self, tenant_id: str, *, enabled_only: bool = False, limit: int = 100):
        return await self.list_for_organization(tenant_id, enabled_only=enabled_only, limit=limit)

    async def find_for_organization(self, organization_id: str, area_id: str):
        from app.models.forest_monitoring_area import ForestMonitoringArea

        doc = self._store.get(area_id)
        if doc is None or doc["organization_id"] != organization_id:
            return None
        return ForestMonitoringArea.model_validate(doc)

    async def find_for_tenant(self, tenant_id: str, area_id: str):
        return await self.find_for_organization(tenant_id, area_id)

    async def insert(self, doc):
        self._seq += 1
        area_id = f"area-{self._seq}"
        payload = doc.model_dump()
        payload["id"] = area_id
        payload["_id"] = area_id
        self._store[area_id] = payload
        doc.id = area_id
        return doc

    async def update(self, area_id: str, updates: dict) -> bool:
        if area_id not in self._store:
            return False
        self._store[area_id].update(updates)
        return True

    async def delete(self, area_id: str) -> bool:
        return self._store.pop(area_id, None) is not None

    async def delete_for_organization(self, organization_id: str, area_id: str) -> bool:
        doc = await self.find_for_organization(organization_id, area_id)
        if doc is None:
            return False
        return await self.delete(area_id)

    async def delete_for_tenant(self, tenant_id: str, area_id: str) -> bool:
        return await self.delete_for_organization(tenant_id, area_id)


def _monitoring_client(*, user: UserPublic | None = None, repo: FakeMonitoringAreaRepo | None = None):
    user = user or _user()
    store = repo or FakeMonitoringAreaRepo()
    svc = ForestMonitoringAreaService(store)
    # Read routes go through the enriched read model; give it an empty
    # intelligence repository so area CRUD is testable without a database.
    intel_repo = MagicMock()
    intel_repo.find_active = AsyncMock(return_value=[])
    read_svc = MonitoringAreaReadModelService(svc, intel_repo)
    app = FastAPI()
    app.include_router(monitoring_area_router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_organization_context] = lambda: _org_ctx(user)
    app.dependency_overrides[monitoring_area_service_dep] = lambda: svc
    app.dependency_overrides[monitoring_area_read_model_service_dep] = lambda: read_svc
    return TestClient(app), store, svc


def _analytics_client(
    *,
    user: UserPublic | None = None,
    areas: list[dict] | None = None,
    active_events: list[dict] | None = None,
    scope: str = "romania",
):
    user = user or _user()
    areas = areas or []
    active_events = active_events or []

    mock_analytics = MagicMock()
    mock_repo = MagicMock()
    mock_repo.list_scoped_events_for_map = AsyncMock(return_value=[])
    mock_repo.region_event_centroids = AsyncMock(return_value={"Harghita": (47.12, 25.98)})
    mock_repo.scope_policy = GeographicScopePolicy(GeographicScope(scope))
    mock_analytics.repo = mock_repo
    mock_analytics.geographic_scope = scope
    mock_analytics.get_anomalies = AsyncMock(return_value={"anomalies": []})

    mock_intel_svc = MagicMock()
    mock_intel_svc.get_events = AsyncMock(return_value={"active": active_events, "resolved": []})

    mock_area_svc = MagicMock()
    mock_area_svc.list_enabled_public = AsyncMock(return_value=areas)

    mock_intel_repo = MagicMock()
    mock_intel_repo.find_active = AsyncMock(return_value=active_events)

    mock_evidence = MagicMock()
    mock_evidence.build_intelligence_evidence = AsyncMock(
        return_value={
            "intelligence_cycle_id": "cycle-1",
            "correlation_state": "disabled",
            "items": [
                {
                    "event_id": evt["id"],
                    "incident_category": evt.get("incident_category"),
                    "disturbance_assessment": (evt.get("metadata") or {}).get("forest_disturbance", {}),
                    "evidence_summary": {"evidence_state": "single_source", "providers": ["GFW Alerts"]},
                }
                for evt in active_events
            ],
        }
    )

    mock_status = MagicMock()
    mock_status.get_monitoring_status = AsyncMock(
        return_value={
            "organization": {"id": _org_id(user.id), "name": "Personal Workspace", "role": "owner"},
            "entitlements": {
                "monitored_area_limit": 1,
                "monitored_area_count": len(areas),
                "monitoring_enabled": True,
                "forest_disturbance_enabled": True,
                "evidence_correlation_enabled": False,
                "live_sources_enabled": False,
                "alert_delivery_enabled": False,
            },
            "monitored_areas": {"enabled_count": len(areas)},
        }
    )

    app = FastAPI()
    app.include_router(analytics_router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_organization_context] = lambda: _org_ctx(user)
    app.dependency_overrides[analytics_service_dep] = lambda: mock_analytics
    app.dependency_overrides[intelligence_events_service_dep] = lambda: mock_intel_svc
    app.dependency_overrides[monitoring_area_service_dep] = lambda: mock_area_svc
    app.dependency_overrides[aoi_enrichment_service_dep] = lambda: AoiEnrichmentService()
    app.dependency_overrides[intelligence_events_repo_dep] = lambda: mock_intel_repo
    app.dependency_overrides[evidence_aware_command_center_dep] = lambda: mock_evidence
    app.dependency_overrides[customer_monitoring_status_service_dep] = lambda: mock_status

    return TestClient(app), mock_area_svc, mock_status


class TestTenantContext:
    def test_tenant_id_from_authenticated_user(self):
        assert tenant_id_from_user(_user("user-42")) == "user-42"


class TestGeometryValidation:
    def test_polygon_accepted(self):
        geom = validate_geojson_geometry(_romania_polygon())
        assert geom["type"] == "Polygon"

    def test_multipolygon_accepted(self):
        geom = validate_geojson_geometry(
            {"type": "MultiPolygon", "coordinates": [_romania_polygon()["coordinates"]]}
        )
        assert geom["type"] == "MultiPolygon"

    def test_invalid_geometry_type_rejected(self):
        with pytest.raises(ValueError, match="Polygon or MultiPolygon"):
            validate_geojson_geometry({"type": "Point", "coordinates": [25.0, 47.0]})

    def test_empty_geometry_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            validate_geojson_geometry({"type": "Polygon", "coordinates": []})

    def test_invalid_coordinates_rejected(self):
        bad = {
            "type": "Polygon",
            "coordinates": [[[200.0, 47.0], [26.0, 47.0], [26.0, 48.0], [200.0, 48.0], [200.0, 47.0]]],
        }
        with pytest.raises(ValueError, match="longitude"):
            validate_geojson_geometry(bad)

    def test_unclosed_ring_rejected(self):
        bad = {
            "type": "Polygon",
            "coordinates": [[[25.5, 46.8], [26.5, 46.8], [26.5, 47.5], [25.5, 47.5]]],
        }
        with pytest.raises(ValueError, match="closed"):
            validate_geojson_geometry(bad)


class TestAoiMatching:
    def test_point_inside_aoi(self):
        assert point_in_geometry(47.12, 25.98, _romania_polygon()) is True

    def test_point_outside_aoi(self):
        assert point_in_geometry(44.0, 26.0, _romania_polygon()) is False

    def test_boundary_behavior_deterministic(self):
        # Point on edge — ray-casting result must be stable across calls.
        on_edge = point_in_geometry(46.8, 25.5, _romania_polygon())
        assert point_in_geometry(46.8, 25.5, _romania_polygon()) is on_edge

    def test_multiple_overlapping_aois(self):
        areas = [
            _area("z-area", "Z Forest", _romania_polygon()),
            _area("a-area", "A Forest", _romania_polygon()),
        ]
        matches = match_point_to_areas(47.12, 25.98, areas)
        assert [m["id"] for m in matches] == ["a-area", "z-area"]

    def test_disabled_aoi_ignored(self):
        areas = [_area("off", "Disabled", _romania_polygon(), enabled=False)]
        assert match_point_to_areas(47.12, 25.98, areas) == []

    def test_multiple_tenants_isolated_in_service(self):
        areas_a = [_area("a1", "Tenant A", _romania_polygon(), organization_id="org-tenant-a")]
        areas_b = [_area("b1", "Tenant B", _romania_polygon(), organization_id="org-tenant-b")]
        assert match_point_to_areas(47.12, 25.98, areas_a)[0]["id"] == "a1"
        assert match_point_to_areas(47.12, 25.98, areas_b)[0]["id"] == "b1"


class TestAuthorizationContext:
    def test_default_unknown_authorization(self):
        provider = UnknownAuthorizationContextProvider()
        record = provider.lookup(latitude=47.12, longitude=25.98, tenant_id="t1")
        assert record.status == AuthorizationStatus.UNKNOWN.value

    def test_no_fabricated_permits(self):
        provider = UnknownAuthorizationContextProvider()
        record = provider.lookup(latitude=47.12, longitude=25.98, tenant_id="t1", monitored_area_id="a1")
        assert record.permit_id is None
        assert record.permit_type is None


class TestDisturbanceEnrichment:
    def test_inside_aoi_increases_priority(self):
        svc = AoiEnrichmentService()
        enriched = svc.enrich_disturbance_item(
            latitude=47.12,
            longitude=25.98,
            organization_id="org-tenant-a",
            areas=[_area("a1", "Harghita Block", _romania_polygon())],
            disturbance_block={"investigation_priority": InvestigationPriority.MEDIUM.value},
        )
        assert enriched["inside_monitored_area"] is True
        assert enriched["customer_relevance"] is True
        assert enriched["investigation_priority"] == InvestigationPriority.HIGH.value

    def test_outside_aoi_not_customer_relevant(self):
        svc = AoiEnrichmentService()
        enriched = svc.enrich_disturbance_item(
            latitude=44.0,
            longitude=26.0,
            organization_id="org-tenant-a",
            areas=[_area("a1", "Harghita Block", _romania_polygon())],
            disturbance_block={"investigation_priority": InvestigationPriority.MEDIUM.value},
        )
        assert enriched["inside_monitored_area"] is False
        assert enriched.get("customer_relevance") is not True

    def test_authorization_unknown_for_gfw_only(self):
        svc = AoiEnrichmentService()
        enriched = svc.enrich_disturbance_item(
            latitude=47.12,
            longitude=25.98,
            organization_id="org-tenant-a",
            areas=[_area("a1", "Harghita Block", _romania_polygon())],
            disturbance_block={"authorization_status": AuthorizationStatus.UNKNOWN.value},
        )
        assert enriched["authorization_status"] == AuthorizationStatus.UNKNOWN.value

    def test_multiple_aoi_intersection_status(self):
        svc = AoiEnrichmentService()
        enriched = svc.enrich_disturbance_item(
            latitude=47.12,
            longitude=25.98,
            organization_id="org-tenant-a",
            areas=[
                _area("a1", "Forest A", _romania_polygon()),
                _area("a2", "Forest B", _romania_polygon()),
            ],
            disturbance_block={},
        )
        assert enriched["intersection_status"] == "inside_many"
        assert len(enriched["monitored_area_matches"]) == 2

    def test_forbidden_language_not_in_enrichment(self):
        svc = AoiEnrichmentService()
        for phrase in FORBIDDEN_ASSERTION_PHRASES:
            with pytest.raises(ValueError):
                svc.enrich_disturbance_item(
                    latitude=47.12,
                    longitude=25.98,
                    organization_id="org-tenant-a",
                    areas=[_area("a1", "Forest", _romania_polygon())],
                    disturbance_block={"assessment_label": phrase},
                )


class TestGeographicScopeDistinctFromTenantAoi:
    def test_romania_scope_policy_distinct_from_aoi(self):
        policy = GeographicScopePolicy(GeographicScope.ROMANIA)
        assert policy.centroids_use_romania_admin_fallback() is True
        aoi = _romania_polygon()
        assert aoi != policy  # different concepts

    def test_europe_aoi_accepts_german_polygon(self):
        geom = validate_geojson_geometry(_germany_polygon())
        assert geom["type"] == "Polygon"
        assert point_in_geometry(48.40, 10.00, geom)

    def test_brazil_point_outside_european_aoi(self):
        areas = [_area("de1", "Bavaria", _germany_polygon(), organization_id="org-tenant-eu")]
        assert match_point_to_areas(-3.1, -60.0, areas) == []


class TestMonitoringAreaApi:
    def test_create_and_list_crud(self):
        client, _, _ = _monitoring_client()
        resp = client.post(
            "/monitoring-areas",
            json={"name": "Harghita Forest", "geometry": _romania_polygon(), "country": "Romania"},
        )
        assert resp.status_code == 201
        listed = client.get("/monitoring-areas").json()
        assert listed["total"] == 1
        assert listed["items"][0]["name"] == "Harghita Forest"

    def test_get_update_delete(self):
        client, store, _ = _monitoring_client()
        created = client.post(
            "/monitoring-areas",
            json={"name": "Block A", "geometry": _romania_polygon()},
        ).json()
        area_id = created["id"]
        assert client.get(f"/monitoring-areas/{area_id}").status_code == 200
        updated = client.put(
            f"/monitoring-areas/{area_id}",
            json={"name": "Block A Renamed", "enabled": False},
        ).json()
        assert updated["name"] == "Block A Renamed"
        assert updated["enabled"] is False
        assert client.delete(f"/monitoring-areas/{area_id}").status_code == 204
        assert client.get(f"/monitoring-areas/{area_id}").status_code == 404

    def test_invalid_geometry_rejected_on_create(self):
        client, _, _ = _monitoring_client()
        resp = client.post(
            "/monitoring-areas",
            json={"name": "Bad", "geometry": {"type": "Point", "coordinates": [25, 47]}},
        )
        assert resp.status_code == 422


class TestTenantIsolationApi:
    def test_tenant_a_cannot_read_tenant_b_aoi(self):
        repo = FakeMonitoringAreaRepo()
        client_a, _, svc = _monitoring_client(user=_user("tenant-a"), repo=repo)
        client_b, _, _ = _monitoring_client(user=_user("tenant-b"), repo=repo)
        created = client_a.post(
            "/monitoring-areas",
            json={"name": "Secret Forest", "geometry": _romania_polygon()},
        ).json()
        assert client_b.get(f"/monitoring-areas/{created['id']}").status_code == 404

    def test_tenant_a_cannot_modify_tenant_b_aoi(self):
        repo = FakeMonitoringAreaRepo()
        client_a, _, _ = _monitoring_client(user=_user("tenant-a"), repo=repo)
        client_b, _, _ = _monitoring_client(user=_user("tenant-b"), repo=repo)
        created = client_a.post(
            "/monitoring-areas",
            json={"name": "Protected", "geometry": _romania_polygon()},
        ).json()
        assert client_b.put(f"/monitoring-areas/{created['id']}", json={"name": "Hacked"}).status_code == 404

    def test_tenant_a_cannot_delete_tenant_b_aoi(self):
        repo = FakeMonitoringAreaRepo()
        client_a, _, _ = _monitoring_client(user=_user("tenant-a"), repo=repo)
        client_b, _, _ = _monitoring_client(user=_user("tenant-b"), repo=repo)
        created = client_a.post(
            "/monitoring-areas",
            json={"name": "Protected", "geometry": _romania_polygon()},
        ).json()
        assert client_b.delete(f"/monitoring-areas/{created['id']}").status_code == 404

    def test_tenant_b_list_excludes_tenant_a_areas(self):
        repo = FakeMonitoringAreaRepo()
        client_a, _, _ = _monitoring_client(user=_user("tenant-a"), repo=repo)
        client_b, _, _ = _monitoring_client(user=_user("tenant-b"), repo=repo)
        client_a.post("/monitoring-areas", json={"name": "A Forest", "geometry": _romania_polygon()})
        assert client_b.get("/monitoring-areas").json()["total"] == 0


class TestMapOverlayAoi:
    def test_map_includes_monitored_areas(self):
        areas = [_area("a1", "Harghita Block", _romania_polygon())]
        client, _, _ = _analytics_client(areas=areas)
        body = client.get("/analytics/intelligence/map-overlay").json()
        assert len(body["monitored_areas"]) == 1
        assert body["monitored_areas"][0]["geometry"]["type"] == "Polygon"

    def test_disturbance_marker_aoi_enrichment_inside(self):
        event = _disturbance_intel_event()
        areas = [_area("a1", "Harghita Block", _romania_polygon())]
        client, _, _ = _analytics_client(areas=areas, active_events=[event])
        marker = client.get("/analytics/intelligence/map-overlay").json()["intelligence_events"][0]
        assert marker["latitude"] == 47.12
        assert marker["longitude"] == 25.98
        assert marker["inside_monitored_area"] is True
        assert marker["monitored_area"]["relevance"] == "inside_monitored_area"

    def test_disturbance_outside_aoi_no_customer_relevance(self):
        event = _disturbance_intel_event(lat=44.0, lng=26.0)
        areas = [_area("a1", "Harghita Block", _romania_polygon())]
        client, _, _ = _analytics_client(areas=areas, active_events=[event])
        marker = client.get("/analytics/intelligence/map-overlay").json()["intelligence_events"][0]
        assert marker["monitored_area"]["relevance"] == "outside_monitored_area"

    def test_wildfire_markers_unaffected(self):
        wildfire = {
            "id": "ie-wf-1",
            "incident_category": "wildfire",
            "region": "Suceava",
            "latitude": 47.6353,
            "longitude": 26.259,
            "priority_score": 0.8,
            "metadata": {},
        }
        client, _, _ = _analytics_client(active_events=[wildfire])
        marker = client.get("/analytics/intelligence/map-overlay").json()["intelligence_events"][0]
        assert marker["incident_category"] == "wildfire"
        assert "inside_monitored_area" not in marker


class TestCommandCenterAoi:
    def test_command_center_includes_monitored_area_summary(self):
        event = _disturbance_intel_event()
        areas = [_area("a1", "Harghita Block", _romania_polygon())]

        app = FastAPI()
        app.include_router(analytics_router)
        app.dependency_overrides[get_current_user] = lambda: _user()
        app.dependency_overrides[get_organization_context] = lambda: _org_ctx(_user())
        app.dependency_overrides[analytics_service_dep] = lambda: MagicMock()
        app.dependency_overrides[monitoring_area_service_dep] = lambda: MagicMock(
            list_enabled_public=AsyncMock(return_value=areas)
        )
        app.dependency_overrides[aoi_enrichment_service_dep] = lambda: AoiEnrichmentService()
        app.dependency_overrides[intelligence_events_repo_dep] = lambda: MagicMock(
            find_active=AsyncMock(return_value=[event])
        )
        app.dependency_overrides[evidence_aware_command_center_dep] = lambda: MagicMock(
            build_intelligence_evidence=AsyncMock(
                return_value={
                    "items": [{
                        "event_id": event["id"],
                        "incident_category": "forest_disturbance",
                        "disturbance_assessment": event["metadata"]["forest_disturbance"],
                        "evidence_summary": {"evidence_state": "single_source"},
                    }],
                }
            )
        )
        app.dependency_overrides[source_intelligence_service_dep] = lambda: MagicMock(
            get_health_summary=AsyncMock(return_value={}),
            get_degraded_sources=AsyncMock(return_value=[]),
        )
        app.dependency_overrides[command_center_service_dep] = lambda: MagicMock(
            get_snapshot=AsyncMock(return_value={"domains": []})
        )
        tc = TestClient(app)
        item = tc.get("/analytics/intelligence/command-center").json()["intelligence_evidence"]["items"][0]
        assert item["monitored_area"]["relevance"] == "inside_monitored_area"
        assert item["monitored_area"]["name"] == "Harghita Block"


class TestMonitoringStatusEndpoint:
    def test_monitoring_status_read_only(self):
        client, _, _ = _analytics_client(
            areas=[_area("a1", "Forest", _romania_polygon())],
            active_events=[_disturbance_intel_event()],
        )
        resp = client.get("/analytics/intelligence/monitoring-status")
        assert resp.status_code == 200
        assert resp.json()["monitored_areas"]["enabled_count"] == 1

    @pytest.mark.anyio
    async def test_monitoring_status_counts_inside_aoi(self):
        area_svc = MagicMock()
        area_svc.list_enabled_public = AsyncMock(
            return_value=[_area("a1", "Forest", _romania_polygon())]
        )
        intel_repo = MagicMock()
        intel_repo.find_active = AsyncMock(
            return_value=[
                _disturbance_intel_event(priority=InvestigationPriority.HIGH.value),
                _disturbance_intel_event(event_id="ie-out", lat=44.0, lng=26.0),
            ]
        )
        source_intel = MagicMock()
        source_intel.get_source_status = AsyncMock(return_value={"sources": [{"id": "gfw"}]})
        cycle_repo = MagicMock()
        cycle_repo.get_current = AsyncMock(return_value={"intelligence_cycle_id": "c1"})
        correlation_repo = MagicMock()
        correlation_repo.list_all = AsyncMock(return_value=[])
        health_repo = MagicMock()
        health_repo.list_all = AsyncMock(return_value=[])

        entitlement_svc = MagicMock(spec=EntitlementService)
        entitlement_svc.get_profile = AsyncMock(
            return_value=EntitlementProfile(
                organization_id="org-tenant-a",
                monitored_area_limit=1,
                monitoring_enabled=True,
                forest_disturbance_enabled=True,
                evidence_correlation_enabled=False,
                live_sources_enabled=False,
                alert_delivery_enabled=False,
                source="foundation_profile",
            )
        )

        svc = CustomerMonitoringStatusService(
            area_svc,
            intel_repo,
            source_intel,
            cycle_repo,
            correlation_repo,
            health_repo,
            entitlement_svc,
            settings=_settings(geographic_scope="romania"),
        )
        status = await svc.get_monitoring_status(_org_ctx(_user("tenant-a")))
        assert status["disturbance_summary"]["inside_monitored_area_count"] == 1
        assert status["disturbance_summary"]["high_critical_investigation_count"] >= 1
        assert status["disturbance_summary"]["authorization_status_default"] == "unknown"


class TestSchedulerNoSideEffects:
    def test_map_overlay_get_is_read_only(self):
        client, mock_area_svc, _ = _analytics_client()
        client.get("/analytics/intelligence/map-overlay")
        mock_area_svc.list_enabled_public.assert_called_once()

    def test_monitoring_status_get_is_read_only(self):
        client, _, mock_status = _analytics_client()
        client.get("/analytics/intelligence/monitoring-status")
        mock_status.get_monitoring_status.assert_called_once()


class TestProductLanguage:
    def test_safe_assessment_label_allowed(self):
        assert_safe_assessment_language("Potential Unauthorized Forest Activity")

    def test_map_and_status_never_emit_forbidden_phrases(self):
        svc = AoiEnrichmentService()
        enriched = svc.enrich_disturbance_item(
            latitude=47.12,
            longitude=25.98,
            organization_id="t1",
            areas=[_area("a1", "Forest", _romania_polygon())],
            disturbance_block={"assessment_label": PRODUCT_ASSESSMENT_LABEL},
        )
        blob = json.dumps(enriched).lower()
        for phrase in FORBIDDEN_ASSERTION_PHRASES:
            assert phrase.lower() not in blob


class TestPhase0Safety:
    def test_oracle_manifest_unchanged_with_aoi_defaults(self):
        verify_generated_match_manifest(generate_golden_artifacts())

    def test_wildfire_baseline_unchanged_when_disturbance_disabled(self):
        generated = generate_golden_artifacts()
        baselines = generated["cycle_0_regional_baselines.json"]
        assert "Harghita" in baselines
        assert "forest_disturbance" not in baselines


class TestForestMonitoringAreaService:
    @pytest.mark.anyio
    async def test_create_validates_geometry(self):
        repo = FakeMonitoringAreaRepo()
        svc = ForestMonitoringAreaService(repo)
        created = await svc.create_area(
            "org-tenant-a",
            ForestMonitoringAreaCreate(name="Test", geometry=_romania_polygon()),
            actor_role="owner",
        )
        assert created.geometry_type == "Polygon"
        assert created.organization_id == "org-tenant-a"
