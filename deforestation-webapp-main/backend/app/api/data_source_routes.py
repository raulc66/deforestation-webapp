"""DataSource routes - /api/data-sources/*"""
from fastapi import APIRouter, Depends, Query
from app.api.deps import data_source_service_dep, get_current_user
from app.models.data_source import (
    DATA_SOURCE_TYPES,
    DataSourceCreate,
    DataSourceUpdate,
    DataSourcePublic,
)
from app.models.user import UserPublic
from app.services.data_source_service import DataSourceService

router = APIRouter(prefix="/data-sources", tags=["data-sources"])


@router.get("/types")
async def list_data_source_types():
    """Return the catalogue of valid DataSource types."""
    return list(DATA_SOURCE_TYPES)


@router.get("", response_model=list[DataSourcePublic])
async def list_data_sources(
    type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    _: UserPublic = Depends(get_current_user),
    svc: DataSourceService = Depends(data_source_service_dep),
):
    return await svc.list_sources(type=type, status=status)


@router.post("", response_model=DataSourcePublic, status_code=201)
async def create_data_source(
    payload: DataSourceCreate,
    _: UserPublic = Depends(get_current_user),
    svc: DataSourceService = Depends(data_source_service_dep),
):
    return await svc.create_source(payload)


@router.get("/{source_id}", response_model=DataSourcePublic)
async def get_data_source(
    source_id: str,
    _: UserPublic = Depends(get_current_user),
    svc: DataSourceService = Depends(data_source_service_dep),
):
    return await svc.get_source(source_id)


@router.patch("/{source_id}", response_model=DataSourcePublic)
async def update_data_source(
    source_id: str,
    payload: DataSourceUpdate,
    _: UserPublic = Depends(get_current_user),
    svc: DataSourceService = Depends(data_source_service_dep),
):
    return await svc.update_source(source_id, payload)


@router.delete("/{source_id}", status_code=204)
async def delete_data_source(
    source_id: str,
    _: UserPublic = Depends(get_current_user),
    svc: DataSourceService = Depends(data_source_service_dep),
):
    await svc.delete_source(source_id)
    return None
