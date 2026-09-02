"""Detection-driven reconciliation contracts (WP3).

Reconciliation keys active intelligence events by canonical identity
``(incident_category, spatial_key)`` and produces deterministic change-sets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.ecosystem.canonical_identity import (
    region_from_spatial_key,
    spatial_key_from_region,
)
from app.core.ecosystem.incident_categories import normalize_incident_category

from .detection_contract import Detection


@dataclass(frozen=True)
class ReconciliationTransition:
    """One create, update, or resolve action from a reconciliation cycle."""

    action: str
    incident_category: str
    spatial_key: str
    region: str
    event_id: str | None = None


@dataclass
class ReconciliationChangeSet:
    """Deterministic reconciliation output for one cycle."""

    created: list[ReconciliationTransition] = field(default_factory=list)
    updated: list[ReconciliationTransition] = field(default_factory=list)
    resolved: list[ReconciliationTransition] = field(default_factory=list)

    def as_dict(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "created": [t.__dict__ for t in self.created],
            "updated": [t.__dict__ for t in self.updated],
            "resolved": [t.__dict__ for t in self.resolved],
        }


def identity_key_from_event(event: dict[str, Any]) -> tuple[str, str]:
    """Canonical lookup key for a persisted or in-flight intelligence event."""
    category = normalize_incident_category(event.get("incident_category"))
    spatial_key = event.get("spatial_key")
    if not spatial_key:
        region = event.get("region")
        if not region:
            raise ValueError("event must carry spatial_key or region")
        spatial_key = spatial_key_from_region(str(region))
    return (category, str(spatial_key))


def identity_key_from_detection(detection: Detection) -> tuple[str, str]:
    """Canonical lookup key for a Detection envelope."""
    return detection.identity.as_key_tuple()


def region_from_detection(detection: Detection) -> str:
    """Resolve legacy ``region`` label from a Detection."""
    region = detection.evidence.get("region")
    if region:
        return str(region)
    return region_from_spatial_key(detection.spatial_key)


def dedupe_detections(detections: list[Detection]) -> list[Detection]:
    """Collapse duplicate identities, retaining the highest score."""
    best: dict[tuple[str, str], Detection] = {}
    for detection in detections:
        key = identity_key_from_detection(detection)
        existing = best.get(key)
        if existing is None or detection.score > existing.score:
            best[key] = detection
    return sorted(
        best.values(),
        key=lambda item: (-item.score, item.spatial_key, item.incident_category),
    )


def metadata_from_detection(
    detection: Detection,
    *,
    include_provenance: bool = False,
    geographic_scope: str | None = None,
) -> dict[str, Any]:
    """Extract persisted evidence metadata from a Detection."""
    from .provenance_persistence import provenance_from_detection_evidence

    evidence = detection.evidence
    meta: dict[str, Any] = {
        "baseline_events": int(evidence["baseline_events"]),
        "current_events": int(evidence["current_events"]),
        "deviation_percent": float(evidence["deviation_percent"]),
    }
    for key in (
        "pollutant",
        "unit",
        "station_id",
        "station_name",
        "latitude",
        "longitude",
        "country",
        "hazard_type",
    ):
        if key in evidence and evidence[key] is not None:
            meta[key] = evidence[key]

    if include_provenance:
        provenance = provenance_from_detection_evidence(
            evidence,
            geographic_scope=geographic_scope,
            detected_at=detection.detected_at,
        )
        if provenance:
            meta["provenance"] = provenance

    return meta


# ------------------------------------------------------------------ #
# WP6.2 / WP6.3 — production reconciliation command boundary (ADR-007)
# ------------------------------------------------------------------ #

PRODUCTION_RECONCILIATION_OWNERS: frozenset[str] = frozenset({"scheduler"})
"""Runtime components permitted to invoke persistent reconciliation in production."""

EXPLICIT_HTTP_RECONCILE_COMMAND: bool = False
"""No authenticated HTTP reconcile command is exposed; scheduler ownership suffices."""

RECONCILIATION_COMMAND_CHAIN: tuple[str, ...] = (
    "SchedulerService._run_cycle",
    "ReconciliationAdvisoryLock.try_acquire",
    "AnalyticsService.reconcile_intelligence_events",
    "DetectorRegistry.detect_all",
    "CrossSourceCorrelator.correlate",
    "IntelligenceEventsService.reconcile_detections",
    "ReconciliationAdvisoryLock.release",
)
"""Documented production reconciliation sequence (command side only)."""
