"""Alert policy / notification channel configuration: CRUD, roles, secrets, isolation."""
from __future__ import annotations

import pytest

from app.core.commercial.alert_semantics import (
    MAX_COOLDOWN_MINUTES,
    channel_type_label,
    delivery_state_label,
    suppression_reason_label,
)
from app.core.commercial.secret_storage import (
    decrypt_secret,
    encrypt_secret,
    redact_channel_config,
)
from app.core.errors import ForbiddenError, NotFoundError
from app.models.customer_alert import (
    AlertPolicyCreate,
    AlertPolicyUpdate,
    NotificationChannelCreate,
    NotificationChannelUpdate,
)
from app.services.alert_policy_service import AlertConfigurationError
from fixtures.customer_alert_fakes import (
    APP_SECRET,
    build_alert_environment,
    run_async,
)


@pytest.fixture
def env():
    return build_alert_environment()


@pytest.fixture
def two_orgs():
    return build_alert_environment(
        organizations=(("org-a", "Northern Forestry"), ("org-b", "Carpathian Trust"))
    )


def _email_channel(name: str = "Operations inbox") -> NotificationChannelCreate:
    return NotificationChannelCreate(
        channel_type="email",
        name=name,
        config={"recipients": ["ops@example.com"]},
    )


def _webhook_channel(name: str = "Field webhook", secret: str = "hook-secret"):
    return NotificationChannelCreate(
        channel_type="webhook",
        name=name,
        config={"url": "https://example.com/hook", "secret_token": secret},
    )


class TestPolicyCrud:
    @run_async
    async def test_create_policy_returns_active_policy(self, env):
        policy = await env.policy_svc.create_policy(
            "org-a",
            AlertPolicyCreate(name="Monitored disturbance"),
            actor_role="owner",
        )
        assert policy.name == "Monitored disturbance"
        assert policy.enabled is True
        assert policy.organization_id == "org-a"

    @run_async
    async def test_list_policies_reports_management_capability(self, env):
        await env.policy_svc.create_policy(
            "org-a", AlertPolicyCreate(name="One"), actor_role="admin"
        )
        payload = await env.policy_svc.list_policies("org-a", actor_role="admin")
        assert payload["total"] == 1
        assert payload["can_manage"] is True
        assert payload["alert_delivery_available"] is True

    @run_async
    async def test_list_policies_is_read_only_for_members(self, env):
        await env.policy_svc.create_policy(
            "org-a", AlertPolicyCreate(name="One"), actor_role="owner"
        )
        payload = await env.policy_svc.list_policies("org-a", actor_role="member")
        assert payload["can_manage"] is False
        assert payload["total"] == 1

    @run_async
    async def test_get_policy_by_id(self, env):
        created = await env.policy_svc.create_policy(
            "org-a", AlertPolicyCreate(name="One"), actor_role="owner"
        )
        fetched = await env.policy_svc.get_policy("org-a", created.id)
        assert fetched.id == created.id

    @run_async
    async def test_get_unknown_policy_raises_not_found(self, env):
        with pytest.raises(NotFoundError):
            await env.policy_svc.get_policy("org-a", "does-not-exist")

    @run_async
    async def test_update_policy_changes_thresholds(self, env):
        created = await env.policy_svc.create_policy(
            "org-a", AlertPolicyCreate(name="One"), actor_role="owner"
        )
        updated = await env.policy_svc.update_policy(
            "org-a",
            created.id,
            AlertPolicyUpdate(minimum_investigation_priority="critical", cooldown_minutes=120),
            actor_role="owner",
        )
        assert updated.minimum_investigation_priority == "critical"
        assert updated.cooldown_minutes == 120

    @run_async
    async def test_disable_and_enable_policy(self, env):
        created = await env.policy_svc.create_policy(
            "org-a", AlertPolicyCreate(name="One"), actor_role="owner"
        )
        disabled = await env.policy_svc.set_policy_enabled(
            "org-a", created.id, enabled=False, actor_role="owner"
        )
        assert disabled.enabled is False
        enabled = await env.policy_svc.set_policy_enabled(
            "org-a", created.id, enabled=True, actor_role="owner"
        )
        assert enabled.enabled is True

    @run_async
    async def test_delete_policy_removes_it(self, env):
        created = await env.policy_svc.create_policy(
            "org-a", AlertPolicyCreate(name="One"), actor_role="owner"
        )
        await env.policy_svc.delete_policy("org-a", created.id, actor_role="owner")
        payload = await env.policy_svc.list_policies("org-a", actor_role="owner")
        assert payload["total"] == 0

    @run_async
    async def test_update_preserves_untouched_fields(self, env):
        created = await env.policy_svc.create_policy(
            "org-a",
            AlertPolicyCreate(name="One", minimum_severity="high", cooldown_minutes=45),
            actor_role="owner",
        )
        updated = await env.policy_svc.update_policy(
            "org-a", created.id, AlertPolicyUpdate(name="Renamed"), actor_role="owner"
        )
        assert updated.name == "Renamed"
        assert updated.minimum_severity == "high"
        assert updated.cooldown_minutes == 45

    @run_async
    async def test_clearing_evidence_threshold_stores_none(self, env):
        created = await env.policy_svc.create_policy(
            "org-a",
            AlertPolicyCreate(name="One", minimum_evidence_state="multi_source"),
            actor_role="owner",
        )
        updated = await env.policy_svc.update_policy(
            "org-a", created.id, AlertPolicyUpdate(minimum_evidence_state=""), actor_role="owner"
        )
        assert updated.minimum_evidence_state is None


