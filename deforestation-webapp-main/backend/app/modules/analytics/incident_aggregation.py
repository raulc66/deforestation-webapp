"""Generic incident aggregation layer.

Each :class:`IncidentAggregator` implementation wraps existing analytics
without duplicating business logic.  Wildfire is the first (default) domain.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.core.ecosystem.incident_categories import INCIDENT_CATEGORIES, IncidentCategory

if TYPE_CHECKING:
    from .analytics_service import AnalyticsService


class IncidentAggregator(ABC):
    """Contract for domain-specific incident rollups."""

    @property
    @abstractmethod
    def aggregator_id(self) -> str:
        """Stable identifier (e.g. ``wildfire``)."""

    @property
    @abstractmethod
    def incident_categories(self) -> tuple[str, ...]:
        """Categories this aggregator contributes to."""

    @abstractmethod
    async def aggregate(self, analytics_svc: "AnalyticsService") -> dict:
        """Return a domain-specific aggregation payload."""


class WildfireIncidentAggregator(IncidentAggregator):
    """Wraps existing wildfire / anomaly analytics — no duplicate queries."""

    @property
    def aggregator_id(self) -> str:
        return "wildfire"

    @property
    def incident_categories(self) -> tuple[str, ...]:
        return (IncidentCategory.WILDFIRE.value,)

    async def aggregate(self, analytics_svc: "AnalyticsService") -> dict:
        overview = await analytics_svc.overview()
        by_event_type = await analytics_svc.by_event_type()
        anomalies = await analytics_svc.get_anomalies()
        wildfire_row = next(
            (row for row in by_event_type if row.get("event_type") == "wildfire"),
            {"event_count": 0, "affected_area_ha": 0.0},
        )
        return {
            "aggregator_id": self.aggregator_id,
            "incident_categories": list(self.incident_categories),
            "overview": overview,
            "wildfire_events": wildfire_row,
            "anomaly_count": len(anomalies.get("anomalies", [])),
            "anomalies": anomalies.get("anomalies", []),
        }


class IncidentAggregationRegistry:
    """Register additional domain aggregators without modifying analytics core."""

    def __init__(self) -> None:
        self._aggregators: dict[str, IncidentAggregator] = {}

    def register(self, aggregator: IncidentAggregator) -> None:
        self._aggregators[aggregator.aggregator_id] = aggregator

    def list_aggregators(self) -> list[IncidentAggregator]:
        return list(self._aggregators.values())

    async def aggregate_all(self, analytics_svc: "AnalyticsService") -> dict:
        results: dict[str, dict] = {}
        for agg in self._aggregators.values():
            results[agg.aggregator_id] = await agg.aggregate(analytics_svc)

        by_category: dict[str, dict] = {cat: {"event_count": 0} for cat in INCIDENT_CATEGORIES}
        for payload in results.values():
            for cat in payload.get("incident_categories", []):
                if cat in by_category:
                    by_category[cat]["source_aggregator"] = payload["aggregator_id"]

        wildfire = results.get("wildfire", {})
        wf_events = wildfire.get("wildfire_events", {})
        by_category[IncidentCategory.WILDFIRE.value]["event_count"] = int(
            wf_events.get("event_count", 0)
        )
        by_category[IncidentCategory.WILDFIRE.value]["affected_area_ha"] = wf_events.get(
            "affected_area_ha", 0.0
        )

        return {
            "aggregators": results,
            "by_incident_category": by_category,
        }


def build_default_incident_registry() -> IncidentAggregationRegistry:
    registry = IncidentAggregationRegistry()
    registry.register(WildfireIncidentAggregator())
    return registry


_default_registry = build_default_incident_registry()


def get_incident_aggregation_registry() -> IncidentAggregationRegistry:
    return _default_registry
