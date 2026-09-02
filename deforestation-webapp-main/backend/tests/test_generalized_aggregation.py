"""Generalized aggregation tests (Package A)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.ecosystem.incident_categories import IncidentCategory
from app.modules.analytics.incident_aggregation import (
    IncidentAggregationRegistry,
    WildfireIncidentAggregator,
    build_default_incident_registry,
)


class TestGeneralizedAggregation:
    @pytest.mark.anyio
    async def test_by_incident_category_from_event_type_mapping(self):
        registry = build_default_incident_registry()
        analytics = MagicMock()
        analytics.overview = AsyncMock(return_value={"total_events": 12})
        analytics.by_event_type = AsyncMock(
            return_value=[
                {"event_type": "wildfire", "event_count": 8, "affected_area_ha": 40.0},
                {"event_type": "logging", "event_count": 3, "affected_area_ha": 6.0},
            ]
        )
        analytics.get_anomalies = AsyncMock(return_value={"anomalies": []})

        payload = await registry.aggregate_all(analytics)

        assert payload["by_incident_category"]["wildfire"]["event_count"] == 8
        assert payload["by_incident_category"]["wildfire"]["affected_area_ha"] == 40.0
        assert payload["by_incident_category"]["illegal_logging"]["event_count"] == 3
        assert payload["by_incident_category"]["illegal_logging"]["affected_area_ha"] == 6.0
        assert payload["by_incident_category"]["wildfire"]["source_aggregator"] == "wildfire"

    @pytest.mark.anyio
    async def test_second_category_cannot_alter_wildfire_rollup(self):
        """Logging events must not change wildfire category counts."""
        registry = IncidentAggregationRegistry()
        registry.register(WildfireIncidentAggregator())

        base_types = [
            {"event_type": "wildfire", "event_count": 5, "affected_area_ha": 20.0},
        ]
        with_logging = base_types + [
            {"event_type": "logging", "event_count": 9, "affected_area_ha": 45.0},
        ]

        async def _payload(event_types):
            analytics = MagicMock()
            analytics.overview = AsyncMock(return_value={})
            analytics.by_event_type = AsyncMock(return_value=event_types)
            analytics.get_anomalies = AsyncMock(return_value={"anomalies": []})
            return await registry.aggregate_all(analytics)

        base_payload = await _payload(base_types)
        extra_payload = await _payload(with_logging)

        assert (
            base_payload["by_incident_category"][IncidentCategory.WILDFIRE.value]
            == extra_payload["by_incident_category"][IncidentCategory.WILDFIRE.value]
        )
        assert extra_payload["by_incident_category"]["illegal_logging"]["event_count"] == 9
