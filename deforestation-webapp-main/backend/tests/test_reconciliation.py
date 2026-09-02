"""WP3 — canonical Detection-driven reconciliation tests."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.ecosystem.incident_categories import IncidentCategory
from app.modules.analytics.detection_contract import Detection, SignalType
from app.modules.analytics.detection_adapters import detection_from_anomaly_dict
from app.modules.analytics.intelligence_events_service import IntelligenceEventsService
from app.modules.analytics.reconciliation import (
    dedupe_detections,
    identity_key_from_detection,
    identity_key_from_event,
)

_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

_ANOMALY = {
    "region": "Carpathian Forest",
    "baseline_events": 10,
    "current_events": 30,
    "deviation_percent": 150.0,
    "anomaly_score": 0.69,
    "severity": "high",
    "status": "active",
}


def _mock_repo(
    active_events: list[dict] | None = None,
    all_events: list[dict] | None = None,
) -> MagicMock:
    repo = MagicMock()
    repo.find_active = AsyncMock(return_value=active_events or [])
    repo.find_all = AsyncMock(return_value=all_events or [])
    repo.create = AsyncMock(side_effect=lambda payload: {"id": "new-id", **payload})
    repo.update = AsyncMock(return_value=None)
    repo.resolve = AsyncMock(return_value=None)
    return repo


def _svc(repo: MagicMock) -> IntelligenceEventsService:
    return IntelligenceEventsService(repo)


def _run(coro):
    return asyncio.run(coro)


def _detection(
    *,
    region: str,
    incident_category: str = IncidentCategory.WILDFIRE.value,
    score: float = 0.69,
    severity: str = "high",
) -> Detection:
    return Detection(
        spatial_key=region,
        incident_category=incident_category,
        signal_type=SignalType.BASELINE_DEVIATION.value,
        severity=severity,
        score=score,
        evidence={
            "region": region,
            "baseline_events": 10,
            "current_events": 30,
            "deviation_percent": 150.0,
            "forest_confidence": 1.0,
        },
        detected_at=_NOW,
    )


def _active_event(
    *,
    region: str = "Carpathian Forest",
    incident_category: str | None = None,
    spatial_key: str | None = None,
    event_id: str = "evt-001",
    detection_count: int = 1,
    current_score: float = 0.69,
) -> dict:
    event = {
        "id": event_id,
        "event_type": "anomaly",
        "region": region,
        "status": "active",
        "severity": "high",
        "first_detected_at": _NOW,
        "last_detected_at": _NOW,
        "detection_count": detection_count,
        "current_score": current_score,
        "metadata": {"baseline_events": 10, "current_events": 20, "deviation_percent": 100.0},
    }
    if incident_category is not None:
        event["incident_category"] = incident_category
    if spatial_key is not None:
        event["spatial_key"] = spatial_key
    return event


class TestReconcileDetectionsCreated:
    def test_created_transition_recorded(self):
        repo = _mock_repo(active_events=[])
        change_set = _run(
            _svc(repo).reconcile_detections([_detection(region="Alpha")], _NOW)
        )
        assert len(change_set.created) == 1
        assert change_set.created[0].action == "created"
        assert change_set.created[0].incident_category == "wildfire"
        assert change_set.created[0].spatial_key == "Alpha"

    def test_create_persists_canonical_identity_fields(self):
        repo = _mock_repo(active_events=[])
        _run(_svc(repo).reconcile_detections([_detection(region="Beta")], _NOW))
        created = repo.create.call_args[0][0]
        assert created["incident_category"] == "wildfire"
        assert created["spatial_key"] == "Beta"
        assert created["signal_type"] == SignalType.BASELINE_DEVIATION.value
        assert created["event_type"] == "anomaly"


class TestReconcileDetectionsUpdated:
    def test_updated_transition_recorded(self):
        existing = _active_event(region="Carpathian Forest")
        repo = _mock_repo(active_events=[existing])
        change_set = _run(
            _svc(repo).reconcile_detections(
                [_detection(region="Carpathian Forest")],
                _NOW,
            )
        )
        assert len(change_set.updated) == 1
        assert change_set.updated[0].event_id == "evt-001"
        repo.update.assert_called_once()

    def test_legacy_active_event_without_spatial_key_matches_detection(self):
        existing = _active_event(region="Carpathian Forest")
        repo = _mock_repo(active_events=[existing])
        _run(
            _svc(repo).reconcile_detections(
                [_detection(region="Carpathian Forest")],
                _NOW,
            )
        )
        repo.create.assert_not_called()
        repo.update.assert_called_once()


class TestReconcileDetectionsResolved:
    def test_resolved_transition_recorded(self):
        existing = _active_event(region="Stale", event_id="stale-1")
        repo = _mock_repo(active_events=[existing])
        change_set = _run(_svc(repo).reconcile_detections([], _NOW))
        assert len(change_set.resolved) == 1
        assert change_set.resolved[0].action == "resolved"
        assert change_set.resolved[0].event_id == "stale-1"
        repo.resolve.assert_called_once_with("stale-1", _NOW)


class TestMultiCategoryCoexistence:
    def test_same_region_different_categories_create_independently(self):
        repo = _mock_repo(active_events=[])
        detections = [
            _detection(region="Shared", incident_category="wildfire"),
            _detection(
                region="Shared",
                incident_category="illegal_logging",
                score=0.55,
                severity="medium",
            ),
        ]
        change_set = _run(_svc(repo).reconcile_detections(detections, _NOW))
        assert len(change_set.created) == 2
        assert repo.create.call_count == 2
        categories = {item.incident_category for item in change_set.created}
        assert categories == {"wildfire", "illegal_logging"}

    def test_resolving_one_category_leaves_other_active(self):
        wildfire = _active_event(
            region="Shared",
            incident_category="wildfire",
            spatial_key="Shared",
            event_id="wf-1",
        )
        logging = _active_event(
            region="Shared",
            incident_category="illegal_logging",
            spatial_key="Shared",
            event_id="log-1",
        )
        repo = _mock_repo(active_events=[wildfire, logging])
        change_set = _run(
            _svc(repo).reconcile_detections(
                [_detection(region="Shared", incident_category="illegal_logging", score=0.55, severity="medium")],
                _NOW,
            )
        )
        assert len(change_set.resolved) == 1
        assert change_set.resolved[0].incident_category == "wildfire"
        assert len(change_set.updated) == 1
        assert change_set.updated[0].incident_category == "illegal_logging"


class TestSameCategoryDifferentSpatialKeys:
    def test_two_regions_same_category_both_created(self):
        repo = _mock_repo(active_events=[])
        detections = [
            _detection(region="North"),
            _detection(region="South", score=0.5, severity="medium"),
        ]
        change_set = _run(_svc(repo).reconcile_detections(detections, _NOW))
        assert len(change_set.created) == 2
        keys = {(item.spatial_key, item.incident_category) for item in change_set.created}
        assert keys == {("North", "wildfire"), ("South", "wildfire")}


class TestDeterministicOrdering:
    def test_dedupe_retains_highest_score(self):
        low = _detection(region="Alpha", score=0.4, severity="medium")
        high = _detection(region="Alpha", score=0.9, severity="critical")
        deduped = dedupe_detections([low, high])
        assert len(deduped) == 1
        assert deduped[0].score == pytest.approx(0.9)

    def test_resolve_order_is_sorted_by_identity(self):
        events = [
            _active_event(region="Zulu", event_id="z"),
            _active_event(region="Alpha", event_id="a"),
        ]
        repo = _mock_repo(active_events=events)
        change_set = _run(_svc(repo).reconcile_detections([], _NOW))
        resolved_ids = [item.event_id for item in change_set.resolved]
        assert resolved_ids == ["a", "z"]


class TestLegacyReconcileWrapper:
    def test_reconcile_anomalies_delegates_to_detections(self):
        repo = _mock_repo(active_events=[])
        detection = detection_from_anomaly_dict(_ANOMALY, detected_at=_NOW)
        change_set = _run(_svc(repo).reconcile([_ANOMALY], _NOW))
        assert len(change_set.created) == 1
        assert identity_key_from_detection(detection) == (
            change_set.created[0].incident_category,
            change_set.created[0].spatial_key,
        )


class TestIdentityHelpers:
    def test_identity_key_from_legacy_event_defaults_wildfire(self):
        assert identity_key_from_event({"region": "Cluj"}) == ("wildfire", "Cluj")

    def test_identity_key_from_explicit_fields(self):
        event = {
            "incident_category": "illegal_logging",
            "spatial_key": "grid-42",
            "region": "ignored-for-key",
        }
        assert identity_key_from_event(event) == ("illegal_logging", "grid-42")


class TestWildfireOracleCompatibility:
    def test_legacy_anomaly_round_trip_matches_canonical_reconcile(self):
        repo_legacy = _mock_repo(active_events=[])
        repo_detection = _mock_repo(active_events=[])
        svc_legacy = _svc(repo_legacy)
        svc_detection = _svc(repo_detection)
        detection = detection_from_anomaly_dict(_ANOMALY, detected_at=_NOW)

        _run(svc_legacy.reconcile([_ANOMALY], _NOW))
        _run(svc_detection.reconcile_detections([detection], _NOW))

        legacy_payload = repo_legacy.create.call_args[0][0]
        detection_payload = repo_detection.create.call_args[0][0]
        for field in (
            "region",
            "incident_category",
            "severity",
            "current_score",
            "detection_count",
            "trend",
            "status",
            "event_type",
        ):
            assert legacy_payload[field] == detection_payload[field]
        assert legacy_payload["spatial_key"] == _ANOMALY["region"]
