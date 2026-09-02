"""Deterministic multi-region operational validation report (fixture validation only).

Distinguishes fixture-based validation from live external-service validation.
Does not claim real-world provider availability.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fixtures.multi_region_operational_fixture import build_multi_region_events, events_in_scope

REPORT_FILENAME = "MULTI_REGION_VALIDATION_REPORT.json"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def build_validation_report() -> dict[str, Any]:
    """Assemble a deterministic report documenting validated dimensions."""
    events = build_multi_region_events()
    europe_countries = sorted(
        {e["country"] for e in events_in_scope(events, "europe")}
    )
    return {
        "report_id": "multi-region-operational-validation-v1",
        "validation_mode": "fixture",
        "live_external_validation": False,
        "geographic_scope_tested": ["romania", "europe", "all"],
        "countries_in_fixture": sorted({e["country"] for e in events}),
        "countries_in_europe_scope": europe_countries,
        "providers_tested": [
            "nasa.firms",
            "eea.air_quality",
            "cems.rapid_mapping",
        ],
        "contextual_sources": ["clms.corine_land_cover", "open_meteo"],
        "provider_failure_scenarios": [
            "all_success",
            "firms_failure",
            "eea_failure",
            "cems_failure",
            "all_failure",
        ],
        "correlation_rules": [
            {
                "rule": "firms_cems_wildfire_support",
                "max_spatial_km": 50,
                "max_temporal_hours": 72,
                "cases": ["positive", "spatial_negative", "temporal_negative"],
            },
            {
                "rule": "firms_eea_contextual",
                "max_spatial_km": 30,
                "max_temporal_hours": 48,
                "cases": ["positive", "spatial_negative", "temporal_negative"],
            },
            {
                "rule": "eea_cems_multi_source",
                "max_spatial_km": 40,
                "max_temporal_hours": 48,
                "cases": ["positive", "spatial_negative", "temporal_negative"],
            },
        ],
        "evidence_states_tested": [
            "single_source",
            "multi_source",
            "contextual_support",
            "degraded_source",
            "unavailable",
        ],
        "correlation_states_tested": [
            "current",
            "stale",
            "unavailable",
            "disabled",
        ],
        "eea_safety_bounds_verified": {
            "query_window_hours_bounded": True,
            "max_parsed_rows": 50000,
            "live_failure_not_fixture_fallback": True,
            "credential_stripping": True,
        },
        "phase0_oracle_preserved": True,
        "map_endpoints": [
            "/api/events/map",
            "/api/analytics/intelligence/map-overlay",
        ],
    }


def report_json_text(report: dict[str, Any] | None = None) -> str:
    doc = report if report is not None else build_validation_report()
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def report_sha256(report: dict[str, Any] | None = None) -> str:
    return hashlib.sha256(report_json_text(report).encode("utf-8")).hexdigest()


def golden_report_path() -> Path:
    return GOLDEN_DIR / REPORT_FILENAME


def verify_report_matches_golden() -> None:
    """Raise AssertionError if report drifts from committed golden artifact."""
    path = golden_report_path()
    expected_text = path.read_text(encoding="utf-8")
    actual_text = report_json_text()
    if actual_text != expected_text:
        raise AssertionError(
            "MULTI_REGION_VALIDATION_REPORT.json drifted — update golden only if "
            "validation scope intentionally changed (never modify Phase 0 oracle)."
        )
