# 03 — Reconciliation Engine

## 1. Purpose

This document specifies the Reconciliation Engine, the single authority for the
lifecycle of Intelligence Events.

## 2. Authority

The Reconciliation Engine owns the creation, update, and resolution of Intelligence
Events. No other component shall write Intelligence Event lifecycle state.

The Reconciliation Engine operates over Detections. It does not perform anomaly
detection, does not access external sources, and does not compute geospatial
membership.

## 3. Contract

### 3.1 Inputs
The Reconciliation Engine consumes:

- A set of Detections for the current cycle. Each Detection is a normalized envelope
  containing: `spatial_key`, `incident_category`, `signal_type`, `severity`, `score`,
  `evidence`, and `detected_at`.
- A single time anchor representing the current cycle time.
- The current set of active Intelligence Events, loaded once per cycle.

The Reconciliation Engine shall not distinguish which detector, source, or domain
produced a Detection.

### 3.2 Outputs
The Reconciliation Engine produces:

- A reconciled set of Intelligence Events reflecting created, updated, and resolved
  situations.
- A change-set describing what was created, escalated, de-escalated, and resolved
  during the cycle.

### 3.3 Processing
For each cycle, the Reconciliation Engine shall:

1. Load all active Intelligence Events once.
2. Index active events by canonical identity `(incident_category, spatial_key)`.
3. For each Detection:
   - If no active event exists for the identity, create a new Intelligence Event and
     initialize lifecycle state.
   - If an active event exists for the identity, update it, increment
     `detection_count`, recompute derived dynamics, and record `previous_score`.
4. Resolve every active event whose identity is absent from the current Detection set,
   unless a configured suppression policy specifies otherwise.

The Reconciliation Engine shall perform a single batched read of active events and
shall avoid per-detection query amplification.

## 4. Guarantees

The Reconciliation Engine guarantees:

1. **Idempotency.** Identical Detections and identical prior state yield identical
   results.
2. **No collision.** Each canonical identity maps to at most one active Intelligence
   Event.
3. **Continuity.** An existing situation is updated and its history preserved; it is
   never duplicated.
4. **Completeness of resolution.** Active events absent from the current Detection set
   are resolved unless explicitly suppressed.
5. **Determinism.** All scoring and lifecycle transitions are computed by pure
   functions with no input/output.
6. **Provenance preservation.** `signal_type` and evidence are retained on every
   Intelligence Event.

## 5. Invariants

1. The Reconciliation Engine is the single write authority for Intelligence Event
   lifecycle.
2. The Reconciliation Engine shall never branch on domain or incident category as
   control flow. Category and domain are data flowing through the engine.
3. Canonical identity is `(incident_category, spatial_key)`. Mutable state shall never
   be used as identity.
4. Scoring functions shall be pure and shared across all domains.
5. Reconciliation shall be invoked only by the scheduler or by an explicit,
   authenticated command operation. Query endpoints shall not invoke reconciliation.

## 6. Scoring

The Reconciliation Engine applies shared, pure scoring functions to compute:

- `escalation_level` — derived from detection count and severity.
- `trend` — derived from the change between `previous_score` and `current_score`.
- `priority_score` — derived from severity, escalation, trend, and current score.

Scoring functions shall be identical across all domains. Domain-specific nuance shall
enter the engine through Detection inputs, not through scoring forks.

## 7. Change-Set

The Reconciliation Engine shall emit a change-set as a first-class output. The
change-set shall enumerate transitions occurring during the cycle. Notifications,
audit, and other consumers shall consume the change-set rather than re-deriving
transitions.

## 8. Extension Behavior

Adding a domain, a source, or a detector type adds Detections to the input set. It
shall not require modification of the Reconciliation Engine. The Reconciliation Engine
is closed for modification with respect to domain onboarding.
