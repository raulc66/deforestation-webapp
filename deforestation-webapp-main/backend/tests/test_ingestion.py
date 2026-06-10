"""Iteration 6 - Ingestion module tests.

Tests for:
- POST /api/import/csv (multipart, source_id Form, defaults, auth, file size)
- GET /api/import/status (list, newest first)
- GET /api/import/status/{job_id} (single, 404 on missing)
- CSV validation (headers, row-level field errors, optional defaults)
- UTF-8 BOM handling, non-UTF-8 -> failed
- /api/modules/ingestion -> status='active'

Tests are best-effort cleanup: events created via import are deleted by
metadata.import_job_id, and import jobs themselves are left in place (read-only
collection in production).
"""
from __future__ import annotations

import io
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests


# -- BASE URL --------------------------------------------------------------- #
def _read_env_url() -> str:
    try:
        with open("/app/frontend/.env", "r") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    return ""


_RAW = os.environ.get("REACT_APP_BACKEND_URL") or _read_env_url()
assert _RAW, "REACT_APP_BACKEND_URL must be set"
BASE_URL = _RAW.rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@forestwatch.io"
ADMIN_PASSWORD = "ForestAdmin2026!"


# -- Fixtures --------------------------------------------------------------- #
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


@pytest.fixture(scope="module")
def csv_source_id(admin_session: requests.Session) -> str:
    r = admin_session.get(f"{API}/data-sources", timeout=10)
    assert r.status_code == 200
    for d in r.json():
        if d.get("type") == "csv":
            return d["id"]
    pytest.skip("No csv DataSource seeded")


# -- Helpers ---------------------------------------------------------------- #
HEADER = "title,country,region,latitude,longitude,event_type,severity,affected_area_ha,confidence,detected_at"


def _row(
    title="TEST_evt",
    country="Brazil",
    region="Amazon",
    lat=-3.5,
    lng=-62.2,
    et="logging",
    sev="high",
    area=12.5,
    conf=0.9,
    detected_at="2026-01-10T12:00:00Z",
):
    return f"{title},{country},{region},{lat},{lng},{et},{sev},{area},{conf},{detected_at}"


def _csv(rows: list[str], header: str = HEADER, bom: bool = False) -> bytes:
    body = (header + "\n" + "\n".join(rows) + "\n").encode("utf-8")
    if bom:
        body = b"\xef\xbb\xbf" + body
    return body


def _upload(session, content: bytes, filename="t.csv", source_id=None,
            content_type="text/csv"):
    files = {"file": (filename, content, content_type)}
    data = {}
    if source_id is not None:
        data["source_id"] = source_id
    return session.post(f"{API}/import/csv", files=files, data=data, timeout=60)


def _cleanup_events(session: requests.Session, job_id: str) -> None:
    # Best-effort: walk recent events and delete ones tagged with our job id.
    r = session.get(f"{API}/events", params={"limit": 200}, timeout=15)
    if r.status_code != 200:
        return
    for ev in r.json():
        meta = (ev.get("metadata") or {})
        if meta.get("import_job_id") == job_id:
            session.delete(f"{API}/events/{ev['id']}", timeout=10)


