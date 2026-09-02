"""Authorization context abstraction — no fabricated legal conclusions."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class AuthorizationStatus(StrEnum):
    UNKNOWN = "unknown"
    AUTHORIZED = "authorized"
    REQUIRES_VERIFICATION = "requires_verification"
    POTENTIALLY_UNAUTHORIZED = "potentially_unauthorized"


@dataclass(frozen=True)
class AuthorizationContextRecord:
    """Bounded authorization record from an authoritative source."""

    status: str
    source: str
    permit_id: str | None = None
    permit_type: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    notes: str | None = None


class AuthorizationContextProvider:
    """Replaceable interface for future forestry permit / authorization datasets."""

    def lookup(
        self,
        *,
        latitude: float,
        longitude: float,
        tenant_id: str,
        monitored_area_id: str | None = None,
    ) -> AuthorizationContextRecord:
        raise NotImplementedError


class UnknownAuthorizationContextProvider(AuthorizationContextProvider):
    """Default — no authoritative authorization data available."""

    def lookup(
        self,
        *,
        latitude: float,
        longitude: float,
        tenant_id: str,
        monitored_area_id: str | None = None,
    ) -> AuthorizationContextRecord:
        return AuthorizationContextRecord(
            status=AuthorizationStatus.UNKNOWN.value,
            source="none",
        )


def bounded_authorization_read_model(record: AuthorizationContextRecord | None) -> dict[str, Any]:
    if record is None:
        return {"authorization_status": AuthorizationStatus.UNKNOWN.value, "source": "none"}
    return {
        "authorization_status": record.status,
        "source": record.source,
        "permit_id": record.permit_id,
        "permit_type": record.permit_type,
    }
