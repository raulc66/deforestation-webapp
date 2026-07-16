"""JSON export generator for ForestWatch reports.

Serializes the complete report data payload to a structured JSON file
suitable for third-party integrations.

Entry point: ``generate_report_json(report_data, output_path)``
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("forestwatch.reports.json")


class _ReportEncoder(json.JSONEncoder):
    """JSON encoder that handles datetimes and other non-standard types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            if obj.tzinfo is None:
                obj = obj.replace(tzinfo=timezone.utc)
            return obj.isoformat()
        # bson.ObjectId, etc.
        try:
            return str(obj)
        except Exception:
            return super().default(obj)


def generate_report_json(report_data: dict, output_path: str) -> None:
    """Write a JSON export of *report_data* to *output_path*.

    The output is a single JSON object with top-level sections matching
    the report structure:

    .. code-block:: json

        {
            "meta": { "report_type": ..., "period_start": ..., ... },
            "summary": { ... },
            "overview": { ... },
            "intelligence_events": { "active": [...], "resolved": [...] },
            "risk": { "regions": [...] },
            "anomalies": { "anomalies": [...] },
            "weather": { "regions": [...] },
            "daily_activity": { "days": [...] },
            "regional_history": [...],
            "monthly_summary": { "months": [...] },
            "hotspots": [...],
            "land_cover": { "distribution": {...} },
            "notifications": [...],
            "ingestion_runs": [...]
        }

    Args:
        report_data: Dict returned by ``ReportService.gather_report_data``.
        output_path: Absolute or relative filesystem path for the JSON file.
    """
    payload = {
        "meta": {
            "report_type": report_data.get("report_type", "on_demand"),
            "period_start": report_data.get("period_start"),
            "period_end": report_data.get("period_end"),
            "generated_at": report_data.get("generated_at"),
            "platform": "ForestWatch Intelligence Platform",
            "version": "1.0",
        },
        "summary": report_data.get("summary") or {},
        "overview": report_data.get("overview") or {},
        "intelligence_events": report_data.get("intelligence_events") or {},
        "risk": report_data.get("risk") or {},
        "anomalies": report_data.get("anomalies") or {},
        "weather": report_data.get("weather") or {},
        "daily_activity": report_data.get("daily_activity") or {},
        "regional_history": report_data.get("regional_history") or [],
        "monthly_summary": report_data.get("monthly_summary") or {},
        "hotspots": report_data.get("hotspots") or [],
        "land_cover": report_data.get("land_cover") or {},
        "notifications": report_data.get("notifications") or [],
        "ingestion_runs": report_data.get("ingestion_runs") or [],
    }

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, cls=_ReportEncoder, indent=2, ensure_ascii=False)

    logger.info("JSON report written: %s", output_path)
