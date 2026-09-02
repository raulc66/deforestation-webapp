"""Forest disturbance detection supplements and scoring."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.ecosystem.forest_disturbance_constants import DisturbanceDriver
from app.core.ecosystem.incident_categories import IncidentCategory
from app.modules.analytics.detection_contract import Detection, SignalType
from app.modules.analytics.disturbance_assessment import assess_disturbance_context
from app.modules.analytics.disturbance_driver_classifier import classify_disturbance_driver
from app.modules.ingestion.providers.gfw_integrated_alerts import (
    GFW_PROVIDER_ID,
    disturbance_spatial_key,
)


DISTURBANCE_SCORE_THRESHOLD = 0.45


def compute_disturbance_score(
    *,
    confidence: float,
    affected_area_ha: float,
    forest_context: dict[str, Any] | None,
    repeat_count: int = 1,
    spatial_coherence: float = 1.0,
    temporal_persistence: float = 1.0,
) -> float:
    """Deterministic transparent score — no ML."""
    ctx = forest_context or {}
    forest_factor = 0.15 if bool(ctx.get("is_forest", True)) else 0.0
    area_factor = min(float(affected_area_ha or 0.0) / 25.0, 0.25)
    repeat_factor = min(max(repeat_count - 1, 0) * 0.05, 0.15)
    score = (
        float(confidence or 0.0) * 0.45
        + area_factor
        + forest_factor
        + repeat_factor
        + float(spatial_coherence) * 0.1
        + float(temporal_persistence) * 0.05
    )
    return round(min(max(score, 0.0), 0.99), 4)


def detection_from_disturbance_event(
    event: dict[str, Any],
    *,
    detected_at: datetime,
) -> Detection:
    """Build a Detection envelope from a persisted forest disturbance event."""
    metadata = event.get("metadata") or {}
    block = metadata.get("forest_disturbance") or {}
    alert_id = str(block.get("alert_id") or metadata.get("spatial_key") or event.get("id"))
    if alert_id.startswith("disturbance-alert:"):
        spatial_key = alert_id
        alert_id = alert_id.split(":", 1)[1]
    else:
        spatial_key = disturbance_spatial_key(alert_id)

    lat = float(event["latitude"])
    lng = float(event["longitude"])
    area_ha = float(event.get("affected_area_ha") or block.get("affected_area_ha") or 0.0)
    confidence = float(event.get("confidence") or block.get("alert_confidence") or 0.5)
    forest_ctx = metadata.get("forest_context") or {}
    repeat_count = int(block.get("repeat_count") or 1)

    driver = block.get("driver") or DisturbanceDriver.UNKNOWN.value
    driver_confidence = float(block.get("driver_confidence") or confidence)
    if not block.get("driver"):
        classified = classify_disturbance_driver(
            alert_confidence=confidence,
            alert_intensity=str(block.get("alert_intensity") or ""),
            affected_area_ha=area_ha,
            forest_context=forest_ctx,
            alert_source=str(block.get("alert_source") or ""),
            repeat_count=repeat_count,
        )
        driver = classified["driver"]
        driver_confidence = float(classified["driver_confidence"])

    score = compute_disturbance_score(
        confidence=confidence,
        affected_area_ha=area_ha,
        forest_context=forest_ctx,
        repeat_count=repeat_count,
    )
    assessment = assess_disturbance_context(
        driver=str(driver),
        driver_confidence=driver_confidence,
        affected_area_ha=area_ha,
        forest_context=forest_ctx,
        protected_area_intersection=bool(block.get("protected_area_intersection", False)),
        road_proximity_m=block.get("road_proximity_m"),
        authorization_status=block.get("authorization_status"),
        repeat_count=repeat_count,
    )

    provenance = metadata.get("provenance") or {}
    if not provenance.get("provider_id"):
        provenance = {
            "provider_id": GFW_PROVIDER_ID,
            "source_event_id": (metadata.get("ingestion") or {}).get("source_event_id"),
            "domain_evidence": {"provider_class": "gfw_integrated_alerts"},
        }

    return Detection(
        spatial_key=spatial_key,
        incident_category=IncidentCategory.FOREST_DISTURBANCE.value,
        signal_type=SignalType.DISTURBANCE_SIGNAL.value,
        severity=str(event.get("severity") or "medium"),
        score=score,
        detected_at=event.get("detected_at") or detected_at,
        evidence={
            "latitude": lat,
            "longitude": lng,
            "region": event.get("region"),
            "country": event.get("country"),
            "affected_area_ha": area_ha,
            "alert_id": alert_id,
            "probable_driver": block.get("probable_driver") or driver,
            "driver_confidence": driver_confidence,
            "authorization_status": assessment["authorization_status"],
            "investigation_priority": assessment["investigation_priority"],
            "assessment_label": assessment["assessment_label"],
            "forest_context": forest_ctx,
            "provenance": provenance,
        },
    )


async def supplement_disturbance_detections(
    repo: Any,
    detections: list[Detection],
    detected_at: datetime,
    *,
    enabled: bool,
) -> list[Detection]:
    if not enabled:
        return detections
    events = await repo.list_forest_disturbance_events(detected_at)
    extra = [
        detection_from_disturbance_event(event, detected_at=detected_at)
        for event in events
        if compute_disturbance_score(
            confidence=float(event.get("confidence") or 0.0),
            affected_area_ha=float(event.get("affected_area_ha") or 0.0),
            forest_context=(event.get("metadata") or {}).get("forest_context"),
            repeat_count=int(((event.get("metadata") or {}).get("forest_disturbance") or {}).get("repeat_count") or 1),
        )
        >= DISTURBANCE_SCORE_THRESHOLD
    ]
    combined = list(detections) + extra
    combined.sort(key=lambda d: (-d.score, d.spatial_key))
    return combined
