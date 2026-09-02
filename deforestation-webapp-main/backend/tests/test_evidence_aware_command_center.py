"""Evidence-Aware Command Center tests."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import evidence_aware_command_center_dep, get_current_user
from app.core.ingestion.provider_health import ProviderHealthStatus
from app.models.user import UserPublic
from app.modules.analytics.analytics_routes import router
from app.modules.analytics.analytics_service import AnalyticsService
from app.modules.analytics.correlation_result import CorrelationParticipant, CorrelationResult
from app.modules.analytics.detection_contract import Detection
from app.modules.analytics.evidence_summary import (
    build_evidence_summary,
    build_intelligence_evidence_payload,
    resolve_correlation_state,
)
from app.modules.analytics.intelligence_cycle import detection_fingerprint, resolve_intelligence_cycle_id
from app.modules.analytics.intelligence_events_service import IntelligenceEventsService
from app.services.evidence_aware_command_center_service import EvidenceAwareCommandCenterService
from fixtures.phase0_golden_harness import generate_golden_artifacts
from fixtures.phase0_oracle_manifest import verify_generated_match_manifest

_NOW = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)


def _mock_user() -> UserPublic:
    return UserPublic(
        id="1",
        email="test@example.com",
        name="Test",
        role="admin",
        provider="local",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


def _event(
    *,
    event_id: str = "evt-1",
    category: str = "wildfire",
    region: str = "Suceava",
    spatial_key: str | None = None,
    priority: float = 0.65,
    metadata: dict | None = None,
) -> dict:
    return {
        "id": event_id,
        "incident_category": category,
        "region": region,
        "spatial_key": spatial_key or region,
        "severity": "high",
        "escalation_level": "normal",
        "trend": "new",
        "priority_score": priority,
        "status": "active",
        "metadata": metadata or {},
    }


def _correlation(
    *,
    correlation_id: str = "corr-1",
    category: str = "wildfire",
    spatial_key: str = "Suceava",
    relationship: str = "supporting_evidence",
    strength: float = 0.87,
    providers: tuple[str, ...] = ("nasa.firms", "cems.rapid_mapping"),
) -> CorrelationResult:
    return CorrelationResult(
        correlation_id=correlation_id,
        canonical_incident_category=category,
        canonical_spatial_key=spatial_key,
        relationship_type=relationship,
        correlation_rule="firms_cems_wildfire_support",
        participants=(
            CorrelationParticipant(
                incident_category="wildfire",
                spatial_key=spatial_key,
                provider_id="nasa.firms",
                detected_at=_NOW,
                role="primary",
            ),
            CorrelationParticipant(
                incident_category="environmental_hazard",
                spatial_key="cems-country:Romania",
                provider_id="cems.rapid_mapping",
                detected_at=_NOW,
                role="supporting",
            ),
        ),
        participating_provider_ids=providers,
        spatial_relationship="nearby",
        temporal_relationship="same_window",
        strength=strength,
        created_at=_NOW,
    )


class InMemoryIntelRepo:
    def __init__(self, events: list[dict] | None = None) -> None:
        self.events = list(events or [])

    async def find_active(self) -> list[dict]:
        return list(self.events)


class InMemoryCycleRepo:
    def __init__(self, state: dict | None = None) -> None:
        self.state = state

    async def get_current(self) -> dict | None:
        return self.state

    async def set_current(self, **kwargs) -> dict:
        self.state = kwargs
        return kwargs


class InMemoryCorrelationRepo:
    def __init__(self, rows: list[dict] | None = None) -> None:
        self.rows = list(rows or [])

    async def list_all(self) -> list[dict]:
        return list(self.rows)

    async def replace_all(self, records: list[dict], *, intelligence_cycle_id: str | None = None) -> None:
        self.rows = []
        for record in records:
            doc = dict(record)
            if intelligence_cycle_id:
                doc["intelligence_cycle_id"] = intelligence_cycle_id
            self.rows.append(doc)


class TestCycleConsistency:
    def test_deterministic_cycle_identifier_from_fingerprint(self):
        detections = [
            Detection(
                spatial_key="Suceava",
                incident_category="wildfire",
                signal_type="baseline_deviation",
                severity="high",
                score=0.7,
                evidence={"baseline_events": 1, "current_events": 3, "deviation_percent": 50, "region": "Suceava"},
                detected_at=_NOW,
            )
        ]
        fp = detection_fingerprint(detections)
        cycle_id = resolve_intelligence_cycle_id(None, fp)
        assert cycle_id.startswith("intel-")
        assert resolve_intelligence_cycle_id(None, fp) == cycle_id

    def test_scheduler_cycle_id_reused(self):
        assert resolve_intelligence_cycle_id("sched-abc", "fp") == "sched-abc"

    def test_current_cycle_correlation_state(self):
        assert (
            resolve_correlation_state(
                correlation_enabled=True,
                current_cycle_id="cycle-1",
                correlation_cycle_id="cycle-1",
                has_correlations=True,
            )
            == "current"
        )

    def test_stale_correlation_snapshot(self):
        assert (
            resolve_correlation_state(
                correlation_enabled=True,
                current_cycle_id="cycle-2",
                correlation_cycle_id="cycle-1",
                has_correlations=True,
            )
            == "stale"
        )

    def test_missing_correlation_snapshot(self):
        assert (
            resolve_correlation_state(
                correlation_enabled=True,
                current_cycle_id="cycle-1",
                correlation_cycle_id=None,
                has_correlations=False,
            )
            == "unavailable"
        )


class TestEvidenceSummary:
    def test_single_source_evidence(self):
        summary = build_evidence_summary(
            _event(),
            correlations=[],
            correlation_state="disabled",
            health_by_provider={"nasa.firms": ProviderHealthStatus.HEALTHY.value},
        )
        assert summary.evidence_state == "single_source"
        assert summary.source_count == 1

    def test_multi_source_evidence(self):
        summary = build_evidence_summary(
            _event(),
            correlations=[_correlation()],
            correlation_state="current",
            health_by_provider={
                "nasa.firms": ProviderHealthStatus.HEALTHY.value,
                "cems.rapid_mapping": ProviderHealthStatus.HEALTHY.value,
            },
        )
        assert summary.evidence_state == "multi_source"
        assert summary.strongest_correlation_strength == pytest.approx(0.87)

    def test_contextual_evidence(self):
        summary = build_evidence_summary(
            _event(category="wildfire"),
            correlations=[
                _correlation(
                    relationship="contextual_evidence",
                    providers=("nasa.firms", "eea.air_quality"),
                )
            ],
            correlation_state="current",
            health_by_provider={"nasa.firms": "healthy", "eea.air_quality": "healthy"},
        )
        assert summary.evidence_state == "contextual_support"

    def test_degraded_provider_indicator(self):
        summary = build_evidence_summary(
            _event(),
            correlations=[],
            correlation_state="disabled",
            health_by_provider={"nasa.firms": ProviderHealthStatus.FAILED.value},
        )
        assert summary.evidence_state == "degraded_source"

    def test_provenance_disabled_and_enabled(self):
        disabled = build_intelligence_evidence_payload(
            [_event(metadata={"provenance": {"provider_id": "nasa.firms"}})],
            correlations=[],
            cycle_state=None,
            correlation_enabled=False,
            include_provenance=False,
            health_rows=[],
        )
        enabled = build_intelligence_evidence_payload(
            [_event(metadata={"provenance": {"provider_id": "nasa.firms", "api_key": "SECRET"}})],
            correlations=[],
            cycle_state=None,
            correlation_enabled=False,
            include_provenance=True,
            health_rows=[],
        )
        assert disabled["items"][0]["provenance"] == []
        assert "api_key" not in enabled["items"][0]["provenance"][0]

    def test_priority_fields_unchanged(self):
        payload = build_intelligence_evidence_payload(
            [_event(priority=0.5598)],
            correlations=[],
            cycle_state=None,
            correlation_enabled=False,
            include_provenance=False,
            health_rows=[],
        )
        assert payload["items"][0]["priority_score"] == pytest.approx(0.5598)


class TestEvidenceAwareService:
    @pytest.mark.anyio
    async def test_current_cycle_correlation_and_events(self):
        settings = MagicMock()
        settings.enable_cross_source_correlation = True
        settings.enable_intelligence_provenance = False
        health_repo = MagicMock()
        health_repo.list_all = AsyncMock(return_value=[])
        svc = EvidenceAwareCommandCenterService(
            InMemoryIntelRepo([_event()]),
            InMemoryCorrelationRepo(
                [{**_correlation().as_dict(), "intelligence_cycle_id": "cycle-1"}]
            ),
            InMemoryCycleRepo(
                {
                    "intelligence_cycle_id": "cycle-1",
                    "correlation_cycle_id": "cycle-1",
                }
            ),
            health_repo,
            settings=settings,
        )
        payload = await svc.build_intelligence_evidence()
        assert payload["correlation_state"] == "current"
        assert payload["items"][0]["evidence_summary"]["evidence_state"] == "multi_source"


class TestEvidenceApi:
    def test_command_center_get_side_effect_free(self):
        from tests.fixtures.intelligence_write_spy import build_intelligence_read_client

        client, spy = build_intelligence_read_client()
        resp = client.get("/analytics/intelligence/command-center")
        assert resp.status_code == 200
        assert "intelligence_evidence" in resp.json()
        spy.assert_no_persistence_or_reconciliation()


class TestPhase0Compatibility:
    def test_oracle_unchanged(self):
        verify_generated_match_manifest(generate_golden_artifacts())

    def test_ten_run_determinism(self):
        for _ in range(10):
            verify_generated_match_manifest(generate_golden_artifacts())
