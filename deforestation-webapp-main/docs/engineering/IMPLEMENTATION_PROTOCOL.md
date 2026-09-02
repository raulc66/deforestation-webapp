# Implementation Protocol

**Status:** Frozen.
**Audience:** All engineers and implementation agents executing work on ForestWatch after
Architecture v1.0.
**Authority:** This protocol governs *how* engineering work is performed. It is subordinate
to the frozen architecture in `docs/architecture/`, its ADRs, and the phase specifications
and backlogs under `docs/engineering/`. Where this protocol and those authorities disagree,
the architecture and its ADRs govern. This document is not architecture and does not create
architectural decisions.

**Language:** The key words **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**,
**SHOULD NOT**, **MAY**, and **OPTIONAL** in this document are to be interpreted as
described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## 1. Purpose

### 1.1 Why this protocol exists

ForestWatch has completed its architecture phase. Architecture v1.0, its ADRs, and the Phase 0
engineering specifications are frozen. This protocol exists to ensure that all subsequent
implementation work:

- conforms to the frozen architecture without drift;
- remains verifiable, deterministic, and reversible;
- produces a complete, auditable record of what was done and why;
- stops at the correct boundaries when blockers or contradictions appear.

Without a normative execution protocol, implementation agents and engineers may introduce
implicit design decisions, skip verification, modify frozen documents, or proceed past
architectural blockers. This protocol prevents those failures.

### 1.2 Scope

This protocol applies to:

- all implementation work under the architectural roadmap (`docs/architecture/08-roadmap.md`);
- all work packages and tasks defined in phase specifications and implementation backlogs
  under `docs/engineering/`;
- all code, test, migration, configuration, and as-built documentation changes made in
  service of that roadmap;
- all engineering agents (human or automated) performing that work.

This protocol does **not** apply to:

- changes to frozen architecture documents or ADRs (those require the ADR and architecture
  versioning process defined in `docs/architecture/CHANGELOG.md`);
- product-only feature work that does not touch architectural contracts, unless such work
  would violate an architectural invariant or dependency rule;
- operational runbooks, deployment scripts, or infrastructure provisioning outside the
  application codebase, unless they affect deterministic behavior of the intelligence
  pipeline.

### 1.3 Relationship to the architecture documents

The document hierarchy is:

| Layer | Location | Role |
|-------|----------|------|
| Architecture | `docs/architecture/`, `docs/architecture/adr/` | Defines *what* the platform is and *what invariants must hold*. Frozen. |
| Engineering specifications | `docs/engineering/PHASE-*-*.md`, backlogs | Defines *how* a phase is executed. Frozen per phase. |
| This protocol | `docs/engineering/IMPLEMENTATION_PROTOCOL.md` | Defines *how work is performed* across all phases. |
| Implementation log | `docs/engineering/IMPLEMENTATION_LOG.md` | Records *what was done*. Append-only. |
| Living status | `docs/PROJECT_STATE.md`, changelogs, release notes | Records *current project state*. Living. |
| As-built guides | `docs/ARCHITECTURE.md`, `docs/INTELLIGENCE_PIPELINE.md`, etc. | Describes *what is running*. Living; reconciled to canonical architecture. |

Implementation **MUST NOT** reinterpret, extend, or override architecture documents. When
implementation reveals that an ADR or invariant is objectively incorrect, work **MUST**
stop and the contradiction **MUST** be reported. It **MUST NOT** be worked around silently.

---

## 2. Engineering Principles

The following principles govern all implementation work. They derive from
`docs/architecture/01-architecture-principles.md` and the Phase 0 specification.

### 2.1 Correctness over speed

Implementation **SHALL** prefer the smallest correct change that satisfies the specification.
Speed **MUST NOT** justify skipping verification, omitting tests, or accepting behavioral
drift. A work package that passes tests but violates an invariant **MUST NOT** be considered
complete.

### 2.2 Architecture before implementation

Every work package **MUST** be traceable to a frozen specification and, where applicable, to
one or more ADRs. Implementation agents **MUST** read the relevant specifications before
writing code. Undocumented design decisions **MUST NOT** be introduced during implementation.

