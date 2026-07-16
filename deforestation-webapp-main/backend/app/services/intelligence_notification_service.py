"""Intelligence notification service — delivers ForestWatch events outside the application.

Architecture
------------
``NotificationProvider`` (ABC) — one implementation per delivery channel.
``DiscordWebhookProvider``  — posts rich Discord embeds via incoming webhooks.
``GenericWebhookProvider``  — POSTs a JSON payload to any HTTP endpoint.
``IntelligenceNotificationService`` — orchestrates all active providers and
    records history in MongoDB.

Provider activation
-------------------
Providers are constructed by the factory ``build_providers()`` and activate
**only** when their webhook URL is configured.  An empty URL means the provider
is silently skipped.

Failure isolation
-----------------
Every ``notify_*`` method is wrapped so that HTTP failures, timeouts, and
unexpected exceptions are caught, logged, and written to notification history
as ``success=False``.  They **never** propagate — ingestion and intelligence
reconciliation remain unaffected.

Notification triggers
---------------------
The public helpers map each trigger condition defined in the requirements to a
typed payload and call ``_dispatch()``:

    A. ``notify_new_anomaly``        — new IntelligenceEvent detected
    B. ``notify_escalation_change``  — escalation level upgraded
    C. ``notify_new_critical_anomaly`` — new event with critical severity
    D. ``notify_reliability_alert``  — reliability alert at critical severity

Cycle comparison
----------------
``dispatch_cycle_notifications()`` compares the current and previous active
event states produced by the scheduler and fires the appropriate helpers.
"""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import requests as _requests

if TYPE_CHECKING:
    from app.repositories.notification_history_repository import (
        NotificationHistoryRepository,
    )

logger = logging.getLogger("forestwatch.notifications")

# ---------------------------------------------------------------------------
# Notification payload
# ---------------------------------------------------------------------------

SEVERITY_COLORS: dict[str, int] = {
    "low": 0x2ECC71,       # green
    "medium": 0xF39C12,    # orange
    "high": 0xE74C3C,      # red
    "critical": 0x8E44AD,  # purple
}


class NotificationPayload:
    """Typed container for a single outbound notification."""

    __slots__ = (
        "event_type",
        "region",
        "severity",
        "escalation_level",
        "priority_score",
        "detected_at",
        "message",
    )

    def __init__(
        self,
        *,
        event_type: str,
        region: str,
        severity: str,
        escalation_level: str | None,
        priority_score: float | None,
        detected_at: datetime,
        message: str,
    ) -> None:
        self.event_type = event_type
        self.region = region
        self.severity = severity
        self.escalation_level = escalation_level
        self.priority_score = priority_score
        self.detected_at = detected_at
        self.message = message

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "region": self.region,
            "severity": self.severity,
            "escalation_level": self.escalation_level,
            "priority_score": self.priority_score,
            "detected_at": self.detected_at.isoformat(),
            "message": self.message,
        }


# ---------------------------------------------------------------------------
# Abstract provider
# ---------------------------------------------------------------------------


class NotificationProvider(ABC):
    """Base class for all notification delivery channels."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier, e.g. ``"discord"`` or ``"generic"``."""

    @abstractmethod
    async def send(self, payload: NotificationPayload) -> bool:
        """Deliver one notification.

        Returns ``True`` on success, ``False`` on any failure.
        Should not raise — callers rely on the boolean return.
        """


# ---------------------------------------------------------------------------
# HTTP helper (sync requests in thread pool so we don't need httpx)
# ---------------------------------------------------------------------------


def _sync_post(url: str, json_body: dict, headers: dict | None = None) -> int:
    """Blocking HTTP POST — run via asyncio.to_thread."""
    resp = _requests.post(
        url,
        json=json_body,
        headers=headers or {"Content-Type": "application/json"},
        timeout=10,
    )
    return resp.status_code


async def _async_post(url: str, json_body: dict, headers: dict | None = None) -> int:
    """Non-blocking wrapper around the blocking post."""
    return await asyncio.to_thread(_sync_post, url, json_body, headers)


# ---------------------------------------------------------------------------
# Discord webhook provider
# ---------------------------------------------------------------------------

