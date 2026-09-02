"""Romania intelligence seed — deterministic ForestEvent dataset for analytics.

Purpose
-------
The default demo seed in ``ForestEventService.seed_demo_data`` inserts global
events without ``metadata.ingestion.is_romania``, so the Romania-aware
analytics pipeline (regional baselines, anomaly detection, temporal trends,
intelligence events, source reliability) always returns empty/zero results in a
fresh environment.

This module inserts a second, *disjoint* batch of events that:

  * carry ``metadata.ingestion.is_romania = True`` so every Romania analytics
    query picks them up;
  * are spread across three Romanian regions in patterns that *deterministically*
    trigger anomaly detection for two of them;
  * are distributed across the "current" (last 7 days) and "baseline" (8–34
    days ago) windows so the full baseline → deviation → anomaly → intelligence
    event → escalation → trend → priority pipeline can be exercised end-to-end.

Anomaly design (verified against analytics_service.py thresholds)
-----------------------------------------------------------------
Region      current  baseline_raw  baseline_events  deviation  score   severity
----------  -------  ------------  ---------------  ---------  ------  --------
Suceava        10         8               2            400 %    0.68    high    ← anomaly
Bacău           6         8               2            200 %    0.648   high    ← anomaly
Harghita        5        20               5              0 %    —       —       ← stable

Idempotency
-----------
The seed is a no-op when any event with the ``romania_intelligence_seed`` flag
already exists, so repeated startups are safe.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from app.core.ingestion.ingestion_metadata import build_ingestion_metadata
from app.models.forest_event import ForestEvent
from app.models.geo import GeoJSONPoint
from app.repositories.forest_event_repository import ForestEventRepository
from app.services.land_cover_service import classify as classify_land_cover

logger = logging.getLogger("forestwatch.seed.romania")

# Flag stored in every seeded event's metadata for idempotency checks.
SEED_FLAG: str = "romania_intelligence_seed"

# Source name constants — must match the strings used by ingestion providers
# so that ``by_source()`` analytics aggregation groups them correctly.
_FIRMS: str = "NASA FIRMS"
_CSV: str = "CSV"

# Approximate forest-belt coordinates for each seeded region (Romania).
# City-centroid placement caused urban land-cover classification and red
# markers on roads; forest coordinates keep seed events geospatially valid.
_REGION_COORDS: dict[str, tuple[float, float]] = {
    "Suceava":  (47.68, 25.72),
    "Bacău":    (46.62, 26.55),
    "Harghita": (46.42, 25.65),
}


# ---------------------------------------------------------------------------
# Event spec builder
# ---------------------------------------------------------------------------

def _build_event_specs() -> list[tuple[str, str, float, str, float, int]]:
    """Return the deterministic list of event templates.

    Each tuple: ``(region, source, confidence, severity, area_ha, days_ago)``

    ``days_ago`` placement rules:
      * 0          → within last 24 h  (counted in both "last_24h" and "last_7d")
      * 1 – 6      → within last 7 days ("current" window for baselines)
      * >= 8       → older than 7 days  ("baseline" window for baselines)

    Day 7 is intentionally skipped to avoid boundary ambiguity.
    """
    specs: list[tuple[str, str, float, str, float, int]] = []

    # ── Suceava: 10 current (5 in last 24 h) + 8 baseline ─────────────────
    # Ensures: current=10, baseline_events=2, deviation=400%, score≈0.68
    for i in range(5):
        specs.append(("Suceava", _FIRMS, round(0.91 + i * 0.005, 3), "critical", 210.0 + i * 5, 0))
    for i in range(5):
        specs.append(("Suceava", _FIRMS, round(0.85 + i * 0.005, 3), "high", 150.0 + i * 5, i + 1))
    for i in range(8):
        specs.append(("Suceava", _CSV, round(0.72 + i * 0.003, 3), "medium", 80.0 + i * 3, 8 + i * 3))

    # ── Bacău: 6 current + 8 baseline ─────────────────────────────────────
    # Ensures: current=6, baseline_events=2, deviation=200%, score≈0.648
    for i in range(6):
        specs.append(("Bacău", _FIRMS, round(0.88 + i * 0.004, 3), "high", 130.0 + i * 10, i))
    for i in range(8):
        specs.append(("Bacău", _CSV, round(0.68 + i * 0.003, 3), "medium", 60.0 + i * 3, 8 + i * 3))

    # ── Harghita: 5 current + 20 baseline (stable — NOT an anomaly) ────────
    # Ensures: current=5, baseline_events=5, deviation=0% (<50% threshold)
    for i in range(5):
        specs.append(("Harghita", _CSV, round(0.75 + i * 0.002, 3), "medium", 40.0 + i * 2, i))
    for i in range(20):
        specs.append(("Harghita", _CSV, round(0.71 + i * 0.001, 3), "medium", 30.0 + i, 8 + i))

    return specs


# ---------------------------------------------------------------------------
# Public seed function
# ---------------------------------------------------------------------------

async def seed_romania_intelligence(
    events_repo: ForestEventRepository,
    source_id_pool: list[str],
    now: datetime | None = None,
) -> int:
    """Insert Romania intelligence seed events if none exist yet.

    Parameters
    ----------
    events_repo:
        Live ``ForestEventRepository`` instance (from the startup DI graph).
    source_id_pool:
        List of valid DataSource ObjectId strings.  FIRMS events are assigned
        ``source_id_pool[0]``; CSV events use ``source_id_pool[-1]``.  The
        ``metadata.ingestion.source`` string is always set correctly regardless
        of which pool entry is used, so source-level analytics aggregations
        (which group by the string, not the FK) work as expected.
    now:
        UTC anchor timestamp.  Defaults to ``datetime.now(timezone.utc)``.
        Passing an explicit value makes tests fully deterministic.

    Returns
    -------
    int
        Number of events inserted; ``0`` when the seed was already present.
    """
    if not source_id_pool:
        raise RuntimeError("seed_romania_intelligence requires a non-empty source_id_pool")

    # Idempotency guard — skip if any seed event already exists.
    existing = await events_repo.col.find_one({f"metadata.{SEED_FLAG}": True})
    if existing:
        logger.debug("Romania intelligence seed already present — skipping")
        return 0

    if now is None:
        now = datetime.now(timezone.utc)

    firms_source_id = source_id_pool[0]
    csv_source_id = source_id_pool[-1]
    source_id_map: dict[str, str] = {_FIRMS: firms_source_id, _CSV: csv_source_id}

    specs = _build_event_specs()
    inserted = 0

    for idx, (region, source, confidence, severity, area_ha, days_ago) in enumerate(specs):
        lat, lng = _REGION_COORDS[region]
        # Small forest-biased jitter — keeps events distinct without drifting to urban cores.
        lat_jitter = (idx % 5) * 0.002
        lng_jitter = (idx % 4) * 0.002

        detected_at = now - timedelta(days=days_ago, hours=(idx % 6))

        ingestion_meta = build_ingestion_metadata(
            source=source,
            source_event_id=f"ro-seed-{source.lower().replace(' ', '-')}-{idx:03d}",
            is_romania=True,
            confidence=confidence,
            severity=severity,
            ingestion_timestamp=now,
        )

        metadata: dict = {
            SEED_FLAG: True,
            "is_romania": True,
            "ingestion": ingestion_meta.model_dump(),
        }

        ev_lat = round(lat + lat_jitter, 5)
        ev_lon = round(lng + lng_jitter, 5)
        event = ForestEvent(
            title=f"Romania intelligence seed — {region} event {idx + 1}",
            country="Romania",
            region=region,
            latitude=ev_lat,
            longitude=ev_lon,
            event_type="wildfire",
            severity=severity,
            affected_area_ha=round(area_ha, 1),
            confidence=confidence,
            source_id=source_id_map[source],
            detected_at=detected_at,
            status="open",
            land_cover_type=classify_land_cover(ev_lat, ev_lon),
            metadata=metadata,
        )
        event.location = GeoJSONPoint.from_lat_lng(event.latitude, event.longitude)

        await events_repo.insert(event)
        inserted += 1

    logger.info(
        "Romania intelligence seed: inserted %d events across %d regions",
        inserted,
        len(_REGION_COORDS),
    )
    return inserted