### 2.3 Small, reversible changes

Changes **SHALL** be scoped to the current task or work package. Unrelated refactors,
drive-by fixes, and speculative features **MUST NOT** be included. Each work package **SHALL**
leave the repository in a working state so that a revert of the work package is possible
without orphaning dependent state.

### 2.4 Deterministic behavior

The intelligence pipeline and all engine tests **MUST** be deterministic. Given identical
inputs and an identical injected time anchor, outputs **MUST** be identical across runs.
Implementation **MUST NOT** introduce randomness, wall-clock coupling, or non-deterministic
ordering into the engine path or its regression oracles. This requirement is binding per
INV-4 in `docs/architecture/01-architecture-principles.md`.

### 2.5 Continuous verification

Verification **MUST** occur at task level, work-package level, and phase level as defined in
Section 6. Implementation **MUST NOT** proceed past a failed required verification step.
Every completed task **MUST** leave all previously passing tests passing unless a test is
explicitly superseded by a specification change approved through the architecture process.

### 2.6 No architectural drift

Implementation **MUST NOT** modify frozen architecture documents, **MUST NOT** introduce
architectural patterns not specified in the frozen documents, and **MUST NOT** expand scope
beyond the current phase specification. Extension **SHALL** occur through the registration
and plug-in mechanisms defined in the architecture, not by editing engine internals.

---

## 3. Work Package Workflow

Every work package **MUST** follow this mandatory sequence. Steps **MUST NOT** be skipped
or reordered except where a stop condition (Section 4) halts progress.

```
Read specifications
        ↓
Review dependencies
        ↓
Implement (all tasks in the work package)
        ↓
Run affected tests
        ↓
Run work-package verification
        ↓
Update implementation log
        ↓
Commit
        ↓
Stop for review
```

### 3.1 Read specifications

Before any implementation in a work package, the agent **MUST** read and understand:

- the relevant sections of `docs/architecture/` and applicable ADRs;
- the phase specification (e.g. `docs/engineering/PHASE-0-ENGINE-GENERALIZATION.md`);
- the implementation backlog tasks for the current work package;
- any prior implementation log entries for dependent work packages.

The agent **MUST NOT** begin implementation if specifications for the work package are
missing, ambiguous in a way that requires a new design decision, or contradictory with the
architecture.

### 3.2 Review dependencies

The agent **MUST** confirm that all dependency work packages are complete and verified.
The agent **MUST** identify affected files, expected repository changes, and required tests
before writing code. Work **MUST NOT** begin on a work package whose dependencies are
unmet.

### 3.3 Implement

The agent **SHALL** implement all tasks in the work package according to the backlog.
Tasks **MAY** be executed sequentially within the work package without stopping for review
between individual tasks, subject to the autonomy rules in Section 5.

The agent **MUST NOT** implement tasks belonging to a different work package in the same
change set unless the backlog explicitly groups them.

### 3.4 Run affected tests

After implementation, the agent **MUST** run all tests affected by the changes. At minimum,
this includes new or updated tests for the current work package and all tests in modules
directly touched by the change.

### 3.5 Run work-package verification

The agent **MUST** execute the verification criteria defined in the backlog for every task
in the work package and any work-package-level acceptance criteria defined in the phase
specification. Work-package verification **MUST** pass before the work package is
considered complete.

### 3.6 Update implementation log

The agent **MUST** append one or more entries to `docs/engineering/IMPLEMENTATION_LOG.md`
documenting the completed work package. See Section 11.

### 3.7 Commit

The agent **MUST** commit all changes for the work package in a clean repository state.
See Section 8.

### 3.8 Stop for review

The agent **MUST** stop after work-package completion and await review before beginning the
next work package, unless explicit standing approval has been granted for continuous
execution across multiple work packages within the same phase.

Stop for review also **MUST** occur when any stop condition in Section 4 is triggered,
regardless of work-package progress.

---

## 4. Stop Conditions

