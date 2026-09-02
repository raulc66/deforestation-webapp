"""IntelligenceEvent domain model.

Represents a persisted, trackable intelligence observation such as an
anomaly detection.  Stored in the ``intelligence_events`` MongoDB collection.

Canonical field mapping (ADR-008, WP1.2):
  Identity     → incident_category, spatial_key (Phase 0: region alias)
  Derived      → event_type (never identity)
  Provenance   → signal_type
  Lifecycle    → status, first_detected_at, last_detected_at, detection_count
  Dynamics     → severity, escalation_level, trend, priority_score,
                 current_score, previous_score
  Evidence     → metadata
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.ecosystem.intelligence_event_defaults import (
    DEFAULT_SIGNAL_TYPE,
    DERIVED_ANOMALY_EVENT_TYPE,
    apply_legacy_intelligence_event_defaults,
)


class IntelligenceEvent(BaseModel):
    """Public-facing representation of a persisted intelligence event."""

    id: str
    event_type: str = Field(
        description="Derived label (e.g. anomaly). Not an identity component.",
    )
    region: str
    status: str
    severity: str
    escalation_level: str = "normal"
    previous_score: float | None = None
    trend: str = "new"
    priority_score: float = 0.0
    first_detected_at: datetime
    last_detected_at: datetime
    detection_count: int
    current_score: float
    metadata: dict
    resolved_at: datetime | None = None
    incident_category: str = "wildfire"
    spatial_key: str | None = Field(
        default=None,
        description="Canonical location identity. Phase 0 equals region.",
    )
    signal_type: str | None = Field(
        default=None,
        description="Detector provenance class that produced the event.",
    )

    @classmethod
    def from_persisted(cls, record: dict[str, Any]) -> IntelligenceEvent:
        """Construct from a repository dict applying deterministic legacy defaults."""
        normalized = apply_legacy_intelligence_event_defaults(record)
        return cls(**{k: v for k, v in normalized.items() if k in cls.model_fields})


def intelligence_event_field_mapping() -> dict[str, str]:
    """Document legacy → canonical field relationships for WP1.2."""
    return {
        "region": "spatial_key (Phase 0 administrative region implementation)",
        "event_type": "derived label — not identity",
        "incident_category": "identity component",
        "spatial_key": "identity component",
        "signal_type": "provenance — detector class",
        "severity": "mutable dynamics",
        "escalation_level": "mutable dynamics",
        "trend": "mutable dynamics",
        "priority_score": "mutable dynamics",
        "current_score": "mutable dynamics",
        "previous_score": "mutable dynamics",
        "detection_count": "lifecycle state",
        "metadata": "evidence",
    }


def default_signal_type() -> str:
    return DEFAULT_SIGNAL_TYPE


def default_derived_event_type() -> str:
    return DERIVED_ANOMALY_EVENT_TYPE
