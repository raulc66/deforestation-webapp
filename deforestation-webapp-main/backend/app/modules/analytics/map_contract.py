"""Canonical map marker serialization (Package E)."""
from __future__ import annotations

from typing import Any

from app.core.ecosystem.canonical_identity import (
    spatial_key_from_cems_country,
    spatial_key_from_region,
    spatial_key_from_station,
)
from app.core.ecosystem.incident_categories import resolve_incident_category
from app.modules.analytics.context_enrichment import forest_context_for_map_payload
from app.modules.analytics.disturbance_assessment import bounded_disturbance_read_model


def _source_event_id(metadata: dict[str, Any] | None) -> str | None:
    if not metadata:
        return None
    ingestion = metadata.get("ingestion") or {}
    return ingestion.get("source_event_id")


def _field(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def forest_event_map_marker(event: Any) -> dict[str, Any]:
    """Project a forest event to the canonical map payload."""
    metadata = _field(event, "metadata") or {}
    incident_category = resolve_incident_category(
        {
            "incident_category": metadata.get("incident_category"),
            "event_type": _field(event, "event_type"),
        }
    )
    region = _field(event, "region") or "Unknown"
    detected_at = _field(event, "detected_at")
    event_id = _field(event, "id") or _field(event, "_id")
    if event_id is not None and not isinstance(event_id, str):
        event_id = str(event_id)
    lat = float(_field(event, "latitude"))
    lng = float(_field(event, "longitude"))
    observation = metadata.get("observation") or {}
    activation = metadata.get("emergency_activation") or {}
    station_id = observation.get("station_id")
    if incident_category == "air_quality" and station_id:
        spatial_key = spatial_key_from_station(str(station_id))
    elif incident_category == "environmental_hazard":
        spatial_key = spatial_key_from_cems_country(region)
    elif incident_category == "forest_disturbance":
        spatial_key = metadata.get("spatial_key") or spatial_key_from_region(region)
    else:
        spatial_key = spatial_key_from_region(region)
    marker = {
        "id": event_id,
        "latitude": lat,
        "longitude": lng,
        "spatial_key": spatial_key,
        "incident_category": incident_category,
        "severity": _field(event, "severity"),
        "confidence": _field(event, "confidence"),
        "detected_at": detected_at.isoformat() if detected_at else None,
        "source": _field(event, "source_name") or _field(event, "source_id") or "Unknown",
        "source_event_id": _source_event_id(metadata),
        "event_type": _field(event, "event_type"),
        "region": region,
        "land_cover_type": _field(event, "land_cover_type") or "unknown",
    }
    if incident_category == "air_quality" and observation:
        marker["pollutant"] = observation.get("pollutant")
        marker["measurement_value"] = observation.get("value")
        marker["measurement_unit"] = observation.get("unit")
        marker["station_id"] = station_id
        marker["coordinate_source"] = "monitoring_station"
    if incident_category == "environmental_hazard" and activation:
        marker["hazard_type"] = activation.get("hazard_type")
        marker["activation_code"] = activation.get("activation_code")
        marker["coordinate_source"] = "activation_centroid"
        marker["cems_category"] = activation.get("cems_category")
    if incident_category == "forest_disturbance":
        disturbance = metadata.get("forest_disturbance") or {}
        marker["coordinate_source"] = "alert_centroid"
        marker["affected_area_ha"] = _field(event, "affected_area_ha")
        marker["disturbance_assessment"] = bounded_disturbance_read_model(disturbance)
        if disturbance.get("probable_driver"):
            marker["probable_driver"] = disturbance.get("probable_driver")
        if disturbance.get("driver_confidence") is not None:
            marker["driver_confidence"] = disturbance.get("driver_confidence")
        if disturbance.get("investigation_priority"):
            marker["investigation_priority"] = disturbance.get("investigation_priority")
        if disturbance.get("authorization_status"):
            marker["authorization_status"] = disturbance.get("authorization_status")
    ctx = forest_context_for_map_payload(metadata=metadata, latitude=lat, longitude=lng)
    if ctx:
        marker["forest_context"] = ctx
    return marker


def attach_region_centroid(
    payload: dict[str, Any],
    *,
    centroids: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    """Attach ``latitude``/``longitude`` from event centroids when absent."""
    if payload.get("coordinate_source") in {"monitoring_station", "activation_centroid"}:
        return payload
    if "latitude" in payload and "longitude" in payload:
        return payload
    region = payload.get("region")
    if not region:
        return payload
    coords = centroids.get(str(region))
    if not coords:
        return payload
    lat, lng = coords
    return {
        **payload,
        "latitude": lat,
        "longitude": lng,
        "coordinate_source": "region_event_centroid",
    }


def intelligence_event_map_marker(
    event: dict[str, Any],
    *,
    centroids: dict[str, tuple[float, float]] | None = None,
) -> dict[str, Any]:
    """Project an intelligence event to the canonical map payload."""
    region = str(event.get("region") or "Unknown")
    metadata = event.get("metadata") or {}
    station_id = metadata.get("station_id")
    incident_category = resolve_incident_category(event)
    if incident_category == "air_quality" and station_id:
        spatial_key = event.get("spatial_key") or spatial_key_from_station(str(station_id))
    elif incident_category == "environmental_hazard":
        spatial_key = event.get("spatial_key") or spatial_key_from_cems_country(region)
    elif incident_category == "forest_disturbance":
        spatial_key = event.get("spatial_key") or spatial_key_from_region(region)
    else:
        spatial_key = event.get("spatial_key") or spatial_key_from_region(region)
    payload: dict[str, Any] = {
        "id": event.get("id"),
        "spatial_key": spatial_key,
        "incident_category": incident_category,
        "severity": event.get("severity"),
        "confidence": event.get("confidence"),
        "detected_at": event.get("detected_at") or event.get("last_detected_at"),
        "source": event.get("source") or "derived",
        "source_event_id": event.get("source_event_id"),
        "region": region,
        "priority_score": event.get("priority_score"),
        "escalation_level": event.get("escalation_level"),
    }
    if incident_category == "air_quality":
        if metadata.get("pollutant"):
            payload["pollutant"] = metadata.get("pollutant")
        if metadata.get("latitude") is not None:
            payload["latitude"] = metadata.get("latitude")
            payload["longitude"] = metadata.get("longitude")
            payload["coordinate_source"] = "monitoring_station"
        if metadata.get("station_id"):
            payload["station_id"] = metadata.get("station_id")
        if metadata.get("deviation_percent") is not None:
            payload["deviation_percent"] = metadata.get("deviation_percent")
    if incident_category == "environmental_hazard":
        if metadata.get("hazard_type"):
            payload["hazard_type"] = metadata.get("hazard_type")
        if metadata.get("country"):
            payload["country"] = metadata.get("country")
        if metadata.get("deviation_percent") is not None:
            payload["deviation_percent"] = metadata.get("deviation_percent")
    if incident_category == "forest_disturbance":
        if event.get("latitude") is not None and event.get("longitude") is not None:
            payload["latitude"] = event.get("latitude")
            payload["longitude"] = event.get("longitude")
            payload["coordinate_source"] = "alert_centroid"
        disturbance = metadata.get("forest_disturbance") or {}
        payload["disturbance_assessment"] = bounded_disturbance_read_model(disturbance)
        if event.get("affected_area_ha") is not None:
            payload["affected_area_ha"] = event.get("affected_area_ha")
    if centroids:
        payload = attach_region_centroid(payload, centroids=centroids)
    ctx = forest_context_for_map_payload(
        metadata=event.get("metadata"),
        latitude=payload.get("latitude"),
        longitude=payload.get("longitude"),
    )
    if ctx:
        payload["forest_context"] = ctx
    return payload


def anomaly_map_marker(
    anomaly: dict[str, Any],
    *,
    centroids: dict[str, tuple[float, float]] | None = None,
) -> dict[str, Any]:
    """Project an anomaly to the canonical map payload."""
    region = str(anomaly.get("region") or "Unknown")
    payload: dict[str, Any] = {
        "spatial_key": spatial_key_from_region(region),
        "incident_category": resolve_incident_category(anomaly),
        "severity": anomaly.get("severity"),
        "detected_at": anomaly.get("generated_at"),
        "source": "analytics",
        "region": region,
        "anomaly_score": anomaly.get("anomaly_score"),
        "deviation_percent": anomaly.get("deviation_percent"),
    }
    if centroids:
        payload = attach_region_centroid(payload, centroids=centroids)
    ctx = forest_context_for_map_payload(
        latitude=payload.get("latitude"),
        longitude=payload.get("longitude"),
    )
    if ctx:
        payload["forest_context"] = ctx
    return payload
