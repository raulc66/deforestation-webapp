"""Pydantic models and enumerations for the reporting module."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ReportType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ON_DEMAND = "on_demand"


class ReportFormat(str, Enum):
    PDF = "pdf"
    CSV = "csv"
    JSON = "json"


class ReportStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETE = "complete"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# API request / response models
# ---------------------------------------------------------------------------


class GenerateReportRequest(BaseModel):
    """Body for POST /api/reports/generate."""

    type: ReportType
    format: ReportFormat = ReportFormat.PDF
    period_start: datetime | None = None
    period_end: datetime | None = None


class ReportRecord(BaseModel):
    """Single report metadata document returned by the API."""

    id: str
    type: ReportType
    format: ReportFormat
    status: ReportStatus
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    file_path: str | None = None
    file_size: int | None = None
    generation_time_ms: int | None = None
    summary: dict[str, Any] | None = None
    error: str | None = None


class ReportListResponse(BaseModel):
    reports: list[ReportRecord]
    total: int
