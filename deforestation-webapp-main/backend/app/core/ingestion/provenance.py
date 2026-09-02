"""Provenance envelopes for observations and detections.

Preserves the distinction between:
  observation time  — when the environmental signal was measured
  ingestion time    — when ForestWatch normalized and persisted the record
  detection time    — when the detector evaluated baselines
  reconciliation time — when intelligence events were upserted (set downstream)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .ingestion_metadata import IngestionMetadata


class ProvenanceEnvelope(BaseModel):
    """Generalized provenance block with domain-specific evidence."""

    model_config = ConfigDict(frozen=True)

    source_id: str | None = None
    provider_id: str | None = None
    dataset_id: str | None = None
    dataset_version: str | None = None
    source_event_id: str | None = None
    observed_at: datetime | None = None
    ingested_at: datetime | None = None
    license: str | None = None
    geographic_scope: str | None = None
    domain_evidence: dict[str, Any] = Field(default_factory=dict)


def provenance_from_event_metadata(
    metadata: dict[str, Any],
    *,
    geographic_scope: str | None = None,
) -> dict[str, Any]:
    """Extract observation provenance from a persisted ForestEvent metadata block."""
    ingestion_raw = metadata.get("ingestion") or {}
    observation = metadata.get("observation") or {}
    activation = metadata.get("emergency_activation") or {}
    forest_context = metadata.get("forest_context") or {}

    envelope = ProvenanceEnvelope(
        source_id=ingestion_raw.get("source"),
        provider_id=ingestion_raw.get("provider_id"),
        dataset_id=(
            observation.get("dataset_id")
            or activation.get("dataset_id")
            or forest_context.get("dataset_id")
        ),
        dataset_version=observation.get("dataset_version") or forest_context.get("dataset_version"),
        source_event_id=ingestion_raw.get("source_event_id"),
        observed_at=_coerce_dt(observation.get("observed_at") or activation.get("event_time")),
        ingested_at=_coerce_dt(ingestion_raw.get("ingestion_timestamp")),
        license=observation.get("license") or activation.get("license"),
        geographic_scope=geographic_scope,
        domain_evidence=_domain_evidence(metadata),
    )
    return envelope.model_dump(mode="json")


def build_detection_provenance(
    anomaly: dict[str, Any],
    *,
    detected_at: datetime,
    signal_type: str,
    contributing_sources: list[str] | None = None,
) -> dict[str, Any]:
    """Build detection evidence provenance from a legacy anomaly dict."""
    domain: dict[str, Any] = {}
    if anomaly.get("station_id"):
        domain["station_id"] = str(anomaly["station_id"])
        domain["pollutant"] = anomaly.get("pollutant")
        domain["provider_class"] = "eea_air_quality"
    if anomaly.get("hazard_type") or anomaly.get("activation_code"):
        domain["hazard_type"] = anomaly.get("hazard_type")
        domain["activation_code"] = anomaly.get("activation_code")
        domain["provider_class"] = "cems_rapid_mapping"
    if anomaly.get("country") and not domain.get("provider_class"):
        domain["country"] = anomaly.get("country")
    if not domain.get("provider_class") and anomaly.get("region"):
        domain["provider_class"] = "satellite_fire_observations"

    envelope = ProvenanceEnvelope(
        source_id=anomaly.get("source"),
        provider_id=anomaly.get("provider_id"),
        source_event_id=anomaly.get("source_event_id"),
        observed_at=_coerce_dt(anomaly.get("observed_at")),
        ingested_at=_coerce_dt(anomaly.get("ingested_at")),
        domain_evidence={
            **domain,
            "detection_method": signal_type,
            "detected_at": detected_at.isoformat(),
            "contributing_sources": contributing_sources or [],
        },
    )
    return envelope.model_dump(mode="json")


def provenance_from_ingestion_metadata(
    meta: IngestionMetadata,
    *,
    geographic_scope: str | None = None,
) -> dict[str, Any]:
    envelope = ProvenanceEnvelope(
        source_id=meta.source,
        provider_id=meta.provider_id,
        dataset_id=meta.dataset_id,
        dataset_version=meta.dataset_version,
        source_event_id=meta.source_event_id,
        ingested_at=meta.ingestion_timestamp,
        license=meta.provenance_label,
        geographic_scope=geographic_scope,
    )
    return envelope.model_dump(mode="json")


def _domain_evidence(metadata: dict[str, Any]) -> dict[str, Any]:
    observation = metadata.get("observation") or {}
    activation = metadata.get("emergency_activation") or {}
    evidence: dict[str, Any] = {}
    if observation:
        evidence["observation"] = {
            k: observation.get(k)
            for k in ("pollutant", "value", "unit", "station_id", "provenance")
            if observation.get(k) is not None
        }
    if activation:
        evidence["emergency_activation"] = {
            k: activation.get(k)
            for k in ("activation_code", "hazard_type", "countries", "provenance")
            if activation.get(k) is not None
        }
    if metadata.get("forest_context"):
        evidence["forest_context"] = {
            "dataset_id": metadata["forest_context"].get("dataset_id"),
            "provenance": metadata["forest_context"].get("provenance"),
        }
    return evidence


def _coerce_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
