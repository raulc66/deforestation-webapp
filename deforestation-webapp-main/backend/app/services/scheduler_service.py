"""Background ingestion scheduler — asyncio-native, in-process, zero external deps.

Each cycle runs registered ingestion providers independently, records
per-provider telemetry, then refreshes intelligence when ingestion completes.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.ingestion.provider_contract import IngestionProvider
    from app.modules.analytics.analytics_service import AnalyticsService
    from app.modules.analytics.intelligence_events_service import IntelligenceEventsService
    from app.modules.analytics.risk_service import RiskService
    from app.modules.ingestion.providers.firms import FIRMSProvider
    from app.modules.reports.report_service import ReportService
    from app.repositories.forest_event_repository import ForestEventRepository
    from app.repositories.ingestion_runs_repository import IngestionRunsRepository
    from app.repositories.provider_health_repository import ProviderHealthRepository
    from app.services.forest_event_service import ForestEventService
    from app.services.intelligence_notification_service import IntelligenceNotificationService
    from app.services.customer_alert_notification_service import CustomerAlertNotificationService
    from app.services.reconciliation_advisory_lock import ReconciliationAdvisoryLock
    from app.services.forest_context_service import ForestContextService
    from app.services.weather_service import WeatherService

from app.core.ingestion.provider_health import health_status_from_run

logger = logging.getLogger("forestwatch.scheduler")

_FIRMS_SOURCE = "NASA FIRMS"


class SchedulerService:
    """Periodic multi-provider ingestion + intelligence refresh, driven by asyncio."""

    def __init__(
        self,
        *,
        firms_provider: FIRMSProvider,
        events_service: ForestEventService,
        events_repo: ForestEventRepository,
        analytics_service: AnalyticsService,
        intelligence_service: IntelligenceEventsService,
        runs_repo: IngestionRunsRepository,
        poll_interval_minutes: int = 60,
        enabled: bool = True,
        firms_source_id: str | None = None,
        notification_svc: IntelligenceNotificationService | None = None,
        customer_alert_svc: "CustomerAlertNotificationService | None" = None,
        risk_svc: RiskService | None = None,
        weather_svc: WeatherService | None = None,
        forest_context_svc: ForestContextService | None = None,
        report_svc: ReportService | None = None,
        enable_scheduled_reports: bool = True,
        reconciliation_lock: ReconciliationAdvisoryLock | None = None,
        ingestion_providers: list["IngestionProvider"] | None = None,
        health_repo: "ProviderHealthRepository | None" = None,
    ) -> None:
        self._firms = firms_provider
        self._ingestion_providers = ingestion_providers
        self._events_service = events_service
        self._events_repo = events_repo
        self._analytics = analytics_service
        self._intel = intelligence_service
        self._runs = runs_repo
        self._health = health_repo
        self._interval_seconds: int = poll_interval_minutes * 60
        self._enabled: bool = enabled
        self._firms_source_id: str | None = firms_source_id
        self._notification_svc: IntelligenceNotificationService | None = notification_svc
        self._customer_alert_svc: CustomerAlertNotificationService | None = customer_alert_svc
        self._risk_svc: RiskService | None = risk_svc
        self._weather_svc: WeatherService | None = weather_svc
        self._forest_context_svc: ForestContextService | None = forest_context_svc
        self._report_svc: ReportService | None = report_svc
        self._enable_scheduled_reports: bool = enable_scheduled_reports
        self._reconciliation_lock: ReconciliationAdvisoryLock | None = reconciliation_lock
        self._task: asyncio.Task | None = None
        self._prev_active_events: dict[str, dict] = {}
        self._prev_customer_alert_active: dict[str, dict] = {}
        self._prev_reliability_critical: bool = False

    async def start(self) -> None:
        if not self._enabled:
            logger.info("Background ingestion disabled — scheduler not started")
            return
        if self._task is not None and not self._task.done():
            logger.warning("Scheduler already running — ignoring duplicate start()")
            return
        logger.info(
            "Starting background ingestion scheduler (interval=%d s)", self._interval_seconds
        )
        self._task = asyncio.create_task(self._loop(), name="ingestion-scheduler-loop")

    async def stop(self) -> None:
        if self._task is None or self._task.done():
            return
        logger.info("Stopping background ingestion scheduler")
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("Scheduler stopped cleanly")

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _loop(self) -> None:
        while True:
            try:
                await self._run_cycle()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Unexpected error in scheduler loop — will retry after interval"
                )
            try:
                await asyncio.sleep(self._interval_seconds)
            except asyncio.CancelledError:
                raise

    async def _run_cycle(self) -> dict:
        started_at = datetime.now(timezone.utc)
        cycle_id = str(uuid.uuid4())
        logger.info("Scheduler cycle starting (cycle_id=%s)", cycle_id)

        providers = self._ingestion_providers or [self._firms]
        provider_results: list[dict] = []

        for provider in providers:
            result = await self._run_provider(provider, started_at, cycle_id)
            provider_results.append(result)

        if self._weather_svc is not None:
            try:
                await self._weather_svc.refresh_if_stale()
            except Exception:
                logger.exception("Weather refresh failed — ingestion cycle continues")

        if self._forest_context_svc is not None:
            try:
                await self._forest_context_svc.refresh_if_stale()
            except Exception:
                logger.exception("CLMS context refresh failed — ingestion cycle continues")

        reconciliation_error: str | None = None
        try:
            await self._reconcile_intelligence_with_lock(intelligence_cycle_id=cycle_id)
        except Exception as exc:
            reconciliation_error = str(exc)
            logger.exception("Intelligence reconciliation failed")

        if self._risk_svc is not None:
            try:
                await self._risk_svc.persist_snapshot()
            except Exception:
                logger.exception("Risk snapshot failed — ingestion cycle continues")

        if self._customer_alert_svc is not None:
            try:
                await self._send_customer_alerts()
            except Exception:
                logger.exception("Customer alert dispatch failed — ingestion cycle continues")

        if self._notification_svc and self._notification_svc.is_enabled:
            try:
                await self._send_notifications()
            except Exception:
                logger.exception("Notification dispatch failed — ingestion cycle continues")

        if self._report_svc is not None and self._enable_scheduled_reports:
            now = datetime.now(timezone.utc)
            for generator, label in (
                (self._report_svc.generate_scheduled_daily, "daily"),
                (self._report_svc.generate_scheduled_weekly, "weekly"),
                (self._report_svc.generate_scheduled_monthly, "monthly"),
            ):
                try:
                    if label == "weekly" and now.weekday() != 0:
                        continue
                    if label == "monthly" and now.day != 1:
                        continue
                    await generator()
                except Exception:
                    logger.exception("Scheduled %s report failed", label)

        completed_at = datetime.now(timezone.utc)
        any_success = any(r.get("status") == "success" for r in provider_results)
        cycle_status = "success" if any_success and reconciliation_error is None else "failed"

        summary = await self._runs.create_run(
            started_at=started_at,
            completed_at=completed_at,
            source="scheduler.cycle",
            provider_id="scheduler.cycle",
            status=cycle_status,
            events_fetched=sum(r.get("events_fetched", 0) for r in provider_results),
            events_inserted=sum(r.get("events_inserted", 0) for r in provider_results),
            duplicates_skipped=sum(r.get("duplicates_skipped", 0) for r in provider_results),
            observations_rejected=sum(r.get("observations_rejected", 0) for r in provider_results),
            error=reconciliation_error,
            cycle_id=cycle_id,
        )

        logger.info(
            "Scheduler cycle complete — providers=%d status=%s duration=%.2fs",
            len(provider_results),
            cycle_status,
            summary.get("duration_seconds", 0),
        )
        return summary

    async def _run_provider(
        self,
        provider: "IngestionProvider",
        cycle_started_at: datetime,
        cycle_id: str,
    ) -> dict:
        provider_started = datetime.now(timezone.utc)
        source_id = self._firms_source_id if provider is self._firms else None
        try:
            result = await provider.run(
                self._events_service,
                self._events_repo,
                source_id,
            )
            completed_at = datetime.now(timezone.utc)
            run_doc = await self._runs.create_run(
                started_at=provider_started,
                completed_at=completed_at,
                source=provider.source_name,
                provider_id=provider.provider_id,
                status="success",
                events_fetched=result.get("total", 0),
                events_inserted=result.get("created", 0),
                duplicates_skipped=result.get("skipped", 0),
                observations_rejected=result.get("errors", 0),
                cycle_id=cycle_id,
            )
            await self._record_health(
                provider,
                success=True,
                started_at=provider_started,
                completed_at=completed_at,
                result=result,
            )
            return run_doc
        except Exception as exc:
            completed_at = datetime.now(timezone.utc)
            error_msg = str(exc)
            logger.error(
                "Provider %s failed: %s", provider.provider_id, error_msg, exc_info=True
            )
            run_doc = await self._runs.create_run(
                started_at=provider_started,
                completed_at=completed_at,
                source=provider.source_name,
                provider_id=provider.provider_id,
                status="failed",
                error=error_msg,
                cycle_id=cycle_id,
            )
            await self._record_health(
                provider,
                success=False,
                started_at=provider_started,
                completed_at=completed_at,
                result={"total": 0, "created": 0, "skipped": 0, "errors": 0},
                error=error_msg,
            )
            return run_doc

    async def _record_health(
        self,
        provider: "IngestionProvider",
        *,
        success: bool,
        started_at: datetime,
        completed_at: datetime,
        result: dict,
        error: str | None = None,
    ) -> None:
        if self._health is None:
            return
        existing = await self._health.get(provider.provider_id) or {}
        consecutive = 0 if success else int(existing.get("consecutive_failures", 0)) + 1
        status = health_status_from_run(
            success=success,
            observations_rejected=int(result.get("errors", 0)),
            observations_received=int(result.get("total", 0)),
            consecutive_failures=consecutive,
            enabled=True,
        )
        await self._health.record_run_outcome(
            provider_id=provider.provider_id,
            display_name=provider.source_name,
            success=success,
            started_at=started_at,
            completed_at=completed_at,
            observations_received=int(result.get("total", 0)),
            observations_persisted=int(result.get("created", 0)),
            observations_rejected=int(result.get("errors", 0)),
            current_status=status,
            error=error,
            last_execution_mode=getattr(provider, "last_execution_mode", None),
        )

    async def _reconcile_intelligence_with_lock(
        self,
        *,
        intelligence_cycle_id: str | None = None,
    ) -> None:
        if self._reconciliation_lock is None:
            await self._analytics.reconcile_intelligence_events(
                self._intel,
                intelligence_cycle_id=intelligence_cycle_id,
            )
            return

        acquired = await self._reconciliation_lock.try_acquire()
        if not acquired:
            logger.info(
                "Reconciliation lock contention — skipping intelligence refresh for this cycle"
            )
            return

        logger.info(
            "Reconciliation lock acquired (holder=%s) — starting intelligence refresh",
            self._reconciliation_lock.holder_id,
        )
        try:
            await self._analytics.reconcile_intelligence_events(
                self._intel,
                intelligence_cycle_id=intelligence_cycle_id,
            )
            logger.info("Intelligence reconciliation completed")
        except Exception:
            logger.exception("Intelligence reconciliation failed")
            raise
        finally:
            released = await self._reconciliation_lock.release()
            if not released:
                logger.warning("Reconciliation lock release did not update holder record")

    async def _send_notifications(self) -> None:
        assert self._notification_svc is not None
        intel = await self._intel.get_events()
        current_active: dict[str, dict] = {
            e["id"]: e for e in intel.get("active", [])
        }
        alerts_result = await self._analytics.get_alerts()
        await self._notification_svc.dispatch_cycle_notifications(
            current_active=current_active,
            prev_active=self._prev_active_events,
            alerts_result=alerts_result,
            prev_reliability_critical=self._prev_reliability_critical,
        )
        self._prev_active_events = current_active
        rel_alerts = [
            a for a in alerts_result.get("alerts", []) if a.get("type") == "reliability"
        ]
        self._prev_reliability_critical = (
            rel_alerts[0].get("severity") == "critical" if rel_alerts else False
        )

    async def _send_customer_alerts(self) -> None:
        assert self._customer_alert_svc is not None
        intel = await self._intel.get_events()
        active = list(intel.get("active") or [])
        current_active = {str(e.get("id")): e for e in active if e.get("id")}
        # Customer alerting keeps its own previous-cycle snapshot so resolution
        # detection does not depend on the operator notification service.
        disappeared = set(self._prev_customer_alert_active) - set(current_active)
        resolved_events: list[dict] = [
            {**self._prev_customer_alert_active[event_id], "status": "resolved"}
            for event_id in disappeared
        ]
        self._prev_customer_alert_active = current_active
        health_rows: list[dict] = []
        if self._health is not None:
            try:
                health_rows = await self._health.list_all()
            except Exception:
                health_rows = []
        await self._customer_alert_svc.run_post_reconciliation(
            active_events=active,
            resolved_events=resolved_events,
            health_rows=health_rows,
        )
