"""IntelligenceEventsService — persistence business logic for intelligence events.

Responsibilities:
  - Upsert IntelligenceEvents from detected anomalies (create or update).
  - Compute and persist escalation_level during every create/update.
  - Compute and persist trend (new/improving/stable/worsening) during every
    create/update by comparing incoming score against the stored score.
  - Compute and persist priority_score to rank events by operational importance.
  - Resolve stale active events that were not present in the latest detection run.
  - Return grouped active/resolved event lists (active sorted by priority DESC)
    and summary counts with highest-priority metadata.

No anomaly-detection logic lives here; that stays in analytics_service.py.
"""
from datetime import datetime

from app.core.ecosystem.incident_categories import normalize_incident_category, resolve_incident_category

from .intelligence_events_repository import IntelligenceEventsRepository

# ---------------------------------------------------------------------------
# Weight tables
# ---------------------------------------------------------------------------

_SEVERITY_WEIGHT: dict[str, float] = {
    "low": 0.25,
    "medium": 0.50,
    "high": 0.75,
    "critical": 1.00,
}

_ESCALATION_WEIGHT: dict[str, float] = {
    "normal": 0.25,
    "persistent": 0.60,
    "critical": 1.00,
}

_TREND_WEIGHT: dict[str, float] = {
    "improving": 0.20,
    "stable": 0.50,
    "worsening": 1.00,
    "new": 0.60,
}


# ---------------------------------------------------------------------------
# Escalation logic — pure function, no I/O
# ---------------------------------------------------------------------------

def _compute_escalation_level(detection_count: int, severity: str) -> str:
    """Determine the escalation level for an IntelligenceEvent.

    Rules (evaluated in priority order):

        B: detection_count >= 7              → "critical"
        A: detection_count >= 3              → "persistent"
        C: severity == "critical"            → "persistent"
                                               (floor for critical-severity events)
        otherwise                            → "normal"

    Rule C means a critical-severity event can never be below "persistent",
    even on its first detection.  Rule B supersedes Rule C — a critical-
    severity event with >= 7 detections escalates to "critical" level.
    """
    if detection_count >= 7:
        return "critical"
    if detection_count >= 3 or severity == "critical":
        return "persistent"
    return "normal"


# ---------------------------------------------------------------------------
# Trend logic — pure function, no I/O
# ---------------------------------------------------------------------------

def _compute_trend(previous_score: float | None, current_score: float) -> str:
    """Classify how an anomaly score is moving between detections.

    Rules:
        previous_score is None          → "new"     (first observation)
        current - previous >  0.05      → "worsening"
        current - previous < -0.05      → "improving"
        otherwise (|difference| <= 0.05)→ "stable"

    The ±0.05 threshold treats small floating-point noise as unchanged.
    """
    if previous_score is None:
        return "new"
    difference = current_score - previous_score
    if difference > 0.05:
        return "worsening"
    if difference < -0.05:
        return "improving"
    return "stable"


# ---------------------------------------------------------------------------
# Priority scoring — pure function, no I/O
# ---------------------------------------------------------------------------

def _compute_priority_score(
    severity: str,
    escalation_level: str,
    trend: str,
    current_score: float,
) -> float:
    """Rank an IntelligenceEvent by operational importance (0.0–1.0).

    Formula:
        0.40 × severity_weight
      + 0.30 × escalation_weight
      + 0.20 × trend_weight
      + 0.10 × current_score

    Unknown keys fall back to 0.0 so legacy or future values degrade
    gracefully rather than raising an exception.

    Result is rounded to 4 decimal places for stable comparisons.
    """
    s = _SEVERITY_WEIGHT.get(severity, 0.0)
    e = _ESCALATION_WEIGHT.get(escalation_level, 0.0)
    t = _TREND_WEIGHT.get(trend, 0.0)
    raw = 0.40 * s + 0.30 * e + 0.20 * t + 0.10 * current_score
    return round(raw, 4)


