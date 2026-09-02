# Phase 0 — Engine Generalization: Implementation Backlog

**Status:** Ready for execution.
**Companion to:** `docs/engineering/PHASE-0-ENGINE-GENERALIZATION.md` (the Phase 0 spec).
**Authority:** Subordinate to the frozen Architecture v1.0 (`docs/architecture/`) and its
ADRs. This backlog introduces no architectural decisions. It is a planning artifact only —
no code, pseudo-code, APIs, class definitions, or algorithms.

**How to read a task:** Each task is sized for roughly one working session. "Expected
files/modules affected" names existing paths for orientation only; it is not a design.
Verification criteria are measurable outcomes, not opinions. A task is independent unless a
dependency is listed.

**Legend:** Complexity = Low / Medium / High (blast radius on the shared read/write path).
Risk = the chance and cost of introducing a regression.

---

## WP0 — Characterization Baseline & Golden Dataset

- **Objective:** Freeze the current wildfire-only behavior as an executable oracle before
  any change.
- **Dependencies:** None.
- **Expected deliverables:** A fixed seed fixture; captured golden outputs; a determinism
  harness; reviewer sign-off.

### WP0.1 — Define the frozen seed fixture
- **Purpose:** Provide a deterministic input dataset for all Phase 0 regression testing.
- **Description:** Assemble a fixed set of wildfire forest events that exercises baselines,
  anomalies, escalation, trend, and resolution across multiple regions and cycles.
- **Expected files/modules affected:** `backend/tests/` fixtures; existing seed references
  (`romania_seed_service`) for shape guidance only.
- **Dependencies:** None.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** Fixture loads deterministically; produces a non-trivial mix of
  active and resolved outcomes across at least two cycles.
- **Required unit tests:** Fixture-loader determinism test.
- **Required integration tests:** None.
- **Definition of complete:** Fixture committed and referenced by later WP tests.

### WP0.2 — Capture golden outputs
- **Purpose:** Record expected results of the current pipeline as the regression oracle.
- **Description:** Run the existing pipeline over WP0.1 and capture anomalies, intelligence
  events (active/resolved with scores, escalation, trend, priority, detection_count),
  incident aggregation, and command-center snapshot.
- **Expected files/modules affected:** `backend/tests/` golden artifacts.
- **Dependencies:** WP0.1.
- **Complexity:** Medium.
- **Risk:** Medium (an incorrect oracle masks regressions).
- **Verification criteria:** Captured outputs are byte-stable across repeated runs.
- **Required unit tests:** Snapshot-stability test for each captured output.
- **Required integration tests:** Full-cycle capture over the fixture.
- **Definition of complete:** Golden artifacts reviewed and frozen.

### WP0.3 — Determinism harness and sign-off
- **Purpose:** Guarantee the oracle is reproducible and reviewed.
- **Description:** Establish a single injected time anchor and repeatable execution for all
  golden runs; obtain reviewer sign-off freezing the oracle.
- **Expected files/modules affected:** `backend/tests/` test utilities.
- **Dependencies:** WP0.2.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** Ten consecutive runs produce identical golden outputs.
- **Required unit tests:** Repeated-run equality assertion.
- **Required integration tests:** None.
- **Definition of complete:** Signed-off oracle documented as the Phase 0 baseline.

---

## WP1 — Canonical Identity & Detection Contract (definitions)

- **Objective:** Define, as explicit contracts, canonical identity, the intelligence event
  model fields, and the Detection envelope.
- **Dependencies:** WP0.
- **Expected deliverables:** Contract definitions, validation rules, legacy-default rules,
  field mapping documentation.

### WP1.1 — Canonical identity contract
- **Purpose:** Represent `(incident_category, spatial_key)` as the intelligence identity.
- **Description:** Define the identity contract and establish `spatial_key` as an
  abstraction whose Phase 0 concrete value is the administrative region.
- **Expected files/modules affected:** `backend/app/models/intelligence_event.py`;
  `backend/app/core/ecosystem/`.
- **Dependencies:** WP0.
- **Complexity:** Low.
- **Risk:** Low (definition only).
- **Verification criteria:** Identity constructs from valid inputs and rejects incomplete
  inputs.
- **Required unit tests:** Construction and validation tests; region-as-spatial-key mapping.
- **Required integration tests:** None.
- **Definition of complete:** Contract exists and is referenced by WP3/WP4 planning.

