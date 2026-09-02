"""Minimal organization role checks — explicit, not a generic RBAC framework."""
from __future__ import annotations


class OrganizationRole:
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class MembershipStatus:
    ACTIVE = "active"
    SUSPENDED = "suspended"


def can_manage_members(role: str) -> bool:
    return role in {OrganizationRole.OWNER, OrganizationRole.ADMIN}


def can_manage_monitoring_areas(role: str) -> bool:
    return role in {OrganizationRole.OWNER, OrganizationRole.ADMIN}


def can_update_organization(role: str) -> bool:
    return role == OrganizationRole.OWNER


def can_read_monitoring(role: str, *, membership_status: str) -> bool:
    return membership_status == MembershipStatus.ACTIVE


def can_manage_billing(role: str) -> bool:
    """Purchase, upgrade, or manage the subscription."""
    return role in {OrganizationRole.OWNER, OrganizationRole.ADMIN}


def can_view_billing(role: str, *, membership_status: str) -> bool:
    """See plan and capability state — every active member, no wider than that."""
    return membership_status == MembershipStatus.ACTIVE
