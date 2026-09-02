# Phase 0 — Engine Generalization: Implementation Specification

**Status:** Ready for engineering.
**Audience:** Senior development team executing Phase 0.
**Authority:** This is an execution plan. It is subordinate to the frozen architecture in
`docs/architecture/` (Architecture v1.0) and its ADRs. Where this plan and the canonical
architecture disagree, the canonical architecture governs. This plan introduces no new
architectural decisions.

**Guiding constraint:** Prefer the smallest correct implementation. Phase 0 changes the
engine internals of a single mature domain (wildfire) without changing its observable
behavior for that domain, while opening the engine to future domains. No new
infrastructure, no new architectural patterns.

---

## 1. Phase Objective

### What Phase 0 accomplishes
Phase 0 generalizes the intelligence engine from a single wildfire-shaped pipeline into
the domain-independent engine specified in Architecture v1.0, **without onboarding any new
domain and without ingesting any new data source**. It aligns the running implementation
with the canonical contracts that all later phases depend on.

Concretely, Phase 0 delivers:

1. **Canonical intelligence identity** `(incident_category, spatial_key)` replacing the
   current `(event_type, region)` key (ADR-001, ADR-008).
2. **Category-segmented analysis** — baselines and anomalies computed per
   `(spatial_key, incident_category)` rather than per region only.
3. **The Detector abstraction and registry**, with the existing rule as the first
   registered detector emitting the canonical Detection envelope (ADR-004, ADR-009).
4. **The generalized reconciliation contract** operating over Detections and keyed by
   canonical identity (ADR-002).
5. **The generalized aggregation registry** — cross-category rollup that merges any
   registered aggregator generically (removing the hardcoded wildfire path).
6. **Command–query separation** — reconciliation is a write owned by the scheduler; read
   endpoints return previously reconciled state (ADR-011, ADR-007).
7. **A single-reconciler guarantee** so the write path is safe under more than one
   process.
8. **An idempotent migration** aligning existing records to canonical identity.

### Why it exists
The current implementation encodes wildfire assumptions into engine internals:

- Reconciliation keys active events by the literal `("anomaly", region)`, so two incident
  categories in one region collide.
- Baselines aggregate all events per region with no category segmentation, so a second
  category's observations would poison wildfire baselines.
- The cross-category aggregation rollup extracts wildfire counts by name.
- The events read endpoint triggers reconciliation on every GET.

These are the exact structural blockers to multi-domain operation. Any attempt to onboard
a domain before resolving them would corrupt the existing wildfire domain. Phase 0 removes
the blockers once, so every later domain is additive.

### Architectural problems resolved
- **Identity collision** between categories sharing a region (correctness).
- **Signal contamination** across categories in baselines (correctness).
- **Open/closed violation** in aggregation and domain onboarding (maintainability).
- **Command–query violation** on the read path (correctness, scalability, caching).
- **Uncontrolled concurrency** of the single-writer engine (correctness under scale).

### Expected end-state
- The engine consumes Detections and writes intelligence keyed by canonical identity.
- Wildfire behavior is **observably unchanged**: for the wildfire-only dataset, the set of
  active/resolved intelligence events, their scores, escalation, trend, priority, and
  history are identical before and after Phase 0 (verified by golden dataset).
- Read endpoints never mutate state; reconciliation runs only in the scheduler (or an
  explicit command).
- Adding a second incident category is possible without touching reconciliation,
  segmentation core, scoring, or aggregation merge logic.
- All canonical contracts (identity, Detection envelope, reconciliation) are represented
  in code as explicit, tested contracts.

---

## 2. Scope

### Included
- Canonical identity representation on intelligence events and in the reconciliation key.
- Category-segmented baseline aggregation and anomaly evaluation.
- Detector abstraction, detector registry, and the existing rule refactored into the first
  detector producing the Detection envelope.
- Generalized reconciliation over Detections.
- Generalized incident-aggregation rollup.
- Command–query separation for intelligence reads; scheduler-owned reconciliation; one
  explicit authenticated command path for reconciliation if required operationally.
- Single-reconciler guarantee.
- Idempotent data migration and index alignment.
- Per-category threshold configuration (structure only; wildfire values preserve current
  behavior).
- Tests across all categories defined in Section 6.
- Documentation and ADR status updates.

