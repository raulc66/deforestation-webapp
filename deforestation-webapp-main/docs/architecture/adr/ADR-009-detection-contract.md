# ADR-009 — Detection Contract

## Status

Accepted.

## Context

The Intelligence Engine must accept inputs from many detectors across many domains,
sources, and detection strategies. If each detector produced a differently shaped
input, the Reconciliation Engine would require knowledge of every detector and would be
modified whenever a detector is added. The platform requires a single, stable contract
between detection and reconciliation so that detection strategies can evolve without
altering the engine.

## Decision

Every detector shall produce the canonical Detection envelope before reconciliation.
The Detection envelope shall carry:

- `spatial_key` — the location identity of the candidate situation.
- `incident_category` — the kind of candidate situation.
- `signal_type` — the detector class that produced the Detection.
- `severity` — the severity classification of the Detection.
- `score` — a normalized score in the range 0.0 to 1.0.
- `evidence` — the supporting values that justified the Detection.
- `detected_at` — the time anchor of the detection cycle.

The Detection envelope shall be the sole input shape consumed by the Reconciliation
Engine. Detectors shall emit only this envelope. The Reconciliation Engine shall consume
only this envelope. The envelope defines the boundary between domain-specific detection
and domain-independent reconciliation.

The Detection envelope is the stable contract of the Intelligence Engine because it
decouples how a situation is recognized from how a situation is tracked. Detection
strategy is expected to vary and expand over the life of the platform. Reconciliation
lifecycle is expected to remain stable. Placing a normalized contract between them
allows detection to change freely while reconciliation remains unchanged.

This ADR does not define implementation details of the envelope.

## Alternatives Considered

- **Detector-specific input shapes.** Rejected because the Reconciliation Engine would
  depend on every detector and would require modification for each new detector.
- **Passing raw observations directly into reconciliation.** Rejected because it would
  place detection logic inside the engine and violate domain independence.
- **A shared mutable structure evolving per detector.** Rejected because an unstable
  contract would propagate breakage to reconciliation and to every detector.

## Consequences

- Detectors normalize to a single envelope before reconciliation.
- Adding a detector requires no change to the Reconciliation Engine.
- Reconciliation remains domain-independent because it consumes a uniform contract.
- Evidence and provenance are carried on every Detection and preserved through
  reconciliation.

## Future Implications

- Threshold, change-detection, model-assisted, and external-signal detectors integrate
  through the same contract.
- The contract may be versioned additively without breaking existing detectors.
- The stable contract enables independent evolution of detection strategies over the
  life of the platform.
