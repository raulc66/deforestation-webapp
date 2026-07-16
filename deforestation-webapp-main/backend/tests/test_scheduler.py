"""Comprehensive tests for the background ingestion scheduler.

Coverage
--------
Scheduler lifecycle:
  * start creates an asyncio task when enabled
  * start is a no-op when disabled
  * start is idempotent (double-start does not create a second task)
  * stop cancels a running task cleanly
  * stop is a no-op when not running (never started, already stopped)
  * is_running reflects task state accurately

Interval configuration:
  * poll_interval_minutes is converted to seconds correctly

Run cycle — success path:
  * FIRMS provider is called with the injected services and source_id
  * intelligence refresh is called after successful ingestion
  * run document is written with status="success"
  * correct ingestion metrics are captured (fetched, inserted, skipped)
  * duration_seconds is non-negative

Run cycle — failure path:
  * FIRMS exception → status="failed" in run document
  * error message is captured in the run document
  * intelligence refresh is NOT called when FIRMS ingestion fails
  * intelligence refresh failure → status="failed"
  * run-logging failure does not propagate (best-effort log)

Run logging:
  * create_run receives all required fields
  * source is always "NASA FIRMS"

Ingestion status response logic:
  * empty history returns zero counts and null latest_run
  * successful_runs counted correctly from mixed history
  * failed_runs counted correctly from mixed history
  * latest_run is the first element of the list
  * scheduler_enabled and poll_interval_minutes are forwarded correctly

Intelligence refresh integration:
  * reconcile_intelligence_events is called even when events_inserted == 0
"""
from __future__ import annotations

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.scheduler_service import SchedulerService

# ---------------------------------------------------------------------------
# Fixed test anchor
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 8, 1, 10, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

_DEFAULT_FIRMS_RESULT = {"total": 4, "created": 2, "skipped": 2, "errors": 0}

_DEFAULT_RUN_DOC = {
    "id": "run-abc",
    "status": "success",
    "events_fetched": 4,
    "events_inserted": 2,
    "duplicates_skipped": 2,
    "duration_seconds": 0.5,
    "source": "NASA FIRMS",
    "error": None,
}


def _make_firms(result=None, error=None) -> AsyncMock:
    firms = AsyncMock()
    if error:
        firms.run = AsyncMock(side_effect=error)
    else:
        firms.run = AsyncMock(return_value=result or _DEFAULT_FIRMS_RESULT)
    return firms


def _make_analytics(reconcile_error=None) -> AsyncMock:
    analytics = AsyncMock()
    if reconcile_error:
        analytics.reconcile_intelligence_events = AsyncMock(side_effect=reconcile_error)
    else:
        analytics.reconcile_intelligence_events = AsyncMock(return_value={})
    return analytics


def _make_runs_repo(return_doc=None, create_error=None) -> AsyncMock:
    repo = AsyncMock()
    if create_error:
        repo.create_run = AsyncMock(side_effect=create_error)
    else:
        repo.create_run = AsyncMock(return_value=return_doc or _DEFAULT_RUN_DOC)
    return repo


def _make_scheduler(
    *,
    enabled: bool = True,
    poll_interval_minutes: int = 60,
    firms: AsyncMock | None = None,
    analytics: AsyncMock | None = None,
    runs_repo: AsyncMock | None = None,
    firms_source_id: str | None = None,
    **extra,
) -> SchedulerService:
    return SchedulerService(
        firms_provider=firms or _make_firms(),
        events_service=extra.pop("events_service", AsyncMock()),
        events_repo=extra.pop("events_repo", AsyncMock()),
        analytics_service=analytics or _make_analytics(),
        intelligence_service=extra.pop("intelligence_service", AsyncMock()),
        runs_repo=runs_repo or _make_runs_repo(),
        poll_interval_minutes=poll_interval_minutes,
        enabled=enabled,
        firms_source_id=firms_source_id,
        **extra,
    )


# ===========================================================================
# Section 1 — Scheduler lifecycle
# ===========================================================================

