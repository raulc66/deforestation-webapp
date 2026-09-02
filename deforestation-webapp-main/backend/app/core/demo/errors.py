"""Demo-specific application errors."""
from __future__ import annotations

from app.core.errors import AppError


class DemoBudgetError(AppError):
    status_code = 403
    code = "demo_budget_exhausted"


class DemoRateLimitError(AppError):
    status_code = 429
    code = "demo_rate_limited"
