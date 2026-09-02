"""Reusable write-spy utilities for intelligence read-path tests (WP6.4)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import (
    analytics_service_dep,
    aoi_enrichment_service_dep,
    command_center_service_dep,
    customer_monitoring_status_service_dep,
    forest_context_service_dep,
    get_current_user,
    get_organization_context,
    history_service_dep,
    ingestion_runs_repo_dep,
    intelligence_events_repo_dep,
    intelligence_events_service_dep,
    monitoring_area_service_dep,
    notification_history_repo_dep,
    risk_service_dep,
    source_intelligence_service_dep,
    threat_assessment_service_dep,
    weather_service_dep,
)
from app.core.organization.organization_context import OrganizationContext
from app.models.user import UserPublic
from app.core.geography.geographic_scope import GeographicScope, GeographicScopePolicy
from app.modules.analytics.analytics_routes import router
from app.modules.analytics.analytics_service import AnalyticsService
from app.modules.analytics.command_center_service import CommandCenterService
from app.modules.analytics.intelligence_events_service import IntelligenceEventsService
from app.modules.analytics.threat_assessment_service import ThreatAssessmentService
from app.services.forest_context_service import ForestContextService

_REPO_WRITE_METHODS = ("create", "update", "resolve")
_INTEL_RECONCILE_METHODS = ("reconcile", "reconcile_detections")
_GENERATED_AT = "2026-06-15T12:00:00+00:00"


def mock_user() -> UserPublic:
    return UserPublic(
        id="1",
        email="test@example.com",
        name="Test",
        role="admin",
        provider="local",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def _mock_org_context() -> OrganizationContext:
    user = mock_user()
    return OrganizationContext(
        user=user,
        organization_id="org-1",
        organization_name="Personal Workspace",
        organization_slug="personal-1",
        membership_id="mem-1",
        role="owner",
        membership_status="active",
    )


def tracking_intel_repo(events: list[dict] | None = None) -> MagicMock:
    """Repository mock that records create/update/resolve invocations."""
    repo = MagicMock()
    stored = list(events or [])
    repo.find_all = AsyncMock(return_value=list(stored))
    repo.find_active = AsyncMock(
        return_value=[e for e in stored if e.get("status") == "active"]
    )
    repo.create = AsyncMock(
        side_effect=lambda payload: stored.append({**payload, "id": "new"})
    )
    repo.update = AsyncMock()
    repo.resolve = AsyncMock()
    repo._stored = stored
    return repo


@dataclass
class IntelligenceWriteSpy:
    """Tracks intelligence persistence and reconciliation side effects."""

    intel_repo: MagicMock
    intel_svc: IntelligenceEventsService
    analytics_svc: MagicMock
    history_svc: MagicMock
    risk_svc: MagicMock
    weather_svc: MagicMock
    command_center_svc: CommandCenterService
    threat_svc: ThreatAssessmentService
    runs_repo: MagicMock
    notification_history_repo: MagicMock

    def assert_no_persistence_or_reconciliation(self) -> None:
        """Fail if any write or reconciliation command was invoked."""
        for method in _REPO_WRITE_METHODS:
            getattr(self.intel_repo, method).assert_not_called()
        for method in _INTEL_RECONCILE_METHODS:
            mock = getattr(self.intel_svc, method)
            if isinstance(mock, AsyncMock):
                mock.assert_not_called()
        self.analytics_svc.reconcile_intelligence_events.assert_not_called()


def _stub_analytics_service() -> MagicMock:
    svc = MagicMock(spec=AnalyticsService)
    svc.reconcile_intelligence_events = AsyncMock()
    svc.get_anomalies = AsyncMock(
        return_value={"generated_at": _GENERATED_AT, "anomalies": []}
    )
    svc.get_regional_baselines = AsyncMock(
        return_value={"generated_at": _GENERATED_AT, "regions": []}
    )
    svc.get_temporal_summary = AsyncMock(
        return_value={
            "generated_at": _GENERATED_AT,
            "last_24h": 0,
            "last_7d": 0,
            "previous_7d": 0,
            "trend": "stable",
        }
    )
    svc.get_alerts = AsyncMock(return_value={"generated_at": _GENERATED_AT, "alerts": []})
    svc.get_land_cover_distribution = AsyncMock(
        return_value={"generated_at": _GENERATED_AT, "distribution": []}
    )
    svc.get_incident_aggregation = AsyncMock(return_value={"incidents": []})
    svc.overview = AsyncMock(return_value={"total_events": 0})
    svc.by_event_type = AsyncMock(return_value=[])
    svc.repo = MagicMock()
    svc.repo.scope_policy = GeographicScopePolicy(GeographicScope.ROMANIA)
    svc.repo.region_event_centroids = AsyncMock(return_value={})
    svc.repo.list_scoped_events_for_map = AsyncMock(return_value=[])
    return svc


def build_intelligence_write_spy() -> IntelligenceWriteSpy:
    """Construct spied services used by intelligence read routes."""
    intel_repo = tracking_intel_repo()
    intel_svc = IntelligenceEventsService(intel_repo)
    intel_svc.reconcile = AsyncMock()
    intel_svc.reconcile_detections = AsyncMock()

    analytics_svc = _stub_analytics_service()

    history_svc = MagicMock()
    history_svc.daily_activity = AsyncMock(
        return_value={"generated_at": _GENERATED_AT, "days": []}
    )
    history_svc.regional_history = AsyncMock(return_value=[])
    history_svc.hotspot_history = AsyncMock(return_value=[])
    history_svc.monthly_summary = AsyncMock(return_value={"months": []})

    risk_svc = MagicMock()
    risk_svc.get_risk = AsyncMock(return_value={"generated_at": _GENERATED_AT, "regions": []})

    weather_svc = MagicMock()
    weather_svc.get_current_weather = AsyncMock(
        return_value={
            "generated_at": _GENERATED_AT,
            "provider": "Open-Meteo",
            "cache_ttl_minutes": 30,
            "regions": [],
        }
    )

    threat_svc = ThreatAssessmentService(intel_svc)
    threat_svc.get_threats = AsyncMock(return_value={"threats": []})
    threat_svc.get_threat_summary = AsyncMock(
        return_value={
            "generated_at": _GENERATED_AT,
            "total_active": 0,
            "by_category": {},
            "origin_ratio": {},
            "priority_interventions": [],
        }
    )

    command_center_svc = CommandCenterService(
        analytics_svc,
        intel_svc,
        weather_svc=weather_svc,
        threat_svc=threat_svc,
        investigation_svc=None,
    )

    runs_repo = MagicMock()
    runs_repo.list_runs = AsyncMock(return_value=[])

    notification_history_repo = MagicMock()
    notification_history_repo.list_recent = AsyncMock(return_value=[])

    return IntelligenceWriteSpy(
        intel_repo=intel_repo,
        intel_svc=intel_svc,
        analytics_svc=analytics_svc,
        history_svc=history_svc,
        risk_svc=risk_svc,
        weather_svc=weather_svc,
        command_center_svc=command_center_svc,
        threat_svc=threat_svc,
        runs_repo=runs_repo,
        notification_history_repo=notification_history_repo,
    )


def build_intelligence_read_client(
    spy: IntelligenceWriteSpy | None = None,
) -> tuple[TestClient, IntelligenceWriteSpy]:
    """FastAPI test client with intelligence dependencies overridden and spied."""
    bundle = spy or build_intelligence_write_spy()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = mock_user
    app.dependency_overrides[analytics_service_dep] = lambda: bundle.analytics_svc
    app.dependency_overrides[intelligence_events_service_dep] = lambda: bundle.intel_svc
    app.dependency_overrides[history_service_dep] = lambda: bundle.history_svc
    app.dependency_overrides[risk_service_dep] = lambda: bundle.risk_svc
    app.dependency_overrides[weather_service_dep] = lambda: bundle.weather_svc
    app.dependency_overrides[command_center_service_dep] = lambda: bundle.command_center_svc
    app.dependency_overrides[threat_assessment_service_dep] = lambda: bundle.threat_svc
    app.dependency_overrides[ingestion_runs_repo_dep] = lambda: bundle.runs_repo
    app.dependency_overrides[notification_history_repo_dep] = (
        lambda: bundle.notification_history_repo
    )
    app.dependency_overrides[forest_context_service_dep] = lambda: ForestContextService()

    source_intel = MagicMock()
    source_intel.get_source_status = AsyncMock(return_value={"sources": [], "geographic_scope": "romania"})
    source_intel.get_health_summary = AsyncMock(return_value=[])
    source_intel.get_degraded_sources = AsyncMock(return_value=[])
    app.dependency_overrides[source_intelligence_service_dep] = lambda: source_intel

    from app.api.deps import correlation_service_dep

    correlation_svc = MagicMock()
    correlation_svc.list_correlations = AsyncMock(return_value={"correlations": [], "total": 0})
    app.dependency_overrides[correlation_service_dep] = lambda: correlation_svc

    from app.api.deps import evidence_aware_command_center_dep

    evidence_svc = MagicMock()
    evidence_svc.build_intelligence_evidence = AsyncMock(
        return_value={
            "intelligence_cycle_id": None,
            "correlation_cycle_id": None,
            "correlation_state": "disabled",
            "items": [],
        }
    )
    evidence_svc.get_correlation_evidence = AsyncMock(
        return_value={"correlation_id": "test-correlation-id", "correlation_state": "disabled"}
    )
    app.dependency_overrides[evidence_aware_command_center_dep] = lambda: evidence_svc

    from app.api.deps import operational_status_service_dep

    operational_svc = MagicMock()
    operational_svc.get_operational_status = AsyncMock(
        return_value={
            "geographic_scope": "romania",
            "providers": [],
            "intelligence_cycle": {},
            "correlation": {"enabled": False, "state": "disabled", "diagnostics": {}},
            "evidence": {},
            "regions": [],
        }
    )
    app.dependency_overrides[operational_status_service_dep] = lambda: operational_svc

    mock_area_svc = MagicMock()
    mock_area_svc.list_enabled_public = AsyncMock(return_value=[])
    app.dependency_overrides[monitoring_area_service_dep] = lambda: mock_area_svc

    from app.services.aoi_enrichment_service import AoiEnrichmentService

    app.dependency_overrides[aoi_enrichment_service_dep] = lambda: AoiEnrichmentService()
    app.dependency_overrides[intelligence_events_repo_dep] = lambda: bundle.intel_repo

    mock_customer_monitoring = MagicMock()
    mock_customer_monitoring.get_monitoring_status = AsyncMock(
        return_value={
            "geographic_scope": "romania",
            "organization": {"id": "org-1", "name": "Personal Workspace", "role": "owner"},
            "entitlements": {
                "monitored_area_limit": 1,
                "monitored_area_count": 0,
                "monitoring_enabled": True,
                "forest_disturbance_enabled": True,
                "evidence_correlation_enabled": False,
                "live_sources_enabled": False,
                "alert_delivery_enabled": False,
            },
            "monitored_areas": {"enabled_count": 0, "items": []},
            "disturbance_summary": {
                "inside_monitored_area_count": 0,
                "high_critical_investigation_count": 0,
                "authorization_status_default": "unknown",
            },
            "sources": {"available_count": 0, "degraded_count": 0, "degraded_providers": []},
            "correlation_state": "disabled",
        }
    )
    app.dependency_overrides[customer_monitoring_status_service_dep] = (
        lambda: mock_customer_monitoring
    )

    mock_area_svc = MagicMock()
    mock_area_svc.list_enabled_public = AsyncMock(return_value=[])
    app.dependency_overrides[monitoring_area_service_dep] = lambda: mock_area_svc

    async def _override_org_ctx():
        return _mock_org_context()

    app.dependency_overrides[get_organization_context] = _override_org_ctx

    mock_scheduler = MagicMock()
    mock_scheduler._enabled = True
    mock_scheduler._interval_seconds = 3600
    app.state.scheduler = mock_scheduler
    app.state.notification_svc = MagicMock(is_enabled=False, provider_names=[])

    return TestClient(app), bundle


def iter_intelligence_get_routes() -> list[tuple[str, dict[str, Any]]]:
    """All GET routes under ``/analytics/intelligence`` with optional query params."""
    routes: list[tuple[str, dict[str, Any]]] = []
    for route in router.routes:
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", "")
        if "GET" not in methods or not path.startswith("/analytics/intelligence"):
            continue
        if "{" in path:
            path = path.replace("{correlation_id}", "test-correlation-id")
        query: dict[str, Any] = {}
        if path.endswith("/history/daily"):
            query = {"days": 7}
        routes.append((path, query))
    return sorted(routes, key=lambda item: item[0])


def _dependency_call_name(dependant) -> str | None:
    call = dependant.call
    if call is None:
        return None
    name = getattr(call, "__name__", None)
    if name:
        return name
    return type(call).__name__


def _collect_dependency_names(dependant) -> set[str]:
    names: set[str] = set()
    name = _dependency_call_name(dependant)
    if name:
        names.add(name)
    for sub in dependant.dependencies:
        names |= _collect_dependency_names(sub)
    return names


def route_requires_authentication(path: str) -> bool:
    """Return True when the route requires authenticated organization context."""
    normalized = path.replace("test-correlation-id", "{correlation_id}")
    auth_deps = {"get_current_user", "get_organization_context"}
    for route in router.routes:
        if getattr(route, "path", None) not in {path, normalized}:
            continue
        dep_names = _collect_dependency_names(route.dependant)
        return bool(dep_names & auth_deps)
    raise AssertionError(f"Route not found: {path}")
