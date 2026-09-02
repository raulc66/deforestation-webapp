"""Organization and membership API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import (
    get_current_user,
    organization_context_service_dep,
    organization_service_dep,
)
from app.core.demo.identity import is_demo_user
from app.core.errors import AppError
from app.models.organization import (
    OrganizationCreate,
    OrganizationMembershipCreate,
    OrganizationMembershipUpdate,
    OrganizationUpdate,
)
from app.models.user import UserPublic
from app.services.organization_context_service import OrganizationContextService
from app.services.organization_service import OrganizationService

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _http_error(exc: AppError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("", status_code=201)
async def create_organization(
    payload: OrganizationCreate,
    user: UserPublic = Depends(get_current_user),
    svc: OrganizationService = Depends(organization_service_dep),
):
    if is_demo_user(user):
        raise HTTPException(
            status_code=403,
            detail="Create a real account to start an organization. Demonstration data cannot become a customer workspace.",
        )
    try:
        return await svc.create_organization(str(user.id), payload)
    except AppError as exc:
        raise _http_error(exc) from exc


@router.get("")
async def list_organizations(
    user: UserPublic = Depends(get_current_user),
    org_ctx_svc: OrganizationContextService = Depends(organization_context_service_dep),
):
    return {"items": await org_ctx_svc.list_accessible_organizations(user)}


@router.get("/{organization_id}")
async def get_organization(
    organization_id: str,
    user: UserPublic = Depends(get_current_user),
    svc: OrganizationService = Depends(organization_service_dep),
):
    try:
        return await svc.get_organization(organization_id, user_id=str(user.id))
    except AppError as exc:
        raise _http_error(exc) from exc


@router.put("/{organization_id}")
async def update_organization(
    organization_id: str,
    payload: OrganizationUpdate,
    user: UserPublic = Depends(get_current_user),
    svc: OrganizationService = Depends(organization_service_dep),
):
    try:
        return await svc.update_organization(organization_id, str(user.id), payload)
    except AppError as exc:
        raise _http_error(exc) from exc


@router.get("/{organization_id}/members")
async def list_members(
    organization_id: str,
    user: UserPublic = Depends(get_current_user),
    svc: OrganizationService = Depends(organization_service_dep),
):
    try:
        return await svc.list_members(organization_id, user_id=str(user.id))
    except AppError as exc:
        raise _http_error(exc) from exc


@router.post("/{organization_id}/members", status_code=201)
async def add_member(
    organization_id: str,
    payload: OrganizationMembershipCreate,
    user: UserPublic = Depends(get_current_user),
    svc: OrganizationService = Depends(organization_service_dep),
):
    try:
        return await svc.add_member(organization_id, str(user.id), payload)
    except AppError as exc:
        raise _http_error(exc) from exc


@router.put("/{organization_id}/members/{member_user_id}")
async def update_member(
    organization_id: str,
    member_user_id: str,
    payload: OrganizationMembershipUpdate,
    user: UserPublic = Depends(get_current_user),
    svc: OrganizationService = Depends(organization_service_dep),
):
    try:
        return await svc.update_member(
            organization_id,
            member_user_id,
            str(user.id),
            payload,
        )
    except AppError as exc:
        raise _http_error(exc) from exc


@router.delete("/{organization_id}/members/{member_user_id}", status_code=204)
async def remove_member(
    organization_id: str,
    member_user_id: str,
    user: UserPublic = Depends(get_current_user),
    svc: OrganizationService = Depends(organization_service_dep),
):
    try:
        await svc.remove_member(organization_id, member_user_id, str(user.id))
    except AppError as exc:
        raise _http_error(exc) from exc
