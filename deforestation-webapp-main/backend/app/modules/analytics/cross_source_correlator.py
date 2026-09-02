"""Deterministic cross-source detection correlator.

Runs after Detection generation and before reconciliation persistence.
Does not merge detections into a single intelligence event.
"""
from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Any

from app.modules.analytics.correlation_config import (
    CorrelationConfig,
    CorrelationRuleConfig,
    build_correlation_config,
)
from app.modules.analytics.correlation_result import CorrelationParticipant, CorrelationResult
from app.modules.analytics.detection_contract import Detection
from app.modules.analytics.reconciliation import identity_key_from_detection


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def detection_coordinates(detection: Detection) -> tuple[float, float] | None:
    evidence = detection.evidence
    lat = evidence.get("latitude")
    lng = evidence.get("longitude")
    if lat is None or lng is None:
        return None
    return float(lat), float(lng)


def detection_provider_id(detection: Detection) -> str | None:
    provenance = detection.evidence.get("provenance") or {}
    provider_id = provenance.get("provider_id")
    if provider_id:
        return str(provider_id)
    domain = provenance.get("domain_evidence") or {}
    provider_class = domain.get("provider_class")
    mapping = {
        "satellite_fire_observations": "nasa.firms",
        "eea_air_quality": "eea.air_quality",
        "cems_rapid_mapping": "cems.rapid_mapping",
        "effis_wildfire_context": "effis.wildfire_context",
        "gfw_integrated_alerts": "gfw.integrated_alerts",
    }
    if provider_class in mapping:
        return mapping[str(provider_class)]
    return str(provider_class) if provider_class else None


def detection_source_event_id(detection: Detection) -> str | None:
    provenance = detection.evidence.get("provenance") or {}
    value = provenance.get("source_event_id")
    return str(value) if value else None


def detection_hazard_type(detection: Detection) -> str | None:
    hazard = detection.evidence.get("hazard_type")
    if hazard:
        return str(hazard)
    domain = (detection.evidence.get("provenance") or {}).get("domain_evidence") or {}
    value = domain.get("hazard_type")
    return str(value) if value else None


def detection_country(detection: Detection) -> str | None:
    country = detection.evidence.get("country")
    if country:
        return str(country).strip().lower()
    domain = (detection.evidence.get("provenance") or {}).get("domain_evidence") or {}
    value = domain.get("country")
    return str(value).strip().lower() if value else None


def _temporal_delta_hours(a: datetime, b: datetime) -> float:
    return abs((_ensure_utc(a) - _ensure_utc(b)).total_seconds()) / 3600.0


def _correlation_id(rule_name: str, keys: list[tuple[str, str]]) -> str:
    ordered = sorted(f"{cat}:{sk}" for cat, sk in keys)
    digest = hashlib.sha256(f"{rule_name}|{'|'.join(ordered)}".encode()).hexdigest()
    return digest[:16]


def _spatial_label(distance_km: float | None, *, country_match: bool = False) -> str:
    if country_match:
        return "same_country"
    if distance_km is None:
        return "unknown"
    if distance_km <= 5:
        return "co_located"
    if distance_km <= 25:
        return "nearby"
    return "regional_proximity"


def _temporal_label(delta_hours: float) -> str:
    if delta_hours <= 6:
        return "same_window"
    if delta_hours <= 24:
        return "within_day"
    return "within_window"


def _rule_matches_detection(
    detection: Detection,
    *,
    categories: frozenset[str],
    provider_ids: frozenset[str],
    hazard_types: frozenset[str] = frozenset(),
) -> bool:
    if detection.incident_category not in categories:
        return False
    if provider_ids:
        pid = detection_provider_id(detection)
        if pid not in provider_ids:
            return False
    if hazard_types:
        hazard = detection_hazard_type(detection)
        if hazard not in hazard_types:
            return False
    return True


def _compute_strength(rule: CorrelationRuleConfig, *, distance_km: float | None, delta_hours: float) -> float:
    spatial_factor = 1.0
    if distance_km is not None and rule.max_spatial_distance_km > 0:
        spatial_factor = max(0.0, 1.0 - (distance_km / rule.max_spatial_distance_km))
    temporal_factor = 1.0
    if rule.max_temporal_hours > 0:
        temporal_factor = max(0.0, 1.0 - (delta_hours / rule.max_temporal_hours))
    strength = rule.base_strength * (0.6 * spatial_factor + 0.4 * temporal_factor)
    return round(min(1.0, max(0.0, strength)), 4)


