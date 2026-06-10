"""Notification routes - /api/notifications/*"""
from fastapi import APIRouter, Depends, Query
from app.api.deps import notification_service_dep, get_current_user
from app.models.notification import NotificationPublic
from app.models.user import UserPublic
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationPublic])
async def list_notifications(
    limit: int = Query(default=100, le=500),
    user: UserPublic = Depends(get_current_user),
    svc: NotificationService = Depends(notification_service_dep),
):
    return await svc.list_for_user(user.id, limit=limit)


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    _: UserPublic = Depends(get_current_user),
    svc: NotificationService = Depends(notification_service_dep),
):
    await svc.mark_read(notification_id)
    return {"ok": True}
