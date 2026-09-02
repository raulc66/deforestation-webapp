"""EFFIS public WFS client — burned-area polygons (no authentication)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .effis_constants import (
    EFFIS_MAX_LIVE_FEATURES,
    EFFIS_MAX_RESPONSE_BYTES,
    EFFIS_REQUEST_TIMEOUT_SECONDS,
    EFFIS_WFS_BASE,
    EFFIS_LAYER_PREFIX,
)
from .effis_gml_parser import parse_effis_gml_features

logger = logging.getLogger("forestwatch.ingestion.effis")


def effis_layer_name_for_year(year: int | None = None) -> str:
    y = year or datetime.now(timezone.utc).year
    return f"{EFFIS_LAYER_PREFIX}.{y}"


def _fetch_single_layer(
    *,
    bbox: tuple[float, float, float, float],
    layer_name: str,
    max_features: int,
) -> list[dict[str, Any]]:
    minx, miny, maxx, maxy = bbox
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typename": layer_name,
        "srsName": "EPSG:4326",
        "bbox": f"{minx},{miny},{maxx},{maxy}",
        "maxFeatures": str(max_features),
    }
    import httpx

    response = httpx.get(
        EFFIS_WFS_BASE,
        params=params,
        timeout=EFFIS_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    content = response.content
    if len(content) > EFFIS_MAX_RESPONSE_BYTES:
        raise ValueError(f"EFFIS response exceeds {EFFIS_MAX_RESPONSE_BYTES} bytes")
    text = content.decode("utf-8", errors="replace")
    return parse_effis_gml_features(text, layer=layer_name)


def fetch_burned_area_features(
    *,
    bbox: tuple[float, float, float, float],
    layer: str | None = None,
    max_features: int = EFFIS_MAX_LIVE_FEATURES,
) -> list[dict[str, Any]]:
    """Fetch burned-area features from verified EFFIS WFS endpoint."""
    if layer:
        records = _fetch_single_layer(bbox=bbox, layer_name=layer, max_features=max_features)
        records.sort(key=lambda r: (str(r.get("fire_date") or ""), str(r.get("fire_id") or "")))
        return records[:max_features]

    now = datetime.now(timezone.utc)
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for year in (now.year, now.year - 1, now.year - 2):
        layer_name = effis_layer_name_for_year(year)
        remaining = max_features - len(records)
        if remaining <= 0:
            break
        try:
            batch = _fetch_single_layer(
                bbox=bbox,
                layer_name=layer_name,
                max_features=remaining,
            )
        except ValueError as exc:
            logger.debug("EFFIS layer %s unavailable: %s", layer_name, exc)
            continue
        for record in batch:
            fire_id = str(record.get("fire_id") or record.get("id") or "")
            if fire_id and fire_id in seen_ids:
                continue
            if fire_id:
                seen_ids.add(fire_id)
            records.append(record)
            if len(records) >= max_features:
                break

    records.sort(key=lambda r: (str(r.get("fire_date") or ""), str(r.get("fire_id") or "")))
    return records[:max_features]