### WP1.2 — Intelligence event field model alignment
- **Purpose:** Establish `event_type` as derived and `signal_type` as provenance per
  ADR-008.
- **Description:** Define the canonical field set and the mapping from current fields.
- **Expected files/modules affected:** `backend/app/models/intelligence_event.py`.
- **Dependencies:** WP1.1.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** Field mapping table complete; no identity field is mutable
  state.
- **Required unit tests:** Model field-presence and defaulting tests.
- **Required integration tests:** None.
- **Definition of complete:** Field model documented and validated.

### WP1.3 — Detection envelope contract
- **Purpose:** Define the canonical Detection contract per ADR-009.
- **Description:** Define the envelope fields (`spatial_key`, `incident_category`,
  `signal_type`, `severity`, `score`, `evidence`, `detected_at`) and validation rules.
- **Expected files/modules affected:** `backend/app/modules/analytics/` (new contract
  module location TBD by team).
- **Dependencies:** WP1.1.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** Envelope validates required fields and score bounds.
- **Required unit tests:** Envelope construction/validation tests.
- **Required integration tests:** None.
- **Definition of complete:** Envelope contract exists for WP3 to emit and WP4 to consume.

### WP1.4 — Legacy default rules
- **Purpose:** Guarantee legacy records resolve deterministically to `wildfire`.
- **Description:** Define and test the deterministic defaulting for absent
  `incident_category` on read.
- **Expected files/modules affected:**
  `backend/app/modules/analytics/intelligence_events_service.py` (read-side normalization);
  `backend/app/core/ecosystem/incident_categories.py`.
- **Dependencies:** WP1.1, WP1.2.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** A record without `incident_category` reads as `wildfire`.
- **Required unit tests:** Legacy-defaulting tests.
- **Required integration tests:** None.
- **Definition of complete:** Defaulting behavior specified and tested.

---

## WP2 — Category-Segmented Baselines & Anomaly Analysis

- **Objective:** Compute baselines/anomalies per `(spatial_key, incident_category)` in a
  single pass, preserving wildfire results.
- **Dependencies:** WP1.
- **Expected deliverables:** Segmented aggregation, category-aware anomaly output,
  per-category threshold config, isolation tests.

### WP2.1 — Segment baseline aggregation
- **Purpose:** Group baseline aggregation by spatial key and incident category.
- **Description:** Extend the baseline aggregation to segment by category in one pass.
- **Expected files/modules affected:**
  `backend/app/modules/analytics/analytics_repository.py`.
- **Dependencies:** WP1.1.
- **Complexity:** Medium.
- **Risk:** Medium (feeds dashboards, risk, reports).
- **Verification criteria:** For the wildfire-only oracle, segmented output equals WP0
  golden baselines.
- **Required unit tests:** Segmented aggregation shaping tests.
- **Required integration tests:** Aggregation over the WP0 fixture equals golden.
- **Definition of complete:** Segmented aggregation returns per-category rows.

### WP2.2 — Thread category through baseline shaping
- **Purpose:** Carry the category through the pure baseline-shaping functions.
- **Description:** Update baseline shaping to preserve category on each shaped row.
- **Expected files/modules affected:**
  `backend/app/modules/analytics/analytics_service.py`.
- **Dependencies:** WP2.1.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** Shaped rows retain category; wildfire values unchanged vs.
  golden.
- **Required unit tests:** Shaping tests with category retention.
- **Required integration tests:** None.
- **Definition of complete:** Baseline shaping is category-aware.

### WP2.3 — Category-aware anomaly evaluation
- **Purpose:** Emit anomalies tagged with their incident category.
- **Description:** Update anomaly evaluation to consume segmented baselines and tag output.
- **Expected files/modules affected:**
  `backend/app/modules/analytics/analytics_service.py`.
- **Dependencies:** WP2.2.
- **Complexity:** Medium.
- **Risk:** Medium.
- **Verification criteria:** Wildfire anomalies match WP0 golden set exactly.
- **Required unit tests:** Anomaly evaluation tests per category.
- **Required integration tests:** Anomaly detection over the fixture equals golden.
- **Definition of complete:** Anomalies carry category and match golden for wildfire.

### WP2.4 — Per-category threshold configuration
- **Purpose:** Make anomaly thresholds configuration keyed by category.
- **Description:** Introduce a threshold configuration structure; wildfire values equal the
  current constants.