### Excluded (belongs to later phases, not Phase 0)
- Any new ingestion provider or data source (e.g. forest-loss/GLAD/RADD).
- Any new incident category values or taxonomy expansion beyond what already exists.
- Generic Spatial Engine extraction and new spatial overlays (Phase 1).
- New detector *types* (threshold, change-detection, model-assisted). Phase 0 ships only
  the existing baseline-deviation detector, generalized.
- Frontend features, new map layers, new cards.

### Deferred (intentionally postponed within the engine)
- Finer `spatial_key` implementations (grid cell, feature id). Phase 0 uses the existing
  administrative region as the concrete spatial key, behind the canonical abstraction.
- Suppression / sticky-state resolution policies (contract accommodates them; not
  implemented).
- In-process domain events derived from the change-set (the change-set is produced;
  eventing consumers are future work).

### Out of scope (prohibited by the brief and by the architecture)
- Redesigning any architecture document or ADR.
- New infrastructure (message brokers, external caches, new datastores).
- Microservices, Kafka, event sourcing, CQRS beyond the read/write split already
  specified.
- Multi-tenancy implementation (the `tenant` identity dimension remains reserved per
  ADR-010).

---

## 3. Work Breakdown Structure

Each work package (WP) is sized to be a single milestone/sprint unit. Risk is rated
Low / Medium / High by blast radius on the shared write/read path.

### WP0 — Characterization Baseline & Golden Dataset
- **Purpose:** Capture the current wildfire-only behavior as executable golden fixtures
  *before* any change, so every later WP can prove behavioral equivalence.
- **Dependencies:** None. Must be first.
- **Deliverables:** A fixed seed dataset; captured expected outputs for anomalies,
  intelligence events (active/resolved with scores, escalation, trend, priority,
  detection_count), incident aggregation, command-center snapshot, and a full scheduler
  cycle. Documented as the Phase 0 regression oracle.
- **Estimated risk:** Low.
- **Verification:** Golden outputs reproducible deterministically across runs; reviewed
  and signed off as the frozen oracle.

### WP1 — Canonical Identity & Detection Contract (definitions)
- **Purpose:** Define, as explicit typed contracts, the canonical intelligence identity
  `(incident_category, spatial_key)`, the intelligence event model fields (ADR-008), and
  the Detection envelope (ADR-009). Establish `spatial_key` as an abstraction whose Phase 0
  implementation is the administrative region; establish `signal_type` as provenance and
  `event_type` as a derived label.
- **Dependencies:** WP0 (oracle exists).
- **Deliverables:** Contract definitions and their validation rules; a documented mapping
  from current fields to canonical fields; deterministic defaults for legacy records
  (absent `incident_category` ⇒ `wildfire`).
- **Estimated risk:** Low (definitions; no behavior change yet).
- **Verification:** Contract unit tests (construction, validation, legacy defaulting);
  review against ADR-001/008/009.

### WP2 — Category-Segmented Baselines & Anomaly Analysis
- **Purpose:** Change the baseline aggregation to group by
  `(spatial_key, incident_category)` in a single pass, and thread the category through
  baseline shaping and anomaly evaluation. Introduce per-category threshold configuration
  with wildfire values equal to today's constants.
- **Dependencies:** WP1.
- **Deliverables:** Segmented aggregation; category-aware anomaly output; per-category
  threshold config structure; preserved wildfire results.
- **Estimated risk:** Medium (core analytics; feeds dashboards, risk, reports).
- **Verification:** For the wildfire-only oracle, segmented output equals WP0 golden
  anomalies. New unit tests prove two synthetic categories in one region do not
  cross-contaminate baselines.

### WP3 — Detector Abstraction & Registry
- **Purpose:** Introduce the detector contract and registry; refactor the existing rule
  into a single registered baseline-deviation detector that consumes segmented analysis and
  emits the canonical Detection envelope. No new detector types.
- **Dependencies:** WP1, WP2.
- **Deliverables:** Detector contract; registry; the wildfire baseline detector; Detections
  carrying `spatial_key`, `incident_category`, `signal_type`, `severity`, `score`,
  `evidence`, `detected_at`.
- **Estimated risk:** Medium.
- **Verification:** Detector unit tests; Detections for the oracle match the anomaly set
  from WP0 one-to-one (same regions, scores, severities).

### WP4 — Generalized Reconciliation over Detections
- **Purpose:** Reconcile over Detections keyed by `(incident_category, spatial_key)`;
  remove the hardcoded `"anomaly"` key literal; preserve create/update/resolve semantics,
  the pure scoring functions, and the single batched read. Produce the change-set as a
  first-class output.
