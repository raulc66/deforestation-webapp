"""Deterministic demonstration catalog — Romanian geography, curated scenarios.

These records are demonstration data. They are not live provider observations
and must never be mixed into the operational intelligence_events collection.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.demo.constants import DEMO_CATALOG_FLAG
from app.core.ecosystem.forest_disturbance_constants import (
    PRODUCT_ASSESSMENT_LABEL,
    PRODUCT_VERIFICATION_LABEL,
)
from app.modules.analytics.correlation_result import (
    CorrelationParticipant,
    CorrelationResult,
)

CATALOG_NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)

# Harghita — matches the existing customer-alert fixture coverage.
HARGHITA_POLYGON: dict[str, Any] = {
    "type": "Polygon",
    "coordinates": [
        [[25.5, 46.8], [26.5, 46.8], [26.5, 47.5], [25.5, 47.5], [25.5, 46.8]]
    ],
}
# Suceava working forest, north of the Harghita stand.
SUCEAVA_POLYGON: dict[str, Any] = {
    "type": "Polygon",
    "coordinates": [
        [[26.0, 47.45], [26.7, 47.45], [26.7, 47.95], [26.0, 47.95], [26.0, 47.45]]
    ],
}
# Maramureș — disjoint, used for the informational observation.
MARAMURES_POLYGON: dict[str, Any] = {
    "type": "Polygon",
    "coordinates": [
        [[23.0, 47.5], [24.0, 47.5], [24.0, 48.0], [23.0, 48.0], [23.0, 47.5]]
    ],
}

AREAS: tuple[dict[str, Any], ...] = (
    {
        "catalog_key": "harghita-reserve",
        "name": "Harghita Forest Reserve",
        "country": "Romania",
        "geometry": HARGHITA_POLYGON,
        "geometry_type": "Polygon",
    },
    {
        "catalog_key": "suceava-working",
        "name": "Suceava Working Forest",
        "country": "Romania",
        "geometry": SUCEAVA_POLYGON,
        "geometry_type": "Polygon",
    },
    {
        "catalog_key": "maramures-conservation",
        "name": "Maramureș Conservation Stand",
        "country": "Romania",
        "geometry": MARAMURES_POLYGON,
        "geometry_type": "Polygon",
    },
)

SCENARIOS: tuple[dict[str, str], ...] = (
    {
        "id": "high-priority",
        "title": "High-priority forest disturbance",
        "event_key": "evt-demo-high-priority",
        "region": "Harghita",
        "summary": "A disturbance inside a watched forest that should be investigated first.",
    },
    {
        "id": "repeated",
        "title": "Repeated disturbance",
        "event_key": "evt-demo-repeated",
        "region": "Suceava",
        "summary": "The same stand has changed more than once — that raises investigative importance.",
    },
    {
        "id": "contextual",
        "title": "Contextual evidence",
        "event_key": "evt-demo-high-priority",
        "region": "Harghita",
        "summary": "A nearby wildfire observation adds context to the forest disturbance.",
    },
    {
        "id": "informational",
        "title": "Informational observation",
        "event_key": "evt-demo-informational",
        "region": "Maramureș",
        "summary": "Not everything needs action. This observation is recorded, not urgent.",
    },
)


def _demo_meta(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "demo": {DEMO_CATALOG_FLAG: True, "kind": "demonstration"},
        "ingestion": {"is_romania": True, "is_demo": True},
    }
    if extra:
        payload.update(extra)
    return payload


def catalog_events() -> list[dict[str, Any]]:
    """Three forest-disturbance events. Demonstration only."""
    high_detected = CATALOG_NOW
    repeated_first = CATALOG_NOW - timedelta(days=18)
    info_detected = CATALOG_NOW - timedelta(days=2)
    return [
        {
            "catalog_key": "evt-demo-high-priority",
            "event_type": "anomaly",
            "incident_category": "forest_disturbance",
            "spatial_key": "RO-Harghita",
            "region": "Harghita",
            "status": "active",
            "severity": "high",
            "escalation_level": "normal",
            "trend": "new",
            "priority_score": 0.78,
            "current_score": 0.78,
            "previous_score": None,
            "detection_count": 1,
            "first_detected_at": high_detected,
            "last_detected_at": high_detected,
            "resolved_at": None,
            "signal_type": "forest_disturbance",
            "latitude": 46.9,
            "longitude": 26.0,
            "metadata": _demo_meta(
                {
                    "latitude": 46.9,
                    "longitude": 26.0,
                    "scenario_id": "high-priority",
                    "provenance": {
                        "provider_id": "gfw.integrated_alerts",
                        "source_id": "gfw.integrated_alerts",
                        "dataset_id": "demo.gfw",
                        "detected_at": high_detected.isoformat(),
                    },
                    "forest_disturbance": {
                        "assessment_label": PRODUCT_ASSESSMENT_LABEL,
                        "probable_driver": "selective_logging_candidate",
                        "probable_driver_label": "Selective Logging",
                        "driver_confidence": 0.86,
                        "affected_area_ha": 12.4,
                        "authorization_status": "unknown",
                        "investigation_priority": "high",
                        "repeat_activity": False,
                        "protected_area_intersection": True,
                    },
                    "forest_context": {"is_forest": True, "land_cover": "forest"},
                }
            ),
        },
        {
            "catalog_key": "evt-demo-repeated",
            "event_type": "anomaly",
            "incident_category": "forest_disturbance",
            "spatial_key": "RO-Suceava",
            "region": "Suceava",
            "status": "active",
            "severity": "medium",
            "escalation_level": "persistent",
            "trend": "worsening",
            "priority_score": 0.61,
            "current_score": 0.61,
            "previous_score": 0.44,
            "detection_count": 4,
            "first_detected_at": repeated_first,
            "last_detected_at": CATALOG_NOW - timedelta(days=1),
            "resolved_at": None,
            "signal_type": "forest_disturbance",
            "latitude": 47.62,
            "longitude": 26.25,
            "metadata": _demo_meta(
                {
                    "latitude": 47.62,
                    "longitude": 26.25,
                    "scenario_id": "repeated",
                    "provenance": {
                        "provider_id": "gfw.integrated_alerts",
                        "source_id": "gfw.integrated_alerts",
                        "dataset_id": "demo.gfw",
                        "detected_at": (CATALOG_NOW - timedelta(days=1)).isoformat(),
                    },
                    "forest_disturbance": {
                        "assessment_label": PRODUCT_ASSESSMENT_LABEL,
                        "probable_driver": "road_development_candidate",
                        "probable_driver_label": "Road / Skid-trail Development",
                        "driver_confidence": 0.71,
                        "affected_area_ha": 3.8,
                        "authorization_status": "requires_verification",
                        "investigation_priority": "low",
                        "repeat_activity": True,
                        "protected_area_intersection": False,
                    },
                    "forest_context": {"is_forest": True, "land_cover": "forest"},
                }
            ),
        },
        {
            "catalog_key": "evt-demo-informational",
            "event_type": "anomaly",
            "incident_category": "forest_disturbance",
            "spatial_key": "RO-Maramures",
            "region": "Maramureș",
            "status": "active",
            "severity": "low",
            "escalation_level": "normal",
            "trend": "stable",
            "priority_score": 0.22,
            "current_score": 0.22,
            "previous_score": 0.22,
            "detection_count": 1,
            "first_detected_at": info_detected,
            "last_detected_at": info_detected,
            "resolved_at": None,
            "signal_type": "forest_disturbance",
            "latitude": 47.72,
            "longitude": 23.45,
            "metadata": _demo_meta(
                {
                    "latitude": 47.72,
                    "longitude": 23.45,
                    "scenario_id": "informational",
                    "provenance": {
                        "provider_id": "gfw.integrated_alerts",
                        "source_id": "gfw.integrated_alerts",
                        "dataset_id": "demo.gfw",
                        "detected_at": info_detected.isoformat(),
                    },
                    "forest_disturbance": {
                        "assessment_label": PRODUCT_VERIFICATION_LABEL,
                        "probable_driver": "natural_disturbance",
                        "probable_driver_label": "Natural Disturbance",
                        "driver_confidence": 0.54,
                        "affected_area_ha": 1.1,
                        "authorization_status": "unknown",
                        "investigation_priority": "low",
                        "repeat_activity": False,
                        "protected_area_intersection": False,
                    },
                    "forest_context": {"is_forest": True, "land_cover": "forest"},
                }
            ),
        },
    ]


def catalog_correlation() -> CorrelationResult:
    """Contextual wildfire support for the high-priority Harghita disturbance.

    This is a real CorrelationResult the evidence builder already understands.
    It is stored only with the demonstration catalog, never in the live
    correlation snapshot that reconciliation replaces.
    """
    observed = CATALOG_NOW - timedelta(hours=6)
    return CorrelationResult(
        correlation_id="corr-demo-harghita-wildfire",
        canonical_incident_category="forest_disturbance",
        canonical_spatial_key="RO-Harghita",
        relationship_type="contextual_evidence",
        correlation_rule="demo_wildfire_context",
        participants=(
            CorrelationParticipant(
                incident_category="forest_disturbance",
                spatial_key="RO-Harghita",
                provider_id="gfw.integrated_alerts",
                source_event_id="demo-gfw-harghita-1",
                detected_at=CATALOG_NOW,
                role="primary",
            ),
            CorrelationParticipant(
                incident_category="wildfire",
                spatial_key="RO-Harghita",
                provider_id="effis.wildfire_context",
                source_event_id="demo-effis-harghita-1",
                detected_at=observed,
                role="context",
            ),
        ),
        participating_provider_ids=("gfw.integrated_alerts", "effis.wildfire_context"),
        spatial_relationship="same_spatial_key",
        temporal_relationship="within_context_window",
        strength=0.74,
        created_at=CATALOG_NOW,
        provenance_summary={
            "demo": True,
            "note": "Demonstration correlation — not a live provider join.",
        },
    )


def professional_like_entitlements() -> dict[str, Any]:
    """Capability profile for the demonstration org — not a billed plan."""
    return {
        "monitored_area_limit": 10,
        "monitoring_enabled": True,
        "forest_disturbance_enabled": True,
        "evidence_correlation_enabled": True,
        "live_sources_enabled": True,
        "alert_delivery_enabled": True,
        "alert_policy_limit": 5,
        "notification_channel_limit": 2,
    }
