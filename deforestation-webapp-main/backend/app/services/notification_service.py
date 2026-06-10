"""Notification service - generates and queries notifications referencing
ForestEvent records.
"""
import logging
from app.core.errors import NotFoundError
from app.models.base import utcnow
from app.models.forest_event import ForestEventPublic
from app.models.notification import (
    Notification,
    NotificationPublic,
    NotificationChannel,
)
from app.repositories.notification_repository import NotificationRepository

logger = logging.getLogger("forestwatch.notifications")


def to_public(n: Notification) -> NotificationPublic:
    return NotificationPublic(
        id=n.id,
        forest_event_id=n.forest_event_id,
        recipient_user_id=n.recipient_user_id,
        channel=n.channel,
        severity=n.severity,
        title=n.title,
        cached_payload=n.cached_payload,
        status=n.status,
        created_at=n.created_at,
        delivered_at=n.delivered_at,
        read_at=n.read_at,
    )


class NotificationService:
    def __init__(self, repo: NotificationRepository):
        self.repo = repo

    async def create_from_event(
        self,
        event: ForestEventPublic,
        recipient_user_id: str | None = None,
        channel: NotificationChannel = "in_app",
    ) -> NotificationPublic:
        notif = Notification(
            forest_event_id=event.id,
            recipient_user_id=recipient_user_id,
            channel=channel,
            severity=event.severity,
            title=event.title,
            cached_payload={
                "country": event.country,
                "region": event.region,
                "event_type": event.event_type,
                "affected_area_ha": event.affected_area_ha,
                "detected_at": event.detected_at,
            },
        )
        notif = await self.repo.insert(notif)
        logger.info("Created notification %s for event %s", notif.id, event.id)
        return to_public(notif)

    async def list_for_user(
        self, user_id: str | None, limit: int = 100
    ) -> list[NotificationPublic]:
        docs = await self.repo.find_for_user(user_id, limit=limit)
        return [to_public(d) for d in docs]

    async def mark_read(self, notification_id: str) -> None:
        ok = await self.repo.mark_read(notification_id, utcnow())
        if not ok:
            raise NotFoundError("Notification not found")
