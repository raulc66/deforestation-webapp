"""Safe ZIP/Parquet extraction for EEA E2a downloads."""
from __future__ import annotations

import io
import zipfile
from typing import Any

import pandas as pd

from .eea_aq_validation import EEAAQValidationError, validate_parquet_row

# Documented EEA download limit is 600 MB; cap parsed rows for memory safety.
MAX_PARQUET_ROWS = 50_000


class EEAAQParquetError(RuntimeError):
    """Raised when archive/parquet parsing fails."""


def _safe_member_name(name: str) -> bool:
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or ".." in normalized.split("/"):
        return False
    return normalized.lower().endswith(".parquet")


def extract_parquet_rows(zip_bytes: bytes, *, max_rows: int = MAX_PARQUET_ROWS) -> list[dict[str, Any]]:
    """Extract and parse all parquet members from an EEA ZIP response."""
    if not zip_bytes:
        raise EEAAQParquetError("empty archive")

    rows: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            members = [name for name in archive.namelist() if _safe_member_name(name)]
            if not members:
                raise EEAAQParquetError("no parquet members in archive")

            for member in sorted(members):
                if ".." in member.replace("\\", "/"):
                    raise EEAAQParquetError("unsafe archive member path")
                payload = archive.read(member)
                frame = pd.read_parquet(io.BytesIO(payload))
                if len(frame) > max_rows:
                    frame = frame.head(max_rows)
                for record in frame.to_dict(orient="records"):
                    rows.append(record)
                    if len(rows) >= max_rows:
                        return rows
    except zipfile.BadZipFile as exc:
        raise EEAAQParquetError("malformed zip archive") from exc
    except EEAAQParquetError:
        raise
    except Exception as exc:
        raise EEAAQParquetError("malformed parquet payload") from exc

    return rows


def normalize_parquet_rows(
    parquet_rows: list[dict[str, Any]],
    *,
    station_lookup: dict[str, dict[str, Any]] | None = None,
    dataset_version: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Validate parquet rows and enrich with station metadata when available."""
    accepted: list[dict[str, Any]] = []
    rejected = 0
    lookup = station_lookup or {}

    for row in parquet_rows:
        station_key = str(
            row.get("Samplingpoint") or row.get("samplingpoint") or row.get("station_id") or ""
        ).strip()
        meta = lookup.get(station_key) or lookup.get(station_key.upper()) or {}
        enriched = {
            **row,
            "station_id": station_key or row.get("station_id"),
            "latitude": row.get("latitude", meta.get("latitude")),
            "longitude": row.get("longitude", meta.get("longitude")),
            "station_name": row.get("station_name", meta.get("station_name")),
            "country": row.get("country", meta.get("country")),
            "dataset_version": dataset_version or row.get("dataset_version"),
        }
        try:
            accepted.append(validate_parquet_row(enriched))
        except EEAAQValidationError:
            rejected += 1

    accepted.sort(
        key=lambda item: (
            item["station_id"],
            item["pollutant"],
            item["observed_at"],
        )
    )
    return accepted, rejected
