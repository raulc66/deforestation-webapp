"""Romania geographic classification.

Shared by analytics aggregations (via is_romania_expression) and
Python-level event processing in ingestion providers (via is_romania_event).

Detection priority:
  1. country field — case-insensitive, trimmed
  2. region field  — known Romanian macro-regions
  3. bounding box  — WGS84 coordinate fallback
"""
from __future__ import annotations

ROMANIA_COUNTRY = "romania"

# Canonical Romanian macro-regions (lowercase for case-insensitive matching).
# Includes diacritic and ASCII variants to handle inconsistent source data.
ROMANIA_REGIONS: frozenset[str] = frozenset(
    [
        "transylvania",
        "muntenia",
        "oltenia",
        "banat",
        "moldova",
        "dobrogea",
        "crisana",
        "crișana",
        "maramures",
        "maramureș",
        "bucovina",
        "wallachia",
        "walachia",
        "carpathians",
        "carpathian",
    ]
)

# Approximate Romania bounding box (WGS84).
ROMANIA_BBOX = {
    "min_lat": 43.62,
    "max_lat": 48.27,
    "min_lng": 20.26,
    "max_lng": 29.77,
}


# ---------------------------------------------------------------------------
# Python-level classifier (ingestion providers, tests, etc.)
# ---------------------------------------------------------------------------

def is_romania_event(event: dict) -> bool:
    """Return True when *event* belongs to Romania.

    Accepts any dict with optional 'country', 'region', 'latitude',
    'longitude' keys — missing keys are treated as non-matching rather
    than raising errors.
    """
    country = (event.get("country") or "").strip().lower()
    if country == ROMANIA_COUNTRY:
        return True

    region = (event.get("region") or "").strip().lower()
    if region in ROMANIA_REGIONS:
        return True

    lat = event.get("latitude")
    lng = event.get("longitude")
    if (
        lat is not None
        and lng is not None
        and ROMANIA_BBOX["min_lat"] <= lat <= ROMANIA_BBOX["max_lat"]
        and ROMANIA_BBOX["min_lng"] <= lng <= ROMANIA_BBOX["max_lng"]
    ):
        return True

    return False


# ---------------------------------------------------------------------------
# MongoDB aggregation expression (analytics repository)
# ---------------------------------------------------------------------------

def _normalized(field_ref: str) -> dict:
    return {"$toLower": {"$trim": {"input": {"$ifNull": [field_ref, ""]}}}}


def is_romania_expression() -> dict:
    """MongoDB aggregation $expr: evaluates to True when an event is in Romania."""
    return {
        "$or": [
            {"$eq": [_normalized("$country"), ROMANIA_COUNTRY]},
            {"$in": [_normalized("$region"), sorted(ROMANIA_REGIONS)]},
            {
                "$and": [
                    {"$gte": [{"$ifNull": ["$latitude", -999]}, ROMANIA_BBOX["min_lat"]]},
                    {"$lte": [{"$ifNull": ["$latitude", -999]}, ROMANIA_BBOX["max_lat"]]},
                    {"$gte": [{"$ifNull": ["$longitude", -999]}, ROMANIA_BBOX["min_lng"]]},
                    {"$lte": [{"$ifNull": ["$longitude", -999]}, ROMANIA_BBOX["max_lng"]]},
                ]
            },
        ]
    }