class TestPolicyRolePermissions:
    @run_async
    async def test_member_cannot_create_policy(self, env):
        with pytest.raises(ForbiddenError):
            await env.policy_svc.create_policy(
                "org-a", AlertPolicyCreate(name="Nope"), actor_role="member"
            )

    @run_async
    async def test_member_cannot_update_policy(self, env):
        created = await env.policy_svc.create_policy(
            "org-a", AlertPolicyCreate(name="One"), actor_role="owner"
        )
        with pytest.raises(ForbiddenError):
            await env.policy_svc.update_policy(
                "org-a", created.id, AlertPolicyUpdate(name="Hacked"), actor_role="member"
            )

    @run_async
    async def test_member_cannot_delete_policy(self, env):
        created = await env.policy_svc.create_policy(
            "org-a", AlertPolicyCreate(name="One"), actor_role="owner"
        )
        with pytest.raises(ForbiddenError):
            await env.policy_svc.delete_policy("org-a", created.id, actor_role="member")

    @run_async
    async def test_unknown_role_cannot_manage(self, env):
        with pytest.raises(ForbiddenError):
            await env.policy_svc.create_policy(
                "org-a", AlertPolicyCreate(name="One"), actor_role=""
            )

    @run_async
    async def test_admin_can_manage(self, env):
        policy = await env.policy_svc.create_policy(
            "org-a", AlertPolicyCreate(name="One"), actor_role="admin"
        )
        assert policy.id


class TestPolicyValidation:
    @run_async
    async def test_blank_name_is_rejected(self, env):
        with pytest.raises(AlertConfigurationError):
            await env.policy_svc.create_policy(
                "org-a", AlertPolicyCreate(name="   "), actor_role="owner"
            )

    @run_async
    async def test_unsupported_category_is_rejected(self, env):
        with pytest.raises(AlertConfigurationError):
            await env.policy_svc.create_policy(
                "org-a",
                AlertPolicyCreate(name="One", incident_categories=["teleportation"]),
                actor_role="owner",
            )

    @run_async
    async def test_empty_category_list_is_rejected(self, env):
        with pytest.raises(AlertConfigurationError):
            await env.policy_svc.create_policy(
                "org-a",
                AlertPolicyCreate(name="One", incident_categories=[]),
                actor_role="owner",
            )

    @run_async
    async def test_unsupported_priority_is_rejected(self, env):
        with pytest.raises(AlertConfigurationError):
            await env.policy_svc.create_policy(
                "org-a",
                AlertPolicyCreate(name="One", minimum_investigation_priority="apocalyptic"),
                actor_role="owner",
            )

    @run_async
    async def test_unsupported_evidence_threshold_is_rejected(self, env):
        with pytest.raises(AlertConfigurationError):
            await env.policy_svc.create_policy(
                "org-a",
                AlertPolicyCreate(name="One", minimum_evidence_state="telepathy"),
                actor_role="owner",
            )

    @run_async
    async def test_negative_cooldown_is_rejected(self, env):
        with pytest.raises(AlertConfigurationError):
            await env.policy_svc.create_policy(
                "org-a", AlertPolicyCreate(name="One", cooldown_minutes=-1), actor_role="owner"
            )

    @run_async
    async def test_excessive_cooldown_is_rejected(self, env):
        with pytest.raises(AlertConfigurationError):
            await env.policy_svc.create_policy(
                "org-a",
                AlertPolicyCreate(name="One", cooldown_minutes=MAX_COOLDOWN_MINUTES + 1),
                actor_role="owner",
            )

    @run_async
    async def test_policy_cannot_reference_another_organizations_area(self, two_orgs):
        with pytest.raises(AlertConfigurationError):
            await two_orgs.policy_svc.create_policy(
                "org-a",
                AlertPolicyCreate(
                    name="Cross tenant",
                    monitored_area_ids=[two_orgs.area_ids["org-b"]],
                ),
                actor_role="owner",
            )

    @run_async
    async def test_policy_cannot_reference_another_organizations_channel(self, two_orgs):
        foreign = await two_orgs.policy_svc.create_channel(
            "org-b", _email_channel("Other org"), actor_role="owner"
        )
        with pytest.raises(AlertConfigurationError):
            await two_orgs.policy_svc.create_policy(
                "org-a",
                AlertPolicyCreate(name="Cross tenant", notification_channel_ids=[foreign.id]),
                actor_role="owner",
            )

    @run_async
    async def test_policy_accepts_own_area_and_channel(self, env):
        channel = await env.policy_svc.create_channel(
            "org-a", _email_channel(), actor_role="owner"
        )
        policy = await env.policy_svc.create_policy(
            "org-a",
            AlertPolicyCreate(
                name="Valid",
                monitored_area_ids=[env.area_ids["org-a"]],
                notification_channel_ids=[channel.id],
            ),
            actor_role="owner",
        )
        assert policy.notification_channel_ids == [channel.id]

    @run_async
    async def test_policy_requires_alert_delivery_entitlement(self, env):
        env.store.set_alert_entitlement("org-a", False)
        with pytest.raises(ForbiddenError):
            await env.policy_svc.create_policy(
                "org-a", AlertPolicyCreate(name="One"), actor_role="owner"
            )

    @run_async
    async def test_list_reports_alert_delivery_unavailable(self, env):
        env.store.set_alert_entitlement("org-a", False)
        payload = await env.policy_svc.list_policies("org-a", actor_role="owner")
        assert payload["alert_delivery_available"] is False


