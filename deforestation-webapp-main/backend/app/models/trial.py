"""Public trial read models — no Stripe identifiers, no fabricated billing."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TrialStartRequest(BaseModel):
    organization_name: str | None = Field(default=None, min_length=1, max_length=120)


class TrialStatusPublic(BaseModel):
    organization_id: str
    organization_name: str
    organization_slug: str
    commercial_lifecycle: str
    trial_started_at: datetime | None = None
    trial_ends_at: datetime | None = None
    days_remaining: int | None = None
    originating_user_id: str | None = None
    originating_user_email: str | None = None
    entitlements: dict[str, Any]
    usage: dict[str, Any]
    onboarding: dict[str, Any]
    alert_delivery_mode: str
    upgrade_cta: dict[str, Any]
