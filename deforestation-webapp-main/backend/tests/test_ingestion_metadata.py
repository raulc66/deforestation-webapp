"""Unit tests for the cross-source IngestionMetadata normalization layer."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.core.ingestion.ingestion_metadata import (
    IngestionMetadata,
    build_ingestion_metadata,
    ingestion_metadata_from_event,
)
from app.modules.ingestion.providers.firms import FIRMSProvider, MOCK_FIRMS_DATA


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _romania_firms_raw() -> dict:
    """FIRMS row with coordinates inside Romania (bbox hit)."""
    return next(r for r in MOCK_FIRMS_DATA if float(r["latitude"]) > 43.62)


def _brazil_firms_raw() -> dict:
    """FIRMS row outside Romania."""
    return next(r for r in MOCK_FIRMS_DATA if float(r["latitude"]) < 0)


def _csv_romania_parsed() -> dict:
    """Simulated parsed CSV row for a Romanian event."""
    return {
        "country": "Romania",
        "region": "Transylvania",
        "latitude": 45.856,
        "longitude": 24.974,
        "confidence": 0.85,
        "severity": "high",
    }


def _csv_global_parsed() -> dict:
    """Simulated parsed CSV row for a non-Romanian event."""
    return {
        "country": "Brazil",
        "region": "Amazon",
        "latitude": -3.5,
        "longitude": -62.2,
        "confidence": 0.7,
        "severity": "medium",
    }


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------

class TestIngestionMetadataModel:
    def test_required_fields_accepted(self):
        meta = build_ingestion_metadata(
            source="CSV",
            source_event_id="row:2",
            is_romania=True,
            confidence=0.85,
            severity="high",
        )
        assert meta.source == "CSV"
        assert meta.source_event_id == "row:2"
        assert meta.is_romania is True
        assert meta.confidence == 0.85
        assert meta.severity == "high"
        assert isinstance(meta.ingestion_timestamp, datetime)
        assert meta.ingestion_timestamp.tzinfo == timezone.utc

    def test_optional_fields_accept_none(self):
        meta = build_ingestion_metadata(
            source="NASA FIRMS",
            source_event_id=None,
            is_romania=False,
            confidence=None,
            severity=None,
        )
        assert meta.source_event_id is None
        assert meta.confidence is None
        assert meta.severity is None

    def test_explicit_ingestion_timestamp_preserved(self):
        fixed = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)
        meta = build_ingestion_metadata(
            source="CSV",
            source_event_id=None,
            is_romania=False,
            confidence=0.8,
            severity="medium",
            ingestion_timestamp=fixed,
        )
        assert meta.ingestion_timestamp == fixed

    def test_model_is_frozen(self):
        meta = build_ingestion_metadata(
            source="CSV",
            source_event_id=None,
            is_romania=False,
            confidence=0.8,
            severity="medium",
        )
        with pytest.raises((TypeError, ValidationError)):
            meta.source = "mutated"  # type: ignore[misc]

    def test_model_dump_is_json_compatible(self):
        meta = build_ingestion_metadata(
            source="NASA FIRMS",
            source_event_id=None,
            is_romania=True,
            confidence=0.9,
            severity="critical",
        )
        dumped = meta.model_dump()
        assert set(dumped.keys()) == {
            "source",
            "provider_id",
            "dataset_id",
            "dataset_version",
            "provenance_label",
            "source_event_id",
            "ingestion_timestamp",
            "is_romania",
            "confidence",
            "severity",
        }
        assert isinstance(dumped["ingestion_timestamp"], datetime)

    def test_roundtrip_via_ingestion_metadata_from_event(self):
        meta = build_ingestion_metadata(
            source="CSV",
            source_event_id="row:5",
            is_romania=True,
            confidence=0.75,
            severity="low",
        )
        event_metadata = {"ingestion": meta.model_dump(), "other_key": "value"}
        reconstructed = ingestion_metadata_from_event(event_metadata)
        assert reconstructed is not None
        assert reconstructed.source == "CSV"
        assert reconstructed.source_event_id == "row:5"
        assert reconstructed.is_romania is True

    def test_from_event_returns_none_for_legacy_records(self):
        assert ingestion_metadata_from_event({}) is None
        assert ingestion_metadata_from_event({"other_key": "x"}) is None


# ---------------------------------------------------------------------------
# FIRMS metadata
# ---------------------------------------------------------------------------

class TestFIRMSIngestionMetadata:
    def _get_ingestion(self, raw: dict) -> dict:
        ev = FIRMSProvider().normalize(raw)
        return ev.metadata["ingestion"]

    def test_ingestion_key_present_in_metadata(self):
        ev = FIRMSProvider().normalize(_romania_firms_raw())
        assert "ingestion" in ev.metadata

    def test_source_is_nasa_firms(self):
        block = self._get_ingestion(_romania_firms_raw())
        assert block["source"] == "NASA FIRMS"

    def test_source_event_id_is_none(self):
        block = self._get_ingestion(_romania_firms_raw())
        assert block["source_event_id"] is None

    def test_romania_event_flagged_true(self):
        block = self._get_ingestion(_romania_firms_raw())
        assert block["is_romania"] is True

    def test_non_romania_event_flagged_false(self):
        block = self._get_ingestion(_brazil_firms_raw())
        assert block["is_romania"] is False

    def test_confidence_matches_normalized_confidence(self):
        ev = FIRMSProvider().normalize(_romania_firms_raw())
        block = ev.metadata["ingestion"]
        assert abs(block["confidence"] - ev.confidence) < 0.001

    def test_severity_matches_event_severity(self):
        ev = FIRMSProvider().normalize(_romania_firms_raw())
        block = ev.metadata["ingestion"]
        assert block["severity"] == ev.severity

    def test_ingestion_timestamp_is_datetime(self):
        block = self._get_ingestion(_romania_firms_raw())
        assert isinstance(block["ingestion_timestamp"], datetime)
        assert block["ingestion_timestamp"].tzinfo == timezone.utc

    def test_flat_is_romania_key_still_present_for_backward_compat(self):
        ev = FIRMSProvider().normalize(_romania_firms_raw())
        assert "is_romania" in ev.metadata


# ---------------------------------------------------------------------------
# CSV metadata
# ---------------------------------------------------------------------------

class TestCSVIngestionMetadata:
    def _build_meta(self, parsed: dict) -> IngestionMetadata:
        from app.core.geography.romania import is_romania_event
        from app.core.ingestion.ingestion_metadata import build_ingestion_metadata

        row_idx = 2
        is_romania = is_romania_event({
            "country": parsed["country"],
            "region": parsed["region"],
            "latitude": parsed["latitude"],
            "longitude": parsed["longitude"],
        })
        return build_ingestion_metadata(
            source="CSV",
            source_event_id=f"row:{row_idx}",
            is_romania=is_romania,
            confidence=parsed["confidence"],
            severity=parsed["severity"],
        )

    def test_source_is_csv(self):
        meta = self._build_meta(_csv_romania_parsed())
        assert meta.source == "CSV"

    def test_source_event_id_contains_row_number(self):
        meta = self._build_meta(_csv_romania_parsed())
        assert meta.source_event_id == "row:2"
        assert "row:" in meta.source_event_id

    def test_romania_event_flagged_true(self):
        meta = self._build_meta(_csv_romania_parsed())
        assert meta.is_romania is True

    def test_global_event_flagged_false(self):
        meta = self._build_meta(_csv_global_parsed())
        assert meta.is_romania is False

    def test_confidence_preserved(self):
        meta = self._build_meta(_csv_romania_parsed())
        assert abs(meta.confidence - 0.85) < 0.001

    def test_severity_preserved(self):
        meta = self._build_meta(_csv_romania_parsed())
        assert meta.severity == "high"


# ---------------------------------------------------------------------------
# Cross-source consistency
# ---------------------------------------------------------------------------

class TestCrossSourceConsistency:
    REQUIRED_KEYS = {
        "source",
        "provider_id",
        "dataset_id",
        "dataset_version",
        "provenance_label",
        "source_event_id",
        "ingestion_timestamp",
        "is_romania",
        "confidence",
        "severity",
    }

    def _firms_block(self) -> dict:
        ev = FIRMSProvider().normalize(_romania_firms_raw())
        return ev.metadata["ingestion"]

    def _csv_block(self, is_romania: bool) -> dict:
        from app.core.geography.romania import is_romania_event
        parsed = _csv_romania_parsed() if is_romania else _csv_global_parsed()
        meta = build_ingestion_metadata(
            source="CSV",
            source_event_id="row:2",
            is_romania=is_romania_event(parsed),
            confidence=parsed["confidence"],
            severity=parsed["severity"],
        )
        return meta.model_dump()

    def test_firms_block_has_all_required_keys(self):
        assert self.REQUIRED_KEYS == set(self._firms_block().keys())

    def test_csv_block_has_all_required_keys(self):
        assert self.REQUIRED_KEYS == set(self._csv_block(True).keys())

    def test_both_sources_produce_same_schema(self):
        assert set(self._firms_block().keys()) == set(self._csv_block(True).keys())

    def test_romania_coords_classified_identically_across_sources(self):
        """Same lat/lng should get the same is_romania flag from both sources."""
        lat, lng = 45.856, 24.974

        firms_raw = {**_romania_firms_raw(), "latitude": str(lat), "longitude": str(lng)}
        firms_ev = FIRMSProvider().normalize(firms_raw)
        firms_is_ro = firms_ev.metadata["ingestion"]["is_romania"]

        from app.core.geography.romania import is_romania_event
        csv_is_ro = is_romania_event({"latitude": lat, "longitude": lng})

        assert firms_is_ro == csv_is_ro is True

    def test_non_romania_coords_classified_identically_across_sources(self):
        lat, lng = -3.5, -62.2

        firms_raw = {**_brazil_firms_raw(), "latitude": str(lat), "longitude": str(lng)}
        firms_ev = FIRMSProvider().normalize(firms_raw)
        firms_is_ro = firms_ev.metadata["ingestion"]["is_romania"]

        from app.core.geography.romania import is_romania_event
        csv_is_ro = is_romania_event({"latitude": lat, "longitude": lng})

        assert firms_is_ro == csv_is_ro is False

    def test_ingestion_block_survives_model_dump_roundtrip(self):
        """Verify IngestionMetadata can be written and re-read intact."""
        original = build_ingestion_metadata(
            source="NASA FIRMS",
            source_event_id=None,
            is_romania=True,
            confidence=0.9,
            severity="high",
        )
        restored = ingestion_metadata_from_event({"ingestion": original.model_dump()})
        assert restored is not None
        assert restored.source == original.source
        assert restored.is_romania == original.is_romania
        assert restored.confidence == original.confidence
        assert restored.severity == original.severity
