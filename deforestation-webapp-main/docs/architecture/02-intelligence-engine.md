# 02 — Intelligence Engine

## 1. Purpose

This document specifies the ForestWatch Intelligence Engine: its responsibilities, its
canonical data model, the identity of an Intelligence Event, and the guarantees it
provides.

## 2. Definitions

### 2.1 Observation
An observation is a single detection produced by a source. In the current platform,
observations are persisted as Forest Events. Observations are immutable, high-volume,
and meaningful only in aggregate.

### 2.2 Intelligence Event
An Intelligence Event is a persistent, stateful assertion that an operationally
significant situation exists in a place, of a kind, at a level of concern. It is the
unit that humans act upon.

## 3. Responsibilities

The Intelligence Engine is responsible for:

1. Segmenting observations by incident category and spatial key.
2. Producing scored detections through detectors.
3. Reconciling detections into Intelligence Events.
4. Maintaining the lifecycle, scoring, and history of Intelligence Events.
5. Exposing Intelligence Events as read-only projections to downstream consumers.

The Intelligence Engine is not responsible for acquiring observations, computing
geospatial membership, or rendering artifacts. Those responsibilities belong to
Ingestion, the Spatial Engine, and Reporting respectively.

## 4. Canonical Data Model

The platform recognizes six canonical entities.

### 4.1 Forest Event (Observation)
Represents what a source detected. It carries location, time, source, confidence,
severity, and additive geospatial enrichments. It is classified into exactly one
incident category derived from its type and geography.

### 4.2 Incident Category
Represents the kind of situation in observational terms. It is the segmentation
dimension of the Intelligence Engine. It is a geographic and observational fact and is
never a legal judgment.

### 4.3 Threat Category
Represents the interpreted meaning of a situation. It carries an origin classification
and associated recommended responses. Incident categories map to threat categories.
Threat categories map to ecosystem domains and recommended actions.

### 4.4 Intelligence Event
Represents a tracked situation. It carries identity, lifecycle state, dynamics, and
provenance. Its structure is domain-independent.

### 4.5 Investigation
Represents a human response to a tracked situation. It optionally binds to one
Intelligence Event and carries assignment, workflow status, resolution, outcome, and
an audit timeline.

### 4.6 Report
Represents a point-in-time artifact composed from read-only projections of platform
state.

## 5. Information Flow

```
Sources → Forest Event → (spatial + land-cover enrichment)
        → Incident Category → Threat Category → Ecosystem Domain
        → Detector (scored Detection)
        → Reconciliation → Intelligence Event
        → { Notifications, Investigation, Command Center, Report }
```

Information shall flow in one direction through derivation. Downstream consumers shall
read Intelligence Events. They shall not mutate them. Investigations shall annotate a
tracked situation without creating or resolving it.

## 6. Intelligence Identity

An Intelligence Event shall be uniquely identified by:

```
(incident_category, spatial_key)
```

The ecosystem domain shall be derivable from the incident category. Where multi-tenant
operation is enabled, the identity shall be extended to:

```
(tenant, incident_category, spatial_key)
```

The following shall never form part of identity:

- `event_type` — a derived label.
- `signal_type` — provenance describing how the situation was detected.
- `severity`, `escalation_level`, `trend`, `priority_score`, `current_score`,
  `detection_count` — mutable lifecycle state.

The `spatial_key` is an abstraction. An administrative region is one implementation of
a spatial key. Finer spatial keys, including grid cells and feature identifiers, are
permitted implementations of the same concept.

## 7. Lifecycle State

Each Intelligence Event carries:

- `status` — `active` or `resolved`.
- `first_detected_at`, `last_detected_at` — temporal bounds of the situation.
- `detection_count` — number of cycles in which the situation was detected.
- `current_score`, `previous_score` — scoring inputs for trend computation.
- `severity`, `escalation_level`, `trend`, `priority_score` — derived dynamics.
- `incident_category` — identity component and segmentation dimension.
- `signal_type` — provenance of the detection that produced the event.
- `metadata` — evidence supporting the assertion.

## 8. Guarantees

The Intelligence Engine guarantees:

1. **Continuity.** A tracked situation retains identity across cycles and is updated,
   never duplicated.
2. **Uniqueness.** At most one active Intelligence Event exists per identity.
3. **Determinism.** Scoring and lifecycle transitions are deterministic.
4. **Idempotency.** Reconciliation on identical inputs produces identical state.
5. **Explainability.** Every Intelligence Event retains the evidence and provenance
   that justified it.
6. **Domain independence.** The engine applies identical logic to every domain.

## 9. Downstream Consumers

The following consumers read Intelligence Events and shall not mutate them:

- **Threat Assessment** maps incident categories to threat categories and interpreted
  assessments.
- **Risk** consumes active Intelligence Events as scoring inputs.
- **Notifications** consume the reconciliation change-set.
- **Investigations** bind to Intelligence Events by identity.
- **Command Center** projects active Intelligence Events by domain and category.
- **Reporting** renders Intelligence Events into sections.
