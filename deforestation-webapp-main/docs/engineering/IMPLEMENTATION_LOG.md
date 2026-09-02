# Implementation Log

**Purpose:** Permanent, cumulative engineering journal for the execution of the
ForestWatch platform roadmap. Every completed implementation task is recorded here as a
new, append-only entry. Entries are never overwritten or deleted.

**Authority:** This log is subordinate to the frozen Architecture v1.0
(`docs/architecture/`), its ADRs, and the phase specifications and backlogs under
`docs/engineering/`. It records *what was done*; it does not make architectural decisions.

**Entry format:** Each entry contains — Date, Work Package, Task ID, Objective,
Files Modified, Files Created, Tests Added or Updated, Verification Performed, Result, and
Notes / Follow-up.

---

## 2026-07-16 — WP0 · WP0.1 — Define the frozen seed fixture

- **Date:** 2026-07-16
- **Work Package:** WP0 — Characterization Baseline & Golden Dataset
- **Task ID:** WP0.1 — Define the frozen seed fixture
- **Objective:** Provide a single deterministic input dataset of wildfire forest events
  that drives the existing intelligence pipeline across at least two reconciliation cycles
  and yields a non-trivial mix of active, newly-created, and resolved outcomes, to serve as
  the frozen regression input for all later Phase 0 work packages.
- **Files Modified:** None.
- **Files Created:**
  - `backend/tests/fixtures/__init__.py` — marks the shared test-fixtures package.
  - `backend/tests/fixtures/phase0_golden_fixture.py` — the frozen fixture: fixed UTC time
    anchor (`REFERENCE_NOW`), two ordered cycle anchors, `build_wildfire_events()` returning
    a deterministic list of fresh event dicts across four Romania regions, plus documented
    design-intent constants and the window model mirroring `AnalyticsRepository`.
  - `backend/tests/test_phase0_fixture.py` — fixture tests (see below).
- **Tests Added or Updated:** `backend/tests/test_phase0_fixture.py` (16 tests) covering:
  (1) loader determinism — repeated loads equal and independent, stable event count,
  timezone-aware UTC anchor, ordered ≥2 cycle anchors; (2) structural invariants — all
  events wildfire, Romania-flagged, timezone-aware timestamps, multiple regions, unique
  source event ids; (3) fixture-design self-check — using elementary window arithmetic (not
  the production engine) it proves cycle-1 anomalies `{Suceava, Bacău}`, cycle-2 anomalies
  `{Suceava, Cluj}`, and therefore a persistent (Suceava), new (Cluj), and resolved (Bacău)
  mix, with Harghita as a never-anomalous control.
- **Verification Performed:**
  - `python -m pytest tests/test_phase0_fixture.py -v` → 16 passed.
  - `python -m pytest tests/test_anomaly_detection.py tests/test_regional_baselines.py
    tests/test_incident_aggregation.py -q` → 113 passed (no regressions).
  - `python -m pytest --co -q` → 1204 tests collected; the new fixture package and test
    collect cleanly. The only 3 collection errors are pre-existing live-integration
    harnesses (`backend_test.py`, `test_analytics.py`, `test_ingestion.py`) that require the
    `REACT_APP_BACKEND_URL` environment variable at import time; they are unrelated to this
    change.
- **Result:** Complete. Deterministic frozen fixture committed and available for later WP
  tests to reference. Repository left in a working state with existing unit tests green.
- **Notes / Follow-up:** WP0.1 defines the *input* only. Capturing the authoritative golden
  outputs by running the current pipeline over this fixture is WP0.2; establishing the
  repeated-run determinism harness and reviewer sign-off is WP0.3. No production code was
  modified and no architectural decision was introduced.

---

## 2026-07-16 — WP0 · WP0.1 — Fixture validation addendum (pre-WP0.2 gate)

- **Date:** 2026-07-16
- **Work Package:** WP0 — Characterization Baseline & Golden Dataset
- **Task ID:** WP0.1 (post-approval validation, before WP0.2)
- **Objective:** Confirm the frozen fixture satisfies every architectural determinism
  assumption required to serve as the permanent Phase 0 oracle, and correct any weakness
  before golden outputs are generated.
- **Files Modified:** `backend/tests/test_phase0_fixture.py` (added guard tests only).
- **Files Created:** None.
- **Tests Added or Updated:** Added `TestArchitecturalDeterminismGuards` (6 tests): absolute
  anchoring to `REFERENCE_NOW` (not wall-clock), zero UTC offset on every timestamp,
  deterministic IDs across loads, deterministic ordering across loads, and window-boundary
  clearance at each cycle anchor (parametrized). Fixture file `test_phase0_fixture.py` now
  totals 22 tests.
- **Verification Performed:** `python -m pytest tests/test_phase0_fixture.py -v` → 22 passed.
- **Result:** Complete. No weakness found in the fixture; no fixture data changed. The eight
  required properties are satisfied and now permanently asserted: deterministic timestamps,
  ordering, and IDs; no hidden randomness; no local-timezone dependency (UTC anchor +
  timedelta only); no current-date/time dependency; no MongoDB insertion-order dependency
  (pure Python data); no dict-iteration-order dependency (dicts are keyed lookups; output is
  built from an ordered list).
- **Notes / Follow-up:** These are fixture-level guarantees. WP0.2 capture must add its own
  guardrails when persisting/reading through MongoDB: project out server-assigned fields
  (`_id`, any insert-time `created_at`), inject `REFERENCE_NOW`/cycle anchors as the only
  time source, and canonically sort any aggregation output that lacks a stable server-side
  sort (e.g. `by_severity`) before snapshotting.

---

## 2026-07-22 — WP0 · WP0.2 — Capture golden outputs

- **Date:** 2026-07-22
- **Work Package:** WP0 — Characterization Baseline & Golden Dataset
- **Task ID:** WP0.2 — Capture golden outputs
- **Objective:** Run the existing wildfire intelligence pipeline over the WP0.1 frozen
  fixture across two reconciliation cycles; capture deterministic golden artifacts
  (anomalies, baselines, intelligence events, incident aggregation, command-center
  snapshot) as the Phase 0 regression oracle.
- **Files Modified:**
  - `docs/engineering/IMPLEMENTATION_LOG.md` — this entry.
- **Files Created:**
  - `backend/tests/fixtures/phase0_golden_harness.py` — in-memory fixture-backed
    repository stand-ins, snapshot normalization (persistence-field stripping,
    ISO datetime serialization, sorted dict keys), and two-cycle pipeline runner.
  - `backend/tests/fixtures/golden/cycle_0_regional_baselines.json`
  - `backend/tests/fixtures/golden/cycle_0_anomalies.json`
  - `backend/tests/fixtures/golden/cycle_0_intelligence_events.json`
  - `backend/tests/fixtures/golden/cycle_1_regional_baselines.json`
  - `backend/tests/fixtures/golden/cycle_1_anomalies.json`
  - `backend/tests/fixtures/golden/cycle_1_intelligence_events.json`
  - `backend/tests/fixtures/golden/incident_aggregation.json`
  - `backend/tests/fixtures/golden/command_center_snapshot.json`
  - `backend/tests/test_phase0_golden_outputs.py` — golden snapshot stability and
    oracle-behavior tests (see below).
- **Tests Added or Updated:** `backend/tests/test_phase0_golden_outputs.py` (63 tests):
  golden file presence; byte-stable regeneration (single run + 10 consecutive runs per
  artifact); normalized pipeline equality against loaded goldens; persistence-field
  stripping assertions; design-intent sanity (Suceava persistent, Bacău resolved, Cluj
  new; scoring fields present; wildfire rollup and command-center wiring); canonical
  JSON form (sorted dict keys).
- **Verification Performed:**
  - `python -m pytest tests/test_phase0_golden_outputs.py -v` → 63 passed.
  - `python -m pytest tests/test_phase0_fixture.py tests/test_anomaly_detection.py tests/test_regional_baselines.py tests/test_incident_aggregation.py tests/test_intelligence_events.py -q` → no regressions.
- **Result:** Complete. Eight golden artifacts frozen under `tests/fixtures/golden/`.
  No production code modified. Oracle documents cycle-0 anomalies `{Suceava, Bacău}`,
  cycle-1 anomalies `{Suceava, Cluj}`, and post-cycle-1 intelligence state: two active
  (Suceava updated, Cluj new) and one resolved (Bacău).
- **Notes / Follow-up:** WP0.3 remains — repeated-run harness sign-off and reviewer
  approval to declare the oracle formally frozen. Harness uses in-memory repositories
  mirroring `AnalyticsRepository.regional_baselines` / overview / by_event_type; MongoDB
  is not required for golden capture or CI regression.

---

## 2026-07-22 — WP0 · WP0.3 — Determinism harness and sign-off

- **Date:** 2026-07-22
- **Work Package:** WP0 — Characterization Baseline & Golden Dataset
- **Task ID:** WP0.3 — Determinism harness and sign-off
- **Objective:** Consolidate shared time-anchor injection, execute ten consecutive
  end-to-end pipeline runs with byte-identical outputs, publish an Oracle Manifest with
  SHA-256 hashes for every golden artifact, and formally freeze the Phase 0 regression
  oracle.
- **Files Modified:**
  - `backend/tests/fixtures/phase0_golden_harness.py` — uses shared
    `inject_phase0_time`; artifact filenames sourced from manifest constants; LF writes.
  - `backend/tests/fixtures/golden/*.json` (8 artifacts) — normalized to UTF-8 LF bytes
    (JSON content unchanged; enables cross-platform SHA-256 integrity).
  - `backend/tests/test_phase0_golden_outputs.py` — imports shared `GOLDEN_DIR` /
    `GOLDEN_ARTIFACT_FILES`; byte-level golden comparison on Windows.
  - `docs/engineering/IMPLEMENTATION_LOG.md` — this entry.
- **Files Created:**
  - `backend/tests/fixtures/phase0_time_anchor.py` — shared `inject_phase0_time`
    context manager patching all pipeline `utcnow()` targets; `SIGN_OFF_RUN_COUNT = 10`.
  - `backend/tests/fixtures/phase0_oracle_manifest.py` — manifest loader, SHA-256 helpers,
    and integrity verification functions.
  - `backend/tests/fixtures/golden/ORACLE_MANIFEST.json` — frozen oracle manifest
    (`phase0-wildfire-oracle-v1`, status `frozen`) with per-artifact SHA-256 hashes.
  - `backend/tests/test_phase0_oracle_integrity.py` — manifest presence, hash integrity,
    ten-run sign-off, and time-anchor utility tests.
- **Tests Added or Updated:** `backend/tests/test_phase0_oracle_integrity.py` (20 tests):
  manifest frozen status; all eight artifact hashes; regenerated vs. on-disk vs. manifest
  byte equality; ten consecutive full-pipeline byte-identical runs; ten-run manifest hash gate;
  ten consecutive structured pipeline equality; time-anchor patch coverage.
- **Verification Performed:**
  - `python -m pytest tests/test_phase0_oracle_integrity.py -v` → 20 passed.
  - `python -m pytest tests/test_phase0_oracle_integrity.py tests/test_phase0_golden_outputs.py tests/test_phase0_fixture.py -q` → 106 passed.
  - Related regression suite (anomaly, baselines, aggregation, intel events, command center) → 163 passed.
- **Result:** Complete. **Phase 0 oracle formally frozen.** WP0 (WP0.1–WP0.3) complete;
  WP1 may proceed under `PHASE-0-IMPLEMENTATION-BACKLOG.md` critical path.
- **Notes / Follow-up:** Golden artifact files normalized to UTF-8 LF bytes (JSON content
  unchanged). Oracle changes require a new manifest version and explicit unfreeze/review.
  MongoDB capture path remains optional; in-memory harness is the CI authority.

---

## 2026-07-22 — WP1 — Canonical Identity & Detection Contract

- **Date:** 2026-07-22
- **Work Package:** WP1 — Canonical Identity & Detection Contract (definitions)
- **Task ID:** WP1.1–WP1.4 (complete work package)
- **Objective:** Introduce canonical identity, Detection envelope, detector framework,
  and wildfire baseline detector migration while preserving the frozen Phase 0 oracle.
- **Files Modified:**
  - `backend/app/models/intelligence_event.py` — ADR-008 field model, `from_persisted`,
    mapping helpers.
  - `backend/app/core/ecosystem/__init__.py` — export canonical identity and legacy defaults.
  - `backend/app/modules/analytics/analytics_service.py` — `get_anomalies()` routes through
    detector registry with lossless legacy projection.
  - `docs/engineering/IMPLEMENTATION_LOG.md` — this entry.
- **Files Created:**
  - `backend/app/core/ecosystem/canonical_identity.py` — `(incident_category, spatial_key)`.
  - `backend/app/core/ecosystem/intelligence_event_defaults.py` — WP1.4 read-model defaults.
  - `backend/app/modules/analytics/detection_contract.py` — ADR-009 `Detection` envelope.
  - `backend/app/modules/analytics/detector_contract.py` — `Detector` ABC.
  - `backend/app/modules/analytics/detector_registry.py` — open/closed registry.
  - `backend/app/modules/analytics/detection_adapters.py` — legacy anomaly ↔ Detection.
  - `backend/app/modules/analytics/detectors/wildfire_baseline_detector.py` — first detector.
  - `backend/tests/test_canonical_identity.py`
  - `backend/tests/test_detection_contract.py`
  - `backend/tests/test_intelligence_event_model.py`
  - `backend/tests/test_detector_registry.py`
  - `backend/tests/test_wildfire_baseline_detector.py`
- **Tests Added or Updated:** 24 new WP1 tests; existing anomaly, intelligence, oracle suites
  unchanged (all green).
- **Verification Performed:**
  - `python -m pytest tests/test_phase0_oracle_integrity.py tests/test_phase0_golden_outputs.py -q` → passed.
  - WP1 + related regression suites → passed.
- **Result:** Complete. Detection contracts and wildfire detector registration in place;
  Phase 0 oracle byte-identical.
- **Notes / Follow-up:** WP2 (category-segmented baselines) is next on the critical path.
  Reconciliation still keys `(event_type, region)` until WP4. NASA FIRMS live integration
  remains on scheduler/ingestion path — not gated by WP1.

---

## 2026-07-22 — WP2 — Category-Segmented Baselines & Anomaly Analysis

- **Date:** 2026-07-22
- **Work Package:** WP2 — Category-Segmented Baselines & Anomaly Analysis (complete)
- **Task ID:** WP2.1–WP2.5
- **Objective:** Segment regional baseline aggregation by `(region, incident_category)`,
  thread category through shaping and anomaly evaluation, and preserve wildfire oracle
  equivalence.
- **Files Modified:**
  - `backend/app/modules/analytics/analytics_repository.py` — compound `$group` by
    region + derived category.
  - `backend/app/modules/analytics/analytics_service.py` — category-aware
    `_compute_baselines`, `_evaluate_anomalies`, registry-backed reconcile path.
  - `backend/app/modules/analytics/detectors/wildfire_baseline_detector.py` — filters
    wildfire segments before evaluation.
  - `backend/tests/fixtures/phase0_golden_harness.py` — segmented aggregation mirror;
    oracle uses `include_incident_category=False` and wildfire-only evaluation.
  - `backend/tests/test_regional_baselines.py` — composite `_id` + `incident_category`.
  - `backend/tests/test_anomaly_detection.py` — composite raw rows.
  - `backend/tests/test_romania_intelligence_seed.py` — threshold import from WP2 config.
  - `docs/engineering/IMPLEMENTATION_LOG.md` — this entry.
- **Files Created:**
  - `backend/app/modules/analytics/segmented_baseline.py` — aggregation helpers, segment
    key parsing, category filter.
  - `backend/app/modules/analytics/anomaly_thresholds.py` — per-category threshold config.
  - `backend/tests/test_segmented_baselines.py` — 14 WP2 unit tests (segmentation,
    isolation, thresholds, oracle equivalence).
- **Tests Added or Updated:** 14 new segmented-baseline tests; existing regional,
  anomaly, oracle, intelligence, and seed suites updated and green.
- **Verification Performed:**
  - Oracle integrity + golden outputs → passed (byte-identical).
  - WP1 + WP2 + related regression (404 tests) → passed.
- **Result:** Complete. Baselines and anomalies are category-segmented; wildfire detector
  and registry unchanged in contract; Phase 0 oracle preserved.
- **Notes / Follow-up:** WP3 (detector abstraction formalization) is largely delivered in
  WP1; WP4 canonical reconciliation over Detections is next on the critical path.

---

## 2026-07-22 — WP3 — Canonical Detection-Driven Reconciliation

