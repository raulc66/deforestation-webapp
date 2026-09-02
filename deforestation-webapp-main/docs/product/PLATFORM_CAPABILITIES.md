# ForestWatch — Platform Capabilities

**Status:** Strategic product document — pending review.
**Audience:** Product leadership, commercial stakeholders, forest operators, and anyone
needing a single reference for what the Forest Intelligence Platform **does** as a product.
**Authority:** This document defines **product capabilities** — what ForestWatch exposes
to users and organizations. It is subordinate to `docs/architecture/` and its ADRs for
platform invariants, to `docs/business/BUSINESS_STRATEGY.md` and
`docs/business/PRODUCT_STRATEGY.md` for commercial identity and module context, and to
`docs/product/INVESTIGATION_FRAMEWORK.md` for investigation workflow detail.

**Document type:** Platform capabilities catalog. This is not an implementation
specification, technical architecture document, API reference, or UI design. It describes
*what each capability does*, *who uses it*, and *how capabilities relate* — not *how they
are built*.

**Scope:** Forest Intelligence Platform capabilities within forest ecosystem scope only.

**Language:** The key words **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**,
**SHOULD NOT**, **MAY**, and **OPTIONAL** in this document are to be interpreted as
described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

**Related documents:** Investigation lifecycle and workflow stages are defined in
`docs/product/INVESTIGATION_FRAMEWORK.md`. This document references Investigations as a
capability but does not redefine that workflow.

---

## 1. Purpose

ForestWatch is a **Forest Intelligence Platform** — a product that helps organizations
understand, monitor, investigate, explain, and report changes affecting forest ecosystems.
Users experience the product through a set of **capabilities**: coherent functional areas
that each serve a distinct role in the Observe → Derive → Act thesis
(`docs/architecture/00-platform-vision.md` §4).

This document:

1. Catalogs every major product capability ForestWatch exposes.
2. Defines purpose, responsibilities, inputs, outputs, users, and relationships for each.
3. Describes how capabilities interact without prescribing implementation.
4. Establishes ownership boundaries — what each capability owns and what it must not own.
5. Maps capabilities to architecture bounded contexts and ADRs.
6. Explains how capabilities evolve across architecture Phases 0–3.

The document exists so that product, commercial, and engineering stakeholders share one
vocabulary for **what the product is**, distinct from **how the engine is implemented**.

---

## 2. Capability Philosophy

### 2.1 Capabilities serve forest stewardship

Every capability **SHALL** serve organizations responsible for forest ecosystems. No
capability **SHALL** imply monitoring or intelligence for non-forest environmental domains
(air quality, marine, urban pollution, general water management).

### 2.2 Intelligence before raw data

Capabilities **SHALL** present derived intelligence as the primary operational surface.
Observations and ingestion health are accessible through Monitoring but **SHALL NOT**
replace Intelligence as the unit of daily attention (PRODUCT_STRATEGY P-1).

### 2.3 Derived intelligence is not human conclusion

The Intelligence capability derives tracked situations. The Investigations capability
owns human judgment. Legally or ethically loaded conclusions **MUST** flow through
Investigations only (INV-13). No other capability **MAY** record such conclusions.

### 2.4 Read-only projections do not mutate state

Command Center, Reporting, Historical Analysis, and Compliance views **SHALL** consume
platform state as read-only projections. They **MUST NOT** trigger reconciliation, create
Intelligence Events, or close investigations (ADR-011, `07-reporting-and-command-center.md`).

### 2.5 Extension, not reinvention

New forest incident categories **SHALL** extend existing capabilities through configuration
and registration. New categories **MUST NOT** require new product modules or replacement
of the platform (INV-10, ADR-005).

### 2.6 One engine, many surfaces

The domain-independent intelligence engine (implementation architecture) powers the
Intelligence capability. Operational, analytical, and administrative capabilities are
**surfaces** over that engine and its bounded contexts — not separate intelligence
pipelines per category.

---

## 3. Core Capabilities

Each subsection describes one product capability. **Architecture mapping** summarizes
alignment without duplicating architecture documents.

---

### 3.1 Monitoring

