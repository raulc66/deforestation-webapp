"""Organization-scoped CRUD and read models for customer alerting.

Every method takes an ``organization_id`` resolved from the trusted
``OrganizationContext``; nothing here accepts a client-supplied organization.
Role checks reuse the existing organization role helpers rather than
introducing a second permission model.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.commercial.alert_semantics import (
    ALERT_EVIDENCE_STATES,
    ALERT_PRIORITY_LEVELS,
    ALERT_SEVERITY_LEVELS,
    MAX_CHANNEL_REFERENCES,
    MAX_COOLDOWN_MINUTES,
    MAX_EMAIL_RECIPIENTS,
    MAX_MONITORED_AREA_REFERENCES,
    MAX_POLICY_NAME_LENGTH,
    MIN_COOLDOWN_MINUTES,
    alert_stage_label,
    category_display_name,
    channel_type_label,
    delivery_state_label,
    supported_incident_categories,
    suppression_reason_label,
)
from app.core.commercial.secret_storage import encrypt_secret, redact_channel_config
from app.core.errors import AppError, ForbiddenError, NotFoundError
from app.core.organization.organization_roles import can_manage_monitoring_areas
from app.models.customer_alert import (
    AlertDeliveryChannelOutcome,
    AlertDeliveryPublic,
    AlertLifecycle,
    AlertOperationsOverview,
    AlertPolicy,
    AlertPolicyCreate,
    AlertPolicyPublic,
    AlertPolicyUpdate,
    NotificationChannelCreate,
    NotificationChannelPublic,
    NotificationChannelUpdate,
    OrganizationNotificationChannel,
)
from app.repositories.alert_delivery_repository import AlertDeliveryRepository
from app.repositories.alert_policy_repository import AlertPolicyRepository
from app.repositories.forest_monitoring_area_repository import ForestMonitoringAreaRepository
from app.repositories.organization_notification_channel_repository import (
    OrganizationNotificationChannelRepository,
)
from app.services.demo.demo_alert_simulation_service import (
    delivery_visible_in_demo_session,
)
from app.services.entitlement_service import EntitlementService

MAX_RECENT_DELIVERIES = 200
DEMO_HISTORY_SCAN_LIMIT = 2000
OVERVIEW_RECENT_LIMIT = 6


class AlertConfigurationError(AppError):
    status_code = 422
    code = "invalid_alert_configuration"


def _policy_public(policy: AlertPolicy) -> AlertPolicyPublic:
    return AlertPolicyPublic(
        id=str(policy.id),
        organization_id=policy.organization_id,
        name=policy.name,
        enabled=policy.enabled,
        monitored_area_ids=list(policy.monitored_area_ids),
        incident_categories=list(policy.incident_categories),
        minimum_investigation_priority=policy.minimum_investigation_priority,
        minimum_severity=policy.minimum_severity,
        minimum_evidence_state=policy.minimum_evidence_state,
        notification_channel_ids=list(policy.notification_channel_ids),
        cooldown_minutes=policy.cooldown_minutes,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


def _channel_public(channel: OrganizationNotificationChannel) -> NotificationChannelPublic:
    return NotificationChannelPublic(
        id=str(channel.id),
        organization_id=channel.organization_id,
        channel_type=channel.channel_type,
        name=channel.name,
        enabled=channel.enabled,
        config=redact_channel_config(channel.channel_type, channel.config),
        created_at=channel.created_at,
        updated_at=channel.updated_at,
    )


class AlertPolicyService:
    def __init__(
        self,
        policy_repo: AlertPolicyRepository,
        channel_repo: OrganizationNotificationChannelRepository,
        delivery_repo: AlertDeliveryRepository,
        entitlement_svc: EntitlementService,
        *,
        app_secret: str,
        area_repo: ForestMonitoringAreaRepository | None = None,
    ) -> None:
        self._policies = policy_repo
        self._channels = channel_repo
        self._deliveries = delivery_repo
        self._entitlements = entitlement_svc
        self._app_secret = app_secret
        self._areas = area_repo

    # ------------------------------------------------------------------ #
    # Policies
    # ------------------------------------------------------------------ #

    async def list_policies(self, organization_id: str, *, actor_role: str = "") -> dict:
        policies = await self._policies.list_for_organization(organization_id)
        return {
            "items": [_policy_public(policy) for policy in policies],
            "total": len(policies),
            "can_manage": can_manage_monitoring_areas(actor_role),
            "alert_delivery_available": await self._entitlements.can_receive_alerts(
                organization_id
            ),
        }

    async def get_policy(self, organization_id: str, policy_id: str) -> AlertPolicyPublic:
        policy = await self._require_policy(organization_id, policy_id)
        return _policy_public(policy)

    async def create_policy(
        self,
        organization_id: str,
        payload: AlertPolicyCreate,
        *,
        actor_role: str,
    ) -> AlertPolicyPublic:
        self._require_manage(actor_role, "alert policies")
        if not await self._entitlements.can_receive_alerts(organization_id):
            raise ForbiddenError("Alert delivery is not enabled for this organization")
        await self._enforce_policy_limit(organization_id)

        name = self._validate_name(payload.name)
        await self._validate_thresholds(
            organization_id,
            incident_categories=payload.incident_categories,
            minimum_investigation_priority=payload.minimum_investigation_priority,
            minimum_severity=payload.minimum_severity,
            minimum_evidence_state=payload.minimum_evidence_state,
            cooldown_minutes=payload.cooldown_minutes,
            monitored_area_ids=payload.monitored_area_ids,
            notification_channel_ids=payload.notification_channel_ids,
        )

        now = datetime.now(timezone.utc)
        policy = AlertPolicy(
            organization_id=organization_id,
            name=name,
            enabled=payload.enabled,
            monitored_area_ids=list(payload.monitored_area_ids),
            incident_categories=list(payload.incident_categories),
            minimum_investigation_priority=payload.minimum_investigation_priority,
            minimum_severity=payload.minimum_severity,
            minimum_evidence_state=payload.minimum_evidence_state,
            notification_channel_ids=list(payload.notification_channel_ids),
            cooldown_minutes=payload.cooldown_minutes,
            created_at=now,
            updated_at=now,
        )
        return _policy_public(await self._policies.insert(policy))

    async def update_policy(
        self,
        organization_id: str,
        policy_id: str,
        payload: AlertPolicyUpdate,
        *,
        actor_role: str,
    ) -> AlertPolicyPublic:
        self._require_manage(actor_role, "alert policies")
        existing = await self._require_policy(organization_id, policy_id)

        await self._validate_thresholds(
            organization_id,
            incident_categories=payload.incident_categories,
            minimum_investigation_priority=payload.minimum_investigation_priority,
            minimum_severity=payload.minimum_severity,
            minimum_evidence_state=payload.minimum_evidence_state,
            cooldown_minutes=payload.cooldown_minutes,
            monitored_area_ids=payload.monitored_area_ids,
            notification_channel_ids=payload.notification_channel_ids,
        )

        updates: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
        if payload.name is not None:
            updates["name"] = self._validate_name(payload.name)
        for field in (
            "enabled",
            "monitored_area_ids",
            "incident_categories",
            "minimum_investigation_priority",
            "minimum_severity",
            "notification_channel_ids",
            "cooldown_minutes",
        ):
            value = getattr(payload, field)
            if value is not None:
                updates[field] = value
        if payload.minimum_evidence_state is not None:
            updates["minimum_evidence_state"] = payload.minimum_evidence_state or None

        await self._policies.update(str(existing.id), updates)
        refreshed = await self._require_policy(organization_id, policy_id)
        return _policy_public(refreshed)

    async def set_policy_enabled(
        self,
        organization_id: str,
        policy_id: str,
        *,
        enabled: bool,
        actor_role: str,
    ) -> AlertPolicyPublic:
        return await self.update_policy(
            organization_id,
            policy_id,
            AlertPolicyUpdate(enabled=enabled),
            actor_role=actor_role,
        )

    async def delete_policy(
        self,
        organization_id: str,
        policy_id: str,
        *,
        actor_role: str,
    ) -> None:
        self._require_manage(actor_role, "alert policies")
        existing = await self._require_policy(organization_id, policy_id)
        await self._policies.delete(str(existing.id))

    # ------------------------------------------------------------------ #
    # Notification channels
    # ------------------------------------------------------------------ #

    async def list_channels(self, organization_id: str, *, actor_role: str = "") -> dict:
        channels = await self._channels.list_for_organization(organization_id)
        return {
            "items": [_channel_public(channel) for channel in channels],
            "total": len(channels),
            "can_manage": can_manage_monitoring_areas(actor_role),
        }

    async def create_channel(
        self,
        organization_id: str,
        payload: NotificationChannelCreate,
        *,
        actor_role: str,
        actor_email: str | None = None,
    ) -> NotificationChannelPublic:
        self._require_manage(actor_role, "notification channels")
        if not await self._entitlements.can_receive_alerts(organization_id):
            raise ForbiddenError("Alert delivery is not enabled for this organization")
        await self._enforce_channel_limit(organization_id)

        name = self._validate_name(payload.name)
        await self._constrain_trial_channel(
            organization_id,
            payload.channel_type,
            payload.config,
            actor_email=actor_email,
        )
        config = self._prepare_channel_config(payload.channel_type, payload.config)
        now = datetime.now(timezone.utc)
        channel = OrganizationNotificationChannel(
            organization_id=organization_id,
            channel_type=payload.channel_type,
            name=name,
            enabled=payload.enabled,
            config=config,
            created_at=now,
            updated_at=now,
        )
        return _channel_public(await self._channels.insert(channel))

    async def update_channel(
        self,
        organization_id: str,
        channel_id: str,
        payload: NotificationChannelUpdate,
        *,
        actor_role: str,
        actor_email: str | None = None,
    ) -> NotificationChannelPublic:
        self._require_manage(actor_role, "notification channels")
        existing = await self._require_channel(organization_id, channel_id)

        updates: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
        if payload.name is not None:
            updates["name"] = self._validate_name(payload.name)
        if payload.enabled is not None:
            updates["enabled"] = payload.enabled
        if payload.config is not None:
            await self._constrain_trial_channel(
                organization_id,
                existing.channel_type,
                payload.config,
                actor_email=actor_email,
            )
            updates["config"] = self._prepare_channel_config(
                existing.channel_type,
                payload.config,
                existing_config=existing.config,
            )
        await self._channels.update(str(existing.id), updates)
        refreshed = await self._require_channel(organization_id, channel_id)
        return _channel_public(refreshed)

    async def set_channel_enabled(
        self,
        organization_id: str,
        channel_id: str,
        *,
        enabled: bool,
        actor_role: str,
    ) -> NotificationChannelPublic:
        return await self.update_channel(
            organization_id,
            channel_id,
            NotificationChannelUpdate(enabled=enabled),
            actor_role=actor_role,
        )

    async def delete_channel(
        self,
        organization_id: str,
        channel_id: str,
        *,
        actor_role: str,
    ) -> None:
        self._require_manage(actor_role, "notification channels")
        existing = await self._require_channel(organization_id, channel_id)
        await self._channels.delete(str(existing.id))

    # ------------------------------------------------------------------ #
    # Delivery history and operations overview
    # ------------------------------------------------------------------ #

    async def list_deliveries(
        self,
        organization_id: str,
        *,
        limit: int = 50,
        lifecycle: str | None = None,
        demo_session_id: str | None = None,
        demo_reset_count: int | None = None,
    ) -> dict:
        bounded = max(1, min(int(limit or 50), MAX_RECENT_DELIVERIES))
        fetch_limit = DEMO_HISTORY_SCAN_LIMIT if demo_session_id else bounded
        rows = await self._deliveries.list_for_organization(
            organization_id,
            limit=fetch_limit,
            lifecycle=lifecycle,
            **self._demo_visitor_list_kwargs(demo_session_id),
        )
        rows = self._scope_demo_visitor_rows(
            rows,
            demo_session_id=demo_session_id,
            demo_reset_count=demo_reset_count,
        )[:bounded]
        items = await self._shape_deliveries(organization_id, rows)
        return {"items": items, "total": len(items)}

    async def alert_operations_overview(
        self,
        organization_id: str,
        *,
        actor_role: str = "",
        demo_session_id: str | None = None,
        demo_reset_count: int | None = None,
    ) -> AlertOperationsOverview:
        policies = await self._policies.list_for_organization(organization_id)
        channels = await self._channels.list_for_organization(organization_id)
        if demo_session_id is not None:
            scoped_rows = self._scope_demo_visitor_rows(
                await self._deliveries.list_for_organization(
                    organization_id,
                    limit=DEMO_HISTORY_SCAN_LIMIT,
                    **self._demo_visitor_list_kwargs(demo_session_id),
                ),
                demo_session_id=demo_session_id,
                demo_reset_count=demo_reset_count,
            )
            counts: dict[str, int] = {}
            for row in scoped_rows:
                key = str(row.get("lifecycle") or "unknown")
                counts[key] = counts.get(key, 0) + 1
            recent_rows = scoped_rows[:OVERVIEW_RECENT_LIMIT]
        else:
            counts = await self._deliveries.count_by_lifecycle(organization_id)
            recent_rows = await self._deliveries.list_for_organization(
                organization_id,
                limit=OVERVIEW_RECENT_LIMIT,
            )
        recent = await self._shape_deliveries(organization_id, recent_rows)

        pending = int(counts.get(AlertLifecycle.PENDING.value, 0))
        failed = int(counts.get(AlertLifecycle.FAILED.value, 0))
        suppressed = int(counts.get(AlertLifecycle.SUPPRESSED.value, 0))

        return AlertOperationsOverview(
            alert_delivery_available=await self._entitlements.can_receive_alerts(
                organization_id
            ),
            can_manage=can_manage_monitoring_areas(actor_role),
            policy_count=len(policies),
            active_policy_count=sum(1 for policy in policies if policy.enabled),
            channel_count=len(channels),
            enabled_channel_count=sum(1 for channel in channels if channel.enabled),
            channel_states=[
                {
                    "id": str(channel.id),
                    "name": channel.name,
                    "channel_type": channel.channel_type,
                    "channel_type_label": channel_type_label(channel.channel_type),
                    "enabled": channel.enabled,
                    "configured": self._channel_is_configured(channel),
                }
                for channel in channels
            ],
            pending_count=pending,
            sent_count=int(counts.get(AlertLifecycle.SENT.value, 0)),
            failed_count=failed,
            suppressed_count=suppressed,
            attention_count=failed + suppressed,
            recent_deliveries=recent,
        )

    async def _shape_deliveries(
        self,
        organization_id: str,
        rows: list[dict[str, Any]],
    ) -> list[AlertDeliveryPublic]:
        if not rows:
            return []
        policy_names = {
            str(policy.id): policy.name
            for policy in await self._policies.list_for_organization(organization_id)
        }
        area_names: dict[str, str] = {}
        if self._areas is not None:
            areas = await self._areas.list_for_organization(organization_id)
            area_names = {str(area.id): area.name for area in areas}

        items: list[AlertDeliveryPublic] = []
        for row in rows:
            if str(row.get("organization_id") or "") != organization_id:
                continue
            category = self._delivery_category(row)
            outcomes = [
                self._channel_outcome_from_result(result)
                for result in (row.get("delivery_results") or [])
            ]
            items.append(
                AlertDeliveryPublic(
                    id=str(row.get("id")),
                    dedupe_key=str(row.get("dedupe_key") or ""),
                    organization_id=organization_id,
                    policy_id=str(row.get("policy_id") or ""),
                    policy_name=policy_names.get(str(row.get("policy_id") or "")),
                    intelligence_event_id=str(row.get("intelligence_event_id") or ""),
                    incident_category=category,
                    incident_category_label=(
                        category_display_name(category) if category else None
                    ),
                    alert_stage=str(row.get("alert_stage") or ""),
                    alert_stage_label=alert_stage_label(row.get("alert_stage")),
                    monitored_area_ids=list(row.get("monitored_area_ids") or []),
                    monitored_area_names=[
                        area_names[area_id]
                        for area_id in (row.get("monitored_area_ids") or [])
                        if area_id in area_names
                    ],
                    reason=str(row.get("reason") or ""),
                    priority=str(row.get("priority") or "medium"),
                    evidence_summary=row.get("evidence_summary") or {},
                    lifecycle=str(row.get("lifecycle") or ""),
                    delivery_state_label=delivery_state_label(row.get("lifecycle")),
                    created_at=row["created_at"],
                    updated_at=row.get("updated_at") or row["created_at"],
                    sent_at=row.get("sent_at"),
                    dispatch_attempt_count=int(row.get("dispatch_attempt_count") or 0),
                    last_attempt_at=row.get("last_attempt_at"),
                    channel_outcomes=outcomes,
                    suppression_reason=row.get("suppression_reason"),
                    suppression_reason_label=suppression_reason_label(
                        row.get("suppression_reason")
                    ),
                    last_error=row.get("last_error"),
                    simulated=self._delivery_is_simulated(row, outcomes),
                )
            )
        return items

    @staticmethod
    def _demo_visitor_list_kwargs(demo_session_id: str | None) -> dict[str, str]:
        if not demo_session_id:
            return {}
        return {"demo_visitor_session_id": demo_session_id}

    @staticmethod
    def _scope_demo_visitor_rows(
        rows: list[dict[str, Any]],
        *,
        demo_session_id: str | None,
        demo_reset_count: int | None,
    ) -> list[dict[str, Any]]:
        if not demo_session_id:
            return rows
        reset_count = int(demo_reset_count or 0)
        return [
            row
            for row in rows
            if delivery_visible_in_demo_session(
                row, session_id=demo_session_id, reset_count=reset_count
            )
        ]

    @staticmethod
    def _channel_result_is_simulated(result: dict[str, Any]) -> bool:
        return bool(result.get("simulated")) or str(result.get("status") or "") == "simulated"

    @classmethod
    def _channel_outcome_from_result(cls, result: dict[str, Any]) -> AlertDeliveryChannelOutcome:
        simulated = cls._channel_result_is_simulated(result)
        return AlertDeliveryChannelOutcome(
            channel_id=str(result.get("channel_id") or ""),
            channel_type=str(result.get("channel_type") or ""),
            channel_type_label=channel_type_label(result.get("channel_type")),
            channel_name=result.get("channel_name"),
            delivered=bool(result.get("success")),
            failure_reason=None if simulated else result.get("error"),
            simulated=simulated,
        )

    @classmethod
    def _delivery_is_simulated(
        cls,
        row: dict[str, Any],
        outcomes: list[AlertDeliveryChannelOutcome],
    ) -> bool:
        evidence = row.get("evidence_summary") or {}
        if evidence.get("simulated") is True:
            return True
        return any(outcome.simulated for outcome in outcomes)

    @staticmethod
    def _delivery_category(row: dict[str, Any]) -> str | None:
        evidence = row.get("evidence_summary") or {}
        category = evidence.get("incident_category")
        return str(category) if category else None

    @staticmethod
    def _channel_is_configured(channel: OrganizationNotificationChannel) -> bool:
        config = channel.config or {}
        if channel.channel_type == "email":
            return bool(config.get("recipients"))
        if channel.channel_type == "webhook":
            return bool(config.get("url"))
        return False

    # ------------------------------------------------------------------ #
    # Validation helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _require_manage(actor_role: str, subject: str) -> None:
        if not can_manage_monitoring_areas(actor_role):
            raise ForbiddenError(f"Insufficient permissions to manage {subject}")

    async def _enforce_policy_limit(self, organization_id: str) -> None:
        profile = await self._entitlements.get_profile(organization_id)
        existing = await self._policies.list_for_organization(organization_id)
        if len(existing) >= max(int(profile.alert_policy_limit), 0):
            raise ForbiddenError("Alert policy limit reached for this organization")

    async def _enforce_channel_limit(self, organization_id: str) -> None:
        profile = await self._entitlements.get_profile(organization_id)
        existing = await self._channels.list_for_organization(organization_id)
        if len(existing) >= max(int(profile.notification_channel_limit), 0):
            raise ForbiddenError(
                "Notification channel limit reached for this organization"
            )

    async def _constrain_trial_channel(
        self,
        organization_id: str,
        channel_type: str,
        config: dict[str, Any] | None,
        *,
        actor_email: str | None,
    ) -> None:
        from app.core.commercial.trial_profile import TRIAL_ENTITLEMENT_SOURCE

        profile = await self._entitlements.get_profile(organization_id)
        if profile.source != TRIAL_ENTITLEMENT_SOURCE:
            return
        if channel_type != "email":
            raise ForbiddenError(
                "Trial organizations can only deliver alerts to the account email"
            )
        allowed = str(actor_email or "").strip().lower()
        recipients = [
            str(value).strip().lower()
            for value in ((config or {}).get("recipients") or [])
            if str(value).strip()
        ]
        if not allowed or not recipients or any(item != allowed for item in recipients):
            raise ForbiddenError(
                "Trial alerts can only be sent to the signed-in account email"
            )

    async def _require_policy(self, organization_id: str, policy_id: str) -> AlertPolicy:
        policy = await self._policies.find_for_organization(organization_id, policy_id)
        if policy is None:
            raise NotFoundError(f"Alert policy {policy_id} not found")
        return policy

    async def _require_channel(
        self,
        organization_id: str,
        channel_id: str,
    ) -> OrganizationNotificationChannel:
        channel = await self._channels.find_for_organization(organization_id, channel_id)
        if channel is None:
            raise NotFoundError(f"Notification channel {channel_id} not found")
        return channel

    @staticmethod
    def _validate_name(name: str) -> str:
        cleaned = str(name or "").strip()
        if not cleaned:
            raise AlertConfigurationError("Name is required")
        if len(cleaned) > MAX_POLICY_NAME_LENGTH:
            raise AlertConfigurationError(
                f"Name must be {MAX_POLICY_NAME_LENGTH} characters or fewer"
            )
        return cleaned

    async def _validate_thresholds(
        self,
        organization_id: str,
        *,
        incident_categories: list[str] | None,
        minimum_investigation_priority: str | None,
        minimum_severity: str | None,
        minimum_evidence_state: str | None,
        cooldown_minutes: int | None,
        monitored_area_ids: list[str] | None,
        notification_channel_ids: list[str] | None,
    ) -> None:
        if incident_categories is not None:
            if not incident_categories:
                raise AlertConfigurationError("Select at least one intelligence category")
            supported = set(supported_incident_categories())
            unknown = [c for c in incident_categories if c not in supported]
            if unknown:
                raise AlertConfigurationError(
                    f"Unsupported intelligence category: {unknown[0]}"
                )
        if minimum_investigation_priority is not None and (
            minimum_investigation_priority not in ALERT_PRIORITY_LEVELS
        ):
            raise AlertConfigurationError("Unsupported investigation priority threshold")
        if minimum_severity is not None and minimum_severity not in ALERT_SEVERITY_LEVELS:
            raise AlertConfigurationError("Unsupported severity threshold")
        if minimum_evidence_state:
            if minimum_evidence_state not in ALERT_EVIDENCE_STATES:
                raise AlertConfigurationError("Unsupported evidence threshold")
        if cooldown_minutes is not None and not (
            MIN_COOLDOWN_MINUTES <= cooldown_minutes <= MAX_COOLDOWN_MINUTES
        ):
            raise AlertConfigurationError(
                f"Cooldown must be between {MIN_COOLDOWN_MINUTES} and "
                f"{MAX_COOLDOWN_MINUTES} minutes"
            )
        if monitored_area_ids is not None:
            if len(monitored_area_ids) > MAX_MONITORED_AREA_REFERENCES:
                raise AlertConfigurationError("Too many monitored areas referenced")
            await self._validate_area_ownership(organization_id, monitored_area_ids)
        if notification_channel_ids is not None:
            if len(notification_channel_ids) > MAX_CHANNEL_REFERENCES:
                raise AlertConfigurationError("Too many notification channels referenced")
            await self._validate_channel_ownership(organization_id, notification_channel_ids)

    async def _validate_area_ownership(
        self,
        organization_id: str,
        area_ids: list[str],
    ) -> None:
        if not area_ids or self._areas is None:
            return
        owned = {
            str(area.id)
            for area in await self._areas.list_for_organization(organization_id)
        }
        missing = [area_id for area_id in area_ids if area_id not in owned]
        if missing:
            raise AlertConfigurationError("Monitored area is not available to this organization")

    async def _validate_channel_ownership(
        self,
        organization_id: str,
        channel_ids: list[str],
    ) -> None:
        if not channel_ids:
            return
        owned = {
            str(channel.id)
            for channel in await self._channels.list_for_organization(organization_id)
        }
        missing = [channel_id for channel_id in channel_ids if channel_id not in owned]
        if missing:
            raise AlertConfigurationError(
                "Notification channel is not available to this organization"
            )

    def _prepare_channel_config(
        self,
        channel_type: str,
        config: dict[str, Any] | None,
        *,
        existing_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Normalize channel configuration and encrypt write-only secrets.

        Secrets arrive as ``secret_token`` and are stored only as
        ``secret_token_encrypted``. An update that omits the secret preserves the
        previously stored value so the frontend never has to echo it back.
        """
        incoming = dict(config or {})
        prepared: dict[str, Any] = {}

        if channel_type == "email":
            recipients = [
                str(value).strip()
                for value in (incoming.get("recipients") or [])
                if str(value).strip()
            ]
            if not recipients:
                raise AlertConfigurationError("At least one email recipient is required")
            if len(recipients) > MAX_EMAIL_RECIPIENTS:
                raise AlertConfigurationError(
                    f"A maximum of {MAX_EMAIL_RECIPIENTS} recipients is supported"
                )
            for recipient in recipients:
                if "@" not in recipient or recipient.startswith("@") or recipient.endswith("@"):
                    raise AlertConfigurationError(f"Invalid email recipient: {recipient}")
            prepared["recipients"] = recipients
            return prepared

        if channel_type == "webhook":
            url = str(incoming.get("url") or "").strip()
            if not url:
                raise AlertConfigurationError("Webhook URL is required")
            if not url.startswith("https://"):
                raise AlertConfigurationError("Webhook URL must use HTTPS")
            prepared["url"] = url
            token = str(incoming.get("secret_token") or "").strip()
            if token:
                prepared["secret_token_encrypted"] = encrypt_secret(
                    token,
                    app_secret=self._app_secret,
                )
            elif existing_config and existing_config.get("secret_token_encrypted"):
                prepared["secret_token_encrypted"] = existing_config["secret_token_encrypted"]
            return prepared

        raise AlertConfigurationError(f"Unsupported channel type: {channel_type}")