# -- Tests ------------------------------------------------------------------ #
class TestModuleInfo:
    def test_ingestion_module_active(self, admin_session):
        r = admin_session.get(f"{API}/modules/ingestion", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "ingestion"
        assert data["status"] == "active"
        caps = data.get("capabilities") or {}
        assert caps.get("csv_import") == "live"
        assert caps.get("scheduled_jobs") == "planned"


class TestAuth:
    def test_csv_upload_unauth_401(self):
        s = requests.Session()
        files = {"file": ("x.csv", _csv([_row()]), "text/csv")}
        r = s.post(f"{API}/import/csv", files=files, timeout=15)
        assert r.status_code == 401

    def test_status_list_unauth_401(self):
        s = requests.Session()
        r = s.get(f"{API}/import/status", timeout=15)
        assert r.status_code == 401


class TestSuccessfulImport:
    def test_happy_path_two_rows(self, admin_session, csv_source_id):
        body = _csv([
            _row(title="TEST_happy_a", lat=-3.4, lng=-62.1, conf=0.91),
            _row(title="TEST_happy_b", lat=-4.0, lng=-63.0, conf=0.55),
        ])
        r = _upload(admin_session, body, "happy.csv", source_id=csv_source_id)
        assert r.status_code == 200, r.text
        job = r.json()
        try:
            assert job["status"] == "completed"
            assert job["total_rows"] == 2
            assert job["success_count"] == 2
            assert job["error_count"] == 0
            assert job["errors"] == []
            assert job["duration_ms"] is not None and job["duration_ms"] >= 0
            assert job["completed_at"] is not None
            assert job["source_id"] == csv_source_id
            assert job["filename"] == "happy.csv"

            # Events retrievable + linked via metadata.import_job_id
            r2 = admin_session.get(f"{API}/events", params={"limit": 200}, timeout=15)
            assert r2.status_code == 200
            evs = [e for e in r2.json()
                   if (e.get("metadata") or {}).get("import_job_id") == job["id"]]
            assert len(evs) == 2
            titles = {e["title"] for e in evs}
            assert {"TEST_happy_a", "TEST_happy_b"} == titles
            # source joined
            for e in evs:
                assert e["source_id"] == csv_source_id
                assert e.get("source_name")  # joined name surfaced
        finally:
            _cleanup_events(admin_session, job["id"])

    def test_default_source_when_omitted(self, admin_session, csv_source_id):
        body = _csv([_row(title="TEST_default_src")])
        r = _upload(admin_session, body, "default.csv")
        assert r.status_code == 200
        job = r.json()
        try:
            assert job["status"] == "completed"
            assert job["source_id"] == csv_source_id  # Hansen seed
        finally:
            _cleanup_events(admin_session, job["id"])

    def test_optional_columns_defaults(self, admin_session, csv_source_id):
        # Drop confidence and detected_at columns entirely
        header = "title,country,region,latitude,longitude,event_type,severity,affected_area_ha"
        row = "TEST_optdef,Brazil,Amazon,-3.5,-62.1,logging,high,5.0"
        body = (header + "\n" + row + "\n").encode("utf-8")
        before = datetime.now(timezone.utc)
        r = _upload(admin_session, body, "optdef.csv", source_id=csv_source_id)
        after = datetime.now(timezone.utc)
        assert r.status_code == 200, r.text
        job = r.json()
        try:
            assert job["status"] == "completed", job
            # Find the created event
            r2 = admin_session.get(f"{API}/events", params={"limit": 200}, timeout=15)
            evs = [e for e in r2.json()
                   if (e.get("metadata") or {}).get("import_job_id") == job["id"]]
            assert len(evs) == 1
            ev = evs[0]
            assert ev["confidence"] == 0.8
            # detected_at should be ~ now (between before-1s and after+1s)
            dt = ev["detected_at"]
            if dt.endswith("Z"):
                dt = dt[:-1] + "+00:00"
            parsed = datetime.fromisoformat(dt)
            assert before.replace(microsecond=0) <= parsed <= after.replace(microsecond=0) \
                or abs((parsed - before).total_seconds()) < 10
        finally:
            _cleanup_events(admin_session, job["id"])

    def test_detected_at_plus0000_format(self, admin_session, csv_source_id):
        body = _csv([_row(title="TEST_plus00", detected_at="2026-01-05T08:30:00+00:00")])
        r = _upload(admin_session, body, "plus0.csv", source_id=csv_source_id)
        assert r.status_code == 200
        job = r.json()
        try:
            assert job["status"] == "completed"
        finally:
            _cleanup_events(admin_session, job["id"])

    def test_header_case_insensitive_and_trimmed(self, admin_session, csv_source_id):
        header = " Title , COUNTRY,region,Latitude,LONGITUDE,Event_Type,Severity, affected_area_ha "
        row = "TEST_caseh,Brazil,Amazon,-3.5,-62.1,logging,high,5.0"
        body = (header + "\n" + row + "\n").encode("utf-8")
        r = _upload(admin_session, body, "case.csv", source_id=csv_source_id)
        assert r.status_code == 200, r.text
        job = r.json()
        try:
            assert job["status"] == "completed", job
            assert job["success_count"] == 1
        finally:
            _cleanup_events(admin_session, job["id"])

    def test_utf8_bom_handled(self, admin_session, csv_source_id):
        body = _csv([_row(title="TEST_bom")], bom=True)
        r = _upload(admin_session, body, "bom.csv", source_id=csv_source_id)
        assert r.status_code == 200, r.text
        job = r.json()
        try:
            assert job["status"] == "completed"
            assert job["success_count"] == 1
        finally:
            _cleanup_events(admin_session, job["id"])


class TestSourceSelection:
    def test_explicit_source_id_used(self, admin_session, csv_source_id):
        body = _csv([_row(title="TEST_explicit_src")])
        r = _upload(admin_session, body, "exp.csv", source_id=csv_source_id)
        assert r.status_code == 200
        job = r.json()
        try:
            assert job["source_id"] == csv_source_id
            r2 = admin_session.get(f"{API}/events", params={"limit": 200}, timeout=15)
            evs = [e for e in r2.json()
                   if (e.get("metadata") or {}).get("import_job_id") == job["id"]]
            assert len(evs) == 1
            assert evs[0]["source_id"] == csv_source_id
            assert evs[0].get("source_name")
        finally:
            _cleanup_events(admin_session, job["id"])

    def test_nonexistent_source_id_returns_404(self, admin_session):
        body = _csv([_row(title="TEST_badsrc")])
        r = _upload(admin_session, body, "bad.csv",
                    source_id="000000000000000000000000")
        assert r.status_code == 404


class TestValidationErrors:
    def test_missing_required_columns_failed(self, admin_session, csv_source_id):
        header = "title,country,latitude,longitude"
        row = "X,Brazil,-3.5,-62.1"
        body = (header + "\n" + row + "\n").encode("utf-8")
        r = _upload(admin_session, body, "miss.csv", source_id=csv_source_id)
        assert r.status_code == 200, r.text
        job = r.json()
        assert job["status"] == "failed"
        assert job["success_count"] == 0
        assert job["error_count"] >= 1
        msg = job["errors"][0]["message"]
        # Should mention each missing column
        for col in ("region", "event_type", "severity", "affected_area_ha"):
            assert col in msg, f"missing col '{col}' not in error message: {msg}"

    def test_row_level_errors_partial(self, admin_session, csv_source_id):
        # 1 good row + 1 bad row -> partial
        good = _row(title="TEST_partial_good")
        bad = _row(title="TEST_partial_bad", lat=200, et="nope", sev="nope", country="")
        body = _csv([good, bad])
        r = _upload(admin_session, body, "partial.csv", source_id=csv_source_id)
        assert r.status_code == 200
        job = r.json()
        try:
            assert job["status"] == "partial", job
            assert job["total_rows"] == 2
            assert job["success_count"] == 1
            assert job["error_count"] >= 3  # at least lat + event_type + severity + country
            # Each error should have field name + message
            fields = {e["field"] for e in job["errors"]}
            assert "latitude" in fields
            assert "event_type" in fields
            assert "severity" in fields
            assert "country" in fields
            # All errors target row 3 (row 2 is good)
            for e in job["errors"]:
                assert e["row_number"] == 3
                assert e["message"]
        finally:
            _cleanup_events(admin_session, job["id"])

    def test_field_bounds(self, admin_session, csv_source_id):
        # All rows invalid - lat=91, lng=181, area=-1, conf=1.5
        rows = [
            _row(title="TEST_b1", lat=91),
            _row(title="TEST_b2", lng=181),
            _row(title="TEST_b3", area=-1),
            _row(title="TEST_b4", conf=1.5),
        ]
        body = _csv(rows)
        r = _upload(admin_session, body, "bounds.csv", source_id=csv_source_id)
        assert r.status_code == 200
        job = r.json()
        assert job["status"] == "failed"  # 0 success
        assert job["success_count"] == 0
        fields = {e["field"] for e in job["errors"]}
        assert {"latitude", "longitude", "affected_area_ha", "confidence"} <= fields

    def test_non_utf8_failed(self, admin_session, csv_source_id):
        body = b"\xff\xfe\x00\x00invalid binary content not csv"
        r = _upload(admin_session, body, "binary.csv",
                    source_id=csv_source_id, content_type="application/octet-stream")
        assert r.status_code == 200
        job = r.json()
        assert job["status"] == "failed"
        msgs = " ".join(e["message"] for e in job["errors"])
        assert "not valid UTF-8" in msgs

    def test_file_too_large_413(self, admin_session, csv_source_id):
        # 5MB + 1 byte
        body = b"a" * (5 * 1024 * 1024 + 1)
        r = _upload(admin_session, body, "big.csv", source_id=csv_source_id)
        assert r.status_code == 413


class TestStatusEndpoints:
    def test_get_status_list_newest_first(self, admin_session, csv_source_id):
        # Create two imports
        ids = []
        for i in range(2):
            body = _csv([_row(title=f"TEST_order_{i}")])
            r = _upload(admin_session, body, f"order{i}.csv", source_id=csv_source_id)
            assert r.status_code == 200
            ids.append(r.json()["id"])

        try:
            r = admin_session.get(f"{API}/import/status", timeout=15)
            assert r.status_code == 200
            jobs = r.json()
            assert isinstance(jobs, list)
            assert len(jobs) <= 20  # default limit
            # The two most recent should be ours, in reverse insertion order
            top_ids = [j["id"] for j in jobs[:2]]
            assert ids[1] == top_ids[0], f"expected newest first; got {top_ids} vs created {ids}"
            assert ids[0] == top_ids[1]

            # created_at descending
            from datetime import datetime as _dt
            def parse(s):
                return _dt.fromisoformat(s.replace("Z", "+00:00"))
            times = [parse(j["created_at"]) for j in jobs]
            assert times == sorted(times, reverse=True)
        finally:
            for jid in ids:
                _cleanup_events(admin_session, jid)

    def test_get_status_limit_param(self, admin_session):
        r = admin_session.get(f"{API}/import/status", params={"limit": 3}, timeout=15)
        assert r.status_code == 200
        assert len(r.json()) <= 3

    def test_get_status_by_id(self, admin_session, csv_source_id):
        body = _csv([
            _row(title="TEST_by_id_a"),
            _row(title="TEST_by_id_bad", lat=200),
        ])
        r = _upload(admin_session, body, "byid.csv", source_id=csv_source_id)
        assert r.status_code == 200
        job_id = r.json()["id"]
        try:
            r2 = admin_session.get(f"{API}/import/status/{job_id}", timeout=15)
            assert r2.status_code == 200
            full = r2.json()
            assert full["id"] == job_id
            assert full["status"] == "partial"
            # Full per-row error detail with field+message
            assert len(full["errors"]) >= 1
            err = full["errors"][0]
            assert "row_number" in err and "field" in err and "message" in err
        finally:
            _cleanup_events(admin_session, job_id)

    def test_get_status_nonexistent_404(self, admin_session):
        r = admin_session.get(f"{API}/import/status/{uuid.uuid4().hex}", timeout=10)
        assert r.status_code == 404


# -- Smoke: prior endpoints still work -------------------------------------- #
class TestRegressionSmoke:
    def test_events_listing(self, admin_session):
        r = admin_session.get(f"{API}/events", params={"limit": 20}, timeout=10)
        assert r.status_code == 200
        assert len(r.json()) == 20

    def test_events_recent(self, admin_session):
        r = admin_session.get(f"{API}/events/recent", params={"days": 30}, timeout=10)
        assert r.status_code == 200

    def test_data_sources(self, admin_session):
        r = admin_session.get(f"{API}/data-sources", timeout=10)
        assert r.status_code == 200
        assert len(r.json()) >= 6

    def test_notifications(self, admin_session):
        r = admin_session.get(f"{API}/notifications", timeout=10)
        assert r.status_code == 200

    def test_alerts_legacy(self, admin_session):
        r = admin_session.get(f"{API}/alerts", timeout=10)
        assert r.status_code == 200

    def test_auth_me(self, admin_session):
        r = admin_session.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL
