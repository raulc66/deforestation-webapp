# Architecture Changelog

This changelog versions the ForestWatch architecture independently from the source code.
It records architectural evolution — engines, contracts, invariants, and decisions — and
does not record application features.

Versioning follows semantic architecture versioning:

- **MAJOR** — a breaking architectural decision that changes an invariant, a canonical
  contract, or a dependency rule.
- **MINOR** — an additive architectural capability that does not break existing
  invariants or contracts.
- **PATCH** — a clarification or non-normative refinement that changes no invariant,
  contract, or rule.

---

## Architecture v1.0

**Version:** 1.0.0

**Date:** 2026-07-15

**Status:** Frozen.

### Summary

The inaugural frozen architecture of ForestWatch as a multi-domain Environmental
Intelligence Platform. This version establishes the canonical Intelligence Engine, the
reconciliation contract, the Spatial Engine, the Detector Framework, the domain plug-in
architecture, the read-only projection subsystems, the system context, and the
dependency rules. It defines the architectural invariants and the Architecture Decision
Records that govern all future implementation.

### Added Documents

- `00-platform-vision.md` — Platform vision, ecosystem domains, bounded contexts,
  layering, and non-negotiable guarantees.
- `01-architecture-principles.md` — Architectural invariants (INV-1 through INV-16) and
  design discipline.
- `02-intelligence-engine.md` — Canonical data model, intelligence identity, lifecycle
  state, and engine guarantees.
- `03-reconciliation-engine.md` — Reconciliation contract: inputs, outputs, guarantees,
  and invariants.
- `04-detector-framework.md` — Segmentation strategy, detector contract, detector types,
  and category configuration.
- `05-spatial-engine.md` — Reusable spatial index, polygon and overlay providers, and
  the enrichment pipeline.
- `06-domain-plugin-architecture.md` — Domain onboarding through extension points.
- `07-reporting-and-command-center.md` — Read-only projection subsystems.
- `08-roadmap.md` — Phased evolution and future domains.
- `09-system-context.md` — High-level system overview and system diagram.
- `10-dependency-rules.md` — Architectural dependency law.

### Added ADRs

- ADR-001 — Canonical Intelligence Identity.
- ADR-002 — Reconciliation Contract.
- ADR-003 — Spatial Engine.
- ADR-004 — Detector Framework.
- ADR-005 — Domain Plug-in Architecture.
- ADR-006 — Intelligence Lifecycle.
- ADR-007 — Scheduler Responsibilities.
- ADR-008 — Intelligence Event Model.
- ADR-009 — Detection Contract.
- ADR-010 — Multi-Tenancy Strategy.
- ADR-011 — Read/Write Separation.

### Established Capabilities

- Canonical Intelligence Engine.
- Reconciliation Contract.
- Spatial Engine.
- Detector Framework.
- Domain Plug-in Architecture.
- Read-only Reporting and Command Center.
- Architectural dependency law.
- ADR-001 through ADR-011.

### Breaking Architectural Decisions

As the inaugural frozen version, v1.0 defines the baseline against which future breaking
changes are measured. Relative to the pre-1.0 platform, the following decisions are
breaking with respect to prior structure and are established as binding:

- Canonical intelligence identity is `(incident_category, spatial_key)`. Identity keyed
  by `event_type` and region alone is superseded (ADR-001).
- Reconciliation operates over the canonical Detection envelope rather than
  domain-specific inputs (ADR-002, ADR-009).
- Reconciliation is a write operation. Read endpoints never reconcile (ADR-011).
- Geometry computation is consolidated into a single Spatial Engine (ADR-003).
- Domains are added by extension only; modifying engine internals to add a domain is
  prohibited (ADR-005).

### Notes

- The `tenant` identity dimension is reserved and intentionally unimplemented (ADR-010).

---

## Future Planned Versions

The following versions are planned. Scope is indicative and non-binding until released.

### Architecture v1.1 (planned, MINOR)

- Detection contract versioning guidance (additive).
- In-process domain events derived from the reconciliation change-set.
- Pipeline observability and stage-level metrics as an architectural concern.

### Architecture v1.2 (planned, MINOR)

- Finer spatial-key strategies for point and linear phenomena.
- Additional spatial datasets as polygon and overlay providers.
- Suppression and sticky-state lifecycle policies.

### Architecture v2.0 (planned, MAJOR)

- Activation of the reserved `tenant` identity dimension and multi-tenant isolation
  (supersedes the single-tenant assumption of ADR-010).
- Cross-domain correlation layer over Intelligence Events.
- Bounded-context extraction where operationally justified.
