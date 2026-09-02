"""EEA Air Quality live activation tests — HTTP/ZIP/Parquet/scheduler/correlation."""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pandas as pd
import pytest

from app.core.config import Settings
from app.core.ecosystem.air_quality_constants import EEA_MISSING_VALUE
from app.core.ecosystem.incident_categories import IncidentCategory
from app.core.geography.geographic_scope import GeographicScopePolicy, GeographicScope
from app.core.ingestion.provider_health import ProviderHealthStatus, health_status_from_run
from app.core.ecosystem.intelligence_event_defaults import DEFAULT_SIGNAL_TYPE
from app.modules.analytics.cross_source_correlator import CrossSourceCorrelator
from app.modules.analytics.correlation_config import build_correlation_config
from app.modules.analytics.detection_contract import Detection, SignalType
from app.modules.analytics.detectors.air_quality_baseline_detector import AirQualityBaselineDetector
from app.modules.ingestion.providers.eea_aq_client import EEAAQDownloadClient
from app.modules.ingestion.providers.eea_aq_parquet import (
    EEAAQParquetError,
    extract_parquet_rows,
    normalize_parquet_rows,
)
from app.modules.ingestion.providers.eea_aq_station_metadata import EEAAQStationMetadata
from app.modules.ingestion.providers.eea_aq_validation import (
    EEAAQAuthenticationError,
    EEAAQValidationError,
    is_valid_eea_token_format,
    sanitize_error_message,
    validate_parquet_row,
)
from app.modules.ingestion.providers.eea_air_quality import (
    EEAAirQualityProvider,
    EEA_AQ_PROVIDER_ID,
    STATION_REGISTRY,
    _dedupe_records,
)
from app.services.scheduler_service import SchedulerService
from fixtures.phase0_golden_harness import generate_golden_artifacts
from fixtures.phase0_oracle_manifest import verify_generated_match_manifest

_VALID_TOKEN = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
_NOW = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)


def _settings(**overrides) -> Settings:
    base = {
        "mongo_url": "mongodb://localhost:27017",
        "db_name": "test",
        "jwt_secret": "secret",
        "admin_email": "admin@test.com",
        "admin_password": "pass",
        "frontend_url": "http://localhost:3000",
    }
    base.update(overrides)
    return Settings(**base)


def _sample_parquet_rows() -> list[dict]:
    return [
        {
            "Samplingpoint": "RO-BUC-AQ01",
            "Pollutant": "PM2.5",
            "Start": "2026-06-10T10:00:00",
            "End": "2026-06-10T11:00:00",
            "Value": 42.0,
            "Unit": "ug/m3",
            "Validity": "valid",
            "Verification": "verified",
            "AggType": "hour",
        }
    ]


def _build_zip(rows: list[dict] | None = None) -> bytes:
    rows = rows if rows is not None else _sample_parquet_rows()
    frame = pd.DataFrame(rows)
    parquet_buffer = io.BytesIO()
    frame.to_parquet(parquet_buffer, index=False)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr("E2a/data.parquet", parquet_buffer.getvalue())
    return zip_buffer.getvalue()


def _station_lookup() -> dict[str, dict]:
    station = STATION_REGISTRY["RO-BUC-AQ01"]
    return {
        "RO-BUC-AQ01": {
            "station_id": "RO-BUC-AQ01",
            "station_name": station["station_name"],
            "latitude": station["latitude"],
            "longitude": station["longitude"],
            "country": station["country"],
        }
    }


class TestAuthentication:
    def test_valid_token_format(self):
        assert is_valid_eea_token_format(_VALID_TOKEN)

    def test_missing_token_invalid(self):
        assert not is_valid_eea_token_format("")

    def test_invalid_token_format(self):
        assert not is_valid_eea_token_format("not-a-guid")

    def test_token_never_in_sanitized_error(self):
        msg = sanitize_error_message(f"failed with {_VALID_TOKEN}", _VALID_TOKEN)
        assert _VALID_TOKEN not in msg
        assert "[REDACTED]" in msg

    @pytest.mark.anyio
    async def test_validate_token_rejects_401(self):
        settings = _settings(eea_aq_api_token=_VALID_TOKEN)
        transport = httpx.MockTransport(
            lambda request: httpx.Response(401, json={"title": "Unauthorized"})
        )
        client = EEAAQDownloadClient(
            settings=settings,
            http_client=httpx.AsyncClient(transport=transport),
        )
        with pytest.raises(EEAAQAuthenticationError):
            await client.validate_token(_VALID_TOKEN)


