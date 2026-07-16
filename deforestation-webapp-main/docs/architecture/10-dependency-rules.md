# 10 — Dependency Rules

## 1. Purpose

This document defines the architectural dependency rules of ForestWatch. These rules are
the architectural law of the platform. They exist to prevent architecture erosion. All
current and future development MUST comply. A change that violates a rule in this
document is a regression regardless of test outcome.

## 2. Canonical Dependency Direction

The platform MUST observe the following dependency direction:

```
Routes → Services → Repositories → MongoDB
```

- Routes MUST depend only on Services.
- Services MUST depend only on Repositories and other Services within permitted
  boundaries.
- Repositories MUST depend only on the datastore driver.
- Dependencies MUST NOT flow in the reverse direction.

## 3. Allowed Dependencies

- Routes MAY depend on Services.
- Services MAY depend on Repositories.
- Services MAY depend on other Services where the dependency does not cross into a
  forbidden direction and does not create a cycle.
- Repositories MAY depend on the datastore driver.
- Providers MAY depend on Services and Repositories to persist normalized observations.
- The Scheduler MAY depend on Services, Providers, and the Reconciliation Engine.
- Reporting MAY depend on read-only Services and Repositories.
- Notifications MAY depend on the reconciliation change-set and read-only Services.

## 4. Forbidden Dependencies

- Services MUST NOT call Routes.
- Repositories MUST NOT call Services.
- Repositories MUST NOT call Routes.
- Providers MUST NOT write directly to MongoDB.
- Routes MUST NOT access MongoDB directly.
- Reports MUST NOT modify state.
- The Command Center MUST NOT modify state.
- Downstream consumers MUST NOT mutate upstream state.
- No component other than a Repository MUST access the datastore directly.
- Cross-module access to another module's Repository MUST NOT occur; modules MUST
  communicate through Services.

## 5. Layer Responsibilities

### 5.1 Route Responsibilities
- Routes MUST expose the platform over its transport interface.
- Routes MUST perform authentication and authorization delegation.
- Routes MUST NOT contain business logic.
- Routes MUST NOT access persistence directly.
- Routes MUST NOT trigger reconciliation on read operations.

### 5.2 Service Responsibilities
- Services MUST contain domain logic.
- Services that operate on the shared intelligence pipeline MUST remain
  domain-independent.
- Services MUST depend on Repositories for persistence.
- Services MUST NOT call Routes.
- Services MUST NOT access the datastore directly.

### 5.3 Repository Responsibilities
- Repositories MUST be the only components that access the datastore.
- Repositories MUST return domain-shaped data free of datastore-specific types.
- Repositories MUST NOT contain business logic.
- Repositories MUST NOT call Services or Routes.
- Each collection MUST be owned by exactly one repository boundary.

## 6. Ownership Rules

- Forest Events MUST be owned by the ingestion and forest-event boundary.
- Intelligence Events MUST be owned by the Reconciliation Engine for lifecycle writes.
- Spatial datasets and geometry MUST be owned by the Spatial Engine.
- Each datastore collection MUST have a single owning repository.
- No component MUST write to a collection it does not own.

## 7. Cross-Module Communication Rules

- Modules MUST communicate through Service boundaries.
- A module MUST NOT access another module's Repository.
- A module MUST NOT access another module's persistence directly.
- Shared vocabulary MUST be expressed through the shared taxonomy kernel.
- Cross-module dependencies MUST NOT form cycles.

## 8. Scheduler Responsibilities

- The Scheduler MUST orchestrate pipeline steps only.
- The Scheduler MUST NOT contain business logic.
- The Scheduler MUST invoke each pipeline step through its owning Service.
- The Scheduler MUST enforce that reconciliation runs under a single-runner guarantee.
- The Scheduler MUST allow best-effort steps to fail independently without aborting the
  cycle.

## 9. Provider Responsibilities

- Providers MUST acquire observations from external or internal sources.
- Providers MUST normalize external data to canonical models at the boundary.
- Providers MUST act as anti-corruption adapters.
- Providers MUST NOT write directly to MongoDB.
- Providers MUST persist normalized observations only through Services or Repositories
  within the permitted dependency direction.
- External schemas MUST NOT propagate beyond providers.

## 10. Report Responsibilities

- Reports MUST compose artifacts from read-only projections.
- Reports MUST NOT modify state.
- Reports MUST NOT invoke reconciliation.
- Report sections MUST be added through registration.
- The failure of one report section MUST NOT prevent composition of the remainder.

## 11. Notification Responsibilities

- Notifications MUST derive from the reconciliation change-set and from investigation
  lifecycle transitions.
- Notifications MUST NOT modify intelligence lifecycle state.
- Notification channels MUST be added through registration.
- Notifications MUST NOT invoke reconciliation.

## 12. Intelligence Lifecycle Rule

- The Reconciliation Engine MUST be the only writer of Intelligence Event lifecycle
  state.
- No other component MUST create, update, or resolve Intelligence Events.
- Reconciliation MUST be invoked only by the Scheduler or by an explicit, authenticated
  command operation.
- Read operations MUST NOT invoke reconciliation.

## 13. Command Center Rule

- The Command Center MUST be read-only.
- The Command Center MUST consume generalized aggregation and read-only projections.
- The Command Center MUST NOT compute or mutate intelligence.

## 14. Enforcement

- Compliance MUST be verified through automated tests, code review, and architectural
  review.
- A violation MUST block release until remediated.
- A rule MUST NOT be waived except through an Architecture Decision Record that formally
  amends this document.
