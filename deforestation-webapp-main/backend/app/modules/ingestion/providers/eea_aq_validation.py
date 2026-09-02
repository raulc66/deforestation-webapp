"""EEA E2a/UTD measurement validation — based on official parquet schema semantics."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.core.ecosystem.air_quality_constants import (
    EEA_MISSING_VALUE,
    is_missing_value,
    normalize_pollutant,
    normalize_unit,
)

# EEA observation validity values that indicate an invalid measurement.
_INVALID_VALIDITY = frozenset(
    {
        "notvalid",
        "not valid",
        "invalid",
        "-1",
        "0",
        "false",
    }
)

_GUID_PATTERN = re.compile(
    r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$"
)


class EEAAQValidationError(ValueError):
    """Raised when an EEA row fails validation."""


class EEAAQAuthenticationError(RuntimeError):
    """Raised when EEA token validation fails."""


def is_valid_eea_token_format(token: str) -> bool:
    """Operator tokens are GUID-shaped per EEA UTD documentation."""
    return bool(token and _GUID_PATTERN.match(token.strip()))


def sanitize_error_message(message: str, token: str | None = None) -> str:
    """Strip token material from exception/log strings."""
    if not message:
        return message
    cleaned = message
    if token:
        cleaned = cleaned.replace(token, "[REDACTED]")
    return cleaned


def _normalize_validity(raw: Any) -> str:
    return str(raw or "").strip().lower()


def is_validity_acceptable(raw: Any) -> bool:
    label = _normalize_validity(raw)
    if not label:
        return True
    return label not in _INVALID_VALIDITY


def parse_observed_at(raw: Any) -> datetime:
    """Parse EEA Start/End timestamp to UTC."""
    if isinstance(raw, datetime):
        observed = raw
    elif raw is None or str(raw).strip() == "":
        raise EEAAQValidationError("missing observation timestamp")
    else:
        text = str(raw).strip().replace("Z", "+00:00")
        try:
            observed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise EEAAQValidationError("malformed observation timestamp") from exc
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return observed.astimezone(timezone.utc)


def validate_coordinates(latitude: float | None, longitude: float | None) -> tuple[float, float]:
    if latitude is None or longitude is None:
        raise EEAAQValidationError("missing station coordinates")
    lat = float(latitude)
    lng = float(longitude)
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        raise EEAAQValidationError("invalid coordinates")
    if lat == 0.0 and lng == 0.0:
        raise EEAAQValidationError("invalid coordinates")
    return lat, lng


def validate_parquet_row(row: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize one EEA parquet row into provider raw record shape."""
    station_id = str(
        row.get("station_id")
        or row.get("Samplingpoint")
        or row.get("samplingpoint")
        or ""
    ).strip()
    if not station_id:
        raise EEAAQValidationError("missing station identity")

    pollutant = normalize_pollutant(
        row.get("pollutant") or row.get("Pollutant")
    )
    if not pollutant:
        raise EEAAQValidationError("missing pollutant")

    validity = row.get("validity") or row.get("Validity")
    if not is_validity_acceptable(validity):
        raise EEAAQValidationError("invalid validity flag")

    value_raw = row.get("value") if "value" in row else row.get("Value")
    if is_missing_value(value_raw):
        raise EEAAQValidationError("missing or sentinel measurement value")
    try:
        value = float(value_raw)
    except (TypeError, ValueError) as exc:
        raise EEAAQValidationError("invalid numeric measurement") from exc
    if value <= EEA_MISSING_VALUE:
        raise EEAAQValidationError("invalid numeric measurement")

    unit = normalize_unit(pollutant, row.get("unit") or row.get("Unit"))
    observed_at = parse_observed_at(
        row.get("observed_at") or row.get("Start") or row.get("start")
    )

    lat_raw = row.get("latitude")
    lng_raw = row.get("longitude")
    latitude: float | None = None
    longitude: float | None = None
    if lat_raw is not None and lng_raw is not None:
        latitude, longitude = validate_coordinates(lat_raw, lng_raw)

    normalized = {
        "station_id": station_id,
        "pollutant": pollutant,
        "value": value,
        "unit": unit,
        "observed_at": observed_at.isoformat(),
        "validity": str(validity or "valid"),
        "verification": str(row.get("verification") or row.get("Verification") or ""),
        "agg_type": str(row.get("agg_type") or row.get("AggType") or "hour"),
    }
    if latitude is not None and longitude is not None:
        normalized["latitude"] = latitude
        normalized["longitude"] = longitude
    if row.get("station_name"):
        normalized["station_name"] = str(row["station_name"])
    if row.get("country"):
        normalized["country"] = str(row["country"])
    if row.get("dataset_version"):
        normalized["dataset_version"] = str(row["dataset_version"])
    return normalized
