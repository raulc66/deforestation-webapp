"""Intelligence cycle identity for correlation / event consistency."""
from __future__ import annotations

import hashlib

from app.modules.analytics.detection_contract import Detection


def detection_fingerprint(detections: list[Detection]) -> str:
    """Deterministic fingerprint of a detection set — not wall-clock based."""
    if not detections:
        return hashlib.sha256(b"empty").hexdigest()
    keys = sorted(f"{d.incident_category}:{d.spatial_key}" for d in detections)
    return hashlib.sha256("|".join(keys).encode()).hexdigest()


def resolve_intelligence_cycle_id(
    scheduler_cycle_id: str | None,
    fingerprint: str,
) -> str:
    """Reuse scheduler cycle_id when present; otherwise derive from fingerprint."""
    if scheduler_cycle_id:
        return str(scheduler_cycle_id)
    return f"intel-{fingerprint[:16]}"
