"""Detection context enrichment — CLMS → Detection evidence path."""
from __future__ import annotations

from typing import Any

from app.core.ecosystem.forest_context import ForestContext
from app.services.forest_context_service import ForestContextService

from .detection_contract import Detection


def enrich_detection_with_forest_context(
    detection: Detection,
    *,
    context_svc: ForestContextService | None = None,
) -> Detection:
    """Attach CLMS forest context to a Detection when coordinates are available."""
    svc = context_svc or ForestContextService()
    return svc.enrich_detection(detection)


def forest_context_for_map_payload(
    *,
    metadata: dict[str, Any] | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    context_svc: ForestContextService | None = None,
) -> dict[str, Any] | None:
    """Resolve map-friendly forest context summary."""
    if metadata:
        ctx = ForestContext.from_metadata_block(metadata.get("forest_context"))
        if ctx:
            return ctx.to_map_summary()

    if latitude is not None and longitude is not None:
        svc = context_svc or ForestContextService()
        return svc.resolve_context(latitude, longitude).to_map_summary()

    return None
