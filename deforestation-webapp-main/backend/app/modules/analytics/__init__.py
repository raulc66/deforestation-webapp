"""Analytics module - deterministic aggregations over ForestEvents.

Public surface:
    analytics_repository.AnalyticsRepository   — raw MongoDB pipelines
    analytics_service.AnalyticsService          — frontend-ready shaping
    analytics_routes.router                     — FastAPI routes /api/analytics/*

No ML / no predictions / no external integrations.
"""
# NOTE: analytics_routes is intentionally NOT eagerly imported here to avoid a
# circular import (routes -> app.api.deps -> this package). server.py imports
# the router directly: `from app.modules.analytics.analytics_routes import router`.
from . import analytics_repository, analytics_service  # noqa: F401

NAME = "analytics"
STATUS = "active"
DESCRIPTION = (
    "Aggregate deforestation metrics across regions, event types, severity and "
    "time. Powers dashboards and charts."
)


def module_info() -> dict:
    return {
        "name": NAME,
        "status": STATUS,
        "description": DESCRIPTION,
        "capabilities": {
            "overview": "live",
            "by_country": "live",
            "by_event_type": "live",
            "by_severity": "live",
            "trends": "live",
        },
        "endpoints": [
            "/api/analytics/overview",
            "/api/analytics/countries",
            "/api/analytics/event-types",
            "/api/analytics/severity",
            "/api/analytics/trends",
        ],
    }


async def run() -> dict:
    return {"name": NAME, "ran": False, "reason": "query via /api/analytics/*"}