- **Expected files/modules affected:** `backend/app/core/config.py` and/or a config module;
  `backend/app/modules/analytics/analytics_service.py`.
- **Dependencies:** WP2.3.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** Wildfire thresholds resolve to current values; a synthetic
  category can use different values.
- **Required unit tests:** Threshold-resolution tests.
- **Required integration tests:** None.
- **Definition of complete:** Thresholds are category-configurable; wildfire unchanged.

### WP2.5 — Cross-category isolation tests
- **Purpose:** Prove categories do not contaminate each other's baselines.
- **Description:** Add tests with two synthetic categories in one region.
- **Expected files/modules affected:** `backend/tests/test_regional_baselines.py`,
  `backend/tests/test_anomaly_detection.py`.
- **Dependencies:** WP2.3.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** Adding category B events does not change category A baselines.
- **Required unit tests:** Isolation assertions.
- **Required integration tests:** Two-category fixture segmentation test.
- **Definition of complete:** Isolation proven by passing tests.

---

## WP3 — Detector Abstraction & Registry

- **Objective:** Introduce the detector contract/registry and refactor the existing rule
  into the first detector emitting Detections.
- **Dependencies:** WP1, WP2.
- **Expected deliverables:** Detector contract, registry, wildfire baseline detector,
  equivalence tests.

### WP3.1 — Detector contract
- **Purpose:** Define the detector contract (segmented input → Detections).
- **Description:** Specify the detector contract per ADR-004.
- **Expected files/modules affected:** `backend/app/modules/analytics/` (detector module
  location TBD).
- **Dependencies:** WP1.3.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** Contract admits a conforming detector and rejects a
  non-conforming one.
- **Required unit tests:** Contract conformance tests.
- **Required integration tests:** None.
- **Definition of complete:** Detector contract exists.

### WP3.2 — Detector registry
- **Purpose:** Register detectors without modifying the engine.
- **Description:** Provide a registry mirroring the existing incident-aggregation/report
  registries.
- **Expected files/modules affected:** `backend/app/modules/analytics/`.
- **Dependencies:** WP3.1.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** A registered detector is discoverable and invoked; a second
  detector registers without engine edits.
- **Required unit tests:** Registration/discovery tests.
- **Required integration tests:** None.
- **Definition of complete:** Registry operational.

### WP3.3 — Refactor existing rule into the wildfire baseline detector
- **Purpose:** Make the current anomaly rule the first registered detector emitting the
  Detection envelope.
- **Description:** Move the existing rule behind the detector contract; output Detections.
- **Expected files/modules affected:**
  `backend/app/modules/analytics/analytics_service.py`; new detector module.
- **Dependencies:** WP2.3, WP3.2, WP1.3.
- **Complexity:** Medium.
- **Risk:** Medium.
- **Verification criteria:** Detections for the oracle map one-to-one to WP0 golden
  anomalies (regions, scores, severities).
- **Required unit tests:** Detector output tests.
- **Required integration tests:** Detector-over-fixture equals golden anomalies.
- **Definition of complete:** The rule runs as a registered detector producing Detections.

### WP3.4 — Detector-to-golden equivalence
- **Purpose:** Lock detector output against the oracle.
- **Description:** Add equivalence tests comparing Detections to golden anomalies.
- **Expected files/modules affected:** `backend/tests/test_anomaly_detection.py`.
- **Dependencies:** WP3.3.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** Equivalence test green.
- **Required unit tests:** Equivalence assertions.
- **Required integration tests:** None.
- **Definition of complete:** Detector equivalence proven.

---

## WP4 — Generalized Reconciliation over Detections

- **Objective:** Reconcile over Detections keyed by canonical identity, preserving scoring
  and producing a change-set.
- **Dependencies:** WP1, WP3.
- **Expected deliverables:** Generalized reconcile, canonical-identity keying, change-set,
  behavioral equivalence, multi-category coexistence.

### WP4.1 — Replace reconciliation key with canonical identity
- **Purpose:** Remove the `("anomaly", region)` literal key.
- **Description:** Key active-event lookup and dedup by `(incident_category, spatial_key)`.
- **Expected files/modules affected:**
  `backend/app/modules/analytics/intelligence_events_service.py`;
  `backend/app/modules/analytics/intelligence_events_repository.py`.
