"""Tenant forest monitoring area (AOI) domain models."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .base import BaseDocument, utcnow


class ForestMonitoringArea(BaseDocument):
    organization_id: str = ""
    tenant_id: str = ""  # legacy — organization_id is authoritative
    name: str
    geometry: dict[str, Any]
    geometry_type: str
    country: str = "Romania"
    enabled: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ForestMonitoringAreaCreate(BaseModel):
    name: str
    geometry: dict[str, Any]
    country: str = "Romania"
    enabled: bool = True


class ForestMonitoringAreaUpdate(BaseModel):
    name: str | None = None
    geometry: dict[str, Any] | None = None
    country: str | None = None
    enabled: bool | None = None


class ForestMonitoringAreaPublic(BaseModel):
    id: str
    organization_id: str
    tenant_id: str
    name: str
    geometry: dict[str, Any]
    geometry_type: str
    country: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
    area_hectares: float | None = None
    intelligence_summary: dict[str, Any] | None = None
