"""Analytics routes - /api/analytics/*"""
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import (
    analytics_service_dep,
    aoi_enrichment_service_dep,
    command_center_service_dep,
    correlation_service_dep,
    customer_monitoring_status_service_dep,
    evidence_aware_command_center_dep,
    forest_context_service_dep,
    get_current_user,
    deny_demo_global_data,
    get_organization_context,
    history_service_dep,
    ingestion_runs_repo_dep,
    intelligence_events_repo_dep,
    monitoring_area_service_dep,
    source_intelligence_service_dep,
    operational_status_service_dep,
    intelligence_events_service_dep,
    notification_history_repo_dep,
    risk_service_dep,
    threat_assessment_service_dep,
    weather_service_dep,
)
from app.core.organization.organization_context import OrganizationContext
from app.models.user import UserPublic
from app.repositories.ingestion_runs_repository import IngestionRunsRepository
from app.repositories.notification_history_repository import NotificationHistoryRepository

from app.services.weather_service import WeatherService
from app.services.forest_context_service import ForestContextService
from .analytics_service import AnalyticsService
from .command_center_service import CommandCenterService
from .history_service import HistoryService
from .risk_service import RiskService
from .intelligence_events_service import IntelligenceEventsService
from .threat_assessment_service import ThreatAssessmentService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
async def overview(
    _: UserPublic = Depends(deny_demo_global_data),
    svc: AnalyticsService = Depends(analytics_service_dep),
):
    """Headline totals: total_events, total_area_affected, open_events,
    resolved_events, average_confidence."""
    return await svc.overview()


@router.get("/countries")
async def by_country(
    _: UserPublic = Depends(get_current_user),
    svc: AnalyticsService = Depends(analytics_service_dep),
):
    """Per-country event_count and affected_area_ha (sorted by count DESC)."""
    return await svc.by_country()


@router.get("/event-types")
async def by_event_type(
    _: UserPublic = Depends(get_current_user),
    svc: AnalyticsService = Depends(analytics_service_dep),
):
    """Per-event-type event_count and affected_area_ha. Zero-fills the full
    taxonomy so frontend axes stay stable."""
    return await svc.by_event_type()


@router.get("/severity")
async def by_severity(
    _: UserPublic = Depends(get_current_user),
    svc: AnalyticsService = Depends(analytics_service_dep),
):
    """Severity distribution: { low, medium, high, critical } each with
    {count, area_ha}."""
    return await svc.by_severity()


@router.get("/trends")
async def trends(
    start_date: datetime | None = Query(None, description="ISO 8601 inclusive; defaults to 30 days ago"),
    end_date: datetime | None = Query(None, description="ISO 8601 inclusive; defaults to now"),
    interval: str = Query("day", description="One of: day, week, month"),
    _: UserPublic = Depends(get_current_user),
    svc: AnalyticsService = Depends(analytics_service_dep),
):
    """Time-series rollup of events bucketed by `interval` (day | week | month).
    When `start_date` / `end_date` are omitted, defaults to the last 30 days."""
    return await svc.trends(start_date, end_date, interval)


@router.get("/data-quality")
async def data_quality(
    _: UserPublic = Depends(get_current_user),
    svc: AnalyticsService = Depends(analytics_service_dep),
):
    """Dataset quality metrics: dedupe rate, confidence distribution, coordinate validity."""
    return await svc.data_quality()


@router.get("/sources")
async def by_source(
    _: UserPublic = Depends(get_current_user),
    svc: AnalyticsService = Depends(analytics_service_dep),
):
    """Per-ingestion-source statistics (FIRMS, CSV, etc.) derived from
    metadata.ingestion.  Events without ingestion metadata are excluded."""
    return await svc.source_statistics()


@router.get("/intelligence/events/summary")
async def intelligence_events_summary(
    _: UserPublic = Depends(get_current_user),
    intelligence_svc: IntelligenceEventsService = Depends(intelligence_events_service_dep),
):
    """Aggregate counts by status and escalation level for persisted events.

    Returns ``{active, resolved, persistent, critical}`` where *persistent*
    and *critical* count only active events at those escalation levels.
    """
    return await intelligence_svc.get_events_summary()