- **Dependencies:** WP1.1.
- **Complexity:** High.
- **Risk:** High (single write authority).
- **Verification criteria:** For the oracle, produced events equal golden; no `"anomaly"`
  literal remains as identity.
- **Required unit tests:** Keying and dedup tests.
- **Required integration tests:** Reconcile-over-fixture equals golden.
- **Definition of complete:** Reconciliation keyed by canonical identity.

### WP4.2 — Reconcile consumes Detections
- **Purpose:** Make reconciliation input the canonical Detection set.
- **Description:** Adapt reconciliation to consume Detections from the detector(s).
- **Expected files/modules affected:**
  `backend/app/modules/analytics/intelligence_events_service.py`;
  `backend/app/modules/analytics/analytics_service.py` (orchestration point).
- **Dependencies:** WP3.3, WP4.1.
- **Complexity:** Medium.
- **Risk:** Medium.
- **Verification criteria:** Reconciliation runs solely from Detections; oracle equivalence
  holds.
- **Required unit tests:** Detection-driven reconcile tests.
- **Required integration tests:** Full detect→reconcile path equals golden.
- **Definition of complete:** Reconciliation consumes only Detections.

### WP4.3 — Change-set output
- **Purpose:** Emit created/updated/resolved transitions as a first-class output.
- **Description:** Produce a per-cycle change-set for downstream consumers.
- **Expected files/modules affected:**
  `backend/app/modules/analytics/intelligence_events_service.py`.
- **Dependencies:** WP4.2.
- **Complexity:** Medium.
- **Risk:** Medium.
- **Verification criteria:** Change-set enumerates exactly the transitions of a cycle
  against the fixture.
- **Required unit tests:** Change-set content tests.
- **Required integration tests:** Change-set over two consecutive cycles.
- **Definition of complete:** Change-set produced and asserted.

### WP4.4 — Preserve scoring and lifecycle (regression)
- **Purpose:** Guarantee scoring/escalation/trend/priority are unchanged.
- **Description:** Confirm scoring functions are untouched in behavior by reconciliation
  changes.
- **Expected files/modules affected:**
  `backend/tests/test_intelligence_events.py`,
  `backend/tests/test_intelligence_escalation.py`,
  `backend/tests/test_intelligence_priority_scoring.py`.
- **Dependencies:** WP4.2.
- **Complexity:** Low.
- **Risk:** Medium.
- **Verification criteria:** All scoring regression tests green; values equal golden.
- **Required unit tests:** Scoring regression suite.
- **Required integration tests:** None.
- **Definition of complete:** Scoring equivalence proven.

### WP4.5 — Multi-category coexistence
- **Purpose:** Prove two categories in one region coexist and resolve independently.
- **Description:** Add tests with two categories sharing a region across cycles.
- **Expected files/modules affected:** `backend/tests/test_intelligence_events.py`.
- **Dependencies:** WP4.2.
- **Complexity:** Medium.
- **Risk:** Medium.
- **Verification criteria:** Category A and B events do not collide; each resolves on its
  own absence.
- **Required unit tests:** Coexistence and independent-resolution tests.
- **Required integration tests:** Two-category multi-cycle reconcile.
- **Definition of complete:** Coexistence proven.

---

## WP5 — Generalized Aggregation Registry

- **Objective:** Merge any registered aggregator generically; remove the hardcoded wildfire
  extraction.
- **Dependencies:** WP2 (category counts). May run parallel to WP4/WP6.
- **Expected deliverables:** Generic contribution shape, generic merge, adapted wildfire
  aggregator, synthetic-aggregator test.

### WP5.1 — Define generic aggregator contribution shape
- **Purpose:** Standardize how aggregators contribute category counts.
- **Description:** Define a normalized contribution shape for the rollup.
- **Expected files/modules affected:**
  `backend/app/modules/analytics/incident_aggregation.py`.
- **Dependencies:** WP2.3.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** Contribution shape accommodates any category without
  special-casing.
- **Required unit tests:** Contribution shape tests.
- **Required integration tests:** None.
- **Definition of complete:** Shape defined.

### WP5.2 — Replace hardcoded wildfire extraction with generic merge
- **Purpose:** Remove category-specific extraction from the rollup.
- **Description:** Merge contributions generically into the by-category rollup.
- **Expected files/modules affected:**
  `backend/app/modules/analytics/incident_aggregation.py`.
