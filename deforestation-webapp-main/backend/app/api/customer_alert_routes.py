"""Organization-scoped customer alert API routes.

Organization scope always comes from the trusted ``OrganizationContext``
(resolved from the ``X-Organization-Id`` header plus membership), never from the
request body or query string.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import alert_policy_service_dep, get_organization_context
from app.core.demo.identity import deny_demo_mutation
from app.core.commercial.alert_semantics import (
    ALERT_EVIDENCE_STATES,
    ALERT_PRIORITY_LEVELS,
    ALERT_SEVERITY_LEVELS,
    MAX_COOLDOWN_MINUTES,
    category_display_name,
    supported_incident_categories,
)
from app.core.errors import AppError, NotFoundError
from app.core.organization.organization_context import OrganizationContext
from app.models.customer_alert import (
    AlertLifecycle,
    AlertPolicyCreate,
    AlertPolicyUpdate,
    NotificationChannelCreate,
    NotificationChannelUpdate,
)
from app.services.alert_policy_service import AlertPolicyService

router = APIRouter(prefix="/customer-alerts", tags=["customer-alerts"])


def _translate(exc: AppError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/options")
async def alert_configuration_options():
    """Configurable vocabulary for the alert policy form — no internal keys."""
    return {
        "incident_categories": [
            {"value": category, "label": category_display_name(category)}
            for category in supported_incident_categories()
        ],
        "investigation_priorities": list(ALERT_PRIORITY_LEVELS),
        "severity_levels": list(ALERT_SEVERITY_LEVELS),
        "evidence_states": list(ALERT_EVIDENCE_STATES),
        "channel_types": ["email", "webhook"],
        "max_cooldown_minutes": MAX_COOLDOWN_MINUTES,
    }


@router.get("/overview")
async def alert_operations_overview(
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: AlertPolicyService = Depends(alert_policy_service_dep),
):
    return await svc.alert_operations_overview(
        org_ctx.organization_id,
        actor_role=org_ctx.role,
    )


@router.get("/policies")
async def list_alert_policies(
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: AlertPolicyService = Depends(alert_policy_service_dep),
):
    return await svc.list_policies(org_ctx.organization_id, actor_role=org_ctx.role)


@router.post("/policies", status_code=201)
async def create_alert_policy(
    payload: AlertPolicyCreate,
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: AlertPolicyService = Depends(alert_policy_service_dep),
):
    deny_demo_mutation(org_ctx.is_demo)
    try:
        return await svc.create_policy(
            org_ctx.organization_id,
            payload,
            actor_role=org_ctx.role,
        )
    except AppError as exc:
        raise _translate(exc) from exc


@router.get("/policies/{policy_id}")
async def get_alert_policy(
    policy_id: str,
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: AlertPolicyService = Depends(alert_policy_service_dep),
):
    try:
        return await svc.get_policy(org_ctx.organization_id, policy_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


@router.put("/policies/{policy_id}")
async def update_alert_policy(
    policy_id: str,
    payload: AlertPolicyUpdate,
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: AlertPolicyService = Depends(alert_policy_service_dep),
):
    deny_demo_mutation(org_ctx.is_demo)
    try:
        return await svc.update_policy(
            org_ctx.organization_id,
            policy_id,
            payload,
            actor_role=org_ctx.role,
        )
    except AppError as exc:
        raise _translate(exc) from exc


@router.post("/policies/{policy_id}/activation")
async def set_alert_policy_activation(
    policy_id: str,
    enabled: bool = Query(...),
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: AlertPolicyService = Depends(alert_policy_service_dep),
):
    deny_demo_mutation(org_ctx.is_demo)
    try:
        return await svc.set_policy_enabled(
            org_ctx.organization_id,
            policy_id,
            enabled=enabled,
            actor_role=org_ctx.role,
        )
    except AppError as exc:
        raise _translate(exc) from exc


@router.delete("/policies/{policy_id}", status_code=204)
async def delete_alert_policy(
    policy_id: str,
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: AlertPolicyService = Depends(alert_policy_service_dep),
):
    deny_demo_mutation(org_ctx.is_demo)
    try:
        await svc.delete_policy(
            org_ctx.organization_id,
            policy_id,
            actor_role=org_ctx.role,
        )
    except AppError as exc:
        raise _translate(exc) from exc


@router.get("/channels")
async def list_notification_channels(
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: AlertPolicyService = Depends(alert_policy_service_dep),
):
    return await svc.list_channels(org_ctx.organization_id, actor_role=org_ctx.role)


@router.post("/channels", status_code=201)
async def create_notification_channel(
    payload: NotificationChannelCreate,
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: AlertPolicyService = Depends(alert_policy_service_dep),
):
    deny_demo_mutation(org_ctx.is_demo)
    try:
        return await svc.create_channel(
            org_ctx.organization_id,
            payload,
            actor_role=org_ctx.role,
            actor_email=org_ctx.user.email,
        )
    except AppError as exc:
        raise _translate(exc) from exc


@router.put("/channels/{channel_id}")
async def update_notification_channel(
    channel_id: str,
    payload: NotificationChannelUpdate,
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: AlertPolicyService = Depends(alert_policy_service_dep),
):
    deny_demo_mutation(org_ctx.is_demo)
    try:
        return await svc.update_channel(
            org_ctx.organization_id,
            channel_id,
            payload,
            actor_role=org_ctx.role,
            actor_email=org_ctx.user.email,
        )
    except AppError as exc:
        raise _translate(exc) from exc


@router.post("/channels/{channel_id}/activation")
async def set_notification_channel_activation(
    channel_id: str,
    enabled: bool = Query(...),
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: AlertPolicyService = Depends(alert_policy_service_dep),
):
    deny_demo_mutation(org_ctx.is_demo)
    try:
        return await svc.set_channel_enabled(
            org_ctx.organization_id,
            channel_id,
            enabled=enabled,
            actor_role=org_ctx.role,
        )
    except AppError as exc:
        raise _translate(exc) from exc


@router.delete("/channels/{channel_id}", status_code=204)
async def delete_notification_channel(
    channel_id: str,
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: AlertPolicyService = Depends(alert_policy_service_dep),
):
    deny_demo_mutation(org_ctx.is_demo)
    try:
        await svc.delete_channel(
            org_ctx.organization_id,
            channel_id,
            actor_role=org_ctx.role,
        )
    except AppError as exc:
        raise _translate(exc) from exc


@router.get("/deliveries")
async def list_alert_deliveries(
    limit: int = Query(50, ge=1, le=200),
    lifecycle: str | None = Query(None),
    org_ctx: OrganizationContext = Depends(get_organization_context),
    svc: AlertPolicyService = Depends(alert_policy_service_dep),
):
    if lifecycle is not None and lifecycle not in {state.value for state in AlertLifecycle}:
        raise HTTPException(status_code=422, detail="Unsupported delivery status filter")
    return await svc.list_deliveries(
        org_ctx.organization_id,
        limit=limit,
        lifecycle=lifecycle,
    )