Implementation **MUST** stop immediately when any of the following conditions is true.
The agent **MUST** report the condition, **MUST NOT** work around it, and **MUST NOT**
proceed to the next task or work package until the condition is resolved through the
correct process.

### 4.1 Architectural contradiction discovered

An implementation step reveals that a frozen architecture document, ADR, or invariant is
inconsistent with observable system behavior or with another frozen document in a way that
cannot be resolved by following the existing specification literally.

### 4.2 ADR modification required

Implementing the specified behavior would require changing an accepted ADR, or the
implementation cannot proceed without a decision that belongs in an ADR.

### 4.3 Blocker prevents deterministic implementation

A dependency, environment constraint, or data condition prevents deterministic
implementation or verification. Examples include: inability to inject a time anchor,
non-reproducible test output, or missing test infrastructure required by the backlog.

### 4.4 New architectural decision required

The specification does not cover a design choice that materially affects architecture,
contracts, invariants, or cross-module behavior. The agent **MUST NOT** make such
decisions unilaterally.

### 4.5 Tests reveal unexpected behavior

Required verification fails, or tests reveal behavior that differs from the specification
or golden oracle in a way not accounted for by the current task. The agent **MUST NOT**
silently update golden outputs to match broken behavior.

### 4.6 Implementation would violate frozen specifications

The requested or implied change would violate phase scope, architectural invariants,
dependency rules, or explicit exclusions in the phase specification.

When stopped, the agent **SHALL** document the stop condition in the implementation log if
any work was completed, and **SHALL** leave the repository in a working state with all
previously passing tests still passing.

---

## 5. Autonomy Rules

### 5.1 Within a work package

An implementation agent **MAY** continue automatically through all tasks in a single work
package without stopping for review between tasks, provided that **all** of the following
hold:

- no architecture change is required;
- no new design decision is introduced;
- no stop condition in Section 4 is triggered;
- all required tests continue to pass after each task;
- no blocker exists.

The agent **MUST NOT** stop after every individual task unless a stop condition applies or
review is explicitly requested.

### 5.2 Between work packages

The agent **MUST** stop at work-package boundaries and await review before beginning the
next work package, unless standing approval for continuous phase execution has been granted.

### 5.3 Mandatory stops regardless of autonomy

The agent **MUST** stop regardless of work-package progress when:

- any stop condition in Section 4 is triggered;
- work-package verification fails;
- a phase-level gate is reached (see Section 12);
- an architectural or engineering gate review is required by the phase specification.

---

## 6. Testing Policy

Three verification levels apply. Higher levels **MUST** pass before a phase is declared
complete. Failure at any required level **MUST** block further implementation in the
affected scope until remediated.

### 6.1 Task-level verification

After each task, the agent **MUST** run tests directly affected by the change. This includes:

- new or updated unit tests required by the backlog for that task;
- existing tests in modules modified by the task;
- any task-specific verification criteria stated in the backlog.

Task-level verification **MUST** pass before proceeding to the next task within the work
package.

### 6.2 Work-package-level verification

After all tasks in a work package are complete, the agent **MUST** run all tests relevant to
the subsystem or subsystems touched by the work package. This includes:

- the full test module(s) for the affected subsystem;
- regression tests that depend on outputs of prior work packages in the same phase;
- integration tests required by the backlog for that work package.

Work-package-level verification **MUST** pass before the work package is committed and
logged.

### 6.3 Phase-level verification

Before a phase is declared complete, the agent **MUST** run the full test suite applicable
to the phase, including:

- all unit, integration, regression, golden-dataset, migration, performance, and acceptance
  tests defined in the phase specification;
- the phase engineering gate review checklist;
- regression comparison against the frozen phase oracle where applicable.

Known pre-existing collection or environment failures **MUST** be documented and **MUST
NOT** be silently ignored if they affect subsystems modified by the phase. Phase-level
verification **MUST** pass before the phase milestone is recorded as complete.

### 6.4 Failure policy

If required verification at any level fails, implementation **MUST NOT** continue in the
affected scope until the failure is remediated or the specification is formally amended
through the architecture process. Updating a golden oracle to match unintended behavior
**MUST NOT** be used as a remediation strategy.