- **Dependencies:** WP5.1.
- **Complexity:** Medium.
- **Risk:** Medium (command-center visible).
- **Verification criteria:** Wildfire-only rollup equals WP0 golden.
- **Required unit tests:** Generic merge tests.
- **Required integration tests:** Rollup over fixture equals golden.
- **Definition of complete:** No category literal remains in the merge.

### WP5.3 — Adapt the wildfire aggregator
- **Purpose:** Make the existing aggregator emit the generic contribution.
- **Description:** Adapt the wildfire aggregator to the new shape.
- **Expected files/modules affected:**
  `backend/app/modules/analytics/incident_aggregation.py`.
- **Dependencies:** WP5.2.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** Wildfire aggregator output unchanged in the rollup vs. golden.
- **Required unit tests:** Wildfire aggregator contribution tests.
- **Required integration tests:** None.
- **Definition of complete:** Aggregator uses generic shape.

### WP5.4 — Synthetic second-aggregator test
- **Purpose:** Prove a new domain appears without engine edits.
- **Description:** Register a synthetic aggregator and assert its counts appear.
- **Expected files/modules affected:** `backend/tests/test_incident_aggregation.py`.
- **Dependencies:** WP5.2.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** Synthetic category counts appear with no merge-logic change.
- **Required unit tests:** Synthetic aggregator test.
- **Required integration tests:** None.
- **Definition of complete:** Extensibility proven.

---

## WP6 — Command–Query Separation

- **Objective:** Reads never write; reconciliation runs in the scheduler (plus optional
  explicit command).
- **Dependencies:** WP4.
- **Expected deliverables:** Write-free read endpoints, scheduler-owned reconcile, optional
  command, write-spy tests.

### WP6.1 — Remove reconciliation from the read path
- **Purpose:** Stop the events read endpoint from triggering reconciliation.
- **Description:** Make the read endpoint return previously reconciled state only.
- **Expected files/modules affected:**
  `backend/app/modules/analytics/analytics_routes.py`;
  `backend/app/modules/analytics/analytics_service.py`.
- **Dependencies:** WP4.2.
- **Complexity:** Medium.
- **Risk:** Medium (API behavior/freshness change).
- **Verification criteria:** The read endpoint performs zero writes (write-spy).
- **Required unit tests:** Read-handler no-write tests.
- **Required integration tests:** Read endpoint over fixture returns state without mutation.
- **Definition of complete:** Reads are side-effect free.

### WP6.2 — Confirm scheduler ownership of reconciliation
- **Purpose:** Ensure reconciliation runs in the scheduler cycle.
- **Description:** Verify the scheduler invokes reconciliation as the owner.
- **Expected files/modules affected:** `backend/app/services/scheduler_service.py`.
- **Dependencies:** WP6.1.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** A scheduler cycle reconciles; no other non-command path does.
- **Required unit tests:** Scheduler-cycle reconcile invocation test.
- **Required integration tests:** Cycle reconciles over fixture.
- **Definition of complete:** Scheduler is the reconciliation owner.

### WP6.3 — Optional explicit reconciliation command
- **Purpose:** Provide one authenticated command path if operationally required.
- **Description:** Provide an explicit command that triggers reconciliation, access
  controlled, separate from queries.
- **Expected files/modules affected:**
  `backend/app/modules/analytics/analytics_routes.py`; `backend/app/api/deps.py`.
- **Dependencies:** WP6.1.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** Command requires authentication; only it (and the scheduler)
  can trigger reconciliation.
- **Required unit tests:** Command authorization tests.
- **Required integration tests:** Command triggers a reconcile; queries do not.
- **Definition of complete:** Command exists and is access controlled (or explicitly
  omitted if the team decides scheduler-only suffices).

### WP6.4 — Read-path write-spy suite
- **Purpose:** Continuously enforce read/write separation.
- **Description:** Add write-spy assertions across intelligence read endpoints.
- **Expected files/modules affected:** `backend/tests/` route tests.
- **Dependencies:** WP6.1.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** No read endpoint issues a write during any test.
- **Required unit tests:** Write-spy tests per read endpoint.
- **Required integration tests:** None.
- **Definition of complete:** Write-spy suite green and CI-enforced.

---

## WP7 — Single-Reconciler Guarantee

- **Objective:** At most one reconciliation runs at a time across processes, using the
  existing datastore.
- **Dependencies:** WP4, WP6.
- **Expected deliverables:** Advisory lock mechanism, scheduler integration, concurrency
  test.

