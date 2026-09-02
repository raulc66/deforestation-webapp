"""Copernicus Land Monitoring Service (CLMS) contextual provider."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.ingestion.clms_attributes import normalize_clms_attributes
from app.core.ingestion.contextual_provider_contract import ContextualDatasetProvider
from app.services.gis_loader import GISIndex, get_bundled_index, load_geojson_file, reset_singleton

logger = logging.getLogger("forestwatch.clms")

CLMS_SOURCE_NAME = "Copernicus Land Monitoring Service"
CLMS_DATASET_ID = "clms.corine_land_cover"
CLMS_LICENSE = "Copernicus Land Monitoring Service Terms"
CLMS_DATA_POLICY = "free_and_open"
CLMS_GEOGRAPHIC_COVERAGE = "Romania (bundled fixture); Europe when full CLMS export supplied"
CLMS_SPATIAL_RESOLUTION = "100m (CORINE CLC reference scale)"
CLMS_UPDATE_FREQUENCY = "static/reference — refresh on dataset version change only"


class CLMSContextProvider(ContextualDatasetProvider):
    """Fixture-first CLMS contextual dataset provider."""

    def __init__(self, dataset_path: str | Path | None = None) -> None:
        env_path = os.environ.get("CLMS_DATASET_PATH", "").strip()
        self._dataset_path = Path(dataset_path or env_path) if (dataset_path or env_path) else None
        self._index: GISIndex | None = None
        self._last_refresh: datetime | None = None
        self._last_refresh_report: dict[str, Any] = {}

    @property
    def source_name(self) -> str:
        return CLMS_SOURCE_NAME

    @property
    def dataset_id(self) -> str:
        return CLMS_DATASET_ID

    @property
    def provider_id(self) -> str:
        return "clms.land_cover"

    def describe(self) -> dict[str, Any]:
        index = self._ensure_index()
        info = index.info
        return {
            "source": self.source_name,
            "provider_id": self.provider_id,
            "dataset_id": self.dataset_id,
            "dataset_version": info.version,
            "reference_date": info.last_updated,
            "geographic_coverage": CLMS_GEOGRAPHIC_COVERAGE,
            "temporal_coverage": info.last_updated,
            "spatial_resolution": CLMS_SPATIAL_RESOLUTION,
            "classification_system": "CORINE Land Cover (CLC)",
            "feature_count": info.feature_count,
            "file_path": info.file_path,
            "license": CLMS_LICENSE,
            "data_policy": CLMS_DATA_POLICY,
            "update_frequency": CLMS_UPDATE_FREQUENCY,
            "live_access_status": self._live_access_status(),
            "last_refresh_at": self._last_refresh.isoformat() if self._last_refresh else None,
        }

    def _live_access_status(self) -> str:
        if self._dataset_path and self._dataset_path.exists():
            return "local_file"
        return "bundled_fixture"

    async def refresh(self) -> dict[str, Any]:
        reset_singleton()
        self._index = None
        index = self._ensure_index(force_reload=True)
        self._last_refresh = datetime.now(timezone.utc)
        self._last_refresh_report = {
            "status": "success",
            "dataset_version": index.info.version,
            "feature_count": index.info.feature_count,
            "source": self._live_access_status(),
            "refreshed_at": self._last_refresh.isoformat(),
        }
        logger.info(
            "CLMS context refresh complete: version=%s features=%d source=%s",
            index.info.version,
            index.info.feature_count,
            self._live_access_status(),
        )
        return self._last_refresh_report

    def lookup(self, latitude: float, longitude: float) -> dict[str, Any]:
        index = self._ensure_index()
        detailed = index.classify_detailed(latitude, longitude)
        attrs = normalize_clms_attributes(
            land_cover_type=str(detailed["land_cover_type"]),
            clc_code=detailed.get("clc_code"),
        )
        return {
            **detailed,
            **attrs,
            "dataset_id": self.dataset_id,
            "license": CLMS_LICENSE,
            "data_policy": CLMS_DATA_POLICY,
            "provenance": "point_in_polygon",
        }

    def last_refresh_report(self) -> dict[str, Any]:
        return dict(self._last_refresh_report)

    def _ensure_index(self, *, force_reload: bool = False) -> GISIndex:
        if self._index is not None and not force_reload:
            return self._index

        if self._dataset_path and self._dataset_path.exists():
            try:
                self._index = load_geojson_file(self._dataset_path)
                return self._index
            except Exception as exc:
                logger.warning(
                    "CLMS dataset load failed for %s: %s — falling back to bundled fixture",
                    self._dataset_path,
                    exc,
                )

        self._index = get_bundled_index()
        return self._index
