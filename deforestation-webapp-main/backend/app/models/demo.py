"""Demonstration session and product-event records."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.demo.constants import DEFAULT_DEMO_BUDGET
from app.models.base import BaseDocument, utcnow


class DemoSession(BaseDocument):
    """Server-side demonstration visit. Usage lives here, not in the browser."""

    created_at: datetime = Field(default_factory=utcnow)
    last_seen_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    budget: dict[str, int] = Field(
        default_factory=lambda: dict(DEFAULT_DEMO_BUDGET)
    )
    used: dict[str, int] = Field(default_factory=dict)
    guide_step: str = "forests"
    focused_scenario: str | None = None
    reset_count: int = 0


class DemoProductEvent(BaseDocument):
    session_id: str
    event_name: str
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


class DemoBudgetPublic(BaseModel):
    remaining: dict[str, int]
    limits: dict[str, int]
    exhausted: bool = False


class DemoStatusPublic(BaseModel):
    session_id: str
    organization_id: str
    organization_name: str
    guide_step: str
    focused_scenario: str | None = None
    scenarios: list[dict[str, str]]
    guide: list[dict[str, str]]
    budget: DemoBudgetPublic
    reset_count: int = 0
    is_demo: bool = True