| Field | Description |
|-------|-------------|
| **Purpose** | Provide visibility into forest observation intake — what the platform has received, from which sources, covering which geographies and time periods, and whether ingestion is healthy. |
| **Responsibilities** | Display observation streams and intake status; expose source provenance and geography coverage; surface ingestion health signals; support manual and configured observation intake visibility. Monitoring confirms the observation layer is active; it does not derive intelligence. |
| **Inputs** | External and internal forest observation sources (satellite feeds, imports, field submissions); ingestion configuration; spatial enrichment results attached to observations. |
| **Outputs** | Observation listings and summaries; source-level intake status; geographic and temporal coverage views; provenance metadata for downstream evidence use. |
| **Primary users** | Duty officers, forest inspectors, data coordinators, research analysts verifying intake completeness. |
| **Relationships** | **Upstream of Intelligence** — observations feed derivation. **Input to Investigations** — observations cited as evidence. **Referenced by Historical Analysis** — observation volume over time. **Configured via Administration** — sources and schedules. Monitoring **MUST NOT** score, reconcile, or lifecycle-manage tracked situations. |

**Architecture mapping:** Ingestion bounded context (`00-platform-vision.md` §5); spatial
enrichment via Spatial Engine (ADR-003) appears on observations but is not a separate product
capability.

---

### 3.2 Intelligence

| Field | Description |
|-------|-------------|
| **Purpose** | Derive and maintain **Intelligence Events** — persistent, scored, lifecycle-managed tracked forest situations — from observations across forest incident categories. |
| **Responsibilities** | Segment observations by forest incident category and location; produce scored detections; reconcile detections into tracked situations; maintain lifecycle (active/resolved), trend, escalation, and priority; expose intelligence as the primary unit of operational attention. |
| **Inputs** | Normalized forest observations; spatial enrichment; category-segmented analysis; detector outputs (Detections); prior intelligence state; configured thresholds per category. |
| **Outputs** | Active and resolved Intelligence Events with identity, score, trend, escalation, severity, priority, detection history, and evidence metadata; reconciliation change-set consumed by notifications. |
| **Primary users** | Duty officers, forest inspectors, compliance officers, regional coordinators — anyone prioritizing daily forest situational attention. |
| **Relationships** | **Downstream of Monitoring** — consumes observations. **Upstream of Command Center, Reporting, Historical Analysis, Compliance** — as read-only inputs. **Trigger for Investigations** — situations warrant human response. **MUST NOT** be mutated by Investigations, Reporting, Command Center, or Compliance views. Only the reconciliation authority writes intelligence lifecycle (INV-1, ADR-002). |

**Architecture mapping:** Intelligence Engine bounded context; canonical identity
`(incident_category, spatial_key)` (ADR-001); Detection envelope (ADR-009); lifecycle
(ADR-006); detector framework (ADR-004); read/write separation — intelligence reads do not
reconcile (ADR-011).

---

### 3.3 Investigations

| Field | Description |
|-------|-------------|
| **Purpose** | Enable structured **human response** to derived intelligence — evidence collection, assessment, human decision, and closure with a complete audit record. |
| **Responsibilities** | Open, assign, progress, and close investigation cases; maintain append-only audit timeline; record human outcomes and rationale; optionally bind to one Intelligence Event; quarantine legally and ethically loaded conclusions (INV-13). |
| **Inputs** | Derived intelligence (linked Intelligence Events); platform evidence (observations, intelligence history, spatial overlays); external evidence attached by analysts; analyst notes and assessments. |
| **Outputs** | Investigation records with workflow status, assignment, outcome, resolution, and audit timeline; investigation statistics for Command Center and Reporting; notification triggers on lifecycle transitions. |
| **Primary users** | Field analysts, forest inspectors, compliance officers, senior analysts, supervisors. |
| **Relationships** | **Downstream of Intelligence** — triggered by tracked situations. **Consumes Monitoring** evidence. **Feeds Reporting and Compliance** — exports and audit artifacts. **Reflected in Command Center** — open/closed counts and statistics. **MUST NOT** create, update, resolve, or score Intelligence Events (ADR-006). Workflow detail: `INVESTIGATION_FRAMEWORK.md`. |

**Architecture mapping:** Investigation bounded context (`00-platform-vision.md` §5,
`02-intelligence-engine.md` §4.5); unchanged on domain onboarding (ADR-005 §3.7); INV-13.

---

### 3.4 Reporting

