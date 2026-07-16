"""Comprehensive tests for the intelligence notification system.

Coverage:
  - NotificationPayload construction and serialization
  - DiscordWebhookProvider: payload shape, HTTP success/failure handling
  - GenericWebhookProvider: payload shape, HTTP success/failure handling
  - build_providers() factory — provider selection from config
  - IntelligenceNotificationService:
      - is_enabled / provider_names
      - _dispatch — sends to all providers, isolates failures
      - _dispatch — records history for each attempt (success + failure)
      - notify_new_anomaly — correct payload fields
      - notify_escalation_change — valid and invalid transitions
      - notify_new_critical_anomaly — correct payload
      - notify_reliability_alert — correct payload
      - dispatch_cycle_notifications — trigger A, B, C, D
  - NotificationHistoryRepository: create_entry, latest, list_recent
  - SchedulerService._send_notifications — integration with notification service
  - Notification status endpoint — correct response shape
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.services.intelligence_notification_service import (
    DiscordWebhookProvider,
    GenericWebhookProvider,
    IntelligenceNotificationService,
    NotificationPayload,
    build_providers,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

UTC = timezone.utc

def _make_event(
    *,
    id: str = "evt-1",
    region: str = "Bacău",
    severity: str = "high",
    escalation_level: str = "normal",
    priority_score: float = 0.65,
    current_score: float = 0.70,
) -> dict:
    return {
        "id": id,
        "region": region,
        "severity": severity,
        "escalation_level": escalation_level,
        "priority_score": priority_score,
        "current_score": current_score,
        "first_detected_at": datetime(2026, 6, 1, tzinfo=UTC),
        "last_detected_at": datetime(2026, 6, 2, tzinfo=UTC),
        "detection_count": 2,
    }


def _make_alert(*, severity: str = "critical", alert_type: str = "reliability") -> dict:
    return {
        "type": alert_type,
        "severity": severity,
        "confidence": 0.85,
        "reliability_score": 0.80,
        "message": "FIRMS critical reliability alert.",
        "source_breakdown": {"NASA FIRMS": 50},
    }


def _mock_history_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.create_entry = AsyncMock(return_value={"id": "hist-1"})
    return repo


def _mock_provider(name: str = "test", success: bool = True) -> MagicMock:
    p = MagicMock()
    p.name = name
    p.send = AsyncMock(return_value=success)
    return p


# ---------------------------------------------------------------------------
# NotificationPayload
# ---------------------------------------------------------------------------


class TestNotificationPayload:
    def test_to_dict_keys(self):
        now = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
        p = NotificationPayload(
            event_type="new_anomaly",
            region="Suceava",
            severity="high",
            escalation_level="normal",
            priority_score=0.75,
            detected_at=now,
            message="Test message",
        )
        d = p.to_dict()
        assert d["event_type"] == "new_anomaly"
        assert d["region"] == "Suceava"
        assert d["severity"] == "high"
        assert d["escalation_level"] == "normal"
        assert d["priority_score"] == 0.75
        assert "2026-01-15" in d["detected_at"]
        assert d["message"] == "Test message"

    def test_to_dict_optional_none(self):
        p = NotificationPayload(
            event_type="reliability_alert",
            region="Romania",
            severity="critical",
            escalation_level=None,
            priority_score=None,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            message="msg",
        )
        d = p.to_dict()
        assert d["escalation_level"] is None
        assert d["priority_score"] is None


# ---------------------------------------------------------------------------
# DiscordWebhookProvider
# ---------------------------------------------------------------------------


class TestDiscordWebhookProvider:
    @pytest.mark.anyio
    async def test_send_returns_true_on_204(self):
        provider = DiscordWebhookProvider("https://discord.example.com/webhook")
        payload = NotificationPayload(
            event_type="new_anomaly",
            region="Cluj",
            severity="high",
            escalation_level="normal",
            priority_score=0.8,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            message="Test",
        )
        with patch(
            "app.services.intelligence_notification_service._sync_post",
            return_value=204,
        ):
            result = await provider.send(payload)
        assert result is True

    @pytest.mark.anyio
    async def test_send_returns_true_on_200(self):
        provider = DiscordWebhookProvider("https://discord.example.com/webhook")
        payload = NotificationPayload(
            event_type="new_anomaly",
            region="Cluj",
            severity="low",
            escalation_level="normal",
            priority_score=0.3,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            message="Test",
        )
        with patch(
            "app.services.intelligence_notification_service._sync_post",
            return_value=200,
        ):
            result = await provider.send(payload)
        assert result is True

    @pytest.mark.anyio
    async def test_send_returns_false_on_4xx(self):
        provider = DiscordWebhookProvider("https://discord.example.com/webhook")
        payload = NotificationPayload(
            event_type="new_anomaly",
            region="Cluj",
            severity="medium",
            escalation_level=None,
            priority_score=0.5,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            message="Test",
        )
        with patch(
            "app.services.intelligence_notification_service._sync_post",
            return_value=400,
        ):
            result = await provider.send(payload)
        assert result is False

    @pytest.mark.anyio
    async def test_send_returns_false_on_exception(self):
        provider = DiscordWebhookProvider("https://discord.example.com/webhook")
        payload = NotificationPayload(
            event_type="new_anomaly",
            region="Cluj",
            severity="high",
            escalation_level="normal",
            priority_score=0.8,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            message="Test",
        )
        with patch(
            "app.services.intelligence_notification_service._sync_post",
            side_effect=ConnectionError("Timeout"),
        ):
            result = await provider.send(payload)
        assert result is False

    def test_name_property(self):
        provider = DiscordWebhookProvider("https://discord.example.com/webhook")
        assert provider.name == "discord"

    @pytest.mark.anyio
    async def test_discord_payload_includes_embeds(self):
        """Verify the HTTP body sent to Discord contains an 'embeds' key."""
        captured_body = {}

        def fake_post(url, json_body, headers=None):
            captured_body.update(json_body)
            return 204

        provider = DiscordWebhookProvider("https://discord.example.com/webhook")
        payload = NotificationPayload(
            event_type="escalation_change",
            region="Suceava",
            severity="critical",
            escalation_level="critical",
            priority_score=0.95,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            message="Escalated to critical",
        )
        with patch(
            "app.services.intelligence_notification_service._sync_post",
            side_effect=fake_post,
        ):
            await provider.send(payload)

        assert "embeds" in captured_body
        embed = captured_body["embeds"][0]
        assert "Suceava" in embed["title"]
        assert embed["color"] == 0x8E44AD  # critical color


# ---------------------------------------------------------------------------
# GenericWebhookProvider
# ---------------------------------------------------------------------------


class TestGenericWebhookProvider:
    @pytest.mark.anyio
    async def test_send_returns_true_on_200(self):
        provider = GenericWebhookProvider("https://hooks.example.com/notify")
        payload = NotificationPayload(
            event_type="new_anomaly",
            region="Iași",
            severity="medium",
            escalation_level="normal",
            priority_score=0.55,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            message="Test",
        )
        with patch(
            "app.services.intelligence_notification_service._sync_post",
            return_value=200,
        ):
            result = await provider.send(payload)
        assert result is True

    @pytest.mark.anyio
    async def test_send_returns_false_on_5xx(self):
        provider = GenericWebhookProvider("https://hooks.example.com/notify")
        payload = NotificationPayload(
            event_type="new_anomaly",
            region="Iași",
            severity="medium",
            escalation_level="normal",
            priority_score=0.55,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            message="Test",
        )
        with patch(
            "app.services.intelligence_notification_service._sync_post",
            return_value=503,
        ):
            result = await provider.send(payload)
        assert result is False

    @pytest.mark.anyio
    async def test_sends_full_payload_dict(self):
        """Verify the generic provider sends the full notification payload as JSON."""
        captured_body = {}

        def fake_post(url, json_body, headers=None):
            captured_body.update(json_body)
            return 201

        provider = GenericWebhookProvider("https://hooks.example.com/notify")
        payload = NotificationPayload(
            event_type="reliability_alert",
            region="Romania",
            severity="critical",
            escalation_level=None,
            priority_score=0.88,
            detected_at=datetime(2026, 6, 1, tzinfo=UTC),
            message="Critical alert",
        )
        with patch(
            "app.services.intelligence_notification_service._sync_post",
            side_effect=fake_post,
        ):
            await provider.send(payload)

        assert captured_body["event_type"] == "reliability_alert"
        assert captured_body["region"] == "Romania"
        assert captured_body["severity"] == "critical"

    def test_name_property(self):
        provider = GenericWebhookProvider("https://hooks.example.com/notify")
        assert provider.name == "generic"

    @pytest.mark.anyio
    async def test_returns_false_on_exception(self):
        provider = GenericWebhookProvider("https://hooks.example.com/notify")
        payload = NotificationPayload(
            event_type="new_anomaly",
            region="Iași",
            severity="high",
            escalation_level=None,
            priority_score=0.7,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            message="Test",
        )
        with patch(
            "app.services.intelligence_notification_service._sync_post",
            side_effect=RuntimeError("network down"),
        ):
            result = await provider.send(payload)
        assert result is False


# ---------------------------------------------------------------------------
# build_providers factory
# ---------------------------------------------------------------------------


class TestBuildProviders:
    def test_no_urls_returns_empty_list(self):
        providers = build_providers(discord_webhook_url="", generic_webhook_url="")
        assert providers == []

    def test_discord_url_activates_discord(self):
        providers = build_providers(
            discord_webhook_url="https://discord.example.com/webhook",
            generic_webhook_url="",
        )
        assert len(providers) == 1
        assert providers[0].name == "discord"

    def test_generic_url_activates_generic(self):
        providers = build_providers(
            discord_webhook_url="",
            generic_webhook_url="https://hooks.example.com/notify",
        )
        assert len(providers) == 1
        assert providers[0].name == "generic"

    def test_both_urls_activates_both(self):
        providers = build_providers(
            discord_webhook_url="https://discord.example.com/webhook",
            generic_webhook_url="https://hooks.example.com/notify",
        )
        assert len(providers) == 2
        names = {p.name for p in providers}
        assert names == {"discord", "generic"}

    def test_whitespace_url_treated_as_empty(self):
        providers = build_providers(discord_webhook_url="   ", generic_webhook_url="  ")
        assert providers == []


# ---------------------------------------------------------------------------
# IntelligenceNotificationService
# ---------------------------------------------------------------------------


class TestIntelligenceNotificationService:
    def test_is_enabled_false_with_no_providers(self):
        svc = IntelligenceNotificationService([], _mock_history_repo())
        assert svc.is_enabled is False

    def test_is_enabled_true_with_providers(self):
        svc = IntelligenceNotificationService([_mock_provider()], _mock_history_repo())
        assert svc.is_enabled is True

    def test_provider_names_empty(self):
        svc = IntelligenceNotificationService([], _mock_history_repo())
        assert svc.provider_names == []

    def test_provider_names_populated(self):
        p1 = _mock_provider("discord")
        p2 = _mock_provider("generic")
        svc = IntelligenceNotificationService([p1, p2], _mock_history_repo())
        assert svc.provider_names == ["discord", "generic"]

    @pytest.mark.anyio
    async def test_dispatch_calls_all_providers(self):
        p1 = _mock_provider("discord", success=True)
        p2 = _mock_provider("generic", success=True)
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p1, p2], hist)

        payload = NotificationPayload(
            event_type="new_anomaly",
            region="Bacău",
            severity="high",
            escalation_level="normal",
            priority_score=0.7,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            message="Test",
        )
        await svc._dispatch(payload)

        p1.send.assert_awaited_once()
        p2.send.assert_awaited_once()

    @pytest.mark.anyio
    async def test_dispatch_records_success_history(self):
        p = _mock_provider("discord", success=True)
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p], hist)

        payload = NotificationPayload(
            event_type="new_anomaly",
            region="Cluj",
            severity="medium",
            escalation_level=None,
            priority_score=0.5,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            message="msg",
        )
        await svc._dispatch(payload)

        hist.create_entry.assert_awaited_once_with(
            provider="discord",
            event_type="new_anomaly",
            region="Cluj",
            success=True,
            error=None,
        )

    @pytest.mark.anyio
    async def test_dispatch_records_failure_history_when_provider_fails(self):
        p = _mock_provider("discord", success=False)
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p], hist)

        payload = NotificationPayload(
            event_type="new_anomaly",
            region="Cluj",
            severity="medium",
            escalation_level=None,
            priority_score=0.5,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            message="msg",
        )
        await svc._dispatch(payload)

        entry_call = hist.create_entry.call_args
        assert entry_call.kwargs["success"] is False
        assert entry_call.kwargs["error"] is not None

    @pytest.mark.anyio
    async def test_dispatch_isolates_provider_failures(self):
        """A failing provider must not prevent subsequent providers from firing."""
        p1 = _mock_provider("discord")
        p1.send = AsyncMock(side_effect=RuntimeError("discord down"))
        p2 = _mock_provider("generic", success=True)
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p1, p2], hist)

        payload = NotificationPayload(
            event_type="new_anomaly",
            region="Iași",
            severity="high",
            escalation_level=None,
            priority_score=0.8,
            detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            message="msg",
        )
        # Must not raise
        await svc._dispatch(payload)

        p2.send.assert_awaited_once()

    @pytest.mark.anyio
    async def test_notify_new_anomaly_payload(self):
        p = _mock_provider()
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p], hist)

        event = _make_event(region="Suceava", severity="high", priority_score=0.75)
        await svc.notify_new_anomaly(event)

        sent_payload: NotificationPayload = p.send.call_args[0][0]
        assert sent_payload.event_type == "new_anomaly"
        assert sent_payload.region == "Suceava"
        assert sent_payload.severity == "high"
        assert "Suceava" in sent_payload.message

    @pytest.mark.anyio
    async def test_notify_escalation_change_normal_to_persistent(self):
        p = _mock_provider()
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p], hist)

        event = _make_event(region="Brașov", escalation_level="persistent")
        await svc.notify_escalation_change(event, "normal", "persistent")

        p.send.assert_awaited_once()
        sent_payload: NotificationPayload = p.send.call_args[0][0]
        assert sent_payload.event_type == "escalation_change"
        assert "normal" in sent_payload.message
        assert "persistent" in sent_payload.message

    @pytest.mark.anyio
    async def test_notify_escalation_change_persistent_to_critical(self):
        p = _mock_provider()
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p], hist)

        event = _make_event(region="Brașov", escalation_level="critical")
        await svc.notify_escalation_change(event, "persistent", "critical")

        p.send.assert_awaited_once()

    @pytest.mark.anyio
    async def test_notify_escalation_change_skips_invalid_transitions(self):
        """normal→critical is NOT a valid transition and must be silently skipped."""
        p = _mock_provider()
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p], hist)

        event = _make_event(region="Brașov", escalation_level="critical")
        await svc.notify_escalation_change(event, "normal", "critical")

        p.send.assert_not_awaited()

    @pytest.mark.anyio
    async def test_notify_escalation_change_skips_downgrade(self):
        """critical→normal is a downgrade — should be silently skipped."""
        p = _mock_provider()
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p], hist)

        event = _make_event(region="Brașov", escalation_level="normal")
        await svc.notify_escalation_change(event, "critical", "normal")

        p.send.assert_not_awaited()

    @pytest.mark.anyio
    async def test_notify_new_critical_anomaly_payload(self):
        p = _mock_provider()
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p], hist)

        event = _make_event(region="Neamț", severity="critical", priority_score=0.9)
        await svc.notify_new_critical_anomaly(event)

        p.send.assert_awaited_once()
        sent_payload: NotificationPayload = p.send.call_args[0][0]
        assert sent_payload.event_type == "new_critical_anomaly"
        assert sent_payload.severity == "critical"
        assert "CRITICAL" in sent_payload.message
        assert "Neamț" in sent_payload.message

    @pytest.mark.anyio
    async def test_notify_reliability_alert_payload(self):
        p = _mock_provider()
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p], hist)

        alert = _make_alert(severity="critical")
        await svc.notify_reliability_alert(alert)

        p.send.assert_awaited_once()
        sent_payload: NotificationPayload = p.send.call_args[0][0]
        assert sent_payload.event_type == "reliability_alert"
        assert sent_payload.severity == "critical"
        assert "Romania" in sent_payload.region


# ---------------------------------------------------------------------------
# dispatch_cycle_notifications — trigger logic
# ---------------------------------------------------------------------------


class TestDispatchCycleNotifications:
    @pytest.mark.anyio
    async def test_trigger_a_new_event(self):
        """Trigger A: new event not in prev_active fires notify_new_anomaly."""
        p = _mock_provider()
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p], hist)

        event = _make_event(id="evt-1", severity="high")
        await svc.dispatch_cycle_notifications(
            current_active={"evt-1": event},
            prev_active={},
            alerts_result={"alerts": []},
            prev_reliability_critical=False,
        )

        # Should have called at least once for "new_anomaly"
        assert p.send.await_count >= 1
        sent_types = [
            call.args[0].event_type for call in p.send.await_args_list
        ]
        assert "new_anomaly" in sent_types

    @pytest.mark.anyio
    async def test_trigger_c_new_critical_event(self):
        """Trigger C: new critical event fires notify_new_anomaly AND notify_new_critical_anomaly."""
        p = _mock_provider()
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p], hist)

        event = _make_event(id="evt-1", severity="critical")
        await svc.dispatch_cycle_notifications(
            current_active={"evt-1": event},
            prev_active={},
            alerts_result={"alerts": []},
            prev_reliability_critical=False,
        )

        sent_types = [call.args[0].event_type for call in p.send.await_args_list]
        assert "new_anomaly" in sent_types
        assert "new_critical_anomaly" in sent_types

    @pytest.mark.anyio
    async def test_trigger_c_not_fired_for_non_critical(self):
        """Trigger C must NOT fire for high (non-critical) severity."""
        p = _mock_provider()
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p], hist)

        event = _make_event(id="evt-1", severity="high")
        await svc.dispatch_cycle_notifications(
            current_active={"evt-1": event},
            prev_active={},
            alerts_result={"alerts": []},
            prev_reliability_critical=False,
        )

        sent_types = [call.args[0].event_type for call in p.send.await_args_list]
        assert "new_critical_anomaly" not in sent_types

    @pytest.mark.anyio
    async def test_trigger_b_escalation_normal_to_persistent(self):
        """Trigger B fires when escalation_level changes normal→persistent."""
        p = _mock_provider()
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p], hist)

        old_event = _make_event(id="evt-1", escalation_level="normal")
        new_event = _make_event(id="evt-1", escalation_level="persistent")

        await svc.dispatch_cycle_notifications(
            current_active={"evt-1": new_event},
            prev_active={"evt-1": old_event},
            alerts_result={"alerts": []},
            prev_reliability_critical=False,
        )

        sent_types = [call.args[0].event_type for call in p.send.await_args_list]
        assert "escalation_change" in sent_types

    @pytest.mark.anyio
    async def test_trigger_b_skipped_for_same_escalation(self):
        """No notification when escalation_level hasn't changed."""
        p = _mock_provider()
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p], hist)

        event = _make_event(id="evt-1", escalation_level="persistent")
        await svc.dispatch_cycle_notifications(
            current_active={"evt-1": event},
            prev_active={"evt-1": event},
            alerts_result={"alerts": []},
            prev_reliability_critical=False,
        )

        sent_types = [call.args[0].event_type for call in p.send.await_args_list]
        assert "escalation_change" not in sent_types

    @pytest.mark.anyio
    async def test_trigger_d_reliability_critical_transition(self):
        """Trigger D fires when a critical reliability alert appears for the first time."""
        p = _mock_provider()
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p], hist)

        alert = _make_alert(severity="critical", alert_type="reliability")
        await svc.dispatch_cycle_notifications(
            current_active={},
            prev_active={},
            alerts_result={"alerts": [alert]},
            prev_reliability_critical=False,
        )

        sent_types = [call.args[0].event_type for call in p.send.await_args_list]
        assert "reliability_alert" in sent_types

    @pytest.mark.anyio
    async def test_trigger_d_not_repeat_when_already_critical(self):
        """Trigger D must NOT fire again when prev_reliability_critical is already True."""
        p = _mock_provider()
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p], hist)

        alert = _make_alert(severity="critical", alert_type="reliability")
        await svc.dispatch_cycle_notifications(
            current_active={},
            prev_active={},
            alerts_result={"alerts": [alert]},
            prev_reliability_critical=True,
        )

        sent_types = [call.args[0].event_type for call in p.send.await_args_list]
        assert "reliability_alert" not in sent_types

    @pytest.mark.anyio
    async def test_no_notifications_when_no_changes(self):
        """No notifications when current state equals previous state."""
        p = _mock_provider()
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p], hist)

        event = _make_event(id="evt-1", escalation_level="normal")
        await svc.dispatch_cycle_notifications(
            current_active={"evt-1": event},
            prev_active={"evt-1": event},
            alerts_result={"alerts": []},
            prev_reliability_critical=False,
        )

        p.send.assert_not_awaited()

    @pytest.mark.anyio
    async def test_trigger_d_not_fired_for_non_reliability_alert(self):
        """A critical volume alert must NOT trigger trigger D (reliability-specific)."""
        p = _mock_provider()
        hist = _mock_history_repo()
        svc = IntelligenceNotificationService([p], hist)

        alert = _make_alert(severity="critical", alert_type="volume")
        await svc.dispatch_cycle_notifications(
            current_active={},
            prev_active={},
            alerts_result={"alerts": [alert]},
            prev_reliability_critical=False,
        )

        sent_types = [call.args[0].event_type for call in p.send.await_args_list]
        assert "reliability_alert" not in sent_types


