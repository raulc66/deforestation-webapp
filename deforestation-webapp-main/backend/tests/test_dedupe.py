"""Unit tests for ingestion dedupe key generation."""
from datetime import datetime, timezone

from app.modules.ingestion.dedupe import build_dedupe_key, resolve_detected_at


class TestBuildDedupeKey:
    def test_deterministic_for_same_inputs(self):
        dt = datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
        a = build_dedupe_key(
            country="Brazil",
            region="Amazon",
            latitude=-3.5,
            longitude=-62.2,
            detected_at=dt,
            event_type="logging",
        )
        b = build_dedupe_key(
            country=" Brazil ",
            region=" Amazon ",
            latitude=-3.5,
            longitude=-62.2,
            detected_at=dt,
            event_type="logging",
        )
        assert a == b

    def test_differs_when_event_type_changes(self):
        dt = datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
        base = dict(
            country="Brazil",
            region="Amazon",
            latitude=-3.5,
            longitude=-62.2,
            detected_at=dt,
        )
        assert build_dedupe_key(**base, event_type="logging") != build_dedupe_key(
            **base, event_type="wildfire"
        )

    def test_normalizes_offset_datetime_to_utc_key(self):
        from datetime import timedelta

        dt_z = datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
        dt_plus2 = datetime(2026, 1, 10, 14, 0, 0, tzinfo=timezone(timedelta(hours=2)))
        key_z = build_dedupe_key(
            country="Brazil",
            region="Amazon",
            latitude=-3.5,
            longitude=-62.2,
            detected_at=dt_z,
            event_type="logging",
        )
        key_plus2 = build_dedupe_key(
            country="Brazil",
            region="Amazon",
            latitude=-3.5,
            longitude=-62.2,
            detected_at=dt_plus2,
            event_type="logging",
        )
        assert key_z == key_plus2

    def test_lat_lng_rounded_to_six_decimals(self):
        dt = datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
        k1 = build_dedupe_key(
            country="Brazil",
            region="Amazon",
            latitude=-3.50000041,
            longitude=-62.20000041,
            detected_at=dt,
            event_type="logging",
        )
        k2 = build_dedupe_key(
            country="Brazil",
            region="Amazon",
            latitude=-3.50000049,
            longitude=-62.20000049,
            detected_at=dt,
            event_type="logging",
        )
        assert k1 == k2


class TestResolveDetectedAt:
    def test_none_returns_utc_now(self):
        before = datetime.now(timezone.utc)
        resolved = resolve_detected_at(None)
        after = datetime.now(timezone.utc)
        assert before <= resolved <= after

    def test_naive_datetime_treated_as_utc(self):
        naive = datetime(2026, 1, 10, 12, 0, 0)
        resolved = resolve_detected_at(naive)
        assert resolved.tzinfo is not None