@router.get("/intelligence/events")
async def intelligence_events_endpoint(
    _: UserPublic = Depends(get_current_user),
    intelligence_svc: IntelligenceEventsService = Depends(intelligence_events_service_dep),
):
    """Return persisted IntelligenceEvents grouped by status (read-only).

    Returns ``{active: [...], resolved: [...]}`` from the last reconciliation
    cycle. This endpoint performs no detection or reconciliation writes.
    """
    return await intelligence_svc.get_events()


@router.get("/intelligence/anomalies")
async def intelligence_anomalies(
    _: UserPublic = Depends(deny_demo_global_data),
    svc: AnalyticsService = Depends(analytics_service_dep),
):
    """Rule-based anomaly detection for Romanian regions: regions whose
    current 7-day event count deviates significantly from their 4-week
    baseline are surfaced with a score, severity, and status."""
    return await svc.get_anomalies()


@router.get("/intelligence/map-overlay")
async def intelligence_map_overlay(
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: AnalyticsService = Depends(analytics_service_dep),
    intelligence_svc: IntelligenceEventsService = Depends(intelligence_events_service_dep),
    monitoring_area_svc=Depends(monitoring_area_service_dep),
    aoi_svc=Depends(aoi_enrichment_service_dep),
):
    """Scoped intelligence map contract — authoritative for IntelligenceMap.

    Applies ``GEOGRAPHIC_SCOPE`` via ``GeographicScopePolicy``, preserves
    authoritative coordinates (event / station / activation), and exposes
    ``allow_romania_centroid_fallback`` so clients never apply Romanian admin
    centroids under Europe or All scope.

    Generic unscoped event retrieval remains ``GET /api/events/map``.
    """
    from app.models.base import utcnow
    from app.modules.analytics.map_contract import (
        anomaly_map_marker,
        forest_event_map_marker,
        intelligence_event_map_marker,
    )

    now = utcnow()
    organization_id = org_ctx.organization_id
    areas = await monitoring_area_svc.list_enabled_public(organization_id)
    intel_payload = await intelligence_svc.get_events()
    allow_romania_centroid_fallback = svc.repo.scope_policy.centroids_use_romania_admin_fallback()

    intelligence_markers = [
        intelligence_event_map_marker(
            evt,
            centroids=None,
        )
        for evt in intel_payload.get("active", [])
    ]
    intelligence_markers = [
        aoi_svc.enrich_map_marker(marker, organization_id=organization_id, areas=areas)
        for marker in intelligence_markers
    ]

    if org_ctx.is_demo:
        return {
            "generated_at": now,
            "geographic_scope": svc.geographic_scope,
            "allow_romania_centroid_fallback": False,
            "region_centroids": {},
            "monitored_areas": [
                {
                    "id": area["id"],
                    "name": area["name"],
                    "country": area["country"],
                    "geometry_type": area["geometry_type"],
                    "geometry": area["geometry"],
                }
                for area in areas[:20]
            ],
            "forest_events": [],
            "anomalies": [],
            "intelligence_events": intelligence_markers,
        }

    centroids = await svc.repo.region_event_centroids()
    raw_events = await svc.repo.list_scoped_events_for_map(limit=500)
    anomalies_payload = await svc.get_anomalies()
    intelligence_markers = [
        intelligence_event_map_marker(
            evt,
            centroids=centroids if allow_romania_centroid_fallback else None,
        )
        for evt in intel_payload.get("active", [])
    ]
    intelligence_markers = [
        aoi_svc.enrich_map_marker(marker, organization_id=organization_id, areas=areas)
        for marker in intelligence_markers
    ]

    return {
        "generated_at": now,
        "geographic_scope": svc.geographic_scope,
        "allow_romania_centroid_fallback": allow_romania_centroid_fallback,
        "region_centroids": {
            region: {"latitude": lat, "longitude": lng}
            for region, (lat, lng) in centroids.items()
        },
        "monitored_areas": [
            {
                "id": area["id"],
                "name": area["name"],
                "country": area["country"],
                "geometry_type": area["geometry_type"],
                "geometry": area["geometry"],
            }
            for area in areas[:20]
        ],
        "forest_events": [forest_event_map_marker(e) for e in raw_events],
        "anomalies": [
            anomaly_map_marker(
                a,
                centroids=centroids if allow_romania_centroid_fallback else None,
            )
            for a in anomalies_payload.get("anomalies", [])
        ],
        "intelligence_events": intelligence_markers,
    }


