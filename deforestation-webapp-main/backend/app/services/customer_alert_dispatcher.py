"""Dispatch pending customer alerts via organization notification channels.

State separation (deliberate):

``pending``    evaluation created the record, no dispatch attempted yet
``sent``       at least one enabled channel accepted the alert
``failed``     dispatch was attempted and every channel failed
``suppressed`` dispatch was refused before contacting any channel

Failures are recorded on the delivery record only. They never propagate to the
intelligence cycle, never alter provider health, and never re-enter evaluation.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.commercial.secret_storage import decrypt_secret
from app.models.customer_alert import AlertLifecycle
from app.modules.analytics.intelligence_events_repository import IntelligenceEventsRepository
from app.repositories.alert_delivery_repository import AlertDeliveryRepository
from app.repositories.alert_policy_repository import AlertPolicyRepository
from app.repositories.forest_monitoring_area_repository import ForestMonitoringAreaRepository
from app.repositories.organization_notification_channel_repository import (
    OrganizationNotificationChannelRepository,
)
from app.services.aoi_enrichment_service import AoiEnrichmentService
from app.services.customer_alert_payload import (
    build_forest_disturbance_alert_body,
    build_webhook_payload,
)
from app.services.notifications.email_sender import EmailSender, FakeEmailSender
from app.services.notifications.org_webhook_sender import OrgWebhookSender

logger = logging.getLogger("forestwatch.customer_alerts.dispatch")


class CustomerAlertDispatcher:
    """Deliver pending alert records — failure isolated from intelligence cycle."""

    def __init__(
        self,
        *,
        delivery_repo: AlertDeliveryRepository,
        policy_repo: AlertPolicyRepository,
        channel_repo: OrganizationNotificationChannelRepository,
        area_repo: ForestMonitoringAreaRepository,
        intel_repo: IntelligenceEventsRepository,
        email_sender: EmailSender | None = None,
        webhook_sender: OrgWebhookSender | None = None,
        aoi_enrichment: AoiEnrichmentService | None = None,
        app_secret: str = "",
    ) -> None:
        self._deliveries = delivery_repo
        self._policies = policy_repo
        self._channels = channel_repo
        self._areas = area_repo
        self._intel = intel_repo
        self._email = email_sender or FakeEmailSender()
        self._webhook = webhook_sender or OrgWebhookSender()
        self._aoi = aoi_enrichment or AoiEnrichmentService()
        self._app_secret = app_secret

    async def dispatch_pending(self, *, limit: int = 100) -> dict[str, int]:
        stats = {"attempted": 0, "sent": 0, "failed": 0, "suppressed": 0}
        pending = await self._deliveries.list_pending(limit=limit)
        for record in pending:
            stats["attempted"] += 1
            try:
                outcome = await self._dispatch_one(record)
            except Exception:
                # A malformed record or adapter defect must not stop the batch.
                logger.exception("Alert dispatch failed for record %s", record.get("id"))
                await self._finalize_failure(record, results=[], error="dispatch_error")
                outcome = AlertLifecycle.FAILED.value
            if outcome == AlertLifecycle.SENT.value:
                stats["sent"] += 1
            elif outcome == AlertLifecycle.SUPPRESSED.value:
                stats["suppressed"] += 1
            else:
                stats["failed"] += 1
        return stats

    async def _dispatch_one(self, record: dict[str, Any]) -> str:
        org_id = str(record.get("organization_id") or "")

        policy = await self._policies.find_by_id(str(record.get("policy_id") or ""))
        if policy is None or policy.organization_id != org_id or not policy.enabled:
            return await self._suppress(record, reason="policy_disabled")

        channels = await self._channels.list_by_ids(
            org_id,
            list(policy.notification_channel_ids),
        )
        enabled_channels = [
            channel
            for channel in channels
            if channel.enabled and channel.organization_id == org_id
        ]
        if not enabled_channels:
            return await self._suppress(record, reason="no_channels")

        event = await self._intel.find_by_id(str(record.get("intelligence_event_id") or ""))
        if event is None:
            return await self._suppress(record, reason="event_missing")

        body, webhook_payload, area_name = await self._build_payloads(record, event)

        results: list[dict[str, Any]] = []
        for channel in enabled_channels:
            results.append(
                await self._send_to_channel(
                    channel,
                    body=body,
                    webhook_payload=webhook_payload,
                    area_name=area_name,
                )
            )

        if any(result.get("success") for result in results):
            await self._finalize_success(record, results=results)
            return AlertLifecycle.SENT.value

        errors = [str(r.get("error")) for r in results if r.get("error")]
        await self._finalize_failure(
            record,
            results=results,
            error=errors[0] if errors else "delivery_failed",
        )
        return AlertLifecycle.FAILED.value

    async def _send_to_channel(
        self,
        channel: Any,
        *,
        body: str,
        webhook_payload: dict[str, Any],
        area_name: str,
    ) -> dict[str, Any]:
        base = {
            "channel_id": str(channel.id),
            "channel_type": channel.channel_type,
            "channel_name": channel.name,
        }
        if channel.channel_type == "email":
            recipients = [
                str(r).strip()
                for r in (channel.config.get("recipients") or [])
                if str(r).strip()
            ]
            result = await self._email.send(
                recipients=recipients,
                subject=f"ForestWatch Alert — {area_name}",
                body=body,
            )
            return {**base, "success": result.success, "error": result.error}

        if channel.channel_type == "webhook":
            secret = decrypt_secret(
                str(channel.config.get("secret_token_encrypted") or ""),
                app_secret=self._app_secret,
            )
            result = await self._webhook.send(
                url=str(channel.config.get("url") or ""),
                payload=webhook_payload,
                secret_token=secret,
            )
            return {
                **base,
                "success": result.success,
                "error": result.error,
                "status_code": result.status_code,
            }

        return {**base, "success": False, "error": "unsupported_channel_type"}

    async def _build_payloads(
        self,
        record: dict[str, Any],
        event: dict[str, Any],
    ) -> tuple[str, dict[str, Any], str]:
        org_id = str(record.get("organization_id") or "")
        areas = await self._areas.list_for_organization(org_id, enabled_only=True)
        area_dicts = [
            {"id": str(a.id), "name": a.name, "geometry": a.geometry, "enabled": a.enabled}
            for a in areas
        ]
        lat, lng = self._coordinates(event)
        disturbance = (event.get("metadata") or {}).get("forest_disturbance") or {}
        enriched = self._aoi.enrich_disturbance_item(
            latitude=lat,
            longitude=lng,
            organization_id=org_id,
            areas=area_dicts,
            disturbance_block=disturbance,
        )
        area_name = enriched.get("monitored_area_name") or "Monitored Area"
        evidence_summary = record.get("evidence_summary") or {}

        body = build_forest_disturbance_alert_body(
            event=event,
            enriched_disturbance=enriched,
            evidence_summary=evidence_summary,
            monitored_area_name=area_name,
        )
        webhook_payload = build_webhook_payload(
            organization_id=org_id,
            policy_id=str(record.get("policy_id") or ""),
            alert_stage=str(record.get("alert_stage") or ""),
            event=event,
            enriched_disturbance=enriched,
            evidence_summary=evidence_summary,
            monitored_area_ids=list(record.get("monitored_area_ids") or []),
            monitored_area_name=area_name,
            reason=str(record.get("reason") or ""),
            priority=str(record.get("priority") or "medium"),
        )
        return body, webhook_payload, area_name

    # ------------------------------------------------------------------ #
    # Terminal state writes
    # ------------------------------------------------------------------ #

    async def _finalize_success(
        self,
        record: dict[str, Any],
        *,
        results: list[dict[str, Any]],
    ) -> None:
        now = datetime.now(timezone.utc)
        failures = [str(r.get("error")) for r in results if not r.get("success") and r.get("error")]
        await self._deliveries.update(
            str(record["id"]),
            {
                "lifecycle": AlertLifecycle.SENT.value,
                "sent_at": now,
                "updated_at": now,
                "last_attempt_at": now,
                "dispatch_attempt_count": int(record.get("dispatch_attempt_count") or 0) + 1,
                "delivery_results": results,
                "suppression_reason": None,
                # Partial failure is retained for visibility without downgrading
                # an alert the customer did receive.
                "last_error": failures[0] if failures else None,
            },
        )

    async def _finalize_failure(
        self,
        record: dict[str, Any],
        *,
        results: list[dict[str, Any]],
        error: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        await self._deliveries.update(
            str(record["id"]),
            {
                "lifecycle": AlertLifecycle.FAILED.value,
                "updated_at": now,
                "last_attempt_at": now,
                "dispatch_attempt_count": int(record.get("dispatch_attempt_count") or 0) + 1,
                "delivery_results": results,
                "suppression_reason": None,
                "last_error": error,
            },
        )

    async def _suppress(self, record: dict[str, Any], *, reason: str) -> str:
        now = datetime.now(timezone.utc)
        await self._deliveries.update(
            str(record["id"]),
            {
                "lifecycle": AlertLifecycle.SUPPRESSED.value,
                "updated_at": now,
                "suppression_reason": reason,
                "last_error": None,
            },
        )
        return AlertLifecycle.SUPPRESSED.value

    @staticmethod
    def _coordinates(event: dict[str, Any]) -> tuple[float | None, float | None]:
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
