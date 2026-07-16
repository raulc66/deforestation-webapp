# 01 — Architecture Principles

## 1. Purpose

This document defines the architectural invariants of ForestWatch. These invariants
are binding. All current and future development shall conform to them. Any change that
violates an invariant is a regression regardless of test outcome.

## 2. Invariants

### INV-1 — Single Reconciliation Authority
The platform shall contain exactly one component that creates, updates, or resolves
Intelligence Events. No other component shall write to Intelligence Event lifecycle
state.

### INV-2 — No Duplicated Intelligence Logic
Anomaly detection, scoring, segmentation, and lifecycle rules shall exist in exactly
one location. Detectors and providers shall contribute inputs; they shall not
reimplement engine logic.

### INV-3 — Domain-Independent Engine
The reconciliation engine and scoring functions shall never branch on domain or
incident category. Domain semantics shall live only in taxonomy, detectors, providers,
and registries.

### INV-4 — Deterministic Analytics
Given identical inputs, analytics, scoring, and reconciliation shall produce identical
outputs. The deterministic path shall contain no machine-learning inference, no
randomness, and no dependence on wall-clock time beyond a single injected time anchor
per cycle.

### INV-5 — Scheduler Orchestrates Only
The scheduler shall sequence pipeline steps and shall own no business logic. Every
pipeline step shall be independently invocable and testable without the scheduler.

### INV-6 — Command–Query Separation
Read operations shall not mutate persistent state. Reconciliation shall be invoked
only by the scheduler or by an explicit, authenticated command operation. Query
endpoints shall return previously reconciled state.

### INV-7 — Repositories Own Persistence
Repositories shall be the only components that access the datastore. Services shall
shape data. Routes shall not access persistence directly.

### INV-8 — Canonical Intelligence Identity
An Intelligence Event shall be uniquely identified by its incident category and its
spatial key. Mutable state, including severity, escalation, trend, and score, shall
never be used as identity. `event_type` shall be a derived label. `signal_type` shall
be provenance.

### INV-9 — Single Spatial Engine
All geospatial membership and classification computation shall use the shared Spatial
Engine. No component shall reimplement geometry operations.

### INV-10 — Extension Over Modification
New domains, sources, detectors, report sections, spatial datasets, and notification
channels shall be added through registration. Editing an engine loop to add a domain
is prohibited.

### INV-11 — Read-Only Projections
Reports and the Command Center shall render intelligence. They shall not compute or
mutate intelligence.

### INV-12 — Additive, Namespaced Enrichment
Enrichment applied to observations shall be additive and namespaced. No enrichment
shall overwrite or remove another enrichment.

### INV-13 — Human Judgment Quarantine
Legally or ethically loaded conclusions shall be produced only through the
Investigation workflow. The engine shall not emit such conclusions automatically.

### INV-14 — Backward-Compatible Evolution
API contracts shall evolve additively. The read model shall tolerate legacy records
by applying deterministic defaults.

### INV-15 — Anti-Corruption Boundary
Ingestion providers shall normalize external data to canonical models at the boundary.
External schemas shall not propagate into the domain.

### INV-16 — Idempotent Reconciliation
Reconciliation shall be idempotent. Repeated execution on identical inputs shall not
change the resulting intelligence state.

## 3. Design Discipline

### 3.1 SOLID Alignment
- Services and engines shall hold a single responsibility.
- Extension points shall be open for extension and closed for modification.
- Contracts crossing extension boundaries shall be substitutable.
- Interfaces shall be minimal and purpose-specific.
- High-level engine logic shall not depend on low-level adapter implementations.

### 3.2 Clean and Hexagonal Structure
The domain core shall be independent of frameworks, transport, and persistence.
Providers, repositories, notification channels, and the Spatial Engine shall act as
adapters around the domain core.

### 3.3 Bounded Contexts
Each bounded context shall interact with others through service boundaries. Cross-
context access to persistence is prohibited.

### 3.4 Shared Kernel
The ecosystem taxonomy — incident categories, threat categories, ecosystem domains,
and their mappings — is the shared kernel and the ubiquitous language of the platform.
The shared kernel shall remain small and stable.

## 4. Consistency Model

The platform shall operate under an eventual-consistency model enforced by idempotent
reconciliation. Multi-document transactional consistency is not required for
intelligence lifecycle. Recovery from partial execution shall occur through subsequent
reconciliation cycles.

## 5. Concurrency Model

Exactly one reconciliation execution shall occur at a time. Where the platform is
deployed across multiple instances, a single-runner guarantee shall be enforced before
reconciliation is permitted to run in more than one process.

## 6. Enforcement

Conformance to these invariants shall be verified through automated tests, code
review, and architectural review. A violation shall block release until remediated or
until an Architecture Decision Record formally amends the invariant.
