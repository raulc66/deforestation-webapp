"""ForestEvent - the canonical domain model for all detected forest disturbances.

Every event carries a GeoJSON `location` (2dsphere-indexed) alongside the
flat `latitude` / `longitude` convenience fields used by clients today.
"""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
from .base import BaseDocument, utcnow
from .enums import Severity, EventType, EventStatus
from .geo import GeoJSONPoint


class ForestEvent(BaseDocument):
    title: str
    country: str
    region: str
    latitude: float
    longitude: float
    location: GeoJSONPoint | None = None  # GeoJSON Point; auto-synced from lat/lng
    event_type: EventType = "unknown"
    severity: Severity
    affected_area_ha: float
    confidence: float = 0.8  # 0..1
    source_id: str = "manual"  # FK to DataSource.id
    detected_at: datetime = Field(default_factory=utcnow)
    status: EventStatus = "open"
    land_cover_type: str = "unknown"  # classified by LandCoverService at ingestion
    metadata: dict[str, Any] = Field(default_factory=dict)


class ForestEventCreate(BaseModel):
    title: str
    country: str
    region: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    event_type: EventType = "unknown"
    severity: Severity
    affected_area_ha: float
    confidence: float = 0.8
    source_id: str = "manual"
    detected_at: datetime | None = None
    status: EventStatus = "open"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ForestEventUpdate(BaseModel):
    title: str | None = None
    country: str | None = None
    region: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    event_type: EventType | None = None
    severity: Severity | None = None
    affected_area_ha: float | None = None
    confidence: float | None = None
    source_id: str | None = None
    detected_at: datetime | None = None
    status: EventStatus | None = None
    metadata: dict[str, Any] | None = None


class ForestEventPublic(BaseModel):
    id: str
    title: str
    country: str
    region: str
    latitude: float
    longitude: float
    location: GeoJSONPoint
    event_type: EventType
    severity: Severity
    affected_area_ha: float
    confidence: float
    source_id: str
    source_name: str | None = None  # joined from DataSource on read
    detected_at: datetime
    status: EventStatus
    land_cover_type: str = "unknown"
    metadata: dict[str, Any]
