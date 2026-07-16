"""Tests for Incident Investigation Management."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.investigation import (
    Investigation,
    InvestigationAssign,
    InvestigationClose,
    InvestigationCreate,
    InvestigationPriority,
    InvestigationStatus,
    InvestigationUpdate,
    TimelineEventType,
)
from app.modules.investigations.investigation_service import InvestigationService

_NOW = datetime(2026, 7, 7, 12, 0, 0, tzinfo=timezone.utc)


def _mock_user():
    from app.models.user import UserPublic
    return UserPublic(
        id="user1",
        email="test@example.com",
        name="Test",
        role="admin",
        provider="local",
        created_at=_NOW,
    )


def _make_investigation(**overrides) -> Investigation:
    data = {
        "id": "inv1",
        "title": "Test Investigation",
        "description": "Desc",
        "status": InvestigationStatus.OPEN,
        "priority": InvestigationPriority.MEDIUM,
        "created_by": "user1",
        "created_at": _NOW,
        "updated_at": _NOW,
        "region": "Suceava",
    }
    data.update(overrides)
    return Investigation(**data)


class TestInvestigationServiceCreate:
    @pytest.mark.anyio
    async def test_create_investigation(self):
        repo = AsyncMock()
        timeline = AsyncMock()
        intel_repo = AsyncMock()
        notif = AsyncMock()

        inserted = _make_investigation()
        repo.insert = AsyncMock(return_value=inserted)
        timeline.insert = AsyncMock()

        svc = InvestigationService(repo, timeline, intel_repo=intel_repo, notification_svc=notif)
        payload = InvestigationCreate(title="New case", description="Details")
        result = await svc.create(payload, created_by="user1")

        assert result["title"] == "Test Investigation"
        repo.insert.assert_called_once()
        assert timeline.insert.call_count >= 1
        notif.notify_investigation_created.assert_called_once()

    @pytest.mark.anyio
    async def test_create_from_intelligence_event(self):
        repo = AsyncMock()
        timeline = AsyncMock()
        intel_repo = AsyncMock()
        intel_repo.find_by_id = AsyncMock(
            return_value={
                "id": "ie1",
                "region": "Harghita",
                "event_type": "anomaly",
                "severity": "high",
                "metadata": {},
            }
        )
        repo.find_by_intelligence_event = AsyncMock(return_value=None)
        repo.insert = AsyncMock(return_value=_make_investigation(region="Harghita", intelligence_event_id="ie1"))
        timeline.insert = AsyncMock()

        svc = InvestigationService(repo, timeline, intel_repo=intel_repo)
        payload = InvestigationCreate(
            title="Intel follow-up",
            intelligence_event_id="ie1",
        )
        result = await svc.create(payload, created_by="user1")

        assert result["region"] == "Harghita"
        intel_repo.find_by_id.assert_called_once_with("ie1")
        event_types = [
            c.args[0].event_type for c in timeline.insert.call_args_list if c.args
        ]
        assert TimelineEventType.THREAT_DETECTED in event_types
        assert TimelineEventType.INVESTIGATION_CREATED in event_types

    @pytest.mark.anyio
    async def test_duplicate_intel_event_rejected(self):
        repo = AsyncMock()
        repo.find_by_intelligence_event = AsyncMock(return_value=_make_investigation())
        svc = InvestigationService(repo, AsyncMock(), intel_repo=AsyncMock())

        from app.core.errors import ConflictError
        with pytest.raises(ConflictError):
            await svc.create(
                InvestigationCreate(title="Dup", intelligence_event_id="ie1"),
                created_by="user1",
            )


class TestInvestigationServiceLifecycle:
    @pytest.mark.anyio
    async def test_assign_updates_status_and_timeline(self):
        repo = AsyncMock()
        timeline = AsyncMock()
        repo.find_by_id = AsyncMock(return_value=_make_investigation())
        repo.update = AsyncMock(return_value=True)
        repo.find_by_id.side_effect = [
            _make_investigation(),
            _make_investigation(
                assigned_to="agent1",
                status=InvestigationStatus.IN_PROGRESS,
            ),
        ]
        timeline.insert = AsyncMock()
        notif = AsyncMock()

        svc = InvestigationService(repo, timeline, notification_svc=notif)
        result = await svc.assign(
            "inv1",
            InvestigationAssign(assigned_to="agent1"),
            actor="user1",
        )

        assert result["assigned_to"] == "agent1"
        notif.notify_investigation_assigned.assert_called_once()

    @pytest.mark.anyio
    async def test_close_investigation(self):
        repo = AsyncMock()
        timeline = AsyncMock()
        repo.find_by_id = AsyncMock(
            side_effect=[
                _make_investigation(),
                _make_investigation(
                    status=InvestigationStatus.CLOSED,
                    resolution="Resolved",
                ),
            ]
        )
        repo.update = AsyncMock(return_value=True)
        timeline.insert = AsyncMock()
        notif = AsyncMock()

        svc = InvestigationService(repo, timeline, notification_svc=notif)
        result = await svc.close(
            "inv1",
            InvestigationClose(resolution="Case closed"),
            actor="user1",
        )

        assert result["status"] == "closed"
        notif.notify_investigation_closed.assert_called_once()

    @pytest.mark.anyio
    async def test_priority_escalation_notification(self):
        repo = AsyncMock()
        timeline = AsyncMock()
        repo.find_by_id = AsyncMock(
            side_effect=[
                _make_investigation(priority=InvestigationPriority.LOW),
                _make_investigation(priority=InvestigationPriority.CRITICAL),
            ]
        )
        repo.update = AsyncMock(return_value=True)
        timeline.insert = AsyncMock()
        notif = AsyncMock()

        svc = InvestigationService(repo, timeline, notification_svc=notif)
        await svc.update(
            "inv1",
            InvestigationUpdate(priority=InvestigationPriority.CRITICAL),
            actor="user1",
        )
        notif.notify_investigation_escalated.assert_called_once()


class TestInvestigationStatistics:
    @pytest.mark.anyio
    async def test_get_statistics(self):
        repo = AsyncMock()
        repo.count_filtered = AsyncMock(side_effect=[2, 1, 0, 1])
        repo.aggregate_by_region = AsyncMock(return_value={"Suceava": 3})
        repo.find_closed_with_duration = AsyncMock(
            return_value=[{"duration_seconds": 7200}, {"duration_seconds": 3600}]
        )

        svc = InvestigationService(repo, AsyncMock())
        stats = await svc.get_statistics()

        assert stats["open_investigations"] == 3
        assert stats["critical_investigations"] == 1
        assert stats["average_resolution_time_hours"] == 1.5
        assert stats["investigations_by_region"]["Suceava"] == 3


class TestInvestigationRoutes:
    def _make_app(self, svc):
        from fastapi import FastAPI
        from app.modules.investigations.investigation_routes import router
        from app.api.deps import get_current_user, investigation_service_dep

        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.dependency_overrides[get_current_user] = lambda: _mock_user()
        app.dependency_overrides[investigation_service_dep] = lambda: svc
        return app

    @pytest.mark.anyio
    async def test_list_investigations(self):
        from fastapi.testclient import TestClient

        svc = AsyncMock()
        svc.list_investigations = AsyncMock(return_value={"investigations": [], "total": 0})
        app = self._make_app(svc)
        with TestClient(app) as client:
            resp = client.get("/api/investigations")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_create_investigation(self):
        from fastapi.testclient import TestClient

        svc = AsyncMock()
        svc.create = AsyncMock(return_value={"id": "inv1", "title": "Case"})
        app = self._make_app(svc)
        with TestClient(app) as client:
            resp = client.post("/api/investigations", json={"title": "Case"})
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_statistics_endpoint(self):
        from fastapi.testclient import TestClient

        svc = AsyncMock()
        svc.get_statistics = AsyncMock(
            return_value={
                "open_investigations": 2,
                "critical_investigations": 1,
                "average_resolution_time_hours": 4.5,
                "investigations_by_region": {"Suceava": 2},
            }
        )
        app = self._make_app(svc)
        with TestClient(app) as client:
            resp = client.get("/api/investigations/statistics")
        assert resp.status_code == 200
        assert resp.json()["open_investigations"] == 2

    @pytest.mark.anyio
    async def test_unauthenticated_rejected(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.modules.investigations.investigation_routes import router
        from app.api.deps import get_current_user, investigation_service_dep
        from app.core.errors import AuthError

        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.dependency_overrides[investigation_service_dep] = lambda: AsyncMock()

        def _raise_auth():
            raise AuthError("Not authenticated")

        app.dependency_overrides[get_current_user] = _raise_auth
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/api/investigations")
        assert resp.status_code in (401, 403, 422, 500)


class TestInvestigationNotifications:
    @pytest.mark.anyio
    async def test_notify_investigation_created(self):
        from app.services.intelligence_notification_service import (
            IntelligenceNotificationService,
        )

        history = AsyncMock()
        provider = MagicMock()
        provider.name = "test"
        provider.send = AsyncMock(return_value=True)
        svc = IntelligenceNotificationService([provider], history)

        await svc.notify_investigation_created(
            {"title": "Case A", "region": "Suceava", "priority": "high"}
        )
        history.create_entry.assert_called()


class TestCommandCenterInvestigations:
    @pytest.mark.anyio
    async def test_snapshot_includes_investigation_stats(self):
        from app.modules.analytics.command_center_service import CommandCenterService

        analytics = MagicMock()
        analytics.overview = AsyncMock(return_value={})
        analytics.by_event_type = AsyncMock(return_value=[])
        analytics.get_anomalies = AsyncMock(return_value={"anomalies": []})

        intel_svc = MagicMock()
        intel_svc.get_events = AsyncMock(return_value={"active": [], "resolved": []})

        inv_svc = AsyncMock()
        inv_svc.get_statistics = AsyncMock(
            return_value={
                "open_investigations": 5,
                "critical_investigations": 2,
                "average_resolution_time_hours": 3.0,
                "investigations_by_region": {"Suceava": 3},
            }
        )

        snapshot = await CommandCenterService(
            analytics, intel_svc, investigation_svc=inv_svc
        ).get_snapshot(generated_at=_NOW)

        assert snapshot["open_investigations"] == 5
        assert snapshot["critical_investigations"] == 2
        assert snapshot["average_resolution_time_hours"] == 3.0
        assert snapshot["investigations_by_region"]["Suceava"] == 3
