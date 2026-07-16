"""Investigation domain models — operational workflow objects linked to intelligence."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from .base import BaseDocument, utcnow


class InvestigationStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"


class InvestigationPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TimelineEventType(StrEnum):
    THREAT_DETECTED = "threat_detected"
    INVESTIGATION_CREATED = "investigation_created"
    ASSIGNED = "assigned"
    EVIDENCE_UPLOADED = "evidence_uploaded"
    COMMENT_ADDED = "comment_added"
    STATUS_CHANGED = "status_changed"
    PRIORITY_CHANGED = "priority_changed"
    CLOSED = "closed"


class Investigation(BaseDocument):
    """Persisted operational investigation — independent from intel generation."""

    intelligence_event_id: str | None = None
    title: str
    description: str = ""
    status: InvestigationStatus = InvestigationStatus.OPEN
    priority: InvestigationPriority = InvestigationPriority.MEDIUM
    assigned_to: str | None = None
    organization: str = ""
    created_by: str
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    closed_at: datetime | None = None
    resolution: str | None = None
    tags: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    actual_actions: list[str] = Field(default_factory=list)
    outcome: str | None = None
    region: str | None = None
    archived: bool = False


class InvestigationTimelineEntry(BaseDocument):
    """Immutable audit entry for an investigation timeline."""

    investigation_id: str
    event_type: TimelineEventType
    message: str
    actor: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


class InvestigationCreate(BaseModel):
    intelligence_event_id: str | None = None
    title: str
    description: str = ""
    priority: InvestigationPriority = InvestigationPriority.MEDIUM
    assigned_to: str | None = None
    organization: str = ""
    tags: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class InvestigationUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: InvestigationStatus | None = None
    priority: InvestigationPriority | None = None
    assigned_to: str | None = None
    organization: str | None = None
    tags: list[str] | None = None
    recommended_actions: list[str] | None = None
    actual_actions: list[str] | None = None
    outcome: str | None = None


class InvestigationAssign(BaseModel):
    assigned_to: str
    organization: str | None = None


class InvestigationClose(BaseModel):
    resolution: str
    outcome: str | None = None
    actual_actions: list[str] | None = None


class InvestigationPublic(BaseModel):
    id: str
    intelligence_event_id: str | None = None
    title: str
    description: str
    status: InvestigationStatus
    priority: InvestigationPriority
    assigned_to: str | None = None
    organization: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    resolution: str | None = None
    tags: list[str]
    recommended_actions: list[str]
    actual_actions: list[str]
    outcome: str | None = None
    region: str | None = None
