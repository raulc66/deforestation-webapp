"""Minimal deterministic correlation keys for multi-source readiness.

Does not implement fusion — only a stable key for associating observations that
refer to the same location, time window, and incident category.
"""
from __future__ import annotations

from datetime import datetime, timezone


def observation_correlation_key(
    *,
    incident_category: str,
    latitude: float | None,
    longitude: float | None,
    observed_at: datetime | None,
    window_hours: int = 24,
) -> str | None:
    """Return a deterministic correlation key or ``None`` when inputs are insufficient."""
    if latitude is None or longitude is None or observed_at is None:
        return None
    dt = observed_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    bucket = int(dt.timestamp()) // (window_hours * 3600)
    lat_bucket = round(float(latitude), 2)
    lng_bucket = round(float(longitude), 2)
    return f"{incident_category}:{lat_bucket}:{lng_bucket}:{bucket}"
