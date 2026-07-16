"""Ecosystem intelligence foundation for ForestWatch.

Shared types used across analytics, intelligence events, reports, and the
future Command Center.  Import from here rather than duplicating enums.
"""
from .command_center import CommandCenterSnapshot, DomainModuleStatus
from .domains import ECOSYSTEM_DOMAINS, EcosystemDomain
from .incident_categories import (
    INCIDENT_CATEGORIES,
    IncidentCategory,
    map_forest_event_type_to_incident,
    normalize_incident_category,
    resolve_incident_category,
)
from .threat_assessment import PriorityLevel, ThreatAssessment
from .threat_categories import THREAT_CATEGORIES, ThreatCategory, ThreatOrigin, threat_origin
from .threat_mapping import (
    affected_domains_for_threat,
    map_forest_event_to_threat,
    map_incident_to_threat,
    recommended_actions_for_threat,
)

__all__ = [
    "CommandCenterSnapshot",
    "DomainModuleStatus",
    "ECOSYSTEM_DOMAINS",
    "EcosystemDomain",
    "INCIDENT_CATEGORIES",
    "IncidentCategory",
    "map_forest_event_type_to_incident",
    "normalize_incident_category",
    "resolve_incident_category",
    "PriorityLevel",
    "ThreatAssessment",
    "THREAT_CATEGORIES",
    "ThreatCategory",
    "ThreatOrigin",
    "threat_origin",
    "affected_domains_for_threat",
    "map_forest_event_to_threat",
    "map_incident_to_threat",
    "recommended_actions_for_threat",
]
