# ForestWatch — Project State

Living project execution status. For canonical architecture, see `docs/architecture/`.
For as-built implementation detail, see the other documents under `docs/`.

**Distribution posture:** ForestWatch is packaged for **commercial source-code licensing**.
See `docs/packaging/` and `docs/getting-started/`. Documents under `docs/business/` are
historical hosted-SaaS strategy drafts and are **not** the current definition of what this
source package is sold as. Architecture and ADRs remain technical authority.

The milestone table below retains earlier Phase 0 tracking text. It is not a claim that
the intelligence pipeline is unfinished; the engine, demo, trial, and Command Center are
implemented. Prefer `docs/engineering/IMPLEMENTATION_LOG.md` for completed packages.
The commercially licensed source-code artifact is **v1.0.0**. That is a source zip
for licensees, not a hosted ForestWatch SaaS.

---

## Executive Summary

ForestWatch has completed Architecture v1.0: the platform vision, architectural
invariants, intelligence engine contracts, ADRs, and Phase 0 engineering planning are
frozen and documented. The codebase implements a mature wildfire intelligence pipeline
with reporting, investigations, and a command center UI. **Phase 0 — Engine Generalization**
implementation is in progress. No hosted SaaS production service has been shipped.

---

## Current Architecture Status

| Area | Status |
|------|--------|
| Architecture (`docs/architecture/00`–`10`, CHANGELOG) | Completed |
| Architecture Principles | Completed |
| ADRs (`docs/architecture/adr/ADR-001`–`ADR-011`) | Completed |
| Engineering Specifications (`docs/engineering/PHASE-0-ENGINE-GENERALIZATION.md`) | Completed |
| Implementation Backlog (`docs/engineering/PHASE-0-IMPLEMENTATION-BACKLOG.md`) | Completed |
| Implementation Protocol (`docs/engineering/IMPLEMENTATION_PROTOCOL.md`) | Frozen |

---

## Current Milestone

| Field | Value |
|-------|-------|
| **Current Phase** | Phase 0 — Engine Generalization |
| **Current Work Package** | WP0 — Characterization Baseline & Golden Dataset |
| **Current Task** | WP0.2 — Capture golden outputs |
| **Last Completed Task** | WP0.1 — Define the frozen seed fixture (approved; validation complete) |
| **Current Objective** | Generalize the intelligence engine to canonical v1.0 contracts without onboarding any new domain or data source, preserving wildfire behavior |

---

## Implementation Progress

| Phase | Name | Status |
|-------|------|--------|
| Phase 0 | Engine Generalization | In Progress (WP0.1 complete) |
| Phase 1 | Generic Spatial Engine | Not Started |
| Phase 2 | First Human Activity Domain | Not Started |
| Phase 3 | Surface Layer | Not Started |

WP0.1 (frozen seed fixture) is complete per `docs/engineering/IMPLEMENTATION_LOG.md`.
WP0.2 (capture golden outputs) is next.

---

## Architecture Freeze Status

| Artifact | State |
|----------|-------|
| Architecture documents (`docs/architecture/`) | Frozen (v1.0) |
| ADRs | Frozen |
| Engineering specifications | Frozen |

Changes to frozen artifacts require an Architecture Decision Record and a version bump
per `docs/architecture/CHANGELOG.md`.

---

## Current Risks

- Reconciliation identity re-keying may corrupt existing wildfire intelligence event
  history if migration is incorrect (Phase 0, WP8).
- Segmented baselines may shift wildfire anomaly scores if equivalence is not proven
  against a golden oracle (Phase 0, WP0/WP2).
- Removing reconcile-on-read changes data freshness semantics for API consumers
  (Phase 0, WP6).
- Concurrent reconciliation under multi-instance deployment without a single-reconciler
  guarantee (Phase 0, WP7).

---

## Outstanding Decisions

These are intentionally deferred architectural decisions, not open problems:

- **Multi-tenancy** — `tenant` identity dimension reserved; implementation deferred until
  first multi-organization deployment (ADR-010).
- **Finer spatial keys** — grid cells and feature identifiers as alternatives to
  administrative region; deferred until a domain requires them.
- **Global spatial indexing** — multi-country bounds and high-resolution polygon storage;
  deferred beyond Phase 1.
- **Cross-domain correlation engine** — layer over Intelligence Events for correlated
  multi-domain situations; deferred as a future platform layer.
- **Suppression and sticky-state policies** — reconciliation contract accommodates them;
  not implemented in Phase 0.

---

## Next Milestone

**M1 — Oracle Frozen (WP0):** Complete WP0 (fixture, golden capture, determinism harness,
sign-off) to freeze the wildfire regression oracle before any engine changes. WP0.1 is
complete; WP0.2 and WP0.3 remain.

---

## Repository Health

| Metric | Status |
|--------|--------|
| Backend unit / integration tests | Present (46 test modules under `backend/tests/`) |
| Frontend component tests | Present (15 test files under `frontend/src/`) |
| CI pipeline | Not configured in repository (no `.github/` workflows) |
| Last verified date | 2026-07-16 (WP0.1 fixture tests, 22 passed) |

---

## Last Updated

2026-07-17