---

## 7. Documentation Policy

Documents fall into three modification classes.

### 7.1 Frozen documents

These documents **MUST NOT** be modified during implementation except through the formal
architecture versioning process (new ADR, architecture version bump per
`docs/architecture/CHANGELOG.md`):

| Document | Modification rule |
|----------|-------------------|
| `docs/architecture/*.md` (all numbered architecture documents) | Frozen. No implementation-driven edits. |
| `docs/architecture/adr/*.md` (ADR-001 through ADR-011) | Frozen. Amendments require a new ADR or a formal supersession record. |
| `docs/engineering/PHASE-*-ENGINE-GENERALIZATION.md` | Frozen per phase. Defines scope and acceptance for that phase. |
| `docs/engineering/PHASE-*-IMPLEMENTATION-BACKLOG.md` | Frozen per phase. Task definitions **MUST NOT** be reinterpreted or altered during execution. |
| `docs/engineering/IMPLEMENTATION_PROTOCOL.md` | Frozen. Amendments require explicit engineering review. |

### 7.2 Append-only documents

These documents **MAY** receive new entries. Existing entries **MUST NOT** be overwritten,
deleted, or rewritten.

| Document | Modification rule |
|----------|-------------------|
| `docs/architecture/CHANGELOG.md` | Append-only. New architecture version entries only through the architecture process. Phase completion **MAY** add a non-normative delivery note as specified in the phase spec (e.g. Phase 0 WP9). |
| `docs/CHANGELOG.md` | Append-only. Project-level notable changes per Keep a Changelog format. |
| `docs/engineering/IMPLEMENTATION_LOG.md` | Append-only. One entry per completed task or work package. See Section 11. |

### 7.3 Living documents

These documents **MAY** be updated to reflect current project state. They **MUST NOT**
contradict frozen architecture. They **MUST NOT** restate architectural concepts that
belong in `docs/architecture/`; they **SHOULD** reference canonical sources instead.

| Document | Modification rule |
|----------|-------------------|
| `docs/PROJECT_STATE.md` | Living. Updated at phase and work-package boundaries to reflect current phase, work package, task, risks, and progress. |
| `docs/RELEASE_NOTES.md` | Living. Updated when user-visible releases occur or when planned release scope changes. |
| `docs/ARCHITECTURE.md` | Living as-built map. Updated when implementation aligns to or diverges from canonical architecture. **MUST** reference, not duplicate, canonical docs. |
| `docs/INTELLIGENCE_PIPELINE.md` | Living as-built guide. Updated when pipeline behavior changes. |
| `docs/EXTENDING_FORESTWATCH.md` | Living extension guide. Updated when extension points change. |
| `docs/ROADMAP.md` | Living product roadmap. Feature delivery tracking. Architectural phase ordering **MUST** defer to `docs/architecture/08-roadmap.md`. |

Implementation **MUST** update living documents when a phase specification or work package
explicitly requires it (e.g. Phase 0 WP9). Implementation **SHOULD** update
`docs/PROJECT_STATE.md` at each work-package boundary.

---

## 8. Git Policy

### 8.1 Commit frequency

- Each completed work package **MUST** end with at least one commit containing all changes
  for that work package.
- A work package **MAY** produce multiple commits if logically separable (e.g. implementation
  commit followed by a documentation-only commit), but **MUST NOT** leave uncommitted work
  at a work-package boundary.
- Partial work packages **MUST NOT** be committed unless the repository remains in a working
  state and the partial progress is explicitly logged.

### 8.2 Commit message style

Commit messages **SHOULD**:

- use imperative mood (e.g. "Add segmented baseline aggregation");
- state the *why* in the subject line, not merely the *what*;
- reference the work package and phase where applicable (e.g. "Phase 0 WP2: segment baseline
  aggregation by incident category");
- be concise (one or two sentences in the subject; optional body for verification notes).

Commit messages **MUST NOT** include secrets, credentials, or environment-specific values.

### 8.3 Milestone tags

Engineering milestone completion **MAY** be marked with an annotated git tag using the
form:

```
phase-<N>-complete
```

Example: `phase-0-complete`. Tags **SHOULD** be applied only after phase-level verification
(Section 6.3) and engineering gate review pass. Tags represent engineering completion gates,
not marketing releases.

### 8.4 Branch expectations

- Implementation work **SHOULD** occur on a feature branch per phase or per major work
  package, merged to the main integration branch after review.
- The main integration branch **MUST** remain in a working state at all times.
- Force-push to the main integration branch **MUST NOT** be performed without explicit
  authorization.

### 8.5 Clean repository state

Every work package **MUST** end with:

- all intended changes committed;
- all required tests passing;
- no unresolved TODO comments introduced by the work package;
- no unintended modifications to unrelated files;
- implementation log updated.

---

## 9. Definition of Done

A **task** is complete only when **all** of the following hold:

1. Implementation is finished per the backlog task description.
2. All required tests for the task pass.
3. Task-level verification (Section 6.1) passes.
4. Required documentation updates, if any, are complete.
5. An entry is appended to `docs/engineering/IMPLEMENTATION_LOG.md`.
6. No TODO comments remain from the task.
7. No architectural invariant is violated.
8. The repository is in a working state.

A **work package** is complete only when **all** of the following hold:

1. Every task in the work package meets the task Definition of Done.
2. Work-package-level verification (Section 6.2) passes.
3. Changes are committed per Section 8.
4. `docs/PROJECT_STATE.md` is updated if the work package changes current phase, work
   package, task, or risk status.
5. The agent stops for review per Section 3.8.

A **phase** is complete only when **all** of the following hold:

1. Every work package in the phase meets the work package Definition of Done.
2. Phase-level verification (Section 6.3) passes.
3. The phase engineering gate review checklist in the phase specification is satisfied.
4. Living and append-only documentation updates required by the phase specification are
   complete.

---

## 10. Regression Policy

### 10.1 Phase 0 oracle immutability

The Phase 0 golden dataset and its captured outputs constitute the Phase 0 regression
oracle. Once frozen (WP0.3 sign-off), the oracle **MUST NOT** be modified to accommodate
implementation changes.

### 10.2 New oracle versions

Any intentional behavioral change to the wildfire domain or to engine outputs that the
oracle covers **MUST** produce a new oracle version. A new oracle version **MUST** be
reviewed and signed off with the same rigor as the original. The prior oracle version
**MUST** remain available for historical comparison.

### 10.3 No overwriting historical oracles

Historical oracle fixtures and golden artifacts **MUST NOT** be overwritten, deleted, or
edited in place. New versions **MUST** be added alongside prior versions with an explicit
version identifier.

### 10.4 Mandatory regression before phase completion

Regression testing against the frozen phase oracle **MUST** pass before any phase is
declared complete. For Phase 0, behavioral equivalence with the WP0 oracle is a hard gate
per the Phase 0 Definition of Done.

---

## 11. Engineering Journal

`docs/engineering/IMPLEMENTATION_LOG.md` is the permanent, cumulative record of
implementation work.

### 11.1 Maintenance rules

- Entries **MUST** be appended. Existing entries **MUST NOT** be modified or deleted.
- Each entry **MUST** be self-contained and auditable.
- Entries **SHOULD** be concise. Verbose narrative **SHOULD** be avoided unless needed to
  explain a stop condition or a non-obvious verification result.

### 11.2 Required entry fields

Each entry **MUST** include:

| Field | Requirement |
|-------|-------------|
| Date | ISO 8601 date of completion. |
| Work Package | Work package identifier and name (e.g. WP0 — Characterization Baseline). |
| Summary | One to three sentences: what was done and the outcome. Task ID **SHOULD** be included when a single task is logged. |
| Files changed | Lists of modified and created files. "None" if applicable. |
| Tests executed | Commands run and pass/fail counts. |
| Outcome | Complete, stopped (with reason), or blocked. |

Extended fields (objective, verification detail, notes/follow-up) **MAY** be included and
**SHOULD** be included when logging stop conditions or validation addenda.

### 11.3 When to write entries

- An entry **MUST** be appended for each completed task or work package.
- A stop condition **MUST** be logged even if no task was completed.
- Validation or review addenda **MAY** be appended as separate entries.

---

## 12. Milestone Policy

Engineering milestones represent **completion gates** — points at which a defined body of
work is verified complete against frozen specifications. They **MUST NOT** be confused
with marketing releases or product roadmap phases.

### 12.1 Milestone sequence

The engineering milestones corresponding to the architectural roadmap are:

```
Phase 0 Complete — Engine Generalization
        ↓
Generic Intelligence Engine aligned to Architecture v1.0
        ↓
Phase 1 Complete — Spatial Engine Generalization
        ↓
Phase 2 Complete — First Human Activity Domain (Forest Loss)
        ↓
Phase 3 Complete — Surface Layer (map, filters, Command Center activation)
        ↓
Platform v1.0 Engineering Complete
```

Each milestone **MUST** satisfy:

- all work packages in the phase are complete per Section 9;
- phase-level verification passes per Section 6.3;
- the engineering gate review for the phase is approved;
- `docs/PROJECT_STATE.md` reflects the milestone completion.

### 12.2 Relationship to releases

Engineering milestone completion **MAY** coincide with a user-visible release but **MUST
NOT** be assumed to do so automatically. User-visible releases are tracked in
`docs/RELEASE_NOTES.md`. A marketing release **MAY** ship before or after an engineering
milestone depending on product decisions.

### 12.3 Milestone naming

Milestone names **SHOULD** align with `docs/architecture/08-roadmap.md` phase names.
Product roadmap items in `docs/ROADMAP.md` **MUST NOT** redefine architectural phase
ordering or scope.

---

## 13. Non-Goals

The following are explicitly prohibited during implementation unless formally approved
through the architecture versioning process:

- **Premature microservices** — splitting the monolith into independently deployed services
  without an ADR and architecture version bump.
- **Event sourcing** — persisting intelligence state as an immutable event stream instead
  of the reconciliation model defined in ADR-002.
- **Kafka, message brokers, or external job queues** — introducing broker-based
  communication or orchestration not specified in Architecture v1.0.
- **Unnecessary abstractions** — frameworks, patterns, or indirection layers not required
  by the current phase specification.
- **Speculative optimization** — performance work not driven by a measured regression or
  a phase specification requirement.
- **Architecture changes outside the ADR process** — any modification to invariants,
  contracts, dependency rules, or frozen documents without a new ADR and architecture
  version entry.
- **Scope leakage** — implementing work belonging to a future phase (e.g. onboarding a new
  domain during Phase 0, extracting the Spatial Engine during Phase 0).
- **CQRS beyond read/write separation** — the read/write split defined in ADR-011 is in
  scope; a full event-sourced CQRS architecture is not.

---

## 14. Final Engineering Invariants

The following rules are permanent and **MUST** be obeyed by every future implementation.
They summarize and operationalize `docs/architecture/01-architecture-principles.md` and
`docs/architecture/10-dependency-rules.md`.

1. **Architecture drives implementation.** Frozen documents define the target. Code follows
   them; code **MUST NOT** redefine them.

2. **Implementation never modifies frozen architecture documents.** Changes require the ADR
   and architecture versioning process.

3. **Every change must be testable.** Untested behavior **MUST NOT** be merged. Tests
   **MUST** be deterministic.

4. **Every work package is independently verifiable.** Each work package **MUST** have
   measurable completion criteria and **MUST** leave the repository working.

5. **Determinism is mandatory.** Identical inputs and time anchor produce identical outputs.
   No randomness, no wall-clock coupling in the engine path.

6. **Simplicity is preferred over unnecessary abstraction.** The smallest correct
   implementation **SHALL** be chosen.

7. **Extension is preferred over modification.** New domains, detectors, aggregators, report
   sections, and notification channels **MUST** be added through registration, not by
   editing engine loops.

8. **Technical debt must never be introduced knowingly.** Known shortcuts **MUST** be
   logged as stop conditions or explicit follow-ups, not silently merged.

9. **Single reconciliation authority.** Only the Reconciliation Engine writes intelligence
   lifecycle state (INV-1, ADR-002).

10. **Command–query separation.** Read endpoints **MUST NOT** mutate state (INV-6,
    ADR-011).

11. **Repositories own persistence.** No direct datastore access outside repositories
    (INV-7, `docs/architecture/10-dependency-rules.md`).

12. **The Phase 0 oracle is immutable.** Regression gates **MUST NOT** be weakened by
    editing frozen golden outputs.

---

## 15. Contradictions Report

This section records contradictions discovered during protocol authoring. Resolved items
are retained for auditability. Open items **MUST** be treated as active until closed.

### 15.1 Resolved

#### C-1 — Project state vs implementation log *(resolved 2026-07-17)*

**Was:** `docs/PROJECT_STATE.md` stated implementation had not started while
`docs/engineering/IMPLEMENTATION_LOG.md` recorded WP0.1 complete.

**Resolution:** `docs/PROJECT_STATE.md` updated to reflect Phase 0 in progress, WP0.1
complete, WP0.2 as current task.

#### C-2 — Product roadmap phase numbering vs architectural phase numbering *(resolved 2026-07-17)*

**Was:** Both `docs/ROADMAP.md` and `docs/architecture/08-roadmap.md` used "Phase N"
with different meanings (Delivery Phases 1–9 vs Architecture Phases 0–3).

**Resolution:** `docs/ROADMAP.md` renamed sections to **Delivery Phase** and added an
explicit terminology table. Implementers **MUST** use Architecture Phase numbers from
`docs/architecture/08-roadmap.md` for engineering work.

#### C-3 — Release version 1.0.0 timing *(resolved 2026-07-17)*

**Was:** `docs/RELEASE_NOTES.md` planned Version 1.0.0 at Phase 0 completion; this
protocol placed Platform v1.0 after Phase 3.

**Resolution:** `docs/RELEASE_NOTES.md` updated. Version 1.0.0 is planned at Architecture
Phase 3 (Surface Layer) completion. Phase 0–2 completions are engineering milestones only
unless product leadership scopes a separate pre-release.

#### C-4 — Product roadmap infrastructure vs architecture non-goals *(resolved 2026-07-17)*

**Was:** `docs/ROADMAP.md` Delivery Phase 6 listed "arq + Redis worker" without an ADR,
conflicting with Architecture v1.0 prohibition on new broker infrastructure.

**Resolution:** `docs/ROADMAP.md` updated. External job queues (arq + Redis) are marked
architecture-gated and require an ADR and architecture version bump. In-process alternatives
remain the default path until approved.

### 15.2 Open

The following contradictions remain documented. Implementation **MUST NOT** interpret
them as resolved.

#### C-5 — CI pipeline absence

`docs/PROJECT_STATE.md` records that no CI pipeline is configured in the repository. This
protocol requires phase-level and work-package-level verification but does not define who
enforces it in the absence of CI. Verification **MUST** still be performed and logged
manually until CI is configured.

#### C-6 — Architecture CHANGELOG updates on phase completion

Phase 0 WP9 specifies an additive entry in `docs/architecture/CHANGELOG.md` marking Phase 0
delivered. Architecture CHANGELOG entries are normally tied to architecture version bumps.
The exact status of a "Phase 0 delivered" note (non-normative delivery marker vs. version
increment) **SHOULD** be confirmed at the Phase 0 gate review.

---

## 16. Document Control

| Field | Value |
|-------|-------|
| Created | 2026-07-17 |
| Frozen | 2026-07-17 |
| Status | **Frozen** |
| Supersedes | Informal implementation instructions in conversation and ad-hoc agent prompts |
| Related documents | `docs/architecture/`, `docs/engineering/PHASE-0-*`, `docs/engineering/IMPLEMENTATION_LOG.md` |

This document is frozen per Section 7.1. Amendments require explicit engineering review
and **MUST NOT** alter architectural authority.

---

*End of Implementation Protocol.*
