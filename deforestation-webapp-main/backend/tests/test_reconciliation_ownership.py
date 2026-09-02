"""WP6.2 / WP6.3 — reconciliation command ownership and boundary."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, ANY

import pytest

from app.modules.analytics.analytics_routes import router
from app.modules.analytics.analytics_service import AnalyticsService
from app.modules.analytics.intelligence_events_service import IntelligenceEventsService
from app.modules.analytics.reconciliation import (
    EXPLICIT_HTTP_RECONCILE_COMMAND,
    PRODUCTION_RECONCILIATION_OWNERS,
    RECONCILIATION_COMMAND_CHAIN,
)
from app.services.scheduler_service import SchedulerService

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_APP_ROOT = _BACKEND_ROOT / "app"


def _run(coro):
    import asyncio

    return asyncio.run(coro)


class TestProductionReconciliationCallSites:
    def test_only_scheduler_invokes_reconcile_intelligence_events_in_app_code(self):
        """Persistent reconciliation is invoked from scheduler code only (WP6.2)."""
        callers: list[str] = []

        for path in _APP_ROOT.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "async def reconcile_intelligence_events" in text:
                continue
            rel = path.relative_to(_BACKEND_ROOT).as_posix()
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                    continue
                if "await" in line and "reconcile_intelligence_events(" in line.replace(" ", ""):
                    callers.append(rel)
                    break

        assert callers == ["app/services/scheduler_service.py"]

    def test_only_analytics_service_invokes_reconcile_detections_in_app_code(self):
        """reconcile_detections is called only from the analytics command orchestrator."""
        pattern = re.compile(r"reconcile_detections\s*\(")
        callers: list[str] = []

        for path in _APP_ROOT.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "async def reconcile_detections" in text:
                continue
            rel = path.relative_to(_BACKEND_ROOT).as_posix()
            for line in text.splitlines():
                if pattern.search(line) and not line.strip().startswith("#"):
                    callers.append(rel)
                    break

        assert callers == ["app/modules/analytics/analytics_service.py"]

    def test_no_http_route_handler_calls_reconcile_intelligence_events(self):
        """No analytics route performs persistent reconciliation (WP6.1+)."""
        routes_module = _APP_ROOT / "modules" / "analytics" / "analytics_routes.py"
        source = routes_module.read_text(encoding="utf-8")
        tree = ast.parse(source)
        offenders: list[str] = []

        for node in tree.body:
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            segment = ast.get_source_segment(source, node) or ""
            if "reconcile_intelligence_events" in segment:
                offenders.append(node.name)
            if "reconcile_detections" in segment:
                offenders.append(node.name)
            if ".reconcile(" in segment:
                offenders.append(node.name)

        assert offenders == []

    def test_no_post_reconcile_command_route_registered(self):
        """No HTTP command endpoint exposes reconciliation (WP6.3)."""
        for route in router.routes:
            methods = getattr(route, "methods", None) or set()
            path = getattr(route, "path", "")
            if not methods.intersection({"POST", "PUT", "PATCH"}):
                continue
            assert "reconcile" not in path.lower()


class TestReconciliationCommandChain:
    def test_documented_command_chain_is_complete(self):
        assert RECONCILIATION_COMMAND_CHAIN == (
            "SchedulerService._run_cycle",
            "ReconciliationAdvisoryLock.try_acquire",
            "AnalyticsService.reconcile_intelligence_events",
            "DetectorRegistry.detect_all",
            "CrossSourceCorrelator.correlate",
            "IntelligenceEventsService.reconcile_detections",
            "ReconciliationAdvisoryLock.release",
        )

    def test_analytics_reconcile_intelligence_events_executes_detector_chain(self):
        repo = MagicMock()
        repo.regional_baselines = AsyncMock(return_value=[])

        intel_svc = MagicMock(spec=IntelligenceEventsService)
        intel_svc.reconcile_detections = AsyncMock()
        intel_svc.get_events = AsyncMock(return_value={"active": [], "resolved": []})

        analytics = AnalyticsService(repo)

        with patch(
            "app.modules.analytics.detector_registry.get_detector_registry"
        ) as registry_factory:
            registry = MagicMock()
            registry.detect_all = MagicMock(return_value=[])
            registry_factory.return_value = registry

            result = _run(analytics.reconcile_intelligence_events(intel_svc))

        repo.regional_baselines.assert_called_once()
        registry.detect_all.assert_called_once()
        intel_svc.reconcile_detections.assert_called_once()
        intel_svc.get_events.assert_called_once()
        assert result == {"active": [], "resolved": []}

    @pytest.mark.anyio
    async def test_scheduler_run_cycle_is_production_reconciliation_owner(self):
        firms = AsyncMock()
        firms.run = AsyncMock(return_value={"total": 0, "created": 0, "skipped": 0})

        analytics = AsyncMock()
        analytics.reconcile_intelligence_events = AsyncMock(
            return_value={"active": [], "resolved": []}
        )

        runs_repo = AsyncMock()
        runs_repo.create_run = AsyncMock(
            return_value={
                "events_fetched": 0,
                "events_inserted": 0,
                "duplicates_skipped": 0,
                "duration_seconds": 0.1,
            }
        )

        intel_svc = AsyncMock()
        scheduler = SchedulerService(
            firms_provider=firms,
            events_service=AsyncMock(),
            events_repo=AsyncMock(),
            analytics_service=analytics,
            intelligence_service=intel_svc,
            runs_repo=runs_repo,
            poll_interval_minutes=60,
            enabled=True,
            firms_source_id=None,
        )

        await scheduler._run_cycle()

        analytics.reconcile_intelligence_events.assert_called_once_with(
            intel_svc, intelligence_cycle_id=ANY
        )

    @pytest.mark.anyio
    async def test_scheduler_runs_reconciliation_when_ingestion_fails(self):
        firms = AsyncMock()
        firms.source_name = "NASA FIRMS"
        firms.provider_id = "nasa.firms"
        firms.describe = MagicMock(return_value={"source": "NASA FIRMS", "provider_id": "nasa.firms"})
        firms.run = AsyncMock(side_effect=RuntimeError("ingestion failed"))

        analytics = AsyncMock()
        analytics.reconcile_intelligence_events = AsyncMock()

        runs_repo = AsyncMock()
        runs_repo.create_run = AsyncMock(
            return_value={"status": "failed", "duration_seconds": 0.1}
        )

        scheduler = SchedulerService(
            firms_provider=firms,
            events_service=AsyncMock(),
            events_repo=AsyncMock(),
            analytics_service=analytics,
            intelligence_service=AsyncMock(),
            runs_repo=runs_repo,
            poll_interval_minutes=60,
            enabled=True,
            firms_source_id=None,
        )

        run = await scheduler._run_cycle()

        analytics.reconcile_intelligence_events.assert_called_once()
        assert run.get("status") == "failed"


class TestExplicitReconciliationCommandBoundary:
    """WP6.3 — scheduler-only ownership is sufficient; no HTTP command added."""

    def test_scheduler_only_production_owner_policy(self):
        assert PRODUCTION_RECONCILIATION_OWNERS == frozenset({"scheduler"})

    def test_explicit_http_reconcile_command_not_required(self):
        assert EXPLICIT_HTTP_RECONCILE_COMMAND is False

    def test_adr007_allows_scheduler_without_mandatory_http_command(self):
        """ADR-007 permits scheduler or explicit command; scheduler-only is valid."""
        adr_path = (
            _BACKEND_ROOT.parent
            / "docs"
            / "architecture"
            / "adr"
            / "ADR-007-scheduler-responsibilities.md"
        )
        text = adr_path.read_text(encoding="utf-8")
        assert "scheduler or by an explicit" in text.lower()
        assert EXPLICIT_HTTP_RECONCILE_COMMAND is False