@router.get("/intelligence/baselines")
async def intelligence_baselines(
    _: UserPublic = Depends(get_current_user),
    svc: AnalyticsService = Depends(analytics_service_dep),
):
    """Per-region Romanian activity baselines: average weekly count over the
    preceding 4 weeks vs. current 7-day count, with deviation_percent."""
    return await svc.get_regional_baselines()


@router.get("/intelligence/temporal")
async def intelligence_temporal(
    _: UserPublic = Depends(get_current_user),
    svc: AnalyticsService = Depends(analytics_service_dep),
):
    """Rolling 24 h / 7 d / previous-7 d Romania event counts with trend
    classification (increasing | stable | decreasing)."""
    return await svc.get_temporal_summary()


@router.get("/intelligence/alerts")
async def intelligence_alerts(
    _: UserPublic = Depends(get_current_user),
    svc: AnalyticsService = Depends(analytics_service_dep),
):
    """Rule-based environmental alert evaluation for Romania using existing
    source analytics.  Returns zero or more fire_activity alerts with
    severity, confidence, reliability score, and per-source breakdowns."""
    return await svc.get_alerts()


@router.get("/intelligence/source-status")
async def source_status(
    _: UserPublic = Depends(get_current_user),
    svc=Depends(source_intelligence_service_dep),
):
    """Read-only generalized provider status and health (no credentials)."""
    return await svc.get_source_status()


@router.get("/intelligence/correlations")
async def intelligence_correlations(
    _: UserPublic = Depends(get_current_user),
    svc=Depends(correlation_service_dep),
):
    """Read-only cross-source correlation results (no side effects)."""
    return await svc.list_correlations()


@router.get("/intelligence/ingestion-status")
async def ingestion_status(
    request: Request,
    _: UserPublic = Depends(get_current_user),
    runs_repo: IngestionRunsRepository = Depends(ingestion_runs_repo_dep),
):
    """Background scheduler status and ingestion run history summary.

    Returns the scheduler configuration, the latest run record, and aggregate
    counts of successful vs. failed runs across the last 50 cycles.
    """
    runs = await runs_repo.list_runs(limit=50)
    latest = runs[0] if runs else None
    successful = sum(1 for r in runs if r.get("status") == "success")
    failed = sum(1 for r in runs if r.get("status") == "failed")

    scheduler = getattr(request.app.state, "scheduler", None)
    enabled = getattr(scheduler, "_enabled", False) if scheduler else False
    interval = (
        getattr(scheduler, "_interval_seconds", 3600) // 60
        if scheduler
        else 60
    )

    return {
        "scheduler_enabled": enabled,
        "poll_interval_minutes": interval,
        "latest_run": latest,
        "successful_runs": successful,
        "failed_runs": failed,
    }


@router.get("/intelligence/notifications")
async def notification_status(
    request: Request,
    _: UserPublic = Depends(get_current_user),
    hist_repo: NotificationHistoryRepository = Depends(notification_history_repo_dep),
):
    """Outbound notification system status and recent history summary.

    Returns whether notifications are enabled, which providers are active,
    the last notification record, and aggregate sent/failed counts from the
    most recent 100 attempts.
    """
    recent = await hist_repo.list_recent(limit=100)
    latest = recent[0] if recent else None
    notifications_sent = sum(1 for r in recent if r.get("success"))
    notifications_failed = sum(1 for r in recent if not r.get("success"))

    notif_svc = getattr(request.app.state, "notification_svc", None)
    enabled = notif_svc.is_enabled if notif_svc else False
    providers = notif_svc.provider_names if notif_svc else []

    return {
        "enabled": enabled,
        "providers": providers,
        "last_notification": latest,
        "notifications_sent": notifications_sent,
        "notifications_failed": notifications_failed,
    }


@router.get("/intelligence/land-cover")
async def land_cover_distribution(
    _: UserPublic = Depends(get_current_user),
    svc: AnalyticsService = Depends(analytics_service_dep),
):
    """Per-land-cover-type event counts across all stored events.

    Returns the distribution of land-cover labels assigned by the Romania
    Land Cover Classification Engine.  Useful for the dashboard distribution
    card and any client that wants to understand the data composition.

    Response schema::

        {
            "generated_at": "<ISO-8601>",
            "distribution": [
                {"land_cover": "forest",      "events": 52},
                {"land_cover": "near_forest",  "events": 31},
                {"land_cover": "agriculture",  "events": 18},
                {"land_cover": "urban",        "events": 5},
                {"land_cover": "water",        "events": 3},
                {"land_cover": "unknown",      "events": 121}
            ]
        }
    """
    return await svc.get_land_cover_distribution()


