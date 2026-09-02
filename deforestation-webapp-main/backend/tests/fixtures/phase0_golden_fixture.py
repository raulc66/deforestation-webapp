"""Phase 0 frozen seed fixture (WP0.1).

Purpose
-------
Provide a single, deterministic input dataset of **wildfire** forest events that
drives the existing intelligence pipeline across **at least two reconciliation
cycles**, producing a non-trivial mix of *active*, *newly-created*, and
*resolved* intelligence events.

This module is the frozen regression *input* for Phase 0. Later work packages
(WP0.2 capture, WP0.3 determinism harness, and every equivalence test in WP2–WP8)
consume this fixture. It is deliberately pure data: it performs no I/O, imports no
application services, and depends only on the standard library, so it loads
identically in every environment.

**Scope note (WP0.1 only):** this file defines the *fixture* and its design
intent. It does **not** run the pipeline or capture golden outputs — that is
WP0.2. The design-intent constants below document the outcomes the fixture is
engineered to produce; the companion test `tests/test_phase0_fixture.py` proves,
using elementary window arithmetic (not the production engine), that the fixture
is distributed to yield exactly those outcomes.

Determinism
-----------
All timestamps derive from the fixed anchor :data:`REFERENCE_NOW`. There is no
wall-clock coupling and no randomness. :func:`build_wildfire_events` returns a
fresh list of fresh dicts on every call, so consumers may mutate the result
without affecting subsequent loads.

Window model (mirrors ``AnalyticsRepository.regional_baselines``)
-----------------------------------------------------------------
For a reconciliation anchor ``A`` (grouping per ``region``, Romania-only):

  * ``current_events``  = events with ``detected_at >= A - 7d``  (no upper bound)
  * ``baseline_raw``    = events with ``A - 35d <= detected_at < A - 7d``
  * ``baseline_events`` = ``round(baseline_raw / 4)``  (average weekly baseline)

Anomaly candidacy (mirrors ``AnalyticsService`` gates):

  * ``current_events >= 5``            (volume gate)
  * ``deviation_percent >= 50``        (signal gate)

where ``deviation_percent`` is ``100`` when ``baseline_events == 0`` and
``current_events > 0``, otherwise ``(current - baseline) / baseline * 100``.

Regional design (P = whole days *before* :data:`REFERENCE_NOW`; negative P is
after the anchor and lands inside the second cycle's current window)
-------------------------------------------------------------------------------
| Region   | Role                | Cycle 1 (anchor = REFERENCE_NOW) | Cycle 2 (anchor + 7d) |
|----------|---------------------|----------------------------------|-----------------------|
| Suceava  | persistent anomaly  | anomaly (create)                 | anomaly (update)      |
| Bacău    | resolving anomaly   | anomaly (create)                 | absent  → resolved    |
| Cluj     | emerging anomaly    | below signal gate → not anomaly  | anomaly (create)      |
| Harghita | stable control      | below signal gate → not anomaly  | quiet   → not anomaly |

Net effect across the two cycles: one persistent active event (Suceava), one new
active event (Cluj), and one resolved event (Bacău) — the required active/resolved
mix.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Frozen time anchor and cycle schedule
# ---------------------------------------------------------------------------

#: The single injected time anchor for all Phase 0 golden runs (cycle 1).
REFERENCE_NOW: datetime = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

#: Days between successive reconciliation cycles.
CYCLE_INTERVAL_DAYS: int = 7

#: Ordered reconciliation anchors. At least two cycles, per WP0.1.
CYCLE_ANCHORS: tuple[datetime, ...] = (
    REFERENCE_NOW,
    REFERENCE_NOW + timedelta(days=CYCLE_INTERVAL_DAYS),
)

# Window bounds (documented for consumers; identical to the repository).
CURRENT_WINDOW_DAYS: int = 7
BASELINE_HORIZON_DAYS: int = 35

# ---------------------------------------------------------------------------
# Design intent (documentation + fixture self-check oracle, NOT engine output)
# ---------------------------------------------------------------------------

#: Regions the fixture is engineered to flag as anomalies, per cycle index (0-based).
DESIGN_INTENT_ANOMALY_REGIONS: dict[int, frozenset[str]] = {
    0: frozenset({"Suceava", "Bacău"}),
    1: frozenset({"Suceava", "Cluj"}),
}

# ---------------------------------------------------------------------------
# Region geography (approximate centres in Romania)
# ---------------------------------------------------------------------------

_REGION_COORDS: dict[str, tuple[float, float]] = {
    "Suceava":  (47.53, 25.93),
    "Bacău":    (46.57, 26.92),
    "Cluj":     (46.77, 23.60),
    "Harghita": (46.35, 25.80),
}

_FIRMS: str = "NASA FIRMS"
_CSV: str = "CSV"

# ---------------------------------------------------------------------------
# Deterministic event specification
# ---------------------------------------------------------------------------
# Each entry: (region, source, severity, days_before_reference).
#   days_before_reference (P):
#     P  > 0  → detected before REFERENCE_NOW (past)
#     P == 0  → exactly at REFERENCE_NOW
#     P  < 0  → detected after REFERENCE_NOW (inside cycle-2 current window)
#
# Placement is chosen so the window arithmetic above yields the roles documented
# in the module docstring. See tests/test_phase0_fixture.py for the proof.

_CLUJ_BASELINE_P: list[int] = [29, 30, 31, 32, 33, 34] * 2 + [29, 30, 31, 32]  # 16 events
_HARGHITA_BASELINE_P: list[int] = list(range(8, 28))                          # 20 events


def _event_specs() -> list[tuple[str, str, str, int]]:
    specs: list[tuple[str, str, str, int]] = []

    # Suceava — persistent anomaly: current in BOTH cycles + small baseline.
    for p in (-1, -2, -3, -4, -5):
        specs.append(("Suceava", _FIRMS, "high", p))
    for p in (8, 9, 10, 11):
        specs.append(("Suceava", _CSV, "medium", p))

    # Bacău — resolving anomaly: current only in cycle 1 + small baseline.
    for p in (1, 2, 3, 4, 5, 6):
        specs.append(("Bacău", _FIRMS, "high", p))
    for p in (8, 9, 10, 11):
        specs.append(("Bacău", _CSV, "medium", p))

    # Cluj — emerging anomaly: current only in cycle 2; large-but-stale baseline
    # that lands inside cycle 1's baseline window yet falls outside cycle 2's
    # 35-day horizon, so cycle 2 has an empty baseline (deviation = 100%).
    for p in (-1, -2, -3, -4, -5):
        specs.append(("Cluj", _FIRMS, "high", p))
    for p in _CLUJ_BASELINE_P:
        specs.append(("Cluj", _CSV, "medium", p))

    # Harghita — stable control: current present in cycle 1 but matched by a
    # proportional baseline (deviation = 0%); quiet in cycle 2.
    for p in (1, 2, 3, 4, 5):
        specs.append(("Harghita", _CSV, "medium", p))
    for p in _HARGHITA_BASELINE_P:
        specs.append(("Harghita", _CSV, "medium", p))

    return specs


#: Total number of events in the fixture (stable invariant).
EVENT_COUNT: int = len(_event_specs())

_SEVERITY_CONFIDENCE: dict[str, float] = {
    "critical": 0.95,
    "high": 0.85,
    "medium": 0.70,
    "low": 0.55,
}


def _slug(region: str) -> str:
    return (
        region.lower()
        .replace("ă", "a")
        .replace("â", "a")
        .replace("î", "i")
        .replace("ș", "s")
        .replace("ț", "t")
        .replace(" ", "-")
    )


def build_wildfire_events() -> list[dict]:
    """Return the frozen wildfire event dataset as a list of fresh dicts.

    The output is byte-for-byte identical on every call and safe to mutate:
    a new list of new dicts is constructed each time.
    """
    events: list[dict] = []

    for idx, (region, source, severity, days_before) in enumerate(_event_specs()):
        lat, lng = _REGION_COORDS[region]
        # Deterministic sub-degree jitter so no two events share coordinates.
        lat_jitter = round((idx % 9) * 0.004, 5)
        lng_jitter = round((idx % 7) * 0.005, 5)
        ev_lat = round(lat + lat_jitter, 5)
        ev_lng = round(lng + lng_jitter, 5)

        # Sub-day minute offset keeps timestamps unique without crossing any
        # window boundary (interior events stay interior; post-anchor events
        # stay after the anchor).
        detected_at = REFERENCE_NOW - timedelta(days=days_before, minutes=idx)
        confidence = _SEVERITY_CONFIDENCE[severity]
        source_event_id = f"phase0-{_slug(region)}-{idx:03d}"

        events.append(
            {
                "title": f"Phase 0 golden fixture — {region} event {idx + 1}",
                "country": "Romania",
                "region": region,
                "latitude": ev_lat,
                "longitude": ev_lng,
                "event_type": "wildfire",
                "severity": severity,
                "affected_area_ha": round(100.0 + idx, 1),
                "confidence": confidence,
                "detected_at": detected_at,
                "status": "open",
                "land_cover_type": "forest",
                "metadata": {
                    "phase0_golden_fixture": True,
                    "is_romania": True,
                    "ingestion": {
                        "source": source,
                        "source_event_id": source_event_id,
                        "is_romania": True,
                        "confidence": confidence,
                        "severity": severity,
                    },
                },
            }
        )

    return events


def cycle_anchor(cycle_index: int) -> datetime:
    """Return the reconciliation anchor for a 0-based ``cycle_index``."""
    return CYCLE_ANCHORS[cycle_index]
