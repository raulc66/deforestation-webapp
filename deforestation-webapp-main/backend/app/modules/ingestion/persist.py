"""Shared ingest persistence helpers (dedupe + create)."""
from __future__ import annotations

from typing import Literal

from app.models.forest_event import ForestEventCreate
from app.repositories.forest_event_repository import ForestEventRepository
from app.services.forest_event_service import ForestEventService

from .dedupe import build_dedupe_key, is_duplicate_event, resolve_detected_at

PersistResult = Literal["created", "skipped"]


async def persist_import_event(
    events_service: ForestEventService,
    events_repo: ForestEventRepository,
    payload: ForestEventCreate,
    *,
    seen_keys: set[str],
) -> PersistResult:
    """Insert a ForestEvent unless a duplicate identity already exists."""
    detected_at = resolve_detected_at(payload.detected_at)
    dedupe_key = build_dedupe_key(
        country=payload.country,
        region=payload.region,
        latitude=payload.latitude,
        longitude=payload.longitude,
        detected_at=detected_at,
        event_type=payload.event_type,
    )

    if dedupe_key in seen_keys or await is_duplicate_event(
        events_repo,
        country=payload.country,
        region=payload.region,
        latitude=payload.latitude,
        longitude=payload.longitude,
        detected_at=detected_at,
        event_type=payload.event_type,
        dedupe_key=dedupe_key,
    ):
        seen_keys.add(dedupe_key)
        return "skipped"

    seen_keys.add(dedupe_key)
    enriched = payload.model_copy(
        update={
            "detected_at": detected_at,
            "metadata": {
                **payload.metadata,
                "dedupe_key": dedupe_key,
            },
        }
    )
    await events_service.create_event(enriched)
    return "created"
