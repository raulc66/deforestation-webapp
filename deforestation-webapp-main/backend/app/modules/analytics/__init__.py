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
from . import analytics_repository, analytics_service, history_repository, history_service, risk_repository, risk_service  # noqa: F401
from app.services import weather_service as _weather_svc_module  # noqa: F401

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
            "data_quality": "live",
            "sources": "live",
            "intelligence_alerts": "live",
            "temporal_intelligence": "live",
            "regional_baselines": "live",
            "anomaly_detection": "live",
            "intelligence_events": "live",
            "intelligence_events_summary": "live",
            "ingestion_status": "live",
            "notification_status": "live",
            "land_cover_distribution": "live",
            "historical_daily": "live",
            "historical_regions": "live",
            "historical_hotspots": "live",
            "historical_monthly": "live",
            "regional_risk": "live",
            "regional_weather": "live",
            "incident_aggregation": "live",
            "command_center": "partial",
            "threat_intelligence": "live",
        },
        "endpoints": [
            "/api/analytics/overview",
            "/api/analytics/countries",
            "/api/analytics/event-types",
            "/api/analytics/severity",
            "/api/analytics/trends",
            "/api/analytics/data-quality",
            "/api/analytics/sources",
            "/api/analytics/intelligence/alerts",
            "/api/analytics/intelligence/temporal",
            "/api/analytics/intelligence/baselines",
            "/api/analytics/intelligence/anomalies",
            "/api/analytics/intelligence/events/summary",
            "/api/analytics/intelligence/events",
            "/api/analytics/intelligence/ingestion-status",
            "/api/analytics/intelligence/notifications",
            "/api/analytics/intelligence/land-cover",
            "/api/analytics/intelligence/history/daily",
            "/api/analytics/intelligence/history/regions",
            "/api/analytics/intelligence/history/hotspots",
            "/api/analytics/intelligence/history/monthly",
            "/api/analytics/intelligence/risk",
            "/api/analytics/intelligence/weather",
            "/api/analytics/intelligence/incidents",
            "/api/analytics/intelligence/command-center",
            "/api/analytics/intelligence/threats",
            "/api/analytics/intelligence/threat-summary",
        ],
    }


async def run() -> dict:
    return {"name": NAME, "ran": False, "reason": "query via /api/analytics/*"}