- **Dependencies:** WP1, WP3.
- **Deliverables:** Generalized reconcile; canonical-identity keying; change-set output;
  scoring untouched in behavior.
- **Estimated risk:** High (the single write authority; central correctness).
- **Verification:** Golden equivalence with WP0 for wildfire; new tests prove two
  categories in one region coexist without collision and resolve independently.

### WP5 — Generalized Aggregation Registry
- **Purpose:** Replace the wildfire-specific extraction in the cross-category rollup with a
  generic merge, so any registered aggregator contributes its category counts without
  editing the merge logic.
- **Dependencies:** WP2 (category counts available). May proceed in parallel with WP4.
- **Deliverables:** Generic rollup; wildfire aggregator adapted to the generic
  contribution shape; command-center snapshot unchanged for wildfire-only data.
- **Estimated risk:** Medium (user-visible in command center; localized).
- **Verification:** Command-center and incidents outputs equal WP0 golden for wildfire-only
  data; a synthetic second aggregator appears correctly in the rollup.

### WP6 — Command–Query Separation
- **Purpose:** Remove reconciliation from the read path. Reads return previously reconciled
  state. Reconciliation runs in the scheduler cycle and, if operationally required, via one
  explicit authenticated command path.
- **Dependencies:** WP4 (reconcile is invocable independently of reads).
- **Deliverables:** Read endpoints free of writes; scheduler remains the reconciliation
  owner; optional explicit command documented and access-controlled.
- **Estimated risk:** Medium (API behavior change; freshness semantics shift to cycle
  cadence).
- **Verification:** Read endpoints perform no writes (asserted via repository write spies);
  scheduler cycle still reconciles; freshness documented.

### WP7 — Single-Reconciler Guarantee
- **Purpose:** Ensure at most one reconciliation executes at a time across processes, using
  the existing datastore (an advisory lock/record), with no new infrastructure.
- **Dependencies:** WP4, WP6.
- **Deliverables:** A single-runner mechanism; safe no-op when the lock is held; documented
  operational behavior for multi-instance deployment.
- **Estimated risk:** Medium.
- **Verification:** Concurrent-cycle test shows only one reconciler mutates state; the other
  yields without corrupting lifecycle.

### WP8 — Migration & Index Alignment
- **Purpose:** Idempotently backfill `incident_category` on existing `forest_events` and
  active `intelligence_events`, and re-key existing active events to canonical identity so
  the first post-deploy cycle does not mass-resolve/recreate them. Add/adjust indexes for
  segmented aggregation and canonical-identity dedup.
- **Dependencies:** WP1, WP4.
- **Deliverables:** Idempotent migration in the existing migration mechanism; index
  changes; documented rollback and recovery.
- **Estimated risk:** High (mutates live intelligence state once).
- **Verification:** Migration test — seed legacy `("anomaly", region)` events → migrate →
  run a cycle → assert history preserved, no spurious resolve/create; migration is
  re-runnable with no additional effect.

### WP9 — Documentation & ADR Status Updates
- **Purpose:** Update as-built docs to reflect that Phase 0 behaviors now match canonical;
  bump the architecture CHANGELOG note if warranted; mark superseded pre-v1.0 notes as
  resolved. No architecture redesign.
- **Dependencies:** All implementation WPs merged.
- **Deliverables:** Updated `docs/INTELLIGENCE_PIPELINE.md`, `docs/ARCHITECTURE.md`
  as-built notes; `docs/architecture/CHANGELOG.md` entry for Phase 0 completion (additive,
  non-normative).
- **Estimated risk:** Low.
- **Verification:** Docs review; links resolve; no canonical spec content altered beyond an
  additive changelog entry.

---

## 4. Dependency Graph

```
WP0 (baseline/oracle)
        │
        ▼
WP1 (identity + Detection contract)
        │
        ├────────────► WP2 (segmented baselines)
        │                     │
        │                     ├────────────► WP3 (detector + registry)
        │                     │                     │
        │                     │                     ▼
        │                     │              WP4 (reconciliation) ──► WP6 (read/write split) ──► WP7 (single reconciler)
        │                     │                     │
        │                     └────────────► WP5 (generalized aggregation)   [parallel with WP4/WP6]
        │                                            │
        └──────────────────────────────────────────► WP8 (migration + indexes)   [needs WP1 + WP4]
                                                                                   │
                                                                                   ▼
                                                                              WP9 (docs/ADR status)
```

