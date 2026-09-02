# Ten consecutive runs of the determinism set, asserting an identical outcome
# every time and byte-identical Phase 0 golden artifacts throughout.
#
#   powershell -File scripts/determinism_check.ps1
#
# The set is written out explicitly so the composition is reviewable rather than
# reconstructed from memory: the frozen Phase 0 oracle, the engine suites whose
# output the oracle depends on, and the commercial suites.

$ErrorActionPreference = "Stop"

# `get_settings()` reads these three directly and is lru-cached, so a partial
# selection that never loads an environment fails where the full suite passes
# only because an earlier module happened to warm the cache. Supplying them here
# makes the harness independent of test ordering. They point at nothing: no test
# in this selection opens a connection.
$env:MONGO_URL = "mongodb://localhost:27017"
$env:DB_NAME = "forestwatch_determinism"
$env:JWT_SECRET = "determinism-harness"

$phase0 = @(
    "tests/test_phase0_oracle_integrity.py",
    "tests/test_phase0_golden_outputs.py",
    "tests/test_phase0_fixture.py",
    "tests/test_wildfire_baseline_detector.py",
    "tests/test_romania_intelligence_seed.py"
)
$engine = @(
    "tests/test_anomaly_detection.py",
    "tests/test_regional_baselines.py",
    "tests/test_segmented_baselines.py",
    "tests/test_reconciliation.py",
    "tests/test_intelligence_events.py",
    "tests/test_incident_aggregation.py",
    "tests/test_command_center.py",
    "tests/test_detection_contract.py",
    "tests/test_detector_registry.py",
    "tests/test_intelligence_event_model.py"
)
$commercial = @(
    "tests/test_billing_plan_catalog.py",
    "tests/test_billing_entitlement_sync.py",
    "tests/test_stripe_webhook.py",
    "tests/test_stripe_real_payloads.py",
    "tests/test_billing_configuration_states.py",
    "tests/test_billing_api.py",
    "tests/test_demo_control_plane.py",
    "tests/test_trial_organization.py"
)
$selection = $phase0 + $engine + $commercial

function Get-GoldenFingerprint {
    $parts = Get-ChildItem "tests/fixtures/golden" -Filter "*.json" |
        Sort-Object Name |
        ForEach-Object { "$($_.Name):$((Get-FileHash $_.FullName -Algorithm SHA256).Hash)" }
    return ($parts -join "|")
}

$baselineGolden = Get-GoldenFingerprint
$outcomes = @()

for ($run = 1; $run -le 10; $run++) {
    $output = & python -m pytest @selection -q 2>&1 | Out-String
    $summary = ($output -split "`n" | Select-String -Pattern "^\d+ passed|passed,|failed").Line |
        Select-Object -Last 1
    $normalized = ($summary -replace "in [\d.]+s.*", "").Trim()
    $golden = Get-GoldenFingerprint
    if ($golden -ne $baselineGolden) {
        Write-Output "run $run : GOLDEN ARTIFACTS CHANGED"
        exit 1
    }
    Write-Output "run $run : $normalized"
    $outcomes += $normalized
}

$distinct = $outcomes | Select-Object -Unique
if ($distinct.Count -ne 1) {
    Write-Output "NOT DETERMINISTIC: $($distinct -join ' / ')"
    exit 1
}
if ($outcomes[0] -match "failed") {
    Write-Output "FAILURES PRESENT: $($outcomes[0])"
    exit 1
}
Write-Output "deterministic across 10 runs: $($outcomes[0])"
Write-Output "golden artifacts byte-identical throughout"