@router.get("/intelligence/clms/dataset")
async def clms_dataset_metadata(
    _: UserPublic = Depends(get_current_user),
    context_svc: ForestContextService = Depends(forest_context_service_dep),
):
    """CLMS contextual dataset metadata (read-only, no download)."""
    return context_svc.describe_dataset()


# ---------------------------------------------------------------------------
# Historical intelligence endpoints
# ---------------------------------------------------------------------------


@router.get("/intelligence/history/daily")
async def history_daily(
    days: int = Query(
        30,
        ge=1,
        le=365,
        description="Look-back window in days. Typical values: 7, 30, 90, 365.",
    ),
    _: UserPublic = Depends(get_current_user),
    svc: HistoryService = Depends(history_service_dep),
):
    """Per-day event and anomaly counts for the last *days* days.

    The series is zero-filled so every date in the range is present.

    Response schema::

        {
            "generated_at": "<ISO-8601>",
            "days": [
                {"date": "2026-06-01", "events": 14, "anomalies": 2},
                ...
            ]
        }
    """
    return await svc.daily_activity(days)


@router.get("/intelligence/history/regions")
async def history_regions(
    _: UserPublic = Depends(get_current_user),
    svc: HistoryService = Depends(history_service_dep),
):
    """Per-region activity comparison: last 30 days vs. the prior 30 days.

    Includes *change_percent* and a *trend* label (increasing / stable /
    decreasing) derived from the pure ``compute_trend`` helper.

    Response schema::

        [
            {
                "region": "Suceava",
                "events_last_30d": 54,
                "events_previous_30d": 38,
                "change_percent": 42.1,
                "trend": "increasing"
            },
            ...
        ]
    """
    return await svc.regional_history()


@router.get("/intelligence/history/hotspots")
async def history_hotspots(
    _: UserPublic = Depends(get_current_user),
    svc: HistoryService = Depends(history_service_dep),
):
    """All-time hotspot ranking sorted by detection count descending.

    Merges per-region average priority scores from intelligence events.

    Response schema::

        [
            {
                "region": "Suceava",
                "detections": 125,
                "average_priority": 0.83,
                "highest_severity": "critical"
            },
            ...
        ]
    """
    return await svc.hotspot_history()


@router.get("/intelligence/history/monthly")
async def history_monthly(
    _: UserPublic = Depends(get_current_user),
    svc: HistoryService = Depends(history_service_dep),
):
    """Per-month event totals with land-cover and anomaly breakdowns.

    Response schema::

        {
            "months": [
                {
                    "month": "2026-05",
                    "events": 88,
                    "anomalies": 3,
                    "forest_events": 52,
                    "urban_events": 7
                },
                ...
            ]
        }
    """
    return await svc.monthly_summary()


@router.get("/intelligence/risk")
async def regional_risk(
    _: UserPublic = Depends(deny_demo_global_data),
    svc: RiskService = Depends(risk_service_dep),
):
    """Compute deterministic fire risk scores for every Romanian region.

    Combines anomaly activity, historical events, forest confidence, priority
    scores and escalation levels into a single normalised risk score (0–1).

    Response schema::

        {
            "generated_at": "...",
            "regions": [
                {
                    "region": "Suceava",
                    "risk_score": 0.8123,
                    "risk_level": "Extreme",
                    "change": "up",
                    "breakdown": {
                        "current_activity":   0.35,
                        "historical_activity": 0.21,
                        "forest":             0.15,
                        "priority":           0.08,
                        "escalation":         0.02
                    }
                },
                ...
            ]
        }

    Sorted descending by ``risk_score``.
    ``change`` compares the current score to the most-recent stored snapshot:
    ``"up"``, ``"down"``, ``"stable"``, or ``"new"`` for first-time regions.
    """
    return await svc.get_risk()


