# 00 — Platform Vision

## 1. Purpose

This document defines the canonical vision of the ForestWatch platform. It is the
top-level normative reference from which all subsequent architecture documents and
Architecture Decision Records derive their authority.

## 2. Platform Definition

### 2.1 Commercial product identity

ForestWatch is delivered commercially as a **Forest Intelligence Platform**. The product
understands, monitors, investigates, explains, and reports changes affecting **forest
ecosystems**. Commercial scope, user segments, and product modules are defined in
`docs/business/BUSINESS_STRATEGY.md` and `docs/business/PRODUCT_STRATEGY.md`.

The product shall not be defined as a wildfire monitoring application, a deforestation-only
tool, or a generic environmental monitoring platform. Wildfire is one forest incident
category among many.

### 2.2 Implementation architecture

The Forest Intelligence Platform is built on a **domain-independent intelligence engine** —
an implementation architecture that transforms high-volume observations into a small,
stable, and actionable set of tracked situations across multiple incident categories
through a single shared pipeline. The engine is category-independent by design: forest
incident semantics live in taxonomy, detectors, providers, and configuration, not in
engine internals.

This document specifies the implementation architecture and its invariants. It describes
engine capability, not permission to expand commercial product scope beyond forest
ecosystems. Domains outside the forest vertical may be technically extensible through the
engine; they are not ForestWatch product scope unless approved through business and product
strategy review.

The platform shall not be defined as a single-category alert tool. Every forest incident
category supported by the product shall be a first-class participant in the shared
intelligence pipeline.

## 3. Ecosystem Domains

Within the Forest Intelligence Platform, the architecture recognizes the following
**ecosystem domain groupings** — taxonomy dimensions that organize forest incident
categories:

- Forest Health
- Wildlife
- Human Activity
- Environmental Conditions
- Ecosystem Health

Each grouping shall be onboarded through the same extension mechanisms. No grouping shall
receive a private pipeline, a private reconciliation path, or private intelligence
logic.

These groupings describe **forest ecosystem intelligence**, not permission to expand the
commercial product into unrelated environmental verticals (e.g. air quality, marine
environments, general water management). Categories outside the forest ecosystem may be
engine-extensible per `docs/architecture/08-roadmap.md` §8; they are not ForestWatch
product scope unless approved through business and product strategy review.

## 4. Core Thesis

The platform shall observe, derive, and act:

1. **Observe.** External and internal sources produce observations.
2. **Derive.** The Intelligence Engine reconciles observations into tracked situations.
3. **Act.** Humans respond to tracked situations through investigations, and the
   platform communicates them through notifications, reports, and the Command Center.

Every forest incident category shall express itself within this thesis. No category shall
bypass it.

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
5. New forest incident categories are added by extension and configuration, never by
   modification of engine internals.
6. Geospatial computation exists in exactly one engine.

## 8. Evolution Mandate

The implementation architecture is expected to evolve for a minimum of five to ten years.
All design decisions shall preserve the ability to add new forest incident categories,
new sources, new detectors, and new spatial datasets without redesigning the Intelligence
Engine. Engine extensibility beyond the forest vertical is permitted at the architecture
level; commercial product scope remains forest ecosystems unless explicitly expanded
through business and product strategy review.

## 9. Document Authority

The documents in `docs/architecture/` are normative. Where implementation and these
documents disagree, the implementation shall be brought into conformance with these
documents. Deviations shall be recorded as Architecture Decision Records.