class TestChannelCrud:
    @run_async
    async def test_create_email_channel_normalizes_recipients(self, env):
        channel = await env.policy_svc.create_channel(
            "org-a",
            NotificationChannelCreate(
                channel_type="email",
                name="Ops",
                config={"recipients": [" ops@example.com ", ""]},
            ),
            actor_role="owner",
        )
        assert channel.config["recipients"] == ["ops@example.com"]

    @run_async
    async def test_create_webhook_channel_stores_url(self, env):
        channel = await env.policy_svc.create_channel(
            "org-a", _webhook_channel(), actor_role="owner"
        )
        assert channel.config["url"] == "https://example.com/hook"

    @run_async
    async def test_list_channels_reports_capability(self, env):
        await env.policy_svc.create_channel("org-a", _email_channel(), actor_role="owner")
        payload = await env.policy_svc.list_channels("org-a", actor_role="member")
        assert payload["total"] == 1
        assert payload["can_manage"] is False

    @run_async
    async def test_update_channel_name(self, env):
        channel = await env.policy_svc.create_channel(
            "org-a", _email_channel(), actor_role="owner"
        )
        updated = await env.policy_svc.update_channel(
            "org-a", channel.id, NotificationChannelUpdate(name="Renamed"), actor_role="owner"
        )
        assert updated.name == "Renamed"

    @run_async
    async def test_disable_and_enable_channel(self, env):
        channel = await env.policy_svc.create_channel(
            "org-a", _email_channel(), actor_role="owner"
        )
        disabled = await env.policy_svc.set_channel_enabled(
            "org-a", channel.id, enabled=False, actor_role="owner"
        )
        assert disabled.enabled is False
        enabled = await env.policy_svc.set_channel_enabled(
            "org-a", channel.id, enabled=True, actor_role="owner"
        )
        assert enabled.enabled is True

    @run_async
    async def test_delete_channel(self, env):
        channel = await env.policy_svc.create_channel(
            "org-a", _email_channel(), actor_role="owner"
        )
        await env.policy_svc.delete_channel("org-a", channel.id, actor_role="owner")
        payload = await env.policy_svc.list_channels("org-a", actor_role="owner")
        assert payload["total"] == 0

    @run_async
    async def test_member_cannot_create_channel(self, env):
        with pytest.raises(ForbiddenError):
            await env.policy_svc.create_channel("org-a", _email_channel(), actor_role="member")

    @run_async
    async def test_member_cannot_delete_channel(self, env):
        channel = await env.policy_svc.create_channel(
            "org-a", _email_channel(), actor_role="owner"
        )
        with pytest.raises(ForbiddenError):
            await env.policy_svc.delete_channel("org-a", channel.id, actor_role="member")

    @run_async
    async def test_channel_requires_entitlement(self, env):
        env.store.set_alert_entitlement("org-a", False)
        with pytest.raises(ForbiddenError):
            await env.policy_svc.create_channel("org-a", _email_channel(), actor_role="owner")