### WP7.1 — Advisory lock mechanism
- **Purpose:** Provide a single-runner primitive without new infrastructure.
- **Description:** Use an existing-datastore advisory lock/record to gate reconciliation.
- **Expected files/modules affected:** `backend/app/services/scheduler_service.py`;
  a repository under `backend/app/repositories/`.
- **Dependencies:** WP4.2.
- **Complexity:** Medium.
- **Risk:** Medium.
- **Verification criteria:** Acquiring the lock twice concurrently grants it once.
- **Required unit tests:** Lock acquire/release/contention tests.
- **Required integration tests:** None.
- **Definition of complete:** Lock primitive available.

### WP7.2 — Integrate the lock into the cycle
- **Purpose:** Guard the reconciliation step with the lock.
- **Description:** The cycle acquires the lock before reconciling and yields safely if held.
- **Expected files/modules affected:** `backend/app/services/scheduler_service.py`.
- **Dependencies:** WP7.1.
- **Complexity:** Low.
- **Risk:** Medium.
- **Verification criteria:** A held lock causes a no-op cycle with no state mutation.
- **Required unit tests:** Guarded-cycle tests.
- **Required integration tests:** None.
- **Definition of complete:** Cycle is lock-guarded.

### WP7.3 — Concurrency test
- **Purpose:** Prove concurrent cycles cannot both mutate state.
- **Description:** Simulate two concurrent cycles and assert single-writer behavior.
- **Expected files/modules affected:** `backend/tests/test_scheduler.py`.
- **Dependencies:** WP7.2.
- **Complexity:** Medium.
- **Risk:** Medium.
- **Verification criteria:** Only one of two concurrent cycles mutates state; the other
  yields.
- **Required unit tests:** None beyond WP7.1.
- **Required integration tests:** Concurrent-cycle single-writer test.
- **Definition of complete:** Concurrency guarantee proven.

---

## WP8 — Migration & Index Alignment

- **Objective:** Idempotently backfill category, re-key active events to canonical identity,
  and align indexes.
- **Dependencies:** WP1, WP4.
- **Expected deliverables:** Idempotent migration, index changes, migration regression +
  idempotency tests, rollback/recovery runbook.

### WP8.1 — Backfill `incident_category`
- **Purpose:** Populate category on existing records.
- **Description:** Idempotently set category on `forest_events` and active
  `intelligence_events`; absent ⇒ `wildfire`.
- **Expected files/modules affected:** `backend/app/core/migrations.py`.
- **Dependencies:** WP1.1, WP1.4.
- **Complexity:** Medium.
- **Risk:** Medium.
- **Verification criteria:** All targeted records carry a category after migration; re-run
  changes nothing.
- **Required unit tests:** Backfill correctness and idempotency tests.
- **Required integration tests:** Backfill over a legacy fixture.
- **Definition of complete:** Backfill idempotent and correct.

### WP8.2 — Re-key active events to canonical identity
- **Purpose:** Prevent the first post-deploy cycle from mass-resolving/recreating events.
- **Description:** Align stored identity of active `intelligence_events` with
  `(incident_category, spatial_key)`.
- **Expected files/modules affected:** `backend/app/core/migrations.py`.
- **Dependencies:** WP8.1, WP4.1.
- **Complexity:** High.
- **Risk:** High (one-time live mutation).
- **Verification criteria:** After migration + one cycle, active events retain
  `detection_count`/`trend`; no spurious resolve/create.
- **Required unit tests:** Re-key correctness tests.
- **Required integration tests:** Legacy → migrate → cycle history-preservation test (the
  go/no-go gate).
- **Definition of complete:** Re-key proven safe and idempotent.

### WP8.3 — Index alignment
- **Purpose:** Support segmented aggregation and canonical-identity dedup.
- **Description:** Add/adjust indexes for `(event_type/category, region, detected_at)` style
  segmentation and canonical-identity active dedup.
- **Expected files/modules affected:** `backend/server.py` (index creation);
  `backend/app/modules/analytics/intelligence_events_repository.py`.
- **Dependencies:** WP2.1, WP4.1.
- **Complexity:** Medium.
- **Risk:** Medium.
- **Verification criteria:** Segmented aggregation and dedup queries use the new indexes.
- **Required unit tests:** None.
- **Required integration tests:** Query-plan/timing check at elevated cardinality.
- **Definition of complete:** Indexes present and effective.

