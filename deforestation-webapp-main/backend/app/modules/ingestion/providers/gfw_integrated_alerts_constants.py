"""Verified GFW integrated disturbance alerts constants."""

GFW_SOURCE_NAME = "Global Forest Watch Integrated Alerts"
GFW_PROVIDER_ID = "gfw.integrated_alerts"
GFW_DATASET_ID = "gfw_integrated_alerts"
GFW_DATASET_VERSION = "latest"
GFW_API_BASE = "https://data-api.globalforestwatch.org"
GFW_DOCUMENTATION = "https://data-api.globalforestwatch.org/datasets"
GFW_LICENSE = "Global Forest Watch data policy — attribution required"

GFW_MAX_LIVE_ALERTS = 500
GFW_MAX_RESPONSE_BYTES = 10 * 1024 * 1024
GFW_REQUEST_TIMEOUT_SECONDS = 60
GFW_DEFAULT_LOOKBACK_DAYS = 30

# Romania bounding polygon (lon, lat) — WGS84.
ROMANIA_QUERY_POLYGON: list[list[list[float]]] = [
    [
        [20.2, 43.6],
        [29.7, 43.6],
        [29.7, 48.3],
        [20.2, 48.3],
        [20.2, 43.6],
    ]
]

EUROPE_QUERY_POLYGON: list[list[list[float]]] = [
    [
        [-25.0, 34.0],
        [45.0, 34.0],
        [45.0, 72.0],
        [-25.0, 72.0],
        [-25.0, 34.0],
    ]
]
