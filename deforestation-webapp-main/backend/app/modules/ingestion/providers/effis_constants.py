"""Verified EFFIS source constants — European Forest Fire Information System."""

EFFIS_SOURCE_NAME = "European Forest Fire Information System"
EFFIS_PROVIDER_ID = "effis.wildfire_context"
EFFIS_DATASET_ID = "effis.modis_burned_area"
EFFIS_DATASET_VERSION = "modis.ba.poly-v1"
EFFIS_LICENSE = "Copernicus/EFFIS EU data policy — free and open; attribution required"
EFFIS_WFS_BASE = "https://maps.effis.emergency.copernicus.eu/effis"
EFFIS_LAYER_PREFIX = "modis.ba.poly"
EFFIS_DOCUMENTATION = "https://forest-fire.emergency.copernicus.eu/applications/data-and-services"

EFFIS_MAX_LIVE_FEATURES = 500
EFFIS_MAX_RESPONSE_BYTES = 10 * 1024 * 1024
EFFIS_REQUEST_TIMEOUT_SECONDS = 60

# WFS 1.0.0 bbox axis order: minx,miny,maxx,maxy (lon,lat).
ROMANIA_WFS_BBOX = (20.2, 43.6, 29.7, 48.3)
EUROPE_WFS_BBOX = (-25.0, 34.0, 45.0, 72.0)
