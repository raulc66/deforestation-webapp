"""ImportJob domain model - tracks CSV ingestion runs."""
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field
from .base import BaseDocument, utcnow


ImportStatus = Literal["pending", "running", "completed", "partial", "failed"]


class ImportError(BaseModel):
    row_number: int
    field: str | None = None
    message: str
    raw: dict[str, Any] | None = None  # original row for debugging


class ImportJob(BaseDocument):
    filename: str
    source_id: str  # DataSource used for imported events
    status: ImportStatus = "pending"
    total_rows: int = 0
    success_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    errors: list[ImportError] = Field(default_factory=list)
    triggered_by_user_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None
    duration_ms: int | None = None


class ImportJobPublic(BaseModel):
    id: str
    filename: str
    source_id: str
    status: ImportStatus
    total_rows: int
    success_count: int
    skipped_count: int = 0
    error_count: int
    errors: list[ImportError]
    triggered_by_user_id: str | None
    created_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
