"""Demonstration control-plane routes.

Anonymous visitors start a signed demonstration session. Product reads then
reuse the existing organization-scoped APIs under that session.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.deps import (
    demo_alert_simulation_service_dep,
    demo_payload_guard,
    demo_session_id_dep,
    demo_session_service_dep,
    get_current_user,
    get_optional_user,
    get_organization_context,
)
from app.core.config import get_settings
from app.core.demo.constants import DEMO_SESSION_HOURS, DEMO_USER_PROVIDER
from app.core.demo.identity import is_demo_user
from app.core.errors import ForbiddenError
from app.core.organization.organization_context import OrganizationContext
from app.models.user import UserPublic
from app.services.demo.demo_alert_simulation_service import DemoAlertSimulationService
from app.services.demo.demo_rate_limit import check_demo_rate
from app.services.demo.demo_session_service import DemoSessionService

router = APIRouter(
    prefix="/demo",
    tags=["demo"],
    dependencies=[Depends(demo_payload_guard)],
)


def _set_demo_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=DEMO_SESSION_HOURS * 3600,
        path="/",
    )


def _require_demo(user: UserPublic) -> None:
    if not is_demo_user(user):
        raise ForbiddenError("This action is only available in the interactive demonstration")


@router.post("/start")
async def start_demo(
    response: Response,
    user: UserPublic | None = Depends(get_optional_user),
    svc: DemoSessionService = Depends(demo_session_service_dep),
):
    if user is not None and not is_demo_user(user):
        raise ForbiddenError(
            "Sign out before starting the interactive demonstration"
        )
    user_public, token, status = await svc.start()
    _set_demo_cookie(response, token)
    return {
        **user_public.model_dump(),
        "demo": status.model_dump(),
        "access_token": token,
        "token_type": "bearer",
    }


@router.get("/status")
async def demo_status(
    user: UserPublic = Depends(get_current_user),
    session_id: str = Depends(demo_session_id_dep),
    svc: DemoSessionService = Depends(demo_session_service_dep),
):
    _require_demo(user)
    check_demo_rate(session_id)
    return (await svc.status_for(session_id)).model_dump()


@router.post("/reset")
async def reset_demo(
    user: UserPublic = Depends(get_current_user),
    session_id: str = Depends(demo_session_id_dep),
    svc: DemoSessionService = Depends(demo_session_service_dep),
):
    _require_demo(user)
    check_demo_rate(session_id)
    return (await svc.reset(session_id)).model_dump()


@router.post("/guide/{step_id}")
async def set_guide_step(
    step_id: str,
    user: UserPublic = Depends(get_current_user),
    session_id: str = Depends(demo_session_id_dep),
    svc: DemoSessionService = Depends(demo_session_service_dep),
):
    _require_demo(user)
    check_demo_rate(session_id)
    return (await svc.set_guide_step(session_id, step_id)).model_dump()


@router.post("/scenarios/{scenario_id}")
async def open_scenario(
    scenario_id: str,
    user: UserPublic = Depends(get_current_user),
    session_id: str = Depends(demo_session_id_dep),
    svc: DemoSessionService = Depends(demo_session_service_dep),
):
    _require_demo(user)
    check_demo_rate(session_id)
    return (await svc.focus_scenario(session_id, scenario_id)).model_dump()


@router.post("/actions/investigate")
async def investigate(
    request: Request,
    user: UserPublic = Depends(get_current_user),
    session_id: str = Depends(demo_session_id_dep),
    svc: DemoSessionService = Depends(demo_session_service_dep),
):
    _require_demo(user)
    check_demo_rate(session_id)
    await svc.consume(session_id, "investigation")
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    event_id = str((body or {}).get("event_id") or "")
    await svc.record(session_id, "investigation_opened", {"event_id": event_id})
    status = await svc.status_for(session_id)
    return {
        "ok": True,
        "action": "investigation",
        "demo": status.model_dump(),
    }


@router.post("/actions/report")
async def sample_report(
    user: UserPublic = Depends(get_current_user),
    session_id: str = Depends(demo_session_id_dep),
    svc: DemoSessionService = Depends(demo_session_service_dep),
    ctx: OrganizationContext = Depends(get_organization_context),
):
    _require_demo(user)
    check_demo_rate(session_id)
    await svc.consume(session_id, "report")
    await svc.record(session_id, "report_generated")
    status = await svc.status_for(session_id)
    return {
        "ok": True,
        "action": "report",
        "simulated": True,
        "title": f"Demonstration summary — {ctx.organization_name}",
        "summary": (
            "ForestWatch would compile monitored forests, prioritized "
            "disturbances, and evidence into a report for your organization. "
            "This demonstration copy is not a live environmental assessment."
        ),
        "demo": status.model_dump(),
    }


@router.post("/actions/refresh")
async def refresh_intelligence(
    user: UserPublic = Depends(get_current_user),
    session_id: str = Depends(demo_session_id_dep),
    svc: DemoSessionService = Depends(demo_session_service_dep),
):
    _require_demo(user)
    check_demo_rate(session_id)
    await svc.consume(session_id, "intelligence_query")
    await svc.record(session_id, "intelligence_query")
    status = await svc.status_for(session_id)
    return {"ok": True, "action": "intelligence_query", "demo": status.model_dump()}


@router.post("/alerts/simulate")
async def simulate_alert(
    request: Request,
    user: UserPublic = Depends(get_current_user),
    session_id: str = Depends(demo_session_id_dep),
    svc: DemoSessionService = Depends(demo_session_service_dep),
    alerts: DemoAlertSimulationService = Depends(demo_alert_simulation_service_dep),
):
    _require_demo(user)
    check_demo_rate(session_id)
    await svc.consume(session_id, "alert_simulation")
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    result = await alerts.simulate(
        session_id,
        event_id=(body or {}).get("event_id"),
    )
    status = await svc.status_for(session_id)
    return {**result, "demo": status.model_dump()}


@router.post("/events/{event_name}")
async def record_product_event(
    event_name: str,
    request: Request,
    user: UserPublic = Depends(get_current_user),
    session_id: str = Depends(demo_session_id_dep),
    svc: DemoSessionService = Depends(demo_session_service_dep),
):
    _require_demo(user)
    allowed = {
        "evidence_viewed",
        "conversion_cta_clicked",
        "organization_creation_started",
    }
    if event_name not in allowed:
        raise HTTPException(status_code=400, detail="Unknown demonstration event")
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    await svc.record(session_id, event_name, body if isinstance(body, dict) else {})
    return {"ok": True}


_ = DEMO_USER_PROVIDER