class TestZipParquet:
    def test_valid_archive(self):
        rows = extract_parquet_rows(_build_zip())
        assert len(rows) == 1
        assert rows[0]["Samplingpoint"] == "RO-BUC-AQ01"

    def test_malformed_zip(self):
        with pytest.raises(EEAAQParquetError):
            extract_parquet_rows(b"not-a-zip")

    def test_empty_archive(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w"):
            pass
        with pytest.raises(EEAAQParquetError):
            extract_parquet_rows(buffer.getvalue())

    def test_unsafe_archive_path(self):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as archive:
            archive.writestr("../evil.parquet", b"bad")
        with pytest.raises(EEAAQParquetError):
            extract_parquet_rows(zip_buffer.getvalue())

    def test_normalize_with_metadata(self):
        records, rejected = normalize_parquet_rows(
            _sample_parquet_rows(),
            station_lookup=_station_lookup(),
            dataset_version="Raster1",
        )
        assert rejected == 0
        assert records[0]["station_id"] == "RO-BUC-AQ01"
        assert records[0]["latitude"] == STATION_REGISTRY["RO-BUC-AQ01"]["latitude"]


class TestMeasurementValidation:
    def test_valid_measurement(self):
        row = validate_parquet_row(
            {
                "station_id": "RO-BUC-AQ01",
                "pollutant": "PM2.5",
                "value": 10.0,
                "unit": "ug/m3",
                "observed_at": "2026-06-10T10:00:00+00:00",
                "latitude": 44.4,
                "longitude": 26.1,
            }
        )
        assert row["value"] == 10.0

    def test_sentinel_rejected(self):
        with pytest.raises(EEAAQValidationError):
            validate_parquet_row(
                {
                    "station_id": "X",
                    "pollutant": "PM2.5",
                    "value": EEA_MISSING_VALUE,
                    "observed_at": "2026-06-10T10:00:00+00:00",
                    "latitude": 44.0,
                    "longitude": 26.0,
                }
            )

    def test_invalid_validity_flag(self):
        with pytest.raises(EEAAQValidationError):
            validate_parquet_row(
                {
                    "station_id": "X",
                    "pollutant": "PM2.5",
                    "value": 10.0,
                    "validity": "not valid",
                    "observed_at": "2026-06-10T10:00:00+00:00",
                    "latitude": 44.0,
                    "longitude": 26.0,
                }
            )

    def test_valid_zero(self):
        row = validate_parquet_row(
            {
                "station_id": "X",
                "pollutant": "PM2.5",
                "value": 0.0,
                "observed_at": "2026-06-10T10:00:00+00:00",
                "latitude": 44.0,
                "longitude": 26.0,
            }
        )
        assert row["value"] == 0.0


class TestDeterminism:
    def test_same_query_same_records(self):
        rows = _sample_parquet_rows()
        first, _ = normalize_parquet_rows(rows, station_lookup=_station_lookup())
        second, _ = normalize_parquet_rows(rows, station_lookup=_station_lookup())
        assert first == second

    def test_dedupe_identity(self):
        duplicate = [
            {
                "station_id": "RO-BUC-AQ01",
                "pollutant": "PM2.5",
                "observed_at": "2026-06-10T10:00:00+00:00",
                "value": 1.0,
            },
            {
                "station_id": "RO-BUC-AQ01",
                "pollutant": "PM2.5",
                "observed_at": "2026-06-10T10:00:00+00:00",
                "value": 1.0,
            },
        ]
        assert len(_dedupe_records(duplicate)) == 1


class TestLiveProviderFetch:
    @pytest.mark.anyio
    async def test_live_fetch_with_mock_client(self):
        settings = _settings(eea_aq_api_token=_VALID_TOKEN)
        mock_client = AsyncMock()
        mock_client.download_parquet_zip = AsyncMock(return_value=_build_zip())
        mock_client.fetch_dataset_version = AsyncMock(return_value="Raster1")
        mock_client.aclose = AsyncMock()

        metadata = EEAAQStationMetadata(index=_station_lookup())
        provider = EEAAirQualityProvider(
            settings=settings,
            download_client=mock_client,
            station_metadata=metadata,
        )
        records = await provider.fetch()
        assert len(records) == 1
        assert records[0]["pollutant"] == "PM2.5"

    @pytest.mark.anyio
    async def test_missing_token_uses_fixture(self):
        settings = _settings(eea_aq_api_token="")
        provider = EEAAirQualityProvider(settings=settings)
        records = await provider.fetch()
        assert len(records) >= 8

    @pytest.mark.anyio
    async def test_live_failure_does_not_fall_back(self):
        settings = _settings(eea_aq_api_token=_VALID_TOKEN)
        mock_client = AsyncMock()
        mock_client.download_parquet_zip = AsyncMock(side_effect=RuntimeError("timeout"))
        mock_client.aclose = AsyncMock()
        provider = EEAAirQualityProvider(
            settings=settings,
            download_client=mock_client,
            station_metadata=EEAAQStationMetadata(index=_station_lookup()),
        )
        with pytest.raises(RuntimeError):
            await provider.fetch()


class TestSchedulerIsolation:
    @pytest.mark.anyio
    async def test_firms_failure_does_not_stop_eea(self):
        firms = MagicMock()
        firms.source_name = "NASA FIRMS"
        firms.provider_id = "nasa.firms"
        firms.describe = MagicMock(return_value={"source": "NASA FIRMS"})
        firms.run = AsyncMock(side_effect=RuntimeError("FIRMS down"))

        eea = MagicMock()
        eea.source_name = "EEA Air Quality"
        eea.provider_id = EEA_AQ_PROVIDER_ID
        eea.describe = MagicMock(return_value={"source": "EEA Air Quality", "provider_id": EEA_AQ_PROVIDER_ID})
        eea.run = AsyncMock(return_value={"total": 1, "created": 1, "skipped": 0, "errors": 0})

        runs_repo = MagicMock()
        runs_repo.create_run = AsyncMock(return_value={"status": "failed", "duration_seconds": 0.1})

        scheduler = SchedulerService(
            firms_provider=firms,
            events_service=MagicMock(),
            events_repo=MagicMock(),
            analytics_service=MagicMock(reconcile_intelligence_events=AsyncMock()),
            intelligence_service=MagicMock(),
            runs_repo=runs_repo,
            enabled=True,
            ingestion_providers=[firms, eea],
            reconciliation_lock=MagicMock(try_acquire=AsyncMock(return_value=True), release=AsyncMock()),
        )
        await scheduler._run_cycle()
        eea.run.assert_awaited_once()

    @pytest.mark.anyio
    async def test_all_providers_fail_reconciliation_still_runs(self):
        firms = MagicMock()
        firms.source_name = "NASA FIRMS"
        firms.provider_id = "nasa.firms"
        firms.describe = MagicMock(return_value={"source": "NASA FIRMS"})
        firms.run = AsyncMock(side_effect=RuntimeError("FIRMS down"))

        eea = MagicMock()
        eea.source_name = "EEA Air Quality"
        eea.provider_id = EEA_AQ_PROVIDER_ID
        eea.describe = MagicMock(return_value={"source": "EEA Air Quality"})
        eea.run = AsyncMock(side_effect=RuntimeError("EEA down"))

        reconcile = AsyncMock()
        runs_repo = MagicMock()
        runs_repo.create_run = AsyncMock(return_value={"status": "failed", "duration_seconds": 0.1})

        scheduler = SchedulerService(
            firms_provider=firms,
            events_service=MagicMock(),
            events_repo=MagicMock(),
            analytics_service=MagicMock(reconcile_intelligence_events=reconcile),
            intelligence_service=MagicMock(),
            runs_repo=runs_repo,
            enabled=True,
            ingestion_providers=[firms, eea],
            reconciliation_lock=MagicMock(try_acquire=AsyncMock(return_value=True), release=AsyncMock()),
        )
        await scheduler._run_cycle()
        reconcile.assert_awaited_once()


class TestGeographicScope:
    def test_romania_event_in_scope(self):
        policy = GeographicScopePolicy(GeographicScope.ROMANIA)
        event = {
            "country": "Romania",
            "metadata": {"ingestion": {"is_romania": True}},
        }
        assert policy.event_in_scope(event)

    def test_europe_event_in_europe_scope(self):
        policy = GeographicScopePolicy(GeographicScope.EUROPE)
        event = {"country": "Germany", "latitude": 52.5, "longitude": 13.4}
        assert policy.event_in_scope(event)

    def test_non_european_excluded(self):
        policy = GeographicScopePolicy(GeographicScope.EUROPE)
        event = {"country": "Brazil", "latitude": -3.0, "longitude": -62.0}
        assert not policy.event_in_scope(event)


class TestCorrelationWithLiveEEA:
    def _detection(
        self,
        *,
        category: str,
        provider_id: str,
        provider_class: str,
        lat: float,
        lng: float,
        observed_at: datetime,
        region: str = "RO-BUC-AQ01",
        spatial_key: str | None = None,
    ) -> Detection:
        key = spatial_key or region
        return Detection(
            spatial_key=key,
            incident_category=category,
            signal_type=SignalType.BASELINE_DEVIATION.value,
            severity="high",
            score=0.8,
            detected_at=observed_at,
            evidence={
                "region": region,
                "latitude": lat,
                "longitude": lng,
                "provenance": {
                    "provider_id": provider_id,
                    "source_event_id": f"{provider_id}-{key}",
                    "domain_evidence": {
                        "provider_class": provider_class,
                        "detection_method": DEFAULT_SIGNAL_TYPE,
                    },
                },
            },
        )

    def test_firms_eea_contextual_positive(self):
        now = _NOW
        correlator = CrossSourceCorrelator(build_correlation_config())
        detections = [
            self._detection(
                category=IncidentCategory.WILDFIRE.value,
                provider_id="nasa.firms",
                provider_class="satellite_fire_observations",
                lat=44.4268,
                lng=26.1025,
                observed_at=now,
                region="Suceava",
            ),
            self._detection(
                category=IncidentCategory.AIR_QUALITY.value,
                provider_id="eea.air_quality",
                provider_class="eea_air_quality",
                lat=44.4268,
                lng=26.1025,
                observed_at=now,
            ),
        ]
        results = correlator.correlate(detections, now)
        assert any(r.correlation_rule == "firms_eea_contextual" for r in results)

    def test_temporal_negative(self):
        now = _NOW
        correlator = CrossSourceCorrelator(build_correlation_config())
        detections = [
            self._detection(
                category=IncidentCategory.WILDFIRE.value,
                provider_id="nasa.firms",
                provider_class="satellite_fire_observations",
                lat=44.4268,
                lng=26.1025,
                observed_at=now - timedelta(hours=100),
                region="Suceava",
            ),
            self._detection(
                category=IncidentCategory.AIR_QUALITY.value,
                provider_id="eea.air_quality",
                provider_class="eea_air_quality",
                lat=44.4268,
                lng=26.1025,
                observed_at=now,
            ),
        ]
        results = correlator.correlate(detections, now)
        assert not any(r.correlation_rule == "firms_eea_contextual" for r in results)

    def test_spatial_negative(self):
        now = _NOW
        correlator = CrossSourceCorrelator(build_correlation_config())
        detections = [
            self._detection(
                category=IncidentCategory.WILDFIRE.value,
                provider_id="nasa.firms",
                provider_class="satellite_fire_observations",
                lat=45.0,
                lng=25.0,
                observed_at=now,
                region="Suceava",
            ),
            self._detection(
                category=IncidentCategory.AIR_QUALITY.value,
                provider_id="eea.air_quality",
                provider_class="eea_air_quality",
                lat=44.4268,
                lng=26.1025,
                observed_at=now,
            ),
        ]
        results = correlator.correlate(detections, now)
        assert not any(r.correlation_rule == "firms_eea_contextual" for r in results)


class TestProviderHealthSemantics:
    def test_missing_token_unknown_when_disabled(self):
        status = health_status_from_run(
            success=True,
            observations_rejected=0,
            observations_received=8,
            consecutive_failures=0,
            enabled=False,
        )
        assert status == ProviderHealthStatus.DISABLED.value

    def test_http_failure_degraded_then_failed(self):
        degraded = health_status_from_run(
            success=False,
            observations_rejected=0,
            observations_received=0,
            consecutive_failures=1,
            enabled=True,
        )
        failed = health_status_from_run(
            success=False,
            observations_rejected=0,
            observations_received=0,
            consecutive_failures=3,
            enabled=True,
        )
        assert degraded == ProviderHealthStatus.DEGRADED.value
        assert failed == ProviderHealthStatus.FAILED.value


class TestPhase0Compatibility:
    def test_oracle_unchanged(self):
        generated = generate_golden_artifacts()
        verify_generated_match_manifest(generated)

    def test_ten_run_determinism(self):
        first = generate_golden_artifacts()
        for _ in range(9):
            verify_generated_match_manifest(generate_golden_artifacts())
        verify_generated_match_manifest(first)
