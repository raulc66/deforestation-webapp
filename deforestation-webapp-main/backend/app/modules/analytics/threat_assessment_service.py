"""Environmental Threat Intelligence Engine.

Classifies ecosystem threats from existing intelligence events and incident
categories.  Does not duplicate AnalyticsService — consumes
IntelligenceEventsService only.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.ecosystem.domains import EcosystemDomain
from app.core.ecosystem.incident_categories import normalize_incident_category
from app.core.ecosystem.threat_assessment import PriorityLevel, ThreatAssessment
from app.core.ecosystem.threat_categories import (
    THREAT_CATEGORIES,
    ThreatCategory,
    threat_origin,
)
from app.core.ecosystem.threat_mapping import (
    affected_domains_for_threat,
    map_incident_to_threat,
    recommended_actions_for_threat,
)
from app.models.base import utcnow

if TYPE_CHECKING:
    from .intelligence_events_service import IntelligenceEventsService

# ---------------------------------------------------------------------------
# Pure scoring helpers — deterministic, no ML
# ---------------------------------------------------------------------------

_SEVERITY_SCORE: dict[str, float] = {
    "low": 0.25,
    "medium": 0.50,
    "high": 0.75,
    "critical": 1.00,
}

_ESCALATION_BOOST: dict[str, float] = {
    "normal": 0.0,
    "persistent": 0.15,
    "critical": 0.30,
}

_TREND_BOOST: dict[str, float] = {
    "new": 0.05,
    "stable": 0.0,
    "improving": -0.10,
    "worsening": 0.15,
}

_PRIORITY_ORDER = {
    PriorityLevel.LOW: 0,
    PriorityLevel.MEDIUM: 1,
    PriorityLevel.HIGH: 2,
    PriorityLevel.CRITICAL: 3,
}


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _score_to_priority(score: float) -> PriorityLevel:
    if score >= 0.85:
        return PriorityLevel.CRITICAL
    if score >= 0.65:
        return PriorityLevel.HIGH
    if score >= 0.40:
        return PriorityLevel.MEDIUM
    return PriorityLevel.LOW


def _compute_confidence(event: dict) -> float:
    """Derive confidence from intelligence event score and severity."""
    score = float(event.get("current_score", 0.0))
    severity = _SEVERITY_SCORE.get(str(event.get("severity", "medium")), 0.5)
    detections = int(event.get("detection_count", 1))
    detection_factor = min(1.0, 0.5 + detections * 0.05)
    return round(_clamp(0.5 * score + 0.3 * severity + 0.2 * detection_factor), 4)


def _compute_risk_contribution(event: dict) -> float:
    priority = float(event.get("priority_score", 0.0))
    severity = _SEVERITY_SCORE.get(str(event.get("severity", "medium")), 0.5)
    return round(_clamp(0.6 * priority + 0.4 * severity), 4)


def _compute_monitoring_priority(event: dict, threat: ThreatCategory) -> PriorityLevel:
    base = float(event.get("priority_score", 0.0))
    esc = _ESCALATION_BOOST.get(str(event.get("escalation_level", "normal")), 0.0)
    trend = _TREND_BOOST.get(str(event.get("trend", "stable")), 0.0)
    # Natural wildfire threats get slightly elevated monitoring
    if threat == ThreatCategory.WILDFIRE:
        base += 0.05
    return _score_to_priority(_clamp(base + esc + trend))


def _compute_intervention_priority(
    event: dict, threat: ThreatCategory, origin: str
) -> PriorityLevel:
    monitoring = _compute_monitoring_priority(event, threat)
    base_score = _PRIORITY_ORDER[monitoring]
    # Human-caused threats escalate intervention priority
    if origin == "human":
        base_score += 1
    if str(event.get("escalation_level")) == "critical":
        base_score += 1
    return _score_to_priority(_clamp(base_score / 3.0))


def _compute_long_term_impact(event: dict, threat: ThreatCategory) -> PriorityLevel:
    severity = _SEVERITY_SCORE.get(str(event.get("severity", "medium")), 0.5)
    persistent = 0.2 if str(event.get("escalation_level")) in ("persistent", "critical") else 0.0
    structural = 0.15 if threat in (
        ThreatCategory.HABITAT_FRAGMENTATION,
        ThreatCategory.BIODIVERSITY_LOSS,
        ThreatCategory.SOIL_DEGRADATION,
        ThreatCategory.ILLEGAL_LOGGING,
    ) else 0.0
    return _score_to_priority(_clamp(severity + persistent + structural))


def assess_from_intelligence_event(event: dict) -> ThreatAssessment:
    """Convert a persisted intelligence event dict into a ThreatAssessment."""
    incident_cat = normalize_incident_category(event.get("incident_category"))
    threat_cat = map_incident_to_threat(incident_cat)
    origin = threat_origin(threat_cat)

    return ThreatAssessment(
        threat_category=threat_cat,
        confidence=_compute_confidence(event),
        risk_contribution=_compute_risk_contribution(event),
        affected_domains=affected_domains_for_threat(threat_cat),
        origin=origin,
        long_term_impact=_compute_long_term_impact(event, threat_cat),
        monitoring_priority=_compute_monitoring_priority(event, threat_cat),
        intervention_priority=_compute_intervention_priority(event, threat_cat, origin),
        recommended_actions=recommended_actions_for_threat(threat_cat),
        region=event.get("region"),
        incident_category=incident_cat,
        source_event_id=event.get("id"),
    )


def build_threat_summary(assessments: list[ThreatAssessment]) -> dict:
    """Aggregate threat assessments into a summary payload."""
    distribution: dict[str, int] = {cat: 0 for cat in THREAT_CATEGORIES}
    domain_counts: dict[str, int] = {d.value: 0 for d in EcosystemDomain}
    human_count = natural_count = environmental_count = unknown_count = 0

    for assessment in assessments:
        key = assessment.threat_category.value
        distribution[key] = distribution.get(key, 0) + 1
        if assessment.origin == "human":
            human_count += 1
        elif assessment.origin == "natural":
            natural_count += 1
        elif assessment.origin == "environmental":
            environmental_count += 1
        else:
            unknown_count += 1
        for domain in assessment.affected_domains:
            domain_counts[domain.value] = domain_counts.get(domain.value, 0) + 1

    total = len(assessments) or 1
    human_vs_natural = {
        "human": round(human_count / total, 4),
        "natural": round(natural_count / total, 4),
        "environmental": round(environmental_count / total, 4),
        "unknown": round(unknown_count / total, 4),
    }

    sorted_by_intervention = sorted(
        assessments,
        key=lambda a: (
            -_PRIORITY_ORDER[a.intervention_priority],
            -a.risk_contribution,
        ),
    )
    sorted_by_risk = sorted(assessments, key=lambda a: -a.risk_contribution)

    most_affected_domains = sorted(
        [{"domain": k, "threat_count": v} for k, v in domain_counts.items() if v > 0],
        key=lambda x: -x["threat_count"],
    )

    return {
        "distribution": {k: v for k, v in distribution.items() if v > 0},
        "human_vs_natural_ratio": human_vs_natural,
        "most_affected_domains": most_affected_domains,
        "top_threats": [a.model_dump(mode="json") for a in sorted_by_risk[:10]],
        "highest_priority_interventions": [
            a.model_dump(mode="json") for a in sorted_by_intervention[:10]
        ],
    }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ThreatAssessmentService:
    """Orchestrates threat classification from existing intelligence data."""

    def __init__(self, intel_svc: "IntelligenceEventsService") -> None:
        self._intel_svc = intel_svc

    async def get_threats(self) -> dict:
        """Return threat assessments for all active intelligence events."""
        events = await self._intel_svc.get_events()
        active = events.get("active", [])
        assessments = [assess_from_intelligence_event(e) for e in active]
        return {
            "generated_at": utcnow().isoformat(),
            "threats": [a.model_dump(mode="json") for a in assessments],
        }

    async def get_threat_summary(self) -> dict:
        """Return aggregated threat intelligence summary."""
        events = await self._intel_svc.get_events()
        active = events.get("active", [])
        assessments = [assess_from_intelligence_event(e) for e in active]
        summary = build_threat_summary(assessments)
        return {
            "generated_at": utcnow().isoformat(),
            **summary,
        }

    async def get_threat_assessment_report(self) -> dict:
        """Combined payload for the Environmental Threat Assessment report section."""
        threats = await self.get_threats()
        summary = await self.get_threat_summary()
        return {
            "generated_at": threats["generated_at"],
            "threats": threats["threats"],
            **{k: v for k, v in summary.items() if k != "generated_at"},
        }
