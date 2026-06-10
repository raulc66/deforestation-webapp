"""Data ingestion module — CSV import + (future) scheduled pulls.

Public surface:
    csv_importer.CsvImporter   — synchronous CSV → ForestEvent ingestion
    scheduler.scheduler         — in-memory registry of scheduled jobs (no
                                  runner yet)
    validation.validate_row     — row-level validation primitives
"""

from . import csv_importer, scheduler, validation  # noqa: F401

NAME = "ingestion"
STATUS = "active"  # csv_importer is live; scheduled pulls remain "planned"
DESCRIPTION = (
    "Ingest forest-disturbance datasets. CSV upload is live; scheduled API/"
    "satellite pulls are planned."
)


def module_info() -> dict:
    return {
        "name": NAME,
        "status": STATUS,
        "description": DESCRIPTION,
        "capabilities": {
            "csv_import": "live",
            "scheduled_jobs": "planned",
        },
        "planned_capabilities": [
            "Source registry & versioning",
            "Cron-scheduled batch pulls (APScheduler)",
            "Schema validation & dead-letter queue",
        ],
        "scheduled_jobs": scheduler.scheduler.list_jobs(),
    }


async def run() -> dict:
    return {"name": NAME, "ran": False, "reason": "use POST /api/import/csv for now"}
