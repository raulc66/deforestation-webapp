"""HTTP client for the official EEA Air Quality Parquet Download API."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.config import Settings, get_settings

from .eea_aq_validation import (
    EEAAQAuthenticationError,
    is_valid_eea_token_format,
    sanitize_error_message,
)

EEA_AQ_API_BASE = "https://eeadmz1-downloads-api-appservice.azurewebsites.net"
EEA_AQ_PARQUET_ENDPOINT = "/ParquetFile/dynamic"
EEA_AQ_SUMMARY_ENDPOINT = "/DownloadSummary"
EEA_AQ_VERSION_ENDPOINT = "/Version"

# E2a / UTD dataset (official documentation dataset=1).
EEA_AQ_DATASET_E2A = 1

DEFAULT_POLLUTANTS: tuple[str, ...] = ("PM2.5", "PM10", "NO2", "O3", "SO2")

# Bounded incremental window — default 24h per operational requirement.
DEFAULT_QUERY_WINDOW_HOURS = 24


class EEAAQDownloadClient:
    """Async client for bounded EEA E2a/UTD parquet downloads."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._http = http_client

    async def validate_token(self, token: str) -> None:
        """Validate operator token format and service reachability."""
        cleaned = token.strip()
        if not cleaned:
            raise EEAAQAuthenticationError("EEA token is missing")
        if not is_valid_eea_token_format(cleaned):
            raise EEAAQAuthenticationError("EEA token format is invalid")

        client = await self._client()
        url = self._url(EEA_AQ_SUMMARY_ENDPOINT, token=cleaned)
        body = self.build_request_body(
            countries=["RO"],
            pollutants=["PM2.5"],
            window_hours=1,
        )
        try:
            response = await client.post(url, json=body)
        except httpx.TimeoutException as exc:
            raise EEAAQAuthenticationError("EEA token validation timed out") from exc
        except httpx.HTTPError as exc:
            raise EEAAQAuthenticationError(
                sanitize_error_message(f"EEA token validation failed: {exc}", cleaned)
            ) from exc

        if response.status_code in {401, 403}:
            raise EEAAQAuthenticationError("EEA token rejected by download service")
        if response.status_code == 429:
            raise EEAAQAuthenticationError("EEA download service rate limited")
        if response.status_code >= 500:
            raise EEAAQAuthenticationError("EEA download service unavailable")
        if response.status_code >= 400:
            raise EEAAQAuthenticationError("EEA token validation request rejected")

    async def fetch_dataset_version(self) -> str:
        client = await self._client()
        response = await client.get(self._url(EEA_AQ_VERSION_ENDPOINT))
        response.raise_for_status()
        return response.text.strip() or "e2a-live"

    async def download_parquet_zip(
        self,
        *,
        token: str,
        countries: list[str] | None = None,
        pollutants: list[str] | None = None,
        window_hours: int | None = None,
    ) -> bytes:
        """Download bounded E2a ZIP archive containing parquet files."""
        cleaned = token.strip()
        await self.validate_token(cleaned)

        client = await self._client()
        body = self.build_request_body(
            countries=countries,
            pollutants=pollutants,
            window_hours=window_hours,
        )
        url = self._url(EEA_AQ_PARQUET_ENDPOINT, token=cleaned)
        try:
            response = await client.post(url, json=body)
        except httpx.TimeoutException as exc:
            raise RuntimeError("EEA parquet download timed out") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(
                sanitize_error_message(f"EEA parquet download failed: {exc}", cleaned)
            ) from exc

        if response.status_code in {401, 403}:
            raise EEAAQAuthenticationError("EEA token rejected by download service")
        if response.status_code == 429:
            raise RuntimeError("EEA download service rate limited")
        if response.status_code >= 500:
            raise RuntimeError("EEA download service unavailable")
        if response.status_code not in {200, 206}:
            raise RuntimeError(f"EEA parquet download failed with status {response.status_code}")

        content = response.content
        if not content:
            raise RuntimeError("EEA parquet download returned empty payload")
        return content

    def build_request_body(
        self,
        *,
        countries: list[str] | None = None,
        pollutants: list[str] | None = None,
        window_hours: int | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        hours = window_hours or self._settings.eea_aq_query_window_hours or DEFAULT_QUERY_WINDOW_HOURS
        start = now - timedelta(hours=max(1, min(hours, DEFAULT_QUERY_WINDOW_HOURS)))

        resolved_countries = countries if countries is not None else self._resolve_countries()
        resolved_pollutants = pollutants or list(DEFAULT_POLLUTANTS)

        return {
            "countries": resolved_countries,
            "cities": [],
            "pollutants": resolved_pollutants,
            "dataset": EEA_AQ_DATASET_E2A,
            "source": "ForestWatch",
            "dateTimeStart": start.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "dateTimeEnd": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "aggregationType": "hour",
            "compress": True,
        }

    def _resolve_countries(self) -> list[str]:
        explicit = (self._settings.eea_aq_countries or "").strip()
        if explicit:
            return [code.strip().upper() for code in explicit.split(",") if code.strip()]
        scope = (self._settings.geographic_scope or "romania").lower()
        if scope == "romania":
            return ["RO"]
        return []

    def _url(self, endpoint: str, *, token: str | None = None) -> str:
        base = f"{EEA_AQ_API_BASE.rstrip('/')}/{endpoint.lstrip('/')}"
        if token:
            return f"{base}?UserToken={token}"
        return base

    async def _client(self) -> httpx.AsyncClient:
        if self._http is not None:
            return self._http
        return httpx.AsyncClient(timeout=120.0, follow_redirects=True)

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
