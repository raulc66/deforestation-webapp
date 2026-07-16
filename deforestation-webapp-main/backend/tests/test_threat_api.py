"""API tests for Environmental Threat Intelligence endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest


def _mock_user():
    from app.models.user import UserPublic
    return UserPublic(
        id="1",
        email="test@example.com",
        name="Test",
        role="admin",
        provider="local",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def _make_app(threat_svc):
    from fastapi import FastAPI
    from app.modules.analytics.analytics_routes import router
    from app.api.deps import get_current_user, threat_assessment_service_dep

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: _mock_user()
    app.dependency_overrides[threat_assessment_service_dep] = lambda: threat_svc
    return app


class TestThreatAPIEndpoints:
    @pytest.mark.anyio
    async def test_threats_endpoint_schema(self):
        from fastapi.testclient import TestClient

        threat_svc = AsyncMock()
        threat_svc.get_threats = AsyncMock(
            return_value={
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "threats": [
                    {
                        "threat_category": "wildfire",
                        "origin": "natural",
                        "region": "Suceava",
                        "confidence": 0.8,
                        "risk_contribution": 0.6,
                        "monitoring_priority": "high",
                        "intervention_priority": "medium",
                        "recommended_actions": ["Alert regional fire response teams"],
                    }
                ],
            }
        )
        app = _make_app(threat_svc)
        with TestClient(app) as client:
            resp = client.get("/analytics/intelligence/threats")
        assert resp.status_code == 200
        body = resp.json()
        assert "threats" in body
        assert body["threats"][0]["threat_category"] == "wildfire"

    @pytest.mark.anyio
    async def test_threat_summary_endpoint_schema(self):
        from fastapi.testclient import TestClient

        threat_svc = AsyncMock()
        threat_svc.get_threat_summary = AsyncMock(
            return_value={
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "distribution": {"wildfire": 2},
                "human_vs_natural_ratio": {"human": 0.0, "natural": 1.0, "environmental": 0.0, "unknown": 0.0},
                "top_threats": [],
                "highest_priority_interventions": [],
                "most_affected_domains": [{"domain": "forest_health", "threat_count": 2}],
            }
        )
        app = _make_app(threat_svc)
        with TestClient(app) as client:
            resp = client.get("/analytics/intelligence/threat-summary")
        assert resp.status_code == 200
        body = resp.json()
        assert "distribution" in body
        assert "human_vs_natural_ratio" in body

    @pytest.mark.anyio
    async def test_threats_requires_auth(self):
        from fastapi.testclient import TestClient
        from app.core.errors import AuthError

        threat_svc = AsyncMock()
        threat_svc.get_threats = AsyncMock(return_value={"threats": []})

        from fastapi import FastAPI
        from app.modules.analytics.analytics_routes import router
        from app.api.deps import get_current_user, threat_assessment_service_dep

        def raise_auth_error():
            raise AuthError("Not authenticated")

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = raise_auth_error
        app.dependency_overrides[threat_assessment_service_dep] = lambda: threat_svc

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/analytics/intelligence/threats")
        assert resp.status_code in (401, 403, 422, 500)
