"""Canonical environmental observation model (domain-neutral)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.base import ensure_utc


class EnvironmentalObservation(BaseModel):
    """A single authoritative environmental measurement — not an incident."""

    model_config = ConfigDict(frozen=True)

    pollutant: str
    value: float
    unit: str
    observed_at: datetime
    latitude: float | None = None
    longitude: float | None = None
    station_id: str | None = None
    station_name: str | None = None
    source: str = "EEA Air Quality"
    dataset_id: str = "eea.aq.e2a"
    dataset_version: str = "unknown"
    geographic_scope: str = "Europe"
    provenance: str = "monitoring_station"
    validity: str = "valid"
    missing_value: bool = False

    def to_metadata_block(self) -> dict[str, Any]:
        return {
            "pollutant": self.pollutant,
            "value": self.value,
            "unit": self.unit,
            "observed_at": self.observed_at.isoformat(),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "station_id": self.station_id,
            "station_name": self.station_name,
            "source": self.source,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "geographic_scope": self.geographic_scope,
            "provenance": self.provenance,
            "validity": self.validity,
            "missing_value": self.missing_value,
        }

    @classmethod
    def from_metadata_block(cls, block: dict[str, Any] | None) -> "EnvironmentalObservation | None":
        if not block:
            return None
        try:
            observed = block.get("observed_at")
            if isinstance(observed, str):
                observed_at = ensure_utc(
                    datetime.fromisoformat(observed.replace("Z", "+00:00"))
                )
            elif isinstance(observed, datetime):
                observed_at = ensure_utc(observed)
            else:
                return None
            return cls(
                pollutant=str(block["pollutant"]),
                value=float(block["value"]),
                unit=str(block["unit"]),
                observed_at=observed_at,
                latitude=block.get("latitude"),
                longitude=block.get("longitude"),
                station_id=block.get("station_id"),
                station_name=block.get("station_name"),
                source=str(block.get("source") or "EEA Air Quality"),
                dataset_id=str(block.get("dataset_id") or "eea.aq.e2a"),
                dataset_version=str(block.get("dataset_version") or "unknown"),
                geographic_scope=str(block.get("geographic_scope") or "Europe"),
                provenance=str(block.get("provenance") or "monitoring_station"),
                validity=str(block.get("validity") or "valid"),
                missing_value=bool(block.get("missing_value", False)),
            )
        except Exception:
            return None
