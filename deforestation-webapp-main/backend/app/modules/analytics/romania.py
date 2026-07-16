"""Backward-compatible re-exports from the canonical geography module.

Import from app.core.geography.romania directly in new code.
"""
from app.core.geography.romania import (  # noqa: F401
    ROMANIA_BBOX,
    ROMANIA_COUNTRY,
    ROMANIA_REGIONS,
    is_romania_event,
    is_romania_expression,
)
