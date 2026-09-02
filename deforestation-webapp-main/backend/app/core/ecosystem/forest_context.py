"""ForestContext — deterministic CLMS-derived contextual intelligence."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ForestContext(BaseModel):
    """Contextual forest/environment attributes for a geographic point.

    This model represents *reference context*, not a detected intelligence event.
    """

    model_config = ConfigDict(frozen=True)

    is_forest: bool
    land_cover_type: str = "unknown"
    forest_type: str | None = None
    tree_cover_density_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    dominant_leaf_type: str | None = None
    clc_code: int | None = None
    label: str | None = None
    classification_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str = "Copernicus Land Monitoring Service"
    dataset_id: str = "clms.corine_land_cover"
    dataset_version: str = "unknown"
    reference_date: str | None = None
    latitude: float
    longitude: float
    license: str = "Copernicus Land Monitoring Service Terms"
    data_policy: str = "free_and_open"
    provenance: str = "point_in_polygon"

    def to_metadata_block(self) -> dict[str, Any]:
        """Compact dict suitable for ``ForestEvent.metadata.forest_context``."""
        return {
            "is_forest": self.is_forest,
            "land_cover_type": self.land_cover_type,
            "forest_type": self.forest_type,
            "tree_cover_density_pct": self.tree_cover_density_pct,
            "dominant_leaf_type": self.dominant_leaf_type,
            "clc_code": self.clc_code,
            "label": self.label,
            "classification_confidence": self.classification_confidence,
            "source": self.source,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "reference_date": self.reference_date,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "license": self.license,
            "data_policy": self.data_policy,
            "provenance": self.provenance,
        }

    @classmethod
    def from_metadata_block(cls, block: dict[str, Any] | None) -> "ForestContext | None":
        if not block:
            return None
        try:
            return cls(**block)
        except Exception:
            return None

    def to_map_summary(self) -> dict[str, Any]:
        """Minimal fields for map marker enrichment."""
        return {
            "is_forest": self.is_forest,
            "forest_type": self.forest_type,
            "tree_cover_density_pct": self.tree_cover_density_pct,
            "dominant_leaf_type": self.dominant_leaf_type,
            "land_cover_type": self.land_cover_type,
            "context_source": self.source,
            "context_dataset_version": self.dataset_version,
        }


def forest_context_from_lookup(
    lookup: dict[str, Any],
    *,
    latitude: float,
    longitude: float,
) -> ForestContext:
    """Build a ``ForestContext`` from a provider ``lookup()`` result."""
    land_cover = str(lookup.get("land_cover_type") or "unknown")
    is_forest = land_cover in {"forest", "near_forest"}
    return ForestContext(
        is_forest=is_forest,
        land_cover_type=land_cover,
        forest_type=lookup.get("forest_type"),
        tree_cover_density_pct=lookup.get("tree_cover_density_pct"),
        dominant_leaf_type=lookup.get("dominant_leaf_type"),
        clc_code=lookup.get("clc_code"),
        label=lookup.get("label"),
        classification_confidence=float(lookup.get("confidence") or 0.5),
        source=str(lookup.get("source") or "Copernicus Land Monitoring Service"),
        dataset_id=str(lookup.get("dataset_id") or "clms.corine_land_cover"),
        dataset_version=str(lookup.get("dataset_version") or "unknown"),
        reference_date=lookup.get("reference_date"),
        latitude=latitude,
        longitude=longitude,
        license=str(lookup.get("license") or "Copernicus Land Monitoring Service Terms"),
        data_policy=str(lookup.get("data_policy") or "free_and_open"),
        provenance=str(lookup.get("provenance") or "point_in_polygon"),
    )
