"""Standardized ingestion metadata embedded in every ForestEvent.

Every ingestion source (FIRMS, CSV, future GFW, etc.) produces an
IngestionMetadata block stored at ``ForestEvent.metadata["ingestion"]``.
This gives analytics a stable cross-source key without altering the
ForestEvent schema.

Usage:
    from app.core.ingestion.ingestion_metadata import build_ingestion_metadata

    meta = build_ingestion_metadata(
        source="NASA FIRMS",
        source_event_id=None,
        is_romania=True,
        confidence=0.9,
        severity="high",
    )
    payload = ForestEventCreate(
        ...
        metadata={"ingestion": meta.model_dump(), ...other_source_keys...},
    )
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict


class IngestionMetadata(BaseModel):
    """Normalized per-event ingestion context, source-agnostic.

    Stored verbatim inside ``ForestEvent.metadata["ingestion"]``.
    All fields are intentionally flat for easy MongoDB queries.
    """

    model_config = ConfigDict(frozen=True)

    source: str
    """Human-readable data source name: 'NASA FIRMS', 'CSV', 'GFW', etc."""

    provider_id: str | None = None
    """Stable provider identifier (e.g. ``nasa.firms``)."""

    dataset_id: str | None = None
    dataset_version: str | None = None
    provenance_label: str | None = None

    source_event_id: str | None
    """Provider-specific row / feature identifier, or None when unavailable."""

    ingestion_timestamp: datetime
    """UTC datetime when this record was normalized and persisted."""

    is_romania: bool
    """True when the event is geographically classified as being in Romania."""

    confidence: float | None
    """Normalized detection confidence in [0.0, 1.0], or None if unknown."""

    severity: str | None
    """Severity label: 'low' | 'medium' | 'high' | 'critical', or None."""


def build_ingestion_metadata(
    *,
    source: str,
    source_event_id: str | None,
    is_romania: bool,
    confidence: float | None,
    severity: str | None,
    ingestion_timestamp: datetime | None = None,
    provider_id: str | None = None,
    dataset_id: str | None = None,
    dataset_version: str | None = None,
    provenance_label: str | None = None,
) -> IngestionMetadata:
    """Construct an IngestionMetadata instance with a UTC timestamp.

    Args:
        source:             Data source name (e.g. "NASA FIRMS").
        source_event_id:    Provider-internal row ID, or None.
        is_romania:         Result of ``is_romania_event()`` for this record.
        confidence:         Normalized confidence float (0.0–1.0), or None.
        severity:           Severity label string, or None.
        ingestion_timestamp: Explicit UTC datetime; defaults to ``utcnow()``.

    Returns:
        An immutable IngestionMetadata instance.
    """
    return IngestionMetadata(
        source=source,
        provider_id=provider_id,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        provenance_label=provenance_label,
        source_event_id=source_event_id,
        ingestion_timestamp=ingestion_timestamp or datetime.now(timezone.utc),
        is_romania=is_romania,
        confidence=confidence,
        severity=severity,
    )


def ingestion_metadata_from_event(event_metadata: dict[str, Any]) -> IngestionMetadata | None:
    """Reconstruct IngestionMetadata from a stored ForestEvent.metadata dict.

    Returns None when the event predates ingestion metadata (legacy records).
    """
    raw = event_metadata.get("ingestion")
    if not raw:
        return None
    return IngestionMetadata.model_validate(raw)
