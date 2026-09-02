"""Command Center snapshot assembly (architecture preparation).

Builds a read-only snapshot from existing services.  Domains marked ``planned``
have no ingestion pipeline yet — only structural placeholders.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.core.ecosystem.command_center import CommandCenterSnapshot, DomainModuleStatus
from app.core.ecosystem.domains import EcosystemDomain
from app.core.ecosystem.incident_categories import (
    IncidentCategory,
    PHASE0_ORACLE_CATEGORY_KEYS,
    normalize_incident_category,
)
from app.models.base import utcnow

from .incident_aggregation import get_incident_aggregation_registry
from .threat_assessment_service import ThreatAssessmentService

if TYPE_CHECKING:
    from .analytics_service import AnalyticsService
    from .intelligence_events_service import IntelligenceEventsService
    from app.services.weather_service import WeatherService
    from app.modules.investigations.investigation_service import InvestigationService


def _domain_catalog() -> list[DomainModuleStatus]:
    """Static domain metadata — extended as modules come online."""
    return [
        DomainModuleStatus(
            domain=EcosystemDomain.FOREST_HEALTH,
            status="active",
            label="Forest Health",
            description="Wildfire monitoring, anomaly detection, and regional risk.",
            incident_categories=[
                IncidentCategory.WILDFIRE.value,
                IncidentCategory.DEFORESTATION.value,
                IncidentCategory.ILLEGAL_LOGGING.value,
            ],
            capabilities=["anomaly_detection", "regional_risk", "land_cover"],
            endpoints=[
                "/api/analytics/intelligence/anomalies",
                "/api/analytics/intelligence/risk",
                "/api/analytics/intelligence/land-cover",
            ],
        ),
        DomainModuleStatus(
            domain=EcosystemDomain.WILDLIFE,
            status="planned",
            label="Wildlife",
            description="Wildlife and habitat disturbance monitoring (not yet implemented).",
            incident_categories=[IncidentCategory.HABITAT_DISTURBANCE.value],
            capabilities=[],
            endpoints=[],
        ),
        DomainModuleStatus(
            domain=EcosystemDomain.ENVIRONMENT,
            status="partial",
            label="Environment",
            description="Environmental conditions via cached weather observations.",
            incident_categories=[IncidentCategory.UNKNOWN.value],
            capabilities=["regional_weather"],
            endpoints=["/api/analytics/intelligence/weather"],
        ),
        DomainModuleStatus(
            domain=EcosystemDomain.HUMAN_ACTIVITY,
            status="planned",
            label="Human Activity",
            description="Illegal logging, tree theft, and protected-area violations (planned).",
            incident_categories=[
                IncidentCategory.ILLEGAL_LOGGING.value,
                IncidentCategory.TREE_THEFT.value,
                IncidentCategory.PROTECTED_AREA_VIOLATION.value,
            ],
            capabilities=[],
            endpoints=[],
        ),
    ]


def _count_active_by_category(active_events: list[dict]) -> dict[str, int]:
    counts = {cat: 0 for cat in PHASE0_ORACLE_CATEGORY_KEYS}
    for event in active_events:
        cat = normalize_incident_category(event.get("incident_category"))
        if cat not in counts:
            counts[cat] = 0
        counts[cat] += 1
    return counts


class CommandCenterService:
    """Assembles Command Center snapshots from existing intelligence services."""

    def __init__(
        self,
        analytics_svc: "AnalyticsService",
        intel_svc: "IntelligenceEventsService",
        weather_svc: "WeatherService | None" = None,
        threat_svc: "ThreatAssessmentService | None" = None,
        investigation_svc: "InvestigationService | None" = None,
    ) -> None:
        self._analytics = analytics_svc
        self._intel_svc = intel_svc
        self._weather_svc = weather_svc
        self._threat_svc = threat_svc or ThreatAssessmentService(intel_svc)
        self._investigation_svc = investigation_svc

    async def get_snapshot(self, *, generated_at: datetime | None = None) -> dict:
        ts = generated_at or utcnow()
        registry = get_incident_aggregation_registry()
        incident_aggregation = await registry.aggregate_all(self._analytics)
        intel_events = await self._intel_svc.get_events()
        active_by_category = _count_active_by_category(intel_events.get("active", []))
        threat_summary = await self._threat_svc.get_threat_summary()

        inv_stats = {
            "open_investigations": 0,
            "critical_investigations": 0,
            "average_resolution_time_hours": None,
            "investigations_by_region": {},
        }
        if self._investigation_svc is not None:
            inv_stats = await self._investigation_svc.get_statistics()

        domains = _domain_catalog()
        if self._weather_svc is not None:
            # Environment domain is partial — weather cache is live
            for domain in domains:
                if domain.domain == EcosystemDomain.ENVIRONMENT:
                    domain.status = "partial"

        snapshot = CommandCenterSnapshot(
            generated_at=ts,
            domains=domains,
            incident_aggregation=incident_aggregation,
            active_intel_by_category=active_by_category,
            top_threats=threat_summary.get("top_threats", []),
            threat_distribution=threat_summary.get("distribution", {}),
            human_vs_natural_ratio=threat_summary.get("human_vs_natural_ratio", {}),
            most_affected_domains=threat_summary.get("most_affected_domains", []),
            highest_priority_interventions=threat_summary.get(
                "highest_priority_interventions", []
            ),
            open_investigations=inv_stats.get("open_investigations", 0),
            critical_investigations=inv_stats.get("critical_investigations", 0),
            average_resolution_time_hours=inv_stats.get("average_resolution_time_hours"),
            investigations_by_region=inv_stats.get("investigations_by_region", {}),
        )
        return snapshot.model_dump(mode="json")
