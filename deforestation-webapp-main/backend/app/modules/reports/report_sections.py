"""Pluggable report section registry.

Existing report sections are registered at import time.  Future ecosystem
modules register additional sections via :func:`register_report_section` without
modifying :class:`~app.modules.reports.report_service.ReportService`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.reports.report_service import ReportGatherContext


ReportSectionFetcher = Callable[["ReportGatherContext"], Awaitable[object]]


@dataclass(frozen=True)
class ReportSectionSpec:
    key: str
    description: str
    fetcher: ReportSectionFetcher
    ecosystem_domain: str | None = None


class ReportSectionRegistry:
    def __init__(self) -> None:
        self._sections: dict[str, ReportSectionSpec] = {}

    def register(self, spec: ReportSectionSpec) -> None:
        if spec.key in self._sections:
            raise ValueError(f"Report section {spec.key!r} is already registered")
        self._sections[spec.key] = spec

    def list_sections(self) -> list[ReportSectionSpec]:
        return list(self._sections.values())

    def get(self, key: str) -> ReportSectionSpec | None:
        return self._sections.get(key)


_default_registry = ReportSectionRegistry()


def get_report_section_registry() -> ReportSectionRegistry:
    return _default_registry


def register_report_section(spec: ReportSectionSpec) -> None:
    """Public hook for future ecosystem report modules."""
    _default_registry.register(spec)


def _register_builtins(ctx_factory: type) -> None:
    """Register all existing report sections (wildfire / intelligence core)."""

    async def _overview(ctx: "ReportGatherContext") -> object:
        return await ctx.analytics.get_overview()

    async def _anomalies(ctx: "ReportGatherContext") -> object:
        return await ctx.analytics.get_anomalies()

    async def _land_cover(ctx: "ReportGatherContext") -> object:
        return await ctx.analytics.get_land_cover_distribution()

    async def _intel_events(ctx: "ReportGatherContext") -> object:
        return await ctx.intel_svc.get_events()

    async def _risk(ctx: "ReportGatherContext") -> object:
        return await ctx.risk_svc.get_risk()

    async def _daily_activity(ctx: "ReportGatherContext") -> object:
        return await ctx.history_svc.daily_activity(30)

    async def _regional_history(ctx: "ReportGatherContext") -> object:
        return await ctx.history_svc.regional_history()

    async def _hotspots(ctx: "ReportGatherContext") -> object:
        return await ctx.history_svc.hotspot_history()

    async def _monthly_summary(ctx: "ReportGatherContext") -> object:
        return await ctx.history_svc.monthly_summary()

    async def _weather(ctx: "ReportGatherContext") -> object:
        if ctx.weather_svc is None:
            return {"regions": []}
        return await ctx.weather_svc.get_current_weather()

    async def _notifications(ctx: "ReportGatherContext") -> object:
        return await ctx.notif_history_repo.list_recent(50)

    async def _ingestion_runs(ctx: "ReportGatherContext") -> object:
        return await ctx.runs_repo.list_runs(20)

    async def _incident_aggregation(ctx: "ReportGatherContext") -> object:
        return await ctx.analytics.get_incident_aggregation()

    async def _environmental_threat_assessment(ctx: "ReportGatherContext") -> object:
        if ctx.threat_svc is None:
            from app.modules.analytics.threat_assessment_service import ThreatAssessmentService
            svc = ThreatAssessmentService(ctx.intel_svc)
        else:
            svc = ctx.threat_svc
        return await svc.get_threat_assessment_report()

    async def _investigation_summary(ctx: "ReportGatherContext") -> object:
        if ctx.investigation_svc is None:
            return {
                "open_investigations": 0,
                "critical_investigations": 0,
                "average_resolution_time_hours": None,
                "investigations_by_region": {},
                "recent_investigations": [],
            }
        return await ctx.investigation_svc.get_summary_report()

    specs = [
        ReportSectionSpec("overview", "Headline event totals", _overview, "forest_health"),
        ReportSectionSpec("anomalies", "Regional anomaly detections", _anomalies, "forest_health"),
        ReportSectionSpec("land_cover", "Land cover distribution", _land_cover, "forest_health"),
        ReportSectionSpec(
            "intelligence_events",
            "Active and resolved intelligence events",
            _intel_events,
            "forest_health",
        ),
        ReportSectionSpec("risk", "Regional fire risk scores", _risk, "forest_health"),
        ReportSectionSpec("daily_activity", "30-day daily activity", _daily_activity, "forest_health"),
        ReportSectionSpec(
            "regional_history",
            "Regional historical comparison",
            _regional_history,
            "forest_health",
        ),
        ReportSectionSpec("hotspots", "Hotspot rankings", _hotspots, "forest_health"),
        ReportSectionSpec("monthly_summary", "Monthly activity summary", _monthly_summary, "forest_health"),
        ReportSectionSpec("weather", "Regional weather observations", _weather, "environment"),
        ReportSectionSpec("notifications", "Notification delivery history", _notifications),
        ReportSectionSpec("ingestion_runs", "Scheduler ingestion runs", _ingestion_runs),
        ReportSectionSpec(
            "incident_aggregation",
            "Cross-domain incident aggregation",
            _incident_aggregation,
        ),
        ReportSectionSpec(
            "environmental_threat_assessment",
            "Environmental Threat Assessment",
            _environmental_threat_assessment,
        ),
        ReportSectionSpec(
            "investigation_summary",
            "Investigation Summary",
            _investigation_summary,
            "human_activity",
        ),
    ]
    for spec in specs:
        if _default_registry.get(spec.key) is None:
            _default_registry.register(spec)


_builtins_registered = False


def ensure_default_report_sections() -> ReportSectionRegistry:
    global _builtins_registered
    if not _builtins_registered:
        _register_builtins(object)  # ctx type only used for annotations
        _builtins_registered = True
    return _default_registry
