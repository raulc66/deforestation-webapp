"""Notification model - delivery records referencing a ForestEvent."""
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field
from .base import BaseDocument, utcnow
from .enums import Severity


NotificationChannel = Literal["in_app", "email", "sms", "webhook"]
NotificationStatus = Literal["pending", "delivered", "read", "dismissed"]


class Notification(BaseDocument):
    # Reference to the canonical ForestEvent
    forest_event_id: str

    # Delivery target
    recipient_user_id: str | None = None  # None = broadcast / system-wide
    channel: NotificationChannel = "in_app"

    # Cached fields from the event for fast filtering and list display
    severity: Severity
    title: str
    cached_payload: dict[str, Any] = Field(default_factory=dict)

    status: NotificationStatus = "pending"
    created_at: datetime = Field(default_factory=utcnow)
    delivered_at: datetime | None = None
    read_at: datetime | None = None


class NotificationPublic(BaseModel):
    id: str
    forest_event_id: str
    recipient_user_id: str | None
    channel: NotificationChannel
    severity: Severity
    title: str
    cached_payload: dict[str, Any]
    status: NotificationStatus
    created_at: datetime
    delivered_at: datetime | None
    read_at: datetime | None


# ---------------------------------------------------------------------------
# Legacy "Alert" response shape kept for backwards-compatible /api/alerts.
# ---------------------------------------------------------------------------
class LegacyGeoPoint(BaseModel):
    lat: float
    lng: float


class LegacyAlertPublic(BaseModel):
    id: str
    title: str
    region: str
    country: str
    severity: Severity
    area_ha: float
    location: LegacyGeoPoint
    source: str
    confidence: float
    detected_at: datetime
    status: str
