"""Mapping from IncidentCategory and ForestEvent types to ThreatCategory."""
from __future__ import annotations

from app.core.ecosystem.domains import EcosystemDomain
from app.core.ecosystem.incident_categories import IncidentCategory, normalize_incident_category
from app.core.ecosystem.threat_categories import ThreatCategory

# IncidentCategory → ThreatCategory (verified against existing incident taxonomy)
_INCIDENT_TO_THREAT: dict[str, ThreatCategory] = {
    IncidentCategory.WILDFIRE.value: ThreatCategory.WILDFIRE,
    IncidentCategory.ILLEGAL_LOGGING.value: ThreatCategory.ILLEGAL_LOGGING,
    IncidentCategory.TREE_THEFT.value: ThreatCategory.TREE_THEFT,
    IncidentCategory.DEFORESTATION.value: ThreatCategory.HABITAT_FRAGMENTATION,
    IncidentCategory.PROTECTED_AREA_VIOLATION.value: ThreatCategory.ILLEGAL_LOGGING,
    IncidentCategory.HABITAT_DISTURBANCE.value: ThreatCategory.HABITAT_FRAGMENTATION,
    IncidentCategory.UNKNOWN.value: ThreatCategory.UNKNOWN,
}

# ForestEvent.event_type → ThreatCategory (extends existing _FOREST_EVENT_TYPE_MAP)
_FOREST_EVENT_TO_THREAT: dict[str, ThreatCategory] = {
    "wildfire": ThreatCategory.WILDFIRE,
    "logging": ThreatCategory.ILLEGAL_LOGGING,
    "mining": ThreatCategory.MINING,
    "agriculture": ThreatCategory.AGRICULTURE_EXPANSION,
    "road_construction": ThreatCategory.ROAD_CONSTRUCTION,
    "urban_expansion": ThreatCategory.URBAN_EXPANSION,
    "unknown": ThreatCategory.UNKNOWN,
}

# ThreatCategory → affected EcosystemDomain(s)
_THREAT_DOMAINS: dict[ThreatCategory, tuple[EcosystemDomain, ...]] = {
    ThreatCategory.WILDFIRE: (EcosystemDomain.FOREST_HEALTH, EcosystemDomain.ENVIRONMENT),
    ThreatCategory.STORM: (EcosystemDomain.ENVIRONMENT, EcosystemDomain.FOREST_HEALTH),
    ThreatCategory.FLOOD: (EcosystemDomain.ENVIRONMENT,),
    ThreatCategory.DROUGHT: (EcosystemDomain.ENVIRONMENT, EcosystemDomain.FOREST_HEALTH),
    ThreatCategory.LANDSLIDE: (EcosystemDomain.ENVIRONMENT, EcosystemDomain.FOREST_HEALTH),
    ThreatCategory.PEST_OUTBREAK: (EcosystemDomain.FOREST_HEALTH, EcosystemDomain.WILDLIFE),
    ThreatCategory.DISEASE: (EcosystemDomain.FOREST_HEALTH, EcosystemDomain.WILDLIFE),
    ThreatCategory.ILLEGAL_LOGGING: (EcosystemDomain.FOREST_HEALTH, EcosystemDomain.HUMAN_ACTIVITY),
    ThreatCategory.TREE_THEFT: (EcosystemDomain.FOREST_HEALTH, EcosystemDomain.HUMAN_ACTIVITY),
    ThreatCategory.MINING: (EcosystemDomain.HUMAN_ACTIVITY, EcosystemDomain.ENVIRONMENT),
    ThreatCategory.AGRICULTURE_EXPANSION: (EcosystemDomain.HUMAN_ACTIVITY, EcosystemDomain.FOREST_HEALTH),
    ThreatCategory.URBAN_EXPANSION: (EcosystemDomain.HUMAN_ACTIVITY, EcosystemDomain.FOREST_HEALTH),
    ThreatCategory.ROAD_CONSTRUCTION: (EcosystemDomain.HUMAN_ACTIVITY, EcosystemDomain.FOREST_HEALTH),
    ThreatCategory.POLLUTION: (EcosystemDomain.ENVIRONMENT,),
    ThreatCategory.WASTE_DUMPING: (EcosystemDomain.ENVIRONMENT, EcosystemDomain.HUMAN_ACTIVITY),
    ThreatCategory.POACHING: (EcosystemDomain.WILDLIFE, EcosystemDomain.HUMAN_ACTIVITY),
    ThreatCategory.HABITAT_FRAGMENTATION: (EcosystemDomain.WILDLIFE, EcosystemDomain.FOREST_HEALTH),
    ThreatCategory.WATER_STRESS: (EcosystemDomain.ENVIRONMENT,),
    ThreatCategory.BIODIVERSITY_LOSS: (EcosystemDomain.WILDLIFE, EcosystemDomain.ENVIRONMENT),
    ThreatCategory.SOIL_DEGRADATION: (EcosystemDomain.ENVIRONMENT, EcosystemDomain.FOREST_HEALTH),
    ThreatCategory.UNKNOWN: (EcosystemDomain.FOREST_HEALTH,),
}

# Recommended response actions per threat category (deterministic templates)
_RECOMMENDED_ACTIONS: dict[ThreatCategory, tuple[str, ...]] = {
    ThreatCategory.WILDFIRE: (
        "Increase satellite monitoring frequency",
        "Alert regional fire response teams",
        "Review weather and wind conditions",
    ),
    ThreatCategory.ILLEGAL_LOGGING: (
        "Dispatch field inspection team",
        "Cross-reference with protected area boundaries",
        "Notify enforcement authorities",
    ),
    ThreatCategory.TREE_THEFT: (
        "Verify land ownership records",
        "Increase patrol frequency in affected region",
        "Document evidence for enforcement",
    ),
    ThreatCategory.HABITAT_FRAGMENTATION: (
        "Assess connectivity corridors",
        "Monitor wildlife movement patterns",
        "Review land-use change permits",
    ),
    ThreatCategory.MINING: (
        "Verify mining permit compliance",
        "Monitor water quality downstream",
        "Assess habitat impact radius",
    ),
    ThreatCategory.AGRICULTURE_EXPANSION: (
        "Review land conversion permits",
        "Monitor forest edge encroachment",
        "Assess soil and water impact",
    ),
    ThreatCategory.UNKNOWN: (
        "Increase general monitoring",
        "Collect additional field evidence",
    ),
}


def map_incident_to_threat(incident_category: str | None) -> ThreatCategory:
    """Map an :class:`IncidentCategory` value to a :class:`ThreatCategory`."""
    normalized = normalize_incident_category(incident_category)
    return _INCIDENT_TO_THREAT.get(normalized, ThreatCategory.UNKNOWN)


def map_forest_event_to_threat(event_type: str) -> ThreatCategory:
    """Map a ForestEvent ``event_type`` to a :class:`ThreatCategory`."""
    return _FOREST_EVENT_TO_THREAT.get(event_type, ThreatCategory.UNKNOWN)


def affected_domains_for_threat(threat: ThreatCategory) -> list[EcosystemDomain]:
    return list(_THREAT_DOMAINS.get(threat, (EcosystemDomain.FOREST_HEALTH,)))


def recommended_actions_for_threat(threat: ThreatCategory) -> list[str]:
    return list(_RECOMMENDED_ACTIONS.get(threat, _RECOMMENDED_ACTIONS[ThreatCategory.UNKNOWN]))
