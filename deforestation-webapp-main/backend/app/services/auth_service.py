"""Authentication service: register, login, current-user."""
import logging
from app.core.errors import AuthError, ConflictError
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.base import utcnow
from app.models.user import User, UserPublic, RegisterRequest, LoginRequest
from app.repositories.user_repository import UserRepository

logger = logging.getLogger("forestwatch.auth")


def _to_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        provider=user.provider,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
    )


class AuthService:
    def __init__(self, users: UserRepository):
        self.users = users

    async def register(self, payload: RegisterRequest) -> tuple[UserPublic, str, str]:
        email = payload.email.lower()
        existing = await self.users.find_by_email(email)
        if existing:
            raise ConflictError("Email already registered")
        user = User(
            email=email,
            name=payload.name,
            password_hash=hash_password(payload.password),
            role="user",
            provider="local",
        )
        user = await self.users.insert(user)
        logger.info("Registered user %s", email)
        access = create_access_token(user.id, user.email)
        refresh = create_refresh_token(user.id)
        return _to_public(user), access, refresh

    async def login(self, payload: LoginRequest) -> tuple[UserPublic, str, str]:
        email = payload.email.lower()
        user = await self.users.find_by_email(email)
        if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
            raise AuthError("Invalid email or password")
        access = create_access_token(user.id, user.email)
        refresh = create_refresh_token(user.id)
        logger.info("Login success for %s", email)
        return _to_public(user), access, refresh

    async def get_user_from_token(self, token: str) -> UserPublic:
        try:
            payload = decode_token(token)
        except Exception as e:
            raise AuthError("Invalid or expired token") from e
        if payload.get("type") != "access":
            raise AuthError("Invalid token type")
        user = await self.users.find_by_id(payload["sub"])
        if not user:
            raise AuthError("User not found")
        return _to_public(user)

    async def refresh_access(self, refresh_token: str) -> str:
        try:
            payload = decode_token(refresh_token)
        except Exception as e:
            raise AuthError("Invalid or expired refresh token") from e
        if payload.get("type") != "refresh":
            raise AuthError("Invalid token type")
        user = await self.users.find_by_id(payload["sub"])
        if not user:
            raise AuthError("User not found")
        return create_access_token(user.id, user.email)

    async def seed_admin(self, admin_email: str, admin_password: str) -> None:
        existing = await self.users.find_by_email(admin_email)
        if existing is None:
            admin = User(
                email=admin_email.lower(),
                name="Administrator",
                role="admin",
                password_hash=hash_password(admin_password),
                provider="local",
                created_at=utcnow(),
            )
            await self.users.insert(admin)
            logger.info("Seeded admin user %s", admin_email)
        elif not existing.password_hash or not verify_password(admin_password, existing.password_hash):
            await self.users.update(existing.id, {"password_hash": hash_password(admin_password)})
            logger.info("Updated admin password for %s", admin_email)