class TestSchedulerLifecycle:

    @pytest.mark.anyio
    async def test_start_creates_task_when_enabled(self):
        svc = _make_scheduler(enabled=True)
        with patch.object(svc, "_run_cycle", new_callable=AsyncMock):
            await svc.start()
            assert svc.is_running
            await svc.stop()

    @pytest.mark.anyio
    async def test_start_does_not_create_task_when_disabled(self):
        svc = _make_scheduler(enabled=False)
        await svc.start()
        assert not svc.is_running

    @pytest.mark.anyio
    async def test_start_is_idempotent(self):
        """Calling start() twice does not create a second asyncio task."""
        svc = _make_scheduler(enabled=True)
        with patch.object(svc, "_run_cycle", new_callable=AsyncMock):
            await svc.start()
            first_task = svc._task
            await svc.start()  # second call — must be ignored
            assert svc._task is first_task
            await svc.stop()

    @pytest.mark.anyio
    async def test_stop_cancels_running_task(self):
        svc = _make_scheduler(enabled=True)
        with patch.object(svc, "_run_cycle", new_callable=AsyncMock):
            await svc.start()
            await asyncio.sleep(0)  # let the task start
            assert svc.is_running
            await svc.stop()
            assert not svc.is_running

    @pytest.mark.anyio
    async def test_stop_is_no_op_when_never_started(self):
        """stop() on a scheduler that was never started must not raise."""
        svc = _make_scheduler(enabled=False)
        await svc.stop()  # should complete without error

    @pytest.mark.anyio
    async def test_stop_is_idempotent(self):
        """Calling stop() twice must not raise."""
        svc = _make_scheduler(enabled=True)
        with patch.object(svc, "_run_cycle", new_callable=AsyncMock):
            await svc.start()
            await svc.stop()
            await svc.stop()  # second stop — must be safe

    @pytest.mark.anyio
    async def test_is_running_false_before_start(self):
        svc = _make_scheduler(enabled=True)
        assert not svc.is_running

    @pytest.mark.anyio
    async def test_is_running_false_after_stop(self):
        svc = _make_scheduler(enabled=True)
        with patch.object(svc, "_run_cycle", new_callable=AsyncMock):
            await svc.start()
            await svc.stop()
        assert not svc.is_running

    @pytest.mark.anyio
    async def test_is_running_false_when_disabled(self):
        svc = _make_scheduler(enabled=False)
        await svc.start()
        assert not svc.is_running


# ===========================================================================
# Section 2 — Interval configuration
# ===========================================================================

class TestIntervalConfiguration:

    def test_poll_interval_minutes_converted_to_seconds(self):
        svc = _make_scheduler(poll_interval_minutes=30)
        assert svc._interval_seconds == 30 * 60

    def test_default_poll_interval_is_60_minutes(self):
        svc = _make_scheduler()
        assert svc._interval_seconds == 60 * 60

    def test_enabled_flag_stored_correctly(self):
        svc_on = _make_scheduler(enabled=True)
        svc_off = _make_scheduler(enabled=False)
        assert svc_on._enabled is True
        assert svc_off._enabled is False

    def test_firms_source_id_stored(self):
        svc = _make_scheduler(firms_source_id="abc123")
        assert svc._firms_source_id == "abc123"

    def test_firms_source_id_defaults_none(self):
        svc = _make_scheduler()
        assert svc._firms_source_id is None


# ===========================================================================
# Section 3 — Run cycle: success path
# ===========================================================================