def _normalize_event(event: dict) -> dict:
    """Ensure legacy records expose ``incident_category`` (default: wildfire)."""
    out = dict(event)
    out["incident_category"] = normalize_incident_category(out.get("incident_category"))
    return out


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class IntelligenceEventsService:
    def __init__(self, repo: IntelligenceEventsRepository) -> None:
        self.repo = repo

    # ------------------------------------------------------------------ #
    # Core reconciliation
    # ------------------------------------------------------------------ #

    async def reconcile(self, anomalies: list[dict], now: datetime) -> None:
        """Create, update, or resolve events based on the current anomaly list.

        Algorithm (single batch, avoids N+1 queries):
          1. Fetch all currently-active events once.
          2. Build a lookup dict keyed by (event_type, region).
          3. For each detected anomaly:
               - No existing event  → create a new one; initialize
                                      escalation_level, trend, previous_score,
                                      and priority_score.
               - Existing event     → increment detection_count; recalculate
                                      escalation_level, trend, and priority_score;
                                      store previous_score.
          4. Any active event whose (event_type, region) key is absent from
             the current detection set is marked resolved.
        """
        active_events = await self.repo.find_active()
        active_by_key: dict[tuple[str, str], dict] = {
            (e["event_type"], e["region"]): e for e in active_events
        }
        detected_keys: set[tuple[str, str]] = set()

        for anomaly in anomalies:
            key = ("anomaly", anomaly["region"])
            detected_keys.add(key)
            existing = active_by_key.get(key)

            event_metadata = {
                "baseline_events": anomaly["baseline_events"],
                "current_events": anomaly["current_events"],
                "deviation_percent": anomaly["deviation_percent"],
            }
            incident_category = resolve_incident_category(anomaly)

            if existing is None:
                escalation = _compute_escalation_level(1, anomaly["severity"])
                await self.repo.create(
                    {
                        "event_type": "anomaly",
                        "incident_category": incident_category,
                        "region": anomaly["region"],
                        "status": "active",
                        "severity": anomaly["severity"],
                        "escalation_level": escalation,
                        "previous_score": None,
                        "trend": "new",
                        "priority_score": _compute_priority_score(
                            anomaly["severity"],
                            escalation,
                            "new",
                            anomaly["anomaly_score"],
                        ),
                        "first_detected_at": now,
                        "last_detected_at": now,
                        "detection_count": 1,
                        "current_score": anomaly["anomaly_score"],
                        "metadata": event_metadata,
                    }
                )
            else:
                new_count = existing["detection_count"] + 1
                previous_score = existing["current_score"]
                incoming_score = anomaly["anomaly_score"]
                escalation = _compute_escalation_level(new_count, anomaly["severity"])
                trend = _compute_trend(previous_score, incoming_score)
                await self.repo.update(
                    existing["id"],
                    {
                        "last_detected_at": now,
                        "detection_count": new_count,
                        "current_score": incoming_score,
                        "severity": anomaly["severity"],
                        "incident_category": incident_category,
                        "escalation_level": escalation,
                        "previous_score": previous_score,
                        "trend": trend,
                        "priority_score": _compute_priority_score(
                            anomaly["severity"],
                            escalation,
                            trend,
                            incoming_score,
                        ),
                        "metadata": event_metadata,
                    },
                )

        # Resolve events that were active but absent from this detection run.
        for key, event in active_by_key.items():
            if key not in detected_keys:
                await self.repo.resolve(event["id"], now)

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    async def get_events(self) -> dict:
        """Return all events grouped by status.

        Active events are sorted by priority_score DESC, then last_detected_at DESC
        so the most operationally important events appear first.

        Resolved events retain their original sort order (most recently resolved
        first) as returned by the repository.
        """
        all_events = await self.repo.find_all()
        active = sorted(
            [_normalize_event(e) for e in all_events if e["status"] == "active"],
            key=lambda e: (
                -e.get("priority_score", 0.0),
                -(
                    e["last_detected_at"].timestamp()
                    if e.get("last_detected_at") is not None
                    else 0.0
                ),
            ),
        )
        resolved = [_normalize_event(e) for e in all_events if e["status"] == "resolved"]
        return {"active": active, "resolved": resolved}

    async def get_events_summary(self) -> dict:
        """Return aggregate counts by status, escalation level, trend, and priority.

        ``persistent``, ``critical``, ``worsening``, ``stable``, ``improving``,
        ``highest_priority_score``, and ``highest_priority_region`` all reflect
        only *active* events.

        Response keys:
            active                  — count of active events
            resolved                — count of resolved events
            persistent              — active events with escalation_level="persistent"
            critical                — active events with escalation_level="critical"
            worsening               — active events with trend="worsening"
            stable                  — active events with trend="stable"
            improving               — active events with trend="improving"
            highest_priority_score  — float | None
            highest_priority_region — str | None
        """
        all_events = await self.repo.find_all()
        active = [_normalize_event(e) for e in all_events if e["status"] == "active"]
        resolved = [_normalize_event(e) for e in all_events if e["status"] == "resolved"]

        if active:
            top = max(active, key=lambda e: e.get("priority_score", 0.0))
            highest_priority_score: float | None = top.get("priority_score", 0.0)
            highest_priority_region: str | None = top.get("region")
        else:
            highest_priority_score = None
            highest_priority_region = None

        return {
            "active": len(active),
            "resolved": len(resolved),
            "persistent": sum(
                1 for e in active if e.get("escalation_level") == "persistent"
            ),
            "critical": sum(
                1 for e in active if e.get("escalation_level") == "critical"
            ),
            "worsening": sum(
                1 for e in active if e.get("trend") == "worsening"
            ),
            "stable": sum(
                1 for e in active if e.get("trend") == "stable"
            ),
            "improving": sum(
                1 for e in active if e.get("trend") == "improving"
            ),
            "highest_priority_score": highest_priority_score,
            "highest_priority_region": highest_priority_region,
        }
