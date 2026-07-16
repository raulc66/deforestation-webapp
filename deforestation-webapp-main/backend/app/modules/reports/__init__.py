"""Operational Reporting module for ForestWatch.

Provides daily, weekly, monthly, and on-demand reports in PDF, CSV, and JSON
formats.  Reports are generated asynchronously, stored on disk, and metadata
persisted in MongoDB.
"""
from . import report_models, report_repository, report_service  # noqa: F401


def module_info() -> dict:
    return {
        "module": "reports",
        "status": "active",
        "capabilities": {
            "pdf_reports": "live",
            "csv_exports": "live",
            "json_exports": "live",
            "scheduled_reports": "live",
            "modular_sections": "live",
        },
        "endpoints": [
            "GET  /api/reports",
            "GET  /api/reports/{id}",
            "POST /api/reports/generate",
            "DELETE /api/reports/{id}",
            "GET  /api/reports/{id}/download",
        ],
    }
