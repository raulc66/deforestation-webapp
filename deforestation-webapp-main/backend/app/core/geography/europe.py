"""European geographic classification for intelligence scope filtering.

Classification priority (documented mechanism):
  1. ``metadata.ingestion.is_romania`` — Romania is always in-scope for Europe
  2. Explicit ``country`` field — case-insensitive match against ISO-style names
  3. ``metadata.emergency_activation.countries`` — CEMS activation country lists
  4. Coordinate bbox fallback — approximate Europe WGS84 envelope when country absent

The country set covers EU/EEA and neighbouring states used by Copernicus EMS.
It is deterministic and does not depend on external geography services.
"""
from __future__ import annotations

from .romania import is_romania_event

# Authoritative country names as emitted by Copernicus EMS and EEA providers.
EUROPEAN_COUNTRY_NAMES: frozenset[str] = frozenset({
    "Albania",
    "Andorra",
    "Austria",
    "Belarus",
    "Belgium",
    "Bosnia and Herzegovina",
    "Bulgaria",
    "Croatia",
    "Cyprus",
    "Czechia",
    "Czech Republic",
    "Denmark",
    "Estonia",
    "Finland",
    "France",
    "Germany",
    "Greece",
    "Hungary",
    "Iceland",
    "Ireland",
    "Italy",
    "Kosovo",
    "Latvia",
    "Liechtenstein",
    "Lithuania",
    "Luxembourg",
    "Malta",
    "Moldova",
    "Monaco",
    "Montenegro",
    "Netherlands",
    "North Macedonia",
    "Norway",
    "Poland",
    "Portugal",
    "Romania",
    "San Marino",
    "Serbia",
    "Slovakia",
    "Slovenia",
    "Spain",
    "Sweden",
    "Switzerland",
    "Ukraine",
    "United Kingdom",
    "Vatican City",
})

EUROPEAN_COUNTRY_NAMES_LOWER: frozenset[str] = frozenset(
    name.lower() for name in EUROPEAN_COUNTRY_NAMES
)

# Approximate Europe bounding box (excludes North Africa / Middle East).
EUROPE_BBOX = {
    "min_lat": 34.0,
    "max_lat": 72.0,
    "min_lng": -25.0,
    "max_lng": 45.0,
}


def normalize_country_name(value: str | None) -> str:
    return str(value or "").strip()


def is_europe_country(country: str | None) -> bool:
    normalized = normalize_country_name(country).lower()
    if not normalized:
        return False
    return normalized in EUROPEAN_COUNTRY_NAMES_LOWER


def _activation_countries(event: dict) -> list[str]:
    activation = (event.get("metadata") or {}).get("emergency_activation") or {}
    raw = activation.get("countries") or []
    return [str(c) for c in raw if c]


def is_europe_event(event: dict) -> bool:
    """Return True when *event* is geographically within Europe."""
    if is_romania_event(event):
        return True

    ingestion = (event.get("metadata") or {}).get("ingestion") or {}
    if ingestion.get("is_romania") is True:
        return True

    if is_europe_country(event.get("country")):
        return True

    for country in _activation_countries(event):
        if is_europe_country(country):
            return True

    lat = event.get("latitude")
    lng = event.get("longitude")
    if lat is not None and lng is not None:
        return (
            EUROPE_BBOX["min_lat"] <= float(lat) <= EUROPE_BBOX["max_lat"]
            and EUROPE_BBOX["min_lng"] <= float(lng) <= EUROPE_BBOX["max_lng"]
        )

    return False


def _normalized_country_field(field_ref: str) -> dict:
    return {"$toLower": {"$trim": {"input": {"$ifNull": [field_ref, ""]}}}}


def is_europe_expression() -> dict:
    """MongoDB aggregation expression: True when document is in Europe."""
    from .romania import is_romania_expression

    return {
        "$or": [
            is_romania_expression(),
            {"$eq": ["$metadata.ingestion.is_romania", True]},
            {
                "$in": [
                    _normalized_country_field("$country"),
                    sorted(EUROPEAN_COUNTRY_NAMES_LOWER),
                ]
            },
            {
                "$gt": [
                    {
                        "$size": {
                            "$filter": {
                                "input": {
                                    "$ifNull": [
                                        "$metadata.emergency_activation.countries",
                                        [],
                                    ]
                                },
                                "as": "c",
                                "cond": {
                                    "$in": [
                                        {"$toLower": {"$trim": {"input": "$$c"}}},
                                        sorted(EUROPEAN_COUNTRY_NAMES_LOWER),
                                    ]
                                },
                            }
                        }
                    },
                    0,
                ]
            },
            {
                "$and": [
                    {"$gte": [{"$ifNull": ["$latitude", -999]}, EUROPE_BBOX["min_lat"]]},
                    {"$lte": [{"$ifNull": ["$latitude", -999]}, EUROPE_BBOX["max_lat"]]},
                    {"$gte": [{"$ifNull": ["$longitude", -999]}, EUROPE_BBOX["min_lng"]]},
                    {"$lte": [{"$ifNull": ["$longitude", -999]}, EUROPE_BBOX["max_lng"]]},
                ]
            },
        ]
    }
