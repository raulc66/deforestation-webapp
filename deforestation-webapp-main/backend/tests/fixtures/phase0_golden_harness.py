"""Phase 0 golden-output harness (WP0.2 / WP0.3).

Runs the **existing** analytics and intelligence pipeline over the WP0.1 frozen
fixture using in-memory repository stand-ins — no production code changes and
no MongoDB dependency.

Time is injected via :mod:`fixtures.phase0_time_anchor` and
:data:`fixtures.phase0_golden_fixture.CYCLE_ANCHORS` only.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.modules.analytics.analytics_service import (
    AnalyticsService,
    _compute_baselines,
    _evaluate_anomalies,
)
from app.modules.analytics.command_center_service import CommandCenterService
from app.modules.analytics.incident_aggregation import build_default_incident_registry
from app.modules.analytics.intelligence_events_service import IntelligenceEventsService
from app.modules.analytics.reconciliation import identity_key_from_event
from app.core.ecosystem.incident_categories import normalize_incident_category

from app.core.geography.geographic_scope import GeographicScope, GeographicScopePolicy

from fixtures.phase0_golden_fixture import CYCLE_ANCHORS, build_wildfire_events
from fixtures.phase0_oracle_manifest import GOLDEN_ARTIFACT_FILES, GOLDEN_DIR
from fixtures.phase0_time_anchor import inject_phase0_time, pipeline_final_anchor

# Phase 0 oracle executes under explicit Romania scope — never implicit defaults.
PHASE0_GEOGRAPHIC_SCOPE = GeographicScopePolicy(GeographicScope.ROMANIA)

# Fields assigned by persistence layers — stripped before snapshotting.
_PERSISTENCE_FIELD_RE = re.compile(
    r"^(_id|id|created_at|updated_at|inserted_at)$"
)

# ---------------------------------------------------------------------------
# In-memory analytics repository (fixture-backed)
# ---------------------------------------------------------------------------


class Phase0FixtureAnalyticsRepository:
    """Minimal ``AnalyticsRepository`` stand-in for the frozen fixture."""

    collection_name = "forest_events"

    def __init__(
        self,
        events: list[dict],
        *,
        scope_policy: GeographicScopePolicy | None = None,
    ) -> None:
        self._events = events
        self._scope = scope_policy or PHASE0_GEOGRAPHIC_SCOPE

    @property
    def scope_policy(self) -> GeographicScopePolicy:
        return self._scope

    def _scoped_events(self) -> list[dict]:
        return [e for e in self._events if self._scope.event_in_scope(e)]

    async def regional_baselines(self, now: datetime) -> list[dict]:
        """Mirror ``AnalyticsRepository.regional_baselines`` in pure Python."""
        from app.modules.analytics.segmented_baseline import (
            aggregate_regional_baselines_by_category,
        )

        return aggregate_regional_baselines_by_category(
            self._events,
            now,
            scope_policy=self._scope,
        )

    async def overview(self) -> dict | None:
        events = self._events
        if not events:
            return None
        total_area = sum(float(e.get("affected_area_ha", 0.0)) for e in events)
        open_events = sum(1 for e in events if e.get("status") == "open")
        resolved_events = sum(1 for e in events if e.get("status") == "resolved")
        investigating = sum(1 for e in events if e.get("status") == "investigating")
        confidences = [float(e.get("confidence", 0.0)) for e in events]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return {
            "total_events": len(events),
            "total_area": total_area,
            "open_events": open_events,
            "resolved_events": resolved_events,
            "investigating_events": investigating,
            "average_confidence": avg_conf,
        }

    async def by_event_type(self) -> list[dict]:
        totals: dict[str, dict[str, float | int]] = {}
        for event in self._events:
            et = event.get("event_type", "unknown")
            bucket = totals.setdefault(et, {"event_count": 0, "affected_area_ha": 0.0})
            bucket["event_count"] += 1
            bucket["affected_area_ha"] += float(event.get("affected_area_ha", 0.0))
        rows = [
            {"_id": et, **data}
            for et, data in totals.items()
        ]
        rows.sort(key=lambda r: (-int(r["event_count"]), r["_id"]))
        return rows


# ---------------------------------------------------------------------------
# In-memory intelligence-events repository
# ---------------------------------------------------------------------------


class InMemoryIntelligenceEventsRepository:
    """Minimal ``IntelligenceEventsRepository`` stand-in (list-backed)."""

    collection_name = "intelligence_events"

    def __init__(self) -> None:
        self._events: list[dict] = []
        self._seq = 0

    def _assign_id(self, event: dict) -> dict:
        self._seq += 1
        stored = dict(event)
        stored["id"] = f"phase0-mem-{self._seq:04d}"
        self._events.append(stored)
        return stored

    async def find_active(self) -> list[dict]:
        active = [dict(e) for e in self._events if e.get("status") == "active"]
        active.sort(key=lambda e: e.get("last_detected_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return active

    async def find_all(self) -> list[dict]:
        ordered = sorted(
            [dict(e) for e in self._events],
            key=lambda e: e.get("last_detected_at") or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return ordered

    async def find_active_by_identity(
        self,
        incident_category: str,
        spatial_key: str,
    ) -> dict | None:
        """Return the active event matching canonical identity, or None."""
        target = (
            normalize_incident_category(incident_category),
            str(spatial_key),
        )
        for event in self._events:
            if event.get("status") != "active":
                continue
            if identity_key_from_event(event) == target:
                return dict(event)
        return None

    async def find_active_by_region(self, event_type: str, region: str) -> dict | None:
        for event in self._events:
            if (
                event.get("event_type") == event_type
                and event.get("region") == region
                and event.get("status") == "active"
            ):
                return dict(event)
        return None

    async def create(self, event: dict) -> dict:
        return self._assign_id(event)

    async def update(self, event_id: str, update_data: dict) -> None:
        for idx, event in enumerate(self._events):
            if event.get("id") == event_id:
                self._events[idx] = {**event, **update_data}
                return

    async def resolve(self, event_id: str, resolved_at: datetime) -> None:
        for idx, event in enumerate(self._events):
            if event.get("id") == event_id:
                self._events[idx] = {
                    **event,
                    "status": "resolved",
                    "resolved_at": resolved_at,
                }
                return


# ---------------------------------------------------------------------------
# Snapshot normalization
# ---------------------------------------------------------------------------


def _normalize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, raw in value.items():
            if _PERSISTENCE_FIELD_RE.match(str(key)):
                continue
            normalized[key] = _normalize_value(raw)
        return normalized
    if isinstance(value, list):
        return [_normalize_value(v) for v in value]
    return value


def normalize_for_snapshot(payload: Any) -> Any:
    """Remove persistence fields and canonically sort unordered collections."""
    return _normalize_value(copy.deepcopy(payload))


def snapshot_to_json(payload: Any) -> str:
    """Deterministic JSON text for byte-stable golden files."""
    normalized = normalize_for_snapshot(payload)
    return json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# Pipeline execution
# ---------------------------------------------------------------------------


async def run_phase0_golden_pipeline() -> dict[str, Any]:
    """Execute two reconciliation cycles and collect all baseline artifacts."""
    events = build_wildfire_events()
    analytics_repo = Phase0FixtureAnalyticsRepository(
        events,
        scope_policy=PHASE0_GEOGRAPHIC_SCOPE,
    )
    intel_repo = InMemoryIntelligenceEventsRepository()
    analytics_svc = AnalyticsService(analytics_repo)
    intel_svc = IntelligenceEventsService(intel_repo)

    artifacts: dict[str, Any] = {}

    for cycle_idx, anchor in enumerate(CYCLE_ANCHORS):
        rows = await analytics_repo.regional_baselines(anchor)
        baselines = _compute_baselines(
            rows,
            generated_at=anchor,
            include_incident_category=False,
        )
        anomalies = _evaluate_anomalies(
            baselines["regions"],
            generated_at=anchor,
            incident_category="wildfire",
        )

        artifacts[f"cycle_{cycle_idx}_regional_baselines"] = baselines
        artifacts[f"cycle_{cycle_idx}_anomalies"] = anomalies

        from app.modules.analytics.detector_registry import get_detector_registry

        detections = get_detector_registry().detect_all(baselines["regions"], anchor)
        await intel_svc.reconcile_detections(detections, anchor)
        artifacts[f"cycle_{cycle_idx}_intelligence_events"] = await intel_svc.get_events()

    last_anchor = pipeline_final_anchor()
    with inject_phase0_time(last_anchor):
        registry = build_default_incident_registry()
        artifacts["incident_aggregation"] = await registry.aggregate_all(analytics_svc)

    cmd_svc = CommandCenterService(analytics_svc, intel_svc)
    artifacts["command_center_snapshot"] = await cmd_svc.get_snapshot(generated_at=last_anchor)

    return artifacts


def generate_golden_artifacts() -> dict[str, str]:
    """Run the pipeline and return ``{filename: json_text}`` for golden files."""
    import asyncio

    artifacts = asyncio.run(run_phase0_golden_pipeline())
    file_map = {
        filename: artifacts[filename.removesuffix(".json")]
        for filename in GOLDEN_ARTIFACT_FILES
    }
    return {name: snapshot_to_json(payload) for name, payload in file_map.items()}


def load_golden_file(name: str) -> Any:
    path = GOLDEN_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def write_golden_files() -> list[Path]:
    """Persist golden artifacts to ``tests/fixtures/golden/``."""
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, text in generate_golden_artifacts().items():
        path = GOLDEN_DIR / name
        path.write_text(text, encoding="utf-8", newline="\n")
        written.append(path)
    return written