| Field | Description |
|-------|-------------|
| **Purpose** | Compose and export **point-in-time artifacts** — briefings, audit packages, grant reports, compliance submissions — from read-only platform projections. |
| **Responsibilities** | Compose reports from registered sections; gather intelligence, aggregation, investigation, and status data; export in standard document and data formats; support on-demand and scheduled report generation; isolate section failures so partial reports still compose. |
| **Inputs** | Read-only projections of Intelligence Events, incident aggregation, investigation summaries, Command Center domain status, and registered report sections; user-selected scope (time, geography, category). |
| **Outputs** | Point-in-time report artifacts (document and data exports); scheduled report deliveries where configured. |
| **Primary users** | Policy analysts, grant reporting officers, compliance officers, agency directors, certification reviewers, research leads. |
| **Relationships** | **Reads from Intelligence, Investigations, Command Center** — never writes. **Used by Compliance** — compliance-oriented report templates. **Complements Command Center** — Command Center is live; Reporting is exportable snapshot. **MUST NOT** invoke reconciliation or mutate investigations ( `07-reporting-and-command-center.md`). |

**Architecture mapping:** Reporting bounded context / subsystem; section registry (ADR-005
§3.5); scheduler triggers generation, does not compose (ADR-007).

---

### 3.5 Command Center

| Field | Description |
|-------|-------------|
| **Purpose** | Provide the **daily operational surface** — a live, unified snapshot of forest situational awareness across categories, domains, and response status. |
| **Responsibilities** | Assemble read-only operational snapshot: ecosystem domain catalog status, incident aggregation by category, active intelligence counts, threat distribution, investigation statistics; present cross-category forest picture for prioritization and briefing. |
| **Inputs** | Most recently reconciled intelligence state; generalized aggregation registry outputs; domain catalog configuration; investigation statistics; threat and origin summaries. |
| **Outputs** | Live operational dashboard snapshot; navigation entry points to Intelligence, Investigations, Monitoring, and Reporting. |
| **Primary users** | Duty officers, regional coordinators, forest estate managers, agency directors — primary daily users per PRODUCT_STRATEGY P-6. |
| **Relationships** | **Aggregates Intelligence and Investigations** read-only. **Primary operational hub** — users start here, drill into other capabilities. **MUST NOT** reconcile, score, or mutate intelligence or investigations (`07-reporting-and-command-center.md` §2, §6). Freshness follows scheduler reconciliation cadence (ADR-011). |

**Architecture mapping:** Command Center bounded context; generalized aggregation registry
(ADR-005 §3.4, §3.8); read-only projection invariant.

---

### 3.6 Compliance

| Field | Description |
|-------|-------------|
| **Purpose** | Support **forest compliance workflows** — certification, protected-area rules, carbon forest obligations, harvest regulations — by composing intelligence, investigations, reporting, and spatial context into a compliance-oriented product experience. |
| **Responsibilities** | Present compliance-relevant forest categories and overlays; route compliance situations through Investigation workflow for human findings; enable compliance-oriented report exports; surface permit, protected-area, and jurisdictional context during review. Compliance **does not** derive intelligence or record conclusions outside Investigations. |
| **Inputs** | Intelligence Events in compliance-relevant categories; spatial overlays (protected areas, management boundaries, permits where configured); open and closed investigations; compliance-configured report sections. |
| **Outputs** | Compliance-oriented views and filters; investigation and report artifacts suitable for auditors and regulators; compliance status summaries in Command Center where configured. |
| **Primary users** | Compliance officers, certification assessors, corporate sustainability leads, forestry authority inspectors, audit firms. |
| **Relationships** | **Composes Intelligence + Investigations + Reporting + spatial overlays** — not a separate engine (PRODUCT_STRATEGY §8.5). **MUST** route human findings through Investigations (INV-13). **MUST NOT** auto-generate compliance violations or legal conclusions. **Uses Historical Analysis** for retrospective compliance review. |

**Architecture mapping:** Product composition — no architecture bounded context named
Compliance. Uses incident categories, Spatial Engine overlays (ADR-003), Investigations,
Reporting sections (ADR-005).

---

### 3.7 Historical Analysis

| Field | Description |
|-------|-------------|
| **Purpose** | Provide **temporal and retrospective views** over forest observations and intelligence history — trends, baselines, lifecycle patterns, and long-term forest change. |
| **Responsibilities** | Present read-only historical projections: observation volume trends, category distribution over time, intelligence lifecycle history, resolved situation records, regional baseline and deviation patterns; support research, audit preparation, and long-term forest health assessment. |
| **Inputs** | Historical observations; reconciled intelligence history; aggregation outputs over defined time windows; investigation closure records where relevant. |
| **Outputs** | Temporal summaries, trend views, and historical comparisons; inputs to Reporting and Investigations as evidence context. |
| **Primary users** | Research scientists, policy analysts, compliance officers (retrospective review), certification assessors, senior forest managers. |
| **Relationships** | **Read-only across Monitoring and Intelligence history**. **Supports Investigations** — historical context as evidence. **Feeds Reporting** — historical sections. **MUST NOT** recompute or mutate intelligence lifecycle on read (INV-4 determinism applies to derivation, not to re-execution of past cycles). **Distinct from Command Center** — historical vs. live operational. |

