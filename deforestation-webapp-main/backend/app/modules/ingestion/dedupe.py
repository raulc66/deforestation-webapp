"""Deterministic deduplication for ingestion-created ForestEvents."""
from __future__ import annotations

from datetime import datetime

from app.models.base import ensure_utc, utcnow
from app.repositories.forest_event_repository import ForestEventRepository


def build_dedupe_key(
    *,
    country: str,
    region: str,
    latitude: float,
    longitude: float,
    detected_at: datetime,
    event_type: str,
) -> str:
    """Stable key from country + region + lat + lng + detected_at + event_type."""
    dt = ensure_utc(detected_at)
    ts = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f"{country.strip()}|{region.strip()}|{latitude:.6f}|{longitude:.6f}|{ts}|{event_type}"
    )


def resolve_detected_at(detected_at: datetime | None) -> datetime:
    if detected_at is None:
        return utcnow()
    return ensure_utc(detected_at)


async def is_duplicate_event(
    repo: ForestEventRepository,
    *,
    country: str,
    region: str,
    latitude: float,
    longitude: float,
    detected_at: datetime,
    event_type: str,
    dedupe_key: str,
) -> bool:
    """Return True when an event with the same dedupe identity already exists."""
    if await repo.col.find_one(
        {"metadata.dedupe_key": dedupe_key},
        projection={"_id": 1},
    ):
        return True

    # Match legacy/seeded rows that predate metadata.dedupe_key storage.
    return (
        await repo.col.find_one(
            {
                "country": country.strip(),
                "region": region.strip(),
                "latitude": latitude,
                "longitude": longitude,
                "detected_at": detected_at,
                "event_type": event_type,
            },
            projection={"_id": 1},
        )
        is not None
    )
