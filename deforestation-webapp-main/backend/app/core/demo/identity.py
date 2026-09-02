"""Helpers for identifying demonstration actors without weakening real auth."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings
from app.core.demo.constants import (
    DEMO_ORGANIZATION_KIND,
    DEMO_ORGANIZATION_SLUG,
    DEMO_SESSION_HOURS,
    DEMO_TOKEN_TYPE,
    DEMO_USER_PROVIDER,
    DEMO_VISITOR_EMAIL,
    DEMO_VISITOR_NAME,
)
from app.models.user import UserPublic


def is_demo_user(user: UserPublic | None) -> bool:
    if user is None:
        return False
    return str(user.provider) == DEMO_USER_PROVIDER


DEMO_WRITE_FORBIDDEN = (
    "Demonstration data is shared and read-only. "
    "Create an organization to monitor your own forests."
)
DEMO_UNSCOPED_FORBIDDEN = (
    "This surface is not part of the interactive demonstration."
)


def deny_demo_mutation(is_demo: bool) -> None:
    if is_demo:
        from app.core.errors import ForbiddenError

        raise ForbiddenError(DEMO_WRITE_FORBIDDEN)


def deny_demo_user_unscoped(user: UserPublic | None) -> None:
    if is_demo_user(user):
        from app.core.errors import ForbiddenError

        raise ForbiddenError(DEMO_UNSCOPED_FORBIDDEN)


def is_demo_organization(org: object | None) -> bool:
    if org is None:
        return False
    kind = str(getattr(org, "kind", "") or "")
    slug = str(getattr(org, "slug", "") or "")
    if kind == DEMO_ORGANIZATION_KIND:
        return True
    return slug == DEMO_ORGANIZATION_SLUG


def demo_user_id(session_id: str) -> str:
    return f"demo:{session_id}"


def demo_public_user(session_id: str, *, created_at: datetime | None = None) -> UserPublic:
    return UserPublic(
        id=demo_user_id(session_id),
        email=DEMO_VISITOR_EMAIL,
        name=DEMO_VISITOR_NAME,
        role="user",
        provider=DEMO_USER_PROVIDER,
        created_at=created_at or datetime.now(timezone.utc),
    )


def create_demo_token(session_id: str) -> str:
    settings = get_settings()
    payload = {
        "sub": session_id,
        "email": DEMO_VISITOR_EMAIL,
        "type": DEMO_TOKEN_TYPE,
        "exp": datetime.now(timezone.utc) + timedelta(hours=DEMO_SESSION_HOURS),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
