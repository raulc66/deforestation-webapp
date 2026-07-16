# ADR-002 — Reconciliation Contract

## Status

Accepted.

## Context

The platform must support multiple incident categories, multiple ecosystem domains,
multiple observation sources, and multiple detector types. The reconciliation logic
must not be rewritten each time a new category, domain, source, or detector is added.
The prior reconciliation logic operated over anomaly-shaped inputs specific to a single
domain.

## Decision

The Reconciliation Engine shall operate over a normalized Detection envelope. The
Detection envelope contains `spatial_key`, `incident_category`, `signal_type`,
`severity`, `score`, `evidence`, and `detected_at`.

The Reconciliation Engine shall:

- Accept Detections, a single time anchor, and the current active event set.
- Create, update, or resolve Intelligence Events keyed by canonical identity.
- Emit a change-set describing lifecycle transitions.

The Reconciliation Engine shall not branch on domain or incident category as control
flow. It shall not perform detection, source access, or geospatial computation. It
shall be idempotent and deterministic. It shall be invoked only by the scheduler or by
an explicit, authenticated command operation.

## Alternatives Considered

- **Domain-specific reconciliation paths.** Rejected because it duplicates lifecycle
  logic and violates the single-authority invariant.
- **Reconciliation triggered by read endpoints.** Rejected because it violates
  command–query separation and produces write contention.
- **Per-detection database queries during reconciliation.** Rejected because it
  produces query amplification; a single batched read is required.

## Consequences

- Detectors normalize to a shared envelope before reconciliation.
- Adding a domain, source, or detector adds inputs and requires no reconciliation
  change.
- Notifications and audit consume the change-set rather than re-deriving transitions.
- Reads return previously reconciled state.

## Future Implications

- New detector types integrate without reconciliation changes.
- The change-set may be modeled as in-process domain events for additional consumers.
- Suppression policies may be introduced without altering the core contract.