- **Blocks everything:** WP0 then WP1. Nothing that changes behavior may start before WP1
  contracts exist and the WP0 oracle is frozen.
- **Critical path:** WP0 → WP1 → WP2 → WP3 → WP4 → WP6 → WP7 → (WP8) → WP9.
- **Parallelizable:** WP5 may run alongside WP4/WP6 once WP2 lands. WP8 index work can be
  drafted early but must merge after WP1 and WP4. Test authoring for each WP proceeds
  alongside its implementation.
- **Highest leverage / highest risk:** WP4 and WP8. Schedule them when the team has the
  most review capacity.

---

## 5. Migration Strategy

### Database migrations
- Executed through the existing migration mechanism at startup; no new migration
  infrastructure.
- Two idempotent operations:
  1. **Backfill** `incident_category` on `forest_events` and on active
     `intelligence_events` using existing mapping helpers; absent ⇒ `wildfire`.
  2. **Re-key alignment** of active `intelligence_events` so their stored identity matches
     the canonical `(incident_category, spatial_key)` used by the new reconcile.

### Backward compatibility
- The read model already defaults legacy events to `wildfire`; this behavior is preserved
  and made explicit (WP1).
- API response contracts remain additive: new fields may appear; no field is removed or
  renamed. Existing consumers continue to function.

### Legacy intelligence events
- Existing active wildfire events must retain `detection_count`, `trend`, history, and any
  linked investigations. The re-key step guarantees the first post-deploy cycle recognizes
  them as the same tracked situations rather than resolving and recreating them.

### Rollback strategy
- Migrations are idempotent and additive (they populate fields and align keys; they do not
  delete lifecycle data), so a code rollback to the prior release leaves the data readable
  by the old code path (which ignores the added `incident_category` for wildfire).
- Deploy behind a configuration switch where practical so reconciliation generalization can
  be disabled without redeploying, reverting to scheduler-only wildfire behavior.
- Keep a pre-migration backup/snapshot of `intelligence_events` per standard operational
  practice before the one-time re-key.

### Failure recovery
- If a cycle fails mid-run, the next cycle reconciles from current observations and
  converges (idempotency). No partial-write cleanup is required beyond normal cycle
  re-execution.
- The single-reconciler guarantee (WP7) prevents two processes from interleaving writes
  during recovery.

### Idempotency
- Migration re-runs produce no additional changes.
- Reconciliation is idempotent by contract (ADR-002): identical Detections + identical
  prior state ⇒ identical result.

---

## 6. Testing Strategy

- **Unit tests** — validate pure functions and contracts in isolation: identity and
  Detection envelope construction/validation, per-category threshold selection, segmented
  baseline shaping, anomaly scoring, escalation/trend/priority scoring (unchanged),
  reconciliation create/update/resolve keyed by canonical identity, generic aggregation
  merge. Purpose: prove each unit's correctness independent of I/O.
- **Integration tests** — validate a full pass through repositories and services on a test
  datastore: ingest → enrich → segment → detect → reconcile → aggregate → read. Purpose:
  prove the wired pipeline produces correct persisted state.
- **Regression tests** — assert Phase 0 does not change wildfire behavior: run the WP0
  oracle through the new pipeline and diff against frozen golden outputs. Purpose: guarantee
  behavioral equivalence for the existing domain.
- **Golden dataset tests** — the frozen WP0 fixtures with exact expected anomalies, event
  lifecycles, aggregation, and command-center snapshot. Purpose: a stable, human-reviewed
  oracle for determinism and equivalence.
- **Migration tests** — seed pre-v1.0 records (legacy `("anomaly", region)` events without
  `incident_category`), run migration + one cycle, assert history preserved and no spurious
  resolve/create; re-run migration and assert no further change. Purpose: prove the one-time
  data transition is safe and idempotent.
- **Performance tests** — measure segmented aggregation and a full reconcile cycle at
  representative and elevated cardinality (regions × categories) against current baselines.
  Purpose: confirm segmentation does not regress cycle time and indexes are effective.
- **Acceptance tests** — validate the Definition of Done criteria end-to-end: read
  endpoints perform no writes; scheduler owns reconciliation; two categories coexist in one
  region; adding a synthetic aggregator/category requires no engine edits. Purpose: confirm
  the phase objective is met.