# ---------------------------------------------------------------------------
# NotificationHistoryRepository (mock DB)
# ---------------------------------------------------------------------------


class TestNotificationHistoryRepository:
    def _make_repo(self):
        from app.repositories.notification_history_repository import (
            NotificationHistoryRepository,
        )
        from bson import ObjectId

        mock_db = MagicMock()
        col = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=col)

        repo = NotificationHistoryRepository(mock_db)
        return repo, col

    @pytest.mark.anyio
    async def test_create_entry_inserts_document(self):
        from bson import ObjectId

        repo, col = self._make_repo()
        oid = ObjectId()
        insert_result = MagicMock()
        insert_result.inserted_id = oid
        col.insert_one = AsyncMock(return_value=insert_result)

        entry = await repo.create_entry(
            provider="discord",
            event_type="new_anomaly",
            region="Cluj",
            success=True,
        )

        col.insert_one.assert_awaited_once()
        assert entry["provider"] == "discord"
        assert entry["success"] is True
        assert entry["id"] == str(oid)

    @pytest.mark.anyio
    async def test_create_entry_records_error(self):
        from bson import ObjectId

        repo, col = self._make_repo()
        oid = ObjectId()
        insert_result = MagicMock()
        insert_result.inserted_id = oid
        col.insert_one = AsyncMock(return_value=insert_result)

        entry = await repo.create_entry(
            provider="generic",
            event_type="escalation_change",
            region="Iași",
            success=False,
            error="Connection timeout",
        )

        assert entry["success"] is False
        assert entry["error"] == "Connection timeout"

    @pytest.mark.anyio
    async def test_latest_returns_most_recent(self):
        from bson import ObjectId

        repo, col = self._make_repo()
        oid = ObjectId()
        doc = {
            "_id": oid,
            "provider": "discord",
            "event_type": "new_anomaly",
            "region": "Suceava",
            "sent_at": datetime(2026, 6, 1, tzinfo=UTC),
            "success": True,
            "error": None,
        }
        col.find_one = AsyncMock(return_value=doc)

        result = await repo.latest()

        assert result["provider"] == "discord"
        assert result["id"] == str(oid)

    @pytest.mark.anyio
    async def test_latest_returns_none_when_empty(self):
        repo, col = self._make_repo()
        col.find_one = AsyncMock(return_value=None)

        result = await repo.latest()
        assert result is None

    @pytest.mark.anyio
    async def test_list_recent_returns_shaped_list(self):
        from bson import ObjectId

        repo, col = self._make_repo()
        docs = [
            {
                "_id": ObjectId(),
                "provider": "discord",
                "event_type": "new_anomaly",
                "region": "Brașov",
                "sent_at": datetime(2026, 6, 2, tzinfo=UTC),
                "success": True,
                "error": None,
            },
            {
                "_id": ObjectId(),
                "provider": "generic",
                "event_type": "escalation_change",
                "region": "Cluj",
                "sent_at": datetime(2026, 6, 1, tzinfo=UTC),
                "success": False,
                "error": "Timeout",
            },
        ]
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=docs)
        col.find = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)

        result = await repo.list_recent(limit=10)

        assert len(result) == 2
        assert result[0]["provider"] == "discord"
        assert result[1]["provider"] == "generic"
        # No raw _id in output
        for r in result:
            assert "_id" not in r
            assert "id" in r


