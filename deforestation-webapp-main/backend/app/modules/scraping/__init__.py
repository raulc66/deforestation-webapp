"""Web scraping placeholder - news, NGO reports, government bulletins."""

NAME = "scraping"
STATUS = "planned"
DESCRIPTION = "Collect deforestation news & reports from public sources to enrich alerts."


def module_info() -> dict:
    return {
        "name": NAME,
        "status": STATUS,
        "description": DESCRIPTION,
        "planned_capabilities": [
            "Pluggable spider registry",
            "Robots.txt-respecting fetch layer",
            "NER tagging of region & severity",
        ],
    }


async def run() -> dict:
    return {"name": NAME, "ran": False, "reason": "not implemented yet"}
