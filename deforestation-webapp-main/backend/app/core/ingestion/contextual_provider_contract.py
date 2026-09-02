"""Contextual environmental dataset provider contract.

Static or slow-moving reference datasets (CLMS land cover, forest attributes)
are not real-time event streams.  They use a separate contract from
:class:`~app.core.ingestion.provider_contract.IngestionProvider`, which targets
observation persistence into ``ForestEvent`` records.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ContextualDatasetProvider(ABC):
    """Contract for authoritative contextual/reference environmental datasets."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable source label."""

    @property
    @abstractmethod
    def dataset_id(self) -> str:
        """Stable dataset identifier (e.g. ``clms.corine_land_cover``)."""

    @abstractmethod
    def describe(self) -> dict[str, Any]:
        """Return dataset metadata (coverage, version, license, provenance)."""

    @abstractmethod
    async def refresh(self) -> dict[str, Any]:
        """Load or reload the contextual dataset; return refresh report."""

    @abstractmethod
    def lookup(self, latitude: float, longitude: float) -> dict[str, Any]:
        """Return normalized contextual attributes for a WGS-84 coordinate."""
