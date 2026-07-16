# Ecosystem Intelligence Architecture (Implementation Notes)

ForestWatch is evolving from a wildfire-focused monitor into an **Ecosystem
Intelligence Platform**. This document describes the foundation added in the
first architectural milestone — not future detection pipelines.

> **Canonical architecture:** The authoritative ecosystem intelligence model — the
> canonical data model, intelligence identity, domain plug-in architecture, and the
> registries for aggregation and reporting — is defined in `docs/architecture/`,
> specifically `02-intelligence-engine.md`, `06-domain-plugin-architecture.md`, and
> `07-reporting-and-command-center.md`, with decisions in `docs/architecture/adr/`. This
> file provides **implementation notes** for the `app/core/ecosystem/` shared kernel and
> defers to the canonical specifications for all architectural concepts.

## Design principles

> These principles are the local expression of the canonical invariants in
> `docs/architecture/01-architecture-principles.md` (extension over modification,
> no duplicated intelligence logic, backward-compatible evolution).

1. **Extend, don't replace** — existing services (`AnalyticsService`,
   `IntelligenceEventsService`, `RiskService`, `ReportService`) remain the
   source of truth.
2. **Registries over rewrites** — new domains register aggregators and report
   sections instead of modifying core generation code.
3. **Backward compatibility** — legacy intelligence events without
   `incident_category` default to `wildfire`.

## Core types (`app/core/ecosystem/`)

| Module | Purpose |
|---|---|
| `incident_categories.py` | `IncidentCategory` enum + mapping from `ForestEvent.event_type` |
| `domains.py` | `EcosystemDomain` enum (Forest Health, Wildlife, Environment, Human Activity) |
| `command_center.py` | Pydantic models for Command Center snapshots |

## Incident categories

Intelligence events now carry `incident_category` alongside `event_type`:

- `event_type` — detection mechanism (`anomaly`, future: `volume_alert`, …)
- `incident_category` — ecosystem meaning (`wildfire`, `illegal_logging`, …)

The current anomaly reconciliation uses key `(event_type, region)` and defaults category
to `wildfire`.

> **Canonical target:** Canonical intelligence identity is
> `(incident_category, spatial_key)` — see
> `docs/architecture/adr/ADR-001-canonical-intelligence-identity.md`. Under canonical
> v1.0, `event_type` is a derived label and `signal_type` is provenance; the
> `(event_type, region)` key described here is the pre-v1.0 implementation and is
> superseded by the canonical identity.

## Pluggable incident aggregation

`app/modules/analytics/incident_aggregation.py`:

```python
registry = get_incident_aggregation_registry()
registry.register(MyDomainAggregator())  # future module
```

`WildfireIncidentAggregator` wraps existing `overview()`, `by_event_type()`, and
`get_anomalies()` — no duplicate Mongo queries.

**API:** `GET /api/analytics/intelligence/incidents`

## Modular report sections

`app/modules/reports/report_sections.py`:

```python
from app.modules.reports.report_sections import register_report_section, ReportSectionSpec

register_report_section(ReportSectionSpec(
    key="wildlife_summary",
    description="Wildlife module summary",
    fetcher=my_async_fetcher,
    ecosystem_domain="wildlife",
))
```

Built-in sections (overview, anomalies, risk, weather, …) register at import.
`ReportService.gather_report_data()` iterates the registry; PDF/CSV/JSON
generators continue reading the same section keys.

## Command Center preparation

`CommandCenterService` assembles a read-only snapshot:

- Domain readiness (`active` / `partial` / `planned`)
- Incident aggregation output
- Active intelligence counts by category

**API:** `GET /api/analytics/intelligence/command-center`

## Environmental Threat Intelligence

`ThreatAssessmentService` classifies threats from existing intelligence events:

1. `IncidentCategory` → `ThreatCategory` via `threat_mapping.py`
2. Deterministic scoring (confidence, risk contribution, priorities)
3. Recommended actions from category templates

**API:** `GET /api/analytics/intelligence/threats`, `GET /api/analytics/intelligence/threat-summary`

Report section key: `environmental_threat_assessment` (registered via `report_sections.py`).


## Extension checklist for new ecosystem modules

1. Add aggregator implementing `IncidentAggregator`.
2. Register via `get_incident_aggregation_registry().register(...)`.
3. Optionally register report sections via `register_report_section(...)`.
4. Set `incident_category` when creating intelligence events.
5. Update `CommandCenterService._domain_catalog()` status when the module goes live.
