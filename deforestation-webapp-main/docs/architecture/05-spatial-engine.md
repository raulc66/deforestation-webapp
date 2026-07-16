# 05 — Spatial Engine

## 1. Purpose

This document specifies the Spatial Engine, the single authority for geospatial
indexing, membership resolution, and observation enrichment.

## 2. Authority

The Spatial Engine provides all geospatial computation for the platform. No component
shall reimplement geometry operations. All membership and classification queries shall
be served by the Spatial Engine.

## 3. Separation of Mechanism and Meaning

The Spatial Engine separates the mechanism of spatial computation from the meaning of
spatial datasets.

- The mechanism is a reusable spatial index that resolves which indexed features
  contain a coordinate.
- The meaning is supplied by dataset providers that describe what indexed features
  represent.

## 4. Reusable Spatial Index

The Spatial Engine provides a reusable spatial index that:

- Loads polygon features once.
- Builds an in-memory index using a grid partition and bounding-box pre-filter.
- Resolves point-in-polygon membership for a coordinate.
- Operates with configurable geographic bounds.

The spatial index shall be domain-agnostic. It shall not encode the semantics of any
particular dataset.

## 5. Polygon Providers

A polygon provider supplies a labeled feature collection and its selection semantics.
Each spatial dataset is expressed as a polygon provider. Polygon providers are
registered; they shall not be wired into a monolith.

## 6. Overlay Providers

An overlay provider answers a spatial question using the spatial index. An overlay
provider answers one of:

- Membership — whether a coordinate lies within a labeled feature.
- Classification — which labeled class applies to a coordinate.

Membership and classification are served by the same index with different result
semantics.

## 7. Enrichment Pipeline

The Spatial Engine provides an enrichment pipeline invoked when an observation is
persisted. The pipeline passes an observation coordinate through an ordered set of
registered overlay providers. Each overlay provider attaches a namespaced enrichment
to the observation.

Enrichment shall be additive. Each overlay provider writes into its own namespace. No
overlay provider shall overwrite or remove another overlay provider's enrichment.

Enrichment shall be deterministic and shall not affect intelligence state directly.

## 8. Supported and Future Datasets

The Spatial Engine shall support additional datasets through polygon and overlay
providers, including but not limited to:

- Land Cover
- Protected Areas
- Natura 2000 sites
- Watersheds
- Administrative Boundaries
- Hunting Areas
- Carbon Projects
- Habitat Ranges

Each dataset is added as a polygon provider and an enrichment key. Adding a dataset
shall not require modification of the spatial index or the enrichment pipeline.

## 9. Dataset Management

Spatial datasets shall be treated as static, versioned assets by default. A dataset
shall be promoted to a mutable datastore collection only where the polygons must be
user-editable.

## 10. Spatial Key

The Spatial Engine supports the spatial key abstraction used by intelligence identity.
An administrative region is one implementation of a spatial key. Grid cells and feature
identifiers are permitted implementations. The Spatial Engine shall be capable of
resolving the spatial key applicable to an observation.

## 11. Invariants

1. Geometry computation exists in exactly one engine.
2. Datasets are added by registration, never by modifying the index.
3. Enrichment is additive and namespaced.
4. Enrichment is deterministic and free of side effects on intelligence state.
