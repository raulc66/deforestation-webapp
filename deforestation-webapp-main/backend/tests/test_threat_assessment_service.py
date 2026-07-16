"""Tests for ThreatAssessmentService and scoring logic."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.ecosystem.threat_categories import ThreatCategory
from app.modules.analytics.threat_assessment_service import (
    ThreatAssessmentService,
    assess_from_intelligence_event,
    build_threat_summary,
)


def _intel_event(**overrides) -> dict:
    base = {
        "id": "evt-1",
        "event_type": "anomaly",
        "incident_category": "wildfire",
        "region": "Suceava",
        "status": "active",
        "severity": "high",
        "escalation_level": "persistent",
        "trend": "worsening",
        "priority_score": 0.72,
        "current_score": 0.68,
        "detection_count": 4,
    }
    base.update(overrides)
    return base


class TestAssessFromIntelligenceEvent:
    def test_wildfire_assessment_fields(self):
        assessment = assess_from_intelligence_event(_intel_event())
        assert assessment.threat_category == ThreatCategory.WILDFIRE
        assert assessment.origin == "natural"
        assert assessment.region == "Suceava"
        assert 0.0 <= assessment.confidence <= 1.0
        assert 0.0 <= assessment.risk_contribution <= 1.0
        assert len(assessment.recommended_actions) >= 1

    def test_illegal_logging_is_human_origin(self):
        assessment = assess_from_intelligence_event(
            _intel_event(incident_category="illegal_logging")
        )
        assert assessment.threat_category == ThreatCategory.ILLEGAL_LOGGING
        assert assessment.origin == "human"

    def test_critical_escalation_raises_intervention(self):
        low = assess_from_intelligence_event(_intel_event(escalation_level="normal", severity="low"))
        high = assess_from_intelligence_event(
            _intel_event(escalation_level="critical", severity="critical")
        )
        assert high.intervention_priority.value >= low.intervention_priority.value


class TestBuildThreatSummary:
    def test_summary_aggregates_distribution(self):
        assessments = [
            assess_from_intelligence_event(_intel_event()),
            assess_from_intelligence_event(_intel_event(id="evt-2", region="Cluj")),
        ]
        summary = build_threat_summary(assessments)
        assert summary["distribution"].get("wildfire") == 2
        assert "human_vs_natural_ratio" in summary
        assert summary["human_vs_natural_ratio"]["natural"] == 1.0
        assert len(summary["top_threats"]) == 2


class TestThreatAssessmentService:
    @pytest.mark.anyio
    async def test_get_threats_from_intel_svc(self):
        intel = MagicMock()
        intel.get_events = AsyncMock(
            return_value={"active": [_intel_event()], "resolved": []}
        )
        svc = ThreatAssessmentService(intel)
        result = await svc.get_threats()
        assert "threats" in result
        assert len(result["threats"]) == 1
        assert result["threats"][0]["threat_category"] == "wildfire"

    @pytest.mark.anyio
    async def test_get_threat_summary(self):
        intel = MagicMock()
        intel.get_events = AsyncMock(
            return_value={"active": [_intel_event()], "resolved": []}
        )
        svc = ThreatAssessmentService(intel)
        summary = await svc.get_threat_summary()
        assert "distribution" in summary
        assert "highest_priority_interventions" in summary

    @pytest.mark.anyio
    async def test_report_payload(self):
        intel = MagicMock()
        intel.get_events = AsyncMock(
            return_value={"active": [_intel_event()], "resolved": []}
        )
        svc = ThreatAssessmentService(intel)
        report = await svc.get_threat_assessment_report()
        assert "threats" in report
        assert "distribution" in report
