"""Reusable geographic utilities shared across ingestion providers and analytics."""

from .geographic_scope import (
    GeographicScope,
    GeographicScopePolicy,
    geographic_scope_policy_from_value,
    parse_geographic_scope,
)
from .europe import EUROPEAN_COUNTRY_NAMES, is_europe_country, is_europe_event
from .romania import ROMANIA_BBOX, ROMANIA_REGIONS, is_romania_event

__all__ = [
    "EUROPEAN_COUNTRY_NAMES",
    "GeographicScope",
    "GeographicScopePolicy",
    "ROMANIA_BBOX",
    "ROMANIA_REGIONS",
    "geographic_scope_policy_from_value",
    "is_europe_country",
    "is_europe_event",
    "is_romania_event",
    "parse_geographic_scope",
]