_DISCORD_SEVERITY_LABELS: dict[str, str] = {
    "low": "Low",
    "medium": "Medium",
    "high": "High ⚠️",
    "critical": "CRITICAL 🚨",
}


class DiscordWebhookProvider(NotificationProvider):
    """Delivers rich embed messages to a Discord channel via incoming webhook."""

    def __init__(self, webhook_url: str) -> None:
        self._url = webhook_url

    @property
    def name(self) -> str:
        return "discord"

    async def send(self, payload: NotificationPayload) -> bool:
        color = SEVERITY_COLORS.get(payload.severity, 0x95A5A6)
        embed = {
            "title": f"🌲 ForestWatch Alert — {payload.region}",
            "description": payload.message,
            "color": color,
            "fields": [
                {"name": "Event Type", "value": payload.event_type, "inline": True},
                {
                    "name": "Severity",
                    "value": _DISCORD_SEVERITY_LABELS.get(payload.severity, payload.severity),
                    "inline": True,
                },
                {
                    "name": "Escalation",
                    "value": payload.escalation_level or "—",
                    "inline": True,
                },
                {
                    "name": "Priority Score",
                    "value": str(round(payload.priority_score, 3))
                    if payload.priority_score is not None
                    else "—",
                    "inline": True,
                },
                {
                    "name": "Detected At",
                    "value": payload.detected_at.strftime("%Y-%m-%d %H:%M UTC"),
                    "inline": True,
                },
            ],
            "footer": {"text": "ForestWatch Intelligence Platform"},
        }
        discord_body = {"embeds": [embed]}
        try:
            status = await _async_post(self._url, discord_body)
            # Discord returns 204 No Content on success
            return status in (200, 204)
        except Exception:
            logger.exception("DiscordWebhookProvider: HTTP request failed")
            return False


# ---------------------------------------------------------------------------
# Generic webhook provider
# ---------------------------------------------------------------------------


class GenericWebhookProvider(NotificationProvider):
    """Delivers a plain JSON notification payload to an arbitrary HTTP endpoint."""

    def __init__(self, webhook_url: str) -> None:
        self._url = webhook_url

    @property
    def name(self) -> str:
        return "generic"

    async def send(self, payload: NotificationPayload) -> bool:
        try:
            status = await _async_post(self._url, payload.to_dict())
            return 200 <= status < 300
        except Exception:
            logger.exception("GenericWebhookProvider: HTTP request failed")
            return False


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------


def build_providers(
    *,
    discord_webhook_url: str = "",
    generic_webhook_url: str = "",
) -> list[NotificationProvider]:
    """Construct and return the list of active providers.

    A provider is added only when its URL is non-empty.  This allows operators
    to activate individual channels by setting the corresponding env var.
    """
    providers: list[NotificationProvider] = []
    if discord_webhook_url.strip():
        providers.append(DiscordWebhookProvider(discord_webhook_url.strip()))
        logger.info("Notification provider active: discord")
    if generic_webhook_url.strip():
        providers.append(GenericWebhookProvider(generic_webhook_url.strip()))
        logger.info("Notification provider active: generic")
    if not providers:
        logger.info("No notification providers configured — notifications disabled")
    return providers


# ---------------------------------------------------------------------------
# Intelligence notification service
# ---------------------------------------------------------------------------

_ESCALATION_TRANSITIONS = frozenset({
    ("normal", "persistent"),
    ("persistent", "critical"),
})


