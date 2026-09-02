"""Canonical intelligence identity contract (ADR-001, WP1.1).

Identity is ``(incident_category, spatial_key)``. Phase 0 uses administrative
``region`` as the concrete ``spatial_key`` implementation.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.ecosystem.incident_categories import (
    INCIDENT_CATEGORIES,
    normalize_incident_category,
)


class CanonicalIdentity(BaseModel):
    """Stable intelligence identity — not mutable state."""

    model_config = ConfigDict(frozen=True)

    incident_category: str
    spatial_key: str

    @field_validator("incident_category")
    @classmethod
    def _validate_incident_category(cls, value: str) -> str:
        normalized = normalize_incident_category(value)
        if normalized not in INCIDENT_CATEGORIES:
            raise ValueError(f"invalid incident_category: {value!r}")
        return normalized

    @field_validator("spatial_key")
    @classmethod
    def _validate_spatial_key(cls, value: str) -> str:
        key = str(value).strip()
        if not key:
            raise ValueError("spatial_key must be non-empty")
        return key

    @classmethod
    def from_region(
        cls,
        region: str,
        *,
        incident_category: str = "wildfire",
    ) -> CanonicalIdentity:
        """Phase 0 helper — administrative region as spatial key."""
        return cls(
            incident_category=normalize_incident_category(incident_category),
            spatial_key=spatial_key_from_region(region),
        )

    def as_key_tuple(self) -> tuple[str, str]:
        return (self.incident_category, self.spatial_key)


def spatial_key_from_region(region: str) -> str:
    """Map a legacy administrative region to the Phase 0 spatial key."""
    key = str(region).strip()
    if not key:
        raise ValueError("region must be non-empty")
    return key


def spatial_key_from_station(station_id: str) -> str:
    """Monitoring-station spatial key — distinct from administrative regions."""
    station = str(station_id).strip()
    if not station:
        raise ValueError("station_id must be non-empty")
    return f"aq-station:{station}"


def spatial_key_from_cems_country(country: str) -> str:
    """Country-level CEMS activation spatial key."""
    label = str(country).strip()
    if not label:
        raise ValueError("country must be non-empty")
    return f"cems-country:{label}"


def spatial_key_from_disturbance_alert(alert_id: str) -> str:
    """Alert-level forest disturbance spatial key."""
    alert = str(alert_id).strip()
    if not alert:
        raise ValueError("alert_id must be non-empty")
    return f"disturbance-alert:{alert}"


def region_from_spatial_key(spatial_key: str) -> str:
    """Resolve legacy region label from a spatial key."""
    key = str(spatial_key).strip()
    if key.startswith("aq-station:"):
        return key[len("aq-station:") :]
    if key.startswith("cems-country:"):
        return key[len("cems-country:") :]
    if key.startswith("disturbance-alert:"):
        return key[len("disturbance-alert:") :]
    return spatial_key_from_region(key)