class TestChannelValidation:
    @run_async
    async def test_email_channel_requires_recipient(self, env):
        with pytest.raises(AlertConfigurationError):
            await env.policy_svc.create_channel(
                "org-a",
                NotificationChannelCreate(channel_type="email", name="Ops", config={}),
                actor_role="owner",
            )

    @run_async
    async def test_email_channel_rejects_invalid_address(self, env):
        with pytest.raises(AlertConfigurationError):
            await env.policy_svc.create_channel(
                "org-a",
                NotificationChannelCreate(
                    channel_type="email",
                    name="Ops",
                    config={"recipients": ["not-an-email"]},
                ),
                actor_role="owner",
            )

    @run_async
    async def test_webhook_channel_requires_url(self, env):
        with pytest.raises(AlertConfigurationError):
            await env.policy_svc.create_channel(
                "org-a",
                NotificationChannelCreate(channel_type="webhook", name="Hook", config={}),
                actor_role="owner",
            )

    @run_async
    async def test_webhook_channel_requires_https(self, env):
        with pytest.raises(AlertConfigurationError):
            await env.policy_svc.create_channel(
                "org-a",
                NotificationChannelCreate(
                    channel_type="webhook",
                    name="Hook",
                    config={"url": "http://insecure.example.com/hook"},
                ),
                actor_role="owner",
            )

    @run_async
    async def test_unknown_channel_raises_not_found(self, env):
        with pytest.raises(NotFoundError):
            await env.policy_svc.update_channel(
                "org-a", "nope", NotificationChannelUpdate(name="x"), actor_role="owner"
            )


class TestSecretHandling:
    @run_async
    async def test_created_webhook_never_returns_the_secret(self, env):
        channel = await env.policy_svc.create_channel(
            "org-a", _webhook_channel(secret="plain-secret"), actor_role="owner"
        )
        serialized = channel.model_dump_json()
        assert "plain-secret" not in serialized
        assert "secret_token" not in channel.config
        assert "secret_token_encrypted" not in channel.config

    @run_async
    async def test_created_webhook_reports_secret_configured(self, env):
        channel = await env.policy_svc.create_channel(
            "org-a", _webhook_channel(), actor_role="owner"
        )
        assert channel.config["secret_configured"] is True

    @run_async
    async def test_webhook_without_secret_reports_not_configured(self, env):
        channel = await env.policy_svc.create_channel(
            "org-a",
            NotificationChannelCreate(
                channel_type="webhook",
                name="Hook",
                config={"url": "https://example.com/hook"},
            ),
            actor_role="owner",
        )
        assert channel.config["secret_configured"] is False

    @run_async
    async def test_secret_is_encrypted_at_rest(self, env):
        channel = await env.policy_svc.create_channel(
            "org-a", _webhook_channel(secret="plain-secret"), actor_role="owner"
        )
        stored = env.store.channels[channel.id]["config"]["secret_token_encrypted"]
        assert stored != "plain-secret"
        assert decrypt_secret(stored, app_secret=APP_SECRET) == "plain-secret"

    @run_async
    async def test_update_without_secret_preserves_stored_secret(self, env):
        channel = await env.policy_svc.create_channel(
            "org-a", _webhook_channel(secret="original"), actor_role="owner"
        )
        await env.policy_svc.update_channel(
            "org-a",
            channel.id,
            NotificationChannelUpdate(config={"url": "https://example.com/other"}),
            actor_role="owner",
        )
        stored = env.store.channels[channel.id]["config"]["secret_token_encrypted"]
        assert decrypt_secret(stored, app_secret=APP_SECRET) == "original"

    @run_async
    async def test_update_with_new_secret_replaces_it(self, env):
        channel = await env.policy_svc.create_channel(
            "org-a", _webhook_channel(secret="original"), actor_role="owner"
        )
        await env.policy_svc.update_channel(
            "org-a",
            channel.id,
            NotificationChannelUpdate(
                config={"url": "https://example.com/hook", "secret_token": "rotated"}
            ),
            actor_role="owner",
        )
        stored = env.store.channels[channel.id]["config"]["secret_token_encrypted"]
        assert decrypt_secret(stored, app_secret=APP_SECRET) == "rotated"

    @run_async
    async def test_listing_channels_never_exposes_ciphertext(self, env):
        await env.policy_svc.create_channel(
            "org-a", _webhook_channel(secret="plain-secret"), actor_role="owner"
        )
        payload = await env.policy_svc.list_channels("org-a", actor_role="owner")
        serialized = payload["items"][0].model_dump_json()
        assert "plain-secret" not in serialized
        assert "secret_token_encrypted" not in serialized

    def test_redaction_removes_secret_keys(self):
        safe = redact_channel_config(
            "webhook",
            {"url": "https://x", "secret_token_encrypted": "cipher", "secret_token": "plain"},
        )
        assert safe == {"url": "https://x", "secret_configured": True}

    def test_redaction_strips_email_passwords(self):
        safe = redact_channel_config(
            "email", {"recipients": ["a@b.c"], "smtp_password": "hunter2"}
        )
        assert safe == {"recipients": ["a@b.c"]}

    def test_encryption_roundtrip(self):
        cipher = encrypt_secret("value", app_secret="key")
        assert cipher != "value"
        assert decrypt_secret(cipher, app_secret="key") == "value"

    def test_decryption_with_wrong_key_returns_empty(self):
        cipher = encrypt_secret("value", app_secret="key")
        assert decrypt_secret(cipher, app_secret="other-key") == ""


