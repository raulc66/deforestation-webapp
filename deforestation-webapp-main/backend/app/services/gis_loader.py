"""GIS Land Cover Loader — pure Python, zero external GIS dependencies.

Architecture
------------
The loader reads a GeoJSON FeatureCollection once at startup, builds an
in-memory grid-based spatial index, and exposes a fast ``classify()``
method with confidence scores.

Dataset format (GeoJSON)
------------------------
Each Feature must carry::

    {
      "properties": {
        "land_cover_type": "forest" | "near_forest" | "agriculture" | "urban" | "water",
        "confidence":      float (0-1),
        "label":           str,
        "clc_code":        int   (optional, CORINE class code)
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[lon, lat], ...]]   ← GeoJSON lon/lat order
      }
    }

Spatial index
-------------
Romania bounding box is divided into a 51 × 106 grid at ~0.1° resolution.
Each grid cell holds a list of feature indices whose bounding boxes overlap
that cell.  A classify() call:
  1. Maps (lat, lon) to a single grid cell in O(1).
  2. Checks only the K candidate features in that cell (K ≪ total).
  3. Runs ray-casting point-in-polygon on each candidate.
  4. Returns the highest-priority match (urban > water > forest > near_forest >
     agriculture > unknown).

Replacing the dataset
---------------------
Drop a new GeoJSON file at ``app/data/gis/`` and call
``GISLandCoverLoader.from_file(path)``.  No business-logic changes required.

The bundled file ``romania_corine_simplified.geojson`` is a 50-polygon
approximation derived from CORINE CLC 2018.  Replace it with the official
Copernicus CLC export (reprojected to EPSG:4326 and converted to GeoJSON)
for full spatial resolution.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Classification priority (lower = higher priority)
# ---------------------------------------------------------------------------

_PRIORITY: dict[str, int] = {
    "urban":       0,
    "water":       1,
    "forest":      2,
    "near_forest": 3,
    "agriculture": 4,
    "unknown":     5,
}

# Default confidence when the dataset doesn't provide one.
_DEFAULT_CONFIDENCE: dict[str, float] = {
    "forest":      0.90,
    "near_forest": 0.78,
    "agriculture": 0.85,
    "urban":       0.95,
    "water":       0.95,
    "unknown":     0.50,
}

# Romania bounding box for the spatial grid.
_LAT_MIN = 43.4
_LAT_MAX = 48.5
_LON_MIN = 20.0
_LON_MAX = 30.5
_GRID_ROWS = 51
_GRID_COLS = 106
_CELL_LAT = (_LAT_MAX - _LAT_MIN) / _GRID_ROWS   # ≈ 0.10°
_CELL_LON = (_LON_MAX - _LON_MIN) / _GRID_COLS   # ≈ 0.099°


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class _BBox(NamedTuple):
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float


@dataclass
class GISFeature:
    """One land-cover feature loaded from the GeoJSON dataset."""

    land_cover_type: str
    confidence: float
    label: str
    clc_code: int | None
    # Polygon as (lat, lon) tuples — converted from GeoJSON lon/lat.
    polygon: list[tuple[float, float]]
    bbox: _BBox


@dataclass
class GISDatasetInfo:
    """Metadata extracted from the FeatureCollection ``properties`` block."""

    source: str = "Copernicus Land Monitoring Service"
    version: str = "unknown"
    last_updated: str = "unknown"
    feature_count: int = 0
    file_path: str = ""


@dataclass
class GISIndex:
    """Loaded dataset with an in-memory grid-based spatial index."""

    info: GISDatasetInfo
    features: list[GISFeature] = field(default_factory=list)
    # grid[row][col] → list of feature indices
    _grid: dict[tuple[int, int], list[int]] = field(default_factory=dict)
    _built: bool = False

    # ------------------------------------------------------------------ #
    # Index construction
    # ------------------------------------------------------------------ #

    def build(self) -> None:
        """Build the grid index.  Called once after loading."""
        self._grid = {}
        for idx, feat in enumerate(self.features):
            for cell in _bbox_cells(feat.bbox):
                self._grid.setdefault(cell, []).append(idx)
        self._built = True

    # ------------------------------------------------------------------ #
    # Classification
    # ------------------------------------------------------------------ #

    def classify(self, lat: float, lon: float) -> dict:
        """Return classification for a WGS-84 coordinate.

        Returns::

            {
                "land_cover_type": str,
                "confidence":      float,
                "source":          str
            }

        When no polygon contains the point, returns ``land_cover_type="unknown"``.
        """
        if not self._built:
            self.build()

        cell = _coord_to_cell(lat, lon)
        candidates = self._grid.get(cell, [])

        best_type = "unknown"
        best_conf = _DEFAULT_CONFIDENCE["unknown"]
        best_priority = _PRIORITY["unknown"]

        for idx in candidates:
            feat = self.features[idx]
            if not _bbox_contains(feat.bbox, lat, lon):
                continue
            if not _point_in_polygon(lat, lon, feat.polygon):
                continue
            priority = _PRIORITY.get(feat.land_cover_type, _PRIORITY["unknown"])
            if priority < best_priority:
                best_priority = priority
                best_type = feat.land_cover_type
                best_conf = feat.confidence

        return {
            "land_cover_type": best_type,
            "confidence": best_conf,
            "source": self.info.source,
        }


# ---------------------------------------------------------------------------
# Geometry helpers — pure Python, no external dependencies
# ---------------------------------------------------------------------------


def _point_in_polygon(lat: float, lon: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon test.

    ``polygon`` is a list of (lat, lon) pairs.  Handles arbitrary convex
    and concave polygons.  Returns False for degenerate inputs (< 3 vertices).
    """
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > lon) != (yj > lon)) and (
            lat < (xj - xi) * (lon - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i
    return inside


def _bbox_cells(bbox: _BBox) -> list[tuple[int, int]]:
    """Return all grid cells that overlap the given bounding box."""
    row_min = max(0, int((bbox.lat_min - _LAT_MIN) / _CELL_LAT))
    row_max = min(_GRID_ROWS - 1, int((bbox.lat_max - _LAT_MIN) / _CELL_LAT))
    col_min = max(0, int((bbox.lon_min - _LON_MIN) / _CELL_LON))
    col_max = min(_GRID_COLS - 1, int((bbox.lon_max - _LON_MIN) / _CELL_LON))
    cells = []
    for row in range(row_min, row_max + 1):
        for col in range(col_min, col_max + 1):
            cells.append((row, col))
    return cells


def _coord_to_cell(lat: float, lon: float) -> tuple[int, int]:
    """Map a (lat, lon) coordinate to a grid cell index."""
    row = int((lat - _LAT_MIN) / _CELL_LAT)
    col = int((lon - _LON_MIN) / _CELL_LON)
    row = max(0, min(_GRID_ROWS - 1, row))
    col = max(0, min(_GRID_COLS - 1, col))
    return (row, col)


def _bbox_contains(bbox: _BBox, lat: float, lon: float) -> bool:
    """Fast bounding-box pre-filter before running ray-casting."""
    return (
        bbox.lat_min <= lat <= bbox.lat_max
        and bbox.lon_min <= lon <= bbox.lon_max
    )


def _extract_bbox(polygon: list[tuple[float, float]]) -> _BBox:
    """Compute the axis-aligned bounding box of a polygon."""
    lats = [p[0] for p in polygon]
    lons = [p[1] for p in polygon]
    return _BBox(min(lats), max(lats), min(lons), max(lons))


# ---------------------------------------------------------------------------
# GeoJSON parsing
# ---------------------------------------------------------------------------


def _parse_geometry(geometry: dict) -> list[tuple[float, float]] | None:
    """Convert a GeoJSON Polygon geometry to a list of (lat, lon) tuples.

    GeoJSON uses [longitude, latitude] order; we convert to (lat, lon).
    Only the exterior ring (index 0) is used — holes are ignored for the
    simplified use case.

    Supports ``Polygon`` and ``MultiPolygon`` (returns the first polygon
    of a MultiPolygon).
    """
    if geometry is None:
        return None
    gtype = geometry.get("type")
    if gtype == "Polygon":
        ring = geometry.get("coordinates", [[]])[0]
    elif gtype == "MultiPolygon":
        polys = geometry.get("coordinates", [[]])
        if not polys:
            return None
        ring = polys[0][0]
    else:
        return None
    if not ring:
        return None
    # GeoJSON [lon, lat] → (lat, lon)
    return [(coord[1], coord[0]) for coord in ring]


def _parse_feature(feature: dict) -> GISFeature | None:
    """Parse a single GeoJSON Feature into a ``GISFeature``.

    Returns ``None`` if the feature is missing required fields or has an
    unsupported geometry type.
    """
    if feature.get("type") != "Feature":
        return None

    props = feature.get("properties") or {}
    land_cover_type = props.get("land_cover_type", "unknown")
    if land_cover_type not in _PRIORITY:
        land_cover_type = "unknown"

    confidence = float(props.get("confidence") or _DEFAULT_CONFIDENCE.get(land_cover_type, 0.5))
    label = str(props.get("label") or "")
    clc_code = props.get("clc_code")

    polygon = _parse_geometry(feature.get("geometry"))
    if not polygon or len(polygon) < 3:
        return None

    bbox = _extract_bbox(polygon)
    return GISFeature(
        land_cover_type=land_cover_type,
        confidence=confidence,
        label=label,
        clc_code=int(clc_code) if clc_code is not None else None,
        polygon=polygon,
        bbox=bbox,
    )


# ---------------------------------------------------------------------------
# Loader — public entry points
# ---------------------------------------------------------------------------


def load_geojson_file(path: str | Path) -> GISIndex:
    """Load and index a GeoJSON FeatureCollection from disk.

    Parameters
    ----------
    path:
        Path to the ``.geojson`` file.  The file is read once; subsequent
        ``classify()`` calls use only the in-memory index.

    Returns
    -------
    GISIndex
        A built index ready for classification.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the file is not a valid GeoJSON FeatureCollection.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"GIS dataset not found: {path}")

    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    return _build_index_from_geojson(data, file_path=str(path))


def load_geojson_dict(data: dict) -> GISIndex:
    """Load and index a GeoJSON FeatureCollection from an in-memory dict.

    Useful for testing without a filesystem dependency.
    """
    return _build_index_from_geojson(data, file_path="<in-memory>")


def _build_index_from_geojson(data: dict, file_path: str = "") -> GISIndex:
    """Internal: parse features, build grid index, return GISIndex."""
    if data.get("type") != "FeatureCollection":
        raise ValueError("Expected a GeoJSON FeatureCollection")

    root_props = data.get("properties") or {}
    info = GISDatasetInfo(
        source=str(root_props.get("source") or "Copernicus Land Monitoring Service"),
        version=str(root_props.get("version") or "unknown"),
        last_updated=str(root_props.get("last_updated") or "unknown"),
        file_path=file_path,
    )

    features: list[GISFeature] = []
    for raw in data.get("features") or []:
        feat = _parse_feature(raw)
        if feat is not None:
            features.append(feat)

    info.feature_count = len(features)
    index = GISIndex(info=info, features=features)
    index.build()
    return index


# ---------------------------------------------------------------------------
# Bundled dataset singleton
# ---------------------------------------------------------------------------

_BUNDLED_PATH = Path(__file__).parent.parent / "data" / "gis" / "romania_corine_simplified.geojson"

_singleton: GISIndex | None = None


def get_bundled_index() -> GISIndex:
    """Return the module-level GIS index, loading it on first call.

    Thread-safety note: module-level assignment is GIL-protected in CPython.
    If you need strict thread safety, initialise explicitly at startup.
    """
    global _singleton
    if _singleton is None:
        if _BUNDLED_PATH.exists():
            _singleton = load_geojson_file(_BUNDLED_PATH)
        else:
            # Fallback: empty index with metadata stub
            _singleton = GISIndex(
                info=GISDatasetInfo(
                    source="Copernicus Land Monitoring Service",
                    version="unknown — data file missing",
                    last_updated="unknown",
                    feature_count=0,
                    file_path=str(_BUNDLED_PATH),
                )
            )
            _singleton.build()
    return _singleton


def reset_singleton() -> None:
    """Force reload of the bundled dataset on next access.  Test helper."""
    global _singleton
    _singleton = None
