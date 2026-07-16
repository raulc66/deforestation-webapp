"""Tests for Command Center snapshot assembly."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.analytics.command_center_service import CommandCenterService


_NOW = datetime(2026, 7, 7, 12, 0, 0, tzinfo=timezone.utc)


class TestCommandCenterService:
    @pytest.mark.anyio
    async def test_snapshot_includes_all_domains(self):
        analytics = MagicMock()
        analytics.overview = AsyncMock(return_value={"total_events": 5})
        analytics.by_event_type = AsyncMock(return_value=[])
        analytics.get_anomalies = AsyncMock(return_value={"anomalies": []})

        intel_svc = MagicMock()
        intel_svc.get_events = AsyncMock(
            return_value={
                "active": [{"incident_category": "wildfire", "status": "active"}],
                "resolved": [],
            }
        )

        svc = CommandCenterService(analytics, intel_svc)
        snapshot = await svc.get_snapshot(generated_at=_NOW)

        domain_ids = {d["domain"] for d in snapshot["domains"]}
        assert "forest_health" in domain_ids
        assert "wildlife" in domain_ids
        assert "environment" in domain_ids
        assert "human_activity" in domain_ids

    @pytest.mark.anyio
    async def test_wildlife_domain_is_planned(self):
        analytics = MagicMock()
        analytics.overview = AsyncMock(return_value={})
        analytics.by_event_type = AsyncMock(return_value=[])
        analytics.get_anomalies = AsyncMock(return_value={"anomalies": []})
        intel_svc = MagicMock()
        intel_svc.get_events = AsyncMock(return_value={"active": [], "resolved": []})

        snapshot = await CommandCenterService(analytics, intel_svc).get_snapshot(
            generated_at=_NOW
        )
        wildlife = next(d for d in snapshot["domains"] if d["domain"] == "wildlife")
        assert wildlife["status"] == "planned"
        assert wildlife["capabilities"] == []

    @pytest.mark.anyio
    async def test_active_intel_by_category(self):
        analytics = MagicMock()
        analytics.overview = AsyncMock(return_value={})
        analytics.by_event_type = AsyncMock(return_value=[])
        analytics.get_anomalies = AsyncMock(return_value={"anomalies": []})
        intel_svc = MagicMock()
        intel_svc.get_events = AsyncMock(
            return_value={
                "active": [
                    {"incident_category": "wildfire"},
                    {},  # legacy — defaults to wildfire
                ],
                "resolved": [],
            }
        )

        snapshot = await CommandCenterService(analytics, intel_svc).get_snapshot(
            generated_at=_NOW
        )
        assert snapshot["active_intel_by_category"]["wildfire"] == 2

    @pytest.mark.anyio
    async def test_snapshot_includes_threat_intelligence(self):
        analytics = MagicMock()
        analytics.overview = AsyncMock(return_value={})
        analytics.by_event_type = AsyncMock(return_value=[])
        analytics.get_anomalies = AsyncMock(return_value={"anomalies": []})
        intel_svc = MagicMock()
        intel_svc.get_events = AsyncMock(
            return_value={
                "active": [
                    {
                        "id": "evt-1",
                        "incident_category": "wildfire",
                        "region": "Suceava",
                        "severity": "high",
                        "priority_score": 0.8,
                        "current_score": 0.7,
                        "detection_count": 3,
                        "escalation_level": "persistent",
                        "trend": "worsening",
                    }
                ],
                "resolved": [],
            }
        )

        snapshot = await CommandCenterService(analytics, intel_svc).get_snapshot(
            generated_at=_NOW
        )
        assert "threat_distribution" in snapshot
        assert "human_vs_natural_ratio" in snapshot
        assert "top_threats" in snapshot
        assert "highest_priority_interventions" in snapshot
        assert snapshot["threat_distribution"].get("wildfire", 0) >= 1
