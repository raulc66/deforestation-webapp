"""Encrypt sensitive notification channel configuration at rest."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def _fernet_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(plain: str, *, app_secret: str) -> str:
    if not plain:
        return ""
    token = Fernet(_fernet_key(app_secret)).encrypt(plain.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(ciphertext: str, *, app_secret: str) -> str:
    if not ciphertext:
        return ""
    try:
        return Fernet(_fernet_key(app_secret)).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""


SECRET_CONFIG_KEYS = ("secret_token", "secret_token_encrypted", "smtp_password", "password")


def redact_channel_config(channel_type: str, config: dict) -> dict:
    """Public read-model — secret material is removed, not masked.

    Secrets are write-only: the response reports *whether* a secret is stored
    via ``secret_configured`` and never returns plaintext or ciphertext.
    """
    safe = {
        key: value
        for key, value in (config or {}).items()
        if key not in SECRET_CONFIG_KEYS
    }
    if channel_type == "webhook":
        safe["secret_configured"] = bool((config or {}).get("secret_token_encrypted"))
    return safe
