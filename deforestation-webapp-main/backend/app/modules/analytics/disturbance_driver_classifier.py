"""Deterministic probable-driver classification for forest disturbance signals."""
from __future__ import annotations

from typing import Any

from app.core.ecosystem.forest_disturbance_constants import (
    DRIVER_CANDIDATE_SUFFIX,
    DisturbanceDriver,
)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def classify_disturbance_driver(
    *,
    alert_confidence: float | None,
    alert_intensity: str | None,
    affected_area_ha: float | None,
    forest_context: dict[str, Any] | None,
    alert_source: str | None = None,
    repeat_count: int = 1,
) -> dict[str, Any]:
    """Return probable driver, confidence, and bounded reason codes."""
    area = float(affected_area_ha or 0.0)
    base_conf = _clamp(float(alert_confidence or 0.55))
    intensity = str(alert_intensity or "").strip().lower()
    ctx = forest_context or {}
    is_forest = bool(ctx.get("is_forest", True))
    tree_cover = float(ctx.get("tree_cover_density_pct") or 0.0)

    reasons: list[str] = []
    driver = DisturbanceDriver.UNKNOWN
    score = base_conf * 0.5

    if intensity in {"high", "severe", "strong"} or area >= 50:
        driver = DisturbanceDriver.CLEARCUTTING
        score = _clamp(0.55 + min(area / 200.0, 0.25) + base_conf * 0.2)
        reasons.append("large_patch_high_intensity")
    elif area >= 10:
        driver = DisturbanceDriver.CLEARCUTTING
        score = _clamp(0.45 + min(area / 100.0, 0.2) + base_conf * 0.15)
        reasons.append("medium_patch_extent")
    elif 0.5 <= area < 10:
        driver = DisturbanceDriver.SELECTIVE_LOGGING
        score = _clamp(0.4 + min(area / 20.0, 0.25) + base_conf * 0.15)
        reasons.append("small_patch_selective_pattern")
    elif area > 0:
        driver = DisturbanceDriver.SELECTIVE_LOGGING
        score = _clamp(0.35 + base_conf * 0.1)
        reasons.append("minimal_patch_extent")

    source = str(alert_source or "").lower()
    if "road" in source or "linear" in source:
        driver = DisturbanceDriver.ROAD_DEVELOPMENT
        score = _clamp(max(score, 0.5 + base_conf * 0.1))
        reasons.append("linear_signal_hint")
    if "agri" in source or "crop" in source:
        driver = DisturbanceDriver.AGRICULTURAL_CONVERSION
        score = _clamp(max(score, 0.52 + base_conf * 0.1))
        reasons.append("agricultural_context_hint")
    if "mine" in source:
        driver = DisturbanceDriver.MINING
        score = _clamp(max(score, 0.58 + base_conf * 0.1))
        reasons.append("mining_context_hint")
    if "fire" in source or intensity == "fire":
        driver = DisturbanceDriver.WILDFIRE
        score = _clamp(max(score, 0.5 + base_conf * 0.15))
        reasons.append("fire_signal_hint")

    if not is_forest and tree_cover < 20:
        if driver in {DisturbanceDriver.SELECTIVE_LOGGING, DisturbanceDriver.CLEARCUTTING}:
            driver = DisturbanceDriver.UNKNOWN
            score = _clamp(score * 0.6)
            reasons.append("low_forest_intersection")

    if repeat_count >= 3 and driver in {
        DisturbanceDriver.SELECTIVE_LOGGING,
        DisturbanceDriver.CLEARCUTTING,
    }:
        score = _clamp(score + 0.08)
        reasons.append("repeated_observations")

    probable = f"{driver.value}{DRIVER_CANDIDATE_SUFFIX}"
    return {
        "driver": driver.value,
        "probable_driver": probable,
        "driver_confidence": round(score, 4),
        "classification_reasons": tuple(sorted(set(reasons))),
    }