class IntelligenceNotificationService:
    """Orchestrates outbound notifications for intelligence events.

    Responsibilities:
      - Accept typed trigger calls (new_anomaly, escalation_change, etc.).
      - Build a ``NotificationPayload`` for each trigger.
      - Dispatch to all active providers via ``_dispatch()``.
      - Record every attempt in ``notification_history``.
      - Never raise — all failures are logged and swallowed.
    """

    def __init__(
        self,
        providers: list[NotificationProvider],
        history_repo: NotificationHistoryRepository,
    ) -> None:
        self._providers = providers
        self._history = history_repo

    # ------------------------------------------------------------------ #
    # Public properties
    # ------------------------------------------------------------------ #

    @property
    def is_enabled(self) -> bool:
        """``True`` when at least one provider is configured."""
        return bool(self._providers)

    @property
    def provider_names(self) -> list[str]:
        return [p.name for p in self._providers]

    # ------------------------------------------------------------------ #
    # Internal dispatch
    # ------------------------------------------------------------------ #

    async def _dispatch(self, payload: NotificationPayload) -> None:
        """Send payload to every provider; log and record all results."""
        for provider in self._providers:
            success = False
            error: str | None = None
            try:
                success = await provider.send(payload)
                if not success:
                    error = f"Provider '{provider.name}' returned failure status"
            except Exception as exc:
                error = str(exc)
                logger.exception(
                    "Notification provider '%s' raised an unexpected exception",
                    provider.name,
                )

            try:
                await self._history.create_entry(
                    provider=provider.name,
                    event_type=payload.event_type,
                    region=payload.region,
                    success=success,
                    error=error,
                )
            except Exception:
                logger.exception(
                    "Failed to record notification history for provider '%s'",
                    provider.name,
                )

            if not success:
                logger.warning(
                    "Notification via '%s' failed — event_type=%s region=%s error=%s",
                    provider.name,
                    payload.event_type,
                    payload.region,
                    error,
                )
            else:
                logger.info(
                    "Notification sent via '%s' — event_type=%s region=%s",
                    provider.name,
                    payload.event_type,
                    payload.region,
                )

    # ------------------------------------------------------------------ #
    # Trigger A — new anomaly
    # ------------------------------------------------------------------ #

    async def notify_new_anomaly(self, event: dict) -> None:
        """Trigger A: fired when a new IntelligenceEvent is first detected."""
        region = event.get("region", "Unknown")
        severity = event.get("severity", "low")
        score = event.get("priority_score") or event.get("current_score") or 0.0
        payload = NotificationPayload(
            event_type="new_anomaly",
            region=region,
            severity=severity,
            escalation_level=event.get("escalation_level"),
            priority_score=score,
            detected_at=event.get("first_detected_at") or datetime.now(timezone.utc),
            message=(
                f"New deforestation anomaly detected in {region}. "
                f"Severity: {severity}. Priority score: {round(score, 3)}."
            ),
        )
        await self._dispatch(payload)

    # ------------------------------------------------------------------ #
    # Trigger B — escalation level change
    # ------------------------------------------------------------------ #

    async def notify_escalation_change(
        self, event: dict, old_level: str, new_level: str
    ) -> None:
        """Trigger B: fired on valid escalation upgrades (normal→persistent, persistent→critical).

        Silently skipped for invalid transitions.
        """
        if (old_level, new_level) not in _ESCALATION_TRANSITIONS:
            return
        region = event.get("region", "Unknown")
        severity = event.get("severity", "low")
        score = event.get("priority_score", 0.0)
        payload = NotificationPayload(
            event_type="escalation_change",
            region=region,
            severity=severity,
            escalation_level=new_level,
            priority_score=score,
            detected_at=event.get("last_detected_at") or datetime.now(timezone.utc),
            message=(
                f"Intelligence event escalated in {region}: "
                f"{old_level} → {new_level}. "
                f"Severity: {severity}. Priority score: {round(score, 3)}."
            ),
        )
        await self._dispatch(payload)

    # ------------------------------------------------------------------ #
    # Trigger C — new critical anomaly
    # ------------------------------------------------------------------ #

    async def notify_new_critical_anomaly(self, event: dict) -> None:
        """Trigger C: fired when a newly-detected event has critical severity."""
        region = event.get("region", "Unknown")
        score = event.get("priority_score") or event.get("current_score") or 0.0
        payload = NotificationPayload(
            event_type="new_critical_anomaly",
            region=region,
            severity="critical",
            escalation_level=event.get("escalation_level"),
            priority_score=score,
            detected_at=event.get("first_detected_at") or datetime.now(timezone.utc),
            message=(
                f"CRITICAL deforestation anomaly detected in {region}. "
                f"Immediate attention required. Priority score: {round(score, 3)}."
            ),
        )
        await self._dispatch(payload)

    # ------------------------------------------------------------------ #
    # Trigger D — reliability alert at critical severity
    # ------------------------------------------------------------------ #

    async def notify_reliability_alert(self, alert: dict) -> None:
        """Trigger D: fired when a FIRMS reliability alert reaches critical severity."""
        region = "Romania"
        score = alert.get("reliability_score", 0.0)
        payload = NotificationPayload(
            event_type="reliability_alert",
            region=region,
            severity="critical",
            escalation_level=None,
            priority_score=score,
            detected_at=datetime.now(timezone.utc),
            message=(
                f"Critical reliability alert: {alert.get('message', 'FIRMS source reliability critical.')} "
                f"Reliability score: {round(score, 3)}."
            ),
        )
        await self._dispatch(payload)

    # ------------------------------------------------------------------ #
    # Cycle comparison dispatcher
    # ------------------------------------------------------------------ #

    async def dispatch_cycle_notifications(
        self,
        *,
        current_active: dict[str, dict],
        prev_active: dict[str, dict],
        alerts_result: dict,
        prev_reliability_critical: bool,
    ) -> None:
        """Compare current vs. previous scheduler cycle states and send notifications.

        Fires:
          A — for every event present in current_active but absent from prev_active.
          C — subset of A where severity is "critical".
          B — for events present in both whose escalation_level changed on a valid
              transition (normal→persistent or persistent→critical).
          D — when a critical reliability alert appears for the first time this cycle.
        """
        for event_id, event in current_active.items():
            if event_id not in prev_active:
                # Trigger A
                await self.notify_new_anomaly(event)
                # Trigger C
                if event.get("severity") == "critical":
                    await self.notify_new_critical_anomaly(event)
            else:
                old_event = prev_active[event_id]
                old_esc = old_event.get("escalation_level", "normal")
                new_esc = event.get("escalation_level", "normal")
                # Trigger B
                if old_esc != new_esc:
                    await self.notify_escalation_change(event, old_esc, new_esc)

        # Trigger D — reliability alert transition into critical
        rel_alerts = [
            a
            for a in alerts_result.get("alerts", [])
            if a.get("type") == "reliability" and a.get("severity") == "critical"
        ]
        if rel_alerts and not prev_reliability_critical:
            await self.notify_reliability_alert(rel_alerts[0])

    # ------------------------------------------------------------------ #
    # Investigation triggers
    # ------------------------------------------------------------------ #

    async def notify_investigation_created(self, investigation: dict) -> None:
        region = investigation.get("region") or "Unknown"
        priority = investigation.get("priority", "medium")
        payload = NotificationPayload(
            event_type="investigation_created",
            region=region,
            severity=priority,
            escalation_level=None,
            priority_score=None,
            detected_at=datetime.now(timezone.utc),
            message=(
                f"Investigation created: {investigation.get('title', 'Untitled')} "
                f"({region}). Priority: {priority}."
            ),
        )
        await self._dispatch(payload)

    async def notify_investigation_assigned(self, investigation: dict) -> None:
        region = investigation.get("region") or "Unknown"
        assignee = investigation.get("assigned_to") or "Unassigned"
        payload = NotificationPayload(
            event_type="investigation_assigned",
            region=region,
            severity=investigation.get("priority", "medium"),
            escalation_level=None,
            priority_score=None,
            detected_at=datetime.now(timezone.utc),
            message=(
                f"Investigation assigned: {investigation.get('title', 'Untitled')} "
                f"→ {assignee}."
            ),
        )
        await self._dispatch(payload)

    async def notify_investigation_escalated(
        self, investigation: dict, new_priority: str
    ) -> None:
        region = investigation.get("region") or "Unknown"
        payload = NotificationPayload(
            event_type="investigation_escalated",
            region=region,
            severity=new_priority,
            escalation_level=None,
            priority_score=None,
            detected_at=datetime.now(timezone.utc),
            message=(
                f"Investigation escalated to {new_priority}: "
                f"{investigation.get('title', 'Untitled')} ({region})."
            ),
        )
        await self._dispatch(payload)

    async def notify_investigation_closed(self, investigation: dict) -> None:
        region = investigation.get("region") or "Unknown"
        payload = NotificationPayload(
            event_type="investigation_closed",
            region=region,
            severity=investigation.get("priority", "medium"),
            escalation_level=None,
            priority_score=None,
            detected_at=datetime.now(timezone.utc),
            message=(
                f"Investigation closed: {investigation.get('title', 'Untitled')} "
                f"({region}). Resolution: {investigation.get('resolution', 'N/A')}."
            ),
        )
        await self._dispatch(payload)
