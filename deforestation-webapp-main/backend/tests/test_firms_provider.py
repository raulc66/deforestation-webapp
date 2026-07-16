"""Unit tests for the NASA FIRMS ingestion provider."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.geography.romania import ROMANIA_BBOX, is_romania_event
from app.modules.ingestion.dedupe import build_dedupe_key
from app.modules.ingestion.providers.firms import (
    MOCK_FIRMS_DATA,
    FIRMSProvider,
    _parse_confidence,
    _parse_detected_at,
    _severity_from_frp,
    _affected_area_from_scan_track,
    _country_region_from_event,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _romania_raw() -> dict:
    """A FIRMS row whose coordinates fall inside Romania."""
    return {
        "latitude": "45.8560",
        "longitude": "24.9745",
        "brightness": "332.4",
        "scan": "0.40",
        "track": "0.37",
        "acq_date": "2026-06-10",
        "acq_time": "0845",
        "satellite": "N",
        "confidence": "nominal",
        "version": "2.0NRT",
        "bright_t31": "295.3",
        "frp": "12.8",
        "daynight": "D",
    }


def _brazil_raw() -> dict:
    """A FIRMS row with coordinates in the Amazon (outside Romania)."""
    return {
        "latitude": "-3.5120",
        "longitude": "-62.2480",
        "brightness": "342.0",
        "scan": "0.39",
        "track": "0.36",
        "acq_date": "2026-06-10",
        "acq_time": "1423",
        "satellite": "N",
        "confidence": "high",
        "version": "2.0NRT",
        "bright_t31": "288.7",
        "frp": "43.2",
        "daynight": "D",
    }


# ---------------------------------------------------------------------------
# Field-mapping: normalize()
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_event_type_is_always_wildfire(self):
        ev = FIRMSProvider().normalize(_romania_raw())
        assert ev.event_type == "wildfire"

    def test_coordinates_mapped_correctly(self):
        ev = FIRMSProvider().normalize(_romania_raw())
        assert abs(ev.latitude - 45.856) < 0.001
        assert abs(ev.longitude - 24.9745) < 0.001

    def test_detected_at_is_utc_datetime(self):
        ev = FIRMSProvider().normalize(_romania_raw())
        assert ev.detected_at is not None
        assert ev.detected_at.tzinfo == timezone.utc
        assert ev.detected_at.hour == 8
        assert ev.detected_at.minute == 45

    def test_confidence_nominal_maps_to_0_7(self):
        ev = FIRMSProvider().normalize(_romania_raw())
        assert abs(ev.confidence - 0.7) < 0.001

    def test_confidence_high_maps_to_0_9(self):
        raw = {**_romania_raw(), "confidence": "high"}
        ev = FIRMSProvider().normalize(raw)
        assert abs(ev.confidence - 0.9) < 0.001

    def test_confidence_low_maps_to_0_3(self):
        raw = {**_romania_raw(), "confidence": "low"}
        ev = FIRMSProvider().normalize(raw)
        assert abs(ev.confidence - 0.3) < 0.001

    def test_confidence_integer_pct_normalised(self):
        raw = {**_romania_raw(), "confidence": "80"}
        ev = FIRMSProvider().normalize(raw)
        assert abs(ev.confidence - 0.80) < 0.001

    def test_severity_low_when_frp_below_10(self):
        raw = {**_romania_raw(), "frp": "5.0"}
        ev = FIRMSProvider().normalize(raw)
        assert ev.severity == "low"

    def test_severity_medium_when_frp_10_to_50(self):
        raw = {**_romania_raw(), "frp": "25.0"}
        ev = FIRMSProvider().normalize(raw)
        assert ev.severity == "medium"

    def test_severity_high_when_frp_50_to_200(self):
        raw = {**_romania_raw(), "frp": "100.0"}
        ev = FIRMSProvider().normalize(raw)
        assert ev.severity == "high"

    def test_severity_critical_when_frp_200_plus(self):
        raw = {**_romania_raw(), "frp": "250.0"}
        ev = FIRMSProvider().normalize(raw)
        assert ev.severity == "critical"

    def test_affected_area_computed_from_scan_track(self):
        raw = {**_romania_raw(), "scan": "0.40", "track": "0.37"}
        ev = FIRMSProvider().normalize(raw)
        expected = round(0.40 * 0.37 * 100, 2)
        assert abs(ev.affected_area_ha - expected) < 0.01

    def test_title_contains_coords_and_date(self):
        ev = FIRMSProvider().normalize(_romania_raw())
        assert "45.8560" in ev.title
        assert "24.9745" in ev.title
        assert "2026-06-10" in ev.title

    def test_metadata_contains_provider_key(self):
        ev = FIRMSProvider().normalize(_romania_raw())
        assert ev.metadata.get("provider") == "nasa_firms"

    def test_metadata_contains_satellite_and_frp(self):
        ev = FIRMSProvider().normalize(_romania_raw())
        assert "satellite" in ev.metadata
        assert "frp_mw" in ev.metadata


# ---------------------------------------------------------------------------
# Romania classification
# ---------------------------------------------------------------------------

class TestRomaniaClassification:
    def test_romania_event_flagged_true(self):
        ev = FIRMSProvider().normalize(_romania_raw())
        assert ev.metadata.get("is_romania") is True

    def test_non_romania_event_flagged_false(self):
        ev = FIRMSProvider().normalize(_brazil_raw())
        assert ev.metadata.get("is_romania") is False

    def test_romania_event_gets_country_romania(self):
        ev = FIRMSProvider().normalize(_romania_raw())
        assert ev.country == "Romania"

    def test_non_romania_event_gets_country_unknown(self):
        ev = FIRMSProvider().normalize(_brazil_raw())
        assert ev.country == "Unknown"

    def test_bbox_boundary_inside_is_romania(self):
        result = is_romania_event({
            "latitude": ROMANIA_BBOX["min_lat"],
            "longitude": ROMANIA_BBOX["min_lng"],
        })
        assert result is True

    def test_coords_just_outside_bbox_not_romania(self):
        result = is_romania_event({
            "latitude": ROMANIA_BBOX["min_lat"] - 0.1,
            "longitude": ROMANIA_BBOX["min_lng"],
        })
        assert result is False

    def test_all_mock_romania_records_classified(self):
        """At least two mock records should be inside Romania."""
        provider = FIRMSProvider()
        romania_events = [
            provider.normalize(r)
            for r in MOCK_FIRMS_DATA
            if provider.normalize(r).metadata.get("is_romania")
        ]
        assert len(romania_events) >= 2


# ---------------------------------------------------------------------------
# Deduplication compatibility
# ---------------------------------------------------------------------------

class TestDedupeCompatibility:
    def test_dedupe_key_is_stable_across_calls(self):
        provider = FIRMSProvider()
        ev1 = provider.normalize(_romania_raw())
        ev2 = provider.normalize(_romania_raw())
        key1 = build_dedupe_key(
            country=ev1.country,
            region=ev1.region,
            latitude=ev1.latitude,
            longitude=ev1.longitude,
            detected_at=ev1.detected_at,
            event_type=ev1.event_type,
        )
        key2 = build_dedupe_key(
            country=ev2.country,
            region=ev2.region,
            latitude=ev2.latitude,
            longitude=ev2.longitude,
            detected_at=ev2.detected_at,
            event_type=ev2.event_type,
        )
        assert key1 == key2

    def test_different_coords_produce_different_keys(self):
        provider = FIRMSProvider()
        ev_ro = provider.normalize(_romania_raw())
        ev_br = provider.normalize(_brazil_raw())
        key_ro = build_dedupe_key(
            country=ev_ro.country,
            region=ev_ro.region,
            latitude=ev_ro.latitude,
            longitude=ev_ro.longitude,
            detected_at=ev_ro.detected_at,
            event_type=ev_ro.event_type,
        )
        key_br = build_dedupe_key(
            country=ev_br.country,
            region=ev_br.region,
            latitude=ev_br.latitude,
            longitude=ev_br.longitude,
            detected_at=ev_br.detected_at,
            event_type=ev_br.event_type,
        )
        assert key_ro != key_br

    def test_run_skips_duplicate_in_same_batch(self):
        """Two identical records in one fetch should produce skipped=1."""
        provider = FIRMSProvider()
        dup_raw = [_romania_raw(), _romania_raw()]

        events_svc = MagicMock()
        events_svc.create_event = AsyncMock()
        events_repo = MagicMock()
        events_repo.col = MagicMock()
        events_repo.col.find_one = AsyncMock(return_value=None)

        with patch.object(provider, "fetch", new=AsyncMock(return_value=dup_raw)):
            result = asyncio.run(provider.run(events_svc, events_repo))

        assert result["created"] == 1
        assert result["skipped"] == 1
        assert result["errors"] == 0
        assert result["total"] == 2


# ---------------------------------------------------------------------------
# Fetch behaviour
# ---------------------------------------------------------------------------

class TestFetch:
    def test_returns_mock_when_no_api_key(self):
        provider = FIRMSProvider(api_key="")
        records = asyncio.run(provider.fetch())
        assert records == MOCK_FIRMS_DATA

    def test_mock_data_has_required_fields(self):
        required = {"latitude", "longitude", "acq_date", "acq_time", "confidence", "frp"}
        for row in MOCK_FIRMS_DATA:
            missing = required - row.keys()
            assert not missing, f"Mock row missing fields: {missing}"

    def test_mock_data_not_empty(self):
        assert len(MOCK_FIRMS_DATA) >= 3


# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_parse_detected_at_returns_utc(self):
        dt = _parse_detected_at("2026-06-10", "0845")
        assert dt.tzinfo == timezone.utc
        assert dt.year == 2026
        assert dt.hour == 8
        assert dt.minute == 45

    def test_parse_detected_at_invalid_gracefully_returns_now(self):
        dt = _parse_detected_at("bad-date", "XXXX")
        assert dt.tzinfo == timezone.utc

    @pytest.mark.parametrize("raw,expected", [
        ("nominal", 0.7), ("n", 0.7),
        ("high", 0.9), ("h", 0.9),
        ("low", 0.3), ("l", 0.3),
        ("80", 0.8), ("100", 1.0), ("0", 0.0),
    ])
    def test_parse_confidence_parametrized(self, raw, expected):
        assert abs(_parse_confidence(raw) - expected) < 0.001

    @pytest.mark.parametrize("frp,sev", [
        ("0", "low"), ("9.9", "low"),
        ("10", "medium"), ("49.9", "medium"),
        ("50", "high"), ("199", "high"),
        ("200", "critical"), ("999", "critical"),
    ])
    def test_severity_from_frp_parametrized(self, frp, sev):
        assert _severity_from_frp(frp) == sev

    def test_affected_area_calculation(self):
        result = _affected_area_from_scan_track("0.40", "0.37")
        assert abs(result - 14.8) < 0.01

    def test_country_region_inside_romania(self):
        country, region = _country_region_from_event(45.856, 24.974)
        assert country == "Romania"

    def test_country_region_outside_romania(self):
        country, region = _country_region_from_event(-3.512, -62.248)
        assert country == "Unknown"
