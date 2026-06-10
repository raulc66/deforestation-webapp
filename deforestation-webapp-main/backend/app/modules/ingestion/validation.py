"""Row-level CSV validation for the ingestion module.

Validates the header set and each row's value types/bounds. Returns parsed
canonical values plus a structured error list (no Mongo writes here).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.models.enums import EVENT_TYPES

REQUIRED_COLUMNS: set[str] = {
    "title",
    "country",
    "region",
    "latitude",
    "longitude",
    "event_type",
    "severity",
    "affected_area_ha",
}
OPTIONAL_COLUMNS: set[str] = {"confidence", "detected_at"}
ALL_COLUMNS: set[str] = REQUIRED_COLUMNS | OPTIONAL_COLUMNS

VALID_EVENT_TYPES = set(EVENT_TYPES)
VALID_SEVERITIES = {"low", "medium", "high", "critical"}


@dataclass
class RowError:
    row_number: int
    field: str | None
    message: str
    raw: dict[str, Any] | None = None


@dataclass
class ParsedRow:
    title: str
    country: str
    region: str
    latitude: float
    longitude: float
    event_type: str
    severity: str
    affected_area_ha: float
    confidence: float | None = None
    detected_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Header validation
# --------------------------------------------------------------------------- #
def validate_header(headers: list[str]) -> list[str]:
    """Return a list of missing-required-column messages (empty if OK)."""
    header_set = {h.strip().lower() for h in headers if h}
    missing = REQUIRED_COLUMNS - header_set
    return [f"Missing required column: '{c}'" for c in sorted(missing)]


# --------------------------------------------------------------------------- #
# Field parsers (single source of truth for value coercion + bounds)
# --------------------------------------------------------------------------- #
def _parse_float(value: str, field_name: str, lo: float | None, hi: float | None) -> tuple[float | None, str | None]:
    if value is None or value.strip() == "":
        return None, f"'{field_name}' is required"
    try:
        v = float(value)
    except ValueError:
        return None, f"'{field_name}' must be a number (got '{value}')"
    if lo is not None and v < lo:
        return None, f"'{field_name}' must be >= {lo} (got {v})"
    if hi is not None and v > hi:
        return None, f"'{field_name}' must be <= {hi} (got {v})"
    return v, None


def _parse_string(value: str, field_name: str) -> tuple[str | None, str | None]:
    if value is None or value.strip() == "":
        return None, f"'{field_name}' is required"
    return value.strip(), None


def _parse_choice(value: str, field_name: str, choices: set[str]) -> tuple[str | None, str | None]:
    if value is None or value.strip() == "":
        return None, f"'{field_name}' is required"
    v = value.strip().lower()
    if v not in choices:
        sample = ", ".join(sorted(choices))
        return None, f"'{field_name}' must be one of [{sample}] (got '{value}')"
    return v, None


def _parse_datetime(value: str, field_name: str) -> tuple[datetime | None, str | None]:
    if value is None or value.strip() == "":
        return None, None  # optional
    raw = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None, f"'{field_name}' must be ISO 8601 datetime (got '{value}')"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc), None


# --------------------------------------------------------------------------- #
# Row validation
# --------------------------------------------------------------------------- #
def validate_row(row_number: int, row: dict[str, str]) -> tuple[ParsedRow | None, list[RowError]]:
    """Return (parsed_row, errors). Errors is empty when parsing succeeded."""
    errors: list[RowError] = []
    norm = {(k or "").strip().lower(): (v if v is not None else "") for k, v in row.items()}

    def add(field_name: str | None, message: str) -> None:
        errors.append(RowError(row_number=row_number, field=field_name, message=message, raw=row))

    title, err = _parse_string(norm.get("title", ""), "title")
    if err:
        add("title", err)
    country, err = _parse_string(norm.get("country", ""), "country")
    if err:
        add("country", err)
    region, err = _parse_string(norm.get("region", ""), "region")
    if err:
        add("region", err)
    lat, err = _parse_float(norm.get("latitude", ""), "latitude", -90.0, 90.0)
    if err:
        add("latitude", err)
    lng, err = _parse_float(norm.get("longitude", ""), "longitude", -180.0, 180.0)
    if err:
        add("longitude", err)
    event_type, err = _parse_choice(norm.get("event_type", ""), "event_type", VALID_EVENT_TYPES)
    if err:
        add("event_type", err)
    severity, err = _parse_choice(norm.get("severity", ""), "severity", VALID_SEVERITIES)
    if err:
        add("severity", err)
    area, err = _parse_float(norm.get("affected_area_ha", ""), "affected_area_ha", 0.0, None)
    if err:
        add("affected_area_ha", err)

    confidence: float | None = None
    if (norm.get("confidence") or "").strip():
        confidence, err = _parse_float(norm["confidence"], "confidence", 0.0, 1.0)
        if err:
            add("confidence", err)

    detected_at, err = _parse_datetime(norm.get("detected_at", ""), "detected_at")
    if err:
        add("detected_at", err)

    if errors:
        return None, errors

    return (
        ParsedRow(
            title=title,
            country=country,
            region=region,
            latitude=lat,
            longitude=lng,
            event_type=event_type,
            severity=severity,
            affected_area_ha=area,
            confidence=confidence,
            detected_at=detected_at,
        ),
        [],
    )