### WP8.4 — Migration regression & idempotency tests
- **Purpose:** Gate the migration.
- **Description:** Consolidate the go/no-go migration tests.
- **Expected files/modules affected:** `backend/tests/` migration tests.
- **Dependencies:** WP8.2, WP8.3.
- **Complexity:** Medium.
- **Risk:** Medium.
- **Verification criteria:** History preserved; migration re-runnable with no further
  change.
- **Required unit tests:** Idempotency assertions.
- **Required integration tests:** End-to-end migrate-then-cycle test.
- **Definition of complete:** Migration gate green.

### WP8.5 — Rollback & recovery runbook
- **Purpose:** Document safe rollback and failure recovery.
- **Description:** Write the operational runbook (snapshot, config switch, re-run behavior).
- **Expected files/modules affected:** `docs/engineering/`.
- **Dependencies:** WP8.2.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** Runbook lists snapshot, switch, and recovery steps with
  measurable checkpoints.
- **Required unit tests:** None.
- **Required integration tests:** None.
- **Definition of complete:** Runbook reviewed.

---

## WP9 — Documentation & ADR Status Updates

- **Objective:** Reconcile as-built docs with delivered behavior; additive changelog entry.
- **Dependencies:** All implementation WPs merged.
- **Expected deliverables:** Updated as-built docs, changelog entry, deploy runbook.

### WP9.1 — Update as-built documentation
- **Purpose:** Reflect that Phase 0 behaviors now match canonical.
- **Description:** Update as-built notes and mark superseded pre-v1.0 notes resolved.
- **Expected files/modules affected:** `docs/INTELLIGENCE_PIPELINE.md`,
  `docs/ARCHITECTURE.md`.
- **Dependencies:** WP4, WP6, WP8.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** No stale "pre-v1.0" divergence notes for delivered items.
- **Required unit tests:** None.
- **Required integration tests:** None.
- **Definition of complete:** As-built docs accurate.

### WP9.2 — Architecture changelog entry
- **Purpose:** Record Phase 0 delivery.
- **Description:** Add an additive, non-normative entry.
- **Expected files/modules affected:** `docs/architecture/CHANGELOG.md`.
- **Dependencies:** WP9.1.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** Entry present; no canonical spec content altered.
- **Required unit tests:** None.
- **Required integration tests:** None.
- **Definition of complete:** Changelog updated.

### WP9.3 — Deploy runbook
- **Purpose:** Document deploy ordering (migration before scheduler start; config switch).
- **Description:** Write the deployment sequence and verification checkpoints.
- **Expected files/modules affected:** `docs/engineering/`.
- **Dependencies:** WP8.5.
- **Complexity:** Low.
- **Risk:** Low.
- **Verification criteria:** Runbook lists ordered steps with measurable checkpoints.
- **Required unit tests:** None.
- **Required integration tests:** None.
- **Definition of complete:** Deploy runbook reviewed.

---

## 1. Critical Path

```
WP0.1 → WP0.2 → WP0.3
      → WP1.1 → WP1.2 → WP1.4
             → WP2.1 → WP2.2 → WP2.3
                    → WP3.1 → WP3.2 → WP3.3
                           → WP4.1 → WP4.2 → WP4.3
                                  → WP6.1 → WP6.2
                                         → WP7.1 → WP7.2 → WP7.3
                    → WP8.1 → WP8.2 → WP8.4
      → WP9.1 → WP9.2
```

The dominant chain is: **oracle (WP0) → contracts (WP1) → segmentation (WP2) → detector
(WP3) → reconciliation (WP4) → read/write split (WP6) → single-reconciler (WP7) → migration
(WP8) → docs (WP9)**. WP4.x and WP8.2 are the narrowest, highest-risk gates on this path.

## 2. Parallel Work Opportunities

- **WP1.3** (Detection envelope) can proceed alongside **WP2.1–WP2.2** once WP1.1 lands.
- **WP5.x** (generalized aggregation) can run in parallel with **WP4.x/WP6.x** after WP2.3.
- **WP2.5** (isolation tests) can be authored in parallel with WP2.4.
- **WP4.4** (scoring regression) can be prepared in parallel with WP4.2/WP4.3.
- **WP6.4** (write-spy suite) can be authored while WP6.1 is in progress.
- **WP8.3** (indexes) can be drafted early but must merge after WP2.1 and WP4.1.
- **WP8.5 / WP9.3** (runbooks) can be drafted in parallel with WP8.4.

