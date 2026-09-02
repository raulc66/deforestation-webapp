"""Legacy anomaly ↔ Detection adapters and intelligence read-model defaults."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.ecosystem.canonical_identity import (
    region_from_spatial_key,
    spatial_key_from_cems_country,
    spatial_key_from_region,
    spatial_key_from_station,
)
from app.core.ecosystem.incident_categories import (
    IncidentCategory,
    normalize_incident_category,
    resolve_incident_category,
)
from app.core.ecosystem.intelligence_event_defaults import DEFAULT_SIGNAL_TYPE
from app.core.ingestion.provenance import build_detection_provenance

from .detection_contract import Detection


def detection_from_anomaly_dict(
    anomaly: dict[str, Any],
    *,
    detected_at: datetime,
    incident_category: str = IncidentCategory.WILDFIRE.value,
    signal_type: str = DEFAULT_SIGNAL_TYPE,
) -> Detection:
    """Convert a legacy anomaly API dict into a canonical Detection envelope."""
    region = str(anomaly["region"])
    evidence: dict[str, Any] = {
        "baseline_events": int(anomaly["baseline_events"]),
        "current_events": int(anomaly["current_events"]),
        "deviation_percent": float(anomaly["deviation_percent"]),
        "forest_confidence": anomaly.get("forest_confidence"),
        "region": region,
    }
    if anomaly.get("latitude") is not None:
        evidence["latitude"] = float(anomaly["latitude"])
    if anomaly.get("longitude") is not None:
        evidence["longitude"] = float(anomaly["longitude"])
    if anomaly.get("station_id"):
        evidence["station_id"] = str(anomaly["station_id"])
    if anomaly.get("station_name"):
        evidence["station_name"] = str(anomaly["station_name"])
    if anomaly.get("pollutant"):
        evidence["pollutant"] = str(anomaly["pollutant"])
    if anomaly.get("unit"):
        evidence["unit"] = str(anomaly["unit"])
    if anomaly.get("country"):
        evidence["country"] = str(anomaly["country"])
    if anomaly.get("hazard_type"):
        evidence["hazard_type"] = str(anomaly["hazard_type"])
    station_id = anomaly.get("station_id")
    country = anomaly.get("country")
    if station_id:
        spatial_key = spatial_key_from_station(str(station_id))
    elif country:
        spatial_key = spatial_key_from_cems_country(str(country))
    else:
        spatial_key = spatial_key_from_region(region)
    provenance = build_detection_provenance(
        anomaly,
        detected_at=detected_at,
        signal_type=signal_type,
    )
    evidence["provenance"] = provenance
    return Detection(
        spatial_key=spatial_key,
        incident_category=normalize_incident_category(incident_category),
        signal_type=signal_type,
        severity=str(anomaly["severity"]),
        score=float(anomaly["anomaly_score"]),
        evidence=evidence,
        detected_at=detected_at,
    )


def anomaly_dict_from_detection(detection: Detection) -> dict[str, Any]:
    """Project a Detection back to the legacy anomalies API shape."""
    evidence = detection.evidence
    region = evidence.get("region") or region_from_spatial_key(detection.spatial_key)
    return {
        "region": region,
        "baseline_events": int(evidence["baseline_events"]),
        "current_events": int(evidence["current_events"]),
        "deviation_percent": float(evidence["deviation_percent"]),
        "anomaly_score": float(detection.score),
        "severity": detection.severity,
        "status": "active",
        "forest_confidence": evidence.get("forest_confidence"),
    }


def anomalies_response_from_detections(
    detections: list[Detection],
    *,
    generated_at: datetime,
) -> dict[str, Any]:
    """Build the legacy ``get_anomalies`` response from Detection envelopes."""
    anomalies = [anomaly_dict_from_detection(d) for d in detections]
    anomalies.sort(key=lambda item: item["anomaly_score"], reverse=True)
    return {"generated_at": generated_at, "anomalies": anomalies}


def resolve_incident_category_from_anomaly(anomaly: dict[str, Any]) -> str:
    """Resolve category for reconciliation from a legacy anomaly payload."""
    return resolve_incident_category(anomaly)
