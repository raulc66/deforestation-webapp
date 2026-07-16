# 04 — Detector Framework

## 1. Purpose

This document specifies the Detector Framework, the mechanism through which the
platform converts segmented observations into scored Detections consumed by the
Reconciliation Engine.

## 2. Position in the Pipeline

Detectors sit between segmented analytics and reconciliation:

```
Observations → Segmented Aggregation → Detector → Detection → Reconciliation Engine
```

Detectors are the only components in the intelligence pipeline that carry domain
knowledge about how a situation is recognized.

## 3. Detector Contract

A detector consumes segmented observations for one or more incident categories and
produces zero or more Detections.

A Detection is a normalized envelope containing:

- `spatial_key` — the location identity of the situation.
- `incident_category` — the kind of situation.
- `signal_type` — the detector class that produced the Detection.
- `severity` — the severity classification of the Detection.
- `score` — a normalized score in the range 0.0 to 1.0.
- `evidence` — the supporting values that justified the Detection.
- `detected_at` — the time anchor of the detection cycle.

The Detection envelope is the stable contract between detectors and the Reconciliation
Engine. Detectors shall emit only the Detection envelope. The Reconciliation Engine
shall consume only the Detection envelope.

## 4. Segmentation Strategy

The segmentation layer shall group observations by `(spatial_key, incident_category)`
in a single aggregation pass. Segmentation shall precede detection.

Observations of one incident category shall not contribute to the baseline of another
incident category. The platform shall not mix categories within a single baseline.

## 5. Detector Types

The framework supports multiple detector classes. Each detector class implements the
same contract and differs only in its evaluation logic.

- **Baseline deviation detectors** evaluate current activity against a historical
  baseline for count-driven categories.
- **Threshold detectors** evaluate measured values against configured limits for
  measurement-driven categories.
- **Change-detection detectors** evaluate deltas between observation periods.
- **Model-assisted detectors** wrap external or learned inference and emit its output
  as Detections.
- **External-signal detectors** convert normalized third-party signals into
  Detections.

## 6. Category-Specific Configuration

Detection thresholds and weights shall be configuration keyed by incident category and,
where required, by spatial key. Thresholds shall not be global constants shared across
categories.

Changing a threshold is a configuration change. It shall not require modification of
detector logic or the Reconciliation Engine.

## 7. Reusable Detection Pipeline

All detectors shall follow the same pipeline:

```
segment → evaluate → score → normalize to Detection → hand to Reconciliation Engine
```

Detectors shall differ only in the evaluation step. Segmentation, normalization, and
handoff shall be shared.

## 8. Determinism

Detectors shall be deterministic and free of input/output. All data access shall occur
in the segmented aggregation layer prior to detection. A detector shall produce
identical Detections given identical segmented inputs.

Model-assisted detectors shall confine inference to the production of Detections.
Inference shall not enter the scoring or lifecycle functions of the Reconciliation
Engine.

## 9. Registration

Detectors shall be added through registration in a detector registry. Adding a detector
shall not require modification of the Reconciliation Engine, the segmentation layer, or
any other detector.

## 10. Explainability

Every Detection shall carry the evidence that justified it. The evidence shall be
preserved through reconciliation onto the resulting Intelligence Event.
