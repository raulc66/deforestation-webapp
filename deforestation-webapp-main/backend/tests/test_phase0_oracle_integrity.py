"""WP0.3 — Oracle manifest integrity and determinism sign-off tests."""
from __future__ import annotations

import json

import pytest

from fixtures.phase0_golden_harness import (
    generate_golden_artifacts,
    run_phase0_golden_pipeline,
    snapshot_to_json,
)
from fixtures.phase0_oracle_manifest import (
    GOLDEN_ARTIFACT_FILES,
    GOLDEN_DIR,
    MANIFEST_FILENAME,
    load_manifest,
    manifest_artifact_index,
    sha256_file,
    sha256_text,
    verify_generated_match_manifest,
    verify_golden_files_match_manifest,
)
from fixtures.phase0_time_anchor import (
    SIGN_OFF_RUN_COUNT,
    UTCNOW_PATCH_TARGETS,
    inject_phase0_time,
    pipeline_final_anchor,
)
from fixtures.phase0_golden_fixture import CYCLE_ANCHORS, REFERENCE_NOW


class TestOracleManifestPresent:
    def test_manifest_file_exists(self):
        assert (GOLDEN_DIR / MANIFEST_FILENAME).is_file()

    def test_manifest_declares_frozen_status(self):
        manifest = load_manifest()
        assert manifest["phase_0_status"] == "frozen"
        assert manifest["oracle_id"] == "phase0-wildfire-oracle-v1"

    def test_manifest_lists_all_golden_artifacts(self):
        manifest = load_manifest()
        manifest_files = {a["filename"] for a in manifest["artifacts"]}
        assert manifest_files == set(GOLDEN_ARTIFACT_FILES)

    def test_manifest_records_reference_now_and_cycle_anchors(self):
        manifest = load_manifest()
        assert manifest["reference_now"] == REFERENCE_NOW.isoformat()
        assert manifest["cycle_anchors"] == [a.isoformat() for a in CYCLE_ANCHORS]

    def test_manifest_documents_time_anchor_utility(self):
        manifest = load_manifest()
        assert manifest["harness_modules"]["time_anchor"] == (
            "tests/fixtures/phase0_time_anchor.py"
        )


class TestOracleSha256Integrity:
    def test_on_disk_golden_files_match_manifest_hashes(self):
        verify_golden_files_match_manifest()

    def test_regenerated_artifacts_match_manifest_hashes(self):
        verify_generated_match_manifest(generate_golden_artifacts())

    @pytest.mark.parametrize("filename", GOLDEN_ARTIFACT_FILES)
    def test_regenerated_text_matches_golden_file_bytes(self, filename: str):
        expected_bytes = (GOLDEN_DIR / filename).read_bytes()
        generated = generate_golden_artifacts()[filename]
        generated_bytes = generated.encode("utf-8")
        assert generated_bytes == expected_bytes
        manifest_hash = manifest_artifact_index()[filename]
        assert sha256_text(generated) == manifest_hash
        assert sha256_file(GOLDEN_DIR / filename) == manifest_hash


class TestOracleDeterminismSignOff:
    def test_ten_consecutive_full_pipeline_runs_are_identical(self):
        """WP0.3 sign-off gate: entire artifact set stable across ten runs."""
        runs = [generate_golden_artifacts() for _ in range(SIGN_OFF_RUN_COUNT)]
        first = runs[0]
        for idx, run in enumerate(runs[1:], start=2):
            assert run == first, f"run {idx} differed from run 1"

    def test_ten_consecutive_full_pipeline_runs_match_manifest(self):
        for _ in range(SIGN_OFF_RUN_COUNT):
            verify_generated_match_manifest(generate_golden_artifacts())

    def test_ten_consecutive_raw_pipeline_structures_are_identical(self):
        import asyncio

        def _once():
            return asyncio.run(run_phase0_golden_pipeline())

        runs = [_once() for _ in range(SIGN_OFF_RUN_COUNT)]
        baseline = json.dumps(runs[0], sort_keys=True, default=str)
        for idx, run in enumerate(runs[1:], start=2):
            assert json.dumps(run, sort_keys=True, default=str) == baseline, (
                f"structured pipeline run {idx} differed"
            )


class TestPhase0TimeAnchorUtility:
    def test_patch_targets_cover_pipeline_modules(self):
        assert "app.modules.analytics.analytics_service.utcnow" in UTCNOW_PATCH_TARGETS
        assert "app.modules.analytics.threat_assessment_service.utcnow" in UTCNOW_PATCH_TARGETS
        assert "app.modules.analytics.command_center_service.utcnow" in UTCNOW_PATCH_TARGETS

    def test_inject_phase0_time_pins_utcnow(self):
        from app.models.base import utcnow as base_utcnow
        from app.modules.analytics import analytics_service

        anchor = pipeline_final_anchor()
        with inject_phase0_time(anchor):
            assert analytics_service.utcnow() == anchor
            assert base_utcnow() != anchor  # unpatchable base remains wall-clock

    def test_pipeline_final_anchor_is_last_cycle(self):
        assert pipeline_final_anchor() == CYCLE_ANCHORS[-1]
