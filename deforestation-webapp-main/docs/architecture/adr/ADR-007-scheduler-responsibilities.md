# ADR-007 — Scheduler Responsibilities

## Status

Accepted.

## Context

The platform executes a recurring pipeline that ingests observations, enriches them,
detects situations, reconciles intelligence, snapshots derived state, dispatches
notifications, and generates scheduled reports. The orchestration of these steps must
be defined so that business logic does not accumulate inside the scheduler and so that
concurrency is controlled.

## Decision

The scheduler is responsible for sequencing pipeline steps and for nothing else. The
scheduler shall own no business logic. Each pipeline step shall reside in its owning
service and shall be independently invocable and testable without the scheduler.

The scheduler is responsible for:

- Invoking ingestion providers.
- Invoking spatial enrichment as part of observation persistence.
- Invoking detection and reconciliation.
- Invoking derived-state snapshots.
- Invoking notification dispatch over the reconciliation change-set.
- Invoking scheduled report generation.
- Recording ingestion run records.

Reconciliation shall be invoked only by the scheduler or by an explicit, authenticated
command operation. Exactly one reconciliation execution shall occur at a time. Where
the platform runs across multiple instances, a single-runner guarantee shall be
enforced before reconciliation is permitted in more than one process.

## Alternatives Considered

- **Business logic embedded in the scheduler.** Rejected because it prevents
  independent testing and couples orchestration to domain logic.
- **Reconciliation triggered by read traffic.** Rejected because it violates
  command–query separation and creates uncontrolled concurrency.
- **Multiple concurrent reconcilers without coordination.** Rejected because it
  produces write contention on intelligence lifecycle state.

## Consequences

- Pipeline steps are testable in isolation.
- The scheduler remains a thin orchestrator.
- Reconciliation concurrency is controlled.
- Best-effort steps may fail independently without aborting the cycle.

## Future Implications

- A single-runner guarantee enables horizontal scaling of the application.
- Step cadence may vary per step without changing orchestration structure.
- Steps may be relocated to separate services if bounded contexts are extracted.
