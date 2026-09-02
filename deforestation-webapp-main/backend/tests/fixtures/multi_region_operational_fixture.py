"""Deterministic multi-region operational fixture — no live external calls."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_REFERENCE = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)


def reference_now() -> datetime:
    return _REFERENCE


def _base_event(
    *,
    country: str,
    region: str,
    incident_category: str,
    latitude: float,
    longitude: float,
    source: str,
    provider_id: str,
    is_romania: bool,
    station_id: str | None = None,
    hazard_type: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "incident_category": incident_category,
        "ingestion": {
            "source": source,
            "provider_id": provider_id,
            "is_romania": is_romania,
            "source_event_id": f"{provider_id}:{region}:{incident_category}",
        },
    }
    if incident_category == "air_quality":
        metadata["observation"] = {
            "pollutant": "PM2.5",
            "value": 42.0,
            "unit": "ug/m3",
            "observed_at": _REFERENCE.isoformat(),
            "latitude": latitude,
            "longitude": longitude,
            "station_id": station_id or region,
            "station_name": region,
            "source": source,
            "provenance": "monitoring_station",
        }
    if incident_category == "environmental_hazard":
        metadata["emergency_activation"] = {
            "activation_code": f"EMSR-FIX-{region[:2].upper()}",
            "hazard_type": hazard_type or "Flood",
            "countries": [country],
        }
    return {
        "country": country,
        "region": region,
        "latitude": latitude,
        "longitude": longitude,
        "detected_at": _REFERENCE,
        "event_type": "unknown",
        "severity": "high",
        "confidence": 0.85,
        "metadata": metadata,
    }


def build_multi_region_events() -> list[dict[str, Any]]:
    """Romania, Germany, Italy, Spain coverage + one out-of-scope control."""
    return [
        # Romania
        _base_event(
            country="Romania",
            region="Suceava",
            incident_category="wildfire",
            latitude=47.6353,
            longitude=26.259,
            source="NASA FIRMS",
            provider_id="nasa.firms",
            is_romania=True,
        ),
        _base_event(
            country="Romania",
            region="RO-BUC-AQ01",
            incident_category="air_quality",
            latitude=44.4268,
            longitude=26.1025,
            source="EEA Air Quality",
            provider_id="eea.air_quality",
            is_romania=True,
            station_id="RO-BUC-AQ01",
        ),
        _base_event(
            country="Romania",
            region="Romania",
            incident_category="environmental_hazard",
            latitude=47.6353,
            longitude=26.259,
            source="Copernicus EMS",
            provider_id="cems.rapid_mapping",
            is_romania=True,
            hazard_type="Flood",
        ),
        # Germany
        _base_event(
            country="Germany",
            region="Bavaria",
            incident_category="wildfire",
            latitude=48.1351,
            longitude=11.582,
            source="NASA FIRMS",
            provider_id="nasa.firms",
            is_romania=False,
        ),
        _base_event(
            country="Germany",
            region="DE-MUC-AQ01",
            incident_category="air_quality",
            latitude=48.1374,
            longitude=11.5755,
            source="EEA Air Quality",
            provider_id="eea.air_quality",
            is_romania=False,
            station_id="DE-MUC-AQ01",
        ),
        _base_event(
            country="Germany",
            region="Germany",
            incident_category="environmental_hazard",
            latitude=48.1374,
            longitude=11.5755,
            source="Copernicus EMS",
            provider_id="cems.rapid_mapping",
            is_romania=False,
            hazard_type="Storm",
        ),
        # Italy
        _base_event(
            country="Italy",
            region="IT-ROM-AQ01",
            incident_category="air_quality",
            latitude=41.9028,
            longitude=12.4964,
            source="EEA Air Quality",
            provider_id="eea.air_quality",
            is_romania=False,
            station_id="IT-ROM-AQ01",
        ),
        _base_event(
            country="Italy",
            region="Italy",
            incident_category="environmental_hazard",
            latitude=41.9028,
            longitude=12.4964,
            source="Copernicus EMS",
            provider_id="cems.rapid_mapping",
            is_romania=False,
            hazard_type="Wildfire",
        ),
        # Spain
        _base_event(
            country="Spain",
            region="Galicia",
            incident_category="wildfire",
            latitude=42.8805,
            longitude=-8.5456,
            source="NASA FIRMS",
            provider_id="nasa.firms",
            is_romania=False,
        ),
        _base_event(
            country="Spain",
            region="Spain",
            incident_category="environmental_hazard",
            latitude=42.8805,
            longitude=-8.5456,
            source="Copernicus EMS",
            provider_id="cems.rapid_mapping",
            is_romania=False,
            hazard_type="Flood",
        ),
        # France
        _base_event(
            country="France",
            region="FR-PAR-AQ01",
            incident_category="air_quality",
            latitude=48.8566,
            longitude=2.3522,
            source="EEA Air Quality",
            provider_id="eea.air_quality",
            is_romania=False,
            station_id="FR-PAR-AQ01",
        ),
        _base_event(
            country="France",
            region="France",
            incident_category="environmental_hazard",
            latitude=48.8566,
            longitude=2.3522,
            source="Copernicus EMS",
            provider_id="cems.rapid_mapping",
            is_romania=False,
            hazard_type="Flood",
        ),
        # Poland
        _base_event(
            country="Poland",
            region="PL-WAW-AQ01",
            incident_category="air_quality",
            latitude=52.2297,
            longitude=21.0122,
            source="EEA Air Quality",
            provider_id="eea.air_quality",
            is_romania=False,
            station_id="PL-WAW-AQ01",
        ),
        _base_event(
            country="Poland",
            region="Mazovia",
            incident_category="wildfire",
            latitude=52.2297,
            longitude=21.0122,
            source="NASA FIRMS",
            provider_id="nasa.firms",
            is_romania=False,
        ),
        # Out of scope
        _base_event(
            country="Brazil",
            region="Amazon",
            incident_category="wildfire",
            latitude=-3.4653,
            longitude=-62.2159,
            source="NASA FIRMS",
            provider_id="nasa.firms",
            is_romania=False,
        ),
    ]


def events_in_scope(events: list[dict], scope: str) -> list[dict]:
    from app.core.geography.geographic_scope import GeographicScope, GeographicScopePolicy

    policy = GeographicScopePolicy(GeographicScope(scope))
    return [event for event in events if policy.event_in_scope(event)]
