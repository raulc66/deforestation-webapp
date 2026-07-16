# 08 — Roadmap

## 1. Purpose

This document defines the phased evolution of ForestWatch toward multi-domain
environmental intelligence. Phases are ordered so that platform capabilities precede
the domains that depend on them.

## 2. Phase Ordering Principle

Engine generalization shall precede domain onboarding. New observation data shall not
enter the shared pipeline until the pipeline is capable of segmenting and reconciling it
without corrupting existing domains.

## 3. Phase 0 — Engine Generalization

Phase 0 establishes the platform capabilities required for multi-domain operation.

Scope:

- Canonical intelligence identity `(incident_category, spatial_key)`.
- Generalized reconciliation contract operating over Detections.
- Segmented analysis grouped by `(spatial_key, incident_category)`.
- Detector abstraction and detector registry.
- Generalized aggregation registry.
- Command–query separation for intelligence reads.
- Single-reconciler guarantee.
- Idempotent migration aligning existing records to canonical identity.

Phase 0 introduces no new domain and no new observation source. Existing domain
behavior shall be preserved.

## 4. Phase 1 — Spatial Engine Generalization

Phase 1 establishes the generic Spatial Engine.

Scope:

- Extraction of the reusable spatial index.
- Polygon provider and overlay provider abstractions.
- Additive, namespaced enrichment pipeline.

Phase 1 preserves existing land-cover classification behavior.

## 5. Phase 2 — First Human Activity Domain

Phase 2 onboards the Human Activity domain through the extension points.

Scope:

- Forest-loss ingestion provider.
- Forest-loss observation type and incident category mappings.
- Protected-area overlay and enrichment.
- Category-configured detector.
- Registered aggregator, report sections, and notification templates.
- Scheduler ingestion step for forest-loss observations.

Phase 2 depends on Phase 0 and Phase 1.

## 6. Phase 3 — Surface Layer

Phase 3 exposes the Human Activity domain to users.

Scope:

- Forest-loss map layer and protected-area overlay.
- Domain and category filters.
- Domain watch card.
- Command Center domain status activation.
- Category-aware presentation of intelligence events and notifications.

Phase 3 depends on Phase 2.

## 7. Future Domains

The following domains shall be onboarded through the domain plug-in architecture
without redesign of the Intelligence Engine:

- Wildlife Monitoring
- Biodiversity
- Pollution
- Water Quality
- Flood Intelligence
- Drought Monitoring
- Landslides
- Carbon Monitoring
- Habitat Fragmentation

## 8. Future Platform Layers

The following layers are recognized as future extensions of the platform. They are
additive to the architecture and shall not require redesign of the Intelligence Engine:

- Satellite change-detection detectors.
- Model-assisted detection.
- External government data providers.
- Cross-domain correlation over Intelligence Events.
- Finer spatial-key strategies for point and linear phenomena.
- Multi-tenant isolation and domain-scoped authorization.
- Pipeline observability and stage-level metrics.

## 9. Dependency Summary

```
Phase 0 ─┬─► Phase 2 ─► Phase 3
Phase 1 ─┘
Future Domains ──► depend on Phase 0 and Phase 1
Future Platform Layers ──► additive
```
