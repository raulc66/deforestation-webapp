"""Notification repository (formerly AlertRepository)."""
from datetime import datetime
from app.models.notification import Notification
from .base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    collection_name = "notifications"
    model = Notification

    async def find_for_user(self, user_id: str | None, limit: int = 100) -> list[Notification]:
        # Includes broadcast notifications (recipient_user_id = None) + user-specific
        query = {"$or": [{"recipient_user_id": user_id}, {"recipient_user_id": None}]}
        return await self.find_many(query, limit=limit, sort=[("created_at", -1)])

    async def mark_read(self, notification_id: str, when: "datetime") -> bool:
        return await self.update(notification_id, {"status": "read", "read_at": when})
