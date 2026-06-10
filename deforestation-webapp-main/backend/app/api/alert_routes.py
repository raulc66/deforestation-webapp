"""Alert routes - /api/alerts/*

Legacy compatibility surface. Returns ForestEvent data adapted to the old
alert shape (`area_ha`, `location.{lat,lng}`, `source`, etc.) so the existing
dashboard/map clients keep working unchanged.

New clients should prefer /api/events.
"""
from fastapi import APIRouter, Depends, Query
from app.api.deps import alert_service_dep, get_current_user
from app.models.user import UserPublic
from app.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["alerts (legacy)"])


@router.get("")
async def list_alerts(
    severity: str | None = Query(default=None),
    limit: int = Query(default=200, le=1000),
    _: UserPublic = Depends(get_current_user),
    svc: AlertService = Depends(alert_service_dep),
):
    return await svc.list_alerts(severity=severity, limit=limit)


@router.get("/stats")
async def alert_stats(
    _: UserPublic = Depends(get_current_user),
    svc: AlertService = Depends(alert_service_dep),
):
    return await svc.get_stats()
