"""Generalized source reliability scoring and provider-specific alert hooks."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


_SEVERITY_WEIGHTS: dict[str, float] = {
    "low": 0.2,
    "medium": 0.5,
    "high": 0.8,
    "critical": 1.0,
}

_FIRMS_SOURCE = "NASA FIRMS"


@dataclass(frozen=True)
class ReliabilityDimensions:
    """Placeholder dimensions for future deterministic scoring extensions."""

    completeness: float | None = None
    freshness: float | None = None
    consistency: float | None = None
    historical_availability: float | None = None
    failure_rate: float | None = None
    confidence: float | None = None
    geographic_coverage: float | None = None
    duplicate_rate: float | None = None


@dataclass(frozen=True)
class SourceReliabilityInput:
    average_confidence: float
    total_events: int
    in_scope_events: int
    severity_distribution: dict[str, int]
    dimensions: ReliabilityDimensions = field(default_factory=ReliabilityDimensions)


def compute_baseline_reliability_score(data: SourceReliabilityInput) -> float:
    """Deterministic baseline reliability score in [0.0, 1.0].

    Preserves the existing cross-source formula (confidence + in-scope ratio + severity).
    """
    total = data.total_events
    if total == 0:
        return 0.0

    in_scope_ratio = data.in_scope_events / total
    weighted_severity = sum(
        data.severity_distribution.get(sev, 0) * weight
        for sev, weight in _SEVERITY_WEIGHTS.items()
    )
    severity_weight = weighted_severity / total
    score = (
        0.4 * data.average_confidence
        + 0.3 * in_scope_ratio
        + 0.3 * severity_weight
    )
    return round(score, 4)


def compute_baseline_reliability_score_legacy(
    average_confidence: float,
    total_events: int,
    romania_events: int,
    severity_distribution: dict[str, int],
) -> float:
    """Backward-compatible alias using Romania event counts."""
    return compute_baseline_reliability_score(
        SourceReliabilityInput(
            average_confidence=average_confidence,
            total_events=total_events,
            in_scope_events=romania_events,
            severity_distribution=severity_distribution,
        )
    )


class SourceReliabilityEvaluator(Protocol):
    """Future hook for provider-class-specific reliability evaluation."""

    def evaluate(self, data: SourceReliabilityInput) -> float: ...


def firms_reliability_alert_trigger(
    source_rows: list[dict],
    *,
    firms_source_name: str = _FIRMS_SOURCE,
    reliability_threshold: float = 0.65,
    share_threshold: float = 0.30,
) -> bool:
    """FIRMS-specific reliability alert trigger — isolated from generalized scoring."""
    if not source_rows:
        return False
    total_events = sum(row["total_events"] for row in source_rows)
    firms = next((row for row in source_rows if row["source"] == firms_source_name), None)
    if not firms or total_events == 0:
        return False
    firms_share = firms["total_events"] / total_events
    return (
        firms["reliability_score"] > reliability_threshold
        and firms_share > share_threshold
    )
