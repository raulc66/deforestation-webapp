"""GFW Data API client — integrated disturbance alerts (API key required for live)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from .gfw_integrated_alerts_constants import (
    GFW_API_BASE,
    GFW_DATASET_ID,
    GFW_DEFAULT_LOOKBACK_DAYS,
    GFW_MAX_LIVE_ALERTS,
    GFW_MAX_RESPONSE_BYTES,
    GFW_REQUEST_TIMEOUT_SECONDS,
)

logger = logging.getLogger("forestwatch.ingestion.gfw")


def _parse_alert_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("data") or payload.get("results") or []
    else:
        rows = []
    records: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        alert_id = (
            row.get("alert_id")
            or row.get("id")
            or row.get("gfw_integrated_alerts__alert_id")
        )
        lat = row.get("latitude")
        lng = row.get("longitude")
        if lat is None or lng is None:
            continue
        records.append(
            {
                "alert_id": str(alert_id or f"{lat:.5f}:{lng:.5f}"),
                "latitude": float(lat),
                "longitude": float(lng),
                "alert_date": row.get("gfw_integrated_alerts__date")
                or row.get("alert_date")
                or row.get("date"),
                "confidence": row.get("gfw_integrated_alerts__confidence")
                or row.get("confidence"),
                "intensity": row.get("gfw_integrated_alerts__intensity")
                or row.get("intensity"),
                "area_ha": row.get("area__ha") or row.get("area_ha"),
                "alert_source": row.get("alert_source") or row.get("source"),
            }
        )
    return records


def fetch_integrated_alerts(
    *,
    api_key: str,
    geometry: dict[str, Any],
    lookback_days: int = GFW_DEFAULT_LOOKBACK_DAYS,
    max_alerts: int = GFW_MAX_LIVE_ALERTS,
) -> list[dict[str, Any]]:
    """Fetch integrated alerts from verified GFW Data API (requires API key)."""
    if not api_key.strip():
        raise ValueError("GFW API key is required for live fetch")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, lookback_days))).date()
    sql = (
        "SELECT alert_id, longitude, latitude, gfw_integrated_alerts__date, "
        "gfw_integrated_alerts__confidence, gfw_integrated_alerts__intensity, area__ha "
        f"FROM results WHERE gfw_integrated_alerts__date >= '{cutoff.isoformat()}' "
        f"LIMIT {max(1, min(max_alerts, GFW_MAX_LIVE_ALERTS))}"
    )
    url = f"{GFW_API_BASE}/dataset/{GFW_DATASET_ID}/latest/query/json"
    import httpx

    response = httpx.post(
        url,
        headers={"x-api-key": api_key.strip(), "Content-Type": "application/json"},
        json={"sql": sql, "geometry": geometry},
        timeout=GFW_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    if len(response.content) > GFW_MAX_RESPONSE_BYTES:
        raise ValueError(f"GFW response exceeds {GFW_MAX_RESPONSE_BYTES} bytes")
    return _parse_alert_rows(response.json())
