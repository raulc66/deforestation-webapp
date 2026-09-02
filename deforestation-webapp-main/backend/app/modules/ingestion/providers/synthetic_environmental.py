"""Synthetic environmental provider for ingestion contract tests (Package C).

Exercises the generic ingestion pipeline without external APIs or credentials.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.ecosystem.incident_categories import IncidentCategory
from app.core.ingestion.ingestion_metadata import build_ingestion_metadata
from app.core.ingestion.provider_contract import IngestionProvider
from app.models.forest_event import ForestEventCreate

SYNTHETIC_SOURCE_NAME = "Synthetic Environmental Observations"


class SyntheticEnvironmentalProvider(IngestionProvider):
    """Deterministic second provider for pipeline compatibility tests."""

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self._records = records if records is not None else _DEFAULT_RECORDS

    @property
    def source_name(self) -> str:
        return SYNTHETIC_SOURCE_NAME

    @property
    def supported_incident_categories(self) -> tuple[str, ...]:
        return (IncidentCategory.ILLEGAL_LOGGING.value,)

    async def fetch(self) -> list[dict[str, Any]]:
        return list(self._records)

    def normalize(self, raw: dict[str, Any]) -> ForestEventCreate:
        lat = float(raw["latitude"])
        lng = float(raw["longitude"])
        detected_at = raw.get("detected_at") or datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
        confidence = float(raw.get("confidence", 0.75))
        severity = str(raw.get("severity", "medium"))
        region = str(raw.get("region", "Harghita"))
        source_event_id = str(raw.get("source_event_id", "synthetic-001"))

        ingestion_meta = build_ingestion_metadata(
            source=self.source_name,
            source_event_id=source_event_id,
            is_romania=True,
            confidence=confidence,
            severity=severity,
        )

        return ForestEventCreate(
            title=f"Synthetic logging observation {lat:.4f},{lng:.4f}",
            country="Romania",
            region=region,
            latitude=lat,
            longitude=lng,
            event_type="logging",
            severity=severity,
            affected_area_ha=float(raw.get("affected_area_ha", 2.5)),
            confidence=confidence,
            source_id=self.source_name,
            detected_at=detected_at,
            metadata={
                "provider": "synthetic_environmental",
                "incident_category": IncidentCategory.ILLEGAL_LOGGING.value,
                "ingestion": ingestion_meta.model_dump(),
            },
        )


_DEFAULT_RECORDS: list[dict[str, Any]] = [
    {
        "latitude": 46.42,
        "longitude": 25.65,
        "region": "Harghita",
        "source_event_id": "synthetic-harghita-001",
        "confidence": 0.82,
        "severity": "medium",
        "affected_area_ha": 3.1,
    },
]
