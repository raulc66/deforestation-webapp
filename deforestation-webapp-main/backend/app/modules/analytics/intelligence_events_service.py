"""IntelligenceEventsService — persistence business logic for intelligence events.

Responsibilities:
  - Reconcile IntelligenceEvents from canonical Detection envelopes (WP3).
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
from app.core.ecosystem.intelligence_event_defaults import (
    DEFAULT_SIGNAL_TYPE,
    DERIVED_ANOMALY_EVENT_TYPE,
)

from .detection_adapters import detection_from_anomaly_dict
from .detection_contract import Detection
from .intelligence_events_repository import IntelligenceEventsRepository
from .reconciliation import (
    ReconciliationChangeSet,
    ReconciliationTransition,
    dedupe_detections,
    identity_key_from_detection,
    identity_key_from_event,
    metadata_from_detection,
    region_from_detection,
)

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


def _normalize_event(event: dict, *, include_provenance: bool = False) -> dict:
    """Ensure legacy records expose ``incident_category`` (default: wildfire).

    Canonical fields ``spatial_key`` and ``signal_type`` are persisted for WP3
    identity but omitted from the read model so Phase 0 oracle snapshots stay
    byte-identical.  Provenance in metadata is stripped unless explicitly enabled.
    """
    out = dict(event)
    out["incident_category"] = normalize_incident_category(out.get("incident_category"))
    out.pop("spatial_key", None)
    out.pop("signal_type", None)
    metadata = dict(out.get("metadata") or {})
    if not include_provenance and "provenance" in metadata:
        metadata = {k: v for k, v in metadata.items() if k != "provenance"}
        out["metadata"] = metadata
    return out


def _build_create_payload(
    detection: Detection,
    now: datetime,
    *,
    include_provenance: bool = False,
    geographic_scope: str | None = None,
) -> dict:
    region = region_from_detection(detection)
    escalation = _compute_escalation_level(1, detection.severity)
    return {
        "event_type": DERIVED_ANOMALY_EVENT_TYPE,
        "incident_category": detection.incident_category,
        "spatial_key": detection.spatial_key,
        "signal_type": detection.signal_type or DEFAULT_SIGNAL_TYPE,
        "region": region,
        "status": "active",
        "severity": detection.severity,
        "escalation_level": escalation,
        "previous_score": None,
        "trend": "new",
        "priority_score": _compute_priority_score(
            detection.severity,
            escalation,
            "new",
            detection.score,
        ),
        "first_detected_at": now,
        "last_detected_at": now,
        "detection_count": 1,
        "current_score": detection.score,
        "metadata": metadata_from_detection(
            detection,
            include_provenance=include_provenance,
            geographic_scope=geographic_scope,
        ),
    }


def _build_update_payload(
    existing: dict,
    detection: Detection,
    now: datetime,
    *,
    include_provenance: bool = False,
    geographic_scope: str | None = None,
) -> dict:
    new_count = existing["detection_count"] + 1
    previous_score = existing["current_score"]
    escalation = _compute_escalation_level(new_count, detection.severity)
    trend = _compute_trend(previous_score, detection.score)
    return {
        "last_detected_at": now,
        "detection_count": new_count,
        "current_score": detection.score,
        "severity": detection.severity,
        "incident_category": detection.incident_category,
        "spatial_key": detection.spatial_key,
        "signal_type": detection.signal_type or DEFAULT_SIGNAL_TYPE,
        "region": region_from_detection(detection),
        "escalation_level": escalation,
        "previous_score": previous_score,
        "trend": trend,
        "priority_score": _compute_priority_score(
            detection.severity,
            escalation,
            trend,
            detection.score,
        ),
        "metadata": metadata_from_detection(
            detection,
            include_provenance=include_provenance,
            geographic_scope=geographic_scope,
        ),
    }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class IntelligenceEventsService:
    def __init__(
        self,
        repo: IntelligenceEventsRepository,
        *,
        include_provenance: bool = False,
        geographic_scope: str | None = None,
    ) -> None:
        self.repo = repo
        self._include_provenance = include_provenance
        self._geographic_scope = geographic_scope

    # ------------------------------------------------------------------ #
    # Core reconciliation
    # ------------------------------------------------------------------ #

    async def reconcile_detections(
        self,
        detections: list[Detection],
        now: datetime,
    ) -> ReconciliationChangeSet:
        """Create, update, or resolve events from canonical Detection envelopes.

        Identity is ``(incident_category, spatial_key)``. Legacy active events
        without ``spatial_key`` resolve identity via ``region``.
        """
        change_set = ReconciliationChangeSet()
        active_events = await self.repo.find_active()
        active_by_key: dict[tuple[str, str], dict] = {
            identity_key_from_event(event): event for event in active_events
        }
        detected_keys: set[tuple[str, str]] = set()

        for detection in dedupe_detections(detections):
            key = identity_key_from_detection(detection)
            detected_keys.add(key)
            existing = active_by_key.get(key)
            region = region_from_detection(detection)

            if existing is None:
                created = await self.repo.create(
                    _build_create_payload(
                        detection,
                        now,
                        include_provenance=self._include_provenance,
                        geographic_scope=self._geographic_scope,
                    )
                )
                change_set.created.append(
                    ReconciliationTransition(
                        action="created",
                        incident_category=detection.incident_category,
                        spatial_key=detection.spatial_key,
                        region=region,
                        event_id=created.get("id"),
                    )
                )
            else:
                await self.repo.update(
                    existing["id"],
                    _build_update_payload(
                        existing,
                        detection,
                        now,
                        include_provenance=self._include_provenance,
                        geographic_scope=self._geographic_scope,
                    ),
                )
                change_set.updated.append(
                    ReconciliationTransition(
                        action="updated",
                        incident_category=detection.incident_category,
                        spatial_key=detection.spatial_key,
                        region=region,
                        event_id=existing["id"],
                    )
                )

        stale_keys = sorted(
            (key for key in active_by_key if key not in detected_keys),
            key=lambda item: (item[0], item[1]),
        )
        for key in stale_keys:
            event = active_by_key[key]
            await self.repo.resolve(event["id"], now)
            change_set.resolved.append(
                ReconciliationTransition(
                    action="resolved",
                    incident_category=key[0],
                    spatial_key=key[1],
                    region=str(event.get("region") or key[1]),
                    event_id=event["id"],
                )
            )

        return change_set

    async def reconcile(
        self,
        anomalies: list[dict],
        now: datetime,
    ) -> ReconciliationChangeSet:
        """Legacy entry point — converts anomaly dicts to Detections (WP3 compat)."""
        detections = [
            detection_from_anomaly_dict(
                anomaly,
                detected_at=now,
                incident_category=resolve_incident_category(anomaly),
            )
            for anomaly in anomalies
        ]
        return await self.reconcile_detections(detections, now)

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
            [
                _normalize_event(e, include_provenance=self._include_provenance)
                for e in all_events
                if e["status"] == "active"
            ],
            key=lambda e: (
                -e.get("priority_score", 0.0),
                -(
                    e["last_detected_at"].timestamp()
                    if e.get("last_detected_at") is not None
                    else 0.0
                ),
            ),
        )
        resolved = [
            _normalize_event(e, include_provenance=self._include_provenance)
            for e in all_events
            if e["status"] == "resolved"
        ]
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
        active = [
            _normalize_event(e, include_provenance=self._include_provenance)
            for e in all_events
            if e["status"] == "active"
        ]
        resolved = [
            _normalize_event(e, include_provenance=self._include_provenance)
            for e in all_events
            if e["status"] == "resolved"
        ]

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
