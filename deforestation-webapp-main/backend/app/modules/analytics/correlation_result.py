"""Immutable cross-source correlation result models."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CorrelationParticipant(BaseModel):
    """One detection participating in a correlation."""

    model_config = ConfigDict(frozen=True)

    incident_category: str
    spatial_key: str
    provider_id: str | None = None
    source_event_id: str | None = None
    detected_at: datetime
    role: str = "participant"


class CorrelationResult(BaseModel):
    """Deterministic cross-source correlation output."""

    model_config = ConfigDict(frozen=True)

    correlation_id: str
    canonical_incident_category: str
    canonical_spatial_key: str
    relationship_type: str
    correlation_rule: str
    participants: tuple[CorrelationParticipant, ...]
    participating_provider_ids: tuple[str, ...]
    spatial_relationship: str
    temporal_relationship: str
    strength: float = Field(ge=0.0, le=1.0)
    created_at: datetime
    provenance_summary: dict[str, Any] = Field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def as_read_model(self) -> dict[str, Any]:
        """Bounded read-model projection — no raw payloads or credentials."""
        return {
            "correlation_id": self.correlation_id,
            "canonical_incident_category": self.canonical_incident_category,
            "canonical_spatial_key": self.canonical_spatial_key,
            "categories": sorted({p.incident_category for p in self.participants}),
            "participating_sources": list(self.participating_provider_ids),
            "evidence_count": len(self.participants),
            "correlation_rule": self.correlation_rule,
            "relationship_type": self.relationship_type,
            "spatial_relationship": self.spatial_relationship,
            "temporal_relationship": self.temporal_relationship,
            "strength": self.strength,
            "created_at": self.created_at.isoformat(),
            "provenance_summary": self.provenance_summary,
        }
