# ADR-005 — Domain Plug-in Architecture

## Status

Accepted.

## Context

The platform is expected to grow from a single mature domain to many ecosystem domains
over a multi-year horizon. Onboarding a domain must not require modification of engine
internals. Without a defined plug-in architecture, each new domain risks introducing
isolated pipelines and duplicated logic.

## Decision

An ecosystem domain shall be onboarded exclusively through extension points:

- Ingestion providers, acting as anti-corruption adapters.
- Spatial polygon and overlay providers for enrichment.
- Detectors emitting Detections.
- Incident aggregators registered in the aggregation registry.
- Report sections registered in the report section registry.
- Notification channels and category-aware templates.
- Taxonomy mappings from incident categories to threat categories, ecosystem domains,
  and recommended actions.
- Command Center domain catalog configuration.

Investigations shall require no change to onboard a domain. Editing engine loops,
scoring functions, reconciliation identity, or the segmentation core to add a domain is
prohibited.

## Alternatives Considered

- **Per-domain services and pipelines.** Rejected because it duplicates logic and
  fragments the platform.
- **Conditional branching in shared engines per domain.** Rejected because it violates
  domain independence and the extension-over-modification invariant.
- **A dynamic plugin loading system with sandboxing.** Rejected as unnecessary
  complexity for the current requirement; registration within the application is
  sufficient.

## Consequences

- New domains are added by registration and configuration.
- Downstream engines absorb new domains automatically.
- The shared kernel grows additively through taxonomy extension.
- The onboarding sequence is uniform across domains.

## Future Implications

- Wildlife, biodiversity, pollution, water quality, flood, drought, landslide, carbon,
  and habitat-fragmentation domains onboard through the same points.
- External government data and model-assisted detection integrate as providers and
  detectors.
- Bounded contexts remain extractable into separate services if required.
