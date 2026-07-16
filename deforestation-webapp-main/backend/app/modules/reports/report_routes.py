"""FastAPI routes for the Operational Reporting module.

Mount this router at ``/api/reports`` in ``server.py``.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import get_current_user, report_service_dep
from app.models.user import UserPublic

from .report_models import GenerateReportRequest, ReportFormat, ReportType
from .report_repository import ReportRepository
from .report_service import ReportService

logger = logging.getLogger("forestwatch.reports.routes")
router = APIRouter(tags=["reports"])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("")
async def list_reports(
    _: UserPublic = Depends(get_current_user),
    report_svc: ReportService = Depends(report_service_dep),
):
    """Return all report metadata records, newest first."""
    reports = await report_svc.list_reports()
    return {"reports": reports, "total": len(reports)}


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    _: UserPublic = Depends(get_current_user),
    report_svc: ReportService = Depends(report_service_dep),
):
    """Return metadata for a single report."""
    record = await report_svc.get_report(report_id)
    if not record:
        raise HTTPException(status_code=404, detail="Report not found")
    return record


@router.post("/generate", status_code=202)
async def generate_report(
    request: GenerateReportRequest,
    background_tasks: BackgroundTasks,
    _: UserPublic = Depends(get_current_user),
    report_svc: ReportService = Depends(report_service_dep),
):
    """Create a new report and begin generation in the background.

    Returns the PENDING record immediately (HTTP 202 Accepted).
    Poll ``GET /api/reports/{id}`` to track progress.
    """
    record = await report_svc.create_pending(
        report_type=request.type,
        report_format=request.format,
        period_start=request.period_start,
        period_end=request.period_end,
    )

    # Determine final report_type string from the pending record
    report_type_str = record.get("type", request.type.value)
    period_start = record["period_start"]
    period_end = record["period_end"]

    background_tasks.add_task(
        report_svc.generate_background,
        report_id=record["id"],
        period_start=period_start,
        period_end=period_end,
        report_format=request.format,
        report_type=report_type_str,
    )

    return record


@router.delete("/{report_id}", status_code=204)
async def delete_report(
    report_id: str,
    _: UserPublic = Depends(get_current_user),
    report_svc: ReportService = Depends(report_service_dep),
):
    """Delete a report and its associated file."""
    deleted = await report_svc.delete_report(report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Report not found")


@router.get("/{report_id}/download")
async def download_report(
    report_id: str,
    _: UserPublic = Depends(get_current_user),
    report_svc: ReportService = Depends(report_service_dep),
):
    """Download the generated report file."""
    record = await report_svc.get_report(report_id)
    if not record:
        raise HTTPException(status_code=404, detail="Report not found")

    if record.get("status") != "complete":
        raise HTTPException(
            status_code=400,
            detail=f"Report is not ready (status: {record.get('status', 'unknown')})",
        )

    file_path_str = record.get("file_path")
    if not file_path_str:
        raise HTTPException(status_code=404, detail="Report file path not set")

    file_path = Path(file_path_str)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found on disk")

    ext = file_path.suffix.lstrip(".").lower()
    media_type_map = {
        "pdf":  "application/pdf",
        "csv":  "text/csv; charset=utf-8",
        "json": "application/json; charset=utf-8",
    }
    media_type = media_type_map.get(ext, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type=media_type,
    )
