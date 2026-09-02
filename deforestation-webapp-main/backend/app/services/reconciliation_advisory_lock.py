"""MongoDB-backed advisory lock for intelligence reconciliation (WP7).

This abstraction gates the scheduler reconciliation command path so at most
one application process mutates ``IntelligenceEvents`` at a time.

Failure and crash semantics
---------------------------
* Each ``try_acquire()`` sets ``expires_at = now + lease_seconds``.
* ``release()`` sets ``expires_at`` to the release timestamp so the next
  scheduler cycle can acquire immediately.
* If a holder crashes without calling ``release()``, the lease eventually
  expires and another scheduler instance can acquire the lock (stale-lock
  recovery).  No lease renewal is performed during reconciliation — the
  default lease (300 s) must exceed expected reconciliation runtime.
* The lock is replaceable: only ``ReconciliationLockRepository`` is
  MongoDB-specific; callers depend on this service interface.
"""
from __future__ import annotations

import os
import socket
import uuid
from datetime import timedelta

from app.models.base import utcnow
from app.repositories.reconciliation_lock_repository import ReconciliationLockRepository

INTELLIGENCE_RECONCILIATION_LOCK_ID = "intelligence_reconciliation"
DEFAULT_RECONCILIATION_LOCK_LEASE_SECONDS = 300


def default_holder_id() -> str:
    """Unique identifier for this scheduler process instance."""
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


class ReconciliationAdvisoryLock:
    """Lease-based advisory lock for the reconciliation command path."""

    def __init__(
        self,
        repo: ReconciliationLockRepository,
        *,
        holder_id: str | None = None,
        lease_seconds: int = DEFAULT_RECONCILIATION_LOCK_LEASE_SECONDS,
        lock_id: str = INTELLIGENCE_RECONCILIATION_LOCK_ID,
    ) -> None:
        self._repo = repo
        self._holder_id = holder_id or default_holder_id()
        self._lease_seconds = lease_seconds
        self._lock_id = lock_id
        self._held = False

    @property
    def holder_id(self) -> str:
        return self._holder_id

    @property
    def held(self) -> bool:
        return self._held

    async def try_acquire(self) -> bool:
        now = utcnow()
        expires_at = now + timedelta(seconds=self._lease_seconds)
        acquired = await self._repo.try_acquire(
            lock_id=self._lock_id,
            holder_id=self._holder_id,
            acquired_at=now,
            expires_at=expires_at,
        )
        self._held = acquired
        return acquired

    async def release(self) -> bool:
        if not self._held:
            return False
        released = await self._repo.release(
            lock_id=self._lock_id,
            holder_id=self._holder_id,
            released_at=utcnow(),
        )
        self._held = False
        return released
