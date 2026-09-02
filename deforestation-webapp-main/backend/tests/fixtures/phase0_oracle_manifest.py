"""Oracle manifest loader and SHA-256 integrity helpers (WP0.3)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
MANIFEST_FILENAME = "ORACLE_MANIFEST.json"

GOLDEN_ARTIFACT_FILES: tuple[str, ...] = (
    "cycle_0_regional_baselines.json",
    "cycle_0_anomalies.json",
    "cycle_0_intelligence_events.json",
    "cycle_1_regional_baselines.json",
    "cycle_1_anomalies.json",
    "cycle_1_intelligence_events.json",
    "incident_aggregation.json",
    "command_center_snapshot.json",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def manifest_path() -> Path:
    return GOLDEN_DIR / MANIFEST_FILENAME


def load_manifest() -> dict[str, Any]:
    return json.loads(manifest_path().read_text(encoding="utf-8"))


def manifest_artifact_index(manifest: dict[str, Any] | None = None) -> dict[str, str]:
    """Return ``{filename: sha256_hex}`` from the manifest."""
    doc = manifest if manifest is not None else load_manifest()
    return {entry["filename"]: entry["sha256"] for entry in doc["artifacts"]}


def verify_golden_files_match_manifest(manifest: dict[str, Any] | None = None) -> None:
    """Raise ``AssertionError`` if any on-disk golden file differs from the manifest."""
    expected = manifest_artifact_index(manifest)
    for filename, manifest_hash in expected.items():
        path = GOLDEN_DIR / filename
        actual = sha256_file(path)
        if actual != manifest_hash:
            raise AssertionError(
                f"{filename}: manifest sha256 {manifest_hash} != file {actual}"
            )


def verify_generated_match_manifest(
    generated: dict[str, str],
    manifest: dict[str, Any] | None = None,
) -> None:
    """Raise ``AssertionError`` if regenerated artifact text differs from the manifest."""
    expected = manifest_artifact_index(manifest)
    for filename, manifest_hash in expected.items():
        if filename not in generated:
            raise AssertionError(f"missing regenerated artifact: {filename}")
        actual = sha256_text(generated[filename])
        if actual != manifest_hash:
            raise AssertionError(
                f"{filename}: manifest sha256 {manifest_hash} != regenerated {actual}"
            )
