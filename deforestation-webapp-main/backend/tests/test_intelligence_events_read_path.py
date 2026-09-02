"""WP6.1 — intelligence events read path must not reconcile or write."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import analytics_service_dep, get_current_user, intelligence_events_service_dep
from app.models.user import UserPublic
from app.modules.analytics.analytics_routes import router
from app.modules.analytics.analytics_service import AnalyticsService
from app.modules.analytics.intelligence_events_service import IntelligenceEventsService

_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

_PERSISTED_EVENTS = {
    "active": [
        {
            "id": "evt-001",
            "event_type": "anomaly",
            "region": "Suceava",
            "status": "active",
            "severity": "high",
            "escalation_level": "normal",
            "previous_score": None,
            "trend": "new",
            "priority_score": 0.5598,
            "first_detected_at": _NOW,
            "last_detected_at": _NOW,
            "detection_count": 1,
            "current_score": 0.648,
            "metadata": {
                "baseline_events": 1,
                "current_events": 6,
                "deviation_percent": 500.0,
            },
        }
    ],
    "resolved": [],
}


def _mock_user() -> UserPublic:
    return UserPublic(
        id="1",
        email="test@example.com",
        name="Test",
        role="admin",
        provider="local",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def _build_client(
    intelligence_svc: IntelligenceEventsService | MagicMock,
    analytics_svc: AnalyticsService | MagicMock | None = None,
) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = _mock_user
    app.dependency_overrides[intelligence_events_service_dep] = lambda: intelligence_svc
    if analytics_svc is not None:
        app.dependency_overrides[analytics_service_dep] = lambda: analytics_svc
    return TestClient(app)


def _tracking_repo(all_events: list[dict] | None = None) -> MagicMock:
    repo = MagicMock()
    events = list(all_events or [])
    repo.find_all = AsyncMock(return_value=events)
    repo.find_active = AsyncMock(return_value=[e for e in events if e.get("status") == "active"])
    repo.create = AsyncMock(side_effect=lambda payload: events.append({**payload, "id": "new"}))
    repo.update = AsyncMock()
    repo.resolve = AsyncMock()
    return repo


class TestIntelligenceEventsReadPath:
    def test_get_returns_persisted_events_without_reconciliation(self):
        repo = _tracking_repo(
            [{**_PERSISTED_EVENTS["active"][0], "incident_category": "wildfire"}]
        )
        intel_svc = IntelligenceEventsService(repo)
        client = _build_client(intel_svc)

        with patch.object(
            AnalyticsService,
            "reconcile_intelligence_events",
            new_callable=AsyncMock,
        ) as reconcile_mock:
            resp = client.get("/analytics/intelligence/events")

        assert resp.status_code == 200
        body = resp.json()
        assert body["active"][0]["region"] == "Suceava"
        assert body["active"][0]["incident_category"] == "wildfire"
        reconcile_mock.assert_not_called()
        repo.create.assert_not_called()
        repo.update.assert_not_called()
        repo.resolve.assert_not_called()

    def test_get_performs_zero_repository_writes(self):
        repo = _tracking_repo([])
        intel_svc = IntelligenceEventsService(repo)
        client = _build_client(intel_svc)

        client.get("/analytics/intelligence/events")

        repo.create.assert_not_called()
        repo.update.assert_not_called()
        repo.resolve.assert_not_called()

    def test_get_does_not_invoke_detector_or_reconcile_stack(self):
        intel_svc = MagicMock(spec=IntelligenceEventsService)
        intel_svc.get_events = AsyncMock(return_value=_PERSISTED_EVENTS)
        intel_svc.reconcile = AsyncMock()
        intel_svc.reconcile_detections = AsyncMock()
        analytics_svc = MagicMock(spec=AnalyticsService)
        analytics_svc.reconcile_intelligence_events = AsyncMock()
        client = _build_client(intel_svc, analytics_svc=analytics_svc)

        with patch(
            "app.modules.analytics.detector_registry.get_detector_registry"
        ) as registry_mock:
            resp = client.get("/analytics/intelligence/events")

        assert resp.status_code == 200
        intel_svc.get_events.assert_called_once()
        intel_svc.reconcile.assert_not_called()
        intel_svc.reconcile_detections.assert_not_called()
        analytics_svc.reconcile_intelligence_events.assert_not_called()
        registry_mock.assert_not_called()

    def test_repeated_get_calls_do_not_mutate_persisted_state(self):
        stored = [{**_PERSISTED_EVENTS["active"][0], "incident_category": "wildfire"}]
        repo = _tracking_repo(stored)
        intel_svc = IntelligenceEventsService(repo)
        client = _build_client(intel_svc)

        first = client.get("/analytics/intelligence/events")
        second = client.get("/analytics/intelligence/events")

        assert first.json() == second.json()
        assert len(stored) == 1
        repo.create.assert_not_called()
        repo.update.assert_not_called()
        repo.resolve.assert_not_called()

    def test_read_model_omits_spatial_key_and_signal_type(self):
        stored = [
            {
                **_PERSISTED_EVENTS["active"][0],
                "incident_category": "wildfire",
                "spatial_key": "Suceava",
                "signal_type": "baseline_deviation",
            }
        ]
        repo = _tracking_repo(stored)
        intel_svc = IntelligenceEventsService(repo)
        client = _build_client(intel_svc)

        body = client.get("/analytics/intelligence/events").json()
        event = body["active"][0]

        assert "spatial_key" not in event
        assert "signal_type" not in event
        assert event["incident_category"] == "wildfire"

    def test_route_still_requires_authentication_dependency(self):
        from app.modules.analytics import analytics_routes

        route = next(
            r for r in analytics_routes.router.routes
            if getattr(r, "path", None) == "/analytics/intelligence/events"
        )
        dep_names = {d.call.__name__ for d in route.dependant.dependencies if d.call}
        assert "get_current_user" in dep_names


class TestSchedulerReconciliationOwnership:
    @pytest.mark.anyio
    async def test_scheduler_still_invokes_reconciliation_command(self):
        from app.services.scheduler_service import SchedulerService

        firms = AsyncMock()
        firms.run = AsyncMock(return_value={"total": 0, "created": 0, "skipped": 0})

        analytics = AsyncMock()
        analytics.reconcile_intelligence_events = AsyncMock(return_value={"active": [], "resolved": []})

        runs_repo = AsyncMock()
        runs_repo.create_run = AsyncMock(
            return_value={
                "events_fetched": 0,
                "events_inserted": 0,
                "duplicates_skipped": 0,
                "duration_seconds": 0.1,
            }
        )

        scheduler = SchedulerService(
            firms_provider=firms,
            events_service=AsyncMock(),
            events_repo=AsyncMock(),
            analytics_service=analytics,
            intelligence_service=AsyncMock(),
            runs_repo=runs_repo,
            poll_interval_minutes=60,
            enabled=True,
            firms_source_id=None,
        )

        await scheduler._run_cycle()

        analytics.reconcile_intelligence_events.assert_called_once()
