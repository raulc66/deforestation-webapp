"""Ingestion scheduler — planned home for scheduled ingestion jobs.

Currently a scaffolding registry (not yet started). Other modules can already
register their cron-style jobs; the runner will be wired up later (likely
APScheduler or arq).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Awaitable, Callable

logger = logging.getLogger("forestwatch.ingestion.scheduler")

JobCallable = Callable[[], Awaitable[None]]


@dataclass
class ScheduledJob:
    name: str
    cron: str
    description: str = ""
    run: JobCallable | None = None  # callable invoked by the future runner


@dataclass
class IngestionScheduler:
    """In-memory registry of scheduled ingestion jobs (no runner yet)."""

    _jobs: list[ScheduledJob] = field(default_factory=list)

    def register(self, name: str, cron: str, run: JobCallable | None = None, description: str = "") -> None:
        for j in self._jobs:
            if j.name == name:
                j.cron = cron
                j.run = run
                j.description = description
                logger.info("Updated scheduled job '%s' (%s)", name, cron)
                return
        self._jobs.append(ScheduledJob(name=name, cron=cron, run=run, description=description))
        logger.info("Registered scheduled job '%s' (%s)", name, cron)

    def list_jobs(self) -> list[dict]:
        return [
            {"name": j.name, "cron": j.cron, "description": j.description, "has_runner": j.run is not None}
            for j in self._jobs
        ]


# Singleton accessor — the rest of the codebase imports `scheduler` from here.
scheduler = IngestionScheduler()
