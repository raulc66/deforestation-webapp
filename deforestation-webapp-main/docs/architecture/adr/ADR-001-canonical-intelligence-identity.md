# ADR-001 — Canonical Intelligence Identity

## Status

Accepted.

## Context

An Intelligence Event represents a tracked situation that persists across detection
cycles. The engine must recognize the same situation on every cycle and must never
conflate two distinct situations. The prior implementation identified events by
`(event_type, region)` with `event_type` fixed to a single literal value. This
representation cannot distinguish two situations of different kinds occurring in the
same location, and it couples identity to a detector artifact.

## Decision

An Intelligence Event shall be uniquely identified by `(incident_category,
spatial_key)`. The ecosystem domain shall be derivable from the incident category.
Where multi-tenant operation is enabled, identity shall extend to `(tenant,
incident_category, spatial_key)`.

`event_type` shall be a derived label. `signal_type` shall be provenance. Severity,
escalation level, trend, priority score, current score, and detection count are mutable
state and shall never form part of identity.

The `spatial_key` is an abstraction. An administrative region is one implementation.
Grid cells and feature identifiers are permitted implementations.

## Alternatives Considered

- **Retain `(event_type, region)`.** Rejected because it cannot represent multiple
  incident categories in a single location and encodes a detector artifact as identity.
- **Include severity or escalation in identity.** Rejected because these are mutable
  states that change between cycles and would fragment a single situation into many.
- **Use a per-detection surrogate key.** Rejected because it would prevent continuity
  of a tracked situation across cycles.

## Consequences

- The Reconciliation Engine keys active events by `(incident_category, spatial_key)`.
- Multiple incident categories may coexist in the same location without collision.
- Existing records require an idempotent migration to populate identity components.
- Detectors must supply the incident category on every Detection.

## Future Implications

- Finer spatial keys may be adopted per domain without changing the identity concept.
- Multi-tenant isolation may be enabled by extending identity with a tenant dimension.
- Cross-domain correlation may operate over stable identities.
