"""Tenant forest monitoring area CRUD routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_organization_context,
    monitoring_area_read_model_service_dep,
    monitoring_area_service_dep,
)
from app.core.errors import AppError, NotFoundError
from app.core.organization.organization_context import OrganizationContext
from app.models.forest_monitoring_area import (
    ForestMonitoringAreaCreate,
    ForestMonitoringAreaUpdate,
)
from app.services.forest_monitoring_area_service import ForestMonitoringAreaService
from app.services.monitoring_area_read_model_service import MonitoringAreaReadModelService

router = APIRouter(prefix="/monitoring-areas", tags=["monitoring-areas"])


@router.get("")
async def list_monitoring_areas(
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: MonitoringAreaReadModelService = Depends(monitoring_area_read_model_service_dep),
):
    return await svc.list_areas(org_ctx.organization_id)


@router.get("/{area_id}")
async def get_monitoring_area(
    area_id: str,
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: MonitoringAreaReadModelService = Depends(monitoring_area_read_model_service_dep),
):
    try:
        return await svc.get_area(org_ctx.organization_id, area_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", status_code=201)
async def create_monitoring_area(
    payload: ForestMonitoringAreaCreate,
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: ForestMonitoringAreaService = Depends(monitoring_area_service_dep),
):
    if org_ctx.is_demo:
        raise HTTPException(
            status_code=403,
            detail="Demonstration forests are curated. Create an organization to monitor your own stands.",
        )
    try:
        return await svc.create_area(
            org_ctx.organization_id,
            payload,
            actor_role=org_ctx.role,
        )
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/{area_id}")
async def update_monitoring_area(
    area_id: str,
    payload: ForestMonitoringAreaUpdate,
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: ForestMonitoringAreaService = Depends(monitoring_area_service_dep),
):
    if org_ctx.is_demo:
        raise HTTPException(
            status_code=403,
            detail="Demonstration forests cannot be edited.",
        )
    try:
        return await svc.update_area(
            org_ctx.organization_id,
            area_id,
            payload,
            actor_role=org_ctx.role,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{area_id}", status_code=204)
async def delete_monitoring_area(
    area_id: str,
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: ForestMonitoringAreaService = Depends(monitoring_area_service_dep),
):
    if org_ctx.is_demo:
        raise HTTPException(
            status_code=403,
            detail="Demonstration forests cannot be removed.",
        )
    try:
        await svc.delete_area(
            org_ctx.organization_id,
            area_id,
            actor_role=org_ctx.role,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
