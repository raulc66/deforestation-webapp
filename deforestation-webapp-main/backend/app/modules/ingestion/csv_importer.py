"""CSV importer - parses an uploaded CSV and creates ForestEvent records.

Synchronous import (suitable for files up to several thousand rows). Each run
is recorded in an ImportJob document with per-row error reporting.

For very large files this can be queued — see scheduler.py for the planned
async background pipeline.
"""
from __future__ import annotations

import csv
import io
import logging
import time
from datetime import datetime, timezone

from app.core.errors import AppError, NotFoundError
from app.models.forest_event import ForestEventCreate
from app.models.import_job import ImportError as ImportErrorModel, ImportJob, ImportJobPublic
from app.repositories.data_source_repository import DataSourceRepository
from app.repositories.forest_event_repository import ForestEventRepository
from app.repositories.import_job_repository import ImportJobRepository
from app.services.forest_event_service import ForestEventService

from .persist import persist_import_event
from .validation import RowError, validate_header, validate_row

logger = logging.getLogger("forestwatch.ingestion.csv")

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_ROWS = 10_000  # safety cap for one synchronous run


def _to_public(job: ImportJob) -> ImportJobPublic:
    return ImportJobPublic(
        id=job.id,
        filename=job.filename,
        source_id=job.source_id,
        status=job.status,
        total_rows=job.total_rows,
        success_count=job.success_count,
        skipped_count=job.skipped_count,
        error_count=job.error_count,
        errors=job.errors,
        triggered_by_user_id=job.triggered_by_user_id,
        created_at=job.created_at,
        completed_at=job.completed_at,
        duration_ms=job.duration_ms,
    )


class CsvImporter:
    def __init__(
        self,
        jobs_repo: ImportJobRepository,
        sources_repo: DataSourceRepository,
        events_service: ForestEventService,
        events_repo: ForestEventRepository,
    ):
        self.jobs = jobs_repo
        self.sources = sources_repo
        self.events = events_service
        self.events_repo = events_repo

    async def _resolve_default_source_id(self) -> str:
        """If the uploader doesn't pass a source_id, pick the first DataSource
        with type='csv'. This lets uploads work out of the box once the demo
        seed has run."""
        doc = await self.sources.find_one({"type": "csv"})
        if doc is None:
            raise AppError(
                "No DataSource with type='csv' exists - create one first or pass source_id",
                status_code=400,
                code="missing_csv_source",
            )
        return doc.id

    async def import_csv(
        self,
        file_bytes: bytes,
        filename: str,
        source_id: str | None,
        user_id: str | None,
    ) -> ImportJobPublic:
        if len(file_bytes) > MAX_FILE_BYTES:
            raise AppError(
                f"File too large ({len(file_bytes)} bytes > {MAX_FILE_BYTES} limit)",
                status_code=413,
                code="file_too_large",
            )

        # Resolve target DataSource
        if source_id:
            ds = await self.sources.find_by_id(source_id)
            if not ds:
                raise NotFoundError(f"DataSource '{source_id}' not found")
            resolved_source_id = ds.id
        else:
            resolved_source_id = await self._resolve_default_source_id()

        # Create the job record
        job = ImportJob(
            filename=filename or "upload.csv",
            source_id=resolved_source_id,
            status="running",
            triggered_by_user_id=user_id,
        )
        job = await self.jobs.insert(job)
        started_at = time.perf_counter()

        # Parse the CSV
        try:
            text = file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            await self._finalize_failed(
                job,
                file_error="File is not valid UTF-8",
                started_at=started_at,
            )
            return await self._reload(job.id)

        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None:
            await self._finalize_failed(
                job, file_error="CSV is empty or has no header row", started_at=started_at
            )
            return await self._reload(job.id)

        header_problems = validate_header(reader.fieldnames)
        if header_problems:
            await self._finalize_failed(
                job, file_error="; ".join(header_problems), started_at=started_at
            )
            return await self._reload(job.id)

        # Process rows
        errors: list[ImportErrorModel] = []
        success = 0
        skipped = 0
        seen_keys: set[str] = set()
        total = 0
        for idx, raw_row in enumerate(reader, start=2):  # row 1 = header
            total += 1
            if total > MAX_ROWS:
                errors.append(
                    ImportErrorModel(
                        row_number=idx,
                        field=None,
                        message=f"Row cap exceeded (max {MAX_ROWS})",
                    )
                )
                break
            parsed, row_errors = validate_row(idx, raw_row)
            if row_errors:
                errors.extend(_to_model_errors(row_errors))
                continue
            try:
                payload = ForestEventCreate(
                    title=parsed.title,
                    country=parsed.country,
                    region=parsed.region,
                    latitude=parsed.latitude,
                    longitude=parsed.longitude,
                    event_type=parsed.event_type,
                    severity=parsed.severity,
                    affected_area_ha=parsed.affected_area_ha,
                    confidence=parsed.confidence if parsed.confidence is not None else 0.8,
                    source_id=resolved_source_id,
                    detected_at=parsed.detected_at,
                    metadata={"imported_from": filename, "import_job_id": job.id},
                )
                outcome = await persist_import_event(
                    self.events,
                    self.events_repo,
                    payload,
                    seen_keys=seen_keys,
                )
                if outcome == "created":
                    success += 1
                else:
                    skipped += 1
            except Exception as e:  # noqa: BLE001 — surface as row error
                logger.exception("Row %d failed to persist", idx)
                errors.append(
                    ImportErrorModel(
                        row_number=idx,
                        field=None,
                        message=f"Persistence error: {e}",
                        raw=raw_row,
                    )
                )

        # Finalize
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        if success == 0 and skipped == 0:
            final_status = "failed"
        elif errors:
            final_status = "partial"
        else:
            final_status = "completed"

        await self.jobs.update(
            job.id,
            {
                "status": final_status,
                "total_rows": total,
                "success_count": success,
                "skipped_count": skipped,
                "error_count": len(errors),
                "errors": [e.model_dump() for e in errors],
                "completed_at": datetime.now(timezone.utc),
                "duration_ms": duration_ms,
            },
        )
        logger.info(
            "Import %s: %s (%d ok / %d skipped / %d errors / %d total)",
            job.id, final_status, success, skipped, len(errors), total,
        )
        return await self._reload(job.id)

    async def _finalize_failed(
        self,
        job: ImportJob,
        file_error: str,
        started_at: float,
    ) -> None:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        await self.jobs.update(
            job.id,
            {
                "status": "failed",
                "errors": [
                    ImportErrorModel(
                        row_number=0, field="__file__", message=file_error
                    ).model_dump()
                ],
                "error_count": 1,
                "completed_at": datetime.now(timezone.utc),
                "duration_ms": duration_ms,
            },
        )

    async def _reload(self, job_id: str) -> ImportJobPublic:
        doc = await self.jobs.find_by_id(job_id)
        return _to_public(doc)

    async def list_recent(self, limit: int = 20) -> list[ImportJobPublic]:
        docs = await self.jobs.list_recent(limit=limit)
        return [_to_public(d) for d in docs]

    async def get_job(self, job_id: str) -> ImportJobPublic:
        doc = await self.jobs.find_by_id(job_id)
        if not doc:
            raise NotFoundError("Import job not found")
        return _to_public(doc)


def _to_model_errors(row_errors: list[RowError]) -> list[ImportErrorModel]:
    return [
        ImportErrorModel(
            row_number=e.row_number,
            field=e.field,
            message=e.message,
            raw=e.raw,
        )
        for e in row_errors
    ]
