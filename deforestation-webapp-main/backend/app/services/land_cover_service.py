"""Romania Land Cover Classification Service — GIS-backed.

This module is the backward-compatible public surface for the rest of the
codebase.  All spatial classification is now handled by ``gis_land_cover_service``
which loads the Copernicus/CORINE-derived GeoJSON dataset at startup.

Public surface (unchanged)
--------------------------
``classify(lat, lon)``              → str   land-cover label
``classify_event(event)``           → str
``classify_batch(events)``          → list[str]
``FOREST_CONFIDENCE_WEIGHTS``       → dict  (fire-risk analytics weights)

New additions
-------------
``classify_full(lat, lon)``         → dict  {land_cover_type, confidence, source}
``get_dataset_info()``              → dict  {source, version, last_updated, …}

Land-cover labels (exhaustive)
-------------------------------
    "forest"        — Carpathian / Apuseni / Maramureș / Bucovina / Harghita forests
    "near_forest"   — Sub-Carpathian transition belts and western hills
    "agriculture"   — Romanian Plain, Banat, Moldavian Plain, Dobrogea
    "urban"         — Major city bounding boxes
    "water"         — Danube Delta, Black Sea coast, major reservoirs
    "unknown"       — Everything outside the defined zones

Forest confidence weights (used by analytics layer to enrich anomalies)
------------------------------------------------------------------------
These weights reflect how "forest-like" a land cover type is for fire-risk
purposes.  They are NOT the GIS classification confidence.

    forest       → 1.00
    near_forest  → 0.75
    agriculture  → 0.40
    urban        → 0.20
    water        → 0.10
    unknown      → 0.50
"""
from __future__ import annotations

from app.services.gis_land_cover_service import (
    FOREST_CONFIDENCE_WEIGHTS,  # re-exported for backward compatibility
    classify as classify,
    classify_event as classify_event,
    classify_batch as classify_batch,
    classify_full as classify_full,
    get_dataset_info as get_dataset_info,
)

__all__ = [
    "FOREST_CONFIDENCE_WEIGHTS",
    "classify",
    "classify_event",
    "classify_batch",
    "classify_full",
    "get_dataset_info",
]
