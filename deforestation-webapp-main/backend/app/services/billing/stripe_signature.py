"""Stripe webhook signature verification.

Implemented directly against Stripe's documented scheme so signature checking
is deterministic and testable without the Stripe SDK or network access:

    Stripe-Signature: t=<timestamp>,v1=<hex hmac sha256>

The signed payload is ``"<timestamp>.<raw body>"`` keyed with the endpoint
signing secret. Secrets are only ever used as HMAC keys — never logged, never
returned, never persisted.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone

SIGNATURE_SCHEME = "v1"
DEFAULT_TOLERANCE_SECONDS = 300


class WebhookVerificationError(Exception):
    """Raised when a webhook payload cannot be trusted."""


def compute_signature(payload: bytes, *, timestamp: int, secret: str) -> str:
    signed_payload = b"%d.%s" % (int(timestamp), payload)
    return hmac.new(
        secret.encode("utf-8"),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()


def build_signature_header(payload: bytes, *, timestamp: int, secret: str) -> str:
    """Build a ``Stripe-Signature`` header — used by tests and local tooling."""
    signature = compute_signature(payload, timestamp=timestamp, secret=secret)
    return f"t={int(timestamp)},{SIGNATURE_SCHEME}={signature}"


def _parse_header(header: str) -> tuple[int | None, list[str]]:
    timestamp: int | None = None
    signatures: list[str] = []
    for part in str(header or "").split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError:
                timestamp = None
        elif key == SIGNATURE_SCHEME and value:
            signatures.append(value)
    return timestamp, signatures


def verify_webhook_signature(
    payload: bytes,
    signature_header: str | None,
    secret: str,
    *,
    tolerance_seconds: int = DEFAULT_TOLERANCE_SECONDS,
    now: datetime | None = None,
) -> None:
    """Validate a Stripe signature header, raising on any failure."""
    if not secret:
        raise WebhookVerificationError("Webhook signing secret is not configured")
    if not signature_header:
        raise WebhookVerificationError("Missing webhook signature")

    timestamp, signatures = _parse_header(signature_header)
    if timestamp is None or not signatures:
        raise WebhookVerificationError("Malformed webhook signature")

    expected = compute_signature(payload, timestamp=timestamp, secret=secret)
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise WebhookVerificationError("Webhook signature mismatch")

    if tolerance_seconds > 0:
        current = now or datetime.now(timezone.utc)
        age = abs(int(current.timestamp()) - timestamp)
        if age > tolerance_seconds:
            raise WebhookVerificationError("Webhook timestamp outside tolerance")