- **Date:** 2026-07-22
- **Work Package:** WP3 — Canonical Detection-Driven Reconciliation (complete)
- **Task ID:** WP3.1–WP3.5
- **Objective:** Reconcile intelligence events from canonical Detection envelopes keyed by
  ``(incident_category, spatial_key)``, produce deterministic change-sets, and preserve
  the frozen Phase 0 wildfire oracle.
- **Files Modified:**
  - `backend/app/modules/analytics/intelligence_events_service.py` — `reconcile_detections()`,
    canonical identity lookup, change-set output; legacy `reconcile()` wrapper retained.
  - `backend/app/modules/analytics/intelligence_events_repository.py` —
    `find_active_by_identity()`.
  - `backend/app/modules/analytics/analytics_service.py` — passes Detections from registry
    to `reconcile_detections()`.
  - `backend/tests/fixtures/phase0_golden_harness.py` — registry-driven reconciliation path.
  - `backend/tests/test_intelligence_events.py` — analytics integration expects Detections.
  - `docs/engineering/IMPLEMENTATION_LOG.md` — this entry.
- **Files Created:**
  - `backend/app/modules/analytics/reconciliation.py` — identity helpers, dedupe,
    `ReconciliationChangeSet` / `ReconciliationTransition`.
  - `backend/tests/test_reconciliation.py` — 15 WP3 reconciliation tests.
- **Tests Added or Updated:** 15 new reconciliation tests; oracle, intelligence, escalation,
  trend, and priority suites green (468 total in regression bundle).
- **Verification Performed:**
  - Phase 0 oracle integrity + golden outputs → byte-identical.
  - WP3 reconciliation + WP0–WP2 regression bundle → 468 passed.
- **Result:** Complete. Reconciliation consumes Detections; identity is
  ``(incident_category, spatial_key)``; multi-category coexistence proven; wildfire oracle
  unchanged.
- **Notes / Follow-up:** Read model still omits persisted ``spatial_key`` / ``signal_type`` for
  oracle compatibility. WP4 (command–query separation, aggregation generalization) is next.

---

## 2026-08-11 — WP6.1 — Remove Reconciliation from the Read Path

- **Date:** 2026-08-11
- **Work Package:** WP6 — Command–Query Separation (WP6.1 only)
- **Task ID:** WP6.1
- **Objective:** Make ``GET /api/analytics/intelligence/events`` strictly read-only so
  multi-instance deployment is safe; reconciliation remains on the command/scheduler path.
- **Files Modified:**
  - `backend/app/modules/analytics/analytics_routes.py` — route calls
    ``IntelligenceEventsService.get_events()`` instead of
    ``AnalyticsService.reconcile_intelligence_events()``; removed ``analytics_service_dep``
    from the handler.
  - `docs/engineering/IMPLEMENTATION_LOG.md` — this entry.
- **Files Created:**
  - `backend/tests/test_intelligence_events_read_path.py` — 7 WP6.1 read-path tests.
- **Read/Write Separation:** The events read endpoint queries persisted
  ``IntelligenceEvents``, applies existing read-model normalization, and performs zero
  ``create``/``update``/``resolve`` operations. No detector registry or reconciliation
  stack is invoked on GET.
- **Reconciliation Ownership:** Unchanged command path —
  ``SchedulerService._run_cycle()`` → ``AnalyticsService.reconcile_intelligence_events()``
  → registry ``detect_all()`` → ``IntelligenceEventsService.reconcile_detections()``.
  No new command endpoint added (scheduler-only suffices for WP6.1).
- **Tests Added:** Read-only GET contract, zero repository writes, no detector/reconcile
  invocation, repeated GET idempotence, legacy normalization (``spatial_key`` /
  ``signal_type`` omitted), auth dependency preserved, scheduler still reconciles.
- **Verification Performed:**
  - `python -m pytest tests/test_phase0_oracle_integrity.py tests/test_phase0_golden_outputs.py -q` → passed (8 golden artifacts and ``ORACLE_MANIFEST.json`` hashes unchanged; ten-run determinism green).
  - WP6.1 + intelligence, scheduler, reconciliation, anomaly, command-center, escalation, trend, priority, segmented-baseline regression → 453 passed.
  - `tests/test_analytics.py` skipped in this environment (pre-existing ``REACT_APP_BACKEND_URL`` collection error; unrelated to WP6.1).
- **Result:** Complete. ``GET /api/analytics/intelligence/events`` is side-effect free;
  Phase 0 oracle byte-identical.
- **Notes / Follow-up:** WP6.2–WP6.4 (scheduler ownership confirmation, optional explicit
  command, full read-path write-spy suite) remain. WP7 advisory locking and WP8 index
  migrations are next on the critical path after WP6.

---

## 2026-08-11 — WP6.2–WP6.4 — Command–Query Separation (complete)

- **Date:** 2026-08-11
- **Work Package:** WP6 — Command–Query Separation (WP6.2, WP6.3, WP6.4)
- **Task ID:** WP6.2–WP6.4
- **Objective:** Complete the command–query separation package: formal scheduler ownership,
  explicit reconciliation command boundary decision, and full intelligence read-path
  write-spy coverage.
- **Files Modified:**
  - `backend/app/modules/analytics/reconciliation.py` — production ownership constants,
    documented command chain, ``EXPLICIT_HTTP_RECONCILE_COMMAND = False``.
  - `docs/engineering/IMPLEMENTATION_LOG.md` — this entry.
- **Files Created:**
  - `backend/tests/fixtures/intelligence_write_spy.py` — reusable write-spy bundle and
    parametrized route discovery helpers.
  - `backend/tests/test_reconciliation_ownership.py` — WP6.2/WP6.3 ownership and boundary
    tests (12 tests).
  - `backend/tests/test_intelligence_read_write_spy.py` — WP6.4 parametrized write-spy
    suite across 19 intelligence GET routes (63 tests).
- **WP6.2 — Scheduler ownership:** Audited production code; only
  ``SchedulerService._run_cycle()`` awaits ``reconcile_intelligence_events``; only
  ``AnalyticsService.reconcile_intelligence_events()`` calls ``reconcile_detections``.
  Command chain verified:
  scheduler → ``reconcile_intelligence_events()`` → ``detect_all()`` →
  ``reconcile_detections()``. Reconciliation skipped when ingestion fails.
- **WP6.3 — Explicit command boundary:** ADR-007 permits scheduler *or* explicit command;
  scheduler-only ownership is sufficient for Phase 0 deployment. No HTTP reconcile command
  added. Policy encoded in ``reconciliation.py`` constants and ownership tests.
