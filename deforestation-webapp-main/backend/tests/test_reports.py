"""Comprehensive test suite for the Operational Reporting module.

Tests cover:
  - report_models: enums and pydantic validation
  - report_repository: CRUD operations (mocked MongoDB)
  - csv_export: CSV file generation
  - json_export: JSON file generation
  - pdf_generator: PDF generation (skipped when ReportLab not installed)
  - report_service: data gathering, lifecycle, scheduled generation
  - report_routes: API endpoints (TestClient)
  - scheduler integration: report_svc wired into SchedulerService
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.base import utcnow
from app.modules.reports.csv_export import generate_report_csv
from app.modules.reports.json_export import generate_report_json
from app.modules.reports.report_models import (
    GenerateReportRequest,
    ReportFormat,
    ReportStatus,
    ReportType,
)
from app.modules.reports.report_repository import ReportRepository
from app.modules.reports.report_service import ReportService, _build_summary

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
PERIOD_START = NOW - timedelta(days=1)
PERIOD_END = NOW


def _make_fake_report(
    *,
    report_id="aaaa0000000000000000aaaa",
    report_type="daily",
    report_format="pdf",
    status="pending",
    file_path=None,
    file_size=None,
    generation_time_ms=None,
    summary=None,
    error=None,
):
    return {
        "id": report_id,
        "type": report_type,
        "format": report_format,
        "status": status,
        "generated_at": NOW,
        "period_start": PERIOD_START,
        "period_end": PERIOD_END,
        "file_path": file_path,
        "file_size": file_size,
        "generation_time_ms": generation_time_ms,
        "summary": summary,
        "error": error,
    }


def _make_report_repo():
    repo = MagicMock(spec=ReportRepository)
    repo.create = AsyncMock(return_value=_make_fake_report())
    repo.get_by_id = AsyncMock(return_value=_make_fake_report(status="complete", file_size=1000, generation_time_ms=500))
    repo.list_all = AsyncMock(return_value=[_make_fake_report(status="complete")])
    repo.update_status = AsyncMock()
    repo.update_complete = AsyncMock()
    repo.update_failed = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    repo.find_by_type_and_period_start = AsyncMock(return_value=None)
    return repo


def _make_minimal_report_data(report_type: str = "daily") -> dict:
    return {
        "report_type": report_type,
        "period_start": PERIOD_START,
        "period_end": PERIOD_END,
        "generated_at": NOW,
        "overview": {
            "total_events": 10,
            "open_events": 3,
            "resolved_events": 7,
            "average_confidence": 0.8,
        },
        "anomalies": {"anomalies": [
            {"region": "Cluj", "anomaly_score": 0.9, "deviation": 2.5, "severity": "high"},
        ]},
        "land_cover": {"distribution": {"forest": 5, "urban": 2, "unknown": 1}},
        "intelligence_events": {
            "active": [
                {
                    "region": "Cluj",
                    "event_type": "sustained_hotspot",
                    "severity": "high",
                    "escalation_level": "persistent",
                    "trend": "worsening",
                    "priority_score": 0.85,
                }
            ],
            "resolved": [{"region": "Brasov", "event_type": "anomaly_cluster", "severity": "medium", "priority_score": 0.5}],
        },
        "risk": {
            "regions": [
                {"region": "Cluj", "risk_score": 0.75, "risk_level": "High", "anomaly_count": 3},
                {"region": "Brasov", "risk_score": 0.45, "risk_level": "Moderate", "anomaly_count": 1},
            ]
        },
        "weather": {
            "regions": [
                {
                    "region": "Cluj",
                    "temperature": 28.0,
                    "humidity": 35.0,
                    "wind_speed": 20.0,
                    "precipitation": 0.0,
                    "weather_code": 0,
                    "updated_at": NOW,
                }
            ]
        },
        "daily_activity": {
            "days": [
                {"date": "2026-05-31", "events": 4, "anomalies": 1},
                {"date": "2026-06-01", "events": 6, "anomalies": 2},
            ]
        },
        "regional_history": [
            {
                "region": "Cluj",
                "events_last_30d": 15,
                "events_previous_30d": 10,
                "change_percent": 50.0,
                "trend": "increasing",
            }
        ],
        "monthly_summary": {
            "months": [
                {"month": "2026-05", "events": 20, "anomalies": 4, "forest_events": 12}
            ]
        },
        "hotspots": [
            {"region": "Cluj", "detections": 100, "average_priority": 0.8, "highest_severity": "high"}
        ],
        "notifications": [
            {"provider": "discord", "event_type": "new_anomaly", "region": "Cluj", "success": True, "sent_at": NOW}
        ],
        "ingestion_runs": [
            {"source": "NASA FIRMS", "status": "success", "events_fetched": 10, "events_inserted": 5, "duration_seconds": 2.5, "started_at": NOW}
        ],
        "summary": {
            "total_events": 10,
            "open_events": 3,
            "active_intel_events": 1,
            "resolved_intel_events": 1,
            "anomaly_count": 1,
            "highest_risk_region": "Cluj",
            "highest_risk_score": 0.75,
            "notifications_sent": 1,
            "notifications_success": 1,
            "ingestion_runs": 1,
            "ingestion_success": 1,
        },
    }


def _make_report_service(
    *,
    report_repo=None,
    reports_dir=None,
    analytics_svc=None,
    intel_svc=None,
    risk_svc=None,
    history_svc=None,
    notif_history_repo=None,
    runs_repo=None,
    weather_svc=None,
):
    if report_repo is None:
        report_repo = _make_report_repo()
    if reports_dir is None:
        tmp = tempfile.mkdtemp()
        reports_dir = Path(tmp)

    def _async_svc(return_val):
        svc = MagicMock()
        for method_name in (
            "get_overview", "get_anomalies", "get_land_cover_distribution",
            "get_events", "get_risk",
            "daily_activity", "regional_history", "hotspot_history", "monthly_summary",
        ):
            setattr(svc, method_name, AsyncMock(return_value=return_val))
        return svc

    if analytics_svc is None:
        analytics_svc = _async_svc({})
        analytics_svc.get_overview = AsyncMock(return_value={"total_events": 5})
        analytics_svc.get_anomalies = AsyncMock(return_value={"anomalies": []})
        analytics_svc.get_land_cover_distribution = AsyncMock(return_value={"distribution": {}})
    if intel_svc is None:
        intel_svc = MagicMock()
        intel_svc.get_events = AsyncMock(return_value={"active": [], "resolved": []})
    if risk_svc is None:
        risk_svc = MagicMock()
        risk_svc.get_risk = AsyncMock(return_value={"regions": []})
    if history_svc is None:
        history_svc = MagicMock()
        history_svc.daily_activity = AsyncMock(return_value={"days": []})
        history_svc.regional_history = AsyncMock(return_value=[])
        history_svc.hotspot_history = AsyncMock(return_value=[])
        history_svc.monthly_summary = AsyncMock(return_value={"months": []})
    if notif_history_repo is None:
        notif_history_repo = MagicMock()
        notif_history_repo.list_recent = AsyncMock(return_value=[])
    if runs_repo is None:
        runs_repo = MagicMock()
        runs_repo.list_runs = AsyncMock(return_value=[])

    return ReportService(
        report_repo=report_repo,
        analytics_svc=analytics_svc,
        intel_svc=intel_svc,
        risk_svc=risk_svc,
        history_svc=history_svc,
        notif_history_repo=notif_history_repo,
        runs_repo=runs_repo,
        weather_svc=weather_svc,
        reports_dir=reports_dir,
    )


# ===========================================================================
# report_models
# ===========================================================================

class TestReportModels:
    def test_report_type_values(self):
        assert ReportType.DAILY.value == "daily"
        assert ReportType.WEEKLY.value == "weekly"
        assert ReportType.MONTHLY.value == "monthly"
        assert ReportType.ON_DEMAND.value == "on_demand"

    def test_report_format_values(self):
        assert ReportFormat.PDF.value == "pdf"
        assert ReportFormat.CSV.value == "csv"
        assert ReportFormat.JSON.value == "json"

    def test_report_status_values(self):
        assert ReportStatus.PENDING.value == "pending"
        assert ReportStatus.GENERATING.value == "generating"
        assert ReportStatus.COMPLETE.value == "complete"
        assert ReportStatus.FAILED.value == "failed"

    def test_generate_request_defaults(self):
        req = GenerateReportRequest(type=ReportType.DAILY)
        assert req.format == ReportFormat.PDF
        assert req.period_start is None
        assert req.period_end is None

    def test_generate_request_full(self):
        req = GenerateReportRequest(
            type="weekly",
            format="csv",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )
        assert req.type == ReportType.WEEKLY
        assert req.format == ReportFormat.CSV


# ===========================================================================
# _build_summary
# ===========================================================================

class TestBuildSummary:
    def test_empty_data(self):
        summary = _build_summary({})
        assert summary["total_events"] == 0
        assert summary["active_intel_events"] == 0

    def test_populated_data(self):
        data = _make_minimal_report_data()
        summary = _build_summary(data)
        assert summary["total_events"] == 10
        assert summary["active_intel_events"] == 1
        assert summary["resolved_intel_events"] == 1
        assert summary["anomaly_count"] == 1
        assert summary["highest_risk_region"] == "Cluj"
        assert abs(summary["highest_risk_score"] - 0.75) < 1e-6
        assert summary["notifications_sent"] == 1
        assert summary["notifications_success"] == 1
        assert summary["ingestion_runs"] == 1
        assert summary["ingestion_success"] == 1

    def test_missing_risk_regions(self):
        data = {"risk": {}}
        summary = _build_summary(data)
        assert summary["highest_risk_region"] is None
        assert summary["highest_risk_score"] is None

    def test_failed_notifications_counted(self):
        data = {
            "notifications": [
                {"success": True},
                {"success": False},
                {"success": False},
            ]
        }
        summary = _build_summary(data)
        assert summary["notifications_sent"] == 3
        assert summary["notifications_success"] == 1


# ===========================================================================
# ReportRepository (mocked MongoDB)
# ===========================================================================

class TestReportRepository:
    def _make_repo(self):
        db = MagicMock()
        col = MagicMock()
        db.__getitem__ = MagicMock(return_value=col)
        return ReportRepository(db), col

    @pytest.mark.anyio
    async def test_create_inserts_document(self):
        from bson import ObjectId

        repo, col = self._make_repo()
        inserted_id = ObjectId()
        col.insert_one = AsyncMock(return_value=MagicMock(inserted_id=inserted_id))

        record = await repo.create(
            report_type="daily",
            report_format="pdf",
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )
        assert record["type"] == "daily"
        assert record["format"] == "pdf"
        assert record["status"] == "pending"
        assert record["id"] == str(inserted_id)
        col.insert_one.assert_called_once()

    @pytest.mark.anyio
    async def test_update_status(self):
        repo, col = self._make_repo()
        col.update_one = AsyncMock()
        await repo.update_status("507f1f77bcf86cd799439011", "generating")
        col.update_one.assert_called_once()

    @pytest.mark.anyio
    async def test_update_complete(self):
        repo, col = self._make_repo()
        col.update_one = AsyncMock()
        await repo.update_complete(
            "507f1f77bcf86cd799439011", "/path/file.pdf", 1024, 500, {}
        )
        call_args = col.update_one.call_args
        assert call_args[0][1]["$set"]["status"] == "complete"
        assert call_args[0][1]["$set"]["file_size"] == 1024

    @pytest.mark.anyio
    async def test_update_failed(self):
        repo, col = self._make_repo()
        col.update_one = AsyncMock()
        await repo.update_failed("507f1f77bcf86cd799439011", "some error")
        call_args = col.update_one.call_args
        assert call_args[0][1]["$set"]["status"] == "failed"
        assert call_args[0][1]["$set"]["error"] == "some error"

    @pytest.mark.anyio
    async def test_delete_returns_true_when_deleted(self):
        repo, col = self._make_repo()
        col.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
        result = await repo.delete("507f1f77bcf86cd799439011")
        assert result is True

    @pytest.mark.anyio
    async def test_delete_returns_false_when_not_found(self):
        repo, col = self._make_repo()
        col.delete_one = AsyncMock(return_value=MagicMock(deleted_count=0))
        result = await repo.delete("507f1f77bcf86cd799439011")
        assert result is False

    @pytest.mark.anyio
    async def test_get_by_id_returns_none_for_invalid(self):
        repo, col = self._make_repo()
        result = await repo.get_by_id("not-an-object-id")
        assert result is None

    @pytest.mark.anyio
    async def test_list_all_returns_list(self):
        repo, col = self._make_repo()
        from bson import ObjectId

        mock_doc = {
            "_id": ObjectId(),
            "type": "daily", "format": "pdf", "status": "complete",
            "generated_at": NOW, "period_start": PERIOD_START, "period_end": PERIOD_END,
            "file_path": None, "file_size": None, "generation_time_ms": None,
            "summary": None, "error": None,
        }

        async def mock_async_iter(*args, **kwargs):
            yield mock_doc

        cursor = MagicMock()
        cursor.__aiter__ = mock_async_iter
        cursor.sort = MagicMock(return_value=cursor)
        cursor.limit = MagicMock(return_value=cursor)
        col.find = MagicMock(return_value=cursor)

        result = await repo.list_all(10)
        assert len(result) == 1
        assert result[0]["type"] == "daily"


# ===========================================================================
# CSV export
# ===========================================================================

class TestCsvExport:
    def test_generates_file(self, tmp_path):
        out = tmp_path / "report.csv"
        data = _make_minimal_report_data()
        generate_report_csv(data, str(out))
        assert out.exists()
        assert out.stat().st_size > 0

    def test_contains_section_headers(self, tmp_path):
        out = tmp_path / "report.csv"
        data = _make_minimal_report_data()
        generate_report_csv(data, str(out))
        content = out.read_text(encoding="utf-8")
        assert "OVERVIEW" in content
        assert "REGIONAL RISK" in content
        assert "ANOMALIES" in content
        assert "WEATHER SUMMARY" in content

    def test_contains_region_data(self, tmp_path):
        out = tmp_path / "report.csv"
        data = _make_minimal_report_data()
        generate_report_csv(data, str(out))
        content = out.read_text(encoding="utf-8")
        assert "Cluj" in content

    def test_empty_data_produces_valid_csv(self, tmp_path):
        out = tmp_path / "empty.csv"
        generate_report_csv({}, str(out))
        assert out.exists()

    def test_csv_is_valid_utf8(self, tmp_path):
        out = tmp_path / "utf8.csv"
        data = _make_minimal_report_data()
        generate_report_csv(data, str(out))
        content = out.read_bytes().decode("utf-8")
        assert len(content) > 0

    def test_hotspot_rankings_section(self, tmp_path):
        out = tmp_path / "report.csv"
        data = _make_minimal_report_data()
        generate_report_csv(data, str(out))
        content = out.read_text(encoding="utf-8")
        assert "HOTSPOT RANKINGS" in content

    def test_notifications_section(self, tmp_path):
        out = tmp_path / "report.csv"
        data = _make_minimal_report_data()
        generate_report_csv(data, str(out))
        content = out.read_text(encoding="utf-8")
        assert "NOTIFICATIONS" in content


# ===========================================================================
# JSON export
# ===========================================================================

class TestJsonExport:
    def test_generates_valid_json(self, tmp_path):
        out = tmp_path / "report.json"
        data = _make_minimal_report_data()
        generate_report_json(data, str(out))
        assert out.exists()
        parsed = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict)

    def test_has_required_sections(self, tmp_path):
        out = tmp_path / "report.json"
        generate_report_json(_make_minimal_report_data(), str(out))
        parsed = json.loads(out.read_text())
        for key in ("meta", "summary", "overview", "intelligence_events", "risk", "weather", "hotspots"):
            assert key in parsed, f"Missing key: {key}"

    def test_meta_contains_period(self, tmp_path):
        out = tmp_path / "report.json"
        generate_report_json(_make_minimal_report_data(), str(out))
        parsed = json.loads(out.read_text())
        assert parsed["meta"]["report_type"] == "daily"
        assert "period_start" in parsed["meta"]
        assert "period_end" in parsed["meta"]

    def test_datetimes_serialized_as_strings(self, tmp_path):
        out = tmp_path / "report.json"
        generate_report_json(_make_minimal_report_data(), str(out))
        content = out.read_text()
        # Datetimes should appear as ISO strings, not Python repr
        assert "datetime.datetime" not in content

    def test_empty_data_produces_valid_json(self, tmp_path):
        out = tmp_path / "empty.json"
        generate_report_json({}, str(out))
        parsed = json.loads(out.read_text())
        assert parsed["meta"]["report_type"] == "on_demand"

    def test_report_data_preserved(self, tmp_path):
        out = tmp_path / "report.json"
        data = _make_minimal_report_data()
        generate_report_json(data, str(out))
        parsed = json.loads(out.read_text())
        assert len(parsed["risk"]["regions"]) == 2
        assert parsed["risk"]["regions"][0]["region"] == "Cluj"

    def test_notifications_included(self, tmp_path):
        out = tmp_path / "report.json"
        generate_report_json(_make_minimal_report_data(), str(out))
        parsed = json.loads(out.read_text())
        assert len(parsed["notifications"]) == 1
        assert parsed["notifications"][0]["provider"] == "discord"


# ===========================================================================
# PDF generator (skipped when ReportLab not available)
# ===========================================================================

try:
    from app.modules.reports.pdf_generator import REPORTLAB_AVAILABLE, generate_report_pdf

    _pdf_available = REPORTLAB_AVAILABLE
except ImportError:
    _pdf_available = False

skip_if_no_reportlab = pytest.mark.skipif(
    not _pdf_available, reason="ReportLab not installed"
)


class TestPdfGenerator:
    @skip_if_no_reportlab
    def test_generates_pdf_file(self, tmp_path):
        out = tmp_path / "report.pdf"
        generate_report_pdf(_make_minimal_report_data(), str(out))
        assert out.exists()
        assert out.stat().st_size > 1000  # Expect a non-trivial PDF

    @skip_if_no_reportlab
    def test_pdf_has_pdf_magic_bytes(self, tmp_path):
        out = tmp_path / "report.pdf"
        generate_report_pdf(_make_minimal_report_data(), str(out))
        header = out.read_bytes()[:5]
        assert header == b"%PDF-"

    @skip_if_no_reportlab
    def test_empty_data_does_not_crash(self, tmp_path):
        out = tmp_path / "empty_report.pdf"
        generate_report_pdf({}, str(out))
        assert out.exists()

    @skip_if_no_reportlab
    def test_all_report_types_generate(self, tmp_path):
        for rtype in ("daily", "weekly", "monthly", "on_demand"):
            out = tmp_path / f"report_{rtype}.pdf"
            data = _make_minimal_report_data(report_type=rtype)
            generate_report_pdf(data, str(out))
            assert out.exists(), f"PDF not created for type={rtype}"
            assert out.stat().st_size > 500

    @skip_if_no_reportlab
    def test_pdf_with_empty_risk_regions(self, tmp_path):
        out = tmp_path / "empty_risk.pdf"
        data = _make_minimal_report_data()
        data["risk"] = {"regions": []}
        generate_report_pdf(data, str(out))
        assert out.exists()

    @skip_if_no_reportlab
    def test_pdf_accepts_analytics_list_land_cover_distribution(self, tmp_path):
        out = tmp_path / "list_land_cover.pdf"
        data = _make_minimal_report_data()
        data["land_cover"] = {
            "distribution": [
                {"land_cover": "forest", "events": 5},
                {"land_cover": "urban", "events": 2},
            ]
        }
        generate_report_pdf(data, str(out))
        assert out.exists()
        assert out.stat().st_size > 500

    def test_raises_when_reportlab_missing(self, tmp_path, monkeypatch):
        """generate_report_pdf raises RuntimeError when ReportLab is absent."""
        import app.modules.reports.pdf_generator as pdf_mod

        with monkeypatch.context() as m:
            m.setattr(pdf_mod, "REPORTLAB_AVAILABLE", False)
            with pytest.raises(RuntimeError, match="reportlab is not installed"):
                pdf_mod.generate_report_pdf({}, str(tmp_path / "x.pdf"))


# ===========================================================================
# ReportService
# ===========================================================================

class TestReportService:
    @pytest.mark.anyio
    async def test_gather_report_data_returns_dict(self):
        svc = _make_report_service()
        data = await svc.gather_report_data(PERIOD_START, PERIOD_END)
        assert "overview" in data
        assert "anomalies" in data
        assert "intelligence_events" in data
        assert "risk" in data
        assert "summary" in data

    @pytest.mark.anyio
    async def test_gather_report_data_handles_section_errors(self):
        analytics = MagicMock()
        analytics.get_overview = AsyncMock(side_effect=RuntimeError("DB error"))
        analytics.get_anomalies = AsyncMock(return_value={"anomalies": []})
        analytics.get_land_cover_distribution = AsyncMock(return_value={})
        svc = _make_report_service(analytics_svc=analytics)
        data = await svc.gather_report_data(PERIOD_START, PERIOD_END)
        # Should not raise; failed section defaults to {}
        assert data["overview"] == {}
        assert data["anomalies"] == {"anomalies": []}

    @pytest.mark.anyio
    async def test_create_pending_returns_record(self):
        repo = _make_report_repo()
        svc = _make_report_service(report_repo=repo)
        record = await svc.create_pending(
            report_type=ReportType.DAILY,
            report_format=ReportFormat.PDF,
        )
        assert record["status"] == "pending"
        repo.create.assert_called_once()

    @pytest.mark.anyio
    async def test_create_pending_computes_default_periods(self):
        repo = _make_report_repo()
        svc = _make_report_service(report_repo=repo)
        await svc.create_pending(
            report_type=ReportType.WEEKLY,
            report_format=ReportFormat.PDF,
        )
        call_kwargs = repo.create.call_args.kwargs
        delta = call_kwargs["period_end"] - call_kwargs["period_start"]
        assert 6 <= delta.days <= 8  # Weekly ≈ 7 days

    @pytest.mark.anyio
    async def test_generate_background_csv(self, tmp_path):
        repo = _make_report_repo()
        repo.get_by_id = AsyncMock(
            return_value=_make_fake_report(file_size=500, generation_time_ms=100, status="complete")
        )
        svc = _make_report_service(report_repo=repo, reports_dir=tmp_path)
        report_id = "507f1f77bcf86cd799439011"
        await svc.generate_background(
            report_id=report_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            report_format=ReportFormat.CSV,
        )
        csv_file = tmp_path / f"{report_id}.csv"
        assert csv_file.exists()
        repo.update_complete.assert_called_once()

    @pytest.mark.anyio
    async def test_generate_background_json(self, tmp_path):
        repo = _make_report_repo()
        repo.get_by_id = AsyncMock(
            return_value=_make_fake_report(file_size=200, generation_time_ms=50, status="complete")
        )
        svc = _make_report_service(report_repo=repo, reports_dir=tmp_path)
        report_id = "507f1f77bcf86cd799439012"
        await svc.generate_background(
            report_id=report_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            report_format=ReportFormat.JSON,
        )
        json_file = tmp_path / f"{report_id}.json"
        assert json_file.exists()
        repo.update_complete.assert_called_once()

    @pytest.mark.anyio
    async def test_generate_background_updates_failed_on_error(self, tmp_path):
        repo = _make_report_repo()
        repo.update_status = AsyncMock()
        analytics = MagicMock()
        analytics.get_overview = AsyncMock(side_effect=RuntimeError("fail"))
        analytics.get_anomalies = AsyncMock(side_effect=RuntimeError("fail"))
        analytics.get_land_cover_distribution = AsyncMock(side_effect=RuntimeError("fail"))

        # PDF generation will fail with RuntimeError (reportlab not installed or error)
        with patch(
            "app.modules.reports.report_service.generate_report_pdf",
            side_effect=RuntimeError("test error"),
        ):
            svc = _make_report_service(
                report_repo=repo,
                analytics_svc=analytics,
                reports_dir=tmp_path,
            )
            await svc.generate_background(
                report_id="507f1f77bcf86cd799439011",
                period_start=PERIOD_START,
                period_end=PERIOD_END,
                report_format=ReportFormat.PDF,
            )
        # update_failed should be called
        repo.update_failed.assert_called_once()

    @pytest.mark.anyio
    async def test_list_reports_delegates_to_repo(self):
        repo = _make_report_repo()
        svc = _make_report_service(report_repo=repo)
        result = await svc.list_reports()
        assert isinstance(result, list)
        repo.list_all.assert_called_once()

    @pytest.mark.anyio
    async def test_get_report_delegates_to_repo(self):
        repo = _make_report_repo()
        svc = _make_report_service(report_repo=repo)
        result = await svc.get_report("507f1f77bcf86cd799439011")
        repo.get_by_id.assert_called_once_with("507f1f77bcf86cd799439011")

    @pytest.mark.anyio
    async def test_delete_report_removes_file(self, tmp_path):
        fake_file = tmp_path / "old_report.csv"
        fake_file.write_text("data")
        repo = _make_report_repo()
        repo.get_by_id = AsyncMock(
            return_value=_make_fake_report(file_path=str(fake_file), status="complete")
        )
        repo.delete = AsyncMock(return_value=True)
        svc = _make_report_service(report_repo=repo, reports_dir=tmp_path)
        result = await svc.delete_report("aaaa0000000000000000aaaa")
        assert result is True
        assert not fake_file.exists()

    @pytest.mark.anyio
    async def test_delete_report_returns_false_when_not_found(self):
        repo = _make_report_repo()
        repo.get_by_id = AsyncMock(return_value=None)
        svc = _make_report_service(report_repo=repo)
        result = await svc.delete_report("507f1f77bcf86cd799439011")
        assert result is False

    @pytest.mark.anyio
    async def test_scheduled_daily_skips_if_exists(self):
        repo = _make_report_repo()
        repo.find_by_type_and_period_start = AsyncMock(
            return_value=_make_fake_report(status="complete")
        )
        svc = _make_report_service(report_repo=repo)
        result = await svc.generate_scheduled_daily()
        assert result is None
        repo.create.assert_not_called()

    @pytest.mark.anyio
    async def test_scheduled_daily_generates_when_absent(self, tmp_path):
        repo = _make_report_repo()
        repo.find_by_type_and_period_start = AsyncMock(return_value=None)
        repo.get_by_id = AsyncMock(
            return_value=_make_fake_report(status="complete", file_size=500)
        )
        svc = _make_report_service(report_repo=repo, reports_dir=tmp_path)
        result = await svc.generate_scheduled_daily()
        repo.create.assert_called_once()

    @pytest.mark.anyio
    async def test_weather_section_empty_when_no_weather_svc(self):
        svc = _make_report_service(weather_svc=None)
        data = await svc.gather_report_data(PERIOD_START, PERIOD_END)
        assert data["weather"] == {"regions": []}

    @pytest.mark.anyio
    async def test_weather_section_fetched_when_svc_provided(self):
        weather_svc = MagicMock()
        weather_svc.get_current_weather = AsyncMock(
            return_value={"regions": [{"region": "Cluj", "temperature": 25.0}]}
        )
        svc = _make_report_service(weather_svc=weather_svc)
        data = await svc.gather_report_data(PERIOD_START, PERIOD_END)
        assert len(data["weather"]["regions"]) == 1
        assert data["weather"]["regions"][0]["region"] == "Cluj"


# ===========================================================================
# API endpoints
# ===========================================================================

try:
    from datetime import datetime as _dt, timezone as _tz
    from fastapi.testclient import TestClient
    from app.modules.reports.report_service import ReportService as _RS
    from app.api.deps import report_service_dep, get_current_user
    from app.models.user import UserPublic

    def _make_test_app():
        from fastapi import FastAPI
        from app.modules.reports.report_routes import router
        from app.core.errors import AppError, app_error_handler

        _app = FastAPI()
        _app.add_exception_handler(AppError, app_error_handler)
        _app.include_router(router, prefix="/reports")
        return _app

    _test_app = _make_test_app()
    _USER = UserPublic(
        id="1", email="test@test.com", name="Tester",
        role="admin", provider="local",
        created_at=_dt(2024, 1, 1, tzinfo=_tz.utc),
    )

    def _override_auth(app, user=_USER):
        app.dependency_overrides[get_current_user] = lambda: user

    def _override_report_svc(app, svc):
        app.dependency_overrides[report_service_dep] = lambda: svc

    APP_IMPORTABLE = True
except Exception as _e:
    import traceback as _tb
    _tb.print_exc()
    APP_IMPORTABLE = False

skip_if_no_app = pytest.mark.skipif(
    not APP_IMPORTABLE, reason="App import failed"
)


class TestReportRoutes:
    def setup_method(self):
        if not APP_IMPORTABLE:
            return
        _test_app.dependency_overrides.clear()
        _override_auth(_test_app)

    @skip_if_no_app
    def test_list_reports_returns_200(self):
        svc = MagicMock()
        svc.list_reports = AsyncMock(return_value=[_make_fake_report(status="complete")])
        _override_report_svc(_test_app, svc)
        client = TestClient(_test_app, raise_server_exceptions=False)
        resp = client.get("/reports")
        assert resp.status_code == 200
        body = resp.json()
        assert "reports" in body
        assert "total" in body

    @skip_if_no_app
    def test_get_report_returns_404_when_missing(self):
        svc = MagicMock()
        svc.get_report = AsyncMock(return_value=None)
        _override_report_svc(_test_app, svc)
        client = TestClient(_test_app, raise_server_exceptions=False)
        resp = client.get("/reports/507f1f77bcf86cd799439011")
        assert resp.status_code == 404

    @skip_if_no_app
    def test_get_report_returns_200_when_found(self):
        svc = MagicMock()
        svc.get_report = AsyncMock(return_value=_make_fake_report(status="complete"))
        _override_report_svc(_test_app, svc)
        client = TestClient(_test_app, raise_server_exceptions=False)
        resp = client.get("/reports/507f1f77bcf86cd799439011")
        assert resp.status_code == 200
        assert resp.json()["status"] == "complete"

    @skip_if_no_app
    def test_generate_returns_202(self):
        svc = MagicMock()
        svc.create_pending = AsyncMock(return_value=_make_fake_report())
        svc.generate_background = AsyncMock()
        _override_report_svc(_test_app, svc)
        client = TestClient(_test_app, raise_server_exceptions=False)
        resp = client.post("/reports/generate", json={"type": "daily", "format": "pdf"})
        assert resp.status_code == 202
        assert resp.json()["status"] == "pending"

    @skip_if_no_app
    def test_generate_requires_auth(self):
        from app.core.errors import AuthError

        def _raise_auth():
            raise AuthError("Not authenticated")

        _test_app.dependency_overrides.clear()
        _test_app.dependency_overrides[get_current_user] = _raise_auth
        client = TestClient(_test_app, raise_server_exceptions=False)
        resp = client.post("/reports/generate", json={"type": "daily", "format": "pdf"})
        assert resp.status_code in (401, 403, 422)
        # Restore auth for other tests
        _override_auth(_test_app)

    @skip_if_no_app
    def test_delete_returns_404_when_missing(self):
        _override_auth(_test_app)
        svc = MagicMock()
        svc.delete_report = AsyncMock(return_value=False)
        _override_report_svc(_test_app, svc)
        client = TestClient(_test_app, raise_server_exceptions=False)
        resp = client.delete("/reports/507f1f77bcf86cd799439011")
        assert resp.status_code == 404

    @skip_if_no_app
    def test_delete_returns_204_when_deleted(self):
        _override_auth(_test_app)
        svc = MagicMock()
        svc.delete_report = AsyncMock(return_value=True)
        _override_report_svc(_test_app, svc)
        client = TestClient(_test_app, raise_server_exceptions=False)
        resp = client.delete("/reports/507f1f77bcf86cd799439011")
        assert resp.status_code == 204

    @skip_if_no_app
    def test_download_returns_400_for_non_complete(self):
        _override_auth(_test_app)
        svc = MagicMock()
        svc.get_report = AsyncMock(return_value=_make_fake_report(status="generating"))
        _override_report_svc(_test_app, svc)
        client = TestClient(_test_app, raise_server_exceptions=False)
        resp = client.get("/reports/507f1f77bcf86cd799439011/download")
        assert resp.status_code == 400

    @skip_if_no_app
    def test_download_returns_404_for_missing_file(self, tmp_path):
        _override_auth(_test_app)
        svc = MagicMock()
        svc.get_report = AsyncMock(
            return_value=_make_fake_report(
                status="complete",
                file_path=str(tmp_path / "nonexistent.pdf"),
            )
        )
        _override_report_svc(_test_app, svc)
        client = TestClient(_test_app, raise_server_exceptions=False)
        resp = client.get("/reports/507f1f77bcf86cd799439011/download")
        assert resp.status_code == 404

    @skip_if_no_app
    def test_download_returns_file_for_complete_report(self, tmp_path):
        _override_auth(_test_app)
        fake_json = tmp_path / "test_report.json"
        fake_json.write_text('{"key": "value"}')
        svc = MagicMock()
        svc.get_report = AsyncMock(
            return_value=_make_fake_report(
                status="complete",
                file_path=str(fake_json),
            )
        )
        _override_report_svc(_test_app, svc)
        client = TestClient(_test_app, raise_server_exceptions=False)
        resp = client.get("/reports/507f1f77bcf86cd799439011/download")
        assert resp.status_code == 200
        assert "json" in resp.headers["content-type"]


# ===========================================================================
# Scheduler integration
# ===========================================================================

class TestSchedulerReportIntegration:
    @pytest.mark.anyio
    async def test_scheduler_calls_daily_report(self):
        from app.services.scheduler_service import SchedulerService

        report_svc = MagicMock()
        report_svc.generate_scheduled_daily = AsyncMock(return_value=None)
        report_svc.generate_scheduled_weekly = AsyncMock(return_value=None)
        report_svc.generate_scheduled_monthly = AsyncMock(return_value=None)

        firms = MagicMock()
        firms.run = AsyncMock(return_value={"total": 0, "created": 0, "skipped": 0})

        events_svc = MagicMock()
        analytics_svc = MagicMock()
        analytics_svc.reconcile_intelligence_events = AsyncMock()
        analytics_svc.get_alerts = AsyncMock(return_value={"alerts": []})
        intel_svc = MagicMock()
        intel_svc.get_events = AsyncMock(return_value={"active": []})
        runs_repo = MagicMock()
        runs_repo.create_run = AsyncMock(
            return_value={
                "id": "run1", "started_at": NOW, "completed_at": NOW,
                "duration_seconds": 1.0, "source": "NASA FIRMS",
                "status": "success", "events_fetched": 0, "events_inserted": 0,
                "duplicates_skipped": 0, "error": None,
            }
        )

        scheduler = SchedulerService(
            firms_provider=firms,
            events_service=events_svc,
            events_repo=MagicMock(),
            analytics_service=analytics_svc,
            intelligence_service=intel_svc,
            runs_repo=runs_repo,
            enabled=True,
            report_svc=report_svc,
            enable_scheduled_reports=True,
        )

        await scheduler._run_cycle()
        report_svc.generate_scheduled_daily.assert_called_once()

    @pytest.mark.anyio
    async def test_scheduler_skips_reports_when_disabled(self):
        from app.services.scheduler_service import SchedulerService

        report_svc = MagicMock()
        report_svc.generate_scheduled_daily = AsyncMock(return_value=None)

        firms = MagicMock()
        firms.run = AsyncMock(return_value={"total": 0, "created": 0, "skipped": 0})
        analytics_svc = MagicMock()
        analytics_svc.reconcile_intelligence_events = AsyncMock()
        analytics_svc.get_alerts = AsyncMock(return_value={"alerts": []})
        intel_svc = MagicMock()
        intel_svc.get_events = AsyncMock(return_value={"active": []})
        runs_repo = MagicMock()
        runs_repo.create_run = AsyncMock(
            return_value={
                "id": "r", "started_at": NOW, "completed_at": NOW,
                "duration_seconds": 1.0, "source": "NASA FIRMS",
                "status": "success", "events_fetched": 0, "events_inserted": 0,
                "duplicates_skipped": 0, "error": None,
            }
        )

        scheduler = SchedulerService(
            firms_provider=firms,
            events_service=MagicMock(),
            events_repo=MagicMock(),
            analytics_service=analytics_svc,
            intelligence_service=intel_svc,
            runs_repo=runs_repo,
            enabled=True,
            report_svc=report_svc,
            enable_scheduled_reports=False,  # disabled
        )

        await scheduler._run_cycle()
        report_svc.generate_scheduled_daily.assert_not_called()
