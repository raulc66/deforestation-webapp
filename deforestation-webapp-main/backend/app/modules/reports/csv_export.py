"""CSV export generator for ForestWatch reports.

Produces a machine-readable CSV with multiple sections separated by blank
lines and section-header comments.

Entry point: ``generate_report_csv(report_data, output_path)``
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("forestwatch.reports.csv")


def _safe(val: Any, default: str = "") -> str:
    if val is None:
        return default
    if isinstance(val, datetime):
        if val.tzinfo is None:
            val = val.replace(tzinfo=timezone.utc)
        return val.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(val)


def _write_section(writer: "csv.writer", title: str, headers: list[str], rows: list[list]) -> None:
    writer.writerow([])
    writer.writerow([f"# {title}"])
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_safe(cell) for cell in row])


def generate_report_csv(report_data: dict, output_path: str) -> None:
    """Write a CSV export of *report_data* to *output_path*.

    Args:
        report_data: Dict returned by ``ReportService.gather_report_data``.
        output_path: Absolute or relative filesystem path for the CSV file.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")

    # ── Meta header ──────────────────────────────────────────────────────
    writer.writerow(["# ForestWatch Intelligence Report — CSV Export"])
    writer.writerow([f"# Period: {_safe(report_data.get('period_start'))} to {_safe(report_data.get('period_end'))}"])
    writer.writerow([f"# Generated: {_safe(report_data.get('generated_at'))}"])
    writer.writerow([f"# Type: {report_data.get('report_type', 'on_demand')}"])

    # ── 1. Overview ───────────────────────────────────────────────────────
    overview = report_data.get("overview") or {}
    _write_section(writer, "OVERVIEW", ["metric", "value"], [
        ["total_events",        overview.get("total_events", 0)],
        ["open_events",         overview.get("open_events", 0)],
        ["resolved_events",     overview.get("resolved_events", 0)],
        ["average_confidence",  overview.get("average_confidence", 0)],
    ])

    # ── 2. Intelligence Events ────────────────────────────────────────────
    events = report_data.get("intelligence_events") or {}
    active_list = events.get("active", [])
    _write_section(writer, "ACTIVE INTELLIGENCE EVENTS",
        ["region", "event_type", "severity", "escalation_level", "trend", "priority_score", "detection_count"],
        [
            [
                e.get("region"),
                e.get("event_type", e.get("type")),
                e.get("severity"),
                e.get("escalation_level"),
                e.get("trend"),
                e.get("priority_score", e.get("priority")),
                e.get("detection_count"),
            ]
            for e in active_list
        ],
    )

    resolved_list = events.get("resolved", [])
    _write_section(writer, "RESOLVED INTELLIGENCE EVENTS",
        ["region", "event_type", "severity", "priority_score"],
        [
            [
                e.get("region"),
                e.get("event_type", e.get("type")),
                e.get("severity"),
                e.get("priority_score", e.get("priority")),
            ]
            for e in resolved_list
        ],
    )

    # ── 3. Regional Risk ──────────────────────────────────────────────────
    risk = report_data.get("risk") or {}
    regions = risk.get("regions", [])
    _write_section(writer, "REGIONAL RISK",
        ["region", "risk_score", "risk_level", "anomaly_count"],
        [
            [
                r.get("region"),
                r.get("risk_score"),
                r.get("risk_level"),
                r.get("anomaly_count"),
            ]
            for r in regions
        ],
    )

    # ── 4. Anomalies ──────────────────────────────────────────────────────
    anomalies_data = report_data.get("anomalies") or {}
    anomalies = anomalies_data.get("anomalies", [])
    _write_section(writer, "ANOMALIES",
        ["region", "anomaly_score", "deviation", "severity", "status"],
        [
            [
                a.get("region"),
                a.get("anomaly_score", a.get("score")),
                a.get("deviation_from_baseline", a.get("deviation")),
                a.get("severity"),
                a.get("status", "active"),
            ]
            for a in anomalies
        ],
    )

    # ── 5. Weather ────────────────────────────────────────────────────────
    weather = report_data.get("weather") or {}
    weather_regions = weather.get("regions", [])
    _write_section(writer, "WEATHER SUMMARY",
        ["region", "temperature_c", "humidity_pct", "wind_speed_kmh", "precipitation_mm", "weather_code", "updated_at"],
        [
            [
                r.get("region"),
                r.get("temperature"),
                r.get("humidity"),
                r.get("wind_speed"),
                r.get("precipitation"),
                r.get("weather_code"),
                r.get("updated_at"),
            ]
            for r in weather_regions
        ],
    )

    # ── 6. Land Cover ─────────────────────────────────────────────────────
    lc = report_data.get("land_cover") or {}
    dist = lc.get("distribution") or lc.get("by_class") or {}
    _write_section(writer, "LAND COVER DISTRIBUTION",
        ["land_cover_type", "event_count"],
        [[k, v] for k, v in dist.items()],
    )

    # ── 7. Historical (daily) ─────────────────────────────────────────────
    daily = report_data.get("daily_activity") or {}
    days = daily.get("days", [])
    _write_section(writer, "DAILY ACTIVITY",
        ["date", "events", "anomalies"],
        [[d.get("date"), d.get("events", 0), d.get("anomalies", 0)] for d in days],
    )

    # ── 8. Regional History ───────────────────────────────────────────────
    reg_hist = report_data.get("regional_history") or []
    _write_section(writer, "REGIONAL HISTORY (30d comparison)",
        ["region", "events_last_30d", "events_previous_30d", "change_percent", "trend"],
        [
            [
                r.get("region"),
                r.get("events_last_30d", 0),
                r.get("events_previous_30d", 0),
                r.get("change_percent", 0),
                r.get("trend"),
            ]
            for r in reg_hist
        ],
    )

    # ── 9. Hotspot Rankings ───────────────────────────────────────────────
    hotspots = report_data.get("hotspots") or []
    _write_section(writer, "HOTSPOT RANKINGS",
        ["rank", "region", "detections", "average_priority", "highest_severity"],
        [
            [i + 1, h.get("region"), h.get("detections"), h.get("average_priority"), h.get("highest_severity")]
            for i, h in enumerate(hotspots)
        ],
    )

    # ── 10. Notifications ─────────────────────────────────────────────────
    notifs = report_data.get("notifications") or []
    _write_section(writer, "NOTIFICATIONS",
        ["provider", "event_type", "region", "success", "error", "sent_at"],
        [
            [
                n.get("provider"),
                n.get("event_type"),
                n.get("region"),
                n.get("success", True),
                n.get("error"),
                n.get("sent_at"),
            ]
            for n in notifs
        ],
    )

    # ── 11. Ingestion Runs ────────────────────────────────────────────────
    runs = report_data.get("ingestion_runs") or []
    _write_section(writer, "INGESTION RUNS",
        ["source", "status", "events_fetched", "events_inserted", "duplicates_skipped", "duration_seconds", "started_at"],
        [
            [
                r.get("source"),
                r.get("status"),
                r.get("events_fetched", 0),
                r.get("events_inserted", 0),
                r.get("duplicates_skipped", 0),
                r.get("duration_seconds"),
                r.get("started_at"),
            ]
            for r in runs
        ],
    )

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        fh.write(buf.getvalue())

    logger.info("CSV report written: %s", output_path)
