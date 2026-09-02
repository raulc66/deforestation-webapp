"""Resolve provider execution mode from settings, health, and last run outcome."""
from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.core.ingestion.provider_health import ProviderHealthStatus


def resolve_provider_execution_mode(
    *,
    provider_id: str,
    enabled: bool,
    settings: Settings,
    health: dict[str, Any] | None,
    last_run: dict[str, Any] | None,
    describe: dict[str, Any] | None = None,
) -> str:
    """Return live | fixture | disabled | unknown from actual operational signals."""
    if not enabled:
        return "disabled"

    if health and health.get("last_execution_mode") in {"live", "fixture"}:
        return str(health["last_execution_mode"])

    if last_run:
        mode = _mode_from_run(provider_id, settings, last_run, describe or {})
        if mode != "unknown":
            return mode

    if health and health.get("last_attempt_at"):
        if health.get("current_status") == ProviderHealthStatus.FAILED.value:
            return "unknown"
        return _configured_mode_hint(provider_id, settings, describe or {})

    return _configured_mode_hint(provider_id, settings, describe or {})


def _mode_from_run(
    provider_id: str,
    settings: Settings,
    last_run: dict[str, Any],
    describe: dict[str, Any],
) -> str:
    status = str(last_run.get("status") or "")
    if status != "success":
        return "unknown"

    if provider_id == "eea.air_quality":
        token = (settings.eea_aq_api_token or "").strip()
        if not token:
            return "fixture"
        live_status = str(describe.get("live_access_status") or "")
        if live_status == "token_configured":
            return "live"
        return "fixture"

    if provider_id == "nasa.firms":
        if (settings.firms_api_key or "").strip():
            return "live"
        return "fixture"

    if provider_id == "cems.rapid_mapping":
        access = str(describe.get("live_access_status") or "")
        if access == "public_api" and settings.enable_cems_rapid_mapping:
            return "live"
        return "fixture"

    if provider_id == "effis.wildfire_context":
        if not settings.enable_effis_wildfire_context:
            return "disabled"
        if health and health.get("last_execution_mode") in {"live", "fixture"}:
            return str(health["last_execution_mode"])
        if settings.enable_effis_live:
            return "live"
        return "fixture"

    access = str(describe.get("live_access_status") or "")
    if access in {"live", "token_configured", "public_api"}:
        return "live"
    if access in {"fixture", "fixture_only"}:
        return "fixture"
    return "unknown"


def _configured_mode_hint(
    provider_id: str,
    settings: Settings,
    describe: dict[str, Any],
) -> str:
    if provider_id == "eea.air_quality":
        return "live" if (settings.eea_aq_api_token or "").strip() else "fixture"
    if provider_id == "nasa.firms":
        return "live" if (settings.firms_api_key or "").strip() else "fixture"
    if provider_id == "cems.rapid_mapping":
        return "live" if settings.enable_cems_rapid_mapping else "disabled"
    if provider_id == "effis.wildfire_context":
        if not settings.enable_effis_wildfire_context:
            return "disabled"
        return "live" if settings.enable_effis_live else "fixture"
    if provider_id == "gfw.integrated_alerts":
        if not settings.enable_forest_disturbance:
            return "disabled"
        return "live" if (settings.gfw_api_key or "").strip() else "fixture"
    access = str(describe.get("live_access_status") or "")
    if access in {"live", "token_configured", "public_api"}:
        return "live"
    if access in {"fixture", "fixture_only"}:
        return "fixture"
    return "unknown"
