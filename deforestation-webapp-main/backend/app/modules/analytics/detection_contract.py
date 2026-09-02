"""Canonical Detection envelope contract (ADR-009, WP1.3)."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.ecosystem.canonical_identity import CanonicalIdentity
from app.core.ecosystem.incident_categories import normalize_incident_category
from app.models.base import ensure_utc


class SignalType(StrEnum):
    """Detector provenance class (ADR-008 provenance / ADR-009 signal_type)."""

    BASELINE_DEVIATION = "baseline_deviation"
    DISTURBANCE_SIGNAL = "disturbance_signal"
    CONTEXTUAL_EVIDENCE = "contextual_evidence"


class Detection(BaseModel):
    """Normalized detection envelope consumed by reconciliation (future WP4)."""

    model_config = ConfigDict(frozen=True)

    spatial_key: str
    incident_category: str
    signal_type: str
    severity: str
    score: float = Field(ge=0.0, le=1.0)
    evidence: dict[str, Any]
    detected_at: datetime

    @field_validator("spatial_key")
    @classmethod
    def _spatial_key_non_empty(cls, value: str) -> str:
        key = str(value).strip()
        if not key:
            raise ValueError("spatial_key must be non-empty")
        return key

    @field_validator("incident_category")
    @classmethod
    def _normalize_category(cls, value: str) -> str:
        return normalize_incident_category(value)

    @field_validator("signal_type")
    @classmethod
    def _signal_type_non_empty(cls, value: str) -> str:
        signal = str(value).strip()
        if not signal:
            raise ValueError("signal_type must be non-empty")
        return signal

    @field_validator("severity")
    @classmethod
    def _severity_non_empty(cls, value: str) -> str:
        sev = str(value).strip().lower()
        if not sev:
            raise ValueError("severity must be non-empty")
        return sev

    @field_validator("detected_at")
    @classmethod
    def _detected_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @property
    def identity(self) -> CanonicalIdentity:
        return CanonicalIdentity(
            incident_category=self.incident_category,
            spatial_key=self.spatial_key,
        )
