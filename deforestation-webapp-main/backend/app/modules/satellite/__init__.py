"""Satellite processing placeholder - tile fetching, NDVI delta, change detection."""

NAME = "satellite"
STATUS = "planned"
DESCRIPTION = "Tile-based processing of Sentinel-2 & Landsat for forest-loss detection."


def module_info() -> dict:
    return {
        "name": NAME,
        "status": STATUS,
        "description": DESCRIPTION,
        "planned_capabilities": [
            "STAC catalog discovery",
            "NDVI / EVI time-series delta",
            "Cloud masking + tile mosaic",
        ],
    }


async def run() -> dict:
    return {"name": NAME, "ran": False, "reason": "not implemented yet"}
