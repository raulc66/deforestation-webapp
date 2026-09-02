"""Air quality pollutant normalization and reference limits (EEA e-Reporting)."""
from __future__ import annotations

# Canonical pollutant codes used internally after normalization.
CANONICAL_POLLUTANTS: frozenset[str] = frozenset({"PM2.5", "PM10", "NO2", "O3", "SO2"})

# Raw EEA / Airbase pollutant code aliases → canonical identifier.
POLLUTANT_ALIASES: dict[str, str] = {
    "pm2.5": "PM2.5",
    "pm25": "PM2.5",
    "pm2_5": "PM2.5",
    "particulatematter2.5": "PM2.5",
    "pm10": "PM10",
    "particulatematter10": "PM10",
    "no2": "NO2",
    "nitrogendioxide": "NO2",
    "o3": "O3",
    "ozone": "O3",
    "so2": "SO2",
    "sulphurdioxide": "SO2",
}

# Canonical unit for each pollutant after normalization.
POLLUTANT_UNITS: dict[str, str] = {
    "PM2.5": "ug/m3",
    "PM10": "ug/m3",
    "NO2": "ug/m3",
    "O3": "ug/m3",
    "SO2": "ug/m3",
}

# EEA sentinel for missing/invalid measurements (UTD guide: -999).
EEA_MISSING_VALUE = -999.0


def normalize_pollutant(raw: str | None) -> str | None:
    if not raw:
        return None
    key = str(raw).strip().lower().replace(" ", "")
    return POLLUTANT_ALIASES.get(key, str(raw).strip().upper())


def normalize_unit(pollutant: str, raw_unit: str | None) -> str:
    if raw_unit:
        normalized = str(raw_unit).strip().lower().replace(" ", "")
        if normalized in {"ug/m3", "µg/m3", "ugm-3", "microg/m3"}:
            return "ug/m3"
        if normalized in {"mg/m3", "mgm-3"}:
            return "mg/m3"
        return str(raw_unit).strip()
    return POLLUTANT_UNITS.get(pollutant, "ug/m3")


def is_missing_value(value: float | None) -> bool:
    if value is None:
        return True
    try:
        return float(value) <= EEA_MISSING_VALUE
    except (TypeError, ValueError):
        return True