Cross-cutting requirements: all engine tests are deterministic (single injected time
anchor, no wall-clock coupling, no randomness); concurrency test covers the
single-reconciler guarantee; a write-spy asserts read endpoints never write.

---

## 7. Risk Assessment

| # | Risk | Category | Probability | Impact | Mitigation |
|---|------|----------|-------------|--------|------------|
| R1 | Re-key migration mass-resolves/recreates existing wildfire events, destroying history and orphaning investigations | Migration | Medium | High | WP8 migration test as go/no-go gate; pre-migration snapshot; idempotent design; config switch for staged rollout |
| R2 | Reconciliation generalization silently changes wildfire scores/lifecycle | Technical | Medium | High | WP0 golden equivalence enforced on WP4; scoring functions left untouched; diff-based regression gate |
| R3 | Segmentation contaminates or shifts baselines vs. current | Technical | Medium | Medium | WP2 equivalence to golden anomalies; explicit cross-category isolation tests |
| R4 | Category special-casing leaks into consumers (aggregation, command center) | Architectural | Medium | Medium | WP5 generic merge; synthetic second-aggregator test; review against ADR-005 |
| R5 | Removing reconcile-from-read changes perceived data freshness for clients | Operational | High | Low | Document cycle-cadence freshness; optional explicit command; scheduler interval tuning |
| R6 | Concurrent reconcilers under multi-instance deploy corrupt lifecycle | Operational | Low | High | WP7 single-reconciler guarantee; concurrency test; document single-runner requirement |
| R7 | New indexes insufficient → cycle latency regression at higher cardinality | Technical | Medium | Medium | WP9 performance tests; index review; single-pass aggregation |
| R8 | Golden oracle captured incorrectly, masking regressions | Testing | Low | High | WP0 sign-off by reviewer; determinism check across repeated runs before freezing |
| R9 | Migration not idempotent → damage on redeploy/re-run | Migration | Low | High | Explicit idempotency test; guard conditions on backfill/re-key |
| R10 | Deployment ordering (code before migration or vice versa) causes transient mismatch | Deployment | Medium | Medium | Migration runs at startup before scheduler starts; config switch; documented deploy runbook |
| R11 | Scope creep into Phase 1 (spatial) or new detectors | Architectural | Medium | Medium | Scope section enforced at gate; only the existing detector generalized |

---

## 8. Implementation Sequence

The order minimizes regression risk by establishing an oracle first, changing contracts
before behavior, changing reads only after the write path is independently correct, and
performing the one-time migration last among code changes.

1. **WP0 — Characterization baseline.** Nothing changes behavior before an oracle exists to
   detect change.
2. **WP1 — Identity & Detection contracts.** Definitions must precede any code that
   produces or consumes them; no behavior change yet.
3. **WP2 — Segmented baselines.** Segmentation is a prerequisite for category-aware
   detection and must be proven equivalent for wildfire before detectors depend on it.
4. **WP3 — Detector + registry.** The existing rule becomes a detector emitting Detections;
   validated against the golden anomaly set so the input to reconciliation is proven before
   reconciliation changes.
5. **WP4 — Generalized reconciliation.** The highest-risk change, made only after its
   inputs (Detections) and its oracle are locked; scoring untouched; equivalence enforced.
6. **WP5 — Generalized aggregation.** Can land in parallel after WP2; sequenced here to
   keep the command center correct once multiple categories are representable.
7. **WP6 — Command–query separation.** Safe only after reconciliation is independently
   invocable (WP4); reads stop writing.
8. **WP7 — Single-reconciler guarantee.** After the write path and read/write split are
   correct, make the writer safe under concurrency.
9. **WP8 — Migration & indexes.** Performed last among behavioral changes so the target
   schema/identity is final; gated by the migration regression test.
10. **WP9 — Documentation & ADR status.** After all behavior is merged and verified.

---

## 9. Definition of Done

Phase 0 is complete only if **all** of the following hold:

1. **Behavioral equivalence:** For the WP0 wildfire-only golden dataset, post-Phase-0
   outputs (anomalies, active/resolved events with scores/escalation/trend/priority/
   detection_count, incident aggregation, command-center snapshot) are identical to the
   frozen oracle.
2. **Canonical identity:** Intelligence events are keyed and stored by
   `(incident_category, spatial_key)`; `event_type` is derived; `signal_type` is present as
   provenance.
