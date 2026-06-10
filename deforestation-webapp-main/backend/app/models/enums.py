"""Common types shared across domain models."""
from typing import Literal

Severity = Literal["low", "medium", "high", "critical"]

EventType = Literal[
    "logging",
    "wildfire",
    "mining",
    "agriculture",
    "road_construction",
    "urban_expansion",
    "unknown",
]

EventStatus = Literal["open", "investigating", "resolved"]

EVENT_TYPES: tuple[str, ...] = (
    "logging",
    "wildfire",
    "mining",
    "agriculture",
    "road_construction",
    "urban_expansion",
    "unknown",
)
