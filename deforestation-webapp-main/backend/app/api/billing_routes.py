"""Organization-scoped billing API and the Stripe webhook endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import (
    billing_service_dep,
    get_organization_context,
    stripe_webhook_service_dep,
)
from app.core.errors import AppError
from app.core.organization.organization_context import OrganizationContext
from app.models.billing import CheckoutRequest
from app.services.billing.billing_service import BillingService
from app.services.billing.stripe_webhook_service import StripeWebhookService

router = APIRouter(prefix="/billing", tags=["billing"])


def _http_error(exc: AppError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/status")
async def get_billing_status(
    ctx: OrganizationContext = Depends(get_organization_context),
    svc: BillingService = Depends(billing_service_dep),
):
    try:
        return await svc.get_status(ctx)
    except AppError as exc:
        raise _http_error(exc) from exc


@router.get("/plans")
async def list_billing_plans(
    ctx: OrganizationContext = Depends(get_organization_context),
    svc: BillingService = Depends(billing_service_dep),
):
    try:
        return await svc.list_plans(ctx)
    except AppError as exc:
        raise _http_error(exc) from exc


@router.post("/checkout")
async def create_checkout_session(
    payload: CheckoutRequest,
    ctx: OrganizationContext = Depends(get_organization_context),
    svc: BillingService = Depends(billing_service_dep),
):
    try:
        return await svc.create_checkout_session(ctx, payload.plan_key)
    except AppError as exc:
        raise _http_error(exc) from exc


@router.post("/portal")
async def create_portal_session(
    ctx: OrganizationContext = Depends(get_organization_context),
    svc: BillingService = Depends(billing_service_dep),
):
    try:
        return await svc.create_portal_session(ctx)
    except AppError as exc:
        raise _http_error(exc) from exc


@router.post("/webhook/stripe")
async def stripe_webhook(
    request: Request,
    svc: StripeWebhookService = Depends(stripe_webhook_service_dep),
):
    """Stripe-authenticated endpoint: signature verified, no user session.

    The raw request body is required — any re-serialization would invalidate the
    signature.
    """
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")
    try:
        result = await svc.handle(payload, signature)
    except AppError as exc:
        raise _http_error(exc) from exc
    return {
        "received": result.received,
        "status": result.status,
        "event_type": result.event_type,
    }