3. **Segmentation:** Baselines/anomalies are computed per `(spatial_key, incident_category)`
   in a single pass; two categories in one region provably do not cross-contaminate.
4. **Detector contract:** The existing rule runs as a registered detector emitting the
   canonical Detection envelope; a second synthetic detector/category integrates with no
   changes to reconciliation.
5. **Reconciliation contract:** Reconciliation consumes Detections, is idempotent, emits a
   change-set, and remains the single writer of intelligence lifecycle.
6. **Generalized aggregation:** The cross-category rollup contains no category-specific
   extraction; a synthetic aggregator contributes without editing merge logic.
7. **Read/write separation:** No read endpoint performs writes (asserted by test);
   reconciliation runs in the scheduler and, if enabled, via one explicit authenticated
   command.
8. **Single-reconciler guarantee:** Concurrent cycles cannot both mutate state (verified).
9. **Migration:** Idempotent; the migration regression test passes as a gate; existing
   active events retain history and links.
10. **Test suite:** All categories in Section 6 present and green in CI; determinism
    verified.
11. **No scope leakage:** No new data source, no new domain, no Spatial Engine extraction,
    no new detector types, no new infrastructure.
12. **Documentation:** As-built docs updated; additive CHANGELOG entry recorded; no
    canonical spec or ADR redesigned.

---

## 10. Deliverables

- **Source code:** Canonical identity + Detection contract definitions; segmented baseline
  aggregation and anomaly analysis; detector abstraction, registry, and the wildfire
  baseline detector; generalized reconciliation with change-set; generalized aggregation
  registry; command–query separated read path and scheduler-owned reconciliation (plus
  optional explicit command); single-reconciler mechanism.
- **Tests:** Unit, integration, regression, golden dataset, migration, performance, and
  acceptance suites per Section 6, wired into CI.
- **Documentation:** Updated `docs/INTELLIGENCE_PIPELINE.md` and `docs/ARCHITECTURE.md`
  as-built notes; this Phase 0 spec retained under `docs/engineering/`.
- **Migrations:** The idempotent backfill + re-key migration in the existing migration
  mechanism, with a documented rollback/recovery runbook.
- **Configuration:** Per-category threshold configuration (wildfire values equal to current
  constants); a rollout switch for the reconciliation generalization; single-reconciler
  settings.
- **ADR updates:** No new ADRs and no ADR redesign. If a Phase 0 implementation choice
  needs recording (e.g. the single-reconciler mechanism detail), add a brief superseding
  note or a new ADR **only** if it records an implementation decision without altering
  existing decisions; otherwise none. An additive entry in
  `docs/architecture/CHANGELOG.md` marking Phase 0 delivered.

---

## 11. Engineering Gate Review

Before approving merge to `main`, a Principal Engineer verifies:

### Correctness
- Golden equivalence holds for the wildfire-only dataset (no behavioral drift).
- Two categories in one region coexist, score, and resolve independently.
- Reconciliation is idempotent; a repeated cycle on identical observations is a no-op.

### Architecture compliance
- Canonical identity `(incident_category, spatial_key)` is used everywhere lifecycle is
  keyed; no `event_type` literal remains as identity.
- Reconciliation contains no domain/category control-flow branching (ADR-002/INV-3).
- Detectors emit only the Detection envelope; reconciliation consumes only it (ADR-009).
- Reconciliation is the sole lifecycle writer; reads never write (ADR-011, INV-1, INV-6).
- Aggregation merge is generic (ADR-005, INV-10).
- No new infrastructure, patterns, or scope beyond Phase 0.

### Performance
- Segmented aggregation and full-cycle timings are within agreed bounds at representative
  and elevated cardinality; indexes demonstrably used.

### Regression
- Full regression/golden suite green; command-center and reports outputs unchanged for
  wildfire-only data.

### Maintainability
- Domain logic confined to detectors/taxonomy/config; engine remains domain-blind.
- Adding a category/detector/aggregator in a test requires no engine edits (demonstrated).

### Test coverage
- All Section 6 categories present, deterministic, and CI-enforced; the migration
  regression test is a required gate; a read-path write-spy is included.

### Documentation
- As-built docs reconciled with delivered behavior; superseded pre-v1.0 notes resolved;
  additive CHANGELOG entry present; rollback/recovery runbook included; no canonical
  spec or ADR redesigned.

**Gate outcome:** Approve merge only if every item above is satisfied. Any unmet item
blocks merge until remediated.
