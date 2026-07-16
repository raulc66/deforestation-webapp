"""Environmental threat taxonomy for the Threat Intelligence Engine."""
from __future__ import annotations

from enum import StrEnum
from typing import Literal

ThreatOrigin = Literal["natural", "human", "environmental", "unknown"]


class ThreatCategory(StrEnum):
    # Natural
    WILDFIRE = "wildfire"
    STORM = "storm"
    FLOOD = "flood"
    DROUGHT = "drought"
    LANDSLIDE = "landslide"
    PEST_OUTBREAK = "pest_outbreak"
    DISEASE = "disease"
    # Human Activity
    ILLEGAL_LOGGING = "illegal_logging"
    TREE_THEFT = "tree_theft"
    MINING = "mining"
    AGRICULTURE_EXPANSION = "agriculture_expansion"
    URBAN_EXPANSION = "urban_expansion"
    ROAD_CONSTRUCTION = "road_construction"
    POLLUTION = "pollution"
    WASTE_DUMPING = "waste_dumping"
    POACHING = "poaching"
    # Environmental
    HABITAT_FRAGMENTATION = "habitat_fragmentation"
    WATER_STRESS = "water_stress"
    BIODIVERSITY_LOSS = "biodiversity_loss"
    SOIL_DEGRADATION = "soil_degradation"
    # Unknown
    UNKNOWN = "unknown"


THREAT_CATEGORIES: tuple[str, ...] = tuple(c.value for c in ThreatCategory)

_NATURAL_THREATS: frozenset[ThreatCategory] = frozenset({
    ThreatCategory.WILDFIRE,
    ThreatCategory.STORM,
    ThreatCategory.FLOOD,
    ThreatCategory.DROUGHT,
    ThreatCategory.LANDSLIDE,
    ThreatCategory.PEST_OUTBREAK,
    ThreatCategory.DISEASE,
})

_HUMAN_THREATS: frozenset[ThreatCategory] = frozenset({
    ThreatCategory.ILLEGAL_LOGGING,
    ThreatCategory.TREE_THEFT,
    ThreatCategory.MINING,
    ThreatCategory.AGRICULTURE_EXPANSION,
    ThreatCategory.URBAN_EXPANSION,
    ThreatCategory.ROAD_CONSTRUCTION,
    ThreatCategory.POLLUTION,
    ThreatCategory.WASTE_DUMPING,
    ThreatCategory.POACHING,
})

_ENVIRONMENTAL_THREATS: frozenset[ThreatCategory] = frozenset({
    ThreatCategory.HABITAT_FRAGMENTATION,
    ThreatCategory.WATER_STRESS,
    ThreatCategory.BIODIVERSITY_LOSS,
    ThreatCategory.SOIL_DEGRADATION,
})


def threat_origin(category: ThreatCategory | str) -> ThreatOrigin:
    """Classify a threat as natural, human-caused, or environmental."""
    try:
        cat = ThreatCategory(str(category))
    except ValueError:
        return "unknown"
    if cat in _NATURAL_THREATS:
        return "natural"
    if cat in _HUMAN_THREATS:
        return "human"
    if cat in _ENVIRONMENTAL_THREATS:
        return "environmental"
    return "unknown"


def normalize_threat_category(value: str | None) -> str:
    if not value:
        return ThreatCategory.UNKNOWN.value
    normalized = str(value).strip().lower()
    if normalized in THREAT_CATEGORIES:
        return normalized
    return ThreatCategory.UNKNOWN.value
