"""Authenticated free-trial organization routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_current_user,
    get_organization_context,
    trial_service_dep,
)
from app.core.organization.organization_context import OrganizationContext
from app.models.trial import TrialStartRequest
from app.models.user import UserPublic
from app.services.trial_service import TrialService

router = APIRouter(prefix="/trial", tags=["trial"])


@router.post("/start")
async def start_trial(
    payload: TrialStartRequest | None = None,
    user: UserPublic = Depends(get_current_user),
    svc: TrialService = Depends(trial_service_dep),
):
    return await svc.start_trial(user, payload or TrialStartRequest())


@router.get("/status")
async def trial_status(
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: TrialService = Depends(trial_service_dep),
):
    return await svc.status_for_context(org_ctx.user, org_ctx.organization_id)
