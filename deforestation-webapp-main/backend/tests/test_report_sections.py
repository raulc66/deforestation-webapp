"""Tests for modular report section registry."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.reports.report_sections import (
    ReportSectionRegistry,
    ReportSectionSpec,
    ensure_default_report_sections,
    get_report_section_registry,
    register_report_section,
)
from app.modules.reports.report_service import ReportGatherContext


class TestReportSectionRegistry:
    def test_default_sections_include_core_keys(self):
        registry = ensure_default_report_sections()
        keys = {spec.key for spec in registry.list_sections()}
        assert "overview" in keys
        assert "anomalies" in keys
        assert "risk" in keys
        assert "weather" in keys
        assert "incident_aggregation" in keys
        assert "environmental_threat_assessment" in keys
        assert "investigation_summary" in keys

    def test_register_custom_section(self):
        registry = ReportSectionRegistry()
        called = False

        async def _fetch(ctx: ReportGatherContext) -> dict:
            nonlocal called
            called = True
            return {"ok": True}

        registry.register(
            ReportSectionSpec("custom_test_section", "Test section", _fetch)
        )
        assert registry.get("custom_test_section") is not None

    def test_duplicate_registration_raises(self):
        registry = ReportSectionRegistry()

        async def _fetch(ctx: ReportGatherContext) -> dict:
            return {}

        registry.register(ReportSectionSpec("dup", "d", _fetch))
        with pytest.raises(ValueError):
            registry.register(ReportSectionSpec("dup", "d2", _fetch))

    @pytest.mark.anyio
    async def test_section_fetcher_receives_context(self):
        registry = ReportSectionRegistry()
        analytics = MagicMock()
        analytics.get_overview = AsyncMock(return_value={"total_events": 1})

        async def _overview(ctx: ReportGatherContext) -> dict:
            return await ctx.analytics.get_overview()

        registry.register(ReportSectionSpec("overview", "Overview", _overview))
        ctx = ReportGatherContext(
            analytics=analytics,
            intel_svc=MagicMock(),
            risk_svc=MagicMock(),
            history_svc=MagicMock(),
            notif_history_repo=MagicMock(),
            runs_repo=MagicMock(),
        )
        spec = registry.get("overview")
        result = await spec.fetcher(ctx)
        assert result["total_events"] == 1

    @pytest.mark.anyio
    async def test_investigation_summary_fetcher(self):
        registry = ensure_default_report_sections()
        inv_svc = AsyncMock()
        inv_svc.get_summary_report = AsyncMock(
            return_value={
                "open_investigations": 2,
                "critical_investigations": 1,
                "recent_investigations": [],
            }
        )
        ctx = ReportGatherContext(
            analytics=MagicMock(),
            intel_svc=MagicMock(),
            risk_svc=MagicMock(),
            history_svc=MagicMock(),
            notif_history_repo=MagicMock(),
            runs_repo=MagicMock(),
            investigation_svc=inv_svc,
        )
        spec = registry.get("investigation_summary")
        result = await spec.fetcher(ctx)
        assert result["open_investigations"] == 2
