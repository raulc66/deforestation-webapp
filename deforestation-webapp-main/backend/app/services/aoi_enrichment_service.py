"""Tenant AOI enrichment for forest disturbance intelligence."""
from __future__ import annotations

from typing import Any

from app.core.ecosystem.authorization_context import (
    AuthorizationContextProvider,
    UnknownAuthorizationContextProvider,
    bounded_authorization_read_model,
)
from app.core.ecosystem.forest_disturbance_constants import (
    InvestigationPriority,
    assert_safe_assessment_language,
)
from app.services.aoi_geometry import match_point_to_areas

MAX_AOI_MATCHES = 5


def _priority_rank(priority: str) -> int:
    order = {
        InvestigationPriority.LOW.value: 0,
        InvestigationPriority.MEDIUM.value: 1,
        InvestigationPriority.HIGH.value: 2,
        InvestigationPriority.CRITICAL.value: 3,
    }
    return order.get(str(priority or ""), 0)


def _bump_priority(priority: str) -> str:
    rank = _priority_rank(priority)
    if rank >= _priority_rank(InvestigationPriority.HIGH.value):
        return InvestigationPriority.CRITICAL.value
    if rank >= _priority_rank(InvestigationPriority.MEDIUM.value):
        return InvestigationPriority.HIGH.value
    if rank >= _priority_rank(InvestigationPriority.LOW.value):
        return InvestigationPriority.MEDIUM.value
    return InvestigationPriority.LOW.value


class AoiEnrichmentService:
    """Post-detection contextual enrichment — not part of ingestion providers."""

    def __init__(
        self,
        authorization_provider: AuthorizationContextProvider | None = None,
    ) -> None:
        self._authorization = authorization_provider or UnknownAuthorizationContextProvider()

    def enrich_disturbance_item(
        self,
        *,
        latitude: float | None,
        longitude: float | None,
        organization_id: str,
        areas: list[dict[str, Any]],
        disturbance_block: dict[str, Any] | None,
    ) -> dict[str, Any]:
        block = dict(disturbance_block or {})
        if latitude is None or longitude is None:
            return {
                **block,
                "inside_monitored_area": False,
                "intersection_status": "no_coordinates",
                "monitored_area_matches": [],
            }

        matches = match_point_to_areas(latitude, longitude, areas)[:MAX_AOI_MATCHES]
        inside = bool(matches)
        intersection_status = "inside_one" if len(matches) == 1 else (
            "inside_many" if len(matches) > 1 else "outside_all"
        )

        auth = self._authorization.lookup(
            latitude=latitude,
            longitude=longitude,
            tenant_id=organization_id,
            monitored_area_id=matches[0]["id"] if matches else None,
        )
        auth_read = bounded_authorization_read_model(auth)
        block.setdefault("authorization_status", auth_read["authorization_status"])

        priority = str(block.get("investigation_priority") or InvestigationPriority.LOW.value)
        if inside:
            priority = _bump_priority(priority)

        assessment_label = str(
            block.get("assessment_label") or "Potential Unauthorized Forest Activity"
        )
        assert_safe_assessment_language(assessment_label)

        primary = matches[0] if matches else None
        return {
            **block,
            "inside_monitored_area": inside,
            "intersection_status": intersection_status,
            "monitored_area_matches": matches,
            "monitored_area_id": primary["id"] if primary else None,
            "monitored_area_name": primary["name"] if primary else None,
            "investigation_priority": priority,
            "customer_relevance": inside,
            "authorization_status": auth_read["authorization_status"],
            "authorization_source": auth_read.get("source"),
        }

    def bounded_monitored_area_summary(
        self,
        enriched_block: dict[str, Any] | None,
    ) -> dict[str, Any]:
        block = enriched_block or {}
        if not block.get("customer_relevance"):
            return {
                "relevance": "outside_monitored_area",
                "inside_monitored_area": False,
            }
        return {
            "id": block.get("monitored_area_id"),
            "name": block.get("monitored_area_name"),
            "relevance": "inside_monitored_area",
            "inside_monitored_area": True,
            "investigation_priority": block.get("investigation_priority"),
            "intersection_status": block.get("intersection_status"),
            "match_count": len(block.get("monitored_area_matches") or []),
        }

    def enrich_intelligence_evidence_payload(
        self,
        payload: dict[str, Any],
        *,
        active_events: list[dict[str, Any]],
        organization_id: str,
        areas: list[dict[str, Any]],
    ) -> dict[str, Any]:
        events_by_id = {
            str(event.get("id")): event for event in active_events if event.get("id")
        }
        enriched_items: list[dict[str, Any]] = []
        for item in payload.get("items") or []:
            if item.get("incident_category") != "forest_disturbance":
                enriched_items.append(item)
                continue
            event = events_by_id.get(str(item.get("event_id"))) or {}
            lat = event.get("latitude")
            lng = event.get("longitude")
            if lat is None or lng is None:
                meta = event.get("metadata") or {}
                lat = meta.get("latitude", lat)
                lng = meta.get("longitude", lng)
            disturbance = dict(item.get("disturbance_assessment") or {})
            enriched = self.enrich_disturbance_item(
                latitude=float(lat) if lat is not None else None,
                longitude=float(lng) if lng is not None else None,
                organization_id=organization_id,
                areas=areas,
                disturbance_block=disturbance,
            )
            new_item = dict(item)
            new_item["disturbance_assessment"] = enriched
            new_item["monitored_area"] = self.bounded_monitored_area_summary(enriched)
            enriched_items.append(new_item)
        return {**payload, "items": enriched_items}

    def enrich_map_marker(
        self,
        marker: dict[str, Any],
        *,
        organization_id: str,
        areas: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if marker.get("incident_category") != "forest_disturbance":
            return marker
        lat = marker.get("latitude")
        lng = marker.get("longitude")
        disturbance = marker.get("disturbance_assessment") or {}
        enriched = self.enrich_disturbance_item(
            latitude=float(lat) if lat is not None else None,
            longitude=float(lng) if lng is not None else None,
            organization_id=organization_id,
            areas=areas,
            disturbance_block=disturbance,
        )
        updated = dict(marker)
        updated["disturbance_assessment"] = enriched
        updated["monitored_area"] = self.bounded_monitored_area_summary(enriched)
        if enriched.get("inside_monitored_area"):
            updated["inside_monitored_area"] = True
            updated["investigation_priority"] = enriched.get("investigation_priority")
            updated["authorization_status"] = enriched.get("authorization_status")
        return updated
