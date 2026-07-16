# ADR-004 — Detector Framework

## Status

Accepted.

## Context

Anomaly detection was a single hard-coded rule applied to an un-segmented regional
count. This mixes incident categories into one baseline and prevents the addition of
new detection strategies for measurement-driven, change-driven, and model-assisted
domains. The platform requires a way to add detection strategies without altering
reconciliation.

## Decision

The platform shall provide a Detector Framework in which detectors consume segmented
observations and produce normalized Detections.

- Segmentation shall group observations by `(spatial_key, incident_category)` in a
  single pass and shall precede detection.
- Detectors shall implement a common contract and differ only in evaluation logic.
- Detection thresholds and weights shall be configuration keyed by incident category.
- Detectors shall be deterministic and free of input/output.
- Detectors shall be added through a detector registry.

Model-assisted detectors shall confine inference to the production of Detections.
Inference shall not enter reconciliation scoring or lifecycle functions.

## Alternatives Considered

- **Keep a single global anomaly rule.** Rejected because it cannot segment categories
  and cannot support other detection strategies.
- **Embed detection inside reconciliation.** Rejected because it couples detection to
  lifecycle and violates the single-responsibility of the Reconciliation Engine.
- **Global thresholds shared across categories.** Rejected because detection tuning for
  one category would govern unrelated categories.

## Consequences

- Baselines are segmented per category, preventing cross-category contamination.
- New detector types integrate by registration.
- Thresholds are tuned per category as configuration.
- Detections carry evidence that is preserved through reconciliation.

## Future Implications

- Threshold, change-detection, model-assisted, and external-signal detectors are added
  without engine changes.
- Detection strategies may evolve per domain independently.
- Explainability is preserved as detectors carry evidence.
