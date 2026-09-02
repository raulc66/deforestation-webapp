"""Generalized source descriptor — single schema for all environmental providers."""
from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SourceType(StrEnum):
    OBSERVATION = "observation"
    CONTEXTUAL = "contextual"
    METEOROLOGICAL = "meteorological"


class AccessType(StrEnum):
    LIVE = "live"
    FIXTURE = "fixture"
    TOKEN = "token"
    PUBLIC_API = "public_api"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class SourceDescriptor(BaseModel):
    """Domain-neutral description of an environmental data source."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    provider_id: str
    display_name: str
    source_type: str
    incident_categories: tuple[str, ...] = ()
    geographic_coverage: str = "unknown"
    temporal_coverage: str = "unknown"
    update_cadence: str = "unknown"
    access_type: str = AccessType.UNKNOWN.value
    license_provenance: str | None = None
    dataset_id: str | None = None
    dataset_version: str | None = None
    enabled: bool = True
    reliability_status: str = "unknown"


def _normalize_access_type(raw: str | None) -> str:
    if not raw:
        return AccessType.UNKNOWN.value
    normalized = str(raw).strip().lower()
    mapping = {
        "live": AccessType.LIVE.value,
        "fixture": AccessType.FIXTURE.value,
        "fixture_only": AccessType.FIXTURE.value,
        "token_configured": AccessType.TOKEN.value,
        "public_api": AccessType.PUBLIC_API.value,
        "disabled": AccessType.DISABLED.value,
    }
    return mapping.get(normalized, normalized)


def source_descriptor_from_describe(
    describe: dict[str, Any],
    *,
    source_type: str = SourceType.OBSERVATION.value,
    incident_categories: tuple[str, ...] = (),
    enabled: bool = True,
    reliability_status: str = "unknown",
) -> SourceDescriptor:
    """Build a :class:`SourceDescriptor` from a provider ``describe()`` dict."""
    display_name = str(describe.get("source") or describe.get("display_name") or "Unknown")
    provider_id = str(
        describe.get("provider_id")
        or describe.get("dataset_id")
        or display_name.lower().replace(" ", ".")
    )
    return SourceDescriptor(
        source_id=provider_id,
        provider_id=provider_id,
        display_name=display_name,
        source_type=source_type,
        incident_categories=incident_categories,
        geographic_coverage=str(describe.get("geographic_coverage") or "unknown"),
        temporal_coverage=str(describe.get("temporal_resolution") or describe.get("temporal_coverage") or "unknown"),
        update_cadence=str(describe.get("update_frequency") or describe.get("update_cadence") or "unknown"),
        access_type=_normalize_access_type(describe.get("live_access_status") or describe.get("access_type")),
        license_provenance=describe.get("license"),
        dataset_id=describe.get("dataset_id"),
        dataset_version=describe.get("dataset_version"),
        enabled=enabled,
        reliability_status=reliability_status,
    )