## 3. Highest-Risk Tasks

| Task | Risk | Why | Primary control |
|------|------|-----|-----------------|
| WP4.1 | High | Changes the single write-authority key | Golden equivalence + coexistence tests |
| WP8.2 | High | One-time live mutation of intelligence state | Go/no-go migration gate (WP8.4) + snapshot |
| WP4.2 | Medium | Redirects reconcile inputs to Detections | Full detect→reconcile equivalence |
| WP2.1 | Medium | Core aggregation feeding many consumers | Segmented output equals golden |
| WP5.2 | Medium | Command-center-visible rollup change | Rollup equals golden; synthetic aggregator test |
| WP6.1 | Medium | API freshness/behavior change | Write-spy + documented cadence |
| WP7.2 | Medium | Concurrency guard on the writer | Concurrency single-writer test |

## 4. Recommended Implementation Order

1. WP0.1 → WP0.2 → WP0.3 (freeze the oracle)
2. WP1.1 → WP1.2 → WP1.3 → WP1.4 (contracts)
3. WP2.1 → WP2.2 → WP2.3 → WP2.4 → WP2.5 (segmentation)
4. WP3.1 → WP3.2 → WP3.3 → WP3.4 (detector)
5. WP4.1 → WP4.2 → WP4.3 → WP4.4 → WP4.5 (reconciliation)
6. WP5.1 → WP5.2 → WP5.3 → WP5.4 (aggregation; may overlap step 5)
7. WP6.1 → WP6.2 → WP6.3 → WP6.4 (read/write separation)
8. WP7.1 → WP7.2 → WP7.3 (single reconciler)
9. WP8.1 → WP8.2 → WP8.3 → WP8.4 → WP8.5 (migration & indexes)
10. WP9.1 → WP9.2 → WP9.3 (documentation)

This order establishes the oracle first, changes contracts before behavior, changes reads
only after the write path is independently correct, and performs the one-time migration
last among code changes.

## 5. Estimated Completion Milestones

Milestones are ordered gates, not calendar commitments. Each is complete when its tasks
meet their Definition of Complete and CI is green.

- **M1 — Oracle Frozen:** WP0 complete.
- **M2 — Contracts Defined:** WP1 complete.
- **M3 — Segmentation Proven:** WP2 complete; wildfire equals golden; isolation proven.
- **M4 — Detector Live:** WP3 complete; Detections equal golden anomalies.
- **M5 — Reconciliation Generalized:** WP4 complete; golden equivalence + coexistence.
- **M6 — Aggregation Generalized:** WP5 complete.
- **M7 — Read/Write Separated & Single Reconciler:** WP6 + WP7 complete.
- **M8 — Migration Gate Passed:** WP8 complete; go/no-go test green.
- **M9 — Documentation Reconciled:** WP9 complete; ready for the engineering gate review.

## 6. Engineering Readiness Checklist

- [ ] WP0 oracle frozen and reproducible across repeated runs.
- [ ] Canonical identity contract in place; no `event_type` literal used as identity.
- [ ] Detection envelope contract in place and consumed only by reconciliation.
- [ ] Baselines/anomalies segmented by `(spatial_key, incident_category)` in one pass.
- [ ] Existing rule runs as a registered detector; second synthetic detector integrates with
      no engine edits.
- [ ] Reconciliation keyed by canonical identity; idempotent; emits a change-set; scoring
      unchanged vs. golden.
- [ ] Two categories in one region coexist and resolve independently (test green).
- [ ] Aggregation rollup generic; synthetic aggregator appears without merge edits.
- [ ] No read endpoint performs writes (write-spy suite green).
- [ ] Reconciliation runs only via scheduler (and optional explicit command).
- [ ] Single-reconciler guarantee proven under concurrency.
- [ ] Migration idempotent; go/no-go regression gate green; history preserved.
- [ ] Indexes present and demonstrably used at elevated cardinality.
- [ ] Full test matrix (unit/integration/regression/golden/migration/performance/
      acceptance) green in CI and deterministic.
- [ ] As-built docs reconciled; additive changelog entry; rollback and deploy runbooks
      present.
- [ ] No scope leakage (no new data source, domain, spatial extraction, detector type, or
      infrastructure).
