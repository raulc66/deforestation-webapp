"""CEMS / environmental hazard category normalization."""
from __future__ import annotations

# Canonical hazard types carried in signal/evidence (not separate incident categories).
CANONICAL_HAZARD_TYPES: frozenset[str] = frozenset({
    "wildfire",
    "flood",
    "earthquake",
    "storm",
    "landslide",
    "drought",
    "volcanic",
    "industrial",
    "other",
})

# CEMS Rapid Mapping category labels → canonical hazard type.
CEMS_CATEGORY_ALIASES: dict[str, str] = {
    "wildfire": "wildfire",
    "fire": "wildfire",
    "flood": "flood",
    "earthquake": "earthquake",
    "storm": "storm",
    "windstorm": "storm",
    "landslide": "landslide",
    "drought": "drought",
    "volcanic activity": "volcanic",
    "volcanic": "volcanic",
    "industrial accident": "industrial",
    "industrial": "industrial",
    "environment": "other",
    "other": "other",
}


def normalize_hazard_type(raw: str | None) -> str:
    if not raw:
        return "other"
    key = str(raw).strip().lower()
    return CEMS_CATEGORY_ALIASES.get(key, "other")


def severity_from_activation(*, n_products: int, closed: bool, hazard_type: str) -> str:
    if closed:
        return "low"
    if n_products >= 5:
        return "critical"
    if n_products >= 2 or hazard_type in {"flood", "earthquake", "volcanic"}:
        return "high"
    if n_products >= 1:
        return "medium"
    return "low"
