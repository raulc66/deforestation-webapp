"""Threat assessment models — strongly typed intelligence output."""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.core.ecosystem.domains import EcosystemDomain
from app.core.ecosystem.threat_categories import ThreatCategory, ThreatOrigin


class PriorityLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatAssessment(BaseModel):
    """Central intelligence classification for an ecosystem threat."""

    threat_category: ThreatCategory
    confidence: float = Field(ge=0.0, le=1.0)
    risk_contribution: float = Field(ge=0.0, le=1.0)
    affected_domains: list[EcosystemDomain]
    origin: ThreatOrigin
    long_term_impact: PriorityLevel
    monitoring_priority: PriorityLevel
    intervention_priority: PriorityLevel
    recommended_actions: list[str] = Field(default_factory=list)
    # Context (optional — populated when derived from a persisted event)
    region: str | None = None
    incident_category: str | None = None
    source_event_id: str | None = None
