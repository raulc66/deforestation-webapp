"""Analytics routes - /api/analytics/*"""
from datetime import datetime
from fastapi import APIRouter, Depends, Query

from app.api.deps import analytics_service_dep, get_current_user
from app.models.user import UserPublic

from .analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
async def overview(
    _: UserPublic = Depends(get_current_user),
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
