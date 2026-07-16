"""Command Center data structures (architecture preparation only).

These models describe how future ecosystem modules expose status to a unified
Command Center.  No detection or ingestion logic lives here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .domains import EcosystemDomain


DomainStatus = Literal["active", "partial", "planned", "unavailable"]


class DomainModuleStatus(BaseModel):
    """Readiness snapshot for one ecosystem domain."""

    domain: EcosystemDomain
    status: DomainStatus
    label: str
    description: str
    incident_categories: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    endpoints: list[str] = Field(default_factory=list)


class CommandCenterSnapshot(BaseModel):
    """Aggregate view consumed by a future Command Center UI."""

    generated_at: datetime
    domains: list[DomainModuleStatus]
    incident_aggregation: dict
    active_intel_by_category: dict[str, int] = Field(default_factory=dict)
    # Environmental Threat Intelligence (additive)
    top_threats: list[dict] = Field(default_factory=list)
    threat_distribution: dict[str, int] = Field(default_factory=dict)
    human_vs_natural_ratio: dict[str, float] = Field(default_factory=dict)
    most_affected_domains: list[dict] = Field(default_factory=list)
    highest_priority_interventions: list[dict] = Field(default_factory=list)
    # Investigation management (additive)
    open_investigations: int = 0
    critical_investigations: int = 0
    average_resolution_time_hours: float | None = None
    investigations_by_region: dict[str, int] = Field(default_factory=dict)
