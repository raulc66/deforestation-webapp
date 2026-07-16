"""GIS-backed Land Cover Service for Romania.

This service wraps the ``GISIndex`` produced by ``gis_loader`` and exposes
the same public API as the previous polygon-based system, plus extended
methods for richer classification results.

Public surface
--------------
``classify(lat, lon)``               → str  (backward-compatible label)
``classify_full(lat, lon)``          → dict {land_cover_type, confidence, source}
``classify_event(event)``            → str
``classify_batch(events)``           → list[str]
``get_dataset_info()``               → dict  (source, version, last_updated, …)

The module-level singleton is initialised from the bundled
``romania_corine_simplified.geojson`` on first import.  Call
``reload()`` to force a fresh load (useful in tests).
"""
from __future__ import annotations

from app.services.gis_loader import GISIndex, GISDatasetInfo, get_bundled_index

# Forest confidence weights — unchanged semantics (used by analytics layer
# to compute how "forest-like" a location is for fire-risk purposes).
# These are distinct from GIS classification confidence.
FOREST_CONFIDENCE_WEIGHTS: dict[str, float] = {
    "forest":      1.00,
    "near_forest": 0.75,
    "agriculture": 0.40,
    "urban":       0.20,
    "water":       0.10,
    "unknown":     0.50,
}

_DEFAULT_LABEL = "unknown"


class GISLandCoverService:
    """Classifies coordinates using the loaded GIS spatial index.

    Delegates all spatial work to ``GISIndex``; this class adds the
    event-dict interface expected by the ingestion pipeline.
    """

    def __init__(self, index: GISIndex) -> None:
        self._index = index

    # ------------------------------------------------------------------ #
    # Core classification
    # ------------------------------------------------------------------ #

    def classify(self, latitude: float, longitude: float) -> str:
        """Return the land-cover label for a WGS-84 coordinate.

        This is the backward-compatible entry point used by the ingestion
        pipeline.  Returns ``"unknown"`` for coordinates outside Romania or
        outside all known polygons.
        """
        result = self._index.classify(latitude, longitude)
        return result["land_cover_type"]

    def classify_full(self, latitude: float, longitude: float) -> dict:
        """Return full classification including confidence and data source.

        Returns::

            {
                "land_cover_type": "forest",
                "confidence":      0.93,
                "source":          "Copernicus Land Monitoring Service"
            }
        """
        return self._index.classify(latitude, longitude)

    # ------------------------------------------------------------------ #
    # Event-dict interface
    # ------------------------------------------------------------------ #

    def classify_event(self, event: dict) -> str:
        """Classify a single event dict using its ``latitude``/``longitude`` keys.

        Missing or non-numeric coordinates default to ``"unknown"``.
        """
        try:
            lat = float(event["latitude"])
            lon = float(event["longitude"])
        except (KeyError, TypeError, ValueError):
            return _DEFAULT_LABEL
        return self.classify(lat, lon)

    def classify_batch(self, events: list[dict]) -> list[str]:
        """Classify a list of event dicts.

        Returns a list of labels in the same order as *events*.
        """
        return [self.classify_event(e) for e in events]

    # ------------------------------------------------------------------ #
    # Metadata
    # ------------------------------------------------------------------ #

    def get_dataset_info(self) -> dict:
        """Return metadata about the loaded GIS dataset."""
        info: GISDatasetInfo = self._index.info
        return {
            "source": info.source,
            "version": info.version,
            "last_updated": info.last_updated,
            "feature_count": info.feature_count,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_service: GISLandCoverService | None = None


def _get_service() -> GISLandCoverService:
    """Return (or lazily create) the module-level service instance."""
    global _service
    if _service is None:
        _service = GISLandCoverService(get_bundled_index())
    return _service


def reload() -> None:
    """Force service reload from the bundled dataset.  Test helper."""
    from app.services import gis_loader as _loader
    _loader.reset_singleton()
    global _service
    _service = None


# ---------------------------------------------------------------------------
# Module-level convenience functions (mirrors old land_cover_service API)
# ---------------------------------------------------------------------------


def classify(latitude: float, longitude: float) -> str:
    """Classify one coordinate pair → land-cover label."""
    return _get_service().classify(latitude, longitude)


def classify_full(latitude: float, longitude: float) -> dict:
    """Classify one coordinate pair → {land_cover_type, confidence, source}."""
    return _get_service().classify_full(latitude, longitude)


def classify_event(event: dict) -> str:
    """Classify a single event dict."""
    return _get_service().classify_event(event)


def classify_batch(events: list[dict]) -> list[str]:
    """Classify a list of event dicts."""
    return _get_service().classify_batch(events)


def get_dataset_info() -> dict:
    """Return metadata about the active GIS dataset."""
    return _get_service().get_dataset_info()
