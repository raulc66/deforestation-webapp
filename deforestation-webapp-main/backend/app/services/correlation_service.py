"""Read-only correlation query service."""
from __future__ import annotations

from typing import Any

from app.modules.analytics.correlation_result import CorrelationResult
from app.repositories.correlation_repository import CorrelationRepository


class CorrelationService:
    """Expose persisted correlation results — no command-side logic."""

    def __init__(self, repo: CorrelationRepository) -> None:
        self._repo = repo

    async def list_correlations(self) -> dict[str, Any]:
        rows = await self._repo.list_all()
        correlations: list[dict[str, Any]] = []
        for row in rows:
            try:
                result = CorrelationResult.model_validate(row)
                correlations.append(result.as_read_model())
            except Exception:
                correlations.append(
                    {
                        "correlation_id": row.get("correlation_id"),
                        "correlation_rule": row.get("correlation_rule"),
                        "relationship_type": row.get("relationship_type"),
                        "strength": row.get("strength"),
                    }
                )
        return {"correlations": correlations, "total": len(correlations)}
