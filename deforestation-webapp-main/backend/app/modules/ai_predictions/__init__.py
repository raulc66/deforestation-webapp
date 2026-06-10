"""AI predictions placeholder - ML risk scoring & forecasting."""

NAME = "ai_predictions"
STATUS = "planned"
DESCRIPTION = "ML-based risk scoring & deforestation forecasting."


def module_info() -> dict:
    return {
        "name": NAME,
        "status": STATUS,
        "description": DESCRIPTION,
        "planned_capabilities": [
            "Risk score per region (LSTM / Transformer)",
            "Cause classification",
            "30/60/90-day forecasts",
        ],
    }


async def run() -> dict:
    return {"name": NAME, "ran": False, "reason": "not implemented yet"}