class TestConfigurationIsolation:
    @run_async
    async def test_policies_are_not_visible_across_organizations(self, two_orgs):
        await two_orgs.policy_svc.create_policy(
            "org-a", AlertPolicyCreate(name="Org A policy"), actor_role="owner"
        )
        payload = await two_orgs.policy_svc.list_policies("org-b", actor_role="owner")
        assert payload["total"] == 0

    @run_async
    async def test_channels_are_not_visible_across_organizations(self, two_orgs):
        await two_orgs.policy_svc.create_channel(
            "org-a", _email_channel("Org A inbox"), actor_role="owner"
        )
        payload = await two_orgs.policy_svc.list_channels("org-b", actor_role="owner")
        assert payload["total"] == 0

    @run_async
    async def test_cannot_read_another_organizations_policy(self, two_orgs):
        created = await two_orgs.policy_svc.create_policy(
            "org-a", AlertPolicyCreate(name="Org A policy"), actor_role="owner"
        )
        with pytest.raises(NotFoundError):
            await two_orgs.policy_svc.get_policy("org-b", created.id)

    @run_async
    async def test_cannot_update_another_organizations_policy(self, two_orgs):
        created = await two_orgs.policy_svc.create_policy(
            "org-a", AlertPolicyCreate(name="Org A policy"), actor_role="owner"
        )
        with pytest.raises(NotFoundError):
            await two_orgs.policy_svc.update_policy(
                "org-b", created.id, AlertPolicyUpdate(name="Hijack"), actor_role="owner"
            )

    @run_async
    async def test_cannot_delete_another_organizations_policy(self, two_orgs):
        created = await two_orgs.policy_svc.create_policy(
            "org-a", AlertPolicyCreate(name="Org A policy"), actor_role="owner"
        )
        with pytest.raises(NotFoundError):
            await two_orgs.policy_svc.delete_policy("org-b", created.id, actor_role="owner")

    @run_async
    async def test_cannot_delete_another_organizations_channel(self, two_orgs):
        created = await two_orgs.policy_svc.create_channel(
            "org-a", _email_channel(), actor_role="owner"
        )
        with pytest.raises(NotFoundError):
            await two_orgs.policy_svc.delete_channel("org-b", created.id, actor_role="owner")


class TestProductLanguage:
    def test_channel_labels_are_customer_facing(self):
        assert channel_type_label("email") == "Email channel"
        assert channel_type_label("webhook") == "Webhook channel"

    def test_unknown_channel_type_falls_back_to_generic_label(self):
        assert channel_type_label("carrier_pigeon") == "Notification channel"

    def test_delivery_state_labels_avoid_internal_names(self):
        assert delivery_state_label("pending") == "Queued"
        assert delivery_state_label("sent") == "Delivered"
        assert delivery_state_label("failed") == "Delivery failed"
        assert delivery_state_label("suppressed") == "Suppressed"

    def test_suppression_labels_explain_the_reason(self):
        assert "turned off" in suppression_reason_label("policy_disabled")
        assert "notification channel" in suppression_reason_label("no_channels")
        assert suppression_reason_label(None) is None

    def test_no_label_mentions_tenant_or_entitlement(self):
        from app.core.commercial.alert_semantics import (
            DELIVERY_STATE_LABELS,
            SUPPRESSION_REASON_LABELS,
        )

        text = " ".join(
            list(DELIVERY_STATE_LABELS.values()) + list(SUPPRESSION_REASON_LABELS.values())
        ).lower()
        assert "tenant" not in text
        assert "entitlement" not in text
        assert "repository" not in text
