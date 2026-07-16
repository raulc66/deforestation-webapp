# ADR-011 — Read/Write Separation

## Status

Accepted.

## Context

Reconciliation creates, updates, and resolves Intelligence Events. It is therefore a
write operation. If reconciliation is triggered by read traffic, every query mutates
persistent state, concurrent queries contend for the same records, and results become
non-deterministic and non-cacheable. The platform requires an explicit separation
between operations that read intelligence state and operations that mutate it.

## Decision

Reconciliation shall be a write operation subject to the following rules.

- The scheduler owns reconciliation. Reconciliation shall be invoked by the scheduler.
- GET endpoints shall never reconcile. Read endpoints shall return previously
  reconciled state.
- Queries shall be read-only. A query shall not mutate persistent state.
- Only explicit commands may mutate intelligence state. Where reconciliation must be
  triggered outside the scheduler, it shall occur through an explicit, authenticated
  command operation.

This separation preserves the following properties:

- **Determinism.** Intelligence state changes only during controlled reconciliation
  cycles, so state transitions are reproducible and are not a side effect of read
  traffic.
- **Scalability.** Read endpoints carry no write contention, so query-serving instances
  scale horizontally without racing on intelligence lifecycle state, and reconciliation
  runs under a single-runner guarantee.
- **Caching.** Read endpoints are free of side effects, so their responses may be cached
  and retried safely.
- **CQRS.** Commands that mutate intelligence state are separated from queries that read
  it, giving each a distinct and predictable contract.

## Alternatives Considered

- **Reconcile on read.** Rejected because it makes every query a write, introduces
  contention, and defeats determinism and caching.
- **Reconcile on both read and schedule.** Rejected because uncontrolled concurrency
  between read-triggered and scheduled reconciliation corrupts lifecycle state.
- **Allow any service to trigger reconciliation.** Rejected because it violates the
  single-authority and single-runner guarantees.

## Consequences

- Read endpoints return the most recently reconciled state and do not mutate it.
- Reconciliation occurs in controlled cycles owned by the scheduler.
- Explicit command operations are the only non-scheduler path to mutate intelligence
  state.
- Freshness of read state is a function of the scheduler cycle.

## Future Implications

- Read endpoints may adopt caching without risk of side effects.
- Query-serving instances may scale horizontally under the single-reconciler guarantee.
- The change-set produced by reconciliation may feed additional read models without
  altering read/write separation.