**Architecture mapping:** Product composition of read-only temporal projections; consistent
with deterministic analytics (INV-4); not a separate architecture bounded context.

---

### 3.8 Administration

| Field | Description |
|-------|-------------|
| **Purpose** | Enable organizations to **configure and govern** the product — sources, geographies, users, categories, overlays, notifications, and operational parameters — without altering intelligence engine internals. |
| **Responsibilities** | Manage organizational access and roles; configure observation sources and ingestion parameters; manage forest geography and monitoring scope; configure domain catalog and category visibility; register spatial overlays for enrichment; configure notification routing and report schedules; enforce edition capability limits (Community, Professional, Enterprise). |
| **Inputs** | Organizational policy; user and role definitions; source credentials and schedules; geography and overlay definitions; product edition entitlements. |
| **Outputs** | Configuration state consumed by all other capabilities; audit log of administrative changes where supported. |
| **Primary users** | System administrators, platform coordinators, agency IT leads, senior forest managers with configuration authority. |
| **Relationships** | **Enables all other capabilities** through configuration. **MUST NOT** bypass Intelligence or Investigations invariants — configuration registers extensions; it does not edit engine loops (INV-10). **Prepares for multi-tenancy** when enabled (ADR-010). Administration is operational governance, not intelligence derivation. |

**Architecture mapping:** Cross-cutting product capability; configuration of Ingestion
providers (ADR-005 §3.1), Spatial overlays (ADR-003), domain catalog (`07-reporting-and-
command-center.md` §4.2), tenant scope when active (ADR-010). Not listed as a separate
bounded context in `00-platform-vision.md` §5 — it governs bounded contexts.

---

## 4. Capability Interactions

Information flows in one direction through **derivation**, then read-only through
**projection** and **response**. The diagram below is a product-level view — not an
implementation map.

```
External sources
        ↓
   [Monitoring]          ← Administration configures sources
        ↓ observations
   [Intelligence]        ← sole writer of tracked situations
        ↓ read-only projections
   ┌────┴────┬──────────────┬─────────────────┐
   ↓         ↓              ↓                 ↓
[Command   [Reporting]  [Historical      [Compliance
 Center]                 Analysis]         views]
   ↓
   └──→ user prioritizes → [Investigations] → human conclusions
                              ↓
                         [Reporting] / [Compliance exports]
```

### 4.1 Derivation path (Observe → Derive)

1. **Administration** configures sources and geography scope.
2. **Monitoring** makes observations visible after intake and spatial enrichment.
3. **Intelligence** derives and maintains tracked situations through scheduled
   reconciliation cycles.

No other capability participates in derivation. Command Center and Reporting **MUST NOT**
trigger derivation (ADR-011).

### 4.2 Response path (Act)

1. Users observe situations via **Command Center** or **Intelligence**.
2. Users open **Investigations** for situations requiring human judgment.
3. Analysts collect evidence from **Monitoring**, **Intelligence**, **Historical Analysis**,
   and external sources (per `INVESTIGATION_FRAMEWORK.md`).
4. Human decisions are recorded in **Investigations** only.
5. **Reporting** and **Compliance** export outcomes for stakeholders.

### 4.3 Projection path (read-only)

**Command Center**, **Reporting**, **Historical Analysis**, and **Compliance** views
consume reconciled state. They reflect the most recent reconciliation cycle; they do not
refresh intelligence on access.

### 4.4 Notifications (cross-cutting)

Outbound notifications are not a separate product capability in this catalog. They derive
from reconciliation change-sets and investigation lifecycle transitions
(`09-system-context.md` §3.10). Notifications alert users to act; **Investigations** and
**Intelligence** record state.

---

## 5. Capability Boundaries

### 5.1 Ownership matrix

