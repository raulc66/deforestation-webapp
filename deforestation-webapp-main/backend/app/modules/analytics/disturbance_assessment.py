"""Contextual and investigation assessment for forest disturbance intelligence."""
from __future__ import annotations

from typing import Any

from app.core.ecosystem.forest_disturbance_constants import (
    PRODUCT_ASSESSMENT_LABEL,
    PRODUCT_VERIFICATION_LABEL,
    AuthorizationStatus,
    DisturbanceDriver,
    InvestigationPriority,
    assert_safe_assessment_language,
    probable_driver_label,
)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def assess_disturbance_context(
    *,
    driver: str,
    driver_confidence: float,
    affected_area_ha: float,
    forest_context: dict[str, Any] | None = None,
    protected_area_intersection: bool = False,
    road_proximity_m: float | None = None,
    authorization_status: str | None = None,
    repeat_count: int = 1,
) -> dict[str, Any]:
    """Deterministic contextual/investigation assessment — no fabricated legality."""
    ctx = forest_context or {}
    auth = str(authorization_status or AuthorizationStatus.UNKNOWN.value)
    if auth not in {s.value for s in AuthorizationStatus}:
        auth = AuthorizationStatus.UNKNOWN.value

    # Never infer unauthorized from satellite evidence alone.
    if auth == AuthorizationStatus.POTENTIALLY_UNAUTHORIZED.value:
        auth = AuthorizationStatus.REQUIRES_VERIFICATION.value

    priority_score = 0.0
    reasons: list[str] = []

    priority_score += min(affected_area_ha / 20.0, 0.35)
    priority_score += driver_confidence * 0.35
    if driver in {
        DisturbanceDriver.SELECTIVE_LOGGING.value,
        DisturbanceDriver.CLEARCUTTING.value,
        DisturbanceDriver.ROAD_DEVELOPMENT.value,
        DisturbanceDriver.AGRICULTURAL_CONVERSION.value,
        DisturbanceDriver.MINING.value,
    }:
        priority_score += 0.15
        reasons.append("anthropogenic_driver_candidate")
    if protected_area_intersection:
        priority_score += 0.2
        reasons.append("protected_area_intersection")
    if road_proximity_m is not None and road_proximity_m <= 500:
        priority_score += 0.08
        reasons.append("road_proximity")
    if repeat_count >= 2:
        priority_score += 0.07
        reasons.append("repeated_activity")
    if bool(ctx.get("is_forest", False)):
        priority_score += 0.05
        reasons.append("forest_intersection")
    if auth == AuthorizationStatus.UNKNOWN.value:
        priority_score += 0.05
        reasons.append("authorization_unknown")

    priority_score = _clamp(priority_score)
    if priority_score >= 0.8:
        priority = InvestigationPriority.CRITICAL.value
    elif priority_score >= 0.65:
        priority = InvestigationPriority.HIGH.value
    elif priority_score >= 0.45:
        priority = InvestigationPriority.MEDIUM.value
    else:
        priority = InvestigationPriority.LOW.value

    assessment_label = (
        PRODUCT_ASSESSMENT_LABEL
        if driver
        not in {
            DisturbanceDriver.NATURAL_DISTURBANCE.value,
            DisturbanceDriver.WILDFIRE.value,
            DisturbanceDriver.UNKNOWN.value,
        }
        else PRODUCT_VERIFICATION_LABEL
    )
    assert_safe_assessment_language(assessment_label)

    return {
        "assessment_label": assessment_label,
        "probable_driver_label": probable_driver_label(driver),
        "driver_confidence": round(driver_confidence, 4),
        "affected_area_ha": round(float(affected_area_ha), 4),
        "authorization_status": auth,
        "protected_area_intersection": protected_area_intersection,
        "road_proximity_m": road_proximity_m,
        "investigation_priority": priority,
        "investigation_score": round(priority_score, 4),
        "assessment_reasons": tuple(sorted(set(reasons))),
    }


def bounded_disturbance_read_model(block: dict[str, Any] | None) -> dict[str, Any]:
    """Strip disturbance assessment fields safe for Command Center / map."""
    if not block:
        return {}
    allowed = {
        "assessment_label",
        "probable_driver_label",
        "probable_driver",
        "driver_confidence",
        "affected_area_ha",
        "authorization_status",
        "investigation_priority",
        "protected_area_intersection",
        "road_proximity_m",
        "repeat_activity",
    }
    return {k: block[k] for k in allowed if k in block}
