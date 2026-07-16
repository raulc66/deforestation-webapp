"""IntelligenceEvent domain model.

Represents a persisted, trackable intelligence observation such as an
anomaly detection.  Stored in the ``intelligence_events`` MongoDB collection.
"""
from datetime import datetime
from pydantic import BaseModel


class IntelligenceEvent(BaseModel):
    """Public-facing representation of a persisted intelligence event.

    ``id`` is the MongoDB ObjectId as a string.
    ``event_type`` is currently always ``"anomaly"``; designed to accommodate
    ``"volume_alert"``, ``"reliability_alert"``, etc. in the future.
    ``incident_category`` classifies the ecosystem incident (e.g. wildfire,
    illegal_logging).  Legacy records without this field default to ``wildfire``.
    ``status`` is ``"active"`` while the condition is still detected and
    ``"resolved"`` once it drops below detection thresholds.
    """

    id: str
    event_type: str
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
