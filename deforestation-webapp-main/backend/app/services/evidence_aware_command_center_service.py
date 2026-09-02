"""Evidence-aware Command Center read assembly."""
from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.core.demo.catalog import catalog_correlation
from app.core.demo.constants import DEMO_INTEL_COLLECTION
from app.modules.analytics.correlation_result import CorrelationResult
from app.modules.analytics.evidence_summary import build_intelligence_evidence_payload
from app.modules.analytics.intelligence_events_repository import IntelligenceEventsRepository
from app.repositories.correlation_repository import CorrelationRepository
from app.repositories.intelligence_cycle_repository import IntelligenceCycleRepository
from app.repositories.provider_health_repository import ProviderHealthRepository


class EvidenceAwareCommandCenterService:
    """Read-only evidence assembly for Command Center — no correlation execution."""

    def __init__(
        self,
        intel_repo: IntelligenceEventsRepository,
        correlation_repo: CorrelationRepository,
        cycle_repo: IntelligenceCycleRepository,
        health_repo: ProviderHealthRepository,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._intel_repo = intel_repo
        self._correlation_repo = correlation_repo
        self._cycle_repo = cycle_repo
        self._health_repo = health_repo
        self._settings = settings or get_settings()
        col = getattr(self._intel_repo, "col", None)
        self._demo = getattr(col, "name", "") == DEMO_INTEL_COLLECTION

    async def build_intelligence_evidence(self) -> dict[str, Any]:
        active_events = await self._intel_repo.find_active()
        cycle_state = await self._cycle_repo.get_current()
        health_rows = await self._health_repo.list_all()
        if self._demo:
            correlations = [catalog_correlation()]
            correlation_enabled = True
            include_provenance = True
        else:
            correlations = await self._load_correlations()
            correlation_enabled = self._settings.enable_cross_source_correlation
            include_provenance = self._settings.enable_intelligence_provenance

        return build_intelligence_evidence_payload(
            active_events,
            correlations=correlations,
            cycle_state=cycle_state,
            correlation_enabled=correlation_enabled,
            include_provenance=include_provenance,
            health_rows=health_rows,
        )

    async def get_correlation_evidence(self, correlation_id: str) -> dict[str, Any] | None:
        if self._demo:
            result = catalog_correlation()
            if result.correlation_id != correlation_id:
                return None
            payload = result.as_read_model()
            payload["correlation_state"] = "current"
            payload["intelligence_cycle_id"] = "demo-catalog"
            payload["correlation_cycle_id"] = "demo-catalog"
            return payload
        rows = await self._correlation_repo.list_all()
        cycle_state = await self._cycle_repo.get_current()
        current_cycle_id = (cycle_state or {}).get("intelligence_cycle_id")
        correlation_cycle_id = (cycle_state or {}).get("correlation_cycle_id")

        for row in rows:
            if row.get("correlation_id") != correlation_id:
                continue
            try:
                result = CorrelationResult.model_validate(row)
            except Exception:
                return None

            row_cycle = row.get("intelligence_cycle_id")
            if (
                self._settings.enable_cross_source_correlation
                and row_cycle
                and current_cycle_id
                and row_cycle != current_cycle_id
            ):
                correlation_state = "stale"
            elif self._settings.enable_cross_source_correlation and row_cycle == current_cycle_id:
                correlation_state = "current"
            elif not self._settings.enable_cross_source_correlation:
                correlation_state = "disabled"
            else:
                correlation_state = "unavailable"

            payload = result.as_read_model()
            payload["correlation_state"] = correlation_state
            payload["intelligence_cycle_id"] = row_cycle
            payload["correlation_cycle_id"] = correlation_cycle_id
            return payload
        return None

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
