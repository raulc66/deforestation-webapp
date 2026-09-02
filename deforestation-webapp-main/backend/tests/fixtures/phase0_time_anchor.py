"""Shared deterministic time-anchor injection for Phase 0 golden runs (WP0.3).

All Phase 0 pipeline and oracle tests **MUST** use :func:`inject_phase0_time` (or
callers that wrap it) whenever production code reads ``utcnow()`` — never wall clock.

Cycle reconciliation anchors come from :data:`fixtures.phase0_golden_fixture.CYCLE_ANCHORS`.
Service-layer reads that still call ``utcnow()`` internally are pinned to the active
anchor via the patch targets listed in :data:`UTCNOW_PATCH_TARGETS`.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Iterator
from unittest.mock import patch

from fixtures.phase0_golden_fixture import CYCLE_ANCHORS, REFERENCE_NOW, cycle_anchor

# Production modules consulted during the Phase 0 golden pipeline that call utcnow().
UTCNOW_PATCH_TARGETS: tuple[str, ...] = (
    "app.modules.analytics.analytics_service.utcnow",
    "app.modules.analytics.threat_assessment_service.utcnow",
    "app.modules.analytics.command_center_service.utcnow",
)

SIGN_OFF_RUN_COUNT: int = 10


@contextmanager
def inject_phase0_time(anchor: datetime) -> Iterator[datetime]:
    """Pin ``utcnow()`` across all Phase 0 pipeline modules to *anchor*."""
    started = [patch(target, return_value=anchor) for target in UTCNOW_PATCH_TARGETS]
    try:
        for item in started:
            item.start()
        yield anchor
    finally:
        for item in reversed(started):
            item.stop()


def pipeline_final_anchor() -> datetime:
    """Reconciliation anchor used for post-cycle aggregation and Command Center."""
    return CYCLE_ANCHORS[-1]
