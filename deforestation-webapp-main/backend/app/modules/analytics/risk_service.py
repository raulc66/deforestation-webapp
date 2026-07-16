"""Fire Risk Assessment Engine — deterministic, weather-enriched, no ML.

Pure helpers (no I/O, independently testable):
    compute_risk_score(inputs)     → float in [0.0, 1.0]
    compute_risk_level(score)      → "Low" | "Moderate" | "High" | "Extreme"
    compute_risk_breakdown(inputs) → per-component weighted contributions

RiskService:
    compute_regional_risk()  — assemble data, score every region, attach change
    persist_snapshot()       — compute + store one snapshot per UTC day
    get_risk()               — compute and return current risk (not persisted)

Architecture notes
------------------
* ``RiskService`` consumes existing services — it does NOT duplicate anomaly or
  priority calculations.  It calls ``AnalyticsService.get_anomalies()`` and
  ``AnalyticsService.get_regional_baselines()`` in parallel via asyncio.gather.
* All six risk inputs are individually normalised to [0, 1] before weighting.
* The formula is additive and sums to exactly 1.0 when all inputs are 1.0
  (0.30 + 0.20 + 0.15 + 0.10 + 0.10 + 0.15 = 1.00).
* ``change`` indicators compare the current score to the most-recent stored
  snapshot so the dashboard card can show ↑ / ↓ / stable without an extra call.

Risk formula weights (v2 — weather enriched)
--------------------------------------------
    current_activity    30 %  — anomaly_score from anomaly detection
    historical_activity 20 %  — events_last_30d normalised by regional max
    forest              15 %  — forest_confidence from land-cover classification
    weather             15 %  — fire-weather sub-score (temp / humidity / wind / rain)
    priority            10 %  — priority_score from active intelligence events
    escalation          10 %  — escalation level: normal=0, persistent=0.5, critical=1

Weather sub-score thresholds
-----------------------------
    Temperature:    0°C → 0.0,   40°C → 1.0   (higher = more fire-prone)
    Humidity:     100% → 0.0,     0% → 1.0   (drier = more fire-prone)
    Wind speed:   0 km/h → 0.0, 80 km/h → 1.0
    Precipitation: 0 mm → 1.0,  20 mm → 0.0   (rain reduces risk)

When weather data is unavailable the input defaults to 0.5 (neutral), which
corresponds to mild, average conditions with no bias toward either extreme.

Risk levels
-----------
    [0.00, 0.25) → Low
    [0.25, 0.50) → Moderate
    [0.50, 0.75) → High
    [0.75, 1.00] → Extreme
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.models.base import utcnow

from .risk_repository import RiskRepository

if TYPE_CHECKING:
    from .analytics_service import AnalyticsService
    from .intelligence_events_repository import IntelligenceEventsRepository
    from ..analytics.history_repository import HistoryRepository
    from app.services.weather_service import WeatherService

logger = logging.getLogger("forestwatch.risk")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RISK_WEIGHTS: dict[str, float] = {
    "current_activity":    0.30,
    "historical_activity": 0.20,
    "forest":              0.15,
    "weather":             0.15,
    "priority":            0.10,
    "escalation":          0.10,
}

ESCALATION_SCORES: dict[str, float] = {
    "normal":     0.0,
    "persistent": 0.5,
    "critical":   1.0,
}

# Threshold for "up" / "down" classification (±0.02 = 2 pp change).
_CHANGE_THRESHOLD = 0.02

# Neutral weather score used when no live data is available for a region.
_NEUTRAL_WEATHER = 0.5

# ---------------------------------------------------------------------------
# Pure helpers — no I/O, no FastAPI, no MongoDB
# ---------------------------------------------------------------------------


def compute_risk_score(inputs: dict) -> float:
    """Compute the weighted risk score from normalised inputs.

    Each input must be in [0.0, 1.0].  The result is clamped and rounded to
    four decimal places.  Missing keys default to 0.0.

    Parameters
    ----------
    inputs:
        Mapping with keys from ``RISK_WEIGHTS``.  ``weather`` defaults to 0.0
        when not supplied (callers that use live weather always include it).

    Returns
    -------
    float in [0.0000, 1.0000]
    """
    raw = sum(
        inputs.get(key, 0.0) * weight
        for key, weight in RISK_WEIGHTS.items()
    )
    return round(min(max(raw, 0.0), 1.0), 4)


def compute_risk_level(score: float) -> str:
    """Classify a risk score into a named level.

    Boundaries (inclusive lower, exclusive upper):
        [0.75, 1.00] → Extreme
        [0.50, 0.75) → High
        [0.25, 0.50) → Moderate
        [0.00, 0.25) → Low
    """
    if score >= 0.75:
        return "Extreme"
    if score >= 0.50:
        return "High"
    if score >= 0.25:
        return "Moderate"
    return "Low"


def compute_risk_breakdown(inputs: dict) -> dict:
    """Return per-component weighted contributions to the risk score.

    The values in the returned dict sum to ``compute_risk_score(inputs)``.

    Returns
    -------
    dict with keys: current_activity, historical_activity, forest,
                    weather, priority, escalation
    """
    return {
        key: round(inputs.get(key, 0.0) * weight, 4)
        for key, weight in RISK_WEIGHTS.items()
    }


def _escalation_score(level: str | None) -> float:
    """Map an escalation level string to a numeric [0, 1] score."""
    return ESCALATION_SCORES.get(level or "normal", 0.0)


def _change_label(current: float, previous: float | None) -> str:
    """Classify the change between snapshot scores."""
    if previous is None:
        return "new"
    delta = current - previous
    if delta > _CHANGE_THRESHOLD:
        return "up"
    if delta < -_CHANGE_THRESHOLD:
        return "down"
    return "stable"


# ---------------------------------------------------------------------------
# RiskService
# ---------------------------------------------------------------------------


class RiskService:
    """Assembles regional fire risk scores from existing intelligence data.

    Optionally enriches each region's risk inputs with live weather data when
    a ``WeatherService`` instance is provided.
    """

    def __init__(
        self,
        analytics_svc: AnalyticsService,
        history_repo: HistoryRepository,
        intel_events_repo: IntelligenceEventsRepository,
        risk_repo: RiskRepository,
        *,
        weather_svc: WeatherService | None = None,
    ) -> None:
        self._analytics = analytics_svc
        self._history = history_repo
        self._intel = intel_events_repo
        self._risk_repo = risk_repo
        self._weather_svc = weather_svc

    async def compute_regional_risk(self) -> dict:
        """Assemble risk inputs from all sources and compute per-region scores.

        Data fetched in parallel (single asyncio.gather):
            • anomaly scores + forest confidence (AnalyticsService)
            • regional baselines for non-anomalous region coverage
            • historical activity (HistoryRepository)
            • active intelligence events for priority + escalation
            • latest stored snapshot for change indicators
            • weather data from cache (WeatherService, if available)

        Returns
        -------
        dict::

            {
                "generated_at": datetime,
                "regions": [
                    {
                        "region":     str,
                        "risk_score": float,
                        "risk_level": str,
                        "change":     str,
                        "breakdown":  {...}
                    },
                    ...   (sorted descending by risk_score)
                ]
            }
        """
        now = utcnow()

        # Build gather tasks — weather is optional
        gather_tasks = [
            self._analytics.get_anomalies(),
            self._analytics.get_regional_baselines(),
            self._history.regional_history(now),
            self._intel.find_active(),
            self._risk_repo.latest(),
        ]

        (
            anomalies_result,
            baselines_result,
            history_rows,
            active_events,
            latest_snapshot,
        ) = await asyncio.gather(*gather_tasks)

        # Weather data: {region: weather_dict} — empty dict when not available
        if self._weather_svc is not None:
            try:
                weather_by_region: dict[str, dict] = await self._weather_svc.get_weather_by_region()
            except Exception:
                logger.warning("Weather data unavailable — using neutral score")
                weather_by_region = {}
        else:
            weather_by_region = {}

        # ------------------------------------------------------------------
        # Build lookup tables
        # ------------------------------------------------------------------
        anomaly_by_region: dict[str, dict] = {
            a["region"]: a for a in anomalies_result.get("anomalies", [])
        }

        baselines_by_region: dict[str, dict] = {
            r["region"]: r for r in baselines_result.get("regions", [])
        }

        hist_raw: dict[str, int] = {
            str(r["_id"]): int(r.get("events_last_30d", 0))
            for r in history_rows
            if r.get("_id")
        }
        max_hist = max(hist_raw.values(), default=1) or 1

        intel_by_region: dict[str, dict] = {}
        for evt in active_events:
            region = evt.get("region", "Unknown")
            if (
                region not in intel_by_region
                or evt.get("priority_score", 0.0) > intel_by_region[region].get("priority_score", 0.0)
            ):
                intel_by_region[region] = evt

        prev_scores: dict[str, float] = {
            r["region"]: float(r["risk_score"])
            for r in (latest_snapshot or {}).get("regions", [])
        } if latest_snapshot else {}

        # ------------------------------------------------------------------
        # Compute risk for every known region
        # ------------------------------------------------------------------
        all_regions: set[str] = (
            set(anomaly_by_region.keys())
            | set(baselines_by_region.keys())
            | set(hist_raw.keys())
        )

        from app.services.weather_service import compute_weather_score

        results: list[dict] = []
        for region in all_regions:
            anomaly = anomaly_by_region.get(region, {})
            baseline = baselines_by_region.get(region, {})
            intel = intel_by_region.get(region, {})

            forest_conf = float(
                anomaly.get("forest_confidence")
                or baseline.get("forest_confidence")
                or 0.5
            )

            # Weather score: use live data when available, else neutral
            wx = weather_by_region.get(region)
            if wx:
                weather_input = compute_weather_score(
                    temperature=wx.get("temperature", 15.0),
                    humidity=wx.get("humidity", 60.0),
                    wind_speed=wx.get("wind_speed", 0.0),
                    precipitation=wx.get("precipitation", 0.0),
                )
            else:
                weather_input = _NEUTRAL_WEATHER

            inputs: dict[str, float] = {
                "current_activity":    float(anomaly.get("anomaly_score", 0.0)),
                "historical_activity": hist_raw.get(region, 0) / max_hist,
                "forest":              forest_conf,
                "weather":             weather_input,
                "priority":            float(intel.get("priority_score", 0.0)),
                "escalation":          _escalation_score(intel.get("escalation_level")),
            }

            score = compute_risk_score(inputs)
            results.append(
                {
                    "region":     region,
                    "risk_score": score,
                    "risk_level": compute_risk_level(score),
                    "change":     _change_label(score, prev_scores.get(region)),
                    "breakdown":  compute_risk_breakdown(inputs),
                }
            )

        results.sort(key=lambda r: r["risk_score"], reverse=True)
        return {"generated_at": now, "regions": results}

    async def persist_snapshot(self) -> dict:
        """Compute risk and persist a daily snapshot (idempotent within UTC day)."""
        risk_data = await self.compute_regional_risk()
        snapshot = {
            "generated_at": risk_data["generated_at"].isoformat()
            if hasattr(risk_data["generated_at"], "isoformat")
            else str(risk_data["generated_at"]),
            "regions": risk_data["regions"],
        }
        return await self._risk_repo.create_snapshot(snapshot)

    async def get_risk(self) -> dict:
        """Compute and return current risk without persisting a snapshot."""
        return await self.compute_regional_risk()
