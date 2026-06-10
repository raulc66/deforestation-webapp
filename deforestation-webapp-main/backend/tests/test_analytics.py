"""Backend tests for the Analytics module (iteration 7).

Covers:
  GET /api/analytics/overview
  GET /api/analytics/countries
  GET /api/analytics/event-types
  GET /api/analytics/severity
  GET /api/analytics/trends   (day | week | month)
  GET /api/modules/analytics  (capabilities reporting)
  + auth (401) + invariants + sort order + zero-fill + ISO 8601 formats
"""
import os
import pytest
import requests
from datetime import datetime, timedelta, timezone


def _read_frontend_env_url() -> str:
    try:
        with open("/app/frontend/.env", "r") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    return ""


_RAW = os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env_url()
assert _RAW, "REACT_APP_BACKEND_URL must be configured"
BASE_URL = _RAW.rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@forestwatch.io"
ADMIN_PASSWORD = "ForestAdmin2026!"

EXPECTED_EVENT_TYPES = [
    "logging",
    "wildfire",
    "mining",
    "agriculture",
    "road_construction",
    "urban_expansion",
    "unknown",
]
EXPECTED_SEVERITY_ORDER = ["low", "medium", "high", "critical"]


def _parse_iso(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


@pytest.fixture(scope="module")
def admin_session() -> requests.Session:
    s = requests.Session()
    r = s.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


# --------------------------------------------------------------------- #
# Module info
# --------------------------------------------------------------------- #
class TestModuleInfo:
    def test_analytics_module_active(self):
        r = requests.get(f"{API}/modules/analytics", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "analytics"
        assert body["status"] == "active"
        caps = body["capabilities"]
        for k in ("overview", "by_country", "by_event_type", "by_severity", "trends"):
            assert caps.get(k) == "live", f"{k} should be 'live', got {caps.get(k)}"


# --------------------------------------------------------------------- #
# Auth requirement
# --------------------------------------------------------------------- #
class TestAuthRequired:
    @pytest.mark.parametrize(
        "path",
        [
            "/analytics/overview",
            "/analytics/countries",
            "/analytics/event-types",
            "/analytics/severity",
            "/analytics/trends?start_date=2026-01-01T00:00:00Z&end_date=2026-01-31T00:00:00Z",
        ],
    )
    def test_requires_auth(self, path):
        r = requests.get(f"{API}{path}", timeout=10)
        assert r.status_code == 401, f"{path} should be 401 unauth, got {r.status_code}"


# --------------------------------------------------------------------- #
# Overview
# --------------------------------------------------------------------- #
class TestOverview:
    def test_shape_and_types(self, admin_session):
        r = admin_session.get(f"{API}/analytics/overview", timeout=15)
        assert r.status_code == 200
        body = r.json()
        for k in (
            "total_events",
            "total_area_affected",
            "open_events",
            "resolved_events",
            "investigating_events",
            "average_confidence",
        ):
            assert k in body, f"missing key: {k}"
        assert isinstance(body["total_events"], int)
        assert isinstance(body["open_events"], int)
        assert isinstance(body["resolved_events"], int)
        assert isinstance(body["investigating_events"], int)
        assert isinstance(body["total_area_affected"], (int, float))
        assert isinstance(body["average_confidence"], (int, float))
        assert 0.0 <= body["average_confidence"] <= 1.0

    def test_overview_invariants(self, admin_session):
        ov = admin_session.get(f"{API}/analytics/overview", timeout=15).json()
        # status buckets must not exceed total
        total = ov["total_events"]
        assert ov["open_events"] + ov["resolved_events"] + ov["investigating_events"] <= total

        # total matches /api/events length
        ev = admin_session.get(f"{API}/events?limit=1000", timeout=15).json()
        assert isinstance(ev, list)
        assert total == len(ev), f"total_events {total} != /api/events count {len(ev)}"

        # total_area_affected ≈ sum(affected_area_ha)
        s = sum(e.get("affected_area_ha", 0) or 0 for e in ev)
        assert abs(ov["total_area_affected"] - round(s, 2)) < 0.1

    def test_average_confidence_decimals(self, admin_session):
        ov = admin_session.get(f"{API}/analytics/overview", timeout=15).json()
        ac = ov["average_confidence"]
        # rounded to 3 decimals
        assert round(ac, 3) == ac


# --------------------------------------------------------------------- #
# By country
# --------------------------------------------------------------------- #
class TestByCountry:
    def test_shape_sort_and_totals(self, admin_session):
        r = admin_session.get(f"{API}/analytics/countries", timeout=15)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        assert len(rows) > 0
        for row in rows:
            assert set(row.keys()) == {"country", "event_count", "affected_area_ha"}
            assert isinstance(row["event_count"], int)
        # sort: event_count DESC, then country ASC
        for i in range(1, len(rows)):
            prev, curr = rows[i - 1], rows[i]
            if prev["event_count"] == curr["event_count"]:
                assert prev["country"] <= curr["country"], (
                    f"tie-broken sort wrong: {prev['country']} vs {curr['country']}"
                )
            else:
                assert prev["event_count"] > curr["event_count"]
        # sum equals overview.total_events
        total = sum(r["event_count"] for r in rows)
        ov = admin_session.get(f"{API}/analytics/overview", timeout=15).json()
        assert total == ov["total_events"]


# --------------------------------------------------------------------- #
# By event type — zero-filled full taxonomy
# --------------------------------------------------------------------- #
class TestByEventType:
    def test_full_taxonomy_zero_filled(self, admin_session):
        r = admin_session.get(f"{API}/analytics/event-types", timeout=15)
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        assert len(rows) == 7, f"expected 7 entries (full taxonomy), got {len(rows)}"
        types_returned = {row["event_type"] for row in rows}
        assert types_returned == set(EXPECTED_EVENT_TYPES)
        # shape
        for row in rows:
            assert set(row.keys()) == {"event_type", "event_count", "affected_area_ha"}
            assert row["event_count"] >= 0
            assert row["affected_area_ha"] >= 0
        # sort by event_count DESC
        for i in range(1, len(rows)):
            assert rows[i - 1]["event_count"] >= rows[i]["event_count"]
        # sum matches total
        ov = admin_session.get(f"{API}/analytics/overview", timeout=15).json()
        assert sum(r["event_count"] for r in rows) == ov["total_events"]


# --------------------------------------------------------------------- #
# Severity — object with canonical key order
# --------------------------------------------------------------------- #
class TestBySeverity:
    def test_object_with_all_four_keys(self, admin_session):
        r = admin_session.get(f"{API}/analytics/severity", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict)
        assert list(body.keys()) == EXPECTED_SEVERITY_ORDER, (
            f"keys must be canonical order, got {list(body.keys())}"
        )
        for sev in EXPECTED_SEVERITY_ORDER:
            entry = body[sev]
            assert set(entry.keys()) == {"count", "area_ha"}
            assert entry["count"] >= 0
            assert entry["area_ha"] >= 0
        # sum matches total
        ov = admin_session.get(f"{API}/analytics/overview", timeout=15).json()
        assert sum(body[s]["count"] for s in EXPECTED_SEVERITY_ORDER) == ov["total_events"]


# --------------------------------------------------------------------- #
# Trends
# --------------------------------------------------------------------- #
class TestTrends:
    def _range(self, days_back: int = 60):
        end = datetime.now(timezone.utc).replace(microsecond=0)
        start = end - timedelta(days=days_back)
        return start, end

    def test_day_buckets_shape(self, admin_session):
        start, end = self._range(60)
        r = admin_session.get(
            f"{API}/analytics/trends",
            params={
                "start_date": start.isoformat().replace("+00:00", "Z"),
                "end_date": end.isoformat().replace("+00:00", "Z"),
                "interval": "day",
            },
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["interval"] == "day"
        assert "start_date" in body and "end_date" in body
        assert isinstance(body["series"], list)
        # ascending order
        prev = None
        for bucket in body["series"]:
            assert set(bucket.keys()) == {"bucket", "event_count", "affected_area_ha"}
            cur = _parse_iso(bucket["bucket"])
            if prev is not None:
                assert cur >= prev
            prev = cur
            # day-aligned: hour/min/sec = 0
            assert cur.hour == 0 and cur.minute == 0 and cur.second == 0

    def test_week_and_month_intervals_consistent(self, admin_session):
        start, end = self._range(90)
        s_iso = start.isoformat().replace("+00:00", "Z")
        e_iso = end.isoformat().replace("+00:00", "Z")

        def fetch(interval):
            r = admin_session.get(
                f"{API}/analytics/trends",
                params={"start_date": s_iso, "end_date": e_iso, "interval": interval},
                timeout=15,
            )
            assert r.status_code == 200, f"{interval}: {r.text}"
            return r.json()["series"]

        day = fetch("day")
        week = fetch("week")
        month = fetch("month")
        # Bucket count invariants
        assert len(month) <= len(week) <= len(day)
        # totals across intervals must match
        s_day = sum(b["event_count"] for b in day)
        s_week = sum(b["event_count"] for b in week)
        s_month = sum(b["event_count"] for b in month)
        assert s_day == s_week == s_month

        # week buckets align to a week boundary (any consistent boundary)
        # at least ensure they are day-aligned UTC
        for b in week + month:
            ts = _parse_iso(b["bucket"])
            assert ts.hour == 0 and ts.minute == 0 and ts.second == 0
        # month-aligned: day==1
        for b in month:
            ts = _parse_iso(b["bucket"])
            assert ts.day == 1, f"month bucket not aligned to day=1: {b['bucket']}"

    def test_invalid_interval(self, admin_session):
        start, end = self._range(30)
        r = admin_session.get(
            f"{API}/analytics/trends",
            params={
                "start_date": start.isoformat().replace("+00:00", "Z"),
                "end_date": end.isoformat().replace("+00:00", "Z"),
                "interval": "hour",
            },
            timeout=10,
        )
        assert r.status_code == 400
        body = r.json()
        # AppError shape — look for code field
        code = body.get("code")
        if code is None and isinstance(body.get("detail"), dict):
            code = body["detail"].get("code")
        assert code == "invalid_interval", body
        # message may be in "message", "detail" (str) or detail.message
        detail = body.get("detail")
        if isinstance(detail, str):
            msg = detail
        elif isinstance(detail, dict):
            msg = detail.get("message", "")
        else:
            msg = body.get("message", "")
        for opt in ("day", "week", "month"):
            assert opt in msg, f"missing {opt!r} in error message: {msg!r}"

    def test_invalid_range(self, admin_session):
        end = datetime.now(timezone.utc)
        start = end + timedelta(days=10)  # start > end
        r = admin_session.get(
            f"{API}/analytics/trends",
            params={
                "start_date": start.isoformat().replace("+00:00", "Z"),
                "end_date": end.isoformat().replace("+00:00", "Z"),
                "interval": "day",
            },
            timeout=10,
        )
        assert r.status_code == 400
        body = r.json()
        code = body.get("code")
        if code is None and isinstance(body.get("detail"), dict):
            code = body["detail"].get("code")
        assert code == "invalid_range", body

    def test_future_range_empty(self, admin_session):
        start = datetime.now(timezone.utc) + timedelta(days=30)
        end = start + timedelta(days=10)
        r = admin_session.get(
            f"{API}/analytics/trends",
            params={
                "start_date": start.isoformat().replace("+00:00", "Z"),
                "end_date": end.isoformat().replace("+00:00", "Z"),
                "interval": "day",
            },
            timeout=10,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["series"] == []

    def test_iso8601_z_and_offset_both_accepted(self, admin_session):
        start, end = self._range(20)
        s_z = start.isoformat().replace("+00:00", "Z")
        e_z = end.isoformat().replace("+00:00", "Z")
        s_off = start.isoformat()  # has +00:00
        e_off = end.isoformat()

        r1 = admin_session.get(
            f"{API}/analytics/trends",
            params={"start_date": s_z, "end_date": e_z, "interval": "day"},
            timeout=10,
        )
        r2 = admin_session.get(
            f"{API}/analytics/trends",
            params={"start_date": s_off, "end_date": e_off, "interval": "day"},
            timeout=10,
        )
        assert r1.status_code == 200, r1.text
        assert r2.status_code == 200, r2.text
        assert sum(b["event_count"] for b in r1.json()["series"]) == sum(
            b["event_count"] for b in r2.json()["series"]
        )


# --------------------------------------------------------------------- #
# Regression smoke — pre-existing endpoints still 200
# --------------------------------------------------------------------- #
class TestRegressionSmoke:
    @pytest.mark.parametrize(
        "path",
        [
            "/events",
            "/events/recent",
            "/events/stats",
            "/data-sources",
            "/notifications",
            "/alerts",
            "/import/status",
            "/auth/me",
            "/modules",
        ],
    )
    def test_endpoint_200(self, admin_session, path):
        r = admin_session.get(f"{API}{path}", timeout=15)
        assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"
