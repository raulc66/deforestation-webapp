"""WP6.4 — intelligence read-path write-spy suite."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.analytics.intelligence_events_service import IntelligenceEventsService
from tests.fixtures.intelligence_write_spy import (
    build_intelligence_read_client,
    build_intelligence_write_spy,
    iter_intelligence_get_routes,
    route_requires_authentication,
    tracking_intel_repo,
)

_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
_INTELLIGENCE_GET_ROUTES = iter_intelligence_get_routes()

_COMPUTE_ONLY_ROUTES = {
    "/analytics/intelligence/anomalies",
    "/analytics/intelligence/baselines",
}


class TestIntelligenceReadWriteSpy:
    @pytest.mark.parametrize("path,query", _INTELLIGENCE_GET_ROUTES)
    def test_read_endpoint_performs_no_persistence_or_reconciliation(
        self, path: str, query: dict
    ):
        client, spy = build_intelligence_read_client()

        with patch(
            "app.modules.analytics.detector_registry.get_detector_registry"
        ) as registry_mock:
            resp = client.get(path, params=query)

        assert resp.status_code == 200, f"{path} returned {resp.status_code}: {resp.text}"
        spy.assert_no_persistence_or_reconciliation()
        if path not in _COMPUTE_ONLY_ROUTES:
            registry_mock.assert_not_called()

    @pytest.mark.parametrize("path,query", _INTELLIGENCE_GET_ROUTES)
    def test_repeated_get_does_not_mutate_intel_repository(self, path: str, query: dict):
        repo = tracking_intel_repo(
            [
                {
                    "id": "evt-1",
                    "event_type": "anomaly",
                    "region": "Suceava",
                    "status": "active",
                    "severity": "high",
                    "escalation_level": "normal",
                    "previous_score": None,
                    "trend": "new",
                    "priority_score": 0.5,
                    "first_detected_at": _NOW,
                    "last_detected_at": _NOW,
                    "detection_count": 1,
                    "current_score": 0.6,
                    "metadata": {},
                    "incident_category": "wildfire",
                }
            ]
        )
        spy = build_intelligence_write_spy()
        spy.intel_repo = repo
        spy.intel_svc = IntelligenceEventsService(repo)
        spy.intel_svc.reconcile = AsyncMock()
        spy.intel_svc.reconcile_detections = AsyncMock()

        client, spy = build_intelligence_read_client(spy)

        before = list(repo._stored)
        client.get(path, params=query)
        client.get(path, params=query)
        after = list(repo._stored)

        assert before == after
        spy.assert_no_persistence_or_reconciliation()

    @pytest.mark.parametrize("path,_query", _INTELLIGENCE_GET_ROUTES)
    def test_read_endpoint_requires_authentication_dependency(self, path: str, _query: dict):
        assert route_requires_authentication(path) is True

    def test_events_endpoint_returns_previously_persisted_state(self):
        stored = [
            {
                "id": "evt-persisted",
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
                "detection_count": 3,
                "current_score": 0.648,
                "metadata": {},
                "incident_category": "wildfire",
            }
        ]
        spy = build_intelligence_write_spy()
        spy.intel_repo._stored.extend(stored)
        spy.intel_repo.find_all = AsyncMock(return_value=list(stored))
        client, spy = build_intelligence_read_client(spy)

        body = client.get("/analytics/intelligence/events").json()

        assert body["active"][0]["region"] == "Suceava"
        assert body["active"][0]["detection_count"] == 3
        spy.assert_no_persistence_or_reconciliation()

    def test_anomalies_may_compute_without_persisting(self):
        """Computation (detect_all) on read is allowed; persistence is not."""
        from app.modules.analytics.analytics_service import AnalyticsService

        repo = MagicMock()
        repo.regional_baselines = AsyncMock(return_value=[])
        intel_repo = tracking_intel_repo()
        intel_svc = IntelligenceEventsService(intel_repo)
        intel_svc.reconcile = AsyncMock()
        intel_svc.reconcile_detections = AsyncMock()
        analytics = AnalyticsService(repo)

        with patch(
            "app.modules.analytics.detector_registry.get_detector_registry"
        ) as registry_factory:
            registry = registry_factory.return_value
            registry.detect_all = MagicMock(return_value=[])

            import asyncio

            asyncio.run(analytics.get_anomalies())

        registry.detect_all.assert_called_once()
        intel_repo.create.assert_not_called()
        intel_repo.update.assert_not_called()
        intel_repo.resolve.assert_not_called()
        intel_svc.reconcile.assert_not_called()
        intel_svc.reconcile_detections.assert_not_called()
