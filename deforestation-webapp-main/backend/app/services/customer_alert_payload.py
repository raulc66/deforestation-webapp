"""Customer alert payload formatting."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.ecosystem.forest_disturbance_constants import (
    PRODUCT_ASSESSMENT_LABEL,
    probable_driver_label,
)
from app.modules.analytics.disturbance_assessment import bounded_disturbance_read_model


def _format_dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "—")


def build_forest_disturbance_alert_body(
    *,
    event: dict[str, Any],
    enriched_disturbance: dict[str, Any],
    evidence_summary: dict[str, Any],
    monitored_area_name: str,
) -> str:
    disturbance = bounded_disturbance_read_model(enriched_disturbance)
    providers = evidence_summary.get("providers") or []
    provider_text = " + ".join(providers) if providers else "GFW"
    strength = evidence_summary.get("strongest_correlation_strength")
    if strength is None:
        strength = disturbance.get("driver_confidence")
    auth = disturbance.get("authorization_status") or "unknown"
    auth_label = str(auth).replace("_", " ").title()
    if auth in {"unknown", "requires_verification"}:
        auth_label = "Unknown — requires verification"

    lines = [
        "FORESTWATCH ALERT",
        "",
        PRODUCT_ASSESSMENT_LABEL,
        "",
        f"Priority: {str(enriched_disturbance.get('investigation_priority') or 'medium').upper()}",
        "",
        "Monitored Area:",
        monitored_area_name or "—",
        "",
        "Affected Area:",
        f"{disturbance.get('affected_area_ha', '—')} ha",
        "",
        "Probable Driver:",
        probable_driver_label(str(disturbance.get('probable_driver') or 'unknown')),
        "",
        "Driver Confidence:",
        str(disturbance.get("driver_confidence", "—")),
        "",
        "Authorization:",
        auth_label,
        "",
        "Evidence:",
        provider_text,
        "",
        "Evidence Strength:",
        str(strength if strength is not None else "—"),
        "",
        "First Detected:",
        _format_dt(event.get("first_detected_at")),
        "",
        "Last Observed:",
        _format_dt(event.get("last_detected_at")),
        "",
        "ForestWatch does not determine legal status from satellite evidence alone.",
    ]
    return "\n".join(lines)


def build_webhook_payload(
    *,
    organization_id: str,
    policy_id: str,
    alert_stage: str,
    event: dict[str, Any],
    enriched_disturbance: dict[str, Any],
    evidence_summary: dict[str, Any],
    monitored_area_ids: list[str],
    monitored_area_name: str,
    reason: str,
    priority: str,
) -> dict[str, Any]:
    disturbance = bounded_disturbance_read_model(enriched_disturbance)
    return {
        "type": "forestwatch.alert",
        "organization_id": organization_id,
        "policy_id": policy_id,
        "alert_stage": alert_stage,
        "intelligence_event_id": event.get("id"),
        "incident_category": event.get("incident_category"),
        "priority": priority,
        "reason": reason,
        "monitored_area_ids": monitored_area_ids,
        "monitored_area_name": monitored_area_name,
        "assessment_label": PRODUCT_ASSESSMENT_LABEL,
        "disturbance": disturbance,
        "evidence": {
            "providers": list(evidence_summary.get("providers") or []),
            "evidence_state": evidence_summary.get("evidence_state"),
            "strongest_correlation_strength": evidence_summary.get(
                "strongest_correlation_strength"
            ),
        },
        "first_detected_at": _format_dt(event.get("first_detected_at")),
        "last_detected_at": _format_dt(event.get("last_detected_at")),
        "disclaimer": (
            "ForestWatch does not determine legal status from satellite evidence alone."
        ),
    }