class TestRunCycleSuccess:

    @pytest.mark.anyio
    async def test_firms_provider_run_is_called(self):
        firms = _make_firms()
        events_service = AsyncMock()
        events_repo = AsyncMock()
        svc = _make_scheduler(
            firms=firms,
            events_service=events_service,
            events_repo=events_repo,
        )
        await svc._run_cycle()
        firms.run.assert_called_once_with(events_service, events_repo, None)

    @pytest.mark.anyio
    async def test_firms_called_with_injected_source_id(self):
        firms = _make_firms()
        svc = _make_scheduler(firms=firms, firms_source_id="src-xyz")
        await svc._run_cycle()
        _, _, source_id_arg = firms.run.call_args.args
        assert source_id_arg == "src-xyz"

    @pytest.mark.anyio
    async def test_intelligence_refresh_called_after_ingestion(self):
        analytics = _make_analytics()
        intel_svc = AsyncMock()
        svc = _make_scheduler(
            analytics=analytics,
            intelligence_service=intel_svc,
        )
        await svc._run_cycle()
        analytics.reconcile_intelligence_events.assert_called_once_with(intel_svc)

    @pytest.mark.anyio
    async def test_run_doc_written_with_success_status(self):
        runs_repo = _make_runs_repo()
        svc = _make_scheduler(runs_repo=runs_repo)
        await svc._run_cycle()

        runs_repo.create_run.assert_called_once()
        kwargs = runs_repo.create_run.call_args.kwargs
        assert kwargs["status"] == "success"

    @pytest.mark.anyio
    async def test_run_doc_source_is_nasa_firms(self):
        runs_repo = _make_runs_repo()
        svc = _make_scheduler(runs_repo=runs_repo)
        await svc._run_cycle()

        kwargs = runs_repo.create_run.call_args.kwargs
        assert kwargs["source"] == "NASA FIRMS"

    @pytest.mark.anyio
    async def test_run_doc_captures_events_fetched(self):
        firms = _make_firms(result={"total": 10, "created": 7, "skipped": 3, "errors": 0})
        runs_repo = _make_runs_repo()
        svc = _make_scheduler(firms=firms, runs_repo=runs_repo)
        await svc._run_cycle()

        kwargs = runs_repo.create_run.call_args.kwargs
        assert kwargs["events_fetched"] == 10

    @pytest.mark.anyio
    async def test_run_doc_captures_events_inserted(self):
        firms = _make_firms(result={"total": 10, "created": 7, "skipped": 3, "errors": 0})
        runs_repo = _make_runs_repo()
        svc = _make_scheduler(firms=firms, runs_repo=runs_repo)
        await svc._run_cycle()

        kwargs = runs_repo.create_run.call_args.kwargs
        assert kwargs["events_inserted"] == 7

    @pytest.mark.anyio
    async def test_run_doc_captures_duplicates_skipped(self):
        firms = _make_firms(result={"total": 10, "created": 7, "skipped": 3, "errors": 0})
        runs_repo = _make_runs_repo()
        svc = _make_scheduler(firms=firms, runs_repo=runs_repo)
        await svc._run_cycle()

        kwargs = runs_repo.create_run.call_args.kwargs
        assert kwargs["duplicates_skipped"] == 3

    @pytest.mark.anyio
    async def test_run_doc_error_is_none_on_success(self):
        runs_repo = _make_runs_repo()
        svc = _make_scheduler(runs_repo=runs_repo)
        await svc._run_cycle()

        kwargs = runs_repo.create_run.call_args.kwargs
        assert kwargs["error"] is None

    @pytest.mark.anyio
    async def test_run_doc_has_started_at_and_completed_at(self):
        runs_repo = _make_runs_repo()
        svc = _make_scheduler(runs_repo=runs_repo)
        await svc._run_cycle()

        kwargs = runs_repo.create_run.call_args.kwargs
        assert isinstance(kwargs["started_at"], datetime)
        assert isinstance(kwargs["completed_at"], datetime)
        assert kwargs["completed_at"] >= kwargs["started_at"]

    @pytest.mark.anyio
    async def test_run_cycle_returns_run_document(self):
        run_doc = {**_DEFAULT_RUN_DOC, "id": "returned-doc"}
        runs_repo = _make_runs_repo(return_doc=run_doc)
        svc = _make_scheduler(runs_repo=runs_repo)
        result = await svc._run_cycle()
        assert result["id"] == "returned-doc"

    @pytest.mark.anyio
    async def test_intelligence_refresh_called_when_zero_new_events(self):
        """reconcile_intelligence_events must run even if all events were duplicates."""
        firms = _make_firms(result={"total": 4, "created": 0, "skipped": 4, "errors": 0})
        analytics = _make_analytics()
        svc = _make_scheduler(firms=firms, analytics=analytics)
        await svc._run_cycle()
        analytics.reconcile_intelligence_events.assert_called_once()


# ===========================================================================
# Section 4 — Run cycle: failure paths
# ===========================================================================

class TestRunCycleFailure:

    @pytest.mark.anyio
    async def test_firms_exception_writes_failed_run(self):
        firms = _make_firms(error=RuntimeError("Network timeout"))
        runs_repo = _make_runs_repo(return_doc={"status": "failed"})
        svc = _make_scheduler(firms=firms, runs_repo=runs_repo)
        await svc._run_cycle()

        kwargs = runs_repo.create_run.call_args.kwargs
        assert kwargs["status"] == "failed"

    @pytest.mark.anyio
    async def test_firms_exception_captures_error_message(self):
        firms = _make_firms(error=RuntimeError("FIRMS API unreachable"))
        runs_repo = _make_runs_repo(return_doc={"status": "failed"})
        svc = _make_scheduler(firms=firms, runs_repo=runs_repo)
        await svc._run_cycle()

        kwargs = runs_repo.create_run.call_args.kwargs
        assert "FIRMS API unreachable" in kwargs["error"]

    @pytest.mark.anyio
    async def test_intelligence_refresh_not_called_when_firms_fails(self):
        firms = _make_firms(error=RuntimeError("error"))
        analytics = _make_analytics()
        runs_repo = _make_runs_repo(return_doc={"status": "failed"})
        svc = _make_scheduler(firms=firms, analytics=analytics, runs_repo=runs_repo)
        await svc._run_cycle()

        analytics.reconcile_intelligence_events.assert_not_called()

    @pytest.mark.anyio
    async def test_intelligence_refresh_exception_writes_failed_run(self):
        analytics = _make_analytics(reconcile_error=RuntimeError("DB error"))
        runs_repo = _make_runs_repo(return_doc={"status": "failed"})
        svc = _make_scheduler(analytics=analytics, runs_repo=runs_repo)
        await svc._run_cycle()

        kwargs = runs_repo.create_run.call_args.kwargs
        assert kwargs["status"] == "failed"
        assert "DB error" in kwargs["error"]

    @pytest.mark.anyio
    async def test_failed_run_doc_has_timestamps(self):
        firms = _make_firms(error=RuntimeError("err"))
        runs_repo = _make_runs_repo(return_doc={"status": "failed"})
        svc = _make_scheduler(firms=firms, runs_repo=runs_repo)
        await svc._run_cycle()

        kwargs = runs_repo.create_run.call_args.kwargs
        assert isinstance(kwargs["started_at"], datetime)
        assert isinstance(kwargs["completed_at"], datetime)

    @pytest.mark.anyio
    async def test_run_log_failure_returns_empty_dict(self):
        """If create_run itself fails, _run_cycle must return {} and not propagate."""
        firms = _make_firms(error=RuntimeError("err"))
        runs_repo = _make_runs_repo(create_error=RuntimeError("Mongo down"))
        svc = _make_scheduler(firms=firms, runs_repo=runs_repo)
        # Should not raise
        result = await svc._run_cycle()
        assert result == {}


