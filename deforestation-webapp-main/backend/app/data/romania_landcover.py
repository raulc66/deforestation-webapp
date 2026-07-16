"""Romania land cover polygon data — deterministic bounding-polygon definitions.

Structure
---------
All zones are rectangles expressed as four (lat, lon) vertices in
counter-clockwise order (SW → NW → NE → SE).  The helper ``_rect()``
builds these rectangles so the raw numbers stay readable.

The ``LAND_COVER_ZONES`` list is ordered by classification priority:

    1. urban        — city bounding boxes
    2. water        — Danube Delta and coast
    3. forest       — Carpathian / Apuseni / Maramureș / Bucovina / Harghita
    4. near_forest  — Sub-Carpathian transition belts and western hills
    5. agriculture  — Romanian Plain, Banat, Moldavian Plain, Dobrogea

Anything that falls outside every polygon receives the fallback label
``"unknown"`` in the classification layer.

Geographic accuracy
-------------------
These are *simplified* bounding rectangles, not exact cadastral boundaries.
They are accurate enough to classify Romanian satellite fire detections by
dominant land-cover type.  A future upgrade can replace any zone's polygon
with a more precise multi-vertex shape without touching the service layer,
because the ray-casting algorithm works on arbitrary convex/concave polygons.

Coordinate system: WGS-84 decimal degrees, latitude first.
Romania bounding box: lat 43.62 – 48.27 °N, lon 20.26 – 29.68 °E.

Point-in-polygon
----------------
``_point_in_polygon(lat, lon, polygon)`` implements the standard ray-casting
(Jordan curve) algorithm.  It is exported so the test suite can exercise it
independently of the classification service.
"""
from __future__ import annotations

from typing import NamedTuple


# ---------------------------------------------------------------------------
# Geometry primitives
# ---------------------------------------------------------------------------


def _rect(
    min_lat: float, max_lat: float, min_lon: float, max_lon: float
) -> list[tuple[float, float]]:
    """Build a rectangular polygon as a list of (lat, lon) vertices.

    Vertices are listed counter-clockwise: SW → NW → NE → SE.
    The order is consistent with the right-hand rule and works correctly
    with the ray-casting algorithm.
    """
    return [
        (min_lat, min_lon),  # SW
        (max_lat, min_lon),  # NW
        (max_lat, max_lon),  # NE
        (min_lat, max_lon),  # SE
    ]


def _point_in_polygon(
    lat: float, lon: float, polygon: list[tuple[float, float]]
) -> bool:
    """Ray-casting point-in-polygon test.

    Works on any simple polygon (convex or concave) expressed as a list of
    ``(lat, lon)`` tuples.  Returns ``False`` for degenerate inputs (fewer
    than 3 vertices).

    The algorithm casts a horizontal ray from the query point eastward and
    counts edge crossings.  An odd count means inside.

    Parameters
    ----------
    lat, lon:
        WGS-84 decimal degrees of the query point.
    polygon:
        Ordered vertex list; the polygon is implicitly closed (last vertex
        connects back to the first).
    """
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    x, y = lon, lat  # treat lon as x-axis, lat as y-axis
    j = n - 1
    for i in range(n):
        lat_i, lon_i = polygon[i]
        lat_j, lon_j = polygon[j]
        xi, yi = lon_i, lat_i
        xj, yj = lon_j, lat_j
        # Edge crosses the y-level of the ray and the ray hits the edge segment
        if (yi > y) != (yj > y):
            x_intersect = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_intersect:
                inside = not inside
        j = i
    return inside


# ---------------------------------------------------------------------------
# Zone descriptor
# ---------------------------------------------------------------------------


class LandCoverZone(NamedTuple):
    """A named polygonal region with a fixed land-cover type."""

    name: str
    cover_type: str  # "forest" | "near_forest" | "urban" | "water" | "agriculture"
    polygon: list[tuple[float, float]]  # (lat, lon) vertices


# ---------------------------------------------------------------------------
# Ordered zone list  — checked top-to-bottom; first match wins
# ---------------------------------------------------------------------------

