# ADR-010 — Multi-Tenancy Strategy

## Status

Accepted.

## Context

The platform is expected to pursue commercial deployment across multiple organizations
over its lifetime. Multi-tenancy is a strategic capability that, if retrofitted late,
imposes a costly migration across identity, persistence, indexing, and access control.
At the same time, the current platform serves a single operational scope, and building
tenant isolation before it is required would add complexity without present benefit.

This ADR records the architectural decision regarding multi-tenancy. It does not
implement multi-tenancy.

## Decision

The platform shall reserve `tenant` as an identity dimension and shall not implement
tenant isolation at this time.

Current architecture assumptions:

- The platform operates within a single tenant scope.
- Data is not partitioned by tenant.
- Access control operates within a single organizational scope.

The tenant dimension is intentionally reserved in the canonical intelligence identity.
Where multi-tenant operation is enabled, identity extends from
`(incident_category, spatial_key)` to `(tenant, incident_category, spatial_key)`. This
reservation is a design provision, not an implementation.

Tenant support shall be introduced when the platform onboards its first deployment that
requires isolation between distinct organizations, or when regulatory or contractual
obligations require partitioned data and access control.

Implementing multi-tenancy now would be premature because there is no tenant boundary
to enforce, no second organization to isolate, and no requirement that partitioning
satisfies. Premature implementation would add persistence partitioning, tenant-scoped
indexing, and tenant-aware access control that carry cost and risk without present
value.

## Alternatives Considered

- **Implement full multi-tenancy now.** Rejected because there is no present tenant
  boundary; the cost and complexity would not be justified.
- **Ignore multi-tenancy entirely.** Rejected because a late retrofit across identity
  and persistence is expensive; reserving the identity dimension preserves the option at
  negligible cost.
- **Introduce tenancy only at the access-control layer.** Rejected because isolation
  must extend to identity and persistence to be correct; a partial approach would create
  a false sense of isolation.

## Consequences

- The canonical identity reserves a tenant dimension that is currently unused.
- No tenant partitioning exists in persistence or indexing at this time.
- The platform retains a low-cost path to multi-tenancy without present complexity.
- A future decision to enable tenancy extends identity rather than redefining it.

## Future Implications

- Tenant isolation may be enabled by activating the reserved identity dimension and
  introducing tenant-scoped persistence and access control.
- Tenant-scoped authorization may be layered onto the existing access model.
- The reservation preserves backward compatibility for existing single-tenant records.