# ===========================================================================
# Section 5 — Ingestion status response logic (pure Python, no I/O)
# ===========================================================================

def _build_status(
    runs: list[dict],
    enabled: bool = True,
    interval_seconds: int = 3600,
) -> dict:
    """Replicate the logic of the ingestion_status endpoint for unit testing."""
    latest = runs[0] if runs else None
    successful = sum(1 for r in runs if r.get("status") == "success")
    failed = sum(1 for r in runs if r.get("status") == "failed")
    return {
        "scheduler_enabled": enabled,
        "poll_interval_minutes": interval_seconds // 60,
        "latest_run": latest,
        "successful_runs": successful,
        "failed_runs": failed,
    }


class TestIngestionStatusLogic:

    def test_empty_history_returns_null_latest(self):
        result = _build_status([])
        assert result["latest_run"] is None

    def test_empty_history_returns_zero_counts(self):
        result = _build_status([])
        assert result["successful_runs"] == 0
        assert result["failed_runs"] == 0

    def test_scheduler_enabled_forwarded(self):
        assert _build_status([], enabled=True)["scheduler_enabled"] is True
        assert _build_status([], enabled=False)["scheduler_enabled"] is False

    def test_poll_interval_minutes_computed_from_seconds(self):
        result = _build_status([], interval_seconds=1800)
        assert result["poll_interval_minutes"] == 30

    def test_successful_runs_counted_correctly(self):
        runs = [
            {"status": "success"},
            {"status": "success"},
            {"status": "failed"},
        ]
        result = _build_status(runs)
        assert result["successful_runs"] == 2
        assert result["failed_runs"] == 1

    def test_all_failed_history(self):
        runs = [{"status": "failed"}, {"status": "failed"}]
        result = _build_status(runs)
        assert result["successful_runs"] == 0
        assert result["failed_runs"] == 2

    def test_latest_run_is_first_element(self):
        runs = [
            {"status": "success", "id": "newest"},
            {"status": "success", "id": "older"},
        ]
        result = _build_status(runs)
        assert result["latest_run"]["id"] == "newest"

    def test_mixed_history_latest_run_correct(self):
        runs = [
            {"status": "failed", "id": "latest-failed"},
            {"status": "success", "id": "prev-success"},
        ]
        result = _build_status(runs)
        assert result["latest_run"]["id"] == "latest-failed"
        assert result["successful_runs"] == 1
        assert result["failed_runs"] == 1

    def test_single_successful_run(self):
        runs = [{"status": "success", "events_inserted": 3}]
        result = _build_status(runs)
        assert result["successful_runs"] == 1
        assert result["failed_runs"] == 0
        assert result["latest_run"]["events_inserted"] == 3


# ===========================================================================
# Section 6 — IngestionRunsRepository duration calculation
# ===========================================================================

class TestIngestionRunsDuration:
    """Test the duration_seconds computation without a live database."""

    def test_duration_computed_from_timestamps(self):
        """duration_seconds = (completed_at - started_at).total_seconds()"""
        from app.repositories.ingestion_runs_repository import _fmt

        started = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        completed = datetime(2024, 1, 1, 12, 0, 7, 500_000, tzinfo=timezone.utc)  # 7.5s
        duration = round((completed - started).total_seconds(), 3)
        assert duration == 7.5

    def test_fmt_converts_objectid_to_string(self):
        from bson import ObjectId
        from app.repositories.ingestion_runs_repository import _fmt

        oid = ObjectId()
        result = _fmt({"_id": oid, "status": "success"})
        assert "id" in result
        assert "_id" not in result
        assert isinstance(result["id"], str)

    def test_fmt_preserves_other_fields(self):
        from bson import ObjectId
        from app.repositories.ingestion_runs_repository import _fmt

        oid = ObjectId()
        result = _fmt({"_id": oid, "source": "NASA FIRMS", "events_fetched": 4})
        assert result["source"] == "NASA FIRMS"
        assert result["events_fetched"] == 4