LAND_COVER_ZONES: list[LandCoverZone] = [

    # ── Urban areas ─────────────────────────────────────────────────────────
    # Tight bounding boxes around the city proper.  Urban has the highest
    # classification priority so a fire inside a city perimeter is labelled
    # correctly even if the coords technically overlap a forested hill.

    LandCoverZone(
        "Bucharest", "urban",
        _rect(44.31, 44.59, 25.92, 26.23),
    ),
    LandCoverZone(
        "Cluj-Napoca", "urban",
        _rect(46.74, 46.83, 23.50, 23.73),
    ),
    LandCoverZone(
        "Iași", "urban",
        _rect(47.11, 47.22, 27.53, 27.68),
    ),
    LandCoverZone(
        "Timișoara", "urban",
        _rect(45.72, 45.83, 21.17, 21.44),
    ),
    LandCoverZone(
        "Constanța", "urban",
        _rect(44.12, 44.24, 28.57, 28.73),
    ),
    LandCoverZone(
        "Brașov", "urban",
        _rect(45.62, 45.73, 25.53, 25.71),
    ),

    # ── Water ────────────────────────────────────────────────────────────────
    # The Danube Delta is Romania's principal water-dominated land-cover zone.
    # Checked after urban so that Tulcea city is not mistakenly classified as water.

    LandCoverZone(
        "Danube Delta", "water",
        _rect(44.76, 45.40, 28.60, 29.70),
    ),

    # ── Forest zones ─────────────────────────────────────────────────────────
    # The Carpathian arc and its major massifs.  Order within this block does
    # not affect correctness because all entries share ``cover_type = "forest"``.
    # Zones may overlap; the first match for any given point is returned.

    # Eastern Carpathians — main Carpathian arc (Moldova-Transylvania border).
    # Covers the Bistrița, Ceahlău, Rarău, Călimani, Hășmaș ranges.
    LandCoverZone(
        "Eastern Carpathians", "forest",
        _rect(45.80, 47.90, 24.80, 26.70),
    ),
    # Southern Carpathians — Fagaraș, Bucegi, Piatra Craiului, Ciucaș.
    LandCoverZone(
        "Southern Carpathians", "forest",
        _rect(45.25, 45.80, 24.50, 25.60),
    ),
    # Western Carpathians / Retezat / Parâng / Șureanu.
    LandCoverZone(
        "Western Carpathians", "forest",
        _rect(45.10, 45.65, 22.70, 24.50),
    ),
    # Apuseni Mountains — the western outlier massif.
    LandCoverZone(
        "Apuseni Mountains", "forest",
        _rect(46.00, 47.25, 22.35, 23.90),
    ),
    # Maramureș forests — dense mixed forest in northwest Romania.
    LandCoverZone(
        "Maramureș Forests", "forest",
        _rect(47.48, 47.95, 23.35, 25.60),
    ),
    # Bucovina forests — UNESCO-heritage old-growth area in northeast.
    LandCoverZone(
        "Bucovina Forests", "forest",
        _rect(47.28, 47.92, 25.45, 26.65),
    ),
    # Harghita-Covasna — forested upland in central-east Romania.
    LandCoverZone(
        "Harghita-Covasna", "forest",
        _rect(45.50, 46.80, 25.50, 26.60),
    ),
    # Retezat National Park — explicit zone even though it overlaps
    # Western Carpathians, included for named-zone completeness.
    LandCoverZone(
        "Retezat NP", "forest",
        _rect(45.20, 45.58, 22.70, 23.25),
    ),

    # ── Near-forest (sub-Carpathian transition zones) ─────────────────────────
    # Hilly belts between the Carpathian forests and the lowland plains.
    # Medium forest confidence (0.75) — mixed forest + pasture + small holdings.

    # Southern sub-Carpathian arc (Muscel, Prahova, Buzău, Vrancea hills).
    LandCoverZone(
        "Sub-Carpathian South", "near_forest",
        _rect(44.75, 45.35, 23.80, 27.20),
    ),
    # Eastern/Moldavian sub-Carpathians (Neamț, Bacău, Vrancea hills).
    LandCoverZone(
        "Sub-Carpathian East", "near_forest",
        _rect(46.00, 47.25, 26.40, 27.60),
    ),
    # Western transition hills (between Apuseni and the Banat/Crișana plain).
    LandCoverZone(
        "Western Hills", "near_forest",
        _rect(46.00, 47.50, 21.80, 23.40),
    ),
    # Hunedoara-Caraș hills (south-western hills).
    LandCoverZone(
        "Hunedoara Hills", "near_forest",
        _rect(45.40, 46.10, 22.40, 23.60),
    ),

    # ── Agriculture (plains) ──────────────────────────────────────────────────
    # Large lowland areas dominated by crop farming.

    # Câmpia Română — the main Romanian plain south of the Carpathians.
    LandCoverZone(
        "Romanian Plain", "agriculture",
        _rect(43.60, 44.80, 23.40, 28.60),
    ),
    # Câmpia de Vest — Banat and Crișana plain in the west.
    LandCoverZone(
        "Western Plain", "agriculture",
        _rect(45.40, 47.60, 20.15, 22.30),
    ),
    # Câmpia Moldovei — Moldavian lowland plain in the northeast.
    LandCoverZone(
        "Moldavian Plain", "agriculture",
        _rect(46.30, 47.80, 27.20, 28.60),
    ),
    # Dobrogea plateau — agricultural and steppe region between Delta and Danube.
    LandCoverZone(
        "Dobrogea Plateau", "agriculture",
        _rect(43.80, 44.80, 27.80, 29.00),
    ),
]