@router.get("/intelligence/weather")
async def regional_weather(
    _: UserPublic = Depends(deny_demo_global_data),
    svc: WeatherService = Depends(weather_service_dep),
):
    """Return cached weather observations for all monitored Romanian regions.

    Data is served from the MongoDB weather cache.  The scheduler refreshes
    the cache automatically every 30 minutes (configurable via
    ``WEATHER_CACHE_TTL_MINUTES``).  An empty ``regions`` list is returned
    when the cache has not been populated yet.

    Response schema::

        {
            "generated_at":      "...",
            "provider":          "Open-Meteo",
            "cache_ttl_minutes": 30,
            "regions": [
                {
                    "region":         "Suceava",
                    "temperature":    22.5,
                    "humidity":       60.0,
                    "wind_speed":     12.3,
                    "wind_direction": 180.0,
                    "precipitation":  0.0,
                    "weather_code":   1,
                    "source":         "open_meteo",
                    "confidence":     1.0,
                    "updated_at":     "..."
                },
                ...
            ]
        }
    """
    return await svc.get_current_weather()


@router.get("/intelligence/incidents")
async def incident_aggregation(
    _: UserPublic = Depends(get_current_user),
    svc: AnalyticsService = Depends(analytics_service_dep),
):
    """Cross-domain incident aggregation.

    Wildfire is the first registered aggregator; additional ecosystem modules
    register their own via :mod:`app.modules.analytics.incident_aggregation`.
    """
    return await svc.get_incident_aggregation()


@router.get("/intelligence/command-center")
async def command_center_snapshot(
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: CommandCenterService = Depends(command_center_service_dep),
    source_intel=Depends(source_intelligence_service_dep),
    evidence_svc=Depends(evidence_aware_command_center_dep),
    intel_repo=Depends(intelligence_events_repo_dep),
    monitoring_area_svc=Depends(monitoring_area_service_dep),
    aoi_svc=Depends(aoi_enrichment_service_dep),
):
    """Command Center readiness snapshot (architecture preparation).

    Returns domain module status, incident aggregation, and active intelligence
    counts by category.  Domains marked ``planned`` have no live pipeline yet.
    """
    snapshot = await svc.get_snapshot()
    snapshot["source_health_summary"] = await source_intel.get_health_summary()
    snapshot["degraded_sources"] = await source_intel.get_degraded_sources()
    evidence = await evidence_svc.build_intelligence_evidence()
    organization_id = org_ctx.organization_id
    areas = await monitoring_area_svc.list_enabled_public(organization_id)
    active_events = await intel_repo.find_active()
    snapshot["intelligence_evidence"] = aoi_svc.enrich_intelligence_evidence_payload(
        evidence,
        active_events=active_events,
        organization_id=organization_id,
        areas=areas,
    )
    return snapshot


@router.get("/intelligence/evidence/{correlation_id}")
async def correlation_evidence_detail(
    correlation_id: str,
    _: UserPublic = Depends(get_current_user),
    evidence_svc=Depends(evidence_aware_command_center_dep),
):
    """Read-only bounded evidence detail for one correlation."""
    detail = await evidence_svc.get_correlation_evidence(correlation_id)
    if detail is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Correlation not found")
    return detail


@router.get("/intelligence/operational-status")
async def operational_status(
    _: UserPublic = Depends(get_current_user),
    svc=Depends(operational_status_service_dep),
):
    """Bounded read-only operational status for multi-region validation."""
    return await svc.get_operational_status()


@router.get("/intelligence/monitoring-status")
async def customer_monitoring_status(
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc=Depends(customer_monitoring_status_service_dep),
):
    """Read-only organization monitoring summary — AOI relevance and disturbance counts."""
    return await svc.get_monitoring_status(org_ctx)


@router.get("/intelligence/threats")
async def intelligence_threats(
    _: UserPublic = Depends(deny_demo_global_data),
    svc: ThreatAssessmentService = Depends(threat_assessment_service_dep),
):
    """Environmental threat assessments for all active intelligence events."""
    return await svc.get_threats()


@router.get("/intelligence/threat-summary")
async def intelligence_threat_summary(
    _: UserPublic = Depends(get_current_user),
    svc: ThreatAssessmentService = Depends(threat_assessment_service_dep),
):
    """Aggregated threat distribution, origin ratio, and priority interventions."""
    return await svc.get_threat_summary()
