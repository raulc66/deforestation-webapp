"""Read-time AOI intelligence counts — organization and AOI scoped."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.ecosystem.forest_disturbance_constants import InvestigationPriority
from app.services.aoi_enrichment_service import AoiEnrichmentService


def _priority_rank(priority: str) -> int:
    order = {
        InvestigationPriority.LOW.value: 0,
        InvestigationPriority.MEDIUM.value: 1,
        InvestigationPriority.HIGH.value: 2,
        InvestigationPriority.CRITICAL.value: 3,
    }
    return order.get(str(priority or ""), 0)


def _event_coordinates(event: dict[str, Any]) -> tuple[float | None, float | None]:
    lat = event.get("latitude")
    lng = event.get("longitude")
    if lat is None or lng is None:
        meta = event.get("metadata") or {}
        lat = meta.get("latitude", lat)
        lng = meta.get("longitude", lng)
    try:
        return (
            float(lat) if lat is not None else None,
            float(lng) if lng is not None else None,
        )
    except (TypeError, ValueError):
        return None, None


class AoiIntelligenceSummaryService:
    """Deterministic read-model counts per monitored area."""

    def __init__(self, aoi_enrichment: AoiEnrichmentService | None = None) -> None:
        self._aoi = aoi_enrichment or AoiEnrichmentService()

    def summarize_areas(
        self,
        *,
        organization_id: str,
        areas: list[dict[str, Any]],
        active_events: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Return per-area-id intelligence summary dicts."""
        summaries: dict[str, dict[str, Any]] = {
            str(area["id"]): self._empty_summary() for area in areas if area.get("id")
        }
        if not areas:
            return summaries

        for event in active_events:
            category = str(event.get("incident_category") or "")
            lat, lng = _event_coordinates(event)
            if category == "forest_disturbance":
                disturbance = (event.get("metadata") or {}).get("forest_disturbance") or {}
                enriched = self._aoi.enrich_disturbance_item(
                    latitude=lat,
                    longitude=lng,
                    organization_id=organization_id,
                    areas=areas,
                    disturbance_block=disturbance,
                )
                if not enriched.get("customer_relevance"):
                    continue
                priority = str(enriched.get("investigation_priority") or "")
                matches = enriched.get("monitored_area_matches") or []
            else:
                from app.services.aoi_geometry import match_point_to_areas

                if lat is None or lng is None:
                    continue
                matches = match_point_to_areas(lat, lng, areas)
                if not matches:
                    continue
                priority = str(event.get("severity") or "low")
                if priority in {"high", "critical"}:
                    priority = InvestigationPriority.HIGH.value
                elif priority == "medium":
                    priority = InvestigationPriority.MEDIUM.value
                else:
                    priority = InvestigationPriority.LOW.value

            detected_at = event.get("last_detected_at") or event.get("first_detected_at")
            for match in matches:
                area_id = str(match.get("id") or "")
                if area_id not in summaries:
                    continue
                row = summaries[area_id]
                row["active_intelligence_count"] += 1
                if category == "forest_disturbance":
                    row["active_disturbance_count"] += 1
                if _priority_rank(priority) >= _priority_rank(InvestigationPriority.HIGH.value):
                    row["high_priority_count"] += 1
                if _priority_rank(priority) >= _priority_rank(InvestigationPriority.CRITICAL.value):
                    row["critical_count"] += 1
                if detected_at is not None:
                    current = row.get("latest_relevant_detection_at")
                    if current is None or detected_at > current:
                        row["latest_relevant_detection_at"] = detected_at
        return summaries

    @staticmethod
    def _empty_summary() -> dict[str, Any]:
        return {
            "active_intelligence_count": 0,
            "high_priority_count": 0,
            "critical_count": 0,
            "active_disturbance_count": 0,
            "latest_relevant_detection_at": None,
        }
