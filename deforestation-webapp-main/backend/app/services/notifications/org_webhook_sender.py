"""Organization-scoped HTTP webhook delivery."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass

import requests

logger = logging.getLogger("forestwatch.customer_alerts.webhook")

WEBHOOK_TIMEOUT_SECONDS = 10
MAX_PAYLOAD_BYTES = 32_768


@dataclass(frozen=True)
class WebhookSendResult:
    success: bool
    status_code: int | None = None
    error: str | None = None


def _sign_payload(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class OrgWebhookSender:
    """Single-attempt bounded webhook dispatch."""

    async def send(
        self,
        *,
        url: str,
        payload: dict,
        secret_token: str = "",
    ) -> WebhookSendResult:
        if not url:
            return WebhookSendResult(success=False, error="missing_url")
        body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        if len(body) > MAX_PAYLOAD_BYTES:
            return WebhookSendResult(success=False, error="payload_too_large")
        headers = {"Content-Type": "application/json", "User-Agent": "ForestWatch-Alerts/1.0"}
        if secret_token:
            headers["X-ForestWatch-Signature"] = _sign_payload(body, secret_token)
        try:
            response = requests.post(url, data=body, headers=headers, timeout=WEBHOOK_TIMEOUT_SECONDS)
            if 200 <= response.status_code < 300:
                return WebhookSendResult(success=True, status_code=response.status_code)
            return WebhookSendResult(
                success=False,
                status_code=response.status_code,
                error=f"http_{response.status_code}",
            )
        except requests.Timeout:
            return WebhookSendResult(success=False, error="timeout")
        except requests.RequestException as exc:
            logger.warning("Webhook delivery failed: %s", type(exc).__name__)
            return WebhookSendResult(success=False, error=type(exc).__name__)