- **WP6.4 — Read-path write-spy:** All 19 ``GET /api/analytics/intelligence/*`` routes
  proven side-effect free (no ``create``/``update``/``resolve``/``reconcile*`` on read).
  Computation-only reads (e.g. ``/anomalies`` ``detect_all()``) allowed; persistence
  forbidden. Repeated GET idempotence and auth dependencies verified per route.
- **Verification Performed:**
  - Phase 0 oracle integrity + golden outputs → byte-identical.
  - WP6 (77) + WP0–WP3 + reconciliation + scheduler + intelligence regression → 409 passed.
  - `tests/test_analytics.py` not run (pre-existing ``REACT_APP_BACKEND_URL`` collection error).
- **Result:** Complete. WP6 command–query separation package delivered; Phase 0 oracle
  unchanged.
- **Notes / Follow-up:** WP7 (single-reconciler advisory lock) is next on the critical path.
  WP8 (migration/index alignment) follows WP7.

---

## 2026-08-11 — WP7 — Single-Reconciler Guarantee

- **Date:** 2026-08-11
- **Work Package:** WP7 — Single-Reconciler Guarantee (WP7.1–WP7.4)
- **Task ID:** WP7.1–WP7.4
- **Objective:** Ensure at most one scheduler process reconciles ``IntelligenceEvents``
  at a time using MongoDB-backed lease locking, without new infrastructure dependencies.
- **Files Modified:**
  - `backend/app/services/scheduler_service.py` — ``_reconcile_intelligence_with_lock()``;
    optional ``reconciliation_lock`` injection; structured logging for acquire/contention/
    complete/fail/release.
  - `backend/app/modules/analytics/reconciliation.py` — command chain includes advisory lock.
  - `backend/app/core/config.py` — ``reconciliation_lock_lease_seconds`` (default 300, env
    ``RECONCILIATION_LOCK_LEASE_SECONDS``).
  - `backend/server.py` — wires ``ReconciliationAdvisoryLock`` into production scheduler.
  - `backend/tests/test_reconciliation_ownership.py` — updated command chain expectation.
  - `docs/engineering/IMPLEMENTATION_LOG.md` — this entry.
- **Files Created:**
  - `backend/app/repositories/reconciliation_lock_repository.py` — MongoDB atomic acquire/
    release for ``reconciliation_locks`` collection.
  - `backend/app/services/reconciliation_advisory_lock.py` — lease-based advisory lock
    abstraction with crash-recovery semantics.
  - `backend/tests/fixtures/fake_reconciliation_lock_collection.py` — async-safe fake
    collection exercising real repository logic in tests.
  - `backend/tests/test_reconciliation_advisory_lock.py` — 9 lock primitive tests.
  - `backend/tests/test_scheduler_reconciliation_lock.py` — 10 scheduler integration and
    concurrency tests.
- **Lock architecture:** Single document per lock id in ``reconciliation_locks``;
  ``try_acquire()`` via atomic ``find_one_and_update`` + ``insert_one`` fallback;
  ``release()`` expires the lease immediately for the holder. Default lease 300 s; stale
  locks recover automatically after lease expiry if a holder crashes.
- **Scheduler integration:** Reconciliation step acquires lock; contention skips reconcile
  only (cycle continues); ``finally`` releases lock on success or failure.
- **Tests Added:** 19 WP7 tests covering acquisition, contention, release, stale recovery,
  concurrent cycles (single reconciler), failure paths, and scheduler-only ownership.
- **Verification Performed:**
  - Phase 0 oracle integrity + golden outputs → byte-identical.
  - WP7 + WP6 + WP0–WP3 + scheduler + reconciliation + intelligence regression → 302 passed
    in focused bundle (19 WP7 + 283 related).
  - `tests/test_analytics.py` not run (pre-existing ``REACT_APP_BACKEND_URL`` error).
- **Result:** Complete. Single-reconciler guarantee established; Phase 0 oracle unchanged.
- **Notes / Follow-up:** WP8 (migration/index alignment) is next on the critical path.

---

## 2026-08-11 — WP8 — Migration & Index Alignment

- **Date:** 2026-08-11
- **Work Package:** WP8 — Migration & Index Alignment (WP8.1–WP8.4)
- **Task ID:** WP8.1–WP8.4
- **Objective:** Idempotently backfill ``incident_category``, persist canonical
  ``(incident_category, spatial_key)`` identity, align MongoDB indexes, and gate with
  comprehensive migration tests — without modifying the frozen Phase 0 oracle.
- **Files Modified:**
  - `backend/app/modules/analytics/intelligence_events_repository.py` — indexed
    ``find_active_by_identity`` query on canonical fields.
  - `backend/server.py` — named legacy + canonical indexes; startup migration hook.
  - `docs/engineering/IMPLEMENTATION_LOG.md` — this entry.
- **Files Created:**
  - `backend/app/core/intelligence_events_migration.py` — WP8.1 category backfill,
    WP8.2 canonical re-key + collision resolution, WP8.3 index ensure, migration reports.
  - `backend/tests/fixtures/fake_intelligence_events_collection.py` — async-safe fake
    collection for migration tests.
  - `backend/tests/test_intelligence_events_migration.py` — 24 WP8.4 migration tests.
- **WP8.1 — Category backfill:** Preserves valid categories; backfills absent values via
  ``resolve_incident_category`` (legacy anomaly → wildfire); marks invalid taxonomy values
  and ambiguous metadata conflicts without silent overwrite.
- **WP8.2 — Canonical re-key:** Persists ``spatial_key`` from ``region``; syncs ``region``
  from ``spatial_key``; detects active identity collisions; resolves deterministically
  (highest ``detection_count``, then ``last_detected_at``, then ``_id``) by resolving
  losers — no deletion, lifecycle fields preserved on winners.
- **WP8.3 — Index alignment:** Retained legacy ``legacy_event_region_status``
  ``(event_type, region, status)``; added ``canonical_identity_status``
  ``(incident_category, spatial_key, status)``; retained ``last_detected_at``.
- **WP8.4 — Migration verification:** 24 tests covering empty/already-migrated DBs,
  legacy wildfire, multi-category independence, spatial-key independence, collisions,
  reruns, index idempotence, lifecycle/unrelated field preservation, Phase 0 golden
  fixture compatibility, and deterministic reports.
- **Verification Performed:**
  - Phase 0 oracle integrity + golden outputs → byte-identical.
  - WP8 + WP7 + WP6 + WP0–WP3 + scheduler + reconciliation + intelligence regression →
    326 passed.
  - `tests/test_analytics.py` not run (pre-existing ``REACT_APP_BACKEND_URL`` error).
- **Result:** Complete. Persisted intelligence events and indexes aligned with canonical
  model; Phase 0 oracle unchanged.
- **Notes / Follow-up:** WP8.5 operational runbook deferred. Next critical-path work is
  post-WP8 deployment validation and any remaining roadmap items beyond Phase 0 engine
  generalization.

---

## Packages A–G — Platform Generalization (Europe-First Readiness)

- **Date:** 2026-08-11
- **Objective:** Generalize the intelligence pipeline beyond wildfire while preserving
  Phase 0 oracle behavior and all WP1–WP8 guarantees.
- **Files Created:**
  - `backend/app/core/ecosystem/category_registry.py` — centralized category definitions
    (identifier, display name, enabled state, detector/source compatibility).
  - `backend/app/core/ingestion/provider_contract.py` — `IngestionProvider` ABC.
  - `backend/app/core/ingestion/provider_capabilities.py` — future provider capability matrix.
  - `backend/app/modules/analytics/map_contract.py` — canonical map marker serialization.
  - `backend/app/modules/ingestion/providers/synthetic_environmental.py` — synthetic second
    provider for pipeline tests.
  - `backend/tests/test_category_registry.py`
  - `backend/tests/test_generalized_aggregation.py`
  - `backend/tests/test_ingestion_provider_contract.py`
  - `backend/tests/test_map_data_contract.py`
  - `backend/tests/test_platform_generalization.py`
- **Files Modified:**
  - `backend/app/modules/analytics/incident_aggregation.py` — category rollups from
    `by_event_type` mapping (removed wildfire-only merge path).
  - `backend/app/core/ecosystem/incident_categories.py` — shared Mongo `$switch` branch builder.
  - `backend/app/modules/analytics/segmented_baseline.py` — deduplicated category branches.
  - `backend/app/modules/analytics/analytics_repository.py` — region event centroids + map query.
  - `backend/app/modules/analytics/analytics_routes.py` — `GET /intelligence/map-overlay`.
  - `backend/app/api/event_routes.py` — canonical `/events/map` payload.
  - `backend/app/modules/ingestion/providers/firms.py` — implements `IngestionProvider`.
  - `backend/app/services/scheduler_service.py` — multi-provider ingestion loop.
  - `backend/app/services/romania_seed_service.py` — forest-biased seed coordinates.
  - `frontend/src/components/intelligence/IntelligenceMap.jsx` — multi-category map contract,
    `resolveMarkerCoords`, category in popups.
  - `backend/tests/fixtures/intelligence_write_spy.py` — map-overlay read-path spy support.
- **Package A — Generalized aggregation:** `aggregate_all()` builds `by_incident_category`
  from event-type → category mapping; wildfire numerical behavior preserved; isolation test
  added.
- **Package B — Category generalization:** Removed blocking wildfire-only aggregation merge;
  segmented baseline branches centralized; wildfire remains default for legacy anomaly paths.
- **Package C — Ingestion abstraction:** `IngestionProvider` contract; FIRMS preserved;
  synthetic provider proves second source enters shared persist pipeline.
- **Package D — Category registry:** `CategoryRegistry` singleton over existing taxonomy.
- **Package E — Map data contract:** Canonical fields on `/events/map` and
  `/intelligence/map-overlay`; seed coords fixed; frontend prefers event coordinates over
  region centroids.
- **Package F — Europe-first readiness:** `PROVIDER_CAPABILITY_MATRIX` documents required
  provider capabilities without fabricated APIs.
- **Package G — Testing:** Comprehensive generalization suite; oracle + WP regressions green.
- **Map marker root cause:** Seed events placed at administrative region centroids were
  classified as urban land cover, producing red marker borders on city/road coordinates;
  anomaly/intelligence layers lacked event coordinates and fell back to city-centroid lookup.
- **Verification Performed:**
  - ORACLE_MANIFEST unchanged; all golden artifacts byte-identical.
  - Ten-run determinism green (`test_phase0_oracle_integrity`).
  - Full backend suite: 1491 passed (excluding env-dependent integration tests).
  - Intelligence GET routes remain read-only (write-spy suite includes map-overlay).
- **Result:** Complete. Platform generalized for multi-category/multi-provider operation;
  Phase 0 wildfire oracle frozen and unchanged.
- **Remaining MVP blockers:** Live European environmental providers not yet integrated;
  non-wildfire detectors not registered; frontend category filtering/layer styling minimal;
  operational provider credential management and deployment runbook pending.

---

## CLMS Contextual Integration — Europe-First Real Data Phase

- **Date:** 2026-08-11
- **Objective:** Integrate Copernicus Land Monitoring Service (CLMS) as contextual
  intelligence enriching observations/detections — not as a real-time event stream.
- **Files Created:**
  - `backend/app/core/ingestion/contextual_provider_contract.py` — `ContextualDatasetProvider` ABC
  - `backend/app/core/ecosystem/forest_context.py` — `ForestContext` model
  - `backend/app/core/ingestion/clms_attributes.py` — CLC → forest attribute normalization
  - `backend/app/services/clms_context_provider.py` — fixture-first CLMS provider
  - `backend/app/services/forest_context_service.py` — spatial association + refresh
  - `backend/app/modules/analytics/context_enrichment.py` — Detection/map enrichment path
  - `backend/tests/test_clms_integration.py` — 27 deterministic CLMS tests
- **Files Modified:**
  - `backend/app/services/gis_loader.py` — `classify_detailed()` with CLC metadata
  - `backend/app/services/forest_event_service.py` — persists `metadata.forest_context`
  - `backend/app/modules/analytics/map_contract.py` — `forest_context` on map markers
  - `backend/app/modules/analytics/detection_adapters.py` — lat/lng in evidence when present
  - `backend/app/modules/analytics/analytics_routes.py` — `GET /intelligence/clms/dataset`
  - `backend/app/services/scheduler_service.py` — CLMS refresh cadence (separate from FIRMS)
  - `backend/app/core/config.py` — `CLMS_DATASET_PATH`, `CLMS_REFRESH_INTERVAL_DAYS`
  - `backend/app/server.py`, `backend/app/api/deps.py` — wiring
  - `frontend/src/components/intelligence/IntelligenceMap.jsx` — forest/non-forest in popup
  - `backend/tests/fixtures/intelligence_write_spy.py` — CLMS route spy support
- **CLMS integration architecture:** Contextual provider (not `IngestionProvider`) → point
  lookup → `ForestContext` → observation metadata / Detection evidence / map payload.
- **Provider status:** Fixture-first via bundled CORINE GeoJSON; live activation via
  `CLMS_DATASET_PATH` local file only (no fabricated API).
- **Live access:** Not wired — requires operator-supplied CLMS GeoJSON export.
- **Verification:** 1518 tests passed; Phase 0 oracle byte-identical; intelligence GET
  routes side-effect free (21 routes including CLMS dataset metadata).
- **Next dynamic European source:** EFFIS/EMS wildfire bulletins or national forest
  authority APIs — requires verified endpoint + credentials before implementation.

---

## EEA Air Quality — First Non-Wildfire European Environmental Source

- **Date:** 2026-08-11
- **Objective:** Prove multi-domain ingestion → baseline/anomaly → canonical `Detection`
  → reconciliation without architectural changes; first dynamic European non-wildfire source.
- **EEA source:** Air Quality Download Service (E2a/UTD monitoring-station time series).
  Portal: https://aqportal.discomap.eea.europa.eu/download-data/
  API Swagger: https://eeadmz1-downloads-api-appservice.azurewebsites.net/swagger/index.html
- **Live access:** Requires operator-issued token (EEA UTD guide); fixture path active when
  `EEA_AQ_API_TOKEN` unset or live fetch unavailable. Enable scheduler ingestion via
  `ENABLE_EEA_AIR_QUALITY=true`.
- **Files Created:**
  - `backend/app/core/ecosystem/environmental_observation.py` — domain-neutral observation model
  - `backend/app/core/ecosystem/air_quality_constants.py` — pollutant/unit normalization
  - `backend/app/modules/ingestion/providers/eea_air_quality.py` — `EEAAirQualityProvider`
  - `backend/app/modules/analytics/detectors/air_quality_baseline_detector.py`
  - `backend/tests/test_eea_air_quality_integration.py` — 29 deterministic tests
- **Files Modified:**
  - `backend/app/core/ecosystem/incident_categories.py` — `AIR_QUALITY`, metadata resolution,
    `PHASE0_ORACLE_CATEGORY_KEYS` (oracle-safe zero-count slots)
  - `backend/app/core/ecosystem/category_registry.py` — air quality display + detector flag
  - `backend/app/core/ecosystem/canonical_identity.py` — `spatial_key_from_station()`
  - `backend/app/modules/analytics/anomaly_thresholds.py` — air quality thresholds
  - `backend/app/modules/analytics/detector_registry.py` — register `AirQualityBaselineDetector`
  - `backend/app/modules/analytics/detection_adapters.py` — station/pollutant evidence
  - `backend/app/modules/analytics/reconciliation.py` — passthrough AQ metadata fields
  - `backend/app/modules/analytics/segmented_baseline.py` — metadata incident_category in Mongo
  - `backend/app/modules/analytics/incident_aggregation.py` — oracle-safe category rollups
  - `backend/app/modules/analytics/command_center_service.py` — oracle-safe active counts
  - `backend/app/modules/analytics/map_contract.py` — AQ marker fields + station spatial keys
  - `backend/app/core/config.py` — `ENABLE_EEA_AIR_QUALITY`, `EEA_AQ_API_TOKEN`
  - `backend/server.py` — optional EEA provider in scheduler list
  - `backend/app/services/data_source_service.py` — EEA DataSource seed entry
  - `frontend/src/components/intelligence/IntelligenceMap.jsx` — AQ popup fields
- **Observation model:** `EnvironmentalObservation` (pollutant, value, unit, observed_at,
  station coords/ids, provenance) persisted under `metadata.observation`.
- **Category:** Single `air_quality` category; pollutant carried in signal/evidence.
- **Detector:** `air_quality_baseline_deviation` via existing segmented baseline + thresholds.
- **Spatial model:** Station ID as region segment; `aq-station:{id}` spatial key; authoritative
  station coordinates (no region-centroid forcing).
- **CLMS cross-domain:** AQ detections enriched with `ForestContext` when coordinates present.
- **Verification:** 1547 backend tests passed; Phase 0 oracle byte-identical; wildfire detector
  behavior unchanged on Phase 0 fixture.
- **Live activation remaining:** Token issuance from EEA; Parquet download API integration against
  documented Swagger endpoints; bounded hourly window queries.

---

## Europe-First Audit + Copernicus EMS Rapid Mapping

- **Date:** 2026-08-11
- **Objective:** Implementation-level generalization audit; onboard highest-value verified
  European event source (CEMS Rapid Mapping) as third dynamic domain.
- **Audit outcome:** Framework genuinely supports multi-category/provider/detector paths;
  remaining blockers are Romania gating, wildfire defaults, ForestEvent schema coupling, and
  read-path oracle field stripping — not missing abstractions.
- **Selected next provider:** Copernicus EMS Rapid Mapping (public JSON API, no credentials).
- **Files Created:**
  - `backend/app/core/ecosystem/environmental_hazard_constants.py`
  - `backend/app/modules/ingestion/providers/cems_rapid_mapping.py`
  - `backend/app/modules/analytics/detectors/environmental_hazard_baseline_detector.py`
  - `backend/tests/test_cems_rapid_mapping_integration.py`
- **Files Modified:**
  - `incident_categories.py`, `category_registry.py`, `canonical_identity.py`
  - `anomaly_thresholds.py`, `detector_registry.py`, `detection_adapters.py`
  - `reconciliation.py`, `map_contract.py`, `provider_capabilities.py`
  - `config.py`, `server.py`, `data_source_service.py`
  - `frontend/.../IntelligenceMap.jsx`
- **Category:** `environmental_hazard` — hazard type (flood, wildfire, earthquake, etc.) in evidence.
- **Spatial model:** Country-level baseline segmentation; `cems-country:{country}` spatial keys;
  activation centroid coordinates on map markers.
- **Live access:** Public API verified; European filter on live fetch; fixture fallback on failure.
- **Verification:** Full backend suite green; Phase 0 oracle byte-identical.

---

## Geographic Scope Generalization — Europe-First Gate

- **Date:** 2026-08-11
- **Objective:** Replace Romania-only intelligence gating with configurable geographic scope
  (`romania` | `europe` | `all`) while preserving Phase 0 oracle behavior under explicit
  `GEOGRAPHIC_SCOPE=romania`. Ingestion remains unfiltered; intelligence pipeline filters
  at query/detection time.
- **Files Created:**
  - `backend/app/core/geography/geographic_scope.py` — `GeographicScope`, `GeographicScopePolicy`
  - `backend/app/core/geography/europe.py` — European country classifier + Mongo `$expr`
  - `backend/app/core/geography/__init__.py` — package exports
  - `backend/tests/test_geographic_scope.py` — 34 scope/oracle/map/scheduler tests
- **Files Modified:**
  - `backend/app/core/config.py` — `GEOGRAPHIC_SCOPE` env (default `romania`)
  - `backend/app/modules/analytics/analytics_repository.py` — scope-aware baselines, temporal
    counts, map queries, region centroids
  - `backend/app/modules/analytics/segmented_baseline.py` — `scope_policy` parameter
  - `backend/app/modules/analytics/analytics_service.py` — `geographic_scope` in API responses;
    scoped alert volume for non-Romania scopes
  - `backend/app/modules/analytics/analytics_routes.py` — map-overlay scope + centroid policy
  - `backend/app/modules/analytics/map_contract.py` — skip admin centroid for station/activation
  - `backend/tests/fixtures/phase0_golden_harness.py` — explicit `PHASE0_GEOGRAPHIC_SCOPE`
  - `backend/app/modules/ingestion/providers/cems_rapid_mapping.py` — shared Europe classifier
  - `frontend/src/components/intelligence/IntelligenceMap.jsx` — scope-aware marker coords
  - Test updates: `test_anomaly_detection.py`, `test_regional_baselines.py`,
    `test_temporal_intelligence.py`, `test_intelligence_alerts.py`,
    `tests/fixtures/intelligence_write_spy.py`
- **Scope semantics:**
  - `romania` — `metadata.ingestion.is_romania == True` (unchanged Phase 0 behavior)
  - `europe` — Romania + European countries via country metadata / CEMS countries / bbox
  - `all` — no geographic filter
- **Europe classifier:** Explicit country-name set (Copernicus EMS aligned) with coordinate
  bbox fallback; documented in `europe.py`.
- **Unchanged by design:** canonical identity, Detection/DetectorRegistry/ReconciliationChangeSet,
  advisory lock, scheduler ownership, ordinary `/events` queries, Phase 0 golden artifacts.
- **Tests Added:** `test_geographic_scope.py` (34) covering parsing, Romania/Europe/All scopes,
  category isolation, map centroid policy, scheduler delegation, oracle compatibility,
  ingestion independence, determinism.
- **Verification:** 1604 backend unit tests passed (excluding env-dependent integration
  harnesses); Phase 0 oracle manifest + 8 golden artifacts byte-identical; 10-run
  determinism sign-off green.
- **Notes / Follow-up:** Tenant AOI is a future extension point on `GeographicScopePolicy`;
  alert/temporal response field names still say `romania_events` (legacy label, scoped counts).

---

## European Source Reliability & Provenance — Source Intelligence

- **Date:** 2026-08-11
- **Work Package:** European Source Reliability & Provenance
- **Objective:** Make ForestWatch capable of evaluating reliability, provenance, freshness, and
  operational health of multiple European environmental data sources without new providers, ML,
  or Phase 0 oracle changes.
- **Files Created:**
  - `backend/app/core/ingestion/source_descriptor.py` — generalized `SourceDescriptor`
  - `backend/app/core/ingestion/provider_health.py` — health status + run telemetry models
  - `backend/app/core/ingestion/provenance.py` — `ProvenanceEnvelope`, detection/observation builders
  - `backend/app/core/ingestion/source_reliability.py` — generalized scoring + isolated FIRMS alert hook
  - `backend/app/core/ingestion/correlation_key.py` — minimal multi-source correlation key
  - `backend/app/repositories/provider_health_repository.py` — Mongo `provider_health` collection
  - `backend/app/services/source_intelligence_service.py` — read-only descriptor/health aggregation
  - `backend/app/modules/ingestion/provider_registry.py` — `build_ingestion_providers()`
  - `backend/tests/test_source_reliability_provenance.py` — 40+ source intelligence tests
- **Files Modified:**
  - `backend/app/core/ingestion/ingestion_metadata.py` — optional `provider_id`, `dataset_id`,
    `dataset_version`, `provenance_label`
  - `backend/app/core/ingestion/provider_contract.py` — `provider_id` + default `describe()`
  - `backend/app/services/scheduler_service.py` — per-provider isolation, telemetry, health recording
  - `backend/app/repositories/ingestion_runs_repository.py` — `provider_id`, `cycle_id`,
    `observations_rejected`
  - `backend/app/modules/analytics/analytics_service.py` — reliability via generalized module
  - `backend/app/modules/analytics/detection_adapters.py` — provenance on `Detection.evidence`
  - `backend/app/modules/analytics/analytics_routes.py` — `GET /intelligence/source-status`;
    command-center `source_health_summary`
  - Provider modules: `firms.py`, `eea_air_quality.py`, `cems_rapid_mapping.py`,
    `clms_context_provider.py` — `describe()` + extended ingestion metadata
  - `backend/server.py`, `backend/app/api/deps.py` — health repo + source intelligence wiring
  - Scheduler/integration test updates for multi-provider run logging
- **Design decisions:**
  - Provenance on `Detection.evidence` only — not persisted to intelligence metadata (Phase 0 safety)
  - Provider failures no longer block sibling providers or reconciliation
  - Ingestion scope ≠ intelligence scope preserved; provider coverage not labeled Romania-only
  - FIRMS reliability formula unchanged; alert trigger isolated behind `firms_reliability_alert_trigger`
- **Tests Added:** SourceDescriptor, provider health lifecycle, provenance, detection provenance,
  reliability abstraction, correlation key, failure isolation (FIRMS/EEA/CEMS/all-fail/timeout),
  geographic scope vs provider coverage, scheduler telemetry, Command Center summary, API read-only,
  credential stripping, CLMS/Weather compatibility, Phase 0 oracle + ten-run determinism.
- **Verification:** 1640+ backend unit tests passed (excluding env-dependent integration harnesses);
  Phase 0 oracle manifest + 8 golden artifacts byte-identical; wildfire detection output unchanged.
- **Notes / Follow-up:** Cross-source fusion, ML scoring dimensions, and additional providers
  (EFAS/GloFAS, EFFIS, CEMS Risk & Recovery) are subsequent packages.

---

## Cross-Source Correlation & Evidence Persistence

- **Date:** 2026-08-11
- **Work Package:** Cross-Source Correlation & Evidence Persistence
- **Objective:** Turn independent FIRMS, EEA, and CEMS detections into correlated environmental
  intelligence with optional provenance persistence — without changing canonical
  Detection → Reconciliation architecture or Phase 0 oracle behavior.
- **Files Created:**
  - `backend/app/modules/analytics/correlation_config.py` — central rule/threshold config
  - `backend/app/modules/analytics/correlation_result.py` — immutable `CorrelationResult`
  - `backend/app/modules/analytics/cross_source_correlator.py` — dedicated correlator component
  - `backend/app/modules/analytics/provenance_persistence.py` — sanitized provenance for metadata
  - `backend/app/repositories/correlation_repository.py` — Mongo `intelligence_correlations`
  - `backend/app/services/correlation_service.py` — read-only correlation query service
  - `backend/tests/test_cross_source_correlation.py` — 25 correlation/provenance tests
- **Files Modified:**
  - `backend/app/core/config.py` — `ENABLE_INTELLIGENCE_PROVENANCE`, `ENABLE_CROSS_SOURCE_CORRELATION`,
    correlation threshold env vars (all default false/off)
  - `backend/app/modules/analytics/reconciliation.py` — optional provenance in `metadata_from_detection`
  - `backend/app/modules/analytics/intelligence_events_service.py` — provenance flag on persist/read
  - `backend/app/modules/analytics/analytics_service.py` — correlator hook pre-reconciliation
  - `backend/app/modules/analytics/analytics_routes.py` — `GET /intelligence/correlations`,
    `degraded_sources` on command-center route
  - `backend/app/services/source_intelligence_service.py` — `get_degraded_sources()`
  - `backend/app/api/deps.py`, `backend/server.py` — correlation repo wiring
  - `backend/tests/fixtures/intelligence_write_spy.py` — correlation service mock
  - `backend/tests/test_reconciliation_ownership.py` — updated command chain
- **Configuration (default off for Phase 0):**
  - `ENABLE_INTELLIGENCE_PROVENANCE=false`
  - `ENABLE_CROSS_SOURCE_CORRELATION=false`
  - `CORRELATION_SPATIAL_DISTANCE_KM=50`, `CORRELATION_TEMPORAL_HOURS=72`
- **Correlation rules (deterministic):**
  - `firms_cems_wildfire_support` — supporting evidence (wildfire + CEMS wildfire hazard)
  - `firms_eea_contextual` — contextual evidence (fire + nearby AQ anomaly)
  - `eea_cems_multi_source` — multi-source situation (AQ + hazard activation)
- **Integration flow:** Provider → Observation → Detector → Detection → CrossSourceCorrelator
  → Reconciliation → IntelligenceEvent (correlation is command-side only, scheduler-owned)
- **Tests:** Provenance on/off, legacy compatibility, FIRMS↔CEMS/EEA pairs, window boundaries,
  category isolation, deterministic IDs, degraded-source handling, GET route safety, Phase 0 oracle.
- **Verification:** 1673 backend unit tests passed; Phase 0 oracle + 8 golden artifacts byte-identical;
  ten-run determinism green.
- **Notes / Follow-up:** EEA live activation, EFAS/GloFAS, EFFIS, ML fusion, tenant AOI are
  subsequent packages.

---

## Evidence-Aware Command Center

- **Date:** 2026-08-11
- **Work Package:** Evidence-Aware Command Center
- **Objective:** Make cross-source correlation and provenance operationally visible through the
  existing Command Center and read models — without redesigning Command Center, changing
  priority/escalation/trend scoring, or altering Phase 0 golden artifacts.
- **Files Created:**
  - `backend/app/modules/analytics/intelligence_cycle.py` — `detection_fingerprint()`,
    `resolve_intelligence_cycle_id()` (scheduler cycle reuse + fingerprint fallback)
  - `backend/app/repositories/intelligence_cycle_repository.py` — Mongo `intelligence_cycle_state`
  - `backend/app/modules/analytics/evidence_summary.py` — bounded `EvidenceSummary` read model,
    `build_evidence_summary()`, `build_intelligence_evidence_payload()`, `resolve_correlation_state()`
  - `backend/app/services/evidence_aware_command_center_service.py` — read-only evidence assembly
  - `backend/tests/test_evidence_aware_command_center.py` — 15 evidence/cycle/API/oracle tests
  - `frontend/src/components/intelligence/EvidenceIndicator.jsx` — compact evidence indicators
  - `frontend/src/components/intelligence/__tests__/EvidenceIndicator.test.jsx` — 2 UI tests
- **Files Modified:**
  - `backend/app/modules/analytics/analytics_service.py` — stamps correlations with
    `intelligence_cycle_id`; records cycle state after reconciliation
  - `backend/app/services/scheduler_service.py` — passes scheduler `cycle_id` to reconciliation
  - `backend/app/repositories/correlation_repository.py` — `replace_all(..., intelligence_cycle_id=...)`
  - `backend/app/modules/analytics/analytics_routes.py` — command-center adds `intelligence_evidence`;
    new `GET /intelligence/evidence/{correlation_id}` (read-only)
  - `backend/app/api/deps.py`, `backend/server.py` — cycle repo + evidence service wiring
  - `backend/tests/fixtures/intelligence_write_spy.py` — evidence service mock; parameterized route spy
  - `backend/tests/test_cross_source_correlation.py` — InMemoryCorrelationRepo cycle_id support
  - `backend/tests/test_scheduler.py`, `test_scheduler_reconciliation_lock.py`,
    `test_reconciliation_ownership.py` — cycle_id kwarg assertions
  - `frontend/src/api/analytics.js` — `fetchCommandCenter()`
  - `frontend/src/components/intelligence/IntelligenceSection.jsx` — evidence lookup by event id
  - `frontend/src/components/intelligence/ActiveIntelligenceEvents.jsx` — Evidence column
  - `frontend/src/components/intelligence/IntelligenceMap.jsx` — evidence in map popups
- **Cycle consistency mechanism:**
  - Scheduler generates `cycle_id` per ingestion cycle; passed to
    `reconcile_intelligence_events(intelligence_cycle_id=...)`
  - Fallback: `intel-{fingerprint[:16]}` from sorted detection identity hash (not wall-clock)
  - `IntelligenceCycleRepository` stores: `intelligence_cycle_id`, `detection_fingerprint`,
    `correlation_cycle_id`, `reconciled_at`
  - Correlation records stamped with matching `intelligence_cycle_id`
  - Command Center exposes `correlation_state`: `current` | `stale` | `unavailable` | `disabled`
  - Stale correlation never presented as current
- **Evidence read model:**
  - Bounded fields: `evidence_count`, `source_count`, `providers`, `provider_ids`,
    `relationship_types`, `correlation_ids`, `strongest_correlation_strength`, `evidence_state`,
    `correlation_state`, `source_availability`
  - Evidence states: `single_source`, `multi_source`, `contextual_support`, `degraded_source`,
    `unavailable`
  - No raw payloads, credentials, or unbounded arrays; max 3 provenance entries per item
- **Degraded-source semantics:**
  - Uses existing `ProviderHealthRecord` — healthy/degraded/failed/unknown per provider
  - Failed/degraded sources never fabricate evidence; absence never interpreted as negative evidence
  - `source_availability` map distinguishes unavailable vs no matching detection
- **Provenance behavior:**
  - `ENABLE_INTELLIGENCE_PROVENANCE=false` — read behavior unchanged (empty provenance arrays)
  - `ENABLE_INTELLIGENCE_PROVENANCE=true` — bounded provenance: `provider_id`, `source_id`,
    `dataset_id`, `dataset_version`, `source_event_id`, `observed_at`, `detected_at`,
    `geographic_scope`; credentials and raw metadata stripped
- **Feature flags:**
  - `ENABLE_CROSS_SOURCE_CORRELATION=false` — no fabricated correlations; evidence_state appropriate
  - `ENABLE_CROSS_SOURCE_CORRELATION=true` — reads persisted correlation snapshots with cycle check
  - Correlation never executed from GET requests
- **Command Center changes:**
  - `CommandCenterService.get_snapshot()` body unchanged (Phase 0 oracle safe)
  - Route layer adds `intelligence_evidence` alongside existing `source_health_summary`
  - Each item exposes canonical identity, category, severity, escalation, trend, priority,
    evidence summary, correlation state; priority/escalation/trend untouched
- **Tests Added:** Cycle identifier determinism, current/stale/missing correlation snapshots,
  single/multi/contextual evidence, degraded provider, provenance on/off + credential stripping,
  priority unchanged, GET side-effect free, Phase 0 oracle + ten-run determinism,
  correlation flag on/off, frontend EvidenceIndicator contract.
- **Verification:** 1691 backend unit tests passed (excluding env-dependent integration harnesses);
  15 evidence-aware tests; 86 Phase 0 oracle tests green; 2 frontend EvidenceIndicator tests;
  Phase 0 golden artifacts + `ORACLE_MANIFEST.json` byte-identical; ten-run determinism green.
- **Notes / Follow-up:** EEA live activation, EFAS/GloFAS, EFFIS, CEMS Risk & Recovery, ML fusion,
  tenant AOI remain subsequent packages. Recommended next: EEA live activation or multi-region
  operational validation dashboard.

---

## EEA Air Quality Live Activation

- **Date:** 2026-08-11
- **Work Package:** EEA Air Quality Live Activation
- **Objective:** Activate the existing EEA Air Quality provider against the official EEA E2a/UTD
  Parquet Download Service with bounded incremental queries, validation, deterministic deduplication,
  provider health telemetry, and scheduler integration — without altering Phase 0 wildfire oracle output.
- **Official source:**
  - Portal: https://aqportal.discomap.eea.europa.eu/download-data/
  - API: https://eeadmz1-downloads-api-appservice.azurewebsites.net/swagger/index.html
  - Endpoint: `POST /ParquetFile/dynamic` (E2a dataset `dataset=1`)
  - Station metadata: EEA AQViewer CSV (`DataExtract.csv` in ZIP)
- **Files Created:**
  - `backend/app/modules/ingestion/providers/eea_aq_client.py` — bounded HTTP client + token validation
  - `backend/app/modules/ingestion/providers/eea_aq_parquet.py` — safe ZIP/Parquet extraction (max 50k rows)
  - `backend/app/modules/ingestion/providers/eea_aq_station_metadata.py` — authoritative station coordinates
  - `backend/app/modules/ingestion/providers/eea_aq_validation.py` — measurement validation + token sanitization
  - `backend/tests/test_eea_live_activation.py` — 31 live activation tests
- **Files Modified:**
  - `backend/app/modules/ingestion/providers/eea_air_quality.py` — live fetch path, no silent fallback on failure
  - `backend/app/core/config.py` — `EEA_AQ_QUERY_WINDOW_HOURS`, `EEA_AQ_COUNTRIES`
  - `backend/requirements.txt` — `pyarrow>=15.0.0` (pandas parquet engine)
  - `backend/app/modules/analytics/detectors/air_quality_baseline_detector.py` — coords from anomaly evidence
  - `backend/tests/test_eea_air_quality_integration.py` — updated live-path test
- **Authentication:**
  - Operator token via `EEA_AQ_API_TOKEN` (GUID format validated)
  - Transmitted as `UserToken` query parameter per EEA UTD guide
  - Token never logged, exposed in API, provenance, or error output (sanitized)
  - Missing token → fixture path; token present → live path only (failures propagate)
- **Bounded query strategy:**
  - Default 24-hour window (`EEA_AQ_QUERY_WINDOW_HOURS=24`)
  - Countries derived from `EEA_AQ_COUNTRIES` or `GEOGRAPHIC_SCOPE` (Romania → `["RO"]`, Europe → all)
  - Pollutants: PM2.5, PM10, NO2, O3, SO2; aggregation: hourly; E2a dataset only
  - Respects documented 600 MB service limit via short window + country filters
- **Validation rules:**
  - Reject `-999` sentinel, invalid validity flags, missing station/pollutant/timestamp
  - Reject invalid coordinates; accept valid zero; preserve negative values when numeric
  - Station coordinates from EEA metadata registry (not region centroids)
- **Deduplication identity:** `{station_id}:{pollutant}:{observed_at}` (deterministic sort + in-memory dedupe)
- **Provider health:** Uses existing `ProviderHealthRecord` semantics via scheduler `_record_health`
- **Scheduler:** EEA isolated from FIRMS/CEMS failures; reconciliation ownership unchanged
- **Geographic scope:** Ingestion global; `is_romania` / country from station metadata; scope applied downstream
- **Detector/correlation:** Live observations flow through existing AQ baseline detector; FIRMS↔EEA contextual rule verified
- **Provenance:** Unchanged feature-flag behavior (`ENABLE_INTELLIGENCE_PROVENANCE`)
- **Activation env vars:**
  ```text
  ENABLE_EEA_AIR_QUALITY=true
  EEA_AQ_API_TOKEN=<operator-guid-token>
  EEA_AQ_POLL_INTERVAL_MINUTES=60
  EEA_AQ_QUERY_WINDOW_HOURS=24
  EEA_AQ_COUNTRIES=RO          # optional; defaults from GEOGRAPHIC_SCOPE
  GEOGRAPHIC_SCOPE=europe      # recommended for Europe-first deployment
  ```
- **Rollback:** Set `ENABLE_EEA_AIR_QUALITY=false` or remove `EEA_AQ_API_TOKEN` (fixture path resumes)
- **Known limitations:**
  - EEA v1 Parquet API may not reject invalid tokens at gateway (ForestWatch validates GUID format + HTTP errors)
  - Baseline segmentation remains per-station (not per-pollutant) — documented, unchanged for Phase 0 safety
  - Live credentials required for production EEA downloads; tests use synthetic ZIP/Parquet fixtures
- **Tests Added:** 31 live activation tests + updated integration tests (auth, HTTP errors, ZIP/Parquet,
  validation, determinism, scheduler isolation, geographic scope, correlation, Phase 0 oracle)
- **Verification:** 1722 backend unit tests passed; Phase 0 oracle + 8 golden artifacts byte-identical;
  ten-run determinism green.
- **Notes / Follow-up:** EFAS/GloFAS, EFFIS, CEMS Risk & Recovery, per-pollutant baseline segmentation,
  multi-region operational validation dashboard remain subsequent packages.

---

## Multi-Region Operational Validation & Evidence Loop Hardening

- **Date:** 2026-08-11
- **Work Package:** Multi-Region Operational Validation & Evidence Loop Hardening
- **Objective:** Prove ForestWatch operates as a Europe-first multi-source intelligence platform through
  deterministic multi-region validation, operational observability, and evidence-loop hardening —
  without new providers, ML, or Phase 0 oracle changes.
- **Files Created:**
  - `backend/tests/fixtures/multi_region_operational_fixture.py` — deterministic Romania/Germany/Italy/Spain events
  - `backend/app/modules/ingestion/provider_execution_mode.py` — live/fixture/disabled/unknown resolution
  - `backend/app/services/operational_status_service.py` — bounded operational read model
  - `backend/tests/test_multi_region_operational_validation.py` — 43 validation tests (all spec minimum scenarios)
  - `frontend/src/components/intelligence/OperationalStatusCard.jsx` — minimal Command Center operational panel
  - `frontend/src/components/intelligence/__tests__/OperationalStatusCard.test.jsx` — 1 UI test
- **Files Modified:**
  - `backend/app/modules/analytics/analytics_routes.py` — `GET /intelligence/operational-status`
  - `backend/app/api/deps.py` — `operational_status_service_dep`
  - `backend/app/repositories/provider_health_repository.py` — `last_execution_mode` on health records
  - `backend/app/services/scheduler_service.py` — records provider execution mode after each run
  - `backend/app/modules/ingestion/providers/firms.py`, `eea_air_quality.py`, `cems_rapid_mapping.py` — execution mode tracking
  - `backend/tests/fixtures/intelligence_write_spy.py` — operational status mock for GET spy tests
  - `frontend/src/api/analytics.js` — `fetchOperationalStatus()`
  - `frontend/src/components/intelligence/IntelligenceSection.jsx` — operational status card
- **Geographic validation:**
  - Romania/Europe/All scope filtering verified with multi-country fixture
  - Provider geographic coverage distinguished from configured ForestWatch scope
  - Multi-country baseline isolation preserved; Phase 0 wildfire unchanged
- **Provider validation:**
  - FIRMS/EEA/CEMS individual failure isolation verified (other providers continue, reconciliation executes)
  - All-providers-fail cycle completes with reconciliation
  - Execution mode derived from health `last_execution_mode` + last run (not token alone)
- **Correlation/evidence validation:**
  - FIRMS↔EEA, FIRMS↔CEMS, EEA↔CEMS rules exercised with spatial/temporal rejection
  - Intelligence cycle states: current/stale/unavailable/disabled
  - Evidence states: single-source, multi-source, contextual, degraded, unavailable
  - Provenance on/off with credential stripping
- **Operational API:**
  - `GET /analytics/intelligence/operational-status` — read-only, bounded, credential-safe
  - Exposes geographic scope, providers, intelligence cycle, correlation diagnostics, evidence aggregate, regions
- **Frontend:** OperationalStatusCard in Command Center sidebar (scope, cycle, correlation, provider modes)
- **Tests Added:** 43 backend + 1 frontend; covers all 43 spec minimum scenarios: geographic scope (6),
  provider health (4), correlation (8), intelligence cycle (4), evidence/provenance (8), map (5),
  operational API (5), Phase 0 oracle (3)
- **Verification:** 1768 backend unit tests passed; 84 Phase 0 oracle tests green; golden artifacts byte-identical;
  ten-run determinism green; 3 frontend tests green; WP6 read/write separation intact.
- **Known limitations:** Per-station (not per-pollutant) AQ baseline segmentation unchanged; tenant AOI not implemented.
- **Notes / Follow-up:** EFAS/GloFAS, EFFIS, CEMS Risk & Recovery, EEA production credential rollout at scale,
  tenant AOI remain subsequent packages.

---

## Map Scope Contract Correction

- **Date:** 2026-08-12
- **Work Package:** Map Scope Contract Correction
- **Objective:** Eliminate geographic-scope bypass where IntelligenceMap consumed unscoped
  ``GET /api/events/map`` while ``GEOGRAPHIC_SCOPE`` applied elsewhere.
- **Map endpoint decision:**
  - ``GET /api/events/map`` — retained as **generic unscoped** event retrieval (backward compatible)
  - ``GET /api/analytics/intelligence/map-overlay`` — **authoritative scoped** intelligence map contract
  - IntelligenceMap migrated to map-overlay; scope/coordinate/centroid policy decided by backend only
- **Files Created:**
  - ``backend/tests/test_map_scope_contract.py`` — 16 scope/coordinate/contract regression tests
- **Files Modified:**
  - ``backend/app/api/event_routes.py`` — docstring clarifies unscoped generic contract
  - ``backend/app/modules/analytics/analytics_routes.py`` — docstring clarifies scoped intelligence contract
  - ``frontend/src/api/analytics.js`` — added ``fetchMapOverlay()``
  - ``frontend/src/components/intelligence/IntelligenceMap.jsx`` — consumes map-overlay
  - ``frontend/src/components/intelligence/__tests__/IntelligenceMap.test.jsx`` — updated + 4 scope tests
- **Verification:** 1800 backend tests passed; 75 IntelligenceMap frontend tests passed; 84 Phase 0 oracle
  tests green; golden artifacts byte-identical; WP6/WP7/WP8 unchanged
- **Pre-existing limitation (unchanged):** ``/api/events/map`` remains available for generic consumers;
  only the intelligence dashboard uses the scoped overlay contract

---

## Multi-Region Operational Validation — Completion Pass (2026-08-12)

- **Date:** 2026-08-12
- **Work Package:** Multi-Region Operational Validation — spec completion pass
- **Objective:** Close remaining spec gaps (France/Poland fixtures, Scenario A, per-rule correlation
  negatives, deterministic validation report artifact) without Phase 0 oracle changes.
- **Files Created:**
  - `backend/tests/fixtures/multi_region_validation_report.py` — deterministic report builder + golden verify
  - `backend/tests/fixtures/golden/MULTI_REGION_VALIDATION_REPORT.json` — fixture validation artifact
- **Files Modified:**
  - `backend/tests/fixtures/multi_region_operational_fixture.py` — added France + Poland synthetic events
  - `backend/tests/test_multi_region_operational_validation.py` — +8 tests (Scenario A, firms_cems/eea_cems
    spatial/temporal negatives, validation report class)
  - `frontend/src/components/intelligence/__tests__/IntelligenceSection.test.jsx` — mock
    `fetchCommandCenter`, `fetchOperationalStatus`, `OperationalStatusCard`
- **Validation report:** Explicitly marks `validation_mode: fixture`, `live_external_validation: false`
- **Phase 0:** `ORACLE_MANIFEST.json` unchanged; golden artifacts byte-identical; ten-run determinism green
- **Tests:** 59 multi-region validation tests; 1784 backend unit tests passed; 137 relevant frontend
  intelligence tests passed; 91 WP6/WP7/WP8 tests passed
- **Europe-first hardening pass (2026-08-12):** scheduler cycle_id propagation to reconciliation;
  map-overlay HTTP integration (Europe scope, no Romania centroid fallback); France/Poland map coordinates;
  Romania-centroid contamination regression; command-center European evidence integration; detection
  fingerprint determinism with multi-region detections
- **Problems discovered (unchanged):** `/api/events/map` unscoped; EEA Europe uses empty country list for live;
  `unavailable` is correlation_state not evidence_state in backend

---

## EFFIS Contextual Enrichment

- **Date:** 2026-08-12
- **Work Package:** EFFIS Contextual Enrichment Implementation Package
- **Objective:** Add European wildfire **contextual evidence** from verified EFFIS burned-area
  polygons without duplicating the FIRMS incident pipeline or altering Phase 0 oracle behavior.
- **Verified source:**
  - European Forest Fire Information System (Copernicus/JRC) public WFS
  - Base URL: `https://maps.effis.emergency.copernicus.eu/effis`
  - Layer: `modis.ba.poly.{year}` (MODIS/VIIRS burned-area polygons)
  - Fields: `id`, `FIREDATE`, `FINALDATE`, `COUNTRY`, `PROVINCE`, `AREA_HA`, geometry
  - Authentication: none (public EU/Copernicus data)
  - Semantic role: **contextual burned-area wildfire evidence** — not duplicate FIRMS incidents
- **Provider:** `effis.wildfire_context` (`EFFISWildfireContextProvider`)
  - Default execution: **fixture** (`ENABLE_EFFIS_WILDFIRE_CONTEXT=false` by default)
  - Live WFS when `ENABLE_EFFIS_LIVE=true` (falls back to fixture on failure)
  - Stored as `ForestEvent` with `metadata.contextual_role=wildfire_burned_area`, `event_type=unknown`
  - Excluded from wildfire baseline aggregation via `metadata.ingestion.provider_id != effis.wildfire_context`
  - Contextual `Detection` supplements via `supplement_contextual_detections()` during reconciliation
- **Identity:** `effis-burn:{fire_id}` spatial key; `effis:{layer}:{fire_id}` source event ID
- **Geographic scope:** Uses existing `GeographicScopePolicy`; WFS bbox Romania vs Europe based on scope
- **Correlation rule:** `firms_effis_contextual` — wildfire↔wildfire, FIRMS↔EFFIS,
  `contextual_evidence`, 25 km / 720 h, strength 0.60
- **Provenance:** Bounded `ProvenanceEnvelope` fields when `ENABLE_INTELLIGENCE_PROVENANCE=true`;
  credential/raw payload stripping via `sanitize_provenance_envelope`
- **Evidence:** `contextual_support` when FIRMS + EFFIS correlate; EFFIS label in evidence summary
- **Scheduler:** Registered in `provider_registry`; isolated health; reconciliation unchanged
- **Map:** No new endpoints; authoritative burned-area coordinates preserved; no Romania centroid fallback
- **Files Created:**
  - `backend/app/modules/ingestion/providers/effis.py`
  - `backend/app/modules/ingestion/providers/effis_constants.py`
  - `backend/app/modules/ingestion/providers/effis_gml_parser.py`
  - `backend/app/modules/ingestion/providers/effis_wfs_client.py`
  - `backend/app/modules/analytics/contextual_detection.py`
  - `backend/tests/test_effis_contextual_enrichment.py` — 45 tests
- **Files Modified:**
  - `backend/app/core/config.py` — `enable_effis_wildfire_context`, `enable_effis_live`, `effis_context_window_days`
  - `backend/app/modules/ingestion/provider_registry.py`
  - `backend/app/modules/ingestion/provider_execution_mode.py`
  - `backend/app/modules/analytics/correlation_config.py`
  - `backend/app/modules/analytics/cross_source_correlator.py`
  - `backend/app/modules/analytics/evidence_summary.py`
  - `backend/app/modules/analytics/analytics_repository.py`
  - `backend/app/modules/analytics/analytics_service.py`
  - `backend/app/services/source_intelligence_service.py`
  - `backend/tests/test_cross_source_correlation.py` — MagicMock settings fix
- **Live validation status:** Public WFS endpoint verified (HTTP 200, `modis.ba.poly.{year}` layers).
  Live client tries current year and up to two prior years when the current-year layer is unavailable;
  bounded fetch validated against Romania bbox (fixture-first remains default:
  `ENABLE_EFFIS_LIVE=false`)
- **Phase 0:** `ORACLE_MANIFEST.json` unchanged; golden artifacts byte-identical; ten-run determinism green
- **Verification:** 1845 backend unit tests passed (excluding live-server integration suites);
  45 EFFIS tests; 21 Phase 0 oracle integrity tests green
- **Known limitations:** Burned-area centroids (not polygon geometry) used for spatial matching; 720 h temporal
  window for burn-scar context; EFFIS disabled by default to preserve Romania Phase 0 behavior
- **Notes / Follow-up:** EFAS/GloFAS, CEMS Risk & Recovery, EEA production credential rollout at scale,
  tenant AOI remain subsequent packages

---

## Forest Disturbance Intelligence Foundation

- **Date:** 2026-08-12
- **Work Package:** Forest Disturbance Intelligence Foundation — Romania MVP
- **Objective:** Introduce `forest_disturbance` domain intelligence with probable driver
  classification, contextual/investigation assessment, and GFW integrated alerts provider —
  without asserting illegality from satellite evidence alone and without altering Phase 0 oracle.
- **Verified source:** Global Forest Watch Data API (`gfw_integrated_alerts` dataset)
  - Base: `https://data-api.globalforestwatch.org`
  - Live access requires `GFW_API_KEY` (token-configured)
  - Default: deterministic Romania/Europe fixture records
- **Provider:** `gfw.integrated_alerts` (`GFWIntegratedAlertsProvider`)
  - `ENABLE_FOREST_DISTURBANCE=false` by default (Phase 0 preserved)
  - Fixture-first; live POST query when API key configured
- **Domain model:**
  - `incident_category=forest_disturbance` (single category; drivers in evidence/metadata)
  - `disturbance_driver` / `probable_driver` with `_candidate` suffix
  - `authorization_status=unknown` unless authoritative legal source exists
  - Product language: **Potential Unauthorized Forest Activity** (never "illegal logging detected")
- **Detector:** `ForestDisturbanceDetector` + `supplement_disturbance_detections()`
  - Deterministic score: confidence + area + forest intersection + repeat + coherence
  - Threshold: `DISTURBANCE_SCORE_THRESHOLD=0.45`
- **Correlation rules:** `disturbance_wildfire_contextual`, `disturbance_effis_contextual`,
  `disturbance_cems_contextual` — contextual only; no event merging
- **Identity:** `disturbance-alert:{alert_id}` spatial keys — distinct from wildfire region keys
- **Map / Command Center:** Extended scoped map-overlay + evidence payload with bounded
  `disturbance_assessment` fields; IntelligenceMap popup shows driver/priority/authorization
- **Files Created:**
  - `backend/app/core/ecosystem/forest_disturbance_constants.py`
  - `backend/app/modules/ingestion/providers/gfw_integrated_alerts*.py` (provider, client, constants)
  - `backend/app/modules/analytics/disturbance_driver_classifier.py`
  - `backend/app/modules/analytics/disturbance_assessment.py`
  - `backend/app/modules/analytics/disturbance_detection.py`
  - `backend/app/modules/analytics/detectors/forest_disturbance_detector.py`
  - `backend/tests/test_forest_disturbance_intelligence.py` — 39 tests
- **Files Modified:**
  - Taxonomy: `incident_categories.py`, `category_registry.py`, `canonical_identity.py`
  - Pipeline: `config.py`, `provider_registry.py`, `detector_registry.py`, `analytics_repository.py`,
    `analytics_service.py`, `anomaly_thresholds.py`, `correlation_config.py`, `cross_source_correlator.py`,
    `evidence_summary.py`, `map_contract.py`, `detection_contract.py`, `provider_execution_mode.py`,
    `source_intelligence_service.py`, `test_cross_source_correlation.py`
  - Frontend: `IntelligenceMap.jsx` — disturbance popup fields
- **Phase 0:** `ORACLE_MANIFEST.json` unchanged; golden artifacts byte-identical; ten-run determinism green
- **Verification:** 1884 backend unit tests passed; 39 forest-disturbance tests; 21 Phase 0 oracle integrity
- **Live validation:** GFW API requires API key — live path implemented but **fixture-validated by default**
- **Known limitations:** No authoritative forestry authorization dataset; driver classifier is rule-based;
  protected-area/road proximity only when present in fixture/metadata; CLMS forest context from bundled CORINE
- **Next package:** Tenant Forest AOI + Authorization Context (monetization foundation)

---

## Tenant Forest AOI + Authorization Context

- **Date:** 2026-08-12
- **Work Package:** Tenant Forest AOI + Authorization Context — Monetization Foundation
- **Objective:** Introduce tenant-scoped forest monitoring areas (AOIs), post-detection AOI enrichment,
  authorization context abstraction, and customer monitoring read models — without billing/payments and
  without altering Phase 0 oracle behavior.
- **Tenant model:** `tenant_id = user.id` via `tenant_context.py` until dedicated multi-tenancy exists
- **Domain:** `ForestMonitoringArea` — Polygon/MultiPolygon GeoJSON, tenant-scoped CRUD, Mongo `2dsphere`
- **Authorization:** `AuthorizationContextProvider` + `UnknownAuthorizationContextProvider` (default `unknown`)
- **AOI enrichment:** `AoiEnrichmentService` — post-detection read-path; bumps investigation priority inside AOI;
  product language remains **Potential Unauthorized Forest Activity**
- **API:**
  - `POST/GET/PUT/DELETE /api/monitoring-areas`
  - `GET /api/analytics/intelligence/monitoring-status`
  - Extended `map-overlay` + `command-center` with bounded `monitored_area` fields
- **Files Created:**
  - `backend/app/core/tenant/tenant_context.py`
  - `backend/app/core/ecosystem/authorization_context.py`
  - `backend/app/models/forest_monitoring_area.py`
  - `backend/app/repositories/forest_monitoring_area_repository.py`
  - `backend/app/services/forest_monitoring_area_service.py`
  - `backend/app/services/aoi_geometry.py`
  - `backend/app/services/aoi_enrichment_service.py`
  - `backend/app/services/customer_monitoring_status_service.py`
  - `backend/app/api/monitoring_area_routes.py`
  - `backend/tests/test_tenant_forest_aoi.py` — 44 tests
  - `frontend/src/api/monitoringAreas.js`
  - `frontend/src/components/intelligence/MonitoredAreasCard.jsx`
  - `frontend/src/components/intelligence/CustomerMonitoringStatusCard.jsx`
  - `frontend/src/components/intelligence/__tests__/TenantMonitoring.test.jsx`
- **Files Modified:**
  - `backend/app/models/geo.py` — `validate_geojson_geometry()`
  - `backend/app/api/deps.py`, `backend/server.py`, `analytics_routes.py`
  - `backend/tests/fixtures/intelligence_write_spy.py`, map/multi-region test clients
  - `frontend/IntelligenceSection.jsx`, `IntelligenceMap.jsx`, related tests
- **Phase 0:** `ORACLE_MANIFEST.json` unchanged; golden artifacts byte-identical; ten-run determinism green
- **Verification:** 1931 unit tests passed (excluding live-server integration tests); 44 tenant-AOI tests;
  21 Phase 0 oracle integrity; 77 IntelligenceMap frontend (+2 AOI); 4 TenantMonitoring frontend
- **Known limitations:** No real forestry permit provider; AOI creation API-driven (no GIS editor);
  tenant isolation maps 1:1 to authenticated user id; no billing/subscription layer yet
- **Next package:** Customer Organization & Commercial Entitlement Foundation

---

## Customer Organization & Commercial Entitlement Foundation

- **Date:** 2026-08-12
- **Work Package:** Customer Organization & Commercial Entitlement Foundation
- **Objective:** Evolve `tenant_id = user.id` into `User → Organization → Membership → Entitlements → ForestMonitoringArea`
  with idempotent bootstrap, backend entitlement enforcement, and minimal frontend org awareness — no Stripe/billing.
- **Organization model:** `Organization` (id, name, slug, status, timestamps); statuses `active` / `suspended`
- **Membership:** `OrganizationMembership` with roles `owner` / `admin` / `member` and statuses `active` / `suspended`
- **Entitlements:** `OrganizationEntitlement` + `EntitlementService` (foundation profile: 1 AOI, monitoring + disturbance on,
  correlation/live/alerts off); authoritative `can_monitor`, `can_add_monitoring_area`, etc.
- **Migration:** Idempotent `OrganizationBootstrapService` — personal org per user, legacy AOIs get `organization_id`
- **Context:** `OrganizationContext` resolved from auth + optional `X-Organization-Id` (membership validated)
- **API:** `POST/GET/PUT /api/organizations`, membership CRUD; monitoring/AOI/analytics routes org-scoped
- **Monitoring status:** Extended with bounded `organization` + `entitlements` blocks
- **Files Created:**
  - `backend/app/core/commercial/entitlement_types.py`
  - `backend/app/core/organization/organization_context.py`, `organization_roles.py`
  - `backend/app/models/organization.py`
  - `backend/app/repositories/organization_*.py`
  - `backend/app/services/entitlement_service.py`, `organization_*.py`
  - `backend/app/api/organization_routes.py`
  - `backend/tests/test_organization_commercial.py` — 45 tests
- **Files Modified:**
  - `forest_monitoring_area.py`, repository, service — `organization_id` ownership + limit enforcement
  - `aoi_enrichment_service.py`, `customer_monitoring_status_service.py`, `monitoring_area_routes.py`, `analytics_routes.py`
  - `deps.py`, `server.py` (indexes + startup bootstrap)
  - `tests/test_tenant_forest_aoi.py`, `tests/fixtures/intelligence_write_spy.py`
  - `CustomerMonitoringStatusCard.jsx`, `MonitoredAreasCard.jsx`, `IntelligenceSection.jsx`, `TenantMonitoring.test.jsx`
- **Phase 0:** `ORACLE_MANIFEST.json` unchanged; golden artifacts byte-identical; ten-run determinism green
- **Verification:** 1976 backend unit tests passed (excluding live-server integration suites); 45 org-commercial tests;
  44 tenant-AOI tests; 6 frontend TenantMonitoring tests; Phase 0 oracle + determinism green
- **Known limitations:** No email invitations; no billing/Stripe; provider execution not gated by entitlements;
  `tenant_id` retained on AOIs for legacy compatibility; no org deletion API
- **Next package:** Stripe subscription → entitlement updates → alert delivery policies

---

## Productization, Organization-Aware UX & Visual Intelligence Foundation

- **Date:** 2026-08-12
- **Work Package:** Productization, Organization-Aware UX & Visual Intelligence Foundation
- **Objective:** Transform intelligence + organization capabilities into a distinctive, entitlement-aware operational product experience — frontend-only; no backend architecture, billing, or provider changes.
- **Design system:** `design/tokens.js`, `design/semanticStates.js`, `fw-surface` / semantic badges in `index.css`, reusable product components (`SurfaceCard`, `StatusBadge`, `PriorityBadge`, `EvidenceBlock`, `EntitlementList`)
- **Organization UX:** `OrganizationContext` provider, `organizations.js` API client with `X-Organization-Id` header, `OrganizationSelector` in `AppLayout`, intelligence reload on org switch
- **Command Center:** `IntelligenceCommandCenter` — org identity, monitoring metrics, priority queue, entitlement capabilities, `DisturbanceInvestigationPanel`
- **Surfaces updated:** `IntelligenceSection`, `ActiveIntelligenceEvents`, `CustomerMonitoringStatusCard`, `MonitoredAreasCard`, `OperationalStatusCard`, `EvidenceIndicator`, `IntelligenceMap` (AOI styling, legend, org context subtitle)
- **Files Created:** organization context/selector, product components, command center + investigation panel, asset card, frontend tests (`ProductSurfaces.test.jsx`, `OrganizationSelector.test.jsx`)
- **Backend/API:** No contract modifications — consumes existing `/organizations`, `/monitoring-areas`, `/analytics/intelligence/monitoring-status`, `/analytics/intelligence/command-center`, map-overlay
- **Verification:** 304 frontend tests passed; backend Phase 0 unchanged (no backend edits in this package)
- **Known limitations:** AOI area (ha) not in current API; multi-org switch reloads intelligence section but not all pages; Taste Skill v2 not present in environment (methodology applied manually)
- **Next package:** Stripe subscription → entitlement sync → alert delivery UI

---

## Customer Alert Delivery & Organization Context Foundation

- **Date:** 2026-08-12
- **Work Package:** Customer Alert Delivery & Organization Context Foundation
- **Objective:** Complete commercial loop Organization → AOI → Disturbance → Alert Policy → Notification without Stripe/billing or frontend redesign.
- **Organization context:** `organizationVersion` in `OrganizationContext`; `IntelligenceMap` reloads on org switch; org-switch regression tests (`OrganizationCoherence.test.jsx`)
- **AOI read model:** `area_hectares` + `intelligence_summary` on monitoring-area GET responses via `MonitoringAreaReadModelService` / `AoiIntelligenceSummaryService`
- **Alert domain:** `AlertPolicy`, `OrganizationNotificationChannel`, `AlertDeliveryRecord` with deterministic dedupe (`org:policy:event:stage`), lifecycle (`pending/sent/acknowledged/resolved/suppressed`), stages (`initial/escalation/resolution`)
- **Delivery pipeline:** Scheduler post-reconciliation → `CustomerAlertEvaluationService` → `CustomerAlertDispatcher` (email fake/SMTP + org webhook); failure isolated from intelligence cycle; respects `alert_delivery_enabled` entitlement
- **API:** `/api/customer-alerts/policies`, `/channels`, `/deliveries` (org-scoped via `X-Organization-Id`)
- **Verification:** 15 new backend tests (AOI summary + customer alert delivery); frontend org-coherence + IntelligenceMap (77) green
- **Known limitations:** No SMTP in default config (FakeEmailSender in dev/tests); webhook single-attempt only; no alert management UI yet; legacy global `IntelligenceNotificationService` unchanged
- **Next package:** Stripe subscription → entitlement sync → alert policy UI

---

## Customer Alert Configuration UX & Alert Reliability Hardening

- **Date:** 2026-08-12
- **Work Package:** Customer Alert Configuration UX & Alert Reliability Hardening
- **Objective:** Turn the alert API into a usable, trustworthy product capability — configuration UI, delivery history,
  Command Center surface, and a hardened delivery state machine. No Stripe/billing, no architecture redesign.
- **Delivery semantics separated:** evaluation (creates records) vs dispatch (sends) vs outcome. New terminal
  `AlertLifecycle.FAILED`; `dispatch_attempt_count`, `last_attempt_at`, `suppression_reason` on `AlertDeliveryRecord`;
  `DISPATCHABLE_LIFECYCLES` so a failed delivery is never silently retried each scheduler cycle
- **Cooldown redefined:** organization + policy + (event OR overlapping monitored area), measured from record
  `created_at` so failed/suppressed dispatches still consume the window; resolutions bypass cooldown
- **Product vocabulary:** `core/commercial/alert_semantics.py` is the single source of validation ranges and
  customer-facing labels; exposed to the UI through `GET /api/customer-alerts/options`
- **Secrets:** `redact_channel_config` now removes secret material entirely and reports `secret_configured`; webhook
  signing secrets are write-only from the frontend
- **New read models:** `AlertDeliveryPublic` (policy/area names, per-channel outcomes, labels) and
  `AlertOperationsOverview` (counts, channel readiness, recent deliveries) behind `GET /overview`
- **UI:** `/alerts` page with Alert policies / Notification channels / Alert history tabs; compact
  `AlertOperationsPanel` inside the existing Command Center (no second dashboard); org-scoped loads keyed on
  `selectedOrgId` + `organizationVersion` with surfaces cleared before every reload
- **Files Created:**
  - `backend/app/core/commercial/alert_semantics.py`
  - `backend/tests/fixtures/customer_alert_fakes.py`
  - `backend/tests/test_customer_alert_configuration.py` (63), `test_customer_alert_operations.py` (50)
  - `frontend/src/api/customerAlerts.js`
  - `frontend/src/components/alerts/{AlertPolicyForm,AlertPolicyList,NotificationChannelForm,NotificationChannelList,AlertDeliveryHistory,AlertOperationsPanel}.jsx`
  - `frontend/src/pages/AlertsPage.jsx`
  - `frontend/src/components/alerts/__tests__/{AlertConfiguration,AlertHistoryAndOperations}.test.jsx`
  - `frontend/src/pages/__tests__/AlertsPage.test.jsx`
- **Files Modified:**
  - `models/customer_alert.py`, `repositories/alert_delivery_repository.py`, `core/commercial/secret_storage.py`
  - `services/{alert_policy_service,customer_alert_evaluation_service,customer_alert_dispatcher,customer_alert_notification_service,scheduler_service}.py`
  - `api/{customer_alert_routes,deps}.py`, `server.py` (delivery history + cooldown indexes)
  - `backend/tests/test_customer_alert_delivery.py` (rewritten, 67 tests)
  - `frontend/src/design/semanticStates.js`, `App.js`, `components/layout/AppLayout.jsx`,
    `components/intelligence/{IntelligenceSection,IntelligenceCommandCenter}.jsx`
- **Pre-existing bugs fixed while verifying the monitored-area step of the journey:**
  - `api/monitoring_area_routes.py` was missing imports for `ForestMonitoringAreaCreate/Update`,
    `OrganizationContext`, `AppError`, `NotFoundError` — with PEP 563 annotations FastAPI treated the request body as a
    query parameter, so every monitoring-area create/update returned 422
  - `MonitoringAreaReadModelService` passed `area_hectares` / `intelligence_summary` twice into
    `ForestMonitoringAreaPublic`, so monitoring-area reads raised `TypeError` whenever an area existed
  - `tests/test_tenant_forest_aoi.py` / `test_organization_commercial.py` now override
    `monitoring_area_read_model_service_dep`, making the read path testable without a database
- **Phase 0:** `ORACLE_MANIFEST.json` and wildfire golden artifacts untouched; oracle integrity + golden output tests green
- **Verification:** 2160 backend tests passed offline (live-server suites excluded); 180 new alert tests;
  374 frontend tests passed (68 new); ten-run determinism identical (345 passed per run)
- **Known limitations:** single bounded dispatch attempt with no retry queue; no acknowledge/resolve action in the UI;
  delivery history is not paginated beyond a 200-record cap; SMTP still optional (FakeEmailSender by default)
- **Next package:** Stripe Subscription → Billing Webhook → Entitlement Sync → Production Plan Limits

---

## Stripe Subscription, Billing Webhook & Entitlement Synchronization

- **Date:** 2026-08-13
- **Work Package:** Stripe Subscription → Billing Webhook → Entitlement Sync → Production Plan Limits
- **Objective:** Turn the existing entitlement foundation into a real monetization system — configuration-driven plans,
  Stripe Checkout/Portal, verified idempotent webhooks, deterministic entitlement synchronization — without a second
  billing, tenancy, entitlement, or organization system and without touching Phase 0 behavior.
- **Plan catalog:** `core/commercial/plan_catalog.py` — Foundation / Professional / Enterprise as data, not code.
  Price ids, price labels, monitored-area limits, and purchasability all come from settings; changing a Stripe price
  never requires a code change. Enterprise ships `purchasable=false` (contact sales) until a price id is configured.
  A plan is checkout-ready only when it is available, purchasable, **and** has a configured price id.
- **Entitlement mapping:** each plan carries a full profile keyed by existing `EntitlementType` values —
  Foundation `limit=1 / disturbance / no correlation / no live sources / no alerts`;
  Professional and Enterprise `disturbance + correlation + live sources + alerts` with configurable limits
  (defaults 10 / 100). Unsubscribed and non-entitling states fall back to `DEFAULT_ENTITLEMENT_PROFILE`.
- **Subscription state:** `core/commercial/subscription_status.py` separates Stripe lifecycle from ForestWatch
  capability. `ENTITLING_STATUSES = {trialing, active, past_due}` — a past-due customer keeps working while payment is
  chased; `incomplete`, `incomplete_expired`, `canceled`, `unpaid` drop to baseline.
- **Domain:** `BillingCustomer` (org ↔ Stripe customer), `OrganizationSubscription` (current subscription + plan +
  status + `last_event_at`/`last_event_id` ordering guard), `BillingEvent` (webhook ledger, idempotency + observability).
  No card data, payment method, or Stripe secret is ever stored.
- **Gateway:** `StripeGateway` protocol with `FakeStripeGateway` (deterministic, in-process) and `LiveStripeGateway`
  (lazy `stripe` import). `ENABLE_BILLING=false` — the default — always yields the fake, so development and the whole
  test suite exercise the real code path without credentials and can never reach a Stripe account.
- **Webhook:** `POST /api/billing/webhook/stripe`. Signature verified by hand (HMAC-SHA256 over `t.payload`, constant-time
  compare, timestamp tolerance) so verification is testable and has no SDK dependency. `BillingEventRepository.claim`
  inserts against a unique `stripe_event_id` index — a duplicate delivery is acknowledged and skipped rather than
  reprocessed. Events older than the stored `last_event_at` are recorded and ignored, so out-of-order delivery cannot
  resurrect a stale plan. Handled: `checkout.session.completed`, `customer.subscription.created/updated/deleted`,
  `invoice.paid`, `invoice.payment_failed`; everything else is acknowledged as ignored.
- **Entitlement sync:** `EntitlementSyncService` resolves `(plan, status) → profile` as a pure function and writes only
  `OrganizationEntitlement` rows. `EntitlementService` remains the single runtime authority; no billing checks were
  added anywhere in the application. Downgrade and cancellation lower the limit and never delete monitored areas,
  intelligence, or alert history — the organization is simply reported as over its current entitlement and blocked from
  creating more.
- **API:** `GET /api/billing/status`, `GET /api/billing/plans`, `POST /api/billing/checkout`, `POST /api/billing/portal` —
  all resolved through `OrganizationContext`/`X-Organization-Id`, never a client-supplied organization id. Checkout
  accepts a **plan key only**; the price id is resolved server-side from the catalog. Owners/admins manage, active
  members view. Suspended organizations cannot purchase.
- **Failure isolation:** the status endpoint reads local state only — no Stripe call on any read path — and degrades the
  observability block rather than failing when the event ledger is unavailable.
- **Files Created:**
  - `backend/app/core/commercial/{plan_catalog,subscription_status}.py`
  - `backend/app/models/billing.py`
  - `backend/app/repositories/{billing_customer,organization_subscription,billing_event}_repository.py`
  - `backend/app/services/billing/{stripe_gateway,stripe_signature,stripe_webhook_service,entitlement_sync_service,billing_service}.py`
  - `backend/app/api/billing_routes.py`
  - `backend/tests/fixtures/billing_fakes.py`
  - `backend/tests/test_billing_plan_catalog.py` (47), `test_billing_entitlement_sync.py` (27),
    `test_stripe_webhook.py` (56), `test_billing_api.py` (55)
  - `frontend/src/api/billing.js`
  - `frontend/src/components/billing/{CurrentPlanCard,PlanOptionList,UpgradePrompt,BillingCapabilityStrip}.jsx`
  - `frontend/src/pages/BillingPage.jsx`
  - `frontend/src/pages/__tests__/BillingPage.test.jsx`, `components/billing/__tests__/BillingSurfaces.test.jsx`
- **Files Modified:**
  - `backend/app/core/config.py` (billing + plan settings), `backend/.env.example`
  - `backend/app/core/organization/organization_roles.py` — `can_manage_billing` / `can_view_billing`
  - `backend/app/api/deps.py`, `backend/server.py` (router + billing indexes), `backend/requirements.txt` (`stripe`)
  - `frontend/src/App.js`, `components/layout/AppLayout.jsx`, `design/semanticStates.js`
  - `components/intelligence/{IntelligenceSection,IntelligenceCommandCenter,MonitoredAreasCard,CustomerMonitoringStatusCard}.jsx`
  - `components/alerts/AlertPolicyList.jsx`
- **Indexes:** `billing_customers.organization_id` (unique), `billing_customers.stripe_customer_id` (unique),
  `organization_subscriptions.organization_id` (unique), `organization_subscriptions.stripe_subscription_id`
  (unique, sparse), `billing_events.stripe_event_id` (unique), plus event history indexes
- **Frontend:** `/billing` built from the existing design system (`SurfaceCard`, `StatusBadge`, `EntitlementList`) —
  current plan, monitoring capacity, included capabilities, subscription state, plan options, manage-subscription.
  `UpgradePrompt` appears in Monitored Areas (at limit), monitoring status (no live sources), and alert policies
  (no alert delivery). A compact `BillingCapabilityStrip` sits in the Command Center; intelligence stays primary and
  renders normally if the billing request fails. Customer-facing language only — no entitlement keys, flags, or Stripe ids.
- **Phase 0:** `ORACLE_MANIFEST.json` and golden artifacts untouched and byte-identical
- **Verification:** 2345 backend tests passed offline (live-server suites excluded), 185 of them new billing tests;
  426 frontend tests passed (52 new); Phase 0 oracle 165 passed; ten-run determinism 378 passed identically on all ten runs
- **Known limitations:** not validated against a live Stripe test-mode account — the gateway, signature verification, and
  webhook state machine are exercised through deterministic fakes and fixtures, so the production path is implemented but
  unproven against real Stripe traffic; no proration/quantity/seat pricing; no dunning beyond `past_due` tolerance;
  no invoice history surface (deferred to the Stripe Portal); Enterprise is contact-sales only
- **Next package:** validate the commercial funnel end to end in Stripe test mode and prepare the first paying customer

---

## 2026-08-13 — Stripe Test-Mode Readiness — Real-Payload Hardening & Validation Runbook

- **Date:** 2026-08-13
- **Work Package:** Commercial validation and first-customer readiness
- **Objective:** Validate the commercial funnel against real Stripe test-mode traffic; where that is externally
  blocked, close every defect discoverable without credentials and leave the remaining work precisely specified.
- **External validation status:** **not performed.** No Stripe credentials exist in this environment
  (`backend/.env` contains no `STRIPE_*`), the `stripe` package is not installed, and the Stripe CLI is absent.
  `api.stripe.com` is reachable (HTTP 401 unauthenticated), so the boundary is credentials and webhook ingress
  only. No claim of Stripe validation is made anywhere in this entry.
- **Defects found by inspection and fixed** — all four are real-Stripe-only; the previous package's fixtures
  encoded the pre-2025-03-31 payload shape exclusively, so none were reachable by the existing tests:
  1. **Invoice subscription reference.** Stripe removed `invoice.subscription` in `2025-03-31.basil`, replacing it
     with `invoice.parent.subscription_details.subscription`. Invoice events from a modern account resolved no
     subscription, so `invoice.paid` / `invoice.payment_failed` could not attribute an organization unless a
     billing customer already happened to be linked.
  2. **Renewal date.** The same release moved `current_period_end` from the subscription onto its items. The
     renewal and "cancels on" dates on `/billing` would have rendered empty against a real account.
  3. **Ordering across concerns.** A single `last_event_at` clock let a newer invoice event make a genuinely newer
     plan change look stale, silently discarding an upgrade or downgrade. Ordering is now tracked per concern and
     is deliberately asymmetric: a subscription event must only be newer than the last subscription event, while
     an invoice event must be newer than everything applied, because Stripe's subscription object is authoritative
     for status and an invoice only infers it.
  4. **Retry after failure.** A delivery that failed mid-processing left a ledger row that made Stripe's retry look
     like a duplicate, stranding the subscription in stale state permanently. A `failed` row is now re-claimed
     atomically on redelivery, with `attempt_count` recording the attempts.
  Also fixed: a failed event was never attributed to an organization, so its own organization's billing status
  reported zero failures; the Stripe API version was unpinned for outbound calls; customer creation had no
  idempotency key, so a retried create could bill a second Stripe customer; and a concurrent first checkout could
  raise on the unique index instead of reusing the customer the other writer created.
- **Files Created:**
  - `backend/app/services/billing/stripe_payloads.py` — readers accepting both the pre-basil and basil shapes
  - `backend/tests/test_stripe_real_payloads.py` (45) — both payload shapes end to end through the real HTTP
    webhook route, per-concern ordering, retry-after-failure, gateway configuration, customer race
  - `backend/scripts/stripe_test_mode_check.py` — `verify-config` (asks Stripe whether each configured price is
    real, active, recurring, and test-mode) and `inspect-org` (local subscription, entitlements, capacity, ledger).
    Refuses live keys, prints no secrets, lives outside `tests/`
  - `backend/scripts/determinism_check.ps1` — ten-run determinism harness with the selection written out explicitly
  - `docs/engineering/STRIPE_TEST_MODE_VALIDATION.md` — what to create in Stripe, configuration, webhook
    forwarding, the ordered validation sequence, and the first-customer checklist
- **Files Modified:**
  - `backend/app/services/billing/stripe_webhook_service.py` — shared payload readers, per-concern clocks,
    organization attribution for failures
  - `backend/app/services/billing/stripe_gateway.py` — optional API-version pin, idempotent customer creation
  - `backend/app/services/billing/billing_service.py` — customer-create race, `last_event_status`
  - `backend/app/models/billing.py` — `last_lifecycle_event_at`, `last_invoice_event_at`, `attempt_count`,
    `last_event_status`
  - `backend/app/repositories/billing_event_repository.py` — failed-row re-claim, `latest()`
  - `backend/app/core/config.py`, `backend/.env.example` — `STRIPE_API_VERSION`
  - `backend/tests/fixtures/billing_fakes.py` — `api_shape` payload builders, failed-row re-claim in the fake
- **Operability:** the ledger distinguishes received (verified and claimed), processed, ignored, and failed, with
  an attempt count; `GET /api/billing/status` exposes the newest delivery's outcome alongside the existing failure
  count. No dashboard was added.
- **Phase 0:** `ORACLE_MANIFEST.json` and the eight golden artifacts untouched and byte-identical
- **Verification:** 2390 backend tests passed offline (live-server suites excluded), 45 of them new;
  426 frontend tests passed; Phase 0 oracle set 140 passed; ten-run determinism 570 passed identically on all ten
  runs with golden artifacts byte-identical throughout. The Phase 0 and determinism selections are now recorded in
  `scripts/determinism_check.ps1` rather than reconstructed per package, which is why the counts differ from the
  previous entry's 165/378 — the composition is explicit, not the behaviour changed.
- **Pre-existing issue observed, not fixed:** `tests/test_intelligence_events.py::TestAnalyticsServiceReconcile`
  fails when that file runs alone, because `reconcile_intelligence_events` calls the lru-cached `get_settings()`
  and only passes when an earlier module has warmed the cache. Out of scope here; the determinism harness supplies
  the environment explicitly instead.
- **Known limitations:** unchanged from the previous entry, plus: the webhook endpoint's Stripe API version is an
  operator decision (both shapes are read correctly, but which one arrives must be recorded during validation);
  no proration handling on mid-cycle plan changes; no forced downgrade after prolonged non-payment.
- **Next package:** perform the runbook against a Stripe test-mode account, then take the first customer.

---

## 2026-08-13 — Stripe API Contract Pin (Dahlia) & Pause / Unknown-Price Hardening

- **Date:** 2026-08-13
- **Work Package:** Stripe test-mode activation and production-readiness validation
- **Objective:** Make the billing implementation internally consistent with the *current* Stripe GA contract
  without rebuilding billing, and without claiming real Stripe traffic that this environment cannot produce.
- **API version targeted:** `2026-07-29.dahlia` (`app.core.commercial.stripe_api.STRIPE_API_VERSION`).
  Previously the pin was empty (account default). Empty is not a first-customer contract. Chosen because it is
  the current GA as of August 2026; the last *object-shape* break ForestWatch reads was `2025-03-31.basil`
  (invoice parent, item-level period). Clover/Dahlia did not move those fields. Checkout does not set
  `ui_mode`, so Dahlia's `hosted` → `hosted_page` rename does not apply. Clover's flexible billing mode becomes
  the default for Checkout-created subscriptions under this pin; ForestWatch does not implement proration, so
  that change is accepted rather than fought.
- **Stripe SDK:** still `stripe>=9.0.0` in requirements; **not installed in this environment**. No SDK bump —
  freshness of the SDK is not required to pin the API version we send.
- **Compatibility changes:**
  1. Explicit API pin for outbound SDK calls (was empty).
  2. `paused` is a known non-entitling subscription status (Dahlia pause API). Ignoring it would have left
     Professional entitlements in place while Stripe stopped billing. Also handle
     `customer.subscription.paused` / `resumed`.
  3. A Stripe price id that is not in the plan catalog no longer grants a plan via leftover
     `metadata.plan_key`. Metadata is only a fallback when items have not been attached yet.
- **Webhook events handled:** the original six plus `customer.subscription.paused` and
  `customer.subscription.resumed`. Payload readers remain dual-shape (pre-basil and basil/dahlia).
- **Real Stripe test-mode:** **not performed.** `backend/.env` has no `STRIPE_*` keys; ENABLE_BILLING is unset;
  Stripe SDK is not installed; Stripe CLI is not installed. Boundary unchanged from the previous entry.
- **Files Created:** `backend/app/core/commercial/stripe_api.py`
- **Files Modified:** `config.py`, `.env.example`, `stripe_gateway.py`, `subscription_status.py`,
  `stripe_webhook_service.py`, billing tests, `docs/engineering/STRIPE_TEST_MODE_VALIDATION.md`
- **Phase 0:** golden artifacts and `ORACLE_MANIFEST.json` not modified
- **Verification:** 2402 backend tests passed offline; 426 frontend tests passed; Phase 0 oracle set 140 passed;
  ten-run determinism 582 passed identically with golden artifacts byte-identical throughout
- **Next package:** execute the test-mode runbook with real credentials, then the first live customer

---

## 2026-08-13 — Deployment Configuration States & Webhook Persistence Hygiene

- **Date:** 2026-08-13
- **Work Package:** Stripe test-mode activation and production-readiness validation (final increment)
- **Objective:** Close the last two gaps in the commercial foundation that were asserted only indirectly: how
  billing behaves in each deployment configuration an operator can get wrong, and what the webhook path is
  allowed to persist. No redesign, no new entitlement authority, no product changes.
- **Defects fixed:**
  1. **The ledger could become a copy of Stripe payloads.** A failed delivery persisted the raw exception
     message, and driver or validation errors quote the document that failed. Persisted detail is now collapsed
     and bounded to `LEDGER_DETAIL_LIMIT` (200 characters) on both the success and failure paths, so the ledger
     records what happened to an event rather than the event.
  2. **An undated event erased the ordering watermark.** With no `created` field the event was applied (correct
     — it cannot be compared) but wrote `None` over `last_event_at` and the concern clock, after which a
     genuinely stale event was free to revert the state. The watermark is now preserved when an event carries no
     timestamp, so ordering stays monotonic. Real Stripe always stamps `created`; the endpoint is public, so the
     absence is now handled deterministically rather than accidentally.
- **Configuration states now asserted through the real gateway factory** (`build_stripe_gateway`), not a
  hand-made double: `ENABLE_BILLING=false` (catalog and status readable, local checkout reaches no Stripe
  domain and grants nothing, monitored-area creation and disturbance capability unaffected);
  `ENABLE_BILLING=true` with no secret key (checkout and portal refuse with 503, no Stripe customer recorded,
  the refusal quotes no configured secret, already-granted entitlements stay usable); `ENABLE_BILLING=true`
  with a key but no configured price (400 before the gateway is touched, plan advertised as not purchasable, no
  customer created); Stripe reachable but failing (503, no partial customer link, status still readable, a
  retry after the outage succeeds exactly once).
- **Webhook failure containment asserted:** a failing entitlement sync leaves the stored plan and profile
  unchanged, the event is retried successfully on Stripe's redelivery, and the ledger row records the failure
  without copying the payload.
- **Files Created:** `backend/tests/test_billing_configuration_states.py` (21)
- **Files Modified:**
  - `backend/app/services/billing/stripe_webhook_service.py` — bounded ledger detail, watermark preservation
  - `backend/tests/test_stripe_real_payloads.py` — undated-event determinism (3)
  - `backend/tests/fixtures/billing_fakes.py` — `build_environment(gateway=...)` injection
  - `backend/scripts/determinism_check.ps1` — configuration states added to the commercial selection
- **Real Stripe test-mode:** **still not performed.** Re-checked at the end of this increment: no `STRIPE_*`
  process environment variables, `backend/.env` has no secret key, webhook secret, or price ids configured, and
  the Stripe SDK is not importable. Nothing in this increment was validated against live Stripe traffic.
- **Phase 0:** `ORACLE_MANIFEST.json` and the golden artifacts not modified and byte-identical
- **Verification:** 2426 backend tests passed offline (live-server suites excluded), 24 of them new;
  commercial selection 342 passed; Phase 0 oracle set 140 passed; ten-run determinism 606 passed identically on
  all ten runs with golden artifacts byte-identical throughout. Frontend untouched this increment, so the
  frontend suite was not re-run (426 passing as of the previous entry).
- **Readiness:** AMBER. Everything deterministically verifiable offline is verified; accepting a paying
  customer still requires the test-mode runbook against a real Stripe account.
- **Next package:** execute the test-mode runbook with real credentials, then the first live customer

---

## 2026-08-13 — Real Stripe Test-Mode Validation Attempted, Not Executed

- **Date:** 2026-08-13
- **Work Package:** Execute real Stripe test-mode validation
- **Objective:** Move ForestWatch from a locally verified Stripe implementation to a real test-mode
  verified commercial flow. No architecture changes.
- **Live validation:** **not performed.** Environment probe (presence only, no secret values printed):
  Stripe CLI absent; `stripe` Python package not importable; `ENABLE_BILLING` is false;
  `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, and all `STRIPE_PRICE_*` keys empty in `backend/.env`;
  no `STRIPE_*` process environment variables; MongoDB not listening on localhost:27017; ForestWatch
  backend and frontend not listening on 8000/8001/3000. Network to Stripe works
  (`https://api.stripe.com/v1/balance` returns 401 without credentials).
- **Decision:** stop the live-validation portion rather than invent credentials or fabricate Stripe
  calls. Offline regression was re-run to confirm the commercial foundation is still intact.
- **Files Created / Modified:** none in application code. `ORACLE_MANIFEST.json` and golden artifacts
  untouched.
- **Verification:** billing/Stripe/organization suite 311 passed; frontend billing surfaces 52 passed;
  backend offline 2426 passed; Phase 0 oracle 140 passed; ten-run determinism 606 passed identically
  with golden artifacts byte-identical throughout.
- **Readiness:** remains **AMBER**. ForestWatch is not ready for the first real paying customer until
  the operator completes the runbook in `docs/engineering/STRIPE_TEST_MODE_VALIDATION.md`.
- **Next package:** operator supplies test-mode credentials and tooling, then this validation is
  re-run against real Stripe traffic.

---

## 2026-08-13 — Interactive Demo / Trial Control Plane

- **Date:** 2026-08-13
- **Work Package:** Interactive Demo / Trial Control Plane
- **Objective:** Let a prospective customer experience the real ForestWatch product — observation
  through investigation and simulated alerting — without an account, without a parallel fake
  frontend universe, and without weakening organization isolation or commercial contracts.
- **Architecture:** A signed demonstration session (`type=demo` JWT in the existing `access_token`
  cookie) resolves to a reserved `kind=demo` organization (`forestwatch-demo`). Intelligence for
  that session is read from `demo_intelligence_events`, not `intelligence_events`. Usage budget is
  session-scoped and separate from commercial entitlements. Existing Command Center, map overlay,
  investigation panel, and alert read models are reused.
- **Files Created:**
  - `backend/app/core/demo/` — constants, identity, catalog (Romanian scenarios), errors
  - `backend/app/models/demo.py` — session, product events, public status
  - `backend/app/repositories/demo_session_repository.py`
  - `backend/app/services/demo/` — catalog seed/reset, session+budget, simulated alerts, in-process rate limit
  - `backend/app/api/demo_routes.py` — `/api/demo/*`
  - `backend/tests/fixtures/demo_fakes.py`, `backend/tests/test_demo_control_plane.py` (15)
  - `frontend/src/api/demo.js`, `frontend/src/lib/demo.js`, `frontend/src/context/DemoContext.jsx`
  - `frontend/src/pages/ExplorePage.jsx` and `frontend/src/pages/__tests__/ExplorePage.test.jsx`
  - `frontend/src/components/demo/` — guide rail, budget bar, conversion CTA, scenario switcher, simulated-alert test
- **Files Modified:** organization context (`is_demo`, demo resolution, listings omit demo org for real users);
  intelligence repo collection override; map-overlay demo-only payload; evidence Command Center catalog
  correlation; billing checkout/portal forbidden; AOI/org/alert/investigation/report/legacy-event mutations
  and unscoped reads blocked; scheduler evaluation skips demo orgs; App routing `/` and `/explore`;
  Auth `startDemo`; dashboard/command center/investigation/map/alerts/billing/layout; determinism
  selection includes `test_demo_control_plane.py`. `ORACLE_MANIFEST.json` and golden artifacts untouched.
- **Tests Added or Updated:** demo isolation, session lifecycle, deterministic catalog, budget exhaustion,
  reset, simulated alert (no senders), billing guard, rate limit, token type; frontend entry, guided path,
  scenarios, budget, investigation sections, simulated alert, command-center demo header, map demoMode
  isolation, ProductSurfaces observation/inference split.
- **Verification:**
  - Demo backend: 15 passed
  - Evidence-aware Command Center (after `col` guard): 30 passed with demo tests
  - Backend offline (`--ignore` live-server `backend_test.py`, `test_analytics.py`, `test_ingestion.py`): **2441 passed**
  - Frontend suite: **437 passed**
  - Phase 0 oracle set: **140 passed**
  - Ten-run determinism: **621 passed identically** on all ten runs; golden artifacts byte-identical throughout
- **Result:** Complete as a demonstrable, conversion-oriented experience on the existing product
  architecture. Not production-ready. Demonstration data is not a live environmental assessment and
  does not claim live provider behavior.
- **Notes / Follow-up:** Usage limits are defaults (5/2/2/10), not commercial values. Rate limiting is
  in-process. Shared demo catalog is read-only for visitors; simulated deliveries are labelled and never
  emailed. Compatible with a future Trial organization on the existing entitlement path — do not implement
  Stripe changes here. Recommended next package: authenticated free-trial organization on the same
  Command Center / AOI / alert surfaces, still without billing-contract changes unless Stripe test-mode
  credentials are supplied.

---

## 2026-08-13 — Authenticated Free Trial Organization Foundation

- **Date:** 2026-08-13
- **Work Package:** Commercial — Authenticated Free Trial Organization
- **Task ID:** Trial organization foundation (post-demo control plane)
- **Objective:** Allow a qualified authenticated user to leave the public Demo and enter a genuine
  ForestWatch organization with a limited free-trial entitlement profile, using the existing
  organization / AOI / intelligence / alert / Command Center architecture. Stripe remains out of scope.
- **Files Created:**
  - `backend/app/core/commercial/lifecycle.py` — commercial lifecycle vocabulary (distinct from
    `organization.status` and `kind`)
  - `backend/app/core/commercial/trial_profile.py` — trial and trial-expired entitlement profiles
  - `backend/app/models/trial.py` — public trial status / start request
  - `backend/app/services/trial_service.py` — idempotent personal-org upgrade, expiration, status
  - `backend/app/api/trial_routes.py` — `POST /api/trial/start`, `GET /api/trial/status`
  - `backend/tests/test_trial_organization.py` (15)
  - `frontend/src/api/trial.js`, `frontend/src/context/TrialContext.jsx`
  - `frontend/src/components/trial/` — status bar, onboarding, conversion CTA
  - `frontend/src/pages/TrialSetupPage.jsx`
  - `frontend/src/components/trial/__tests__/TrialSurfaces.test.jsx` (7)
- **Files Modified:** entitlement types + plan catalog (policy/channel limits so a future paid plan can
  replace the trial profile); Organization commercial fields; EntitlementService `apply_profile`;
  organization public/list; context resolve expires trial on product requests; AOI re-enable limit;
  alert policy/channel limits and trial email-only destination; deps/server/config; demo catalog keys;
  customer-alert test fixture limits; frontend routing, layout, demo conversion, register/login,
  Command Center, investigation, alerts, billing. `ORACLE_MANIFEST.json` and golden artifacts untouched.
  No Stripe checkout/webhook/gateway changes.
- **Decision:** Upgrade the user's **personal organization** into trial state. Bootstrap already creates
  one org per user; a second trial org would split AOI/alerts/future billing. The reserved demo org is
  never converted. Extra orgs created via `POST /organizations` are left untouched.
- **Tests Added or Updated:** trial creation/idempotency/ownership, expiration without data deletion,
  AOI and alert limits, account-email constraint, demo/user/org isolation, paid-source non-overwrite;
  frontend onboarding, status, expiration, conversion, bbox AOI setup.
- **Verification:**
  - Trial + commercial + demo subset: 201 passed
  - Backend offline (ignore live `backend_test.py`, `test_analytics.py`, `test_ingestion.py`): **2456 passed**
  - Frontend suite: **444 passed**
  - Phase 0 oracle set: **140 passed**
  - Ten-run determinism: **636 passed identically** on all ten runs; golden artifacts byte-identical
- **Result:** Complete as an authenticated trial on the real product architecture. Not production-ready.
  Live providers, SMTP, and Stripe are unverified. Trial is not a parallel mock system.
- **Notes / Follow-up:** Trial duration default 14 days (`TRIAL_DURATION_DAYS`). Alert delivery during
  trial is constrained to the signed-in account email; webhooks are blocked. Expiration keeps data and
  applies `trial_expired_profile`. A later Stripe package should write `plan:*` entitlements (already
  treated as paid so trial expiration will not overwrite them) and may set `commercial_lifecycle=paid`.
  Recommended next package: paid subscription replacing the trial entitlement profile, still without
  changing AOI / intelligence / alert / Command Center architecture.

---

## 2026-08-20 — Public Launch Readiness + Customer Value Validation

- **Date:** 2026-08-20
- **Work Package:** Public launch readiness and customer-value validation
- **Task ID:** Launch readiness (post-trial organization)
- **Objective:** Determine whether ForestWatch can be shown publicly as a product that convinces a
  forestry/environmental prospect to start a trial — without redesigning architecture or implementing
  Stripe. Optimize for unmistakable customer value, not feature completeness.
- **Files Created:**
  - `frontend/src/pages/__tests__/DashboardPage.test.jsx` — operator home is organization/Command Center, not a generic SaaS dump
  - `frontend/src/pages/__tests__/AuthPages.test.jsx` — login must not publish admin credentials; register always enters trial setup
  - `frontend/src/components/layout/__tests__/AppLayout.test.jsx` — customer nav hides Modules and the unscoped live map
- **Files Modified:**
  - `frontend/src/pages/DashboardPage.jsx` — operator home is org-named Command Center; removed analytics dump, unscoped `/alerts` table, and roadmap/AI placeholder modules
  - `frontend/src/components/intelligence/IntelligenceCommandCenter.jsx` — empty queue explains next action (no AOI vs watching with no signals)
  - `frontend/src/pages/LoginPage.jsx` — removed published admin credentials and generic slogan/hero; operational copy
  - `frontend/src/pages/RegisterPage.jsx` — every new account continues to `/trial/setup`
  - `frontend/src/pages/ExplorePage.jsx` — secondary CTA is trial language (`/register?from=demo`)
  - `frontend/src/components/layout/AppLayout.jsx` — Command Center label; hide Modules and unscoped map from customer nav
  - `frontend/src/pages/MapPage.jsx` — remaining route labelled as unscoped platform feed, not organization intelligence
  - `frontend/src/test-utils/reactRouterDomMock.js` — `NavLink` and `useLocation` stubs for layout/auth tests
  - `frontend/src/components/intelligence/__tests__/ProductSurfaces.test.jsx`, `frontend/src/pages/__tests__/ExplorePage.test.jsx`
  - `backend/.env.example` — public-deployment blockers documented (JWT, admin password, CORS)
  - No changes to entitlement evaluation, AOI matching, evidence construction, intelligence scoring, alert persistence, or scheduler ownership. `ORACLE_MANIFEST.json` and golden artifacts untouched. No Stripe/billing contract changes.
- **Tests Added or Updated:** operator dashboard surface; Command Center empty next-action; Explore trial CTA; login credential leak; register → trial setup; customer nav.
- **Verification:**
  - Backend offline (ignore live `backend_test.py`, `test_analytics.py`, `test_ingestion.py`): **2456 passed**
  - Frontend suite: **451 passed**
  - Phase 0 oracle set: **140 passed**
  - Ten-run determinism: **636 passed identically** on all ten runs; golden artifacts byte-identical throughout
- **Result:** The public journey now lands on organization-scoped intelligence rather than a generic dashboard, and the login page no longer publishes admin credentials. **Not production-ready.** Deployment still requires rotated secrets, explicit CORS, HTTPS cookies, verified SMTP, and live provider configuration. Stripe remains out of scope.
- **Notes / Follow-up:** Empty Command Center after AOI create is expected while live GFW/EEA/EFFIS are off — copy now says so rather than looking broken. `/map` and `/modules` remain as routes but are no longer promoted. Do not add a pricing system or Stripe checkout in a follow-up unless that is the dedicated package.

---

## 2026-08-20 — ForestWatch Startup + Runtime Stabilization

- **Date:** 2026-08-20
- **Work Package:** Startup + runtime stabilization (blocker)
- **Task ID:** Stop new feature work; make ForestWatch reliably runnable
- **Objective:** Discover the actual startup/runtime failure state by running backend, frontend, MongoDB, and scheduler as a developer would, then fix every blocker on the critical path. No Stripe, no new intelligence/UX/commercial features, no architecture redesign, no Phase 0 golden changes.
- **Files Created:** none (this package only repaired existing startup/runtime paths)
- **Files Modified:**
  - `backend/server.py` — un-indent `demo_router` / `trial_router` registration; restore `ForestEventService` and `IntelligenceCycleRepository` imports used at scheduler bootstrap; remove duplicate intelligence-event index creation (owned by the migration)
  - `backend/app/core/intelligence_events_migration.py` — named indexes are created even when Mongo already has the same keys under an auto-generated name (`IndexOptionsConflict` code 85)
  - `backend/tests/fixtures/fake_intelligence_events_collection.py` — conflict + `drop_index` behaviour for the migration tests
  - `backend/tests/test_intelligence_events_migration.py` — auto-named duplicate index replacement
  - `backend/app/modules/reports/pdf_generator.py` — land-cover distribution accepts the analytics list contract (`[{land_cover, events}, ...]`) as well as a legacy mapping
  - `backend/tests/test_reports.py` — PDF accepts list land-cover distribution
  - `backend/app/modules/analytics/analytics_repository.py` — coordinate `$match` uses `$expr` so aggregation `$gte`/`$lte` are not treated as query operators
  - `backend/tests/test_map_scope_contract.py` — match-stage contract
  - Frontend: no changes this package (compiled and rendered as-is)
  - `ORACLE_MANIFEST.json` and golden artifacts untouched. Billing remains optional (`ENABLE_BILLING` defaults false); Stripe credentials are not required.
- **Tests Added or Updated:** intelligence-events index rename; PDF land-cover list contract; map-overlay `$expr` match stage.
- **Verification:**
  - Actual process start: MongoDB `mongodb://localhost:27017`; uvicorn `127.0.0.1:8000` with `backend/.env`; CRA `localhost:3000` with `REACT_APP_BACKEND_URL`. `GET /api/health` → `{"status":"healthy"}`. Frontend webpack compiled; `/explore` renders without authentication.
  - Browser/API smoke: Landing → Demo (Command Center, investigation, simulated alert) → Register → Trial setup + AOI → Command Center → Alerts → Investigations → Billing with billing disabled (catalog renders, checkout absent, no Stripe calls)
  - Backend offline (ignore live `backend_test.py`, `test_analytics.py`, `test_ingestion.py`): **2458 passed**
  - Frontend suite: **451 passed**
  - Phase 0 oracle set: **140 passed**
  - Ten-run determinism: **636 passed identically** on all ten runs; golden artifacts byte-identical throughout
- **Result:** ForestWatch starts and the authenticated critical path is usable locally with billing disabled. **Not production-ready.** JWT length, CORS default, cookie flags, live providers, SMTP, and Stripe remain deployment concerns. Romania seed is not fully idempotent across restarts.
- **Notes / Follow-up:** Do not resume the product roadmap until this baseline stays green. Excluded live suites still require a running backend (`backend_test.py`, `test_analytics.py`, `test_ingestion.py`). Runtime requires MongoDB. Stripe and SMTP are not required while `ENABLE_BILLING=false`. Next dedicated package may address seed idempotency, cookie/CORS/JWT production hardening, or live-provider configuration — not new product features.

---

## 2026-09-02 — Commercial Packaging Foundation

- **Date:** 2026-09-02
- **Work Package:** Commercial packaging foundation
- **Task ID:** Prepare ForestWatch for source-code licensing without changing product behavior
- **Objective:** Make the existing repository understandable, installable, and distributable as a commercially licensed geospatial intelligence platform with a forest-monitoring reference implementation.
- **Files Created:** `LICENSE`, `NOTICE`, `docker-compose.yml`, `docker/*`, `docs/getting-started/*`, `docs/packaging/*`, `scripts/create_release.ps1`, `scripts/release-exclusions.txt`, `.dockerignore`, `backend/.dockerignore`, `backend/tests/test_production_safety.py`
- **Files Modified:** root `README.md`; `backend/app/core/config.py` (optional `FORESTWATCH_ENV=production` fail-closed); `backend/.env.example`; `.gitignore`; targeted notes in `docs/DOCUMENT_HIERARCHY.md`, `docs/PROJECT_STATE.md`, `docs/DEPENDENCIES.md`, `docs/CHANGELOG.md`, `docs/archive/README.md`, `docs/engineering/STRIPE_TEST_MODE_VALIDATION.md`
- **Files Removed:** tracked `.gitconfig` (developer identity `dev@forestwatch.io`; not required by the application)
- **Tests Added or Updated:** `tests/test_production_safety.py` — production mode rejects documented development defaults; development mode unchanged
- **Verification:** Backend offline **2465 passed** (includes 7 production-safety tests). Frontend **451 passed**. Phase 0 **140 passed**. Ten-run determinism **636 identical**; goldens byte-identical. `docker compose config` validates; image build was not executed here because the Docker daemon was not running. Goldens and `ORACLE_MANIFEST.json` untouched. Stripe code untouched. Romania/forestry implementation retained.
- **Result:** Source package foundation: buyer README, license draft, NOTICE, Compose install path, getting-started, packaging overlay, release exclusions. Not a hosted SaaS; not production-hardened for every environment.
- **Notes / Follow-up:** Counsel must review `LICENSE`. NOTICE items marked VERIFY BEFORE DISTRIBUTION. Docker Compose is a development stack. Cookie `Secure`/`SameSite=None` still requires HTTPS in production. Do not start marketplace, pricing, or license-key work in this package.

---

## 2026-09-02 — Commercial Sales Page Foundation

- **Date:** 2026-09-02
- **Work Package:** Commercial sales page foundation
- **Task ID:** Public `/` landing for the source-code product
- **Objective:** Present ForestWatch to technical buyers as a geospatial intelligence platform package with a forest-monitoring reference implementation. No operational, intelligence, oracle, or Stripe changes.
- **Files Created:** `frontend/src/pages/SalesPage.jsx`, `frontend/src/pages/sales.css`, `frontend/src/config/commercial.js`, `frontend/src/components/sales/ArchitectureDiagram.jsx`, `frontend/src/components/sales/ProductShowcase.jsx`, `frontend/src/pages/__tests__/SalesPage.test.jsx`, `docs/packaging/sales-page.md`
- **Files Modified:** `frontend/src/App.js` (`/` visitors see SalesPage; signed-in users still go to `/dashboard`; `/explore` unchanged); `frontend/.env.example`; `docs/packaging/README.md`
- **Verification:** Full frontend Jest suite 32 files / 455 tests passed, including `SalesPage.test.jsx`. Browser smoke of `/` (desktop + 390px) and `/explore`. Backend, Phase 0, and goldens not modified.
- **Result:** Public commercial landing at `/`. Checkout URLs remain placeholders.

---

## 2026-09-02 — Buyer release artifact verification

- **Date:** 2026-09-02
- **Work Package:** Commercial packaging verification
- **Objective:** Produce `forestwatch-source-v1.0.0-rc1.zip` and verify it as a buyer archive. No application, intelligence, oracle, or billing changes.
- **Files Created:** `RELEASE_MANIFEST.md`
- **Files Modified:** `scripts/create_release.ps1`, `scripts/release-exclusions.txt`, buyer docs (getting-started, packaging checklist, README Compose comments), `docker/frontend.Dockerfile` (copy `.npmrc` before `npm ci`), `frontend/src/pages/MapPage.jsx` (hooks called before demo redirect so `npm run build` succeeds)
- **Verification:** Extracted zip outside the repo. `docker compose config` + `up --build` from the extract. Mongo healthy, `/api/health`, `/` and `/explore` 200. Production-safety 7 passed. Frontend 455 passed. Goldens untouched.
- **Result:** `dist/forestwatch-source-v1.0.0-rc1.zip` (gitignored) with adjacent `.sha256`. Ready with documented warnings (draft LICENSE, unvalidated Stripe, no hosting).

---

## 2026-09-02 — v1.0.0 commercial upload hygiene

- **Date:** 2026-09-02
- **Work Package:** Final source-package version bump and hygiene
- **Objective:** Replace prerelease `v1.0.0-rc1` metadata with `v1.0.0` and produce the upload zip. No application, intelligence, oracle, or billing changes.
- **Files Modified:** `RELEASE_MANIFEST.md`, `scripts/create_release.ps1` comment, `docs/packaging/release-checklist.md`, `docs/CHANGELOG.md`, `docs/RELEASE_NOTES.md`, `docs/PROJECT_STATE.md` (source-package vs hosted SaaS wording)
- **Result:** `dist/forestwatch-source-v1.0.0.zip`

---

