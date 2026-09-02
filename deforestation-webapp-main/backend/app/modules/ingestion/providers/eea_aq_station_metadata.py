"""EEA monitoring-station metadata registry (authoritative coordinates)."""
from __future__ import annotations

import csv
import io
import zipfile
from typing import Any

import httpx

EEA_METADATA_URL = (
    "https://discomap.eea.europa.eu/App/AQViewer/download"
    "?fqn=Airquality_Dissem.b2g.measurements&f=csv"
)

# ISO-3166 alpha-2 → canonical country name for ingestion metadata.
ISO_COUNTRY_NAMES: dict[str, str] = {
    "RO": "Romania",
    "DE": "Germany",
    "ES": "Spain",
    "FR": "France",
    "IT": "Italy",
    "GB": "United Kingdom",
    "UK": "United Kingdom",
    "PL": "Poland",
    "HU": "Hungary",
    "BG": "Bulgaria",
    "GR": "Greece",
    "AT": "Austria",
    "BE": "Belgium",
    "NL": "Netherlands",
    "SE": "Sweden",
    "NO": "Norway",
    "FI": "Finland",
    "DK": "Denmark",
    "PT": "Portugal",
    "IE": "Ireland",
    "CZ": "Czechia",
    "SK": "Slovakia",
    "SI": "Slovenia",
    "HR": "Croatia",
    "RS": "Serbia",
    "UA": "Ukraine",
    "CH": "Switzerland",
}


class EEAAQStationMetadata:
    """Lazy-loaded station coordinate lookup from EEA metadata CSV."""

    def __init__(self, index: dict[str, dict[str, Any]] | None = None) -> None:
        self._index = index

    @property
    def loaded(self) -> bool:
        return self._index is not None

    async def ensure_loaded(self, client: httpx.AsyncClient | None = None) -> None:
        if self._index is not None:
            return
        self._index = await self._download_index(client)

    def lookup(self, sampling_point_id: str) -> dict[str, Any] | None:
        if not self._index or not sampling_point_id:
            return None
        key = sampling_point_id.strip()
        return (
            self._index.get(key)
            or self._index.get(key.upper())
            or self._index.get(key.lower())
        )

    def as_dict(self) -> dict[str, dict[str, Any]]:
        return dict(self._index or {})

    @classmethod
    async def _download_index(
        cls,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, dict[str, Any]]:
        owns_client = client is None
        http = client or httpx.AsyncClient(timeout=120.0, follow_redirects=True)
        try:
            response = await http.get(EEA_METADATA_URL)
            response.raise_for_status()
            return cls.parse_metadata_archive(response.content)
        finally:
            if owns_client:
                await http.aclose()

    @classmethod
    def parse_metadata_archive(cls, archive_bytes: bytes) -> dict[str, dict[str, Any]]:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            csv_name = next(
                (name for name in archive.namelist() if name.lower().endswith(".csv")),
                None,
            )
            if not csv_name:
                return {}
            if ".." in csv_name.replace("\\", "/"):
                return {}
            payload = archive.read(csv_name)
        return cls.parse_metadata_csv(payload)

    @classmethod
    def parse_metadata_csv(cls, csv_bytes: bytes) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig")))
        for row in reader:
            sampling_point = str(row.get("Sampling Point Id") or "").strip()
            station_code = str(row.get("Air Quality Station EoI Code") or "").strip()
            country = str(row.get("Country") or "").strip()
            station_name = str(row.get("Air Quality Station Name") or sampling_point).strip()
            try:
                latitude = float(row["Latitude"])
                longitude = float(row["Longitude"])
            except (KeyError, TypeError, ValueError):
                continue
            record = {
                "station_id": sampling_point or station_code,
                "station_name": station_name,
                "latitude": latitude,
                "longitude": longitude,
                "country": country,
                "pollutant": str(row.get("Air Pollutant") or "").strip(),
            }
            for key in {sampling_point, station_code}:
                if key:
                    index[key] = record
        return index
