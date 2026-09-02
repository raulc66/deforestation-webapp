"""Organization, membership, and entitlement domain models."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.base import BaseDocument, utcnow


OrganizationStatus = Literal["active", "suspended"]
MembershipRole = Literal["owner", "admin", "member"]
MembershipStatusLiteral = Literal["active", "suspended"]


class Organization(BaseDocument):
    name: str
    slug: str
    status: OrganizationStatus = "active"
    kind: str = "customer"
    # Commercial lifecycle is distinct from operational ``status`` and from
    # reserved-org ``kind``. Demo is never stored here.
    commercial_lifecycle: str = "unsubscribed"
    trial_started_at: datetime | None = None
    trial_ends_at: datetime | None = None
    trial_originating_user_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class OrganizationMembership(BaseDocument):
    organization_id: str
    user_id: str
    role: MembershipRole
    status: MembershipStatusLiteral = "active"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class OrganizationEntitlement(BaseDocument):
    organization_id: str
    entitlement_type: str
    value: Any
    source: str = "foundation_profile"
    effective_from: datetime = Field(default_factory=utcnow)
    effective_until: datetime | None = None
    status: Literal["active", "suspended"] = "active"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    status: OrganizationStatus | None = None


class OrganizationPublic(BaseModel):
    id: str
    name: str
    slug: str
    status: OrganizationStatus
    kind: str = "customer"
    commercial_lifecycle: str = "unsubscribed"
    trial_ends_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class OrganizationMembershipCreate(BaseModel):
    email: str
    role: MembershipRole = "member"


class OrganizationMembershipUpdate(BaseModel):
    role: MembershipRole | None = None
    status: MembershipStatusLiteral | None = None


class OrganizationMembershipPublic(BaseModel):
    id: str
    organization_id: str
    user_id: str
    user_email: str | None = None
    user_name: str | None = None
    role: MembershipRole
    status: MembershipStatusLiteral
    created_at: datetime
    updated_at: datetime
