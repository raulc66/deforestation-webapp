"""Import routes - /api/import/*"""
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from app.api.deps import csv_importer_dep, get_current_user
from app.models.import_job import ImportJobPublic
from app.models.user import UserPublic
from app.modules.ingestion.csv_importer import CsvImporter

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/csv", response_model=ImportJobPublic)
async def import_csv(
    file: UploadFile = File(..., description="UTF-8 CSV with the required columns"),
    source_id: str | None = Form(default=None, description="Target DataSource id"),
    user: UserPublic = Depends(get_current_user),
    importer: CsvImporter = Depends(csv_importer_dep),
):
    """Upload a CSV file and import each row as a ForestEvent.

    Required columns: title, country, region, latitude, longitude, event_type,
    severity, affected_area_ha. Optional: confidence, detected_at. When
    `source_id` is omitted, the first DataSource with `type='csv'` is used.
    """
    contents = await file.read()
    return await importer.import_csv(
        contents,
        filename=file.filename or "upload.csv",
        source_id=source_id,
        user_id=user.id,
    )


@router.get("/status", response_model=list[ImportJobPublic])
async def list_import_status(
    limit: int = Query(default=20, ge=1, le=100),
    _: UserPublic = Depends(get_current_user),
    importer: CsvImporter = Depends(csv_importer_dep),
):
    """Return the most recent import jobs (newest first)."""
    return await importer.list_recent(limit=limit)


@router.get("/status/{job_id}", response_model=ImportJobPublic)
async def get_import_status(
    job_id: str,
    _: UserPublic = Depends(get_current_user),
    importer: CsvImporter = Depends(csv_importer_dep),
):
    """Return a single import job with full per-row error detail."""
    return await importer.get_job(job_id)
