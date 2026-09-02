"""In-process request budget for demonstration sessions.

Not a distributed limiter. Sufficient for the current single-process deployment.
"""
from __future__ import annotations

import time
from collections import defaultdict

from app.core.demo.constants import DEMO_REQUESTS_PER_MINUTE
from app.core.demo.errors import DemoRateLimitError

_hits: dict[str, list[float]] = defaultdict(list)


def check_demo_rate(session_id: str, *, now: float | None = None) -> None:
    stamp = now if now is not None else time.time()
    window = stamp - 60.0
    recent = [hit for hit in _hits[session_id] if hit >= window]
    if len(recent) >= DEMO_REQUESTS_PER_MINUTE:
        _hits[session_id] = recent
        raise DemoRateLimitError("Too many demonstration requests. Pause and try again.")
    recent.append(stamp)
    _hits[session_id] = recent


def reset_demo_rate_limiter() -> None:
    _hits.clear()
