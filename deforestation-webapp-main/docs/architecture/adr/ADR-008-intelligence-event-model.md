# ADR-008 — Intelligence Event Model

## Status

Accepted.

## Context

The Intelligence Event is the central persistent entity of the platform and the stable
contract on which all downstream consumers depend for five to ten years. Its structure
must be domain-independent, must carry identity, lifecycle state, dynamics, and
provenance, and must remain stable as domains, sources, and detectors are added.

## Decision

The Intelligence Event model shall be domain-independent and shall carry the following.

Identity:

- `incident_category` — the kind of situation and segmentation dimension.
- `spatial_key` — the location identity of the situation.
- `tenant` — present where multi-tenant operation is enabled.

Lifecycle state:

- `status` — `active` or `resolved`.
- `first_detected_at`, `last_detected_at` — temporal bounds.
- `detection_count` — number of detecting cycles.

Dynamics:

- `severity`, `escalation_level`, `trend`, `priority_score`, `current_score`,
  `previous_score`.

Provenance and evidence:

- `signal_type` — the detector class that produced the event.
- `metadata` — evidence supporting the assertion.

Derived label:

- `event_type` — a derived label and never an identity component.

The read model shall tolerate legacy records by applying deterministic defaults for
absent fields.

## Alternatives Considered

- **Domain-specific event models.** Rejected because it fragments the contract and
  duplicates consumers.
- **Identity embedded in mutable state fields.** Rejected because mutable state cannot
  serve as a stable identity.
- **Discarding provenance after reconciliation.** Rejected because explainability
  requires retained evidence and signal type.

## Consequences

- All domains share a single Intelligence Event structure.
- Consumers depend on one stable contract.
- Legacy records remain readable through deterministic defaults.
- Provenance and evidence support explainability.

## Future Implications

- Additional dynamics or provenance fields may be added additively.
- The tenant dimension supports multi-tenant isolation.
- The model supports cross-domain correlation over a uniform structure.
