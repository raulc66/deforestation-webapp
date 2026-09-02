"""Analytics service - shapes raw aggregation results into frontend-ready JSON.

No ML or predictions here; just deterministic rollups.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .intelligence_events_service import IntelligenceEventsService
    from app.repositories.correlation_repository import CorrelationRepository
    from app.repositories.intelligence_cycle_repository import IntelligenceCycleRepository

from app.core.errors import AppError
from app.models.base import ensure_utc, utcnow
from app.models.enums import EVENT_TYPES
from app.services.land_cover_service import get_dataset_info as _get_gis_dataset_info

from .analytics_repository import VALID_INTERVALS, AnalyticsRepository
from .anomaly_thresholds import get_anomaly_thresholds
from .segmented_baseline import parse_segment_key

logger = logging.getLogger("forestwatch.analytics")

SEVERITY_ORDER = ("low", "medium", "high", "critical")
CONFIDENCE_BUCKETS = ("low", "medium", "high")

from app.core.ingestion.source_reliability import (
    SourceReliabilityInput,
    compute_baseline_reliability_score,
    compute_baseline_reliability_score_legacy,
    firms_reliability_alert_trigger,
)


def _r(value: float | None, places: int = 2) -> float:
    return round(value, places) if value is not None else 0.0


def _first_row(rows: list[dict] | None) -> dict:
    if not rows:
        return {}
    return rows[0]


def _confidence_distribution(rows: list[dict] | None) -> dict[str, int]:
    by_conf = {
        r["_id"]: int(r["count"])
        for r in (rows or [])
        if r.get("_id") in CONFIDENCE_BUCKETS
    }
    return {bucket: by_conf.get(bucket, 0) for bucket in CONFIDENCE_BUCKETS}


# ---------------------------------------------------------------------------
# Alert evaluation — pure heuristic functions (no I/O)
# ---------------------------------------------------------------------------

# Numeric rank used for severity comparisons (higher = more severe).
_SEVERITY_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}

_FIRMS_SOURCE = "NASA FIRMS"


def _reliability_score(
    average_confidence: float,
    total_events: int,
    romania_events: int,
    severity_distribution: dict[str, int],
) -> float:
    """Backward-compatible wrapper around generalized reliability scoring."""
    return compute_baseline_reliability_score_legacy(
        average_confidence, total_events, romania_events, severity_distribution
    )


def _shape_source_rows(rows: list[dict]) -> list[dict]:
    """Map raw aggregation rows from by_source() to shaped dicts with reliability_score."""
    shaped = []
    for r in rows:
        total = int(r["total_events"])
        romania = int(r.get("romania_events", 0))
        avg_conf = _r(r.get("average_confidence"), 3)
        sev_dist = {
            "low": int(r.get("sev_low", 0)),
            "medium": int(r.get("sev_medium", 0)),
            "high": int(r.get("sev_high", 0)),
            "critical": int(r.get("sev_critical", 0)),
        }
        shaped.append({
            "source": r["_id"],
            "total_events": total,
            "romania_events": romania,
            "average_confidence": avg_conf,
            "severity_distribution": sev_dist,
            "reliability_score": _reliability_score(avg_conf, total, romania, sev_dist),
        })
    return shaped


def _alert_severity(total_romania: int) -> str:
    """Map a total Romania event count to an alert severity label."""
    if total_romania > 80:
        return "critical"
    if total_romania > 40:
        return "high"
    if total_romania > 15:
        return "medium"
    return "low"


# Deterministic messages for the reliability alert type, keyed by severity.
_RELIABILITY_MESSAGES: dict[str, str] = {
    "low": (
        "FIRMS source reliability elevated: low-level fire detections observed in Romania."
    ),
    "medium": (
        "FIRMS source reliability elevated: moderate fire detections observed in Romania."
    ),
    "high": (
        "FIRMS source reliability elevated: high-density wildfire signal over Romania."
    ),
    "critical": (
        "FIRMS source reliability elevated: critical wildfire detections confirmed in Romania."
    ),
}


def _alert_message(
    alert_type: str, severity: str, sources_with_events: list[str]
) -> str:
    """Return a deterministic human-readable alert message.

    ``alert_type`` must be ``"volume"`` or ``"reliability"``.
    """
    if alert_type == "reliability":
        return _RELIABILITY_MESSAGES.get(
            severity,
            "FIRMS source reliability elevated: fire detections observed in Romania.",
        )

    # volume
    has_firms = _FIRMS_SOURCE in sources_with_events
    has_csv = "CSV" in sources_with_events
    if severity == "critical":
        return (
            "Critical fire activity alert: sustained high-confidence detections in Romania."
        )
    if severity == "high":
        return "High confidence wildfire signal cluster detected in Romanian territory."
    if severity == "medium":
        if has_firms and has_csv:
            return (
                "Moderate fire activity detected in Romania based on FIRMS + CSV convergence."
            )
        return "Moderate fire activity detected in Romania."
    # low
    if has_firms:
        return "Low fire activity detected in Romania based on satellite monitoring."
    return "Low fire activity detected in Romania."


def _evaluate_alerts(
    source_data: list[dict],
    *,
    in_scope_event_count: int | None = None,
) -> list[dict]:
    """Apply heuristic alert rules to shaped source statistics.

    Returns a list of **up to two** explicitly-typed alerts:

    ``"volume"`` — emitted when the combined Romania event count across all
        sources exceeds 10.  Confidence and reliability are aggregated across
        all sources (weighted avg confidence, max reliability score).

    ``"reliability"`` — emitted when FIRMS reliability_score > 0.65 **and**
        FIRMS contributes more than 30 % of all ingested events.  Confidence
        and reliability reflect FIRMS exclusively, since it is the sole
        trigger for this condition.

    Both alerts may appear simultaneously when both conditions are satisfied.
    Severity is computed independently for each alert via _alert_severity
    applied to the shared total_romania count.
    """
    if not source_data:
        return []

    total_events = sum(s["total_events"] for s in source_data)
    total_romania = sum(s["romania_events"] for s in source_data)
    volume_count = total_romania if in_scope_event_count is None else in_scope_event_count

    firms = next((s for s in source_data if s["source"] == _FIRMS_SOURCE), None)
    firms_events = firms["total_events"] if firms else 0
    firms_reliability = firms["reliability_score"] if firms else 0.0
    firms_share = firms_events / max(total_events, 1)

    severity = _alert_severity(volume_count)
    sources_with_events = [s["source"] for s in source_data if s["romania_events"] > 0]
    source_breakdown = {s["source"]: s["romania_events"] for s in source_data}

    # Weighted average confidence and max reliability — used by the volume alert.
    avg_conf = (
        _r(
            sum(s["average_confidence"] * s["total_events"] for s in source_data)
            / total_events,
            3,
        )
        if total_events > 0
        else 0.0
    )
    best_reliability = max(s["reliability_score"] for s in source_data)

    alerts: list[dict] = []

    # A. Volume-based alert
    if volume_count > 10:
        alerts.append(
            {
                "type": "volume",
                "severity": severity,
                "confidence": avg_conf,
                "reliability_score": best_reliability,
                "source_breakdown": source_breakdown,
                "message": _alert_message("volume", severity, sources_with_events),
            }
        )

    # B. Reliability-based alert — FIRMS-specific trigger isolated in source_reliability.
    if firms_reliability_alert_trigger(source_data):
        firms_conf = _r(firms["average_confidence"], 3) if firms else avg_conf
        alerts.append(
            {
                "type": "reliability",
                "severity": severity,
                "confidence": firms_conf,
                "reliability_score": firms_reliability,
                "source_breakdown": source_breakdown,
                "message": _alert_message("reliability", severity, sources_with_events),
            }
        )

    return alerts


# ---------------------------------------------------------------------------
# Temporal trend computation — pure function (no I/O)
# ---------------------------------------------------------------------------

def _compute_temporal_trend(
    last_24h: int,
    last_7d: int,
    previous_7d: int,
) -> dict:
    """Compute the Romania trend summary from pre-fetched window counts.

    ``change_percent`` measures how the current 7-day window compares to the
    preceding 7-day window:

        change = (last_7d - previous_7d) / previous_7d * 100

    Edge cases:
        previous_7d == 0, last_7d == 0  → change = 0.0  (stable)
        previous_7d == 0, last_7d  > 0  → change = 100.0 (increasing)

    Trend classification uses strict inequalities:
        change > 10   → "increasing"
        change < -10  → "decreasing"
        otherwise     → "stable"
    """
    if previous_7d == 0:
        change_percent = 0.0 if last_7d == 0 else 100.0
    else:
        change_percent = _r((last_7d - previous_7d) / previous_7d * 100, 2)

    if change_percent > 10:
        trend = "increasing"
    elif change_percent < -10:
        trend = "decreasing"
    else:
        trend = "stable"

    return {
        "last_24h": {"romania_events": last_24h},
        "last_7d": {"romania_events": last_7d},
        "previous_7d": {"romania_events": previous_7d},
        "change_percent": change_percent,
        "trend": trend,
    }


# ---------------------------------------------------------------------------
# Regional baseline computation — pure functions (no I/O)
# ---------------------------------------------------------------------------

def _compute_deviation(current_events: int, baseline_events: int) -> float:
    """Return deviation_percent according to the spec rules.

        baseline == 0, current == 0  →   0.0
        baseline == 0, current  > 0  → 100.0
        otherwise                    → (current - baseline) / baseline * 100
    """
    if baseline_events == 0:
        return 0.0 if current_events == 0 else 100.0
    return _r((current_events - baseline_events) / baseline_events * 100, 2)


# Forest confidence weights — kept here alongside the anomaly evaluation logic
# so the enrichment stays co-located with consumption.
_FOREST_CONFIDENCE_WEIGHTS: dict[str, float] = {
    "forest": 1.00,
    "near_forest": 0.75,
    "agriculture": 0.40,
    "urban": 0.20,
    "water": 0.10,
    "unknown": 0.50,
}


def _compute_forest_confidence(row: dict) -> float:
    """Derive a region-level forest_confidence from land-cover event counts.

    Each land-cover bucket (``lc_forest``, ``lc_near_forest``, …) is multiplied
    by its confidence weight; the weighted sum is divided by the total counted
    events.  Regions where no events carry a ``land_cover_type`` field (legacy
    data) return the ``"unknown"`` default weight (0.50).
    """
    lc_keys = list(_FOREST_CONFIDENCE_WEIGHTS.keys())
    lc_counts = {lc: int(row.get(f"lc_{lc}", 0)) for lc in lc_keys}
    total = sum(lc_counts.values())
    if total == 0:
        return _FOREST_CONFIDENCE_WEIGHTS["unknown"]
    weighted = sum(count * _FOREST_CONFIDENCE_WEIGHTS[lc] for lc, count in lc_counts.items())
    return _r(weighted / total, 4)


def _compute_baselines(
    rows: list[dict],
    generated_at: datetime,
    *,
    include_incident_category: bool = True,
) -> dict:
    """Shape raw aggregation rows into the regional baselines response.

    ``baseline_events`` is derived from ``baseline_raw`` (total events in the
    preceding 28 days) divided by 4 (number of weeks) then rounded to the
    nearest integer, consistent with the ``int`` type in the response schema.

    Rows are segmented by ``(region, incident_category)``. When
    ``include_incident_category`` is ``False``, shaped rows omit the category
    field so wildfire-only oracle artifacts remain byte-identical.

    Regions are sorted descending by ``deviation_percent`` so the most
    active regions appear first.

    Each region entry includes ``forest_confidence``, computed from the
    land-cover distribution of all events in the 35-day window.
    """
    regions = []
    for row in rows:
        region, incident_category = parse_segment_key(row["_id"])
        current = int(row.get("current_events", 0))
        baseline_raw = int(row.get("baseline_raw", 0))
        baseline_events = round(baseline_raw / 4)
        entry = {
            "region": region,
            "baseline_events": baseline_events,
            "current_events": current,
            "deviation_percent": _compute_deviation(current, baseline_events),
            "forest_confidence": _compute_forest_confidence(row),
        }
        if include_incident_category:
            entry["incident_category"] = incident_category
        regions.append(entry)
    regions.sort(key=lambda r: r["deviation_percent"], reverse=True)
    return {"generated_at": generated_at, "regions": regions}


# ---------------------------------------------------------------------------
# Anomaly detection — pure, rule-based, no ML
# ---------------------------------------------------------------------------


def _evaluate_anomalies(
    regions: list[dict],
    generated_at: datetime,
    *,
    incident_category: str | None = None,
) -> dict:
    """Filter shaped baseline regions for anomaly candidates and score them.

    When ``incident_category`` is set, only rows for that category are
    evaluated. Per-category thresholds apply (WP2.4); wildfire defaults match
    the pre-WP2 constants.

    ``regions`` must already be shaped by ``_compute_baselines`` — i.e. each
    entry must carry ``region``, ``baseline_events``, ``current_events``, and
    ``deviation_percent``.  No database I/O is performed here.

    Returned anomalies are sorted descending by ``anomaly_score``. Legacy
    anomaly dicts omit ``incident_category`` for backward compatibility.
    """
    if incident_category is not None:
        from .segmented_baseline import filter_baseline_regions_for_category

        candidate_regions = filter_baseline_regions_for_category(regions, incident_category)
        thresholds = get_anomaly_thresholds(incident_category)
    else:
        candidate_regions = regions
        thresholds = get_anomaly_thresholds(None)

    min_events = thresholds.min_events
    min_deviation = thresholds.min_deviation_percent

    anomalies: list[dict] = []
    for r in candidate_regions:
        current = r["current_events"]
        deviation = r["deviation_percent"]
        if current < min_events or deviation < min_deviation:
            continue
        baseline = r["baseline_events"]
        score = _compute_anomaly_score(current, baseline, deviation)
        anomalies.append(
            {
                "region": r["region"],
                "baseline_events": baseline,
                "current_events": current,
                "deviation_percent": deviation,
                "anomaly_score": score,
                "severity": _anomaly_severity(score),
                "status": "active",
                # forest_confidence is context-only — anomaly_score is unchanged.
                "forest_confidence": r.get("forest_confidence", _FOREST_CONFIDENCE_WEIGHTS["unknown"]),
            }
        )
    anomalies.sort(key=lambda a: a["anomaly_score"], reverse=True)
    return {"generated_at": generated_at, "anomalies": anomalies}


def _compute_anomaly_score(
    current_events: int,
    baseline_events: int,
    deviation_percent: float,
) -> float:
    """Return a normalised anomaly score in [0.0, 1.0].

    Formula:
        volume_component    = min(current_events / 50, 1.0)
        deviation_component = min(deviation_percent / 200, 1.0)
        score = 0.4 * volume_component + 0.6 * deviation_component

    ``baseline_events`` is accepted as a parameter for future extensibility
    but is not used in the current formula.
    """
    volume_component = min(current_events / 50, 1.0)
    deviation_component = min(deviation_percent / 200, 1.0)
    return _r(0.4 * volume_component + 0.6 * deviation_component, 4)


def _anomaly_severity(score: float) -> str:
    """Classify an anomaly score into a severity label.

    Boundaries use >= (inclusive):
        >= 0.80 → "critical"
        >= 0.60 → "high"
        >= 0.40 → "medium"
              else "low"
    """
    if score >= 0.80:
        return "critical"
    if score >= 0.60:
        return "high"
    if score >= 0.40:
        return "medium"
    return "low"


def _scope_metrics(totals: dict, confidence_rows: list[dict] | None) -> tuple[int, dict[str, int], float]:
    total = int(totals.get("total_events", 0))
    valid_coords = int(totals.get("valid_coords", 0))
    coord_rate = _r(valid_coords / total, 4) if total > 0 else 0.0
    return total, _confidence_distribution(confidence_rows), coord_rate


class AnalyticsService:
    """Shapes raw aggregation results into frontend-ready JSON."""

    def __init__(
        self,
        repo: AnalyticsRepository,
        *,
        correlation_repo: "CorrelationRepository | None" = None,
        cycle_repo: "IntelligenceCycleRepository | None" = None,
    ) -> None:
        self.repo = repo
        self._correlation_repo = correlation_repo
        self._cycle_repo = cycle_repo

    @property
    def geographic_scope(self) -> str:
        return self.repo.scope_policy.scope_value

    def _scope_metadata(self) -> dict[str, str]:
        return {"geographic_scope": self.geographic_scope}

    # ------------------------------------------------------------------ #
    # Overview
    # ------------------------------------------------------------------ #
    async def overview(self) -> dict:
        doc = await self.repo.overview()
        if doc is None:
            return {
                "total_events": 0,
                "total_area_affected": 0.0,
                "open_events": 0,
                "resolved_events": 0,
                "investigating_events": 0,
                "average_confidence": 0.0,
            }
        return {
            "total_events": int(doc.get("total_events", 0)),
            "total_area_affected": _r(doc.get("total_area")),
            "open_events": int(doc.get("open_events", 0)),
            "resolved_events": int(doc.get("resolved_events", 0)),
            "investigating_events": int(doc.get("investigating_events", 0)),
            "average_confidence": _r(doc.get("average_confidence"), 3),
        }

    # ------------------------------------------------------------------ #
    # By country
    # ------------------------------------------------------------------ #
    async def by_country(self) -> list[dict]:
        rows = await self.repo.by_country()
        return [
            {
                "country": r["_id"],
                "event_count": int(r["event_count"]),
                "affected_area_ha": _r(r["affected_area_ha"]),
            }
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    # By event type — always returns ALL taxonomy entries (zero-filled)
    # so charts have a stable axis.
    # ------------------------------------------------------------------ #
    async def by_event_type(self) -> list[dict]:
        rows = await self.repo.by_event_type()
        by_type = {
            r["_id"]: {
                "event_count": int(r["event_count"]),
                "affected_area_ha": _r(r["affected_area_ha"]),
            }
            for r in rows
        }
        out: list[dict] = []
        for et in EVENT_TYPES:
            data = by_type.get(et, {"event_count": 0, "affected_area_ha": 0.0})
            out.append({"event_type": et, **data})
        # Sort by event_count DESC for chart readability
        out.sort(key=lambda x: (-x["event_count"], x["event_type"]))
        return out

    # ------------------------------------------------------------------ #
    # By severity — always returns the 4 buckets, zero-filled
    # ------------------------------------------------------------------ #
    async def by_severity(self) -> dict:
        rows = await self.repo.by_severity()
        by_sev = {
            r["_id"]: {
                "count": int(r["event_count"]),
                "area_ha": _r(r["affected_area_ha"]),
            }
            for r in rows
        }
        return {
            sev: by_sev.get(sev, {"count": 0, "area_ha": 0.0})
            for sev in SEVERITY_ORDER
        }

    # ------------------------------------------------------------------ #
    # Trends — time series
    # ------------------------------------------------------------------ #
    async def trends(
        self, start_date: datetime | None, end_date: datetime | None, interval: str
    ) -> dict:
        if interval not in VALID_INTERVALS:
            raise AppError(
                f"interval must be one of {sorted(VALID_INTERVALS)}",
                status_code=400,
                code="invalid_interval",
            )
        end_utc = ensure_utc(end_date) if end_date else utcnow()
        start_utc = (
            ensure_utc(start_date) if start_date else end_utc - timedelta(days=30)
        )
        if start_utc > end_utc:
            raise AppError(
                "start_date must be earlier than or equal to end_date",
                status_code=400,
                code="invalid_range",
            )
        rows = await self.repo.trends(start_utc, end_utc, interval)
        series = [
            {
                "bucket": r["_id"],
                "event_count": int(r["event_count"]),
                "affected_area_ha": _r(r["affected_area_ha"]),
            }
            for r in rows
        ]
        return {
            "interval": interval,
            "start_date": start_utc,
            "end_date": end_utc,
            "series": series,
        }

    # ------------------------------------------------------------------ #
    # By source — cross-provider comparison
    # ------------------------------------------------------------------ #
    async def source_statistics(self) -> dict:
        """Per-ingestion-source breakdown derived from metadata.ingestion."""
        rows = await self.repo.by_source()
        return {"sources": _shape_source_rows(rows)}

    # ------------------------------------------------------------------ #
    # Intelligence alerts
    # ------------------------------------------------------------------ #
    async def get_alerts(self) -> dict:
        """Apply heuristic alert rules over per-source aggregation data."""
        rows = await self.repo.by_source()
        source_data = _shape_source_rows(rows)
        in_scope_count = None
        if self.geographic_scope != "romania":
            counts = await self.repo.temporal_scoped_counts(utcnow())
            in_scope_count = counts["last_7d"]
        alerts = _evaluate_alerts(source_data, in_scope_event_count=in_scope_count)
        highest = (
            max(alerts, key=lambda a: _SEVERITY_RANK[a["severity"]])["severity"]
            if alerts
            else None
        )
        return {
            "alerts": alerts,
            "summary": {
                "total_alerts": len(alerts),
                "highest_severity": highest,
            },
            **self._scope_metadata(),
        }

    # ------------------------------------------------------------------ #
    # Temporal intelligence — rolling-window Romania trend
    # ------------------------------------------------------------------ #
    async def get_temporal_summary(self) -> dict:
        """Return Romania event counts for three rolling windows and a trend.

        The ``now`` anchor is captured once at call time so all three windows
        are coherent.  Computation is delegated to the pure
        ``_compute_temporal_trend`` helper.
        """
        now = utcnow()
        counts = await self.repo.temporal_scoped_counts(now)
        result = _compute_temporal_trend(
            last_24h=counts["last_24h"],
            last_7d=counts["last_7d"],
            previous_7d=counts["previous_7d"],
        )
        return {**result, **self._scope_metadata()}

    # ------------------------------------------------------------------ #
    # Regional baselines — historical reference per Romanian region
    # ------------------------------------------------------------------ #
    async def get_regional_baselines(self) -> dict:
        """Compute per-region baseline vs. current activity for Romania.

        ``generated_at`` is captured once so the timestamp is coherent with
        the time windows used by the repository query.
        """
        now = utcnow()
        rows = await self.repo.regional_baselines(now)
        baselines = _compute_baselines(rows, generated_at=now)
        return {**baselines, **self._scope_metadata()}

    # ------------------------------------------------------------------ #
    # Persistent intelligence events
    # ------------------------------------------------------------------ #
    async def reconcile_intelligence_events(
        self,
        intelligence_svc: IntelligenceEventsService,
        *,
        intelligence_cycle_id: str | None = None,
    ) -> dict:
        """Run anomaly detection, persist results, resolve stale events.

        Sequence:
          1. Detect current anomalies (same pipeline as get_anomalies()).
          2. Delegate upsert + resolution to IntelligenceEventsService.
          3. Return the full current event inventory via get_events().

        Only one repository call is made for anomaly detection; persistence
        is handled entirely by intelligence_svc.
        """
        now = utcnow()
        rows = await self.repo.regional_baselines(now)
        baselines = _compute_baselines(rows, generated_at=now)
        from .detector_registry import get_detector_registry

        detections = get_detector_registry().detect_all(baselines["regions"], now)
        from app.core.config import get_settings as _get_settings
        from .contextual_detection import supplement_contextual_detections

        settings = _get_settings()
        detections = await supplement_contextual_detections(
            self.repo,
            detections,
            now,
            enabled=getattr(settings, "enable_effis_wildfire_context", False),
        )
        from .disturbance_detection import supplement_disturbance_detections

        detections = await supplement_disturbance_detections(
            self.repo,
            detections,
            now,
            enabled=getattr(settings, "enable_forest_disturbance", False),
        )
        from .intelligence_cycle import detection_fingerprint, resolve_intelligence_cycle_id

        fingerprint = detection_fingerprint(detections)
        cycle_id = resolve_intelligence_cycle_id(intelligence_cycle_id, fingerprint)
        correlation_cycle_id: str | None = None

        if self._correlation_repo is not None:
            from app.core.config import get_settings

            settings = get_settings()
            if settings.enable_cross_source_correlation:
                from .correlation_config import get_correlation_config
                from .cross_source_correlator import CrossSourceCorrelator

                correlator = CrossSourceCorrelator(get_correlation_config())
                correlation_results = correlator.correlate(
                    detections,
                    now,
                    geographic_scope=settings.geographic_scope,
                )
                correlation_cycle_id = cycle_id
                await self._correlation_repo.replace_all(
                    [result.as_dict() for result in correlation_results],
                    intelligence_cycle_id=cycle_id,
                )

        await intelligence_svc.reconcile_detections(detections, now)

        if self._cycle_repo is not None:
            await self._cycle_repo.set_current(
                intelligence_cycle_id=cycle_id,
                detection_fingerprint=fingerprint,
                correlation_cycle_id=correlation_cycle_id,
                reconciled_at=now,
            )

        return await intelligence_svc.get_events()

    # ------------------------------------------------------------------ #
    # Anomaly detection — rule-based, reuses regional baseline aggregation
    # ------------------------------------------------------------------ #
    async def get_anomalies(self) -> dict:
        """Detect unusual Romanian region activity against historical baselines.

        Runs registered detectors (Phase 0: wildfire baseline deviation only) and
        projects results to the legacy anomalies API shape for backward compatibility.
        """
        now = utcnow()
        rows = await self.repo.regional_baselines(now)
        baselines = _compute_baselines(rows, generated_at=now)
        from .detection_adapters import anomalies_response_from_detections
        from .detector_registry import get_detector_registry

        detections = get_detector_registry().detect_all(baselines["regions"], now)
        response = anomalies_response_from_detections(detections, generated_at=now)
        return {**response, **self._scope_metadata()}

    # ------------------------------------------------------------------ #
    # Land-cover distribution
    # ------------------------------------------------------------------ #
    async def get_land_cover_distribution(self) -> dict:
        """Return per-land-cover-type event counts across all events.

        The six accepted labels are: forest, near_forest, agriculture,
        urban, water, unknown.  Events without ``land_cover_type`` are
        counted under ``"unknown"`` (handled by the repository aggregation).

        Returns::

            {
                "generated_at": <datetime>,
                "dataset": {
                    "source": "Copernicus Land Monitoring Service",
                    "version": "2018-Romania-Simplified-v1",
                    "last_updated": "2024-01-01",
                    "feature_count": 50
                },
                "distribution": [
                    {"land_cover": "forest",      "events": 52},
                    {"land_cover": "near_forest",  "events": 31},
                    ...
                ]
            }
        """
        now = utcnow()
        rows = await self.repo.land_cover_distribution()
        distribution = [
            {
                "land_cover": str(r["_id"]) if r.get("_id") else "unknown",
                "events": int(r.get("events", 0)),
            }
            for r in rows
        ]
        try:
            dataset_info = _get_gis_dataset_info()
        except Exception:
            dataset_info = {
                "source": "Copernicus Land Monitoring Service",
                "version": "unknown",
                "last_updated": "unknown",
                "feature_count": 0,
            }
        return {
            "generated_at": now,
            "dataset": dataset_info,
            "distribution": distribution,
        }

    # ------------------------------------------------------------------ #
    # Data quality
    # ------------------------------------------------------------------ #
    async def data_quality(self) -> dict:
        events_doc = await self.repo.data_quality_events()
        import_doc = await self.repo.data_quality_import_totals()

        global_totals = _first_row(events_doc.get("global_totals"))
        romania_totals = _first_row(events_doc.get("romania_totals"))

        total_events = int(global_totals.get("total_events", 0))
        romania_events = int(romania_totals.get("total_events", 0))

        _, global_confidence, global_coord_rate = _scope_metrics(
            global_totals,
            events_doc.get("global_confidence"),
        )
        _, romania_confidence, romania_coord_rate = _scope_metrics(
            romania_totals,
            events_doc.get("romania_confidence"),
        )

        # Romania-first metrics with global fallback when no Romania events match.
        if romania_events > 0:
            confidence_distribution = romania_confidence
            coordinate_validity_rate = romania_coord_rate
        else:
            confidence_distribution = global_confidence
            coordinate_validity_rate = global_coord_rate

        total_attempts = 0
        skipped_count = 0
        if import_doc:
            total_attempts = int(import_doc.get("total_attempts", 0))
            skipped_count = int(import_doc.get("skipped_count", 0))

        duplicate_prevention_rate = (
            _r(skipped_count / total_attempts, 4) if total_attempts > 0 else 0.0
        )

        return {
            "total_events": total_events,
            "romania_events": romania_events,
            "duplicate_prevention_rate": duplicate_prevention_rate,
            "confidence_distribution": confidence_distribution,
            "coordinate_validity_rate": coordinate_validity_rate,
        }

    # ------------------------------------------------------------------ #
    # Ecosystem intelligence — aliases and aggregation
    # ------------------------------------------------------------------ #
    async def get_overview(self) -> dict:
        """Alias for :meth:`overview` used by the reports module."""
        return await self.overview()

    async def get_incident_aggregation(self) -> dict:
        """Cross-domain incident rollup via the pluggable aggregation registry."""
        from .incident_aggregation import get_incident_aggregation_registry

        registry = get_incident_aggregation_registry()
        return await registry.aggregate_all(self)
