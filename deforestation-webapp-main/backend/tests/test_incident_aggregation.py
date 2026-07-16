"""Tests for pluggable incident aggregation layer."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.analytics.incident_aggregation import (
    IncidentAggregationRegistry,
    WildfireIncidentAggregator,
    build_default_incident_registry,
    get_incident_aggregation_registry,
)


def _run(coro):
    return asyncio.run(coro)


class TestWildfireIncidentAggregator:
    @pytest.mark.anyio
    async def test_wraps_existing_analytics_without_duplicate_logic(self):
        analytics = MagicMock()
        analytics.overview = AsyncMock(return_value={"total_events": 10})
        analytics.by_event_type = AsyncMock(
            return_value=[
                {"event_type": "wildfire", "event_count": 4, "affected_area_ha": 12.0},
                {"event_type": "logging", "event_count": 1, "affected_area_ha": 2.0},
            ]
        )
        analytics.get_anomalies = AsyncMock(return_value={"anomalies": [{"region": "A"}]})

        agg = WildfireIncidentAggregator()
        result = await agg.aggregate(analytics)

        analytics.overview.assert_awaited_once()
        analytics.by_event_type.assert_awaited_once()
        analytics.get_anomalies.assert_awaited_once()
        assert result["aggregator_id"] == "wildfire"
        assert result["wildfire_events"]["event_count"] == 4
        assert result["anomaly_count"] == 1


class TestIncidentAggregationRegistry:
    @pytest.mark.anyio
    async def test_default_registry_includes_wildfire(self):
        registry = build_default_incident_registry()
        analytics = MagicMock()
        analytics.overview = AsyncMock(return_value={"total_events": 0})
        analytics.by_event_type = AsyncMock(return_value=[])
        analytics.get_anomalies = AsyncMock(return_value={"anomalies": []})

        payload = await registry.aggregate_all(analytics)
        assert "wildfire" in payload["aggregators"]
        assert "by_incident_category" in payload

    def test_get_incident_aggregation_registry_singleton(self):
        assert get_incident_aggregation_registry() is get_incident_aggregation_registry()

    @pytest.mark.anyio
    async def test_custom_aggregator_can_register(self):
        registry = IncidentAggregationRegistry()

        class StubAggregator(WildfireIncidentAggregator):
            @property
            def aggregator_id(self) -> str:
                return "stub"

        registry.register(StubAggregator())
        assert len(registry.list_aggregators()) == 1
