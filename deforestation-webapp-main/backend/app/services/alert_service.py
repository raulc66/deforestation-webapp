"""Backwards-compatible AlertService.

Now reads from ForestEventService. The legacy `source` field is the human
DataSource name (joined via ForestEventService's source_name resolution).
"""
import logging
from app.models.notification import LegacyAlertPublic, LegacyGeoPoint
from app.services.forest_event_service import ForestEventService

logger = logging.getLogger("forestwatch.alerts")


class AlertService:
    """Thin compatibility adapter over ForestEventService."""

    def __init__(self, events: ForestEventService):
        self.events = events

    async def list_alerts(
        self, severity: str | None = None, limit: int = 200
    ) -> list[LegacyAlertPublic]:
        items = await self.events.list_events(severity=severity, limit=limit)
        return [
            LegacyAlertPublic(
                id=e.id,
                title=e.title,
                region=e.region,
                country=e.country,
                severity=e.severity,
                area_ha=e.affected_area_ha,
                location=LegacyGeoPoint(lat=e.latitude, lng=e.longitude),
                source=e.source_name or e.source_id,
                confidence=e.confidence,
                detected_at=e.detected_at,
                status=e.status,
            )
            for e in items
        ]

    async def get_stats(self) -> dict:
        return await self.events.get_stats()
