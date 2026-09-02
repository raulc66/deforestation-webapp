"""Bounded operational read model for multi-region intelligence validation."""
from __future__ import annotations

from collections import Counter
from typing import Any

from app.core.config import Settings, get_settings
from app.core.geography.geographic_scope import GeographicScopePolicy, parse_geographic_scope
from app.core.ingestion.provider_health import ProviderHealthStatus
from app.modules.analytics.correlation_result import CorrelationResult
from app.modules.analytics.evidence_summary import resolve_correlation_state
from app.modules.analytics.intelligence_events_repository import IntelligenceEventsRepository
from app.modules.ingestion.provider_execution_mode import resolve_provider_execution_mode
from app.repositories.correlation_repository import CorrelationRepository
from app.repositories.ingestion_runs_repository import IngestionRunsRepository
from app.repositories.intelligence_cycle_repository import IntelligenceCycleRepository
from app.repositories.provider_health_repository import ProviderHealthRepository
from app.services.source_intelligence_service import SourceIntelligenceService

MAX_REGIONS = 20
MAX_RULE_BUCKETS = 10
MAX_PAIR_BUCKETS = 10
MAX_COUNTRY_BUCKETS = 10


class OperationalStatusService:
    """Read-only operational aggregation — no ingestion or reconciliation."""

    def __init__(
        self,
        source_intel: SourceIntelligenceService,
        intel_repo: IntelligenceEventsRepository,
        correlation_repo: CorrelationRepository,
        cycle_repo: IntelligenceCycleRepository,
        health_repo: ProviderHealthRepository,
        runs_repo: IngestionRunsRepository,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._source_intel = source_intel
        self._intel_repo = intel_repo
        self._correlation_repo = correlation_repo
        self._cycle_repo = cycle_repo
        self._health_repo = health_repo
        self._runs_repo = runs_repo
        self._settings = settings or get_settings()

    async def get_operational_status(self) -> dict[str, Any]:
        scope_policy = GeographicScopePolicy(parse_geographic_scope(self._settings.geographic_scope))
        source_status = await self._source_intel.get_source_status()
        health_rows = {row["provider_id"]: row for row in await self._health_repo.list_all()}
        runs = await self._runs_repo.list_runs(limit=50)
        last_run_by_provider = _latest_run_by_provider(runs)
        cycle_state = await self._cycle_repo.get_current() or {}
        correlation_rows = await self._correlation_repo.list_all()
        correlations = await self._load_correlations()
        active_events = await self._intel_repo.find_active()

        providers = [
            _public_provider_row(
                src,
                health=health_rows.get(src["provider_id"]),
                last_run=last_run_by_provider.get(src["provider_id"]),
                settings=self._settings,
                configured_scope=self._settings.geographic_scope,
            )
            for src in source_status.get("sources", [])
        ]

        correlation_state = resolve_correlation_state(
            correlation_enabled=self._settings.enable_cross_source_correlation,
            current_cycle_id=cycle_state.get("intelligence_cycle_id"),
            correlation_cycle_id=cycle_state.get("correlation_cycle_id"),
            has_correlations=bool(correlations),
        )

        return {
            "geographic_scope": self._settings.geographic_scope,
            "scope_policy": {
                "configured_scope": self._settings.geographic_scope,
                "description": _scope_description(self._settings.geographic_scope),
            },
            "providers": providers,
            "intelligence_cycle": _public_cycle(cycle_state),
            "correlation": {
                "enabled": self._settings.enable_cross_source_correlation,
                "state": correlation_state,
                "diagnostics": _correlation_diagnostics(
                    correlations,
                    correlation_rows=correlation_rows,
                    cycle_state=cycle_state,
                    correlation_state=correlation_state,
                ),
            },
            "evidence": _evidence_aggregate(active_events, correlation_state),
            "regions": _scoped_regions(active_events, scope_policy),
        }

    async def _load_correlations(self) -> list[CorrelationResult]:
        if not self._settings.enable_cross_source_correlation:
            return []
        rows = await self._correlation_repo.list_all()
        results: list[CorrelationResult] = []
        for row in rows:
            try:
                results.append(CorrelationResult.model_validate(row))
            except Exception:
                continue
        return results


def _scope_description(scope: str) -> str:
    mapping = {
        "romania": "Romanian observations eligible for intelligence processing",
        "europe": "European observations eligible for intelligence processing",
        "all": "All supported geographic observations eligible",
    }
    return mapping.get(scope, mapping["romania"])


def _latest_run_by_provider(runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for run in runs:
        provider_id = run.get("provider_id")
        if not provider_id or provider_id in latest:
            continue
        latest[str(provider_id)] = run
    return latest


def _public_provider_row(
    src: dict[str, Any],
    *,
    health: dict[str, Any] | None,
    last_run: dict[str, Any] | None,
    settings: Settings,
    configured_scope: str,
) -> dict[str, Any]:
    provider_id = str(src.get("provider_id") or "")
    enabled = bool(src.get("enabled", True))
    describe = {
        "live_access_status": src.get("access_type") or src.get("live_access_status"),
        "geographic_coverage": src.get("geographic_coverage"),
    }
    execution_mode = resolve_provider_execution_mode(
        provider_id=provider_id,
        enabled=enabled,
        settings=settings,
        health=health,
        last_run=last_run,
        describe=describe,
    )
    public_health = _strip_health(health) if health else None
    return {
        "provider_id": provider_id,
        "display_name": src.get("display_name") or provider_id,
        "enabled": enabled,
        "execution_mode": execution_mode,
        "provider_geographic_coverage": src.get("geographic_coverage"),
        "configured_geographic_scope": configured_scope,
        "scope_note": (
            "Provider coverage describes ingestion reach; configured scope filters intelligence."
        ),
        "current_status": (public_health or {}).get(
            "current_status", ProviderHealthStatus.UNKNOWN.value
        ),
        "incident_categories": list(src.get("incident_categories") or []),
        "health": public_health,
        "last_run_status": (last_run or {}).get("status"),
    }


def _strip_health(health: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "provider_id",
        "display_name",
        "current_status",
        "last_attempt_at",
        "last_success_at",
        "last_failure_at",
        "consecutive_failures",
        "observations_received",
        "observations_rejected",
        "observations_persisted",
        "last_fetch_duration_seconds",
        "last_execution_mode",
        "updated_at",
    }
    cleaned = {k: health[k] for k in allowed if k in health}
    error = health.get("last_error")
    if error:
        cleaned["last_error"] = _strip_secrets(str(error))
    return cleaned


def _strip_secrets(text: str) -> str:
    for token_key in ("token", "api_key", "authorization", "bearer"):
        if token_key in text.lower():
            return "[REDACTED]"
    return text


def _public_cycle(cycle_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "intelligence_cycle_id": cycle_state.get("intelligence_cycle_id"),
        "correlation_cycle_id": cycle_state.get("correlation_cycle_id"),
        "detection_fingerprint": cycle_state.get("detection_fingerprint"),
        "reconciled_at": (
            cycle_state.get("reconciled_at").isoformat()
            if cycle_state.get("reconciled_at") is not None
            and hasattr(cycle_state.get("reconciled_at"), "isoformat")
            else cycle_state.get("reconciled_at")
        ),
    }


def _correlation_diagnostics(
    correlations: list[CorrelationResult],
    *,
    correlation_rows: list[dict[str, Any]],
    cycle_state: dict[str, Any],
    correlation_state: str,
) -> dict[str, Any]:
    current_cycle_id = cycle_state.get("intelligence_cycle_id")
    current_row_ids = {
        row.get("correlation_id")
        for row in correlation_rows
        if current_cycle_id and row.get("intelligence_cycle_id") == current_cycle_id
    }
    current_rows = [c for c in correlations if c.correlation_id in current_row_ids] if current_cycle_id else list(correlations)
    stale_count = sum(
        1
        for row in correlation_rows
        if row.get("intelligence_cycle_id")
        and current_cycle_id
        and row.get("intelligence_cycle_id") != current_cycle_id
    )
    strengths = [c.strength for c in current_rows if c.strength is not None]

    by_rule = Counter(c.correlation_rule for c in current_rows)
    by_relationship = Counter(c.relationship_type for c in current_rows)
    by_pair: Counter[str] = Counter()
    by_country: Counter[str] = Counter()

    for corr in current_rows:
        providers = sorted(corr.participating_provider_ids)
        if len(providers) >= 2:
            by_pair["+".join(providers[:2])] += 1
        scope = corr.provenance_summary.get("geographic_scope")
        if scope:
            by_country[str(scope)] += 1

    unavailable_count = 1 if correlation_state == "unavailable" and not current_rows else 0

    return {
        "total": len(current_rows),
        "by_rule": dict(by_rule.most_common(MAX_RULE_BUCKETS)),
        "by_provider_pair": dict(by_pair.most_common(MAX_PAIR_BUCKETS)),
        "by_relationship_type": dict(by_relationship.most_common(MAX_RULE_BUCKETS)),
        "average_strength": round(sum(strengths) / len(strengths), 4) if strengths else None,
        "maximum_strength": round(max(strengths), 4) if strengths else None,
        "by_country": dict(by_country.most_common(MAX_COUNTRY_BUCKETS)),
        "current_cycle_id": current_cycle_id,
        "stale_count": stale_count,
        "unavailable_count": unavailable_count,
    }


def _evidence_aggregate(
    active_events: list[dict[str, Any]],
    correlation_state: str,
) -> dict[str, Any]:
    return {
        "correlation_state": correlation_state,
        "active_event_count": len(active_events),
        "categories": dict(Counter(str(e.get("incident_category") or "unknown") for e in active_events)),
    }


def _scoped_regions(
    active_events: list[dict[str, Any]],
    scope_policy: GeographicScopePolicy,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for event in sorted(
        active_events,
        key=lambda e: (
            str(e.get("country") or ""),
            str(e.get("region") or ""),
            str(e.get("incident_category") or ""),
        ),
    ):
        country = str(event.get("country") or "Unknown")
        region = str(event.get("region") or "Unknown")
        category = str(event.get("incident_category") or "unknown")
        key = (country, region, category)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "country": country,
                "region": region,
                "incident_category": category,
                "in_configured_scope": scope_policy.event_in_scope(event),
            }
        )
        if len(rows) >= MAX_REGIONS:
            break
    return rows
