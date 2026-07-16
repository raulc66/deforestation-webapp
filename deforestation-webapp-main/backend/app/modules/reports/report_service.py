"""Report service — orchestrates data gathering and file generation.

Responsibilities:
  - Gather data from all intelligence services for a given period.
  - Write PDF / CSV / JSON report files asynchronously.
  - Update report metadata in MongoDB at each lifecycle stage.
  - Schedule automatic daily / weekly / monthly generation (called by the scheduler).
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from app.models.base import utcnow

from .csv_export import generate_report_csv
from .json_export import generate_report_json
from .pdf_generator import generate_report_pdf
from .report_models import ReportFormat, ReportStatus, ReportType
from .report_repository import ReportRepository
from .report_sections import ReportSectionRegistry, ensure_default_report_sections

if TYPE_CHECKING:
    from app.modules.analytics.analytics_service import AnalyticsService
    from app.modules.analytics.history_service import HistoryService
    from app.modules.analytics.intelligence_events_service import (
        IntelligenceEventsService,
    )
    from app.modules.analytics.risk_service import RiskService
    from app.modules.analytics.threat_assessment_service import ThreatAssessmentService
    from app.repositories.ingestion_runs_repository import IngestionRunsRepository
    from app.repositories.notification_history_repository import (
        NotificationHistoryRepository,
    )
    from app.services.weather_service import WeatherService
    from app.modules.investigations.investigation_service import InvestigationService

logger = logging.getLogger("forestwatch.reports.service")


@dataclass
class ReportGatherContext:
    """Services available to registered report section fetchers."""

    analytics: "AnalyticsService"
    intel_svc: "IntelligenceEventsService"
    risk_svc: "RiskService"
    history_svc: "HistoryService"
    notif_history_repo: "NotificationHistoryRepository"
    runs_repo: "IngestionRunsRepository"
    weather_svc: "WeatherService | None" = None
    threat_svc: "ThreatAssessmentService | None" = None
    investigation_svc: "InvestigationService | None" = None


# ---------------------------------------------------------------------------
# Pure helper — builds a compact summary dict
# ---------------------------------------------------------------------------

def _build_summary(data: dict) -> dict:
    overview = data.get("overview") or {}
    events = data.get("intelligence_events") or {}
    risk = data.get("risk") or {}
    anomalies_data = data.get("anomalies") or {}
    notifs = data.get("notifications") or []
    runs = data.get("ingestion_runs") or []

    risk_regions = risk.get("regions", [])
    highest = risk_regions[0] if risk_regions else {}
    success_notifs = sum(1 for n in notifs if n.get("success", True))
    success_runs = sum(1 for r in runs if r.get("status") == "success")

    return {
        "total_events": overview.get("total_events", 0),
        "open_events": overview.get("open_events", 0),
        "active_intel_events": len(events.get("active", [])),
        "resolved_intel_events": len(events.get("resolved", [])),
        "anomaly_count": len(anomalies_data.get("anomalies", [])),
        "highest_risk_region": highest.get("region"),
        "highest_risk_score": highest.get("risk_score"),
        "notifications_sent": len(notifs),
        "notifications_success": success_notifs,
        "ingestion_runs": len(runs),
        "ingestion_success": success_runs,
    }


# ---------------------------------------------------------------------------
# Default period helpers
# ---------------------------------------------------------------------------

def _daily_period(now: datetime) -> tuple[datetime, datetime]:
    end = now
    start = now - timedelta(days=1)
    return start, end


def _weekly_period(now: datetime) -> tuple[datetime, datetime]:
    end = now
    start = now - timedelta(days=7)
    return start, end


def _monthly_period(now: datetime) -> tuple[datetime, datetime]:
    end = now
    start = now - timedelta(days=30)
    return start, end


# ---------------------------------------------------------------------------
# ReportService
# ---------------------------------------------------------------------------

class ReportService:
    def __init__(
        self,
        *,
        report_repo: ReportRepository,
        analytics_svc: "AnalyticsService",
        intel_svc: "IntelligenceEventsService",
        risk_svc: "RiskService",
        history_svc: "HistoryService",
        notif_history_repo: "NotificationHistoryRepository",
        runs_repo: "IngestionRunsRepository",
        reports_dir: Path,
        weather_svc: "WeatherService | None" = None,
        threat_svc: "ThreatAssessmentService | None" = None,
        investigation_svc: "InvestigationService | None" = None,
        section_registry: ReportSectionRegistry | None = None,
    ) -> None:
        self._report_repo = report_repo
        self._analytics = analytics_svc
        self._intel_svc = intel_svc
        self._risk_svc = risk_svc
        self._history_svc = history_svc
        self._notif_history_repo = notif_history_repo
        self._runs_repo = runs_repo
        self._weather_svc = weather_svc
        self._threat_svc = threat_svc
        self._investigation_svc = investigation_svc
        self._reports_dir = reports_dir
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        self._section_registry = section_registry or ensure_default_report_sections()

    # ------------------------------------------------------------------ #
    # Data gathering
    # ------------------------------------------------------------------ #

    async def gather_report_data(
        self, period_start: datetime, period_end: datetime, report_type: str = "on_demand"
    ) -> dict:
        """Fetch all intelligence data for the report period.

        Each section is fetched independently; failures are logged and
        replaced with empty defaults to avoid partial-report crashes.
        """
        data: dict = {
            "report_type": report_type,
            "period_start": period_start,
            "period_end": period_end,
            "generated_at": utcnow(),
        }

        ctx = ReportGatherContext(
            analytics=self._analytics,
            intel_svc=self._intel_svc,
            risk_svc=self._risk_svc,
            history_svc=self._history_svc,
            notif_history_repo=self._notif_history_repo,
            runs_repo=self._runs_repo,
            weather_svc=self._weather_svc,
            threat_svc=self._threat_svc,
            investigation_svc=self._investigation_svc,
        )

        async def _safe_fetch(key: str, coro):
            try:
                data[key] = await coro
            except Exception as exc:
                logger.warning("Report section %r failed: %s", key, exc)
                data[key] = {} if key not in ("notifications", "ingestion_runs") else []

        section_tasks = [
            _safe_fetch(spec.key, spec.fetcher(ctx))
            for spec in self._section_registry.list_sections()
        ]
        await asyncio.gather(*section_tasks)

        data["summary"] = _build_summary(data)
        return data

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def create_pending(
        self,
        *,
        report_type: ReportType,
        report_format: ReportFormat,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> dict:
        """Create a PENDING report record and return it.

        Period defaults are computed from *report_type* when not supplied.
        """
        now = utcnow()
        if period_start is None or period_end is None:
            _map = {
                ReportType.DAILY:    _daily_period,
                ReportType.WEEKLY:   _weekly_period,
                ReportType.MONTHLY:  _monthly_period,
                ReportType.ON_DEMAND: _daily_period,
            }
            period_start, period_end = _map.get(report_type, _daily_period)(now)

        return await self._report_repo.create(
            report_type=report_type.value,
            report_format=report_format.value,
            period_start=period_start,
            period_end=period_end,
        )

    async def generate_background(
        self,
        *,
        report_id: str,
        period_start: datetime,
        period_end: datetime,
        report_format: ReportFormat,
        report_type: str = "on_demand",
    ) -> None:
        """Run full generation for an existing PENDING record.

        Updates the record status to GENERATING → COMPLETE (or FAILED).
        Intended to run as a FastAPI BackgroundTask.
        """
        t0 = time.monotonic()
        try:
            await self._report_repo.update_status(report_id, ReportStatus.GENERATING.value)
            data = await self.gather_report_data(period_start, period_end, report_type)
            ext = report_format.value
            output_path = self._reports_dir / f"{report_id}.{ext}"

            loop = asyncio.get_event_loop()
            if report_format == ReportFormat.PDF:
                await loop.run_in_executor(None, generate_report_pdf, data, str(output_path))
            elif report_format == ReportFormat.CSV:
                await loop.run_in_executor(None, generate_report_csv, data, str(output_path))
            elif report_format == ReportFormat.JSON:
                await loop.run_in_executor(None, generate_report_json, data, str(output_path))

            ms = int((time.monotonic() - t0) * 1000)
            size = output_path.stat().st_size if output_path.exists() else 0
            await self._report_repo.update_complete(
                report_id=report_id,
                file_path=str(output_path),
                file_size=size,
                generation_time_ms=ms,
                summary=data.get("summary") or {},
            )
            logger.info(
                "Report %s (%s) complete in %d ms — %d bytes",
                report_id, ext.upper(), ms, size,
            )
        except Exception as exc:
            logger.exception("Report %s generation failed", report_id)
            await self._report_repo.update_failed(report_id, str(exc))

    # ------------------------------------------------------------------ #
    # Scheduled generation helpers
    # ------------------------------------------------------------------ #

    async def _maybe_generate(
        self,
        report_type: ReportType,
        period_start: datetime,
        period_end: datetime,
    ) -> dict | None:
        """Generate *report_type* if no successful/pending one exists for today."""
        today = period_start.date()
        existing = await self._report_repo.find_by_type_and_period_start(
            report_type.value, today
        )
        if existing:
            logger.debug("Skipping scheduled %s: already generated", report_type.value)
            return None

        record = await self.create_pending(
            report_type=report_type,
            report_format=ReportFormat.PDF,
            period_start=period_start,
            period_end=period_end,
        )
        await self.generate_background(
            report_id=record["id"],
            period_start=period_start,
            period_end=period_end,
            report_format=ReportFormat.PDF,
            report_type=report_type.value,
        )
        return await self._report_repo.get_by_id(record["id"])

    async def generate_scheduled_daily(self) -> dict | None:
        """Generate today's daily report if not already done."""
        now = utcnow()
        return await self._maybe_generate(
            ReportType.DAILY,
            period_start=now - timedelta(days=1),
            period_end=now,
        )

    async def generate_scheduled_weekly(self) -> dict | None:
        """Generate this week's report if not already done."""
        now = utcnow()
        return await self._maybe_generate(
            ReportType.WEEKLY,
            period_start=now - timedelta(days=7),
            period_end=now,
        )

    async def generate_scheduled_monthly(self) -> dict | None:
        """Generate this month's report if not already done."""
        now = utcnow()
        return await self._maybe_generate(
            ReportType.MONTHLY,
            period_start=now - timedelta(days=30),
            period_end=now,
        )

    # ------------------------------------------------------------------ #
    # Read operations (delegated to repository)
    # ------------------------------------------------------------------ #

    async def list_reports(self, limit: int = 100) -> list[dict]:
        return await self._report_repo.list_all(limit)

    async def get_report(self, report_id: str) -> dict | None:
        return await self._report_repo.get_by_id(report_id)

    async def delete_report(self, report_id: str) -> bool:
        record = await self._report_repo.get_by_id(report_id)
        if not record:
            return False
        # Delete the file if it exists
        if record.get("file_path"):
            try:
                fp = Path(record["file_path"])
                if fp.exists():
                    fp.unlink()
            except Exception as exc:
                logger.warning("Could not delete report file %s: %s", record["file_path"], exc)
        return await self._report_repo.delete(report_id)
