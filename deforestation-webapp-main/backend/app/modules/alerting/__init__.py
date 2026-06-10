"""Alerting placeholder - notification dispatch (email, SMS, webhook)."""

NAME = "alerting"
STATUS = "planned"
DESCRIPTION = "Dispatch deforestation alerts to subscribed channels."


def module_info() -> dict:
    return {
        "name": NAME,
        "status": STATUS,
        "description": DESCRIPTION,
        "planned_capabilities": [
            "Per-user subscription rules",
            "Multi-channel (email, SMS, webhook, Slack)",
            "Delivery retries & receipts",
        ],
    }


async def run() -> dict:
    return {"name": NAME, "ran": False, "reason": "not implemented yet"}
