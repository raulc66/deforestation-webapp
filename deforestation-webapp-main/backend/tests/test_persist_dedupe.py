"""Unit tests for persist_import_event duplicate handling."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.models.forest_event import ForestEventCreate
from app.modules.ingestion.dedupe import build_dedupe_key, is_duplicate_event
from app.modules.ingestion.persist import persist_import_event


def _sample_payload(**overrides) -> ForestEventCreate:
    base = dict(
        title="Test dedupe",
        country="Brazil",
        region="Amazon",
        latitude=-3.5,
        longitude=-62.2,
        event_type="logging",
        severity="high",
        affected_area_ha=10.0,
        source_id="csv-demo",
        detected_at=datetime(2026, 2, 1, 8, 0, 0, tzinfo=timezone.utc),
        metadata={"import_job_id": "job-1"},
    )
    base.update(overrides)
    return ForestEventCreate(**base)


def _mock_repo(find_one_results: list) -> MagicMock:
    repo = MagicMock()
    col = MagicMock()
    repo.col = col
    col.find_one = AsyncMock(side_effect=find_one_results)
    return repo


def _mock_events_service() -> MagicMock:
    svc = MagicMock()
    svc.create_event = AsyncMock()
    return svc


class TestPersistImportEvent:
    def test_creates_when_unique(self):
        events = _mock_events_service()
        repo = _mock_repo([None, None])
        seen: set[str] = set()
        payload = _sample_payload()

        outcome = asyncio.run(
            persist_import_event(events, repo, payload, seen_keys=seen)
        )

        assert outcome == "created"
        events.create_event.assert_awaited_once()
        created = events.create_event.await_args.args[0]
        assert created.metadata.get("dedupe_key")
        assert len(seen) == 1

    def test_skips_duplicate_in_same_batch(self):
        events = _mock_events_service()
        repo = _mock_repo([None, None])
        seen: set[str] = set()
        payload = _sample_payload()

        asyncio.run(persist_import_event(events, repo, payload, seen_keys=seen))
        outcome = asyncio.run(
            persist_import_event(events, repo, payload, seen_keys=seen)
        )

        assert outcome == "skipped"
        assert events.create_event.await_count == 1

    def test_skips_when_dedupe_key_exists_in_db(self):
        events = _mock_events_service()
        repo = _mock_repo([{"_id": "existing"}])
        seen: set[str] = set()
        payload = _sample_payload()

        outcome = asyncio.run(
            persist_import_event(events, repo, payload, seen_keys=seen)
        )

        assert outcome == "skipped"
        events.create_event.assert_not_awaited()
        repo.col.find_one.assert_awaited_once()


class TestIsDuplicateEvent:
    def _args(self):
        dt = datetime(2026, 2, 1, 8, 0, 0, tzinfo=timezone.utc)
        key = build_dedupe_key(
            country="Brazil",
            region="Amazon",
            latitude=-3.5,
            longitude=-62.2,
            detected_at=dt,
            event_type="logging",
        )
        return dict(
            country="Brazil",
            region="Amazon",
            latitude=-3.5,
            longitude=-62.2,
            detected_at=dt,
            event_type="logging",
            dedupe_key=key,
        )

    def test_true_when_dedupe_key_exists(self):
        repo = _mock_repo([{"_id": "x"}])
        result = asyncio.run(is_duplicate_event(repo, **self._args()))
        assert result is True
        repo.col.find_one.assert_awaited_once()

    def test_true_when_legacy_fields_match(self):
        repo = _mock_repo([None, {"_id": "legacy"}])
        result = asyncio.run(is_duplicate_event(repo, **self._args()))
        assert result is True
        assert repo.col.find_one.await_count == 2

    def test_false_when_no_match(self):
        repo = _mock_repo([None, None])
        result = asyncio.run(is_duplicate_event(repo, **self._args()))
        assert result is False