| Capability | Owns | Does NOT own |
|------------|------|--------------|
| **Monitoring** | Observation visibility; intake status presentation | Intelligence lifecycle; investigation workflow; report composition |
| **Intelligence** | Derived tracked situations; scoring; lifecycle via reconciliation | Observations (intake); human conclusions; report layout; compliance findings |
| **Investigations** | Human response cases; audit timeline; outcomes | Intelligence lifecycle; observation intake; derived scoring |
| **Reporting** | Point-in-time artifact composition and export | Intelligence derivation; investigation decisions; live operational state |
| **Command Center** | Live read-only operational snapshot | Any persistent state mutation; intelligence reconciliation |
| **Compliance** | Compliance-oriented product composition and views | Separate compliance engine; autonomous violation findings |
| **Historical Analysis** | Read-only temporal projections | Intelligence re-derivation on read; lifecycle mutation |
| **Administration** | Configuration and organizational governance | Intelligence logic; detector rules; reconciliation |

### 5.2 Platform-wide prohibitions

No product capability **MAY**:

- create a second intelligence pipeline per forest category;
- record legally or ethically loaded conclusions outside Investigations (INV-13);
- invoke reconciliation from a read path (ADR-011);
- expand scope beyond forest ecosystems without strategy review;
- substitute for field verification, legal process, or auditor judgment.

### 5.3 Intelligence lifecycle authority

**Only Intelligence** (via the reconciliation authority) **MAY** create, update, or resolve
Intelligence Events (INV-1). Every other capability **MUST** treat intelligence as
read-only input unless explicitly performing administration of configuration.

---

## 6. User Interaction Model

Capabilities group into four interaction modes. A user **MAY** use multiple modes in one
session; the product **SHALL** make mode boundaries visible.

### 6.1 Operational capabilities (daily use)

**Command Center**, **Intelligence**, **Monitoring**, and **Investigations** (when cases
are active).

Operators use these for situational awareness, prioritization, field dispatch, and case
progress. Command Center is the primary entry point (PRODUCT_STRATEGY P-6).

### 6.2 Analytical capabilities (retrospective use)

**Historical Analysis** and analytical views within **Reporting**.

Analysts and researchers use these for trend review, baseline comparison, study periods,
and audit preparation. Read-only; no lifecycle impact.

### 6.3 Decision-support capabilities (judgment use)

**Investigations** and **Compliance** (when routing findings through investigation workflow).

Analysts and compliance officers use these to reach evidence-backed human conclusions.
Investigations are the only capability that **MAY** record such conclusions (INV-13).

### 6.4 Administrative capabilities (configuration use)

**Administration**.

Administrators configure sources, scope, users, overlays, and schedules. Used episodically;
changes affect all other capabilities but do not directly derive intelligence.

### 6.5 Interaction summary

| Capability | Mode |
|------------|------|
| Command Center | Operational |
| Intelligence | Operational |
| Monitoring | Operational |
| Investigations | Operational + Decision-support |
| Reporting | Analytical (+ export for operational briefings) |
| Historical Analysis | Analytical |
| Compliance | Decision-support (+ operational views) |
| Administration | Administrative |

---

## 7. Future Extensibility

New forest incident categories **SHALL** extend existing capabilities — not create new
product modules. Extension follows the domain plug-in sequence
(`docs/architecture/06-domain-plugin-architecture.md` §5):

| Extension step | Capability affected |
|----------------|---------------------|
| Register observation provider | **Monitoring**, **Administration** |
| Add incident category and taxonomy | **Intelligence**, **Administration** |
| Register spatial overlays | **Monitoring**, **Compliance**, **Administration** |
| Register detector | **Intelligence** |
| Register aggregator and report sections | **Command Center**, **Reporting** |
| Configure domain catalog entry | **Command Center**, **Administration** |
| Investigation workflow | **Unchanged** — binds to new category automatically |

Users **SHALL** experience a new category (e.g. pest outbreak, storm damage) as new
content within Monitoring, Intelligence, Command Center, Investigations, Reporting,
Compliance, and Historical Analysis — not as a new product.

Categories listed in `docs/architecture/08-roadmap.md` §8 (non-forest) **MUST NOT** be
added to any capability as product scope.

---

## 8. Architectural Alignment

