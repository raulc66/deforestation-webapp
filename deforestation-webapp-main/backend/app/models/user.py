"""User domain model + API schemas."""
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from typing import Literal
from .base import BaseDocument, utcnow


class User(BaseDocument):
    email: str
    name: str
    role: Literal["admin", "user"] = "user"
    password_hash: str | None = None  # null for OAuth-only users
    provider: Literal["local", "google"] = "local"
    avatar_url: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class UserPublic(BaseModel):
    id: str
    email: str
    name: str
    role: str
    provider: str
    avatar_url: str | None = None
    created_at: datetime


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=1, max_length=80)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
