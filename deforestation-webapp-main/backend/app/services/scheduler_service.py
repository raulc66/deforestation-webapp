"""Background ingestion scheduler — asyncio-native, in-process, zero external deps.

Architecture
------------
``SchedulerService`` owns a single ``asyncio.Task`` that runs an infinite
cycle::

    loop: run_cycle → sleep(interval) → run_cycle → …

Each cycle:
  1. Fetches and normalises NASA FIRMS events via the existing ``FIRMSProvider``,
     routing every record through the shared deduplication pipeline.
  2. Refreshes intelligence (regional baselines → anomaly detection →
     IntelligenceEvent reconciliation) via the existing service chain.
  3. Logs the outcome — created count, skipped count, duration, errors — to the
     ``ingestion_runs`` MongoDB collection.

Design decisions
----------------
* **No external infrastructure**: pure asyncio tasks, no Celery / Redis / APScheduler.
* **Non-blocking**: ``asyncio.create_task`` returns immediately; FastAPI request
  handling is unaffected.
* **Fully testable**: all collaborators are injected via constructor; ``_run_cycle``
  is a public async method that tests call directly.
* **Graceful shutdown**: ``stop()`` cancels the task and awaits teardown;
  ``asyncio.CancelledError`` is re-raised inside the loop so the task exits cleanly.
* **Idempotent start/stop**: calling ``start()`` twice does not create a second task;
  calling ``stop()`` when not running is a safe no-op.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.analytics.analytics_service import AnalyticsService
    from app.modules.analytics.intelligence_events_service import IntelligenceEventsService
    from app.modules.analytics.risk_service import RiskService
    from app.modules.ingestion.providers.firms import FIRMSProvider
    from app.modules.reports.report_service import ReportService
    from app.repositories.forest_event_repository import ForestEventRepository
    from app.repositories.ingestion_runs_repository import IngestionRunsRepository
    from app.services.forest_event_service import ForestEventService
    from app.services.intelligence_notification_service import IntelligenceNotificationService
    from app.services.weather_service import WeatherService

logger = logging.getLogger("forestwatch.scheduler")

_FIRMS_SOURCE = "NASA FIRMS"


class SchedulerService:
    """Periodic FIRMS ingestion + intelligence refresh, driven by asyncio."""

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
        risk_svc: RiskService | None = None,
        weather_svc: WeatherService | None = None,
        report_svc: ReportService | None = None,
        enable_scheduled_reports: bool = True,
    ) -> None:
        self._firms = firms_provider
        self._events_service = events_service
        self._events_repo = events_repo
        self._analytics = analytics_service
        self._intel = intelligence_service
        self._runs = runs_repo
        self._interval_seconds: int = poll_interval_minutes * 60
        self._enabled: bool = enabled
        self._firms_source_id: str | None = firms_source_id
        self._notification_svc: IntelligenceNotificationService | None = notification_svc
        self._risk_svc: RiskService | None = risk_svc
        self._weather_svc: WeatherService | None = weather_svc
        self._report_svc: ReportService | None = report_svc
        self._enable_scheduled_reports: bool = enable_scheduled_reports
        self._task: asyncio.Task | None = None
        # Tracks the previous cycle's active event state for notification diffing
        self._prev_active_events: dict[str, dict] = {}
        self._prev_reliability_critical: bool = False

    # ------------------------------------------------------------------ #
    # Public lifecycle API
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        """Spawn the background ingestion loop.

        No-op when:
          * ``enabled`` is ``False`` (e.g. ``ENABLE_BACKGROUND_INGESTION=false``).
          * The task is already running (prevents duplicate tasks on double-start).
        """
        if not self._enabled:
            logger.info("Background ingestion disabled — scheduler not started")
            return
        if self._task is not None and not self._task.done():
            logger.warning("Scheduler already running — ignoring duplicate start()")
            return
        logger.info(
            "Starting background ingestion scheduler (interval=%d s)", self._interval_seconds
        )
        self._task = asyncio.create_task(self._loop(), name="firms-ingestion-loop")

    async def stop(self) -> None:
        """Cancel the background task and wait for clean teardown.

        Safe to call when the scheduler was never started or is already stopped.
        """
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
        """``True`` when the background task exists and has not finished."""
        return self._task is not None and not self._task.done()

    # ------------------------------------------------------------------ #
    # Internal loop
    # ------------------------------------------------------------------ #

    async def _loop(self) -> None:
        """Infinite cycle: run_cycle → sleep → run_cycle → …

        ``asyncio.CancelledError`` is re-raised unconditionally so ``stop()``
        can await a clean exit.  Other exceptions are logged and swallowed so
        a transient network error does not terminate the scheduler permanently.
        """
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

    # ------------------------------------------------------------------ #
    # Run cycle — the testable unit of work
    # ------------------------------------------------------------------ #

    async def _run_cycle(self) -> dict:
        """Execute one full FIRMS ingestion + intelligence refresh cycle.

        Sequence
        --------
        1. Call ``FIRMSProvider.run()`` — fetch → normalise → dedupe → persist.
        2. Call ``AnalyticsService.reconcile_intelligence_events()`` — baselines
           → anomaly detection → IntelligenceEvent upsert/resolve.
        3. Write an ``ingestion_runs`` document (status="success").

        On any exception (step 1 or 2):
        * Skip the intelligence refresh (step 2 is not reached if step 1 fails).
        * Write a "failed" run document and re-raise so ``_loop`` can log it.

        Returns
        -------
        dict
            The persisted run document (used in tests and the log line).
        """
        started_at = datetime.now(timezone.utc)
        logger.info("Scheduler cycle starting")

        try:
            # Step 1 — FIRMS ingestion (includes deduplication via persist_import_event)
            firms_result = await self._firms.run(
                self._events_service,
                self._events_repo,
                self._firms_source_id,
            )

            # Step 2 — weather refresh (best-effort; populates cache for risk engine)
            if self._weather_svc is not None:
                try:
                    await self._weather_svc.refresh_if_stale()
                except Exception:
                    logger.exception(
                        "Weather refresh failed — ingestion cycle continues"
                    )

            # Step 3 — intelligence refresh (reuses existing service chain)
            await self._analytics.reconcile_intelligence_events(self._intel)

            # Step 4 — fire risk snapshot (best-effort; one snapshot per UTC day)
            if self._risk_svc is not None:
                try:
                    await self._risk_svc.persist_snapshot()
                except Exception:
                    logger.exception(
                        "Risk snapshot failed — ingestion cycle continues"
                    )

            # Step 5 — outbound notifications (best-effort; after risk is updated)
            if self._notification_svc and self._notification_svc.is_enabled:
                try:
                    await self._send_notifications()
                except Exception:
                    logger.exception(
                        "Notification dispatch failed — ingestion cycle continues"
                    )

            # Step 6 — scheduled report generation (daily every cycle; weekly on
            # Monday; monthly on the 1st) — fully best-effort
            if self._report_svc is not None and self._enable_scheduled_reports:
                now = datetime.now(timezone.utc)
                try:
                    await self._report_svc.generate_scheduled_daily()
                except Exception:
                    logger.exception("Scheduled daily report failed")
                try:
                    if now.weekday() == 0:  # Monday
                        await self._report_svc.generate_scheduled_weekly()
                except Exception:
                    logger.exception("Scheduled weekly report failed")
                try:
                    if now.day == 1:  # First of the month
                        await self._report_svc.generate_scheduled_monthly()
                except Exception:
                    logger.exception("Scheduled monthly report failed")

            completed_at = datetime.now(timezone.utc)

            # Step 3 — persist run metadata
            run = await self._runs.create_run(
                started_at=started_at,
                completed_at=completed_at,
                source=_FIRMS_SOURCE,
                status="success",
                events_fetched=firms_result.get("total", 0),
                events_inserted=firms_result.get("created", 0),
                duplicates_skipped=firms_result.get("skipped", 0),
                error=None,
            )

            logger.info(
                "Scheduler cycle complete — fetched=%d inserted=%d skipped=%d duration=%.2fs",
                run["events_fetched"],
                run["events_inserted"],
                run["duplicates_skipped"],
                run["duration_seconds"],
            )
            return run

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            completed_at = datetime.now(timezone.utc)
            error_msg = str(exc)
            logger.error("Scheduler cycle failed: %s", error_msg, exc_info=True)

            # Best-effort: log the failure run.  If this also fails, just return {}.
            try:
                return await self._runs.create_run(
                    started_at=started_at,
                    completed_at=completed_at,
                    source=_FIRMS_SOURCE,
                    status="failed",
                    error=error_msg,
                )
            except Exception:
                logger.exception("Failed to persist failure run record")
                return {}

    # ------------------------------------------------------------------ #
    # Notification dispatch — separated for testability
    # ------------------------------------------------------------------ #

    async def _send_notifications(self) -> None:
        """Fetch current intelligence state and dispatch change notifications.

        Compares the current active event set to the state from the previous
        cycle (``_prev_active_events``) to detect new events and escalation
        changes.  Updates the stored state at the end of each call.
        """
        assert self._notification_svc is not None  # guarded by caller

        # Fetch current active events
        intel = await self._intel.get_events()
        current_active: dict[str, dict] = {
            e["id"]: e for e in intel.get("active", [])
        }

        # Fetch current alerts for reliability alert detection
        alerts_result = await self._analytics.get_alerts()

        await self._notification_svc.dispatch_cycle_notifications(
            current_active=current_active,
            prev_active=self._prev_active_events,
            alerts_result=alerts_result,
            prev_reliability_critical=self._prev_reliability_critical,
        )

        # Update stored state for the next cycle comparison
        self._prev_active_events = current_active
        rel_alerts = [
            a
            for a in alerts_result.get("alerts", [])
            if a.get("type") == "reliability"
        ]
        self._prev_reliability_critical = (
            rel_alerts[0].get("severity") == "critical" if rel_alerts else False
        )
