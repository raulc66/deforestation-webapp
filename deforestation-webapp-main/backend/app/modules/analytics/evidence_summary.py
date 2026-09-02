"""Bounded evidence read-model for Command Center intelligence items."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.ingestion.provider_health import ProviderHealthStatus
from app.modules.analytics.correlation_result import CorrelationResult
from app.modules.analytics.disturbance_assessment import bounded_disturbance_read_model
from app.modules.analytics.provenance_persistence import sanitize_provenance_envelope
from app.modules.analytics.reconciliation import identity_key_from_event

MAX_PROVENANCE_ENTRIES = 3
MAX_PROVIDER_LABELS = 5

PROVIDER_LABELS: dict[str, str] = {
    "nasa.firms": "NASA FIRMS",
    "satellite_fire_observations": "NASA FIRMS",
    "eea.air_quality": "EEA Air Quality",
    "cems.rapid_mapping": "Copernicus EMS",
    "effis.wildfire_context": "EFFIS",
    "gfw.integrated_alerts": "GFW Alerts",
    "clms.land_cover": "CLMS",
    "open_meteo.weather": "Open-Meteo",
}

CATEGORY_DEFAULT_PROVIDER: dict[str, str] = {
    "wildfire": "nasa.firms",
    "air_quality": "eea.air_quality",
    "environmental_hazard": "cems.rapid_mapping",
    "forest_disturbance": "gfw.integrated_alerts",
}


class EvidenceSummary(BaseModel):
    """Bounded operational evidence projection for one intelligence event."""

    model_config = ConfigDict(frozen=True)

    evidence_count: int = 1
    source_count: int = 1
    providers: tuple[str, ...] = ()
    provider_ids: tuple[str, ...] = ()
    relationship_types: tuple[str, ...] = ()
    correlation_ids: tuple[str, ...] = ()
    strongest_correlation_strength: float | None = None
    evidence_state: str = "single_source"
    correlation_state: str = "unavailable"
    source_availability: dict[str, str] = Field(default_factory=dict)


def provider_label(provider_id: str | None) -> str:
    if not provider_id:
        return "Unknown"
    return PROVIDER_LABELS.get(provider_id, provider_id.replace("_", " ").replace(".", " ").title())


def _identity_key(event: dict[str, Any]) -> tuple[str, str]:
    return identity_key_from_event(event)


def _infer_primary_provider_id(event: dict[str, Any]) -> str | None:
    meta = event.get("metadata") or {}
    prov = meta.get("provenance") or {}
    if prov.get("provider_id"):
        return str(prov["provider_id"])
    category = str(event.get("incident_category") or "wildfire")
    return CATEGORY_DEFAULT_PROVIDER.get(category)


def _health_status_map(health_rows: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(row["provider_id"]): str(row.get("current_status", ProviderHealthStatus.UNKNOWN.value))
        for row in health_rows
        if row.get("provider_id")
    }


def _availability_label(status: str | None) -> str:
    if status in {
        ProviderHealthStatus.HEALTHY.value,
        ProviderHealthStatus.DEGRADED.value,
        ProviderHealthStatus.FAILED.value,
        ProviderHealthStatus.DISABLED.value,
        ProviderHealthStatus.UNKNOWN.value,
    }:
        return status
    return ProviderHealthStatus.UNKNOWN.value


def resolve_correlation_state(
    *,
    correlation_enabled: bool,
    current_cycle_id: str | None,
    correlation_cycle_id: str | None,
    has_correlations: bool,
) -> str:
    if not correlation_enabled:
        return "disabled"
    if not current_cycle_id:
        return "unavailable"
    if not has_correlations:
        return "unavailable"
    if correlation_cycle_id and correlation_cycle_id == current_cycle_id:
        return "current"
    if correlation_cycle_id:
        return "stale"
    return "unavailable"


def build_evidence_summary(
    event: dict[str, Any],
    *,
    correlations: list[CorrelationResult],
    correlation_state: str,
    health_by_provider: dict[str, str],
) -> EvidenceSummary:
    """Assemble bounded evidence for one intelligence event."""
    key = _identity_key(event)
    matched = [
        corr
        for corr in correlations
        if (corr.canonical_incident_category, corr.canonical_spatial_key) == key
        or any(
            (p.incident_category, p.spatial_key) == key for p in corr.participants
        )
    ]

    primary_provider = _infer_primary_provider_id(event)
    provider_ids: set[str] = set()
    if primary_provider:
        provider_ids.add(primary_provider)

    relationship_types: set[str] = set()
    correlation_ids: list[str] = []
    strongest: float | None = None

    if correlation_state == "current":
        for corr in matched:
            correlation_ids.append(corr.correlation_id)
            relationship_types.add(corr.relationship_type)
            provider_ids.update(corr.participating_provider_ids)
            if strongest is None or corr.strength > strongest:
                strongest = corr.strength

    sorted_provider_ids = tuple(sorted(provider_ids))[:MAX_PROVIDER_LABELS]
    providers = tuple(provider_label(pid) for pid in sorted_provider_ids)

    source_availability: dict[str, str] = {}
    for pid in sorted_provider_ids:
        source_availability[pid] = _availability_label(health_by_provider.get(pid))

    evidence_state = _resolve_evidence_state(
        matched=matched,
        correlation_state=correlation_state,
        source_availability=source_availability,
        primary_provider=primary_provider,
    )

    evidence_count = max(1, len({pid for pid in sorted_provider_ids}))
    if correlation_state == "current" and matched:
        evidence_count = max(
            evidence_count,
            max(len(corr.participants) for corr in matched),
        )

    return EvidenceSummary(
        evidence_count=evidence_count,
        source_count=len(sorted_provider_ids) or 1,
        providers=providers,
        provider_ids=sorted_provider_ids,
        relationship_types=tuple(sorted(relationship_types)),
        correlation_ids=tuple(sorted(correlation_ids)),
        strongest_correlation_strength=strongest,
        evidence_state=evidence_state,
        correlation_state=correlation_state,
        source_availability=source_availability,
    )


def _resolve_evidence_state(
    *,
    matched: list[CorrelationResult],
    correlation_state: str,
    source_availability: dict[str, str],
    primary_provider: str | None,
) -> str:
    degraded_or_failed = any(
        status in {ProviderHealthStatus.DEGRADED.value, ProviderHealthStatus.FAILED.value}
        for status in source_availability.values()
    )
    primary_status = source_availability.get(primary_provider or "", "")
    if primary_status in {ProviderHealthStatus.DEGRADED.value, ProviderHealthStatus.FAILED.value}:
        return "degraded_source"
    if degraded_or_failed and correlation_state == "current" and matched:
        return "degraded_source"

    if correlation_state in {"disabled", "unavailable", "stale"}:
        return "single_source" if not degraded_or_failed else "degraded_source"

    if not matched:
        return "single_source"

    types = {corr.relationship_type for corr in matched}
    if types == {"contextual_evidence"}:
        return "contextual_support"
    if types & {"supporting_evidence", "multi_source_situation"}:
        return "multi_source"
    return "single_source"


def bounded_provenance_entries(
    event: dict[str, Any],
    *,
    include_provenance: bool,
) -> list[dict[str, Any]]:
    if not include_provenance:
        return []
    meta = event.get("metadata") or {}
    raw = meta.get("provenance")
    if not isinstance(raw, dict):
        return []
    cleaned = sanitize_provenance_envelope(raw)
    if not cleaned:
        return []
    entry = {
        k: cleaned[k]
        for k in (
            "provider_id",
            "source_id",
            "dataset_id",
            "dataset_version",
            "source_event_id",
            "observed_at",
            "detected_at",
            "geographic_scope",
        )
        if cleaned.get(k) is not None
    }
    domain = cleaned.get("domain_evidence") or {}
    if domain.get("detected_at") and "detected_at" not in entry:
        entry["detected_at"] = domain["detected_at"]
    return [entry][:MAX_PROVENANCE_ENTRIES]


def build_intelligence_evidence_payload(
    active_events: list[dict[str, Any]],
    *,
    correlations: list[CorrelationResult],
    cycle_state: dict[str, Any] | None,
    correlation_enabled: bool,
    include_provenance: bool,
    health_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the Command Center intelligence evidence read model."""
    current_cycle_id = (cycle_state or {}).get("intelligence_cycle_id")
    correlation_cycle_id = (cycle_state or {}).get("correlation_cycle_id")
    has_correlations = bool(correlations)
    global_correlation_state = resolve_correlation_state(
        correlation_enabled=correlation_enabled,
        current_cycle_id=current_cycle_id,
        correlation_cycle_id=correlation_cycle_id,
        has_correlations=has_correlations,
    )
    health_by_provider = _health_status_map(health_rows)

    items: list[dict[str, Any]] = []
    for event in active_events:
        summary = build_evidence_summary(
            event,
            correlations=correlations,
            correlation_state=global_correlation_state,
            health_by_provider=health_by_provider,
        )
        items.append(
            {
                "event_id": event.get("id"),
                "incident_category": event.get("incident_category"),
                "region": event.get("region"),
                "severity": event.get("severity"),
                "escalation_level": event.get("escalation_level"),
                "trend": event.get("trend"),
                "priority_score": event.get("priority_score"),
                "evidence_summary": summary.model_dump(mode="json"),
                "disturbance_assessment": bounded_disturbance_read_model(
                    (event.get("metadata") or {}).get("forest_disturbance")
                )
                if event.get("incident_category") == "forest_disturbance"
                else {},
                "provenance": bounded_provenance_entries(
                    event,
                    include_provenance=include_provenance,
                ),
            }
        )

    return {
        "intelligence_cycle_id": current_cycle_id,
        "correlation_cycle_id": correlation_cycle_id,
        "correlation_state": global_correlation_state,
        "items": items,
    }
