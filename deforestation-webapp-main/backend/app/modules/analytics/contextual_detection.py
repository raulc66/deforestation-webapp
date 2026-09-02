"""Contextual detection supplements — EFFIS burned-area context for correlation."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.ecosystem.incident_categories import IncidentCategory
from app.modules.analytics.detection_contract import Detection
from app.modules.ingestion.providers.effis import EFFIS_PROVIDER_ID, effis_spatial_key


def _score_from_area(area_ha: Any) -> float:
    try:
        area = float(area_ha or 0)
    except (TypeError, ValueError):
        return 0.55
    return round(min(0.95, max(0.45, 0.45 + area / 500.0)), 4)


def detection_from_effis_context_event(
    event: dict[str, Any],
    *,
    detected_at: datetime,
) -> Detection:
    """Build a contextual Detection envelope from a persisted EFFIS context event."""
    metadata = event.get("metadata") or {}
    effis = metadata.get("effis_context") or {}
    fire_id = str(effis.get("fire_id") or metadata.get("spatial_key") or event.get("id"))
    if fire_id.startswith("effis-burn:"):
        spatial_key = fire_id
        fire_id = fire_id.split(":", 1)[1]
    else:
        spatial_key = effis_spatial_key(fire_id)

    lat = float(event["latitude"])
    lng = float(event["longitude"])
    provenance = metadata.get("provenance") or {}
    if not provenance.get("provider_id"):
        provenance = {
            "provider_id": EFFIS_PROVIDER_ID,
            "source_event_id": (metadata.get("ingestion") or {}).get("source_event_id"),
            "domain_evidence": {"provider_class": "effis_wildfire_context"},
        }

    return Detection(
        spatial_key=spatial_key,
        incident_category=IncidentCategory.WILDFIRE.value,
        signal_type="contextual_evidence",
        severity=str(event.get("severity") or "medium"),
        score=_score_from_area(effis.get("area_ha")),
        detected_at=event.get("detected_at") or detected_at,
        evidence={
            "latitude": lat,
            "longitude": lng,
            "region": event.get("region"),
            "country": event.get("country") or effis.get("country"),
            "area_ha": effis.get("area_ha"),
            "fire_id": fire_id,
            "contextual_role": metadata.get("contextual_role"),
            "provenance": provenance,
        },
    )


async def supplement_contextual_detections(
    repo: Any,
    detections: list[Detection],
    detected_at: datetime,
    *,
    enabled: bool,
) -> list[Detection]:
    """Append EFFIS contextual detections when the provider is enabled."""
    if not enabled:
        return detections
    events = await repo.list_effis_context_events(detected_at)
    extra = [detection_from_effis_context_event(event, detected_at=detected_at) for event in events]
    combined = list(detections) + extra
    combined.sort(key=lambda d: (-d.score, d.spatial_key))
    return combined
