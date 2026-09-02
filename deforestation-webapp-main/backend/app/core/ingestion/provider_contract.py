"""Ingestion provider contract (Package C).

Mirrors the ``WeatherProvider`` pattern: a small ABC that scheduled and manual
ingestion paths depend on, while concrete providers (FIRMS, future European
sources) supply fetch/normalize/run behaviour.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models.forest_event import ForestEventCreate
from app.repositories.forest_event_repository import ForestEventRepository
from app.services.forest_event_service import ForestEventService


class IngestionProvider(ABC):
    """Contract for environmental observation ingestion providers."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable source label (e.g. ``NASA FIRMS``)."""

    @property
    def supported_incident_categories(self) -> tuple[str, ...]:
        """Categories this provider can populate; override in subclasses."""
        return ()

    @abstractmethod
    async def fetch(self) -> list[dict[str, Any]]:
        """Retrieve raw provider records."""

    @abstractmethod
    def normalize(self, raw: dict[str, Any]) -> ForestEventCreate:
        """Map one raw record to a ``ForestEventCreate``."""

    @property
    def provider_id(self) -> str:
        """Stable machine identifier for telemetry and health tracking."""
        return self.source_name.lower().replace(" ", ".")

    def describe(self) -> dict[str, Any]:
        """Return minimal source descriptor metadata; override in subclasses."""
        return {
            "source": self.source_name,
            "provider_id": self.provider_id,
        }

    async def run(
        self,
        events_service: ForestEventService,
        events_repo: ForestEventRepository,
        source_id: str | None = None,
    ) -> dict[str, int]:
        """Default fetch → normalize → persist loop."""
        from app.modules.ingestion.persist import persist_import_event

        raw_records = await self.fetch()
        created = skipped = errors = 0
        seen_keys: set[str] = set()

        for raw in raw_records:
            try:
                payload = self.normalize(raw)
                if source_id:
                    payload = payload.model_copy(update={"source_id": source_id})
                result = await persist_import_event(
                    events_service,
                    events_repo,
                    payload,
                    seen_keys=seen_keys,
                )
                if result == "created":
                    created += 1
                else:
                    skipped += 1
            except Exception:
                errors += 1

        return {
            "total": len(raw_records),
            "created": created,
            "skipped": skipped,
            "errors": errors,
        }
