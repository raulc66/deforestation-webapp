"""Detector framework contract (ADR-004, ADR-005 pattern, WP1)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from .detection_contract import Detection


class Detector(ABC):
    """Domain-independent detector — segmented baselines in, Detections out."""

    @property
    @abstractmethod
    def detector_id(self) -> str:
        """Stable registry identifier."""

    @property
    @abstractmethod
    def incident_categories(self) -> tuple[str, ...]:
        """Categories this detector may emit."""

    @property
    @abstractmethod
    def signal_type(self) -> str:
        """Provenance label placed on each Detection."""

    @abstractmethod
    def detect(
        self,
        baseline_regions: list[dict[str, Any]],
        detected_at: datetime,
    ) -> list[Detection]:
        """Evaluate segmented baseline rows and return normalized detections.

        ``baseline_regions`` must be shaped like ``_compute_baselines`` output
        entries (``region``, ``baseline_events``, ``current_events``,
        ``deviation_percent``, optional ``forest_confidence``).
        """
