# 00 — Platform Vision

## 1. Purpose

This document defines the canonical vision of the ForestWatch platform. It is the
top-level normative reference from which all subsequent architecture documents and
Architecture Decision Records derive their authority.

## 2. Platform Definition

ForestWatch is an Environmental Intelligence Platform. The platform shall transform
high-volume environmental observations into a small, stable, and actionable set of
tracked situations across multiple ecosystem domains.

The platform shall not be defined as a wildfire monitoring application. Wildfire is
one domain among many. The platform shall treat every ecosystem domain as a
first-class participant in a single, shared intelligence pipeline.

## 3. Ecosystem Domains

The platform recognizes the following ecosystem domains:

- Forest Health
- Wildlife
- Human Activity
- Environmental Conditions
- Ecosystem Health

Each domain shall be onboarded through the same extension mechanisms. No domain shall
receive a private pipeline, a private reconciliation path, or private intelligence
logic.

## 4. Core Thesis

The platform shall observe, derive, and act:

1. **Observe.** External and internal sources produce observations.
2. **Derive.** The Intelligence Engine reconciles observations into tracked situations.
3. **Act.** Humans respond to tracked situations through investigations, and the
   platform communicates them through notifications, reports, and the Command Center.

Every domain shall express itself within this thesis. No domain shall bypass it.

## 5. System Boundaries

The platform consists of the following bounded contexts:

- **Ingestion** — acquisition and normalization of observations from external and
  internal sources.
- **Spatial** — geospatial indexing, membership resolution, and enrichment.
- **Intelligence** — anomaly detection, reconciliation, scoring, and lifecycle
  management of tracked situations.
- **Investigation** — human workflow and response to tracked situations.
- **Reporting** — composition and export of point-in-time artifacts.
- **Command Center** — live operational projection of platform state.

Each bounded context shall interact with other contexts through defined service
boundaries. No context shall access the persistence of another context directly.

## 6. Architectural Layering

The platform shall maintain the following layered structure:

```
Routes → Services → Repositories → Datastore
```

- Routes expose the platform over HTTP and perform no business logic.
- Services contain domain logic and shall remain domain-independent where they
  operate on the shared intelligence pipeline.
- Repositories are the sole components that access the datastore.
- The datastore persists observations, tracked situations, and operational records.

## 7. Non-Negotiable Platform Guarantees

The platform shall guarantee the following at all times:

1. Observations are immutable once ingested.
2. Intelligence is derived, never authored.
3. Intelligence lifecycle is owned by a single reconciliation authority.
4. Analytics and scoring are deterministic.
5. New domains are added by extension and configuration, never by modification of
   engine internals.
6. Geospatial computation exists in exactly one engine.

## 8. Evolution Mandate

The platform is expected to evolve for a minimum of five to ten years. All design
decisions shall preserve the ability to add new domains, new sources, new detectors,
and new spatial datasets without redesigning the Intelligence Engine.

## 9. Document Authority

The documents in `docs/architecture/` are normative. Where implementation and these
documents disagree, the implementation shall be brought into conformance with these
documents. Deviations shall be recorded as Architecture Decision Records.
