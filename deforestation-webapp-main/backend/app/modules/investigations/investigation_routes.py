"""REST endpoints for Incident Investigation Management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import deny_demo_global_data, get_current_user, investigation_service_dep
from app.core.demo.identity import is_demo_user
from app.core.errors import NotFoundError, ConflictError
from app.models.investigation import (
    InvestigationAssign,
    InvestigationClose,
    InvestigationCreate,
    InvestigationUpdate,
)
from app.models.user import UserPublic
from app.modules.investigations.investigation_service import InvestigationService

router = APIRouter(prefix="/investigations", tags=["investigations"])


@router.get("")
async def list_investigations(
    status: str | None = Query(None),
    priority: str | None = Query(None),
    region: str | None = Query(None),
    search: str | None = Query(None),
    _: UserPublic = Depends(deny_demo_global_data),
    svc: InvestigationService = Depends(investigation_service_dep),
):
    return await svc.list_investigations(
        status=status, priority=priority, region=region, search=search
    )


@router.get("/statistics")
async def investigation_statistics(
    _: UserPublic = Depends(deny_demo_global_data),
    svc: InvestigationService = Depends(investigation_service_dep),
):
    return await svc.get_statistics()


@router.get("/{investigation_id}")
async def get_investigation(
    investigation_id: str,
    _: UserPublic = Depends(deny_demo_global_data),
    svc: InvestigationService = Depends(investigation_service_dep),
):
    try:
        return await svc.get_investigation(investigation_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", status_code=201)
async def create_investigation(
    payload: InvestigationCreate,
    user: UserPublic = Depends(get_current_user),
    svc: InvestigationService = Depends(investigation_service_dep),
):
    if is_demo_user(user):
        raise HTTPException(
            status_code=403,
            detail="Use the demonstration investigation action. Persistent investigations belong to real organizations.",
        )
    try:
        return await svc.create(payload, created_by=user.id)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/{investigation_id}")
async def update_investigation(
    investigation_id: str,
    payload: InvestigationUpdate,
    user: UserPublic = Depends(deny_demo_global_data),
    svc: InvestigationService = Depends(investigation_service_dep),
):
    try:
        return await svc.update(investigation_id, payload, actor=user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{investigation_id}/assign")
async def assign_investigation(
    investigation_id: str,
    payload: InvestigationAssign,
    user: UserPublic = Depends(deny_demo_global_data),
    svc: InvestigationService = Depends(investigation_service_dep),
):
    try:
        return await svc.assign(investigation_id, payload, actor=user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{investigation_id}/close")
async def close_investigation(
    investigation_id: str,
    payload: InvestigationClose,
    user: UserPublic = Depends(deny_demo_global_data),
    svc: InvestigationService = Depends(investigation_service_dep),
):
    try:
        return await svc.close(investigation_id, payload, actor=user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{investigation_id}", status_code=204)
async def archive_investigation(
    investigation_id: str,
    _: UserPublic = Depends(deny_demo_global_data),
    svc: InvestigationService = Depends(investigation_service_dep),
):
    try:
        await svc.archive(investigation_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
