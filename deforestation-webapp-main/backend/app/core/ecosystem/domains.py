"""Ecosystem domain definitions for Command Center preparation."""
from __future__ import annotations

from enum import StrEnum


class EcosystemDomain(StrEnum):
    """Top-level ecosystem monitoring domains."""

    FOREST_HEALTH = "forest_health"
    WILDLIFE = "wildlife"
    ENVIRONMENT = "environment"
    HUMAN_ACTIVITY = "human_activity"


ECOSYSTEM_DOMAINS: tuple[str, ...] = tuple(d.value for d in EcosystemDomain)