class CrossSourceCorrelator:
    """Deterministic correlator — no ML, no provider-specific logic in analytics."""

    def __init__(self, config: CorrelationConfig | None = None) -> None:
        self._config = config or build_correlation_config()

    def correlate(
        self,
        detections: list[Detection],
        now: datetime,
        *,
        geographic_scope: str | None = None,
    ) -> list[CorrelationResult]:
        if len(detections) < 2:
            return []

        results: list[CorrelationResult] = []
        seen_ids: set[str] = set()

        for rule in self._config.rules:
            left = [
                d
                for d in detections
                if _rule_matches_detection(
                    d,
                    categories=rule.left_categories,
                    provider_ids=rule.left_provider_ids,
                )
            ]
            right = [
                d
                for d in detections
                if _rule_matches_detection(
                    d,
                    categories=rule.right_categories,
                    provider_ids=rule.right_provider_ids,
                    hazard_types=rule.right_hazard_types,
                )
            ]
            for det_a in left:
                for det_b in right:
                    if identity_key_from_detection(det_a) == identity_key_from_detection(det_b):
                        continue
                    pair_result = self._evaluate_pair(
                        det_a,
                        det_b,
                        rule=rule,
                        now=now,
                        geographic_scope=geographic_scope,
                    )
                    if pair_result is None:
                        continue
                    if pair_result.correlation_id in seen_ids:
                        continue
                    seen_ids.add(pair_result.correlation_id)
                    results.append(pair_result)

        return sorted(results, key=lambda item: (item.correlation_id, item.correlation_rule))

    def _evaluate_pair(
        self,
        det_a: Detection,
        det_b: Detection,
        *,
        rule: CorrelationRuleConfig,
        now: datetime,
        geographic_scope: str | None,
    ) -> CorrelationResult | None:
        coords_a = detection_coordinates(det_a)
        coords_b = detection_coordinates(det_b)
        delta_hours = _temporal_delta_hours(det_a.detected_at, det_b.detected_at)
        if delta_hours > rule.max_temporal_hours:
            return None

        distance_km: float | None = None
        country_match = False
        if coords_a and coords_b:
            distance_km = _haversine_km(coords_a[0], coords_a[1], coords_b[0], coords_b[1])
            if distance_km > rule.max_spatial_distance_km:
                return None
        elif rule.allow_country_fallback:
            country_a = detection_country(det_a)
            country_b = detection_country(det_b)
            if country_a and country_b and country_a == country_b:
                country_match = True
            else:
                return None
        else:
            return None

        key_a = identity_key_from_detection(det_a)
        key_b = identity_key_from_detection(det_b)
        correlation_id = _correlation_id(rule.name, [key_a, key_b])
        strength = _compute_strength(rule, distance_km=distance_km, delta_hours=delta_hours)

        participants = tuple(
            sorted(
                [
                    CorrelationParticipant(
                        incident_category=det_a.incident_category,
                        spatial_key=det_a.spatial_key,
                        provider_id=detection_provider_id(det_a),
                        source_event_id=detection_source_event_id(det_a),
                        detected_at=det_a.detected_at,
                        role="primary" if det_a.score >= det_b.score else "supporting",
                    ),
                    CorrelationParticipant(
                        incident_category=det_b.incident_category,
                        spatial_key=det_b.spatial_key,
                        provider_id=detection_provider_id(det_b),
                        source_event_id=detection_source_event_id(det_b),
                        detected_at=det_b.detected_at,
                        role="primary" if det_b.score >= det_a.score else "supporting",
                    ),
                ],
                key=lambda p: (p.incident_category, p.spatial_key),
            )
        )

        provider_ids = tuple(
            sorted({pid for pid in (detection_provider_id(det_a), detection_provider_id(det_b)) if pid})
        )

        primary = det_a if det_a.score >= det_b.score else det_b
        return CorrelationResult(
            correlation_id=correlation_id,
            canonical_incident_category=primary.incident_category,
            canonical_spatial_key=primary.spatial_key,
            relationship_type=rule.relationship_type,
            correlation_rule=rule.name,
            participants=participants,
            participating_provider_ids=provider_ids,
            spatial_relationship=_spatial_label(distance_km, country_match=country_match),
            temporal_relationship=_temporal_label(delta_hours),
            strength=strength,
            created_at=now,
            provenance_summary=_provenance_summary(det_a, det_b, geographic_scope),
        )


def _provenance_summary(
    det_a: Detection,
    det_b: Detection,
    geographic_scope: str | None,
) -> dict[str, Any]:
    return {
        "geographic_scope": geographic_scope,
        "sources": sorted(
            {
                pid
                for pid in (detection_provider_id(det_a), detection_provider_id(det_b))
                if pid
            }
        ),
    }
