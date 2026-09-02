"""WP0.2 — golden output capture and determinism tests.

Validates that the Phase 0 pipeline produces byte-stable, persistence-free
artifacts matching the frozen golden files in ``tests/fixtures/golden/``.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from fixtures.phase0_golden_harness import (
    generate_golden_artifacts,
    load_golden_file,
    normalize_for_snapshot,
    run_phase0_golden_pipeline,
    snapshot_to_json,
)
from fixtures.phase0_oracle_manifest import GOLDEN_ARTIFACT_FILES, GOLDEN_DIR

GOLDEN_FILES: tuple[str, ...] = GOLDEN_ARTIFACT_FILES

ARTIFACT_KEYS: tuple[str, ...] = (
    "cycle_0_regional_baselines",
    "cycle_0_anomalies",
    "cycle_0_intelligence_events",
    "cycle_1_regional_baselines",
    "cycle_1_anomalies",
    "cycle_1_intelligence_events",
    "incident_aggregation",
    "command_center_snapshot",
)


def _run(coro):
    return asyncio.run(coro)


def _pipeline_artifacts() -> dict:
    return _run(run_phase0_golden_pipeline())


def _assert_no_persistence_fields(value, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            assert key not in {"_id", "id", "created_at", "updated_at", "inserted_at"}, (
                f"persistence field {key!r} at {path}"
            )
            _assert_no_persistence_fields(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            _assert_no_persistence_fields(item, f"{path}[{idx}]")


# ---------------------------------------------------------------------------
# Golden file presence
# ---------------------------------------------------------------------------


class TestGoldenArtifactsPresent:
    @pytest.mark.parametrize("filename", GOLDEN_FILES)
    def test_golden_file_exists(self, filename: str):
        path = GOLDEN_DIR / filename
        assert path.is_file(), f"missing golden artifact: {path}"

    def test_golden_directory_contains_expected_count(self):
        present = {p.name for p in GOLDEN_DIR.glob("*.json")}
        assert set(GOLDEN_FILES) <= present


# ---------------------------------------------------------------------------
# Snapshot stability (required by WP0.2)
# ---------------------------------------------------------------------------


class TestGoldenSnapshotStability:
    @pytest.mark.parametrize("filename", GOLDEN_FILES)
    def test_regenerated_json_matches_golden_bytes(self, filename: str):
        expected_bytes = (GOLDEN_DIR / filename).read_bytes()
        generated = generate_golden_artifacts()[filename]
        assert generated.encode("utf-8") == expected_bytes

    @pytest.mark.parametrize("filename", GOLDEN_FILES)
    def test_ten_consecutive_runs_are_byte_identical(self, filename: str):
        texts = [generate_golden_artifacts()[filename] for _ in range(10)]
        assert len(set(texts)) == 1

    @pytest.mark.parametrize("artifact_key", ARTIFACT_KEYS)
    def test_normalized_pipeline_matches_loaded_golden(self, artifact_key: str):
        golden_name = f"{artifact_key}.json"
        expected = load_golden_file(golden_name)
        actual = normalize_for_snapshot(_pipeline_artifacts()[artifact_key])
        assert actual == expected


# ---------------------------------------------------------------------------
# Persistence field stripping
# ---------------------------------------------------------------------------


class TestPersistenceFieldsStripped:
    @pytest.mark.parametrize("filename", GOLDEN_FILES)
    def test_golden_files_contain_no_persistence_fields(self, filename: str):
        payload = load_golden_file(filename)
        _assert_no_persistence_fields(payload)

    def test_live_pipeline_output_strips_persistence_fields(self):
        artifacts = _pipeline_artifacts()
        for key in ARTIFACT_KEYS:
            _assert_no_persistence_fields(normalize_for_snapshot(artifacts[key]))


# ---------------------------------------------------------------------------
# Behavioral sanity — oracle matches fixture design intent
# ---------------------------------------------------------------------------


class TestGoldenOracleBehavior:
    def test_cycle1_anomaly_regions_match_design(self):
        anomalies = load_golden_file("cycle_1_anomalies.json")["anomalies"]
        regions = {a["region"] for a in anomalies}
        assert regions == {"Suceava", "Cluj"}

    def test_cycle1_intelligence_events_active_and_resolved_mix(self):
        events = load_golden_file("cycle_1_intelligence_events.json")
        active_regions = {e["region"] for e in events["active"]}
        resolved_regions = {e["region"] for e in events["resolved"]}
        assert active_regions == {"Suceava", "Cluj"}
        assert resolved_regions == {"Bacău"}

    def test_intelligence_events_carry_scoring_fields(self):
        events = load_golden_file("cycle_1_intelligence_events.json")
        for bucket in ("active", "resolved"):
            for event in events[bucket]:
                for field in (
                    "detection_count",
                    "current_score",
                    "escalation_level",
                    "trend",
                    "priority_score",
                ):
                    assert field in event

    def test_incident_aggregation_includes_wildfire_rollup(self):
        payload = load_golden_file("incident_aggregation.json")
        assert "wildfire" in payload["aggregators"]
        assert payload["by_incident_category"]["wildfire"]["event_count"] > 0

    def test_command_center_snapshot_includes_incident_aggregation(self):
        snapshot = load_golden_file("command_center_snapshot.json")
        assert "incident_aggregation" in snapshot
        assert snapshot["active_intel_by_category"]["wildfire"] == 2


# ---------------------------------------------------------------------------
# JSON canonical form
# ---------------------------------------------------------------------------


class TestCanonicalJsonForm:
    @pytest.mark.parametrize("filename", GOLDEN_FILES)
    def test_golden_files_use_sorted_dict_keys(self, filename: str):
        raw = (GOLDEN_DIR / filename).read_text(encoding="utf-8")
        parsed = json.loads(raw)
        reserialized = json.dumps(parsed, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        assert raw == reserialized

    @pytest.mark.parametrize("artifact_key", ARTIFACT_KEYS)
    def test_snapshot_helper_produces_valid_json(self, artifact_key: str):
        payload = _pipeline_artifacts()[artifact_key]
        text = snapshot_to_json(payload)
        assert json.loads(text) == normalize_for_snapshot(payload)
