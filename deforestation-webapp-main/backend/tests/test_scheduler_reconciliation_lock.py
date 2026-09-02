"""WP7 — scheduler reconciliation lock integration and concurrency tests."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, ANY

import pytest

from app.models.base import utcnow
from app.services.reconciliation_advisory_lock import ReconciliationAdvisoryLock
from app.services.scheduler_service import SchedulerService
from tests.fixtures.fake_reconciliation_lock_collection import make_lock_repository
from tests.test_scheduler import _make_analytics, _make_firms, _make_runs_repo, _make_scheduler


def _make_lock(holder_id: str, lease_seconds: int = 300) -> ReconciliationAdvisoryLock:
    return ReconciliationAdvisoryLock(
        make_lock_repository(),
        holder_id=holder_id,
        lease_seconds=lease_seconds,
    )


class TestSchedulerReconciliationLockIntegration:
    @pytest.mark.anyio
    async def test_reconcile_runs_when_lock_acquired(self):
        analytics = _make_analytics()
        intel_svc = AsyncMock()
        lock = _make_lock("scheduler-a")
        svc = _make_scheduler(
            analytics=analytics,
            intelligence_service=intel_svc,
            reconciliation_lock=lock,
        )
        await svc._run_cycle()
        analytics.reconcile_intelligence_events.assert_called_once_with(
            intel_svc, intelligence_cycle_id=ANY
        )
        assert lock.held is False

    @pytest.mark.anyio
    async def test_reconcile_skipped_when_lock_not_acquired(self):
        shared_repo = make_lock_repository()
        analytics = _make_analytics()
        intel_svc = AsyncMock()
        lock = ReconciliationAdvisoryLock(
            shared_repo, holder_id="scheduler-a", lease_seconds=300
        )
        assert await lock.try_acquire()

        other = _make_scheduler(
            analytics=analytics,
            intelligence_service=intel_svc,
            reconciliation_lock=ReconciliationAdvisoryLock(
                shared_repo, holder_id="scheduler-b", lease_seconds=300
            ),
        )
        await other._run_cycle()

        analytics.reconcile_intelligence_events.assert_not_called()
        await lock.release()

    @pytest.mark.anyio
    async def test_lock_released_after_successful_reconciliation(self):
        lock = _make_lock("scheduler-a")
        svc = _make_scheduler(reconciliation_lock=lock)
        await svc._run_cycle()
        assert lock.held is False
        doc = await lock._repo.get_lock(lock._lock_id)
        assert doc["expires_at"] <= utcnow()

    @pytest.mark.anyio
    async def test_lock_released_after_reconciliation_failure(self):
        analytics = _make_analytics(reconcile_error=RuntimeError("reconcile boom"))
        lock = _make_lock("scheduler-a")
        svc = _make_scheduler(analytics=analytics, reconciliation_lock=lock)
        await svc._run_cycle()
        assert lock.held is False

    @pytest.mark.anyio
    async def test_skipped_reconciliation_still_completes_cycle(self):
        shared_repo = make_lock_repository()
        lock = ReconciliationAdvisoryLock(
            shared_repo, holder_id="scheduler-a", lease_seconds=300
        )
        assert await lock.try_acquire()
        runs_repo = _make_runs_repo()
        svc = _make_scheduler(
            runs_repo=runs_repo,
            reconciliation_lock=ReconciliationAdvisoryLock(
                shared_repo, holder_id="scheduler-b", lease_seconds=300
            ),
        )
        result = await svc._run_cycle()
        assert result["status"] == "success"
        assert runs_repo.create_run.call_count >= 1
        await lock.release()

    @pytest.mark.anyio
    async def test_later_cycle_acquires_after_prior_release(self):
        lock_a = _make_lock("scheduler-a")
        lock_b = _make_lock("scheduler-b")
        analytics = _make_analytics()

        svc_a = _make_scheduler(analytics=analytics, reconciliation_lock=lock_a)
        svc_b = _make_scheduler(analytics=analytics, reconciliation_lock=lock_b)

        await svc_a._run_cycle()
        await svc_b._run_cycle()

        assert analytics.reconcile_intelligence_events.call_count == 2

    @pytest.mark.anyio
    async def test_concurrent_cycles_only_one_reconciles(self):
        shared_repo = make_lock_repository()
        lock_a = ReconciliationAdvisoryLock(
            shared_repo, holder_id="scheduler-a", lease_seconds=300
        )
        lock_b = ReconciliationAdvisoryLock(
            shared_repo, holder_id="scheduler-b", lease_seconds=300
        )

        reconcile_started = asyncio.Event()
        reconcile_release = asyncio.Event()
        call_count = 0

        async def slow_reconcile(_intel, **kwargs):
            nonlocal call_count
            call_count += 1
            reconcile_started.set()
            await reconcile_release.wait()
            return {"active": [], "resolved": []}

        analytics = _make_analytics()
        analytics.reconcile_intelligence_events = AsyncMock(side_effect=slow_reconcile)

        firms = _make_firms()
        runs_repo = _make_runs_repo()

        async def run_cycle(lock):
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
                reconciliation_lock=lock,
            )
            return await scheduler._run_cycle()

        task_a = asyncio.create_task(run_cycle(lock_a))
        await asyncio.wait_for(reconcile_started.wait(), timeout=2.0)

        task_b = asyncio.create_task(run_cycle(lock_b))
        await asyncio.sleep(0.05)
        reconcile_release.set()

        await asyncio.gather(task_a, task_b)
        assert call_count == 1

    @pytest.mark.anyio
    async def test_stale_lock_allows_recovery_after_crash(self):
        repo = make_lock_repository()
        crashed = ReconciliationAdvisoryLock(
            repo, holder_id="crashed", lease_seconds=2
        )
        assert await crashed.try_acquire()

        doc = await repo.get_lock(crashed._lock_id)
        expired_at = utcnow() - timedelta(seconds=1)
        fake_col = repo.col
        async with fake_col._mutex:
            fake_col._docs[crashed._lock_id]["expires_at"] = expired_at

        recovery = ReconciliationAdvisoryLock(
            repo, holder_id="recovery", lease_seconds=300
        )
        analytics = _make_analytics()
        svc = _make_scheduler(analytics=analytics, reconciliation_lock=recovery)
        await svc._run_cycle()
        analytics.reconcile_intelligence_events.assert_called_once()

    @pytest.mark.anyio
    async def test_without_lock_scheduler_behaves_as_before(self):
        analytics = _make_analytics()
        svc = _make_scheduler(analytics=analytics, reconciliation_lock=None)
        await svc._run_cycle()
        analytics.reconcile_intelligence_events.assert_called_once()
