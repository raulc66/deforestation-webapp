"""CLC code → CLMS forest attribute normalization (deterministic fixture layer)."""
from __future__ import annotations

_FOREST_TYPES = frozenset({"forest", "near_forest"})

_CLC_FOREST_ATTRIBUTES: dict[int, dict[str, object]] = {
    311: {
        "forest_type": "broadleaved",
        "dominant_leaf_type": "broadleaved",
        "tree_cover_density_pct": 85.0,
    },
    312: {
        "forest_type": "coniferous",
        "dominant_leaf_type": "coniferous",
        "tree_cover_density_pct": 82.0,
    },
    313: {
        "forest_type": "mixed",
        "dominant_leaf_type": "mixed",
        "tree_cover_density_pct": 78.0,
    },
    324: {
        "forest_type": "transitional",
        "dominant_leaf_type": "mixed",
        "tree_cover_density_pct": 55.0,
    },
    231: {
        "forest_type": "pasture_near_forest",
        "dominant_leaf_type": "grassland",
        "tree_cover_density_pct": 25.0,
    },
}

_NON_FOREST_DEFAULTS: dict[str, object] = {
    "forest_type": None,
    "dominant_leaf_type": None,
    "tree_cover_density_pct": 0.0,
}


def normalize_clms_attributes(
    *,
    land_cover_type: str,
    clc_code: int | None,
    props: dict | None = None,
) -> dict[str, object]:
    """Return forest-type and density fields for a classified location."""
    props = props or {}
    if land_cover_type not in _FOREST_TYPES:
        return dict(_NON_FOREST_DEFAULTS)

    if props.get("forest_type"):
        return {
            "forest_type": props.get("forest_type"),
            "dominant_leaf_type": props.get("dominant_leaf_type"),
            "tree_cover_density_pct": props.get("tree_cover_density_pct"),
        }

    if clc_code is not None and clc_code in _CLC_FOREST_ATTRIBUTES:
        return dict(_CLC_FOREST_ATTRIBUTES[clc_code])

    return {
        "forest_type": "unknown_forest",
        "dominant_leaf_type": "unknown",
        "tree_cover_density_pct": 70.0 if land_cover_type == "forest" else 45.0,
    }
