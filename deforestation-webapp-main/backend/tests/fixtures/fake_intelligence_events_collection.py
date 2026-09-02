"""In-memory fake MongoDB collection for intelligence_events migration tests."""
from __future__ import annotations

import copy
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import OperationFailure


def _index_keys(keys) -> tuple:
    if isinstance(keys, str):
        return ((keys, 1),)
    return tuple((k, int(v)) for k, v in keys)


class _UpdateResult:
    def __init__(self, modified_count: int) -> None:
        self.modified_count = modified_count


class _AsyncCursor:
    def __init__(self, items: list[dict]) -> None:
        self._items = items
        self._idx = 0

    def __aiter__(self):
        return self

    async def __anext__(self) -> dict:
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item


class FakeIntelligenceEventsCollection:
    """Minimal async collection implementing migration operations."""

    def __init__(self, docs: list[dict] | None = None) -> None:
        self._docs: dict[ObjectId, dict] = {}
        self.indexes_created: list[tuple[Any, dict[str, Any]]] = []
        for doc in docs or []:
            stored = copy.deepcopy(doc)
            oid = stored.pop("_id", None) or ObjectId()
            if isinstance(oid, str):
                oid = ObjectId(oid)
            stored["_id"] = oid
            self._docs[oid] = stored

    def all_docs(self) -> list[dict]:
        return [copy.deepcopy(d) for d in self._docs.values()]

    def find(self, filter: dict | None = None, projection=None):
        return _AsyncCursor(self._matching(filter or {}))

    async def find_one(self, filter: dict) -> dict | None:
        matches = self._matching(filter)
        return copy.deepcopy(matches[0]) if matches else None

    async def update_one(self, filter: dict, update: dict) -> _UpdateResult:
        matches = self._matching(filter)
        if not matches:
            return _UpdateResult(0)
        doc = matches[0]
        oid = doc["_id"]
        if not self._matches_filter(doc, filter):
            return _UpdateResult(0)
        merged = copy.deepcopy(doc)
        for key, value in update.get("$set", {}).items():
            merged[key] = value
        changed = merged != doc
        self._docs[oid] = merged
        return _UpdateResult(1 if changed else 0)

    async def create_index(self, keys, name: str | None = None, **kwargs):
        wanted = _index_keys(keys)
        for existing_keys, spec in self.indexes_created:
            existing_name = spec.get("name")
            if _index_keys(existing_keys) == wanted and existing_name not in (None, name):
                raise OperationFailure(
                    f"Index already exists with a different name: {existing_name}",
                    85,
                )
        self.indexes_created.append((keys, {"name": name, **kwargs}))

    async def drop_index(self, name: str) -> None:
        self.indexes_created = [
            item for item in self.indexes_created if item[1].get("name") != name
        ]

    def _matching(self, filter: dict) -> list[dict]:
        return [copy.deepcopy(d) for d in self._docs.values() if self._matches_filter(d, filter)]

    def _matches_filter(self, doc: dict, filter: dict) -> bool:
        for key, expected in filter.items():
            if key == "$or":
                if not any(self._matches_filter(doc, clause) for clause in expected):
                    return False
                continue
            value = doc.get(key)
            if isinstance(expected, dict):
                if "$exists" in expected:
                    exists = key in doc and doc[key] is not None
                    if expected["$exists"] and not exists:
                        return False
                    if not expected["$exists"] and exists:
                        return False
                if "$lte" in expected and not (value is not None and value <= expected["$lte"]):
                    return False
                continue
            if value != expected:
                return False
        return True


def make_migration_db(docs: list[dict] | None = None):
    """Return a fake db object exposing ``intelligence_events`` collection."""
    col = FakeIntelligenceEventsCollection(docs)

    class _DB:
        def __getitem__(self, name: str):
            if name == "intelligence_events":
                return col
            raise KeyError(name)

    return _DB(), col
