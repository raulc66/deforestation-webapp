"""Organization-scoped alert evaluation — scheduler/command path only.

Responsibility boundary: this service decides *whether an organization should be
notified* and persists a ``pending`` :class:`AlertDeliveryRecord`. It never
sends anything and never touches IntelligenceEvents, reconciliation, detectors
or provider health. Dispatch is owned by :class:`CustomerAlertDispatcher`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.demo.identity import is_demo_organization
from app.core.ecosystem.forest_disturbance_constants import InvestigationPriority
from app.models.customer_alert import (
    AlertDeliveryRecord,
    AlertLifecycle,
    AlertPolicy,
    AlertStage,
    alert_dedupe_key,
)
from app.modules.analytics.evidence_summary import (
    build_evidence_summary,
    resolve_correlation_state,
)
from app.repositories.alert_delivery_repository import AlertDeliveryRepository
from app.repositories.alert_policy_repository import AlertPolicyRepository
from app.repositories.forest_monitoring_area_repository import ForestMonitoringAreaRepository
from app.repositories.organization_repository import OrganizationRepository
from app.services.aoi_enrichment_service import AoiEnrichmentService
from app.services.entitlement_service import EntitlementService

logger = logging.getLogger("forestwatch.customer_alerts.evaluation")

MAX_ORGANIZATIONS_PER_CYCLE = 500

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_PRIORITY_RANK = {
    InvestigationPriority.LOW.value: 0,
    InvestigationPriority.MEDIUM.value: 1,
    InvestigationPriority.HIGH.value: 2,
    InvestigationPriority.CRITICAL.value: 3,
}
_EVIDENCE_RANK = {
    "single_source": 0,
    "contextual_support": 1,
    "multi_source": 2,
}


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


def _empty_stats() -> dict[str, int]:
    return {
        "organizations": 0,
        "candidates_created": 0,
        "initial_created": 0,
        "escalation_created": 0,
        "resolution_created": 0,
        "suppressed_cooldown": 0,
        "skipped": 0,
    }


class CustomerAlertEvaluationService:
    """Evaluate persisted IntelligenceEvents against organization alert policies."""

    def __init__(
        self,
        *,
        org_repo: OrganizationRepository,
        policy_repo: AlertPolicyRepository,
        delivery_repo: AlertDeliveryRepository,
        area_repo: ForestMonitoringAreaRepository,
        entitlement_svc: EntitlementService,
        aoi_enrichment: AoiEnrichmentService | None = None,
    ) -> None:
        self._orgs = org_repo
        self._policies = policy_repo
        self._deliveries = delivery_repo
        self._areas = area_repo
        self._entitlements = entitlement_svc
        self._aoi = aoi_enrichment or AoiEnrichmentService()

    async def evaluate_cycle(
        self,
        *,
        active_events: list[dict[str, Any]],
        resolved_events: list[dict[str, Any]] | None = None,
        health_rows: list[dict[str, Any]] | None = None,
        correlation_enabled: bool = False,
        correlation_cycle_id: str | None = None,
        current_cycle_id: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, int]:
        """Create pending delivery records for every entitled organization.

        Never raises: a failure here must not invalidate the intelligence cycle.
        """
        stats = _empty_stats()
        try:
            evidence_map = self._build_evidence_map(
                active_events,
                health_rows=health_rows,
                correlation_enabled=correlation_enabled,
                correlation_cycle_id=correlation_cycle_id,
                current_cycle_id=current_cycle_id,
            )
            organizations = await self._list_organizations()

            for org in organizations:
                org_id = str(org.id)
                if is_demo_organization(org):
                    stats["skipped"] += 1
                    continue
                if not await self._entitlements.can_receive_alerts(org_id):
                    stats["skipped"] += 1
                    continue
                policies = await self._policies.list_for_organization(org_id, enabled_only=True)
                if not policies:
                    stats["skipped"] += 1
                    continue
                stats["organizations"] += 1
                area_dicts = await self._organization_areas(org_id)

                for policy in policies:
                    await self._evaluate_policy(
                        org_id=org_id,
                        policy=policy,
                        area_dicts=area_dicts,
                        active_events=active_events,
                        resolved_events=resolved_events or [],
                        evidence_map=evidence_map,
                        stats=stats,
                        now=now,
                    )
        except Exception:
            logger.exception("Customer alert evaluation failed — cycle continues")
        return stats

    # ------------------------------------------------------------------ #
    # Per-policy evaluation
    # ------------------------------------------------------------------ #

    async def _evaluate_policy(
        self,
        *,
        org_id: str,
        policy: AlertPolicy,
        area_dicts: list[dict[str, Any]],
        active_events: list[dict[str, Any]],
        resolved_events: list[dict[str, Any]],
        evidence_map: dict[str, dict[str, Any]],
        stats: dict[str, int],
        now: datetime | None,
    ) -> None:
        for event in active_events:
            match = self._match_event(
                event=event,
                policy=policy,
                area_dicts=area_dicts,
                org_id=org_id,
                evidence_map=evidence_map,
            )
            if match is None:
                continue
            created_stage = await self._create_active_stage(
                org_id=org_id,
                policy=policy,
                event=event,
                match=match,
                stats=stats,
                now=now,
            )
            if created_stage:
                stats["candidates_created"] += 1

        for event in resolved_events:
            created = await self._create_resolution(
                org_id=org_id,
                policy=policy,
                event=event,
                area_dicts=area_dicts,
                evidence_map=evidence_map,
            )
            if created:
                stats["resolution_created"] += 1
                stats["candidates_created"] += 1

    async def _create_active_stage(
        self,
        *,
        org_id: str,
        policy: AlertPolicy,
        event: dict[str, Any],
        match: dict[str, Any],
        stats: dict[str, int],
        now: datetime | None,
    ) -> str | None:
        """Create the initial alert, or an escalation when priority increased."""
        event_id = str(event.get("id") or "")
        if not event_id:
            return None

        initial_key = alert_dedupe_key(
            organization_id=org_id,
            policy_id=str(policy.id),
            intelligence_event_id=event_id,
            alert_stage=AlertStage.INITIAL.value,
        )
        existing_initial = await self._deliveries.find_by_dedupe_key(initial_key)

        if existing_initial is None:
            if await self._deliveries.within_cooldown(
                organization_id=org_id,
                policy_id=str(policy.id),
                intelligence_event_id=event_id,
                monitored_area_ids=list(match.get("monitored_area_ids") or []),
                cooldown_minutes=policy.cooldown_minutes,
                now=now,
            ):
                stats["suppressed_cooldown"] += 1
                return None
            await self._persist(
                org_id=org_id,
                policy=policy,
                event_id=event_id,
                stage=AlertStage.INITIAL.value,
                match=match,
                reason="policy_match",
                now=now,
            )
            stats["initial_created"] += 1
            return AlertStage.INITIAL.value

        notified = await self._deliveries.latest_sent_for_event(
            organization_id=org_id,
            policy_id=str(policy.id),
            intelligence_event_id=event_id,
        )
        if notified is None:
            return None
        if _PRIORITY_RANK.get(match["priority"], 0) <= _PRIORITY_RANK.get(
            str(notified.get("priority") or ""), 0
        ):
            return None

        escalation_key = alert_dedupe_key(
            organization_id=org_id,
            policy_id=str(policy.id),
            intelligence_event_id=event_id,
            alert_stage=AlertStage.ESCALATION.value,
        )
        if await self._deliveries.find_by_dedupe_key(escalation_key):
            return None
        if await self._deliveries.within_cooldown(
            organization_id=org_id,
            policy_id=str(policy.id),
            intelligence_event_id=event_id,
            monitored_area_ids=list(match.get("monitored_area_ids") or []),
            cooldown_minutes=policy.cooldown_minutes,
            now=now,
        ):
            stats["suppressed_cooldown"] += 1
            return None

        await self._persist(
            org_id=org_id,
            policy=policy,
            event_id=event_id,
            stage=AlertStage.ESCALATION.value,
            match=match,
            reason="priority_escalation",
            now=now,
        )
        stats["escalation_created"] += 1
        return AlertStage.ESCALATION.value

    async def _create_resolution(
        self,
        *,
        org_id: str,
        policy: AlertPolicy,
        event: dict[str, Any],
        area_dicts: list[dict[str, Any]],
        evidence_map: dict[str, dict[str, Any]],
    ) -> bool:
        event_id = str(event.get("id") or "")
        if not event_id:
            return False
        if str(event.get("status") or "") != "resolved":
            return False

        prior = await self._deliveries.latest_sent_for_event(
            organization_id=org_id,
            policy_id=str(policy.id),
            intelligence_event_id=event_id,
        )
        if prior is None:
            return False

        resolution_key = alert_dedupe_key(
            organization_id=org_id,
            policy_id=str(policy.id),
            intelligence_event_id=event_id,
            alert_stage=AlertStage.RESOLUTION.value,
        )
        if await self._deliveries.find_by_dedupe_key(resolution_key):
            return False

        match = self._match_event(
            event=event,
            policy=policy,
            area_dicts=area_dicts,
            org_id=org_id,
            evidence_map=evidence_map,
            ignore_thresholds=True,
        ) or {
            "monitored_area_ids": list(prior.get("monitored_area_ids") or []),
            "priority": str(prior.get("priority") or "medium"),
            "evidence_summary": prior.get("evidence_summary") or {},
        }

        # A resolution closes an alert the customer already received, so it is
        # intentionally exempt from the cooldown window.
        await self._persist(
            org_id=org_id,
            policy=policy,
            event_id=event_id,
            stage=AlertStage.RESOLUTION.value,
            match=match,
            reason="event_resolved",
            now=None,
        )
        return True

    async def _persist(
        self,
        *,
        org_id: str,
        policy: AlertPolicy,
        event_id: str,
        stage: str,
        match: dict[str, Any],
        reason: str,
        now: datetime | None,
    ) -> None:
        timestamp = now or datetime.now(timezone.utc)
        record = AlertDeliveryRecord(
            dedupe_key=alert_dedupe_key(
                organization_id=org_id,
                policy_id=str(policy.id),
                intelligence_event_id=event_id,
                alert_stage=stage,
            ),
            organization_id=org_id,
            policy_id=str(policy.id),
            intelligence_event_id=event_id,
            alert_stage=stage,
            monitored_area_ids=list(match.get("monitored_area_ids") or []),
            reason=reason,
            priority=str(match.get("priority") or "medium"),
            evidence_summary=match.get("evidence_summary") or {},
            lifecycle=AlertLifecycle.PENDING.value,
            created_at=timestamp,
            updated_at=timestamp,
        )
        await self._deliveries.create(record)

    # ------------------------------------------------------------------ #
    # Relevance matching
    # ------------------------------------------------------------------ #

    def _match_event(
        self,
        *,
        event: dict[str, Any],
        policy: AlertPolicy,
        area_dicts: list[dict[str, Any]],
        org_id: str,
        evidence_map: dict[str, dict[str, Any]],
        ignore_thresholds: bool = False,
    ) -> dict[str, Any] | None:
        category = str(event.get("incident_category") or "")
        if policy.incident_categories and category not in policy.incident_categories:
            return None

        lat, lng = _event_coordinates(event)
        enriched: dict[str, Any] = {}

        if category == "forest_disturbance":
            disturbance = (event.get("metadata") or {}).get("forest_disturbance") or {}
            enriched = self._aoi.enrich_disturbance_item(
                latitude=lat,
                longitude=lng,
                organization_id=org_id,
                areas=area_dicts,
                disturbance_block=disturbance,
            )
            if not enriched.get("customer_relevance"):
                return None
            monitored_ids = [
                str(m.get("id"))
                for m in (enriched.get("monitored_area_matches") or [])
                if m.get("id")
            ]
            priority = str(enriched.get("investigation_priority") or InvestigationPriority.LOW.value)
        else:
            from app.services.aoi_geometry import match_point_to_areas

            if lat is None or lng is None:
                return None
            matches = match_point_to_areas(lat, lng, area_dicts)
            if not matches:
                return None
            monitored_ids = [str(m["id"]) for m in matches]
            priority = str(event.get("severity") or "low")

        if policy.monitored_area_ids:
            allowed = set(policy.monitored_area_ids)
            monitored_ids = [mid for mid in monitored_ids if mid in allowed]
            if not monitored_ids:
                return None

        event_id = str(event.get("id") or "")
        evidence = evidence_map.get(event_id) or {}

        if not ignore_thresholds:
            if _PRIORITY_RANK.get(priority, 0) < _PRIORITY_RANK.get(
                policy.minimum_investigation_priority, 0
            ):
                return None
            if _SEVERITY_RANK.get(str(event.get("severity") or "low"), 0) < _SEVERITY_RANK.get(
                policy.minimum_severity, 0
            ):
                return None
            if policy.minimum_evidence_state and _EVIDENCE_RANK.get(
                str(evidence.get("evidence_state") or ""), 0
            ) < _EVIDENCE_RANK.get(policy.minimum_evidence_state, 0):
                return None

        return {
            "monitored_area_ids": monitored_ids,
            "priority": priority,
            "evidence_summary": evidence,
            "enriched_disturbance": enriched,
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _build_evidence_map(
        self,
        active_events: list[dict[str, Any]],
        *,
        health_rows: list[dict[str, Any]] | None,
        correlation_enabled: bool,
        correlation_cycle_id: str | None,
        current_cycle_id: str | None,
    ) -> dict[str, dict[str, Any]]:
        correlation_state = resolve_correlation_state(
            correlation_enabled=correlation_enabled,
            current_cycle_id=current_cycle_id,
            correlation_cycle_id=correlation_cycle_id,
            has_correlations=False,
        )
        health_by_provider = {
            str(row["provider_id"]): str(row.get("current_status") or "unknown")
            for row in (health_rows or [])
            if row.get("provider_id")
        }
        return {
            str(event.get("id")): build_evidence_summary(
                event,
                correlations=[],
                correlation_state=correlation_state,
                health_by_provider=health_by_provider,
            ).model_dump(mode="json")
            for event in active_events
            if event.get("id")
        }

    async def _list_organizations(self) -> list[Any]:
        lister = getattr(self._orgs, "list_all", None)
        if callable(lister):
            return await lister(limit=MAX_ORGANIZATIONS_PER_CYCLE)
        return await self._orgs.find_many({}, limit=MAX_ORGANIZATIONS_PER_CYCLE)

    async def _organization_areas(self, org_id: str) -> list[dict[str, Any]]:
        areas = await self._areas.list_for_organization(org_id, enabled_only=True)
        return [
            {
                "id": str(area.id),
                "name": area.name,
                "geometry": area.geometry,
                "enabled": area.enabled,
            }
            for area in areas
        ]
