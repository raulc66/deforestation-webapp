"""WP7 — reconciliation advisory lock tests."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.repositories.reconciliation_lock_repository import ReconciliationLockRepository
from app.services.reconciliation_advisory_lock import (
    INTELLIGENCE_RECONCILIATION_LOCK_ID,
    ReconciliationAdvisoryLock,
)
from tests.fixtures.fake_reconciliation_lock_collection import make_lock_repository

_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _repo_with_fake() -> ReconciliationLockRepository:
    return make_lock_repository()


class TestReconciliationLockRepository:
    @pytest.mark.anyio
    async def test_first_acquire_succeeds(self):
        repo = _repo_with_fake()
        acquired = await repo.try_acquire(
            lock_id=INTELLIGENCE_RECONCILIATION_LOCK_ID,
            holder_id="holder-a",
            acquired_at=_NOW,
            expires_at=_NOW + timedelta(minutes=5),
        )
        assert acquired is True
        doc = await repo.get_lock(INTELLIGENCE_RECONCILIATION_LOCK_ID)
        assert doc["holder_id"] == "holder-a"

    @pytest.mark.anyio
    async def test_second_holder_blocked_while_lock_active(self):
        repo = _repo_with_fake()
        expires = _NOW + timedelta(minutes=5)
        assert await repo.try_acquire(
            lock_id=INTELLIGENCE_RECONCILIATION_LOCK_ID,
            holder_id="holder-a",
            acquired_at=_NOW,
            expires_at=expires,
        )
        assert not await repo.try_acquire(
            lock_id=INTELLIGENCE_RECONCILIATION_LOCK_ID,
            holder_id="holder-b",
            acquired_at=_NOW + timedelta(seconds=1),
            expires_at=expires,
        )

    @pytest.mark.anyio
    async def test_release_allows_next_acquire(self):
        repo = _repo_with_fake()
        lock_id = INTELLIGENCE_RECONCILIATION_LOCK_ID
        await repo.try_acquire(
            lock_id=lock_id,
            holder_id="holder-a",
            acquired_at=_NOW,
            expires_at=_NOW + timedelta(minutes=5),
        )
        released = await repo.release(
            lock_id=lock_id,
            holder_id="holder-a",
            released_at=_NOW + timedelta(seconds=30),
        )
        assert released is True
        assert await repo.try_acquire(
            lock_id=lock_id,
            holder_id="holder-b",
            acquired_at=_NOW + timedelta(seconds=31),
            expires_at=_NOW + timedelta(minutes=6),
        )

    @pytest.mark.anyio
    async def test_wrong_holder_cannot_release(self):
        repo = _repo_with_fake()
        lock_id = INTELLIGENCE_RECONCILIATION_LOCK_ID
        await repo.try_acquire(
            lock_id=lock_id,
            holder_id="holder-a",
            acquired_at=_NOW,
            expires_at=_NOW + timedelta(minutes=5),
        )
        assert not await repo.release(
            lock_id=lock_id,
            holder_id="holder-b",
            released_at=_NOW + timedelta(seconds=10),
        )

    @pytest.mark.anyio
    async def test_stale_lock_recovery_after_lease_expiry(self):
        repo = _repo_with_fake()
        lock_id = INTELLIGENCE_RECONCILIATION_LOCK_ID
        await repo.try_acquire(
            lock_id=lock_id,
            holder_id="crashed-holder",
            acquired_at=_NOW,
            expires_at=_NOW + timedelta(seconds=60),
        )
        later = _NOW + timedelta(minutes=10)
        assert await repo.try_acquire(
            lock_id=lock_id,
            holder_id="recovery-holder",
            acquired_at=later,
            expires_at=later + timedelta(minutes=5),
        )
        doc = await repo.get_lock(lock_id)
        assert doc["holder_id"] == "recovery-holder"

    @pytest.mark.anyio
    async def test_concurrent_acquire_only_one_winner(self):
        repo = _repo_with_fake()
        lock_id = INTELLIGENCE_RECONCILIATION_LOCK_ID
        expires = _NOW + timedelta(minutes=5)

        async def attempt(holder: str) -> bool:
            return await repo.try_acquire(
                lock_id=lock_id,
                holder_id=holder,
                acquired_at=_NOW,
                expires_at=expires,
            )

        results = await asyncio.gather(
            attempt("holder-a"),
            attempt("holder-b"),
        )
        assert sorted(results) == [False, True]

    @pytest.mark.anyio
    async def test_same_holder_can_reacquire_after_release(self):
        repo = _repo_with_fake()
        lock = ReconciliationAdvisoryLock(
            repo, holder_id="holder-a", lease_seconds=300
        )
        assert await lock.try_acquire()
        assert await lock.release()
        assert await lock.try_acquire()


class TestReconciliationAdvisoryLock:
    @pytest.mark.anyio
    async def test_release_after_exception_clears_held_state(self):
        repo = _repo_with_fake()
        lock = ReconciliationAdvisoryLock(
            repo, holder_id="holder-a", lease_seconds=300
        )
        assert await lock.try_acquire()
        try:
            raise RuntimeError("reconcile failed")
        except RuntimeError:
            await lock.release()
        assert lock.held is False
        assert await lock.try_acquire()

    @pytest.mark.anyio
    async def test_advisory_lock_uses_configured_lease(self):
        repo = _repo_with_fake()
        lock = ReconciliationAdvisoryLock(
            repo, holder_id="holder-a", lease_seconds=120
        )
        await lock.try_acquire()
        doc = await repo.get_lock(INTELLIGENCE_RECONCILIATION_LOCK_ID)
        delta = doc["expires_at"] - doc["acquired_at"]
        assert 119 <= delta.total_seconds() <= 121
