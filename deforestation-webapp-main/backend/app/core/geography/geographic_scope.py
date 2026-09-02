"""Central geographic scope policy for intelligence pipeline filtering.

Scopes:
  - ``romania`` — Romanian observations only (Phase 0 default)
  - ``europe``  — European observations (Romania + other European countries)
  - ``all``     — all supported geographic observations (no geographic filter)

Ingestion is never filtered here — providers may ingest globally while the
intelligence engine applies the configured scope at query/detection time.
"""
from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Any

from .europe import is_europe_event, is_europe_expression
from .romania import is_romania_event, is_romania_expression


class GeographicScope(StrEnum):
    ROMANIA = "romania"
    EUROPE = "europe"
    ALL = "all"


_VALID_SCOPES: frozenset[str] = frozenset(scope.value for scope in GeographicScope)


def parse_geographic_scope(value: str | None) -> GeographicScope:
    """Parse and validate a scope string; default ``romania`` when invalid."""
    if not value:
        return GeographicScope.ROMANIA
    normalized = str(value).strip().lower()
    if normalized not in _VALID_SCOPES:
        return GeographicScope.ROMANIA
    return GeographicScope(normalized)


class GeographicScopePolicy:
    """Single source of truth for intelligence geographic filtering."""

    __slots__ = ("_scope",)

    def __init__(self, scope: GeographicScope) -> None:
        self._scope = scope

    @property
    def scope(self) -> GeographicScope:
        return self._scope

    @property
    def scope_value(self) -> str:
        return self._scope.value

    def event_in_scope(self, event: dict[str, Any]) -> bool:
        if self._scope is GeographicScope.ALL:
            return True
        if self._scope is GeographicScope.ROMANIA:
            ingestion = (event.get("metadata") or {}).get("ingestion") or {}
            if ingestion.get("is_romania") is True:
                return True
            return is_romania_event(event)
        return is_europe_event(event)

    def mongo_match_filter(self) -> dict[str, Any]:
        """Return a MongoDB query filter fragment for scoped intelligence queries."""
        if self._scope is GeographicScope.ALL:
            return {}
        if self._scope is GeographicScope.ROMANIA:
            return {"metadata.ingestion.is_romania": True}
        return {"$expr": is_europe_expression()}

    def mongo_expression(self) -> dict[str, Any]:
        """Return a MongoDB boolean expression for scoped intelligence queries."""
        if self._scope is GeographicScope.ALL:
            return {"$literal": True}
        if self._scope is GeographicScope.ROMANIA:
            return {"$eq": ["$metadata.ingestion.is_romania", True]}
        return is_europe_expression()

    def centroids_use_romania_admin_fallback(self) -> bool:
        """Whether map layers may fall back to Romanian admin-region centroids."""
        return self._scope is GeographicScope.ROMANIA


@lru_cache(maxsize=8)
def geographic_scope_policy_from_value(value: str) -> GeographicScopePolicy:
    return GeographicScopePolicy(parse_geographic_scope(value))
