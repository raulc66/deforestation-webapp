"""Forest context resolution and spatial association (CLMS enrichment)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.ecosystem.canonical_identity import spatial_key_from_region
from app.core.ecosystem.forest_context import ForestContext, forest_context_from_lookup
from app.modules.analytics.detection_contract import Detection
from app.services.clms_context_provider import CLMSContextProvider

logger = logging.getLogger("forestwatch.forest_context")

_DEFAULT_REFRESH_INTERVAL = timedelta(days=30)


class ForestContextService:
    """Associates CLMS contextual intelligence with observations and detections."""

    def __init__(
        self,
        provider: CLMSContextProvider | None = None,
        *,
        refresh_interval_days: int = 30,
    ) -> None:
        self._provider = provider or CLMSContextProvider()
        self._refresh_interval = timedelta(days=max(1, refresh_interval_days))
        self._last_refresh_at: datetime | None = None

    @property
    def provider(self) -> CLMSContextProvider:
        return self._provider

    def describe_dataset(self) -> dict[str, Any]:
        return self._provider.describe()

    async def refresh_if_stale(self) -> dict[str, Any] | None:
        """Reload CLMS reference data when older than the refresh interval."""
        now = datetime.now(timezone.utc)
        if self._last_refresh_at and (now - self._last_refresh_at) < self._refresh_interval:
            return None
        report = await self._provider.refresh()
        self._last_refresh_at = now
        return report

    def resolve_context(self, latitude: float, longitude: float) -> ForestContext:
        """Deterministic point lookup → ``ForestContext``."""
        lookup = self._provider.lookup(latitude, longitude)
        return forest_context_from_lookup(lookup, latitude=latitude, longitude=longitude)

    def enrich_observation_metadata(
        self,
        metadata: dict[str, Any] | None,
        *,
        latitude: float,
        longitude: float,
    ) -> dict[str, Any]:
        """Attach ``forest_context`` to observation metadata without mutating identity."""
        base = dict(metadata or {})
        ctx = self.resolve_context(latitude, longitude)
        base["forest_context"] = ctx.to_metadata_block()
        return base

    def enrich_detection(self, detection: Detection) -> Detection:
        """Return a Detection with CLMS context in evidence (does not alter score/identity)."""
        evidence = dict(detection.evidence)
        region = evidence.get("region")
        lat = evidence.get("latitude")
        lng = evidence.get("longitude")
        if lat is None or lng is None:
            # Preserve spatial_key semantics — no coordinate invention.
            return detection
        ctx = self.resolve_context(float(lat), float(lng))
        evidence["forest_context"] = ctx.to_metadata_block()
        if region:
            evidence.setdefault("spatial_key", spatial_key_from_region(str(region)))
        return detection.model_copy(update={"evidence": evidence})

    def context_for_region_centroid(
        self,
        region: str,
        centroids: dict[str, tuple[float, float]],
    ) -> ForestContext | None:
        """Associate context using a known region centroid (map/intelligence fallback)."""
        coords = centroids.get(region)
        if not coords:
            return None
        lat, lng = coords
        return self.resolve_context(lat, lng)

    @staticmethod
    def forest_context_from_event_metadata(metadata: dict[str, Any] | None) -> ForestContext | None:
        if not metadata:
            return None
        block = metadata.get("forest_context")
        return ForestContext.from_metadata_block(block)
