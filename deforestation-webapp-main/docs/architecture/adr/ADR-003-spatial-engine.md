# ADR-003 — Spatial Engine

## Status

Accepted.

## Context

The platform requires geospatial membership and classification for observation
enrichment. The prior geospatial implementation was specialized for land-cover
classification, encoded land-cover semantics into its core, and used fixed geographic
bounds. Reusing it for additional datasets would require either specialization of a
single-purpose module or duplication of geometry logic.

## Decision

The platform shall provide a single Spatial Engine that separates the mechanism of
spatial computation from the meaning of spatial datasets.

- A reusable spatial index shall resolve point-in-polygon membership using a grid
  partition and bounding-box pre-filter with configurable bounds.
- Polygon providers shall supply labeled feature collections and their selection
  semantics.
- Overlay providers shall answer membership or classification using the spatial index.
- An enrichment pipeline shall apply registered overlay providers to observations,
  attaching additive, namespaced enrichments.

All geospatial computation shall use this engine. No component shall reimplement
geometry operations.

## Alternatives Considered

- **Specialize the existing land-cover module for each dataset.** Rejected because it
  couples unrelated dataset semantics into one module.
- **Duplicate the geometry logic per dataset.** Rejected because it violates the
  no-duplication invariant.
- **Adopt an external GIS service.** Rejected as unnecessary for the current
  membership and classification requirements and as an increase in operational
  complexity.

## Consequences

- Land cover becomes one overlay among many.
- New spatial datasets are added as polygon providers and enrichment keys.
- Enrichment is additive and namespaced across datasets.
- The spatial index is domain-agnostic and dataset-agnostic.

## Future Implications

- Protected Areas, Natura 2000, watersheds, administrative boundaries, hunting areas,
  carbon projects, and habitat ranges are added without modifying the engine.
- Finer spatial keys may be derived from spatial datasets.
- The index mechanism may be upgraded behind its interface for larger datasets.
