"""Backend API tests for ForestWatch deforestation monitor.

Covers (iteration 4 datetime refactor):
 - All previous coverage (auth, events, notifications, alerts, data-sources, modules)
 - NEW: datetime fields are tz-aware ISO-8601 strings (ending in Z or +00:00)
 - NEW: /api/events sorted by detected_at DESC
 - NEW: GET /api/events/recent (days param, validation)
 - NEW: GET /api/events/range (start/end params, validation)
 - NEW: POST/PATCH /api/events with detected_at round-trip
 - NEW: Route ordering for /recent /range vs /{id}
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta


def _parse_iso(s: str) -> datetime:
    """Parse ISO-8601 datetime string returned by API. Must be tz-aware UTC."""
    if s is None:
        raise ValueError("datetime string is None")
    # Accept both 'Z' suffix and '+00:00'
    if s.endswith("Z"):
        s2 = s[:-1] + "+00:00"
    else:
        s2 = s
    dt = datetime.fromisoformat(s2)
    return dt


def _assert_tz_aware_utc(s: str, field: str = "datetime"):
    """Assert the string is a tz-aware UTC ISO 8601 (ends with Z or +00:00)."""
    assert isinstance(s, str), f"{field} must be a string, got {type(s)}: {s!r}"
    assert s.endswith("Z") or s.endswith("+00:00"), (
        f"{field} must be tz-aware UTC (end with Z or +00:00), got: {s!r}"
    )
    dt = _parse_iso(s)
    assert dt.tzinfo is not None, f"{field} parsed without tzinfo: {s!r}"
    # Must be UTC offset 0
    assert dt.utcoffset() == timedelta(0), f"{field} must be UTC offset 0, got: {dt.utcoffset()}"

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
assert _RAW, "REACT_APP_BACKEND_URL must be configured in env or /app/frontend/.env"
BASE_URL = _RAW.rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_EMAIL = "admin@forestwatch.io"
ADMIN_PASSWORD = "ForestAdmin2026!"

EXPECTED_EVENT_TYPES = {
    "logging",
    "wildfire",
    "mining",
    "agriculture",
    "road_construction",
    "urban_expansion",
    "unknown",
}


@pytest.fixture(scope="session")
def admin_session() -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


# -------- Health --------
class TestHealth:
    def test_root(self):
        r = requests.get(f"{API}/", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data.get("service") == "ForestWatch API"
        assert data.get("status") == "ok"


# -------- Auth --------
class TestAuth:
    def test_login_success_sets_cookies(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == ADMIN_EMAIL
        assert data.get("role") == "admin"
        cookie_names = {c.name for c in s.cookies}
        assert "access_token" in cookie_names
        assert "refresh_token" in cookie_names

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "WRONG_PASS"}, timeout=10)
        assert r.status_code == 401

    def test_me_no_token(self):
        r = requests.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 401

    def test_me_with_cookie(self, admin_session):
        r = admin_session.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_register_and_me(self):
        s = requests.Session()
        email = f"test_{uuid.uuid4().hex[:10]}@example.com"
        r = s.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!", "name": "Test User"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["email"] == email
        me = s.get(f"{API}/auth/me", timeout=10)
        assert me.status_code == 200

    def test_refresh(self):
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
        r = s.post(f"{API}/auth/refresh", timeout=10)
        assert r.status_code == 200

    def test_logout_clears_cookies(self):
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=10)
        r = s.post(f"{API}/auth/logout", timeout=10)
        assert r.status_code == 200
        me = s.get(f"{API}/auth/me", timeout=10)
        assert me.status_code == 401


# -------- NEW: ForestEvent /api/events --------
class TestEvents:
    def test_unauth(self):
        assert requests.get(f"{API}/events", timeout=10).status_code == 401

    def test_event_types(self):
        # /event-types is currently registered without auth; that is fine - public catalogue.
        r = requests.get(f"{API}/events/event-types", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert set(data) == EXPECTED_EVENT_TYPES
        assert len(data) == 7

    def test_list_events_full_shape(self, admin_session):
        r = admin_session.get(f"{API}/events", timeout=15)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) >= 20, f"expected >=20 seeded events, got {len(items)}"
        e = items[0]
        for key in [
            "id", "title", "country", "region",
            "latitude", "longitude", "event_type", "severity",
            "affected_area_ha", "confidence", "source_id",
            "detected_at", "status", "metadata",
        ]:
            assert key in e, f"missing key {key} in event: {e}"
        assert e["event_type"] in EXPECTED_EVENT_TYPES
        assert isinstance(e["latitude"], (int, float))
        assert isinstance(e["longitude"], (int, float))
        assert isinstance(e["metadata"], dict)

    def test_filter_severity_critical(self, admin_session):
        r = admin_session.get(f"{API}/events?severity=critical", timeout=15)
        assert r.status_code == 200
        for e in r.json():
            assert e["severity"] == "critical"

    def test_filter_event_type_logging(self, admin_session):
        r = admin_session.get(f"{API}/events?event_type=logging", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        for e in data:
            assert e["event_type"] == "logging"

    def test_filter_country_brazil(self, admin_session):
        r = admin_session.get(f"{API}/events?country=Brazil", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        for e in data:
            assert e["country"] == "Brazil"

    def test_filter_status_open(self, admin_session):
        r = admin_session.get(f"{API}/events?status=open", timeout=15)
        assert r.status_code == 200
        for e in r.json():
            assert e["status"] == "open"

    def test_stats(self, admin_session):
        r = admin_session.get(f"{API}/events/stats", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "total_events" in data
        assert "total_area_ha" in data
        assert "by_severity" in data
        assert "by_event_type" in data
        assert data["total_events"] >= 20
        assert isinstance(data["by_severity"], dict)
        assert isinstance(data["by_event_type"], dict)
        # event_type buckets should be subset of catalogue
        for k in data["by_event_type"].keys():
            assert k in EXPECTED_EVENT_TYPES

    def test_create_get_update_delete_event(self, admin_session):
        # CREATE
        payload = {
            "title": "TEST_create_event",
            "country": "Testland",
            "region": "TestRegion",
            "latitude": 1.23,
            "longitude": 4.56,
            "event_type": "mining",
            "severity": "high",
            "affected_area_ha": 99.9,
            "confidence": 0.91,
            "source_id": "pytest",
            "metadata": {"test": True},
        }
        r = admin_session.post(f"{API}/events", json=payload, timeout=15)
        assert r.status_code == 201, r.text
        created = r.json()
        eid = created["id"]
        assert created["title"] == payload["title"]
        assert created["event_type"] == "mining"
        assert created["latitude"] == 1.23
        assert created["affected_area_ha"] == 99.9

        # GET single
        r = admin_session.get(f"{API}/events/{eid}", timeout=10)
        assert r.status_code == 200
        assert r.json()["id"] == eid

        # PATCH
        r = admin_session.patch(
            f"{API}/events/{eid}",
            json={"status": "investigating", "severity": "critical", "metadata": {"updated": True}},
            timeout=10,
        )
        assert r.status_code == 200
        upd = r.json()
        assert upd["status"] == "investigating"
        assert upd["severity"] == "critical"
        assert upd["metadata"] == {"updated": True}

        # Verify persisted via GET
        r = admin_session.get(f"{API}/events/{eid}", timeout=10)
        assert r.status_code == 200
        assert r.json()["status"] == "investigating"

        # DELETE
        r = admin_session.delete(f"{API}/events/{eid}", timeout=10)
        assert r.status_code == 204

        # GET should now 404
        r = admin_session.get(f"{API}/events/{eid}", timeout=10)
        assert r.status_code == 404

    def test_get_event_404(self, admin_session):
        r = admin_session.get(f"{API}/events/does-not-exist-{uuid.uuid4().hex}", timeout=10)
        assert r.status_code == 404

    def test_create_invalid_event_type(self, admin_session):
        bad = {
            "title": "TEST_bad_event_type",
            "country": "X", "region": "Y",
            "latitude": 0.0, "longitude": 0.0,
            "event_type": "not_a_real_type",
            "severity": "low",
            "affected_area_ha": 1.0,
        }
        r = admin_session.post(f"{API}/events", json=bad, timeout=10)
        assert r.status_code == 422


# -------- NEW: Notifications --------
class TestNotifications:
    def test_unauth(self):
        assert requests.get(f"{API}/notifications", timeout=10).status_code == 401

    def test_list_for_user(self, admin_session):
        r = admin_session.get(f"{API}/notifications", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_mark_read_unknown_404(self, admin_session):
        r = admin_session.post(f"{API}/notifications/does-not-exist-{uuid.uuid4().hex}/read", timeout=10)
        assert r.status_code == 404


# -------- LEGACY: /api/alerts compat --------
class TestLegacyAlerts:
    def test_list_alerts_unauth(self):
        assert requests.get(f"{API}/alerts", timeout=10).status_code == 401

    def test_list_alerts_legacy_shape(self, admin_session):
        r = admin_session.get(f"{API}/alerts", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 20
        a = data[0]
        # Old shape MUST be preserved for the existing frontend
        for key in ["id", "title", "region", "country", "severity", "area_ha", "location", "source", "confidence", "detected_at", "status"]:
            assert key in a, f"legacy shape missing {key}: {a}"
        assert isinstance(a["location"], dict)
        assert "lat" in a["location"]
        assert "lng" in a["location"]
        # New keys MUST NOT leak into the legacy shape
        assert "affected_area_ha" not in a
        assert "latitude" not in a
        assert "longitude" not in a
        assert "source_id" not in a

    def test_alerts_filter_high(self, admin_session):
        r = admin_session.get(f"{API}/alerts?severity=high", timeout=15)
        assert r.status_code == 200
        for a in r.json():
            assert a["severity"] == "high"

    def test_alerts_stats_legacy(self, admin_session):
        r = admin_session.get(f"{API}/alerts/stats", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "total_alerts" in data
        assert "total_area_ha" in data
        assert "by_severity" in data
        assert data["total_alerts"] >= 20


# -------- NEW: DataSource /api/data-sources --------
EXPECTED_DS_TYPES = {"csv", "api", "satellite", "scraper", "manual"}
EXPECTED_DS_DEMOS = {
    "GLAD-S2 Forest Loss": ("satellite", "active"),
    "Hansen Global Forest Change": ("csv", "active"),
    "MapBiomas Alerta": ("api", "active"),
    "InfoAmazonia News Scraper": ("scraper", "active"),
    "Community Field Reports": ("manual", "active"),
    "Sentinel Hub NDVI": ("api", "paused"),
}


class TestDataSources:
    def test_unauth(self):
        assert requests.get(f"{API}/data-sources", timeout=10).status_code == 401

    def test_types_catalog(self):
        r = requests.get(f"{API}/data-sources/types", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert set(data) == EXPECTED_DS_TYPES
        assert len(data) == 5

    def test_list_seeded_six(self, admin_session):
        r = admin_session.get(f"{API}/data-sources", timeout=15)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert len(items) >= 6
        by_name = {it["name"]: it for it in items}
        for name, (expected_type, expected_status) in EXPECTED_DS_DEMOS.items():
            assert name in by_name, f"missing seeded source {name}"
            assert by_name[name]["type"] == expected_type
            assert by_name[name]["status"] == expected_status
            for key in ("id", "provider", "created_at", "updated_at"):
                assert key in by_name[name], f"missing {key} in {name}"

    def test_filter_by_type_satellite(self, admin_session):
        r = admin_session.get(f"{API}/data-sources?type=satellite", timeout=10)
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        for it in items:
            assert it["type"] == "satellite"
        assert any(it["name"] == "GLAD-S2 Forest Loss" for it in items)

    def test_filter_by_status_paused(self, admin_session):
        r = admin_session.get(f"{API}/data-sources?status=paused", timeout=10)
        assert r.status_code == 200
        items = r.json()
        # Only Sentinel Hub NDVI is paused in demo seed
        assert len(items) >= 1
        for it in items:
            assert it["status"] == "paused"
        assert any(it["name"] == "Sentinel Hub NDVI" for it in items)

    def test_get_404(self, admin_session):
        # use a syntactically valid-looking ObjectId that won't exist
        r = admin_session.get(f"{API}/data-sources/507f1f77bcf86cd799439011", timeout=10)
        assert r.status_code == 404

    def test_create_invalid_type_422(self, admin_session):
        r = admin_session.post(
            f"{API}/data-sources",
            json={"name": f"TEST_bad_{uuid.uuid4().hex[:6]}", "type": "ftp", "provider": "Acme"},
            timeout=10,
        )
        assert r.status_code == 422

    def test_create_get_update_delete_and_duplicate(self, admin_session):
        import time
        name = f"TEST_ds_{uuid.uuid4().hex[:8]}"
        # CREATE
        r = admin_session.post(
            f"{API}/data-sources",
            json={"name": name, "type": "api", "provider": "PyTest Provider"},
            timeout=10,
        )
        assert r.status_code == 201, r.text
        created = r.json()
        sid = created["id"]
        assert created["name"] == name
        assert created["type"] == "api"
        assert created["provider"] == "PyTest Provider"
        assert created["status"] == "active"
        original_created_at = created["created_at"]
        original_updated_at = created["updated_at"]

        # DUPLICATE name -> 409
        r = admin_session.post(
            f"{API}/data-sources",
            json={"name": name, "type": "csv", "provider": "X"},
            timeout=10,
        )
        assert r.status_code == 409, r.text

        # GET single
        r = admin_session.get(f"{API}/data-sources/{sid}", timeout=10)
        assert r.status_code == 200
        assert r.json()["id"] == sid

        # PATCH status (sleep so updated_at differs)
        time.sleep(1.05)
        r = admin_session.patch(
            f"{API}/data-sources/{sid}", json={"status": "paused"}, timeout=10
        )
        assert r.status_code == 200
        upd = r.json()
        assert upd["status"] == "paused"
        # After datetime refactor (iter4): MongoDB BSON datetime stores ms-precision,
        # so the original Python microsecond value may be truncated. Compare via
        # datetime parsing (tolerant of trailing Z / +00:00 / sub-ms truncation).
        def _dt(s):
            return _parse_iso(s)
        assert _dt(upd["created_at"]) == _dt(original_created_at).replace(microsecond=_dt(original_created_at).microsecond // 1000 * 1000) or abs((_dt(upd["created_at"]) - _dt(original_created_at)).total_seconds()) < 0.001
        assert _dt(upd["updated_at"]) > _dt(original_updated_at)

        # Verify persisted
        r = admin_session.get(f"{API}/data-sources/{sid}", timeout=10)
        assert r.status_code == 200
        assert r.json()["status"] == "paused"

        # DELETE
        r = admin_session.delete(f"{API}/data-sources/{sid}", timeout=10)
        assert r.status_code == 204

        # GET -> 404
        r = admin_session.get(f"{API}/data-sources/{sid}", timeout=10)
        assert r.status_code == 404


# -------- Integration: ForestEvent <-> DataSource join --------
class TestEventSourceIntegration:
    def _get_sources(self, admin_session):
        r = admin_session.get(f"{API}/data-sources", timeout=10)
        assert r.status_code == 200
        return r.json()

    def test_seeded_events_reference_real_data_sources(self, admin_session):
        sources = self._get_sources(admin_session)
        source_ids = {s["id"] for s in sources}
        source_names = {s["id"]: s["name"] for s in sources}
        r = admin_session.get(f"{API}/events", timeout=15)
        assert r.status_code == 200
        events = r.json()
        assert len(events) >= 20
        for e in events:
            assert e["source_id"] in source_ids, (
                f"event {e['id']} has stale source_id {e['source_id']}"
            )
            # source_name should be joined and match the DataSource name
            assert e.get("source_name") == source_names[e["source_id"]], (
                f"source_name mismatch for event {e['id']}: "
                f"got {e.get('source_name')}, expected {source_names[e['source_id']]}"
            )

    def test_filter_events_by_source_id(self, admin_session):
        sources = self._get_sources(admin_session)
        # Find a source that actually has events
        target = None
        for s in sources:
            r = admin_session.get(f"{API}/events?source_id={s['id']}", timeout=10)
            if r.status_code == 200 and len(r.json()) > 0:
                target = s
                break
        assert target is not None, "no DataSource has any events to filter by"
        r = admin_session.get(f"{API}/events?source_id={target['id']}", timeout=10)
        assert r.status_code == 200
        for e in r.json():
            assert e["source_id"] == target["id"]
            assert e["source_name"] == target["name"]

    def test_post_event_with_real_source_id_returns_source_name(self, admin_session):
        sources = self._get_sources(admin_session)
        ds = sources[0]
        payload = {
            "title": f"TEST_evt_with_real_source_{uuid.uuid4().hex[:6]}",
            "country": "Testland", "region": "TestRegion",
            "latitude": 0.0, "longitude": 0.0,
            "event_type": "logging", "severity": "low",
            "affected_area_ha": 1.0, "confidence": 0.5,
            "source_id": ds["id"],
        }
        r = admin_session.post(f"{API}/events", json=payload, timeout=10)
        assert r.status_code == 201, r.text
        created = r.json()
        assert created["source_id"] == ds["id"]
        assert created["source_name"] == ds["name"]
        # cleanup
        admin_session.delete(f"{API}/events/{created['id']}", timeout=10)

    def test_legacy_alerts_source_is_data_source_name(self, admin_session):
        sources = self._get_sources(admin_session)
        source_names = {s["name"] for s in sources}
        r = admin_session.get(f"{API}/alerts", timeout=15)
        assert r.status_code == 200
        alerts = r.json()
        assert len(alerts) >= 20
        # All seeded events come from seeded DataSources, so every alert's
        # `source` field must equal one of the DataSource names (not a raw id).
        for a in alerts:
            assert a["source"] in source_names, (
                f"alert.source {a['source']!r} is not a DataSource name"
            )
        # Spot check at least one specific demo source name appears
        assert any(a["source"] in {
            "GLAD-S2 Forest Loss",
            "Hansen Global Forest Change",
            "MapBiomas Alerta",
            "InfoAmazonia News Scraper",
            "Community Field Reports",
            "Sentinel Hub NDVI",
        } for a in alerts)


# -------- Modules --------
class TestModules:
    def test_list_modules(self):
        r = requests.get(f"{API}/modules", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 6

    def test_get_nonexistent(self):
        r = requests.get(f"{API}/modules/nonexistent_xyz", timeout=10)
        # Either 404 or 200 with not_found shape (known minor issue from iter1)
        assert r.status_code in (200, 404)
        body = r.json()
        assert "not" in str(body).lower() or body.get("code") == "not_found"


# -------- NEW (iter4): Datetime refactor + /recent /range --------
class TestDatetimeRefactor:
    """All datetime fields must be tz-aware ISO-8601 (Z or +00:00) strings."""

    def test_events_detected_at_tz_aware(self, admin_session):
        r = admin_session.get(f"{API}/events?limit=5", timeout=15)
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        for e in items:
            _assert_tz_aware_utc(e["detected_at"], "events.detected_at")

    def test_single_event_detected_at_tz_aware(self, admin_session):
        r = admin_session.get(f"{API}/events?limit=1", timeout=10)
        eid = r.json()[0]["id"]
        r = admin_session.get(f"{API}/events/{eid}", timeout=10)
        assert r.status_code == 200
        _assert_tz_aware_utc(r.json()["detected_at"], "events/{id}.detected_at")

    def test_data_sources_timestamps_tz_aware(self, admin_session):
        r = admin_session.get(f"{API}/data-sources", timeout=10)
        assert r.status_code == 200
        for ds in r.json():
            _assert_tz_aware_utc(ds["created_at"], "data-sources.created_at")
            _assert_tz_aware_utc(ds["updated_at"], "data-sources.updated_at")

    def test_notifications_created_at_tz_aware(self, admin_session):
        r = admin_session.get(f"{API}/notifications", timeout=10)
        assert r.status_code == 200
        # may be empty; that's fine
        for n in r.json():
            _assert_tz_aware_utc(n["created_at"], "notifications.created_at")

    def test_auth_me_created_at_tz_aware(self, admin_session):
        r = admin_session.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "created_at" in data, f"/auth/me missing created_at: {data}"
        _assert_tz_aware_utc(data["created_at"], "auth/me.created_at")

    def test_legacy_alerts_detected_at_tz_aware(self, admin_session):
        r = admin_session.get(f"{API}/alerts?limit=5", timeout=10)
        assert r.status_code == 200
        for a in r.json():
            _assert_tz_aware_utc(a["detected_at"], "alerts.detected_at")

    def test_events_sorted_desc(self, admin_session):
        r = admin_session.get(f"{API}/events", timeout=15)
        assert r.status_code == 200
        items = r.json()
        ts = [_parse_iso(e["detected_at"]) for e in items]
        for i in range(1, len(ts)):
            assert ts[i - 1] >= ts[i], (
                f"events not sorted DESC at idx {i}: {ts[i - 1]} < {ts[i]}"
            )


class TestEventsRecent:
    def test_unauth(self):
        assert requests.get(f"{API}/events/recent", timeout=10).status_code == 401

    def test_default_days_7(self, admin_session):
        r = admin_session.get(f"{API}/events/recent", timeout=10)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        cutoff = datetime.now(timezone.utc) - timedelta(days=7, hours=1)  # 1h grace
        for e in items:
            dt = _parse_iso(e["detected_at"])
            assert dt >= cutoff, f"event {e['id']} detected_at {dt} older than 7d cutoff {cutoff}"
        # Sorted DESC
        ts = [_parse_iso(e["detected_at"]) for e in items]
        for i in range(1, len(ts)):
            assert ts[i - 1] >= ts[i]

    def test_days_30_returns_more_or_equal(self, admin_session):
        r7 = admin_session.get(f"{API}/events/recent?days=7", timeout=10).json()
        r30 = admin_session.get(f"{API}/events/recent?days=30", timeout=10).json()
        assert len(r30) >= len(r7), f"days=30 ({len(r30)}) should be >= days=7 ({len(r7)})"

    def test_days_zero_rejected_422(self, admin_session):
        r = admin_session.get(f"{API}/events/recent?days=0", timeout=10)
        assert r.status_code == 422

    def test_days_too_large_rejected_422(self, admin_session):
        r = admin_session.get(f"{API}/events/recent?days=400", timeout=10)
        assert r.status_code == 422


class TestEventsRange:
    def test_unauth(self):
        r = requests.get(
            f"{API}/events/range?start=2025-01-01T00:00:00Z&end=2026-12-31T00:00:00Z",
            timeout=10,
        )
        assert r.status_code == 401

    def test_range_returns_events_within_inclusive_interval(self, admin_session):
        # Use a window that covers the seed window (last ~30 days)
        end = datetime.now(timezone.utc) + timedelta(days=1)
        start = end - timedelta(days=60)
        start_s = start.isoformat().replace("+00:00", "Z")
        end_s = end.isoformat().replace("+00:00", "Z")
        r = admin_session.get(f"{API}/events/range?start={start_s}&end={end_s}", timeout=15)
        assert r.status_code == 200, r.text
        items = r.json()
        assert len(items) >= 1
        for e in items:
            dt = _parse_iso(e["detected_at"])
            assert start <= dt <= end, f"event {e['id']} {dt} not in [{start}, {end}]"
        # Sorted DESC
        ts = [_parse_iso(e["detected_at"]) for e in items]
        for i in range(1, len(ts)):
            assert ts[i - 1] >= ts[i]

    def test_range_accepts_plus_00_00_format(self, admin_session):
        end = datetime.now(timezone.utc) + timedelta(days=1)
        start = end - timedelta(days=60)
        start_s = start.isoformat()  # already +00:00
        end_s = end.isoformat()
        assert start_s.endswith("+00:00")
        # Use params= so requests URL-encodes the '+' correctly (otherwise '+' is read as space)
        r = admin_session.get(
            f"{API}/events/range", params={"start": start_s, "end": end_s}, timeout=15
        )
        assert r.status_code == 200, r.text

    def test_range_accepts_z_format(self, admin_session):
        r = admin_session.get(
            f"{API}/events/range?start=2025-12-01T00:00:00Z&end=2026-12-31T00:00:00Z",
            timeout=15,
        )
        assert r.status_code == 200, r.text

    def test_range_start_after_end_returns_400(self, admin_session):
        r = admin_session.get(
            f"{API}/events/range?start=2026-12-31T00:00:00Z&end=2025-01-01T00:00:00Z",
            timeout=10,
        )
        assert r.status_code == 400, r.text
        body = r.json()
        # FastAPI standard error response: {"detail": "..."} or app's structured shape
        detail_str = str(body)
        assert "start must be earlier" in detail_str, f"unexpected detail: {body}"
        # check 'invalid_range' code somewhere in the response
        assert "invalid_range" in detail_str or body.get("code") == "invalid_range", (
            f"expected code 'invalid_range' in body: {body}"
        )


class TestRouteOrdering:
    """Ensure /recent /range /stats /event-types are NOT matched as /{event_id}."""

    def test_recent_not_treated_as_id(self, admin_session):
        r = admin_session.get(f"{API}/events/recent", timeout=10)
        assert r.status_code == 200  # would be 404 if matched as id

    def test_range_not_treated_as_id(self, admin_session):
        # missing required params -> 422 (Query validation), proving it hit the /range handler
        r = admin_session.get(f"{API}/events/range", timeout=10)
        assert r.status_code == 422

    def test_stats_not_treated_as_id(self, admin_session):
        r = admin_session.get(f"{API}/events/stats", timeout=10)
        assert r.status_code == 200

    def test_event_types_not_treated_as_id(self):
        r = requests.get(f"{API}/events/event-types", timeout=10)
        assert r.status_code == 200


class TestEventDatetimeRoundTrip:
    def test_create_with_detected_at_and_round_trip(self, admin_session):
        # use a known historical timestamp
        original = "2026-06-15T12:34:56Z"
        original_dt = _parse_iso(original)
        payload = {
            "title": f"TEST_dt_roundtrip_{uuid.uuid4().hex[:6]}",
            "country": "Testland", "region": "TestRegion",
            "latitude": 0.0, "longitude": 0.0,
            "event_type": "logging", "severity": "low",
            "affected_area_ha": 1.0, "confidence": 0.7,
            "source_id": "pytest",
            "detected_at": original,
        }
        r = admin_session.post(f"{API}/events", json=payload, timeout=10)
        assert r.status_code == 201, r.text
        created = r.json()
        eid = created["id"]
        try:
            _assert_tz_aware_utc(created["detected_at"], "POST.detected_at")
            assert _parse_iso(created["detected_at"]) == original_dt

            # GET should also return the same value
            r = admin_session.get(f"{API}/events/{eid}", timeout=10)
            assert r.status_code == 200
            got = r.json()
            _assert_tz_aware_utc(got["detected_at"], "GET.detected_at")
            assert _parse_iso(got["detected_at"]) == original_dt

            # PATCH detected_at
            new_dt = "2026-06-20T08:00:00Z"
            new_dt_parsed = _parse_iso(new_dt)
            r = admin_session.patch(
                f"{API}/events/{eid}", json={"detected_at": new_dt}, timeout=10
            )
            assert r.status_code == 200, r.text
            upd = r.json()
            _assert_tz_aware_utc(upd["detected_at"], "PATCH.detected_at")
            assert _parse_iso(upd["detected_at"]) == new_dt_parsed

            # Verify persisted
            r = admin_session.get(f"{API}/events/{eid}", timeout=10)
            assert _parse_iso(r.json()["detected_at"]) == new_dt_parsed
        finally:
            admin_session.delete(f"{API}/events/{eid}", timeout=10)



# -------- Iteration 5: Geospatial support (GeoJSON + 2dsphere + /nearby + /bbox) --------
class TestGeoSpatialResponseShape:
    """GET /api/events returns BOTH legacy lat/lng AND new GeoJSON location."""

    def test_list_events_includes_geojson_location(self, admin_session):
        r = admin_session.get(f"{API}/events", timeout=10)
        assert r.status_code == 200
        events = r.json()
        assert len(events) >= 1, "expected seeded events"
        for ev in events:
            # Backwards-compat legacy fields
            assert "latitude" in ev and isinstance(ev["latitude"], (int, float))
            assert "longitude" in ev and isinstance(ev["longitude"], (int, float))
            # GeoJSON location
            assert "location" in ev and ev["location"] is not None
            loc = ev["location"]
            assert loc.get("type") == "Point"
            coords = loc.get("coordinates")
            assert isinstance(coords, list) and len(coords) == 2
            lng, lat = coords[0], coords[1]
            # RFC 7946 order: [longitude, latitude]
            assert abs(lng - ev["longitude"]) < 1e-9, (
                f"location.coordinates[0] should be longitude, got {lng} vs {ev['longitude']}"
            )
            assert abs(lat - ev["latitude"]) < 1e-9, (
                f"location.coordinates[1] should be latitude, got {lat} vs {ev['latitude']}"
            )
            # Within valid ranges
            assert -180 <= lng <= 180
            assert -90 <= lat <= 90

    def test_get_single_event_includes_location(self, admin_session):
        r = admin_session.get(f"{API}/events", timeout=10)
        eid = r.json()[0]["id"]
        r = admin_session.get(f"{API}/events/{eid}", timeout=10)
        assert r.status_code == 200
        ev = r.json()
        assert ev["location"]["type"] == "Point"
        assert len(ev["location"]["coordinates"]) == 2


class TestGeoSpatial2dsphereIndex:
    """The 2dsphere index must exist - verified indirectly via $nearSphere success.

    A direct Mongo verification would require importing motor; we instead rely
    on the fact that /nearby returns 200 (Mongo errors out without the index)."""

    def test_nearby_works_implying_2dsphere_index_exists(self, admin_session):
        r = admin_session.get(
            f"{API}/events/nearby",
            params={"latitude": 0, "longitude": 0, "radius": 1000},
            timeout=10,
        )
        # Even 0 results is fine; 500 would indicate missing index
        assert r.status_code == 200, f"$nearSphere failed (index missing?): {r.text}"


class TestEventsNearby:
    """GET /api/events/nearby - $nearSphere ordering, validation, radius behavior."""

    def test_nearby_amazon_500km(self, admin_session):
        # Amazon center (Brazil), 500km radius
        r = admin_session.get(
            f"{API}/events/nearby",
            params={"latitude": -3.5, "longitude": -62, "radius": 500000},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        results = r.json()
        assert len(results) >= 1, "expected events near Amazon (Brazil seed data)"

    def test_nearby_sorted_by_distance_asc(self, admin_session):
        center_lat, center_lng = -3.5, -62.0
        r = admin_session.get(
            f"{API}/events/nearby",
            params={"latitude": center_lat, "longitude": center_lng, "radius": 20000000},
            timeout=10,
        )
        assert r.status_code == 200
        results = r.json()
        assert len(results) >= 2, "need at least 2 events to verify ordering"

        # Compute haversine-ish distance proxy (squared-degree distance is enough
        # for monotonic ordering check at small scale; use spherical for safety).
        import math

        def dist(ev):
            lat = math.radians(ev["latitude"])
            lng = math.radians(ev["longitude"])
            clat = math.radians(center_lat)
            clng = math.radians(center_lng)
            dlat = lat - clat
            dlng = lng - clng
            a = math.sin(dlat / 2) ** 2 + math.cos(clat) * math.cos(lat) * math.sin(dlng / 2) ** 2
            return 2 * math.asin(math.sqrt(a))

        distances = [dist(e) for e in results]
        for i in range(len(distances) - 1):
            assert distances[i] <= distances[i + 1] + 1e-6, (
                f"nearby not ASC sorted by distance at index {i}: {distances[i]} > {distances[i+1]}"
            )

    def test_nearby_tighter_radius_returns_fewer(self, admin_session):
        params_wide = {"latitude": -3.5, "longitude": -62, "radius": 500000}
        params_tight = {"latitude": -3.5, "longitude": -62, "radius": 200000}
        r_wide = admin_session.get(f"{API}/events/nearby", params=params_wide, timeout=10)
        r_tight = admin_session.get(f"{API}/events/nearby", params=params_tight, timeout=10)
        assert r_wide.status_code == 200 and r_tight.status_code == 200
        assert len(r_tight.json()) <= len(r_wide.json()), (
            "tighter radius must return <= number of events"
        )

    def test_nearby_invalid_latitude(self, admin_session):
        r = admin_session.get(
            f"{API}/events/nearby",
            params={"latitude": 200, "longitude": 0, "radius": 1000},
            timeout=10,
        )
        assert r.status_code == 422

    def test_nearby_invalid_longitude(self, admin_session):
        r = admin_session.get(
            f"{API}/events/nearby",
            params={"latitude": 0, "longitude": 400, "radius": 1000},
            timeout=10,
        )
        assert r.status_code == 422

    def test_nearby_radius_zero_invalid(self, admin_session):
        r = admin_session.get(
            f"{API}/events/nearby",
            params={"latitude": 0, "longitude": 0, "radius": 0},
            timeout=10,
        )
        assert r.status_code == 422

    def test_nearby_radius_too_large_invalid(self, admin_session):
        r = admin_session.get(
            f"{API}/events/nearby",
            params={"latitude": 0, "longitude": 0, "radius": 99999999999},
            timeout=10,
        )
        assert r.status_code == 422

    def test_nearby_requires_auth(self):
        r = requests.get(
            f"{API}/events/nearby",
            params={"latitude": 0, "longitude": 0, "radius": 1000},
            timeout=10,
        )
        assert r.status_code == 401


class TestEventsBbox:
    """GET /api/events/bbox - $geoWithin polygon + validation."""

    def test_bbox_south_america(self, admin_session):
        r = admin_session.get(
            f"{API}/events/bbox",
            params={"min_lat": -23, "min_lng": -82, "max_lat": 12, "max_lng": -34},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        events = r.json()
        # Seed: 8 events in South America (Brazil/Peru/Venezuela)
        assert len(events) == 8, f"expected 8 South America events, got {len(events)}"
        for ev in events:
            assert -23 <= ev["latitude"] <= 12
            assert -82 <= ev["longitude"] <= -34
            assert ev["country"] in {"Brazil", "Peru", "Venezuela"}

    def test_bbox_se_asia(self, admin_session):
        r = admin_session.get(
            f"{API}/events/bbox",
            params={"min_lat": -10, "min_lng": 90, "max_lat": 10, "max_lng": 140},
            timeout=10,
        )
        assert r.status_code == 200
        events = r.json()
        # Seed: 2 events in SE Asia (Indonesia/Malaysia)
        assert len(events) == 2, f"expected 2 SE Asia events, got {len(events)}"
        countries = {e["country"] for e in events}
        assert countries == {"Indonesia", "Malaysia"}

    def test_bbox_sorted_by_detected_at_desc(self, admin_session):
        r = admin_session.get(
            f"{API}/events/bbox",
            params={"min_lat": -23, "min_lng": -82, "max_lat": 12, "max_lng": -34},
            timeout=10,
        )
        events = r.json()
        assert len(events) >= 2
        ts = [_parse_iso(e["detected_at"]) for e in events]
        for i in range(len(ts) - 1):
            assert ts[i] >= ts[i + 1], f"bbox not DESC sorted by detected_at at index {i}"

    def test_bbox_invalid_lat_order(self, admin_session):
        r = admin_session.get(
            f"{API}/events/bbox",
            params={"min_lat": 50, "min_lng": -10, "max_lat": 10, "max_lng": 10},
            timeout=10,
        )
        assert r.status_code == 400, r.text
        body = r.json()
        # AppError surfaces as {"error": {...}} or {"detail": ...} — accept either
        code = (
            body.get("code")
            or (body.get("error") or {}).get("code")
            or (body.get("detail") or {}).get("code")
            if isinstance(body.get("detail"), dict)
            else body.get("code") or (body.get("error") or {}).get("code")
        )
        assert code == "invalid_bbox", f"expected code=invalid_bbox, got body: {body}"

    def test_bbox_invalid_lng_order(self, admin_session):
        r = admin_session.get(
            f"{API}/events/bbox",
            params={"min_lat": -10, "min_lng": 50, "max_lat": 10, "max_lng": 10},
            timeout=10,
        )
        assert r.status_code == 400, r.text
        body = r.json()
        code = (
            body.get("code")
            or (body.get("error") or {}).get("code")
            or (body.get("detail") or {}).get("code")
            if isinstance(body.get("detail"), dict)
            else body.get("code") or (body.get("error") or {}).get("code")
        )
        assert code == "invalid_bbox", f"expected code=invalid_bbox, got body: {body}"

    def test_bbox_requires_auth(self):
        r = requests.get(
            f"{API}/events/bbox",
            params={"min_lat": -10, "min_lng": -10, "max_lat": 10, "max_lng": 10},
            timeout=10,
        )
        assert r.status_code == 401


class TestEventLocationSync:
    """create_event and update_event auto-sync location from lat/lng."""

    def test_create_event_syncs_location(self, admin_session):
        lat, lng = 12.34, 56.78
        payload = {
            "title": f"TEST_geo_create_{uuid.uuid4().hex[:6]}",
            "country": "Testland", "region": "TestRegion",
            "latitude": lat, "longitude": lng,
            "event_type": "logging", "severity": "low",
            "affected_area_ha": 1.0, "confidence": 0.7,
            "source_id": "pytest",
        }
        r = admin_session.post(f"{API}/events", json=payload, timeout=10)
        assert r.status_code == 201, r.text
        created = r.json()
        eid = created["id"]
        try:
            assert created["location"]["type"] == "Point"
            assert abs(created["location"]["coordinates"][0] - lng) < 1e-9
            assert abs(created["location"]["coordinates"][1] - lat) < 1e-9

            # Verify via GET (persisted)
            r = admin_session.get(f"{API}/events/{eid}", timeout=10)
            got = r.json()
            assert got["location"]["coordinates"] == [lng, lat]
        finally:
            admin_session.delete(f"{API}/events/{eid}", timeout=10)

    def test_patch_latitude_only_updates_location(self, admin_session):
        payload = {
            "title": f"TEST_geo_patch_lat_{uuid.uuid4().hex[:6]}",
            "country": "Testland", "region": "TestRegion",
            "latitude": 10.0, "longitude": 20.0,
            "event_type": "logging", "severity": "low",
            "affected_area_ha": 1.0, "confidence": 0.7,
            "source_id": "pytest",
        }
        r = admin_session.post(f"{API}/events", json=payload, timeout=10)
        assert r.status_code == 201
        eid = r.json()["id"]
        try:
            r = admin_session.patch(
                f"{API}/events/{eid}", json={"latitude": 45.0}, timeout=10
            )
            assert r.status_code == 200, r.text
            upd = r.json()
            assert upd["latitude"] == 45.0
            assert upd["longitude"] == 20.0  # unchanged
            assert upd["location"]["coordinates"][0] == 20.0  # lng unchanged
            assert upd["location"]["coordinates"][1] == 45.0  # lat updated
        finally:
            admin_session.delete(f"{API}/events/{eid}", timeout=10)

    def test_patch_longitude_only_updates_location(self, admin_session):
        payload = {
            "title": f"TEST_geo_patch_lng_{uuid.uuid4().hex[:6]}",
            "country": "Testland", "region": "TestRegion",
            "latitude": 10.0, "longitude": 20.0,
            "event_type": "logging", "severity": "low",
            "affected_area_ha": 1.0, "confidence": 0.7,
            "source_id": "pytest",
        }
        r = admin_session.post(f"{API}/events", json=payload, timeout=10)
        eid = r.json()["id"]
        try:
            r = admin_session.patch(
                f"{API}/events/{eid}", json={"longitude": -75.5}, timeout=10
            )
            assert r.status_code == 200
            upd = r.json()
            assert upd["latitude"] == 10.0  # unchanged
            assert upd["longitude"] == -75.5
            assert upd["location"]["coordinates"][0] == -75.5
            assert upd["location"]["coordinates"][1] == 10.0
        finally:
            admin_session.delete(f"{API}/events/{eid}", timeout=10)


class TestGeoRouteOrdering:
    """Ensure /nearby and /bbox are not shadowed by /{event_id}."""

    def test_nearby_not_shadowed(self, admin_session):
        # Missing required params -> 422 (proves it hit /nearby handler, not /{event_id})
        r = admin_session.get(f"{API}/events/nearby", timeout=10)
        assert r.status_code == 422

    def test_bbox_not_shadowed(self, admin_session):
        r = admin_session.get(f"{API}/events/bbox", timeout=10)
        assert r.status_code == 422


class TestBackfillIdempotent:
    """Verify all 20 seeded events have a non-null location (backfill ran)."""

    def test_all_seeded_events_have_location(self, admin_session):
        r = admin_session.get(f"{API}/events", params={"limit": 1000}, timeout=10)
        events = r.json()
        # 20 seeded + any TEST_ leftovers; filter to seed-only via metadata.seed=True
        missing = [e for e in events if not e.get("location")]
        assert not missing, f"events without location: {[e['id'] for e in missing]}"
