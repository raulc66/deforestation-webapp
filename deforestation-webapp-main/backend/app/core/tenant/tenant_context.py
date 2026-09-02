"""Minimal tenant context — maps authenticated user to tenant scope."""
from __future__ import annotations

from app.models.user import UserPublic


def tenant_id_from_user(user: UserPublic) -> str:
    """Legacy tenant identifier — prefer organization context."""
    return str(user.id)
