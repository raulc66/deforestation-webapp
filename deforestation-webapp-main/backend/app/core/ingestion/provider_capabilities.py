"""Future provider capability matrix (Package F).

Documents which ingestion capabilities each source class is expected to
implement. No external APIs or credentials are declared here.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCapability:
    source_class: str
    fetch: bool
    normalize: bool
    validation: bool
    source_metadata: bool
    source_event_identity: bool
    confidence: bool
    category_mapping: bool
    geographic_information: bool
    timestamps: bool
    status: str  # "live" | "planned" | "supported"


PROVIDER_CAPABILITY_MATRIX: tuple[ProviderCapability, ...] = (
    ProviderCapability(
        source_class="satellite_fire_observations",
        fetch=True,
        normalize=True,
        validation=True,
        source_metadata=True,
        source_event_identity=True,
        confidence=True,
        category_mapping=True,
        geographic_information=True,
        timestamps=True,
        status="live",
    ),
    ProviderCapability(
        source_class="land_cover_change_detection",
        fetch=True,
        normalize=True,
        validation=True,
        source_metadata=True,
        source_event_identity=False,
        confidence=True,
        category_mapping=False,
        geographic_information=True,
        timestamps=True,
        status="contextual_fixture",
    ),
    ProviderCapability(
        source_class="meteorological_observations",
        fetch=True,
        normalize=True,
        validation=True,
        source_metadata=True,
        source_event_identity=False,
        confidence=True,
        category_mapping=False,
        geographic_information=True,
        timestamps=True,
        status="live",
    ),
    ProviderCapability(
        source_class="hydrological_flood_observations",
        fetch=True,
        normalize=True,
        validation=True,
        source_metadata=True,
        source_event_identity=True,
        confidence=True,
        category_mapping=True,
        geographic_information=True,
        timestamps=True,
        status="planned",
    ),
    ProviderCapability(
        source_class="protected_area_environmental_datasets",
        fetch=True,
        normalize=True,
        validation=True,
        source_metadata=True,
        source_event_identity=True,
        confidence=False,
        category_mapping=True,
        geographic_information=True,
        timestamps=True,
        status="planned",
    ),
    ProviderCapability(
        source_class="copernicus_ems_rapid_mapping",
        fetch=True,
        normalize=True,
        validation=True,
        source_metadata=True,
        source_event_identity=True,
        confidence=True,
        category_mapping=True,
        geographic_information=True,
        timestamps=True,
        status="live",
    ),
    ProviderCapability(
        source_class="european_public_environmental_datasets",
        fetch=True,
        normalize=True,
        validation=True,
        source_metadata=True,
        source_event_identity=True,
        confidence=False,
        category_mapping=True,
        geographic_information=True,
        timestamps=True,
        status="planned",
    ),
)