| Product capability | Architecture bounded context / basis | Primary ADRs and invariants |
|--------------------|--------------------------------------|----------------------------|
| Monitoring | Ingestion; Spatial enrichment on observations | ADR-003; INV-12, INV-15 |
| Intelligence | Intelligence Engine (detection, reconciliation) | ADR-001, ADR-002, ADR-004, ADR-006, ADR-009, ADR-011; INV-1, INV-3, INV-4, INV-16 |
| Investigations | Investigation bounded context | ADR-005 §3.7, ADR-006; INV-13 |
| Reporting | Reporting subsystem | ADR-005 §3.5, ADR-007; INV-11 |
| Command Center | Command Center read-only projection | ADR-005 §3.4, §3.8; `07-reporting-and-command-center.md` |
| Compliance | Product composition (no separate BC) | ADR-003, ADR-005, INV-13 |
| Historical Analysis | Product composition (read-only temporal) | INV-4 |
| Administration | Cross-cutting configuration | ADR-005, ADR-010, ADR-007 |

**Notes:**

- **Spatial Engine** (ADR-003) is implementation architecture that enriches observations;
  it appears within Monitoring and Intelligence inputs, not as a separate user-facing
  capability.
- **Notifications** (`09-system-context.md` §3.10) are an architecture subsystem, not a
  separate entry in this capability catalog; they alert users across operational capabilities.
- **Scheduler** (ADR-007) orchestrates cycles; it is not a user-facing product capability.

---

## 9. Product Evolution (Phases 0–3)

Capabilities evolve in richness and category coverage; capability set and boundaries
**SHALL** remain stable.

### Phase 0 — Engine Generalization

| Capability | Evolution |
|------------|-----------|
| Intelligence | Generalized multi-category engine; wildfire category preserved |
| Command Center, Reporting | Consume generalized aggregation |
| Monitoring, Investigations, Administration | No structural change |
| Compliance, Historical Analysis | Inherit engine generalization transparently |

User-visible: wildfire workflows unchanged; foundation for all categories.

### Phase 1 — Spatial Engine Generalization

| Capability | Evolution |
|------------|-----------|
| Monitoring | Richer spatial context on observations |
| Intelligence | Enriched evidence metadata |
| Compliance | Standard protected-area and land-cover context |
| Administration | Overlay and polygon provider configuration |
| Others | No structural change |

User-visible: situations carry clearer geographic and jurisdictional meaning.

### Phase 2 — First Human Activity Domain (Forest Loss)

| Capability | Evolution |
|------------|-----------|
| Monitoring | Forest-loss observation sources visible |
| Intelligence | Forest-loss category live |
| Command Center | Second category in aggregation |
| Reporting | Forest-loss report sections registered |
| Compliance | Protected-area and loss compliance views |
| Investigations | Forest-loss cases; workflow unchanged |

User-visible: two forest categories operational in one product.

### Phase 3 — Surface Layer

| Capability | Evolution |
|------------|-----------|
| Command Center | Full multi-category domain catalog activated |
| Intelligence, Monitoring | Map-integrated category exploration |
| Reporting, Investigations, Compliance, Historical Analysis | Category-filtered views |
| Administration | Category and filter configuration for surface layer |

User-visible: Version 1.0.0 product — Forest Intelligence Platform, not a single-category tool.

**Post–Phase 3:** Additional forest categories from `08-roadmap.md` §7 extend all
capabilities through registration without new modules.

---

## 10. Non-Goals

This document **deliberately excludes**:

| Excluded | Reason |
|----------|--------|
| **Microservices or distributed product decomposition** | Product capabilities are logical; deployment shape is implementation |
| **Implementation details** | Code, modules, services, repositories — see as-built and engineering docs |
| **APIs and endpoints** | Interface contracts are implementation |
| **Database schemas and collection names** | Persistence is implementation |
| **UI mockups and wireframes** | Presentation design is separate |
| **Investigation workflow stages** | Defined in `INVESTIGATION_FRAMEWORK.md` |
| **Pricing and editions detail** | Defined in `PRODUCT_STRATEGY.md` §9 |
| **Non-forest environmental capabilities** | Outside Forest Intelligence Platform scope |
| **Autonomous enforcement or legal findings** | Prohibited by INV-13 and product boundaries |

---

## Document Control

| Field | Value |
|-------|-------|
| Created | 2026-07-17 |
| Status | Pending review |
| Related product | `PRODUCT_STRATEGY.md`, `INVESTIGATION_FRAMEWORK.md` |
| Related business | `BUSINESS_STRATEGY.md` |
| Related architecture | `00-platform-vision.md`, `02-intelligence-engine.md`, `06-domain-plugin-architecture.md`, `07-reporting-and-command-center.md`, `08-roadmap.md`, `09-system-context.md`, `10-dependency-rules.md` |

---

*End of Platform Capabilities.*
