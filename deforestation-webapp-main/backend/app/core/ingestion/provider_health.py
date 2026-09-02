"""Provider health and run telemetry models."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ProviderHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class ProviderRunTelemetry(BaseModel):
    """Outcome of one provider execution within a scheduler cycle."""

    model_config = ConfigDict(frozen=True)

    provider_id: str
    display_name: str
    status: str
    started_at: datetime
    completed_at: datetime
    fetch_duration_seconds: float
    observations_received: int = 0
    observations_persisted: int = 0
    observations_rejected: int = 0
    duplicates_skipped: int = 0
    error: str | None = None


class ProviderHealthRecord(BaseModel):
    """Latest operational health for one provider."""

    provider_id: str
    display_name: str
    current_status: str = ProviderHealthStatus.UNKNOWN.value
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    consecutive_failures: int = 0
    observations_received: int = 0
    observations_rejected: int = 0
    observations_persisted: int = 0
    last_fetch_duration_seconds: float | None = None
    last_error: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now())


def health_status_from_run(
    *,
    success: bool,
    observations_rejected: int,
    observations_received: int,
    consecutive_failures: int,
    enabled: bool,
) -> str:
    """Deterministic status from run outcome — no invented health when never run."""
    if not enabled:
        return ProviderHealthStatus.DISABLED.value
    if consecutive_failures == 0 and success:
        if observations_received > 0 and observations_rejected > observations_received // 2:
            return ProviderHealthStatus.DEGRADED.value
        return ProviderHealthStatus.HEALTHY.value
    if consecutive_failures >= 3:
        return ProviderHealthStatus.FAILED.value
    if consecutive_failures > 0 or not success:
        return ProviderHealthStatus.DEGRADED.value
    return ProviderHealthStatus.UNKNOWN.value
