# 06 — Domain Plug-in Architecture

## 1. Purpose

This document specifies how ecosystem domains are added to ForestWatch. Adding a domain
shall require configuration and extension. It shall not require modification of engine
internals.

## 2. Definition of a Domain

An ecosystem domain is fully described by populating the platform's extension points. A
domain shall not introduce a private pipeline, a private reconciliation path, or
private intelligence logic.

## 3. Extension Points

A domain is onboarded by supplying the following.

### 3.1 Provider
The domain shall register an ingestion provider that acquires observations and
normalizes them to canonical models. Providers act as anti-corruption adapters. The
scheduler executes all registered providers.

### 3.2 Enrichment
The domain shall register any required polygon and overlay providers with the Spatial
Engine. Enrichment attaches namespaced spatial context to observations.

### 3.3 Detector
The domain shall register one or more detectors that emit Detections. The
Reconciliation Engine consumes those Detections without modification.

### 3.4 Aggregation
The domain shall register an incident aggregator. The aggregation registry merges
contributions generically. The registry shall not require modification to incorporate a
new aggregator's contribution.

### 3.5 Reporting
The domain shall register report sections through the report section registry. Report
composition shall not require modification.

### 3.6 Notifications
The domain shall register notification channels or category-aware templates. Dispatch
consumes the reconciliation change-set.

### 3.7 Investigations
The domain shall require no change to the Investigation workflow. Investigations bind to
any Intelligence Event by identity.

### 3.8 Command Center
The domain shall be represented in the domain catalog through configuration. The Command
Center consumes generalized aggregation.

## 4. Taxonomy Extension

A domain shall extend the shared kernel by:

- Adding incident categories.
- Adding threat categories where required.
- Adding mappings from incident categories to threat categories, ecosystem domains, and
  recommended actions.

Taxonomy extension is additive. It shall not alter the semantics of existing
categories.

## 5. Domain Onboarding Sequence

The canonical onboarding sequence is:

1. Register the provider.
2. Add the incident category and its taxonomy mappings.
3. Register any spatial overlays.
4. Register the detector and its category-specific configuration.
5. Register the aggregator, report sections, and notification templates.
6. Represent the domain in the Command Center domain catalog.

Downstream engines — reconciliation, scoring, investigations, and reporting — shall
absorb the domain automatically.

## 6. Prerequisite Platform Capabilities

The following platform capabilities enable domain onboarding by extension. They are
provided once and are not repeated per domain:

- Canonical intelligence identity and the generalized reconciliation contract.
- Segmented anomaly analysis and the detector registry.
- The generic Spatial Engine.
- The generalized aggregation registry.

## 7. Prohibition on Modification

Adding a domain by editing an engine loop, a scoring function, the reconciliation
identity, or the segmentation core is prohibited. Such an edit indicates a violation of
the plug-in architecture.
