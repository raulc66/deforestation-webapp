"""Production-safety guards must not change development, tests, or demo startup."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app.core.config import (
    enforce_production_safety,
    get_settings,
    is_production_env,
)


def test_development_is_not_production_mode():
    assert is_production_env("development") is False
    assert is_production_env("") is False
    assert is_production_env(None) is False
    assert is_production_env("production") is True
    assert is_production_env("PROD") is True


def test_development_allows_documented_defaults():
    enforce_production_safety(
        forestwatch_env="development",
        jwt_secret="change-me-to-a-long-random-secret",
        admin_password="admin123",
        cors_origins="*",
    )


def test_production_rejects_wildcard_cors():
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        enforce_production_safety(
            forestwatch_env="production",
            jwt_secret="a-unique-production-jwt-secret-value",
            admin_password="unique-admin-password",
            cors_origins="*",
        )


def test_production_rejects_known_example_jwt_secret():
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        enforce_production_safety(
            forestwatch_env="production",
            jwt_secret="change-me-to-a-long-random-secret",
            admin_password="unique-admin-password",
            cors_origins="https://app.example.com",
        )


def test_production_rejects_known_development_admin_password():
    with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
        enforce_production_safety(
            forestwatch_env="production",
            jwt_secret="a-unique-production-jwt-secret-value",
            admin_password="admin123",
            cors_origins="https://app.example.com",
        )


def test_production_accepts_explicit_operator_values():
    enforce_production_safety(
        forestwatch_env="production",
        jwt_secret="a-unique-production-jwt-secret-value",
        admin_password="unique-admin-password",
        cors_origins="https://app.example.com",
    )


def test_get_settings_production_mode_refuses_to_start():
    env = {
        "MONGO_URL": "mongodb://localhost:27017",
        "DB_NAME": "forestwatch",
        "JWT_SECRET": "change-me-to-a-long-random-secret",
        "FORESTWATCH_ENV": "production",
        "ADMIN_PASSWORD": "unique-admin-password",
        "CORS_ORIGINS": "https://app.example.com",
    }
    get_settings.cache_clear()
    try:
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(RuntimeError, match="FORESTWATCH_ENV=production"):
                get_settings()
    finally:
        get_settings.cache_clear()
