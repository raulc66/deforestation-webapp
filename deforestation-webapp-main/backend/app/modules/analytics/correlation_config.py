"""Central configuration for deterministic cross-source correlation."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache


@dataclass(frozen=True)
class CorrelationRuleConfig:
    """One deterministic correlation rule."""

    name: str
    left_categories: frozenset[str]
    right_categories: frozenset[str]
    relationship_type: str
    max_spatial_distance_km: float
    max_temporal_hours: int
    base_strength: float
    left_provider_ids: frozenset[str] = frozenset()
    right_provider_ids: frozenset[str] = frozenset()
    right_hazard_types: frozenset[str] = frozenset()
    allow_country_fallback: bool = False


@dataclass(frozen=True)
class CorrelationConfig:
    """All spatial/temporal thresholds — no scattered magic numbers."""

    spatial_distance_km_default: float = 50.0
    temporal_hours_default: int = 72
    rules: tuple[CorrelationRuleConfig, ...] = field(default_factory=tuple)


DEFAULT_CORRELATION_RULES: tuple[CorrelationRuleConfig, ...] = (
    CorrelationRuleConfig(
        name="firms_cems_wildfire_support",
        left_categories=frozenset({"wildfire"}),
        right_categories=frozenset({"environmental_hazard"}),
        left_provider_ids=frozenset({"nasa.firms", "satellite_fire_observations"}),
        right_provider_ids=frozenset({"cems.rapid_mapping"}),
        right_hazard_types=frozenset({"wildfire"}),
        relationship_type="supporting_evidence",
        max_spatial_distance_km=50.0,
        max_temporal_hours=72,
        base_strength=0.70,
        allow_country_fallback=True,
    ),
    CorrelationRuleConfig(
        name="firms_eea_contextual",
        left_categories=frozenset({"wildfire"}),
        right_categories=frozenset({"air_quality"}),
        left_provider_ids=frozenset({"nasa.firms", "satellite_fire_observations"}),
        right_provider_ids=frozenset({"eea.air_quality"}),
        relationship_type="contextual_evidence",
        max_spatial_distance_km=30.0,
        max_temporal_hours=48,
        base_strength=0.50,
    ),
    CorrelationRuleConfig(
        name="eea_cems_multi_source",
        left_categories=frozenset({"air_quality"}),
        right_categories=frozenset({"environmental_hazard"}),
        left_provider_ids=frozenset({"eea.air_quality"}),
        right_provider_ids=frozenset({"cems.rapid_mapping"}),
        relationship_type="multi_source_situation",
        max_spatial_distance_km=40.0,
        max_temporal_hours=48,
        base_strength=0.55,
        allow_country_fallback=True,
    ),
    CorrelationRuleConfig(
        name="firms_effis_contextual",
        left_categories=frozenset({"wildfire"}),
        right_categories=frozenset({"wildfire"}),
        left_provider_ids=frozenset({"nasa.firms", "satellite_fire_observations"}),
        right_provider_ids=frozenset({"effis.wildfire_context"}),
        relationship_type="contextual_evidence",
        max_spatial_distance_km=25.0,
        max_temporal_hours=720,
        base_strength=0.60,
    ),
    CorrelationRuleConfig(
        name="disturbance_wildfire_contextual",
        left_categories=frozenset({"forest_disturbance"}),
        right_categories=frozenset({"wildfire"}),
        left_provider_ids=frozenset({"gfw.integrated_alerts"}),
        right_provider_ids=frozenset({"nasa.firms", "satellite_fire_observations"}),
        relationship_type="contextual_evidence",
        max_spatial_distance_km=20.0,
        max_temporal_hours=168,
        base_strength=0.55,
    ),
    CorrelationRuleConfig(
        name="disturbance_effis_contextual",
        left_categories=frozenset({"forest_disturbance"}),
        right_categories=frozenset({"wildfire"}),
        left_provider_ids=frozenset({"gfw.integrated_alerts"}),
        right_provider_ids=frozenset({"effis.wildfire_context"}),
        relationship_type="contextual_evidence",
        max_spatial_distance_km=20.0,
        max_temporal_hours=720,
        base_strength=0.58,
    ),
    CorrelationRuleConfig(
        name="disturbance_cems_contextual",
        left_categories=frozenset({"forest_disturbance"}),
        right_categories=frozenset({"environmental_hazard"}),
        left_provider_ids=frozenset({"gfw.integrated_alerts"}),
        right_provider_ids=frozenset({"cems.rapid_mapping"}),
        relationship_type="contextual_evidence",
        max_spatial_distance_km=40.0,
        max_temporal_hours=168,
        base_strength=0.50,
        allow_country_fallback=True,
    ),
)


def build_correlation_config(
    *,
    spatial_distance_km: float = 50.0,
    temporal_hours: int = 72,
) -> CorrelationConfig:
    """Build config with explicit thresholds — no scattered magic numbers."""
    return CorrelationConfig(
        spatial_distance_km_default=spatial_distance_km,
        temporal_hours_default=temporal_hours,
        rules=DEFAULT_CORRELATION_RULES,
    )


@lru_cache()
def get_correlation_config() -> CorrelationConfig:
    from app.core.config import get_settings

    settings = get_settings()
    return build_correlation_config(
        spatial_distance_km=settings.correlation_spatial_distance_km,
        temporal_hours=settings.correlation_temporal_hours,
    )
