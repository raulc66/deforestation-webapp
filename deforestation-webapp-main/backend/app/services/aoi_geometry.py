"""Deterministic AOI geometry matching — Polygon / MultiPolygon."""
from __future__ import annotations

import math
from typing import Any

_M_PER_DEG_LAT = 111_320.0


def _point_in_ring(lng: float, lat: float, ring: list[list[float]]) -> bool:
    n = len(ring)
    if n < 4:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = float(ring[i][0]), float(ring[i][1])
        xj, yj = float(ring[j][0]), float(ring[j][1])
        if ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-15) + xi
        ):
            inside = not inside
        j = i
    return inside


def point_in_geometry(latitude: float, longitude: float, geometry: dict[str, Any]) -> bool:
    """Return True when the point lies inside the GeoJSON geometry."""
    geom_type = str(geometry.get("type") or "")
    coords = geometry.get("coordinates") or []
    if geom_type == "Polygon":
        if not coords:
            return False
        return _point_in_ring(longitude, latitude, coords[0])
    if geom_type == "MultiPolygon":
        for polygon in coords:
            if polygon and _point_in_ring(longitude, latitude, polygon[0]):
                return True
        return False
    return False


def match_point_to_areas(
    latitude: float,
    longitude: float,
    areas: list[dict[str, Any]],
    *,
    enabled_only: bool = True,
) -> list[dict[str, str]]:
    """Deterministic AOI matches sorted by area id."""
    matches: list[dict[str, str]] = []
    for area in areas:
        if enabled_only and not area.get("enabled", True):
            continue
        geometry = area.get("geometry") or {}
        if point_in_geometry(latitude, longitude, geometry):
            matches.append(
                {
                    "id": str(area.get("id") or area.get("_id")),
                    "name": str(area.get("name") or "Monitored Area"),
                }
            )
    matches.sort(key=lambda item: item["id"])
    return matches


def _ring_area_hectares(ring: list[list[float]]) -> float:
    """Approximate geodesic area for a closed GeoJSON ring in WGS84."""
    if len(ring) < 4:
        return 0.0
    lats = [float(p[1]) for p in ring]
    mean_lat = sum(lats) / len(lats)
    m_per_deg_lng = _M_PER_DEG_LAT * math.cos(math.radians(mean_lat))
    area_m2 = 0.0
    n = len(ring) - 1
    for i in range(n):
        x1 = float(ring[i][0]) * m_per_deg_lng
        y1 = float(ring[i][1]) * _M_PER_DEG_LAT
        x2 = float(ring[i + 1][0]) * m_per_deg_lng
        y2 = float(ring[i + 1][1]) * _M_PER_DEG_LAT
        area_m2 += x1 * y2 - x2 * y1
    return abs(area_m2) / 2.0 / 10_000.0


def geometry_area_hectares(geometry: dict[str, Any]) -> float | None:
    """Deterministic AOI area in hectares from GeoJSON Polygon / MultiPolygon."""
    geom_type = str(geometry.get("type") or "")
    coords = geometry.get("coordinates") or []
    if geom_type == "Polygon":
        if not coords or not coords[0]:
            return None
        area = _ring_area_hectares(coords[0])
        return round(area, 2) if area > 0 else None
    if geom_type == "MultiPolygon":
        total = sum(_ring_area_hectares(poly[0]) for poly in coords if poly and poly[0])
        return round(total, 2) if total > 0 else None
    return None
