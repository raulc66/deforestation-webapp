# ADR-006 — Intelligence Lifecycle

## Status

Accepted.

## Context

A tracked situation evolves over time. It appears, persists, escalates, improves, and
eventually ends. The platform requires a defined lifecycle so that situations are
represented consistently across cycles and across domains, and so that downstream
consumers interpret state uniformly.

## Decision

An Intelligence Event shall follow a defined lifecycle owned by the Reconciliation
Engine.

- An event is created when a Detection appears for an identity with no active event.
- An event is updated when a Detection appears for an identity with an active event.
  Update increments `detection_count`, records `previous_score`, and recomputes derived
  dynamics.
- An event is resolved when its identity is absent from the current Detection set,
  unless a configured suppression policy specifies otherwise.

Derived dynamics shall be computed by shared, pure functions:

- `escalation_level` from detection count and severity.
- `trend` from the change between previous and current score.
- `priority_score` from severity, escalation, trend, and current score.

Temporal bounds shall be recorded through `first_detected_at` and `last_detected_at`.
The lifecycle shall be identical across all domains.

## Alternatives Considered

- **Immutable events per detection.** Rejected because it prevents continuity of a
  tracked situation.
- **Manual resolution only.** Rejected because active state would drift from reality
  when a situation ends.
- **Domain-specific lifecycle rules.** Rejected because it violates domain independence
  and duplicates lifecycle logic.

## Consequences

- Situations retain history across cycles.
- Resolution is automatic and complete unless explicitly suppressed.
- Derived dynamics are consistent and deterministic across domains.
- Investigations annotate lifecycle state without owning it.

## Future Implications

- Suppression and sticky-state policies may be added without changing lifecycle
  ownership.
- Lifecycle transitions may be emitted as domain events for additional consumers.
- Cross-domain correlation may consume lifecycle transitions.
