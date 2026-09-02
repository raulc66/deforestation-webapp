"""Ingestion provider contract tests (Package C)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.ingestion.provider_capabilities import PROVIDER_CAPABILITY_MATRIX
from app.core.ingestion.provider_contract import IngestionProvider
from app.modules.ingestion.providers.firms import FIRMSProvider
from app.modules.ingestion.providers.synthetic_environmental import (
    SYNTHETIC_SOURCE_NAME,
    SyntheticEnvironmentalProvider,
)


def _run(coro):
    return asyncio.run(coro)


class TestProviderCapabilityMatrix:
    def test_satellite_fire_observations_live(self):
        live = [row for row in PROVIDER_CAPABILITY_MATRIX if row.status == "live"]
        assert any(row.source_class == "satellite_fire_observations" for row in live)

    def test_all_rows_declare_core_capabilities(self):
        for row in PROVIDER_CAPABILITY_MATRIX:
            assert row.fetch and row.normalize and row.validation
            assert row.source_metadata and row.geographic_information and row.timestamps


class TestFIRMSProviderContract:
    def test_implements_ingestion_provider(self):
        assert isinstance(FIRMSProvider(), IngestionProvider)

    def test_source_name_and_categories(self):
        provider = FIRMSProvider()
        assert provider.source_name == "NASA FIRMS"
        assert provider.supported_incident_categories == ("wildfire",)


class TestSyntheticProviderPipeline:
    @pytest.mark.anyio
    async def test_second_provider_enters_shared_pipeline(self, monkeypatch):
        provider = SyntheticEnvironmentalProvider()
        events_service = MagicMock()
        events_service.create_event = AsyncMock()
        events_repo = MagicMock()

        async def _no_duplicate(*_args, **_kwargs):
            return False

        monkeypatch.setattr(
            "app.modules.ingestion.persist.is_duplicate_event",
            _no_duplicate,
        )

        result = await provider.run(events_service, events_repo)

        assert result["total"] == 1
        assert result["created"] == 1
        events_service.create_event.assert_awaited_once()
        payload = events_service.create_event.await_args.args[0]
        assert payload.event_type == "logging"
        assert payload.metadata["incident_category"] == "illegal_logging"

    def test_source_name(self):
        assert SyntheticEnvironmentalProvider().source_name == SYNTHETIC_SOURCE_NAME
