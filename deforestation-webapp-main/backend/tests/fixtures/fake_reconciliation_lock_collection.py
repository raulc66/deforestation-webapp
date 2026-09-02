"""In-memory Motor collection fake for reconciliation lock tests (WP7).

Implements the subset of MongoDB semantics used by
``ReconciliationLockRepository``: atomic ``find_one_and_update``,
``insert_one``, and ``find_one`` under an ``asyncio.Lock``.
"""
from __future__ import annotations

import asyncio
import copy

from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument


class FakeReconciliationLockCollection:
    """Thread/async-safe single-document store keyed by ``_id``."""

    def __init__(self) -> None:
        self._docs: dict[str, dict] = {}
        self._mutex = asyncio.Lock()

    async def find_one_and_update(
        self,
        filter: dict,
        update: dict,
        upsert: bool = False,
        return_document=None,
    ) -> dict | None:
        async with self._mutex:
            lock_id = filter.get("_id")
            if lock_id is None:
                return None

            existing = self._docs.get(lock_id)
            now = self._extract_compare_time(filter)
            holder_id = self._extract_holder_id(filter)

            if existing is not None:
                if not self._filter_matches(existing, filter, now):
                    if upsert:
                        return None
                    return None
                merged = self._apply_update(existing, update)
                self._docs[lock_id] = merged
                return copy.deepcopy(merged)

            if not upsert:
                return None

            merged = {"_id": lock_id}
            merged = self._apply_update(merged, update)
            self._docs[lock_id] = merged
            return copy.deepcopy(merged)

    async def insert_one(self, doc: dict) -> None:
        async with self._mutex:
            lock_id = doc["_id"]
            if lock_id in self._docs:
                raise DuplicateKeyError("duplicate lock id")
            self._docs[lock_id] = copy.deepcopy(doc)

    async def find_one(self, filter: dict) -> dict | None:
        async with self._mutex:
            lock_id = filter.get("_id")
            if lock_id is None:
                return None
            doc = self._docs.get(lock_id)
            return copy.deepcopy(doc) if doc else None

    def _extract_compare_time(self, filter: dict) -> object | None:
        for clause in filter.get("$or", []):
            expires = clause.get("expires_at", {})
            if "$lte" in expires:
                return expires["$lte"]
        return None

    def _extract_holder_id(self, filter: dict) -> str | None:
        for clause in filter.get("$or", []):
            if "holder_id" in clause:
                return clause["holder_id"]
        if "holder_id" in filter:
            return filter["holder_id"]
        return None

    def _filter_matches(self, doc: dict, filter: dict, now: object | None) -> bool:
        if filter.get("_id") != doc.get("_id"):
            return False
        if "holder_id" in filter and doc.get("holder_id") != filter["holder_id"]:
            return False
        or_clauses = filter.get("$or")
        if or_clauses:
            return any(self._matches_clause(doc, clause, now) for clause in or_clauses)
        return True

    def _matches_clause(self, doc: dict, clause: dict, now: object | None) -> bool:
        if "holder_id" in clause:
            return doc.get("holder_id") == clause["holder_id"]
        expires_filter = clause.get("expires_at", {})
        if "$lte" in expires_filter and now is not None:
            expires_at = doc.get("expires_at")
            return expires_at is not None and expires_at <= now
        return False

    def _apply_update(self, doc: dict, update: dict) -> dict:
        merged = copy.deepcopy(doc)
        for key, value in update.get("$set", {}).items():
            merged[key] = value
        for key, value in update.get("$setOnInsert", {}).items():
            merged.setdefault(key, value)
        return merged


def make_lock_repository() -> "ReconciliationLockRepository":
    """Build a repository backed by the in-memory fake collection."""
    from app.repositories.reconciliation_lock_repository import (
        ReconciliationLockRepository,
    )

    repo = ReconciliationLockRepository.__new__(ReconciliationLockRepository)
    repo.col = FakeReconciliationLockCollection()
    return repo
