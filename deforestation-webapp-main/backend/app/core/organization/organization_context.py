"""Trusted organization context for authenticated requests."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.user import UserPublic

ORGANIZATION_ID_HEADER = "X-Organization-Id"


@dataclass(frozen=True)
class OrganizationContext:
    """Resolved organization scope for the current request."""

    user: UserPublic
    organization_id: str
    organization_name: str
    organization_slug: str
    membership_id: str
    role: str
    membership_status: str
    is_demo: bool = False
