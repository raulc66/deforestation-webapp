"""Placeholder module routes - announces planned capabilities."""
from fastapi import APIRouter, HTTPException
from app.modules import ingestion, scraping, satellite, alerting, analytics, ai_predictions

router = APIRouter(prefix="/modules", tags=["modules"])

_MODULES = [
    ("ingestion", ingestion),
    ("scraping", scraping),
    ("satellite", satellite),
    ("alerting", alerting),
    ("analytics", analytics),
    ("ai_predictions", ai_predictions),
]


@router.get("")
async def list_modules():
    return [m.module_info() for _, m in _MODULES]


@router.get("/{name}")
async def get_module(name: str):
    for n, m in _MODULES:
        if n == name:
            return m.module_info()
    raise HTTPException(status_code=404, detail="Module not found")