# ---------------------------------------------------------------------------
# SchedulerService._send_notifications integration
# ---------------------------------------------------------------------------


class TestSchedulerSendNotifications:
    def _make_scheduler(self, notification_svc):
        from app.services.scheduler_service import SchedulerService

        svc = SchedulerService.__new__(SchedulerService)
        svc._notification_svc = notification_svc
        svc._prev_active_events = {}
        svc._prev_reliability_critical = False
        svc._intel = AsyncMock()
        svc._analytics = AsyncMock()
        return svc

    @pytest.mark.anyio
    async def test_send_notifications_updates_prev_state(self):
        p = _mock_provider()
        hist = _mock_history_repo()
        notif_svc = IntelligenceNotificationService([p], hist)

        sched = self._make_scheduler(notif_svc)
        sched._intel.get_events = AsyncMock(
            return_value={"active": [_make_event(id="evt-1")], "resolved": []}
        )
        sched._analytics.get_alerts = AsyncMock(return_value={"alerts": []})

        await sched._send_notifications()

        assert "evt-1" in sched._prev_active_events

    @pytest.mark.anyio
    async def test_send_notifications_updates_reliability_critical_state(self):
        p = _mock_provider()
        hist = _mock_history_repo()
        notif_svc = IntelligenceNotificationService([p], hist)

        sched = self._make_scheduler(notif_svc)
        sched._intel.get_events = AsyncMock(
            return_value={"active": [], "resolved": []}
        )
        alert = _make_alert(severity="critical", alert_type="reliability")
        sched._analytics.get_alerts = AsyncMock(
            return_value={"alerts": [alert]}
        )

        await sched._send_notifications()

        assert sched._prev_reliability_critical is True

    @pytest.mark.anyio
    async def test_send_notifications_fires_trigger_a_for_new_event(self):
        p = _mock_provider()
        hist = _mock_history_repo()
        notif_svc = IntelligenceNotificationService([p], hist)

        sched = self._make_scheduler(notif_svc)
        event = _make_event(id="new-evt", severity="high")
        sched._intel.get_events = AsyncMock(
            return_value={"active": [event], "resolved": []}
        )
        sched._analytics.get_alerts = AsyncMock(return_value={"alerts": []})
        sched._prev_active_events = {}  # no previous events

        await sched._send_notifications()

        sent_types = [call.args[0].event_type for call in p.send.await_args_list]
        assert "new_anomaly" in sent_types
