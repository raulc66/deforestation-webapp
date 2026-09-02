# 08 — Roadmap

## 1. Purpose

This document defines the phased evolution of the ForestWatch **implementation
architecture** toward multi-category **forest intelligence**. Phases are ordered so that
platform capabilities precede the forest incident categories that depend on them.

**Commercial product scope** is the Forest Intelligence Platform defined in
`docs/business/BUSINESS_STRATEGY.md` and `docs/business/PRODUCT_STRATEGY.md`. This
roadmap governs engineering phases. It does not authorize expansion of the commercial
product beyond forest ecosystems.

## 2. Phase Ordering Principle

Engine generalization shall precede forest category onboarding. New observation data shall
not enter the shared pipeline until the pipeline is capable of segmenting and reconciling
it without corrupting existing categories.

## 3. Phase 0 — Engine Generalization

Phase 0 establishes the platform capabilities required for multi-category operation.

Scope:

- Canonical intelligence identity `(incident_category, spatial_key)`.
- Generalized reconciliation contract operating over Detections.
- Segmented analysis grouped by `(spatial_key, incident_category)`.
- Detector abstraction and detector registry.
- Generalized aggregation registry.
- Command–query separation for intelligence reads.
- Single-reconciler guarantee.
- Idempotent migration aligning existing records to canonical identity.

Phase 0 introduces no new forest category and no new observation source. Existing category
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

## 7. Future Forest Incident Categories (Product Scope)

The following forest incident categories are planned for onboarding through the domain
plug-in architecture without redesign of the Intelligence Engine. They are **Forest
Intelligence Platform product scope**:

- Wildfire and forest fire intelligence *(implemented; generalized in Phase 0)*
- Forest loss, illegal logging, and land-use change *(Phase 2)*
- Tree theft
- Forest degradation
- Storm damage to forest estate
- Pest outbreaks and forest diseases
- Protected-area violations within forest contexts
- Habitat fragmentation
- Reforestation monitoring
- Biodiversity within forests
- Carbon forests and forest carbon compliance
- Forest compliance and forest ecosystem health
- Wildlife monitoring within forest ecosystems

Onboarding sequence for each category follows
`docs/architecture/06-domain-plugin-architecture.md`.

## 8. Architectural Extension Capability (Not Product Scope)

The domain-independent intelligence engine **can** onboard incident categories outside
forest ecosystems without engine redesign. That extensibility is an implementation
property, not a commercial commitment.

The following are **not** ForestWatch product scope. They are listed only to document
engine extensibility. They may belong to separate future products:

- Water quality and general water management
- Air quality and urban pollution
- Marine environments and oceans
- General flood intelligence outside forest context
- General drought and climate intelligence outside the forest ecosystem
- Non-forest pollution monitoring

ForestWatch shall not commercialize these categories without explicit product and
architecture strategy review.

## 9. Future Platform Layers

The following layers are recognized as future extensions of the implementation
architecture. They are additive and shall not require redesign of the Intelligence Engine:

- Satellite change-detection detectors.
- Model-assisted detection.
- External government data providers.
- Cross-category correlation over Intelligence Events *(within forest scope)*.
- Finer spatial-key strategies for point and linear phenomena.
- Multi-tenant isolation and category-scoped authorization.
- Pipeline observability and stage-level metrics.

## 10. Dependency Summary

```
Phase 0 ─┬─► Phase 2 ─► Phase 3
Phase 1 ─┘
Future Forest Categories (§7) ──► depend on Phase 0 and Phase 1
Architectural Extension (§8) ──► engine capability only; not product roadmap
Future Platform Layers (§9) ──► additive
```
