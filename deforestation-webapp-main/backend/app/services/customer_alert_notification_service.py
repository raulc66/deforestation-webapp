"""Orchestrates customer alert evaluation + dispatch on scheduler path."""
from __future__ import annotations

import logging
from typing import Any

from app.services.customer_alert_dispatcher import CustomerAlertDispatcher
from app.services.customer_alert_evaluation_service import CustomerAlertEvaluationService

logger = logging.getLogger("forestwatch.customer_alerts")


class CustomerAlertNotificationService:
    """Organization-scoped alert pipeline — isolated from intelligence reconciliation."""

    def __init__(
        self,
        evaluation_svc: CustomerAlertEvaluationService,
        dispatcher: CustomerAlertDispatcher,
    ) -> None:
        self._evaluation = evaluation_svc
        self._dispatcher = dispatcher

    async def run_post_reconciliation(
        self,
        *,
        active_events: list[dict[str, Any]],
        resolved_events: list[dict[str, Any]] | None = None,
        health_rows: list[dict[str, Any]] | None = None,
        correlation_enabled: bool = False,
        correlation_cycle_id: str | None = None,
        current_cycle_id: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate policies then dispatch pending alerts. Never raises."""
        try:
            eval_stats = await self._evaluation.evaluate_cycle(
                active_events=active_events,
                resolved_events=resolved_events,
                health_rows=health_rows,
                correlation_enabled=correlation_enabled,
                correlation_cycle_id=correlation_cycle_id,
                current_cycle_id=current_cycle_id,
            )
        except Exception:
            logger.exception("Customer alert evaluation error")
            eval_stats = {"organizations": 0, "candidates_created": 0, "skipped": 0}
        try:
            dispatch_stats = await self._dispatcher.dispatch_pending()
        except Exception:
            logger.exception("Customer alert dispatch error")
            dispatch_stats = {"attempted": 0, "sent": 0, "failed": 0, "suppressed": 0}
        return {"evaluation": eval_stats, "dispatch": dispatch_stats}
