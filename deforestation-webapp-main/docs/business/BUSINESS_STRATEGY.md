# ForestWatch — Business Strategy

**Status:** Strategic document — pending review.
**Audience:** Leadership, product, engineering, and commercial stakeholders.
**Authority:** This document defines the long-term commercial direction of ForestWatch.
It is subordinate to the frozen architecture in `docs/architecture/` and its ADRs. Where
commercial strategy and architecture disagree, architecture governs product and platform
capability. This document does not modify architecture, engineering specifications, or
implementation plans.

**Document type:** Business strategy. This is not a business plan, marketing document,
or pitch deck. It contains no financial projections and no market-size estimates.

---

## 1. Executive Summary

ForestWatch is a **Forest Intelligence Platform** — a system that understands, monitors,
investigates, explains, and reports changes affecting forest ecosystems. It transforms
high-volume forest-related observations into a small, stable, and actionable set of tracked
situations across the many incident categories that describe different aspects of the same
forest ecosystem.

The platform is designed to serve organizations responsible for forest stewardship —
governments, conservation bodies, forestry operators, and land managers — who must monitor,
understand, and respond to forest change over large geographies and long time horizons.

The commercial thesis is straightforward: forest ecosystems face growing pressure from
loss, degradation, fire, illegal activity, disease, and compliance failure, while the tools
available to most organizations remain fragmented, category-specific, and difficult to
operationalize. ForestWatch addresses this gap by providing a unified forest intelligence
layer — not another data feed, dashboard, or single-purpose monitoring application.

The platform's current implementation delivers a mature wildfire intelligence pipeline
with reporting, investigations, and a command center. Architecture v1.0 and the phased
engineering roadmap define how this foundation generalizes into a multi-category forest
platform without redesigning the core engine. Commercial success depends on executing that
roadmap disciplinedly, onboarding forest incident categories that create measurable
operational value, and building trust through deterministic, auditable intelligence.

ForestWatch shall not be positioned or developed as a wildfire alert system, a
deforestation-only tool, or a generic environmental monitoring platform. Wildfire is one
observation domain and one detector among many. Deforestation and forest loss are
categories within the platform, not the platform itself.

---

## 2. Vision

**A world where change in forest ecosystems is understood as intelligence — not as noise.**

ForestWatch exists so that governments, conservation organizations, forestry agencies, and
land managers can move from reactive, fragmented forest monitoring to sustained, cross-
category forest intelligence: a continuously updated picture of what is happening in forest
ecosystems, where it is happening, how it is evolving, and what requires human attention.

The long-term vision is a platform that:

- spans the full spectrum of forest incident categories — loss, fire, degradation, disease,
  compliance, and ecosystem health — through a single shared intelligence pipeline;
- preserves trust through deterministic, reproducible analytics;
- supports human judgment through investigations rather than replacing it;
- grows by extension — new forest categories, sources, and geographies — without
  architectural reinvention;
- serves as the operational intelligence layer between raw forest observations and
  organizational response.

The architecture in `docs/architecture/00-platform-vision.md` defines the intelligence
engine, extension model, and platform guarantees that make this vision technically
achievable. The commercial identity defined here scopes that engine exclusively to forest
ecosystems. ForestWatch is not a generic environmental platform; it is forest intelligence
applied through a domain-independent engine.

---

## 3. Mission

**Understand, monitor, investigate, explain, and report changes affecting forest
ecosystems — transforming forest observations into actionable intelligence that
organizations can trust and act upon.**

ForestWatch fulfills this mission through three operational commitments that mirror the
platform thesis defined in architecture (Observe → Derive → Act):

1. **Observe** — ingest and normalize forest-related observations from diverse external
   and internal sources at the platform boundary, preserving provenance and spatial context.
2. **Derive** — reconcile observations into tracked Intelligence Events through a single,
   category-independent engine that scores, escalates, and maintains lifecycle state
   deterministically.
3. **Act** — surface intelligence through the Command Center, reports, and notifications;
   enable structured human response through investigations; never substitute automated
   conclusions for legally or ethically loaded human judgment.

Every commercial product decision shall support this mission within forest ecosystem
scope. Features that increase data volume without improving forest intelligence quality,
operational clarity, or response capability are out of mission scope. Capabilities
outside forest ecosystems — such as air quality, marine monitoring, urban pollution, or
general water management — belong to separate future products, not to ForestWatch.

---

## 4. Core Problem Statement

Organizations responsible for **forest stewardship** face a structural problem:
**observation volume is increasing faster than operational comprehension.**

### 4.1 Fragmentation

Environmental monitoring tools are typically built per category — wildfire systems, forest-
loss alerts, pest monitoring, compliance dashboards — each with its own data model, alert
logic, and user interface. Operators managing forest ecosystems must correlate manually
across systems that were never designed to interoperate.

### 4.2 Signal-to-noise collapse

Raw observation feeds — satellite detections, sensor readings, import files, scraped
reports — produce high event volume with low immediate actionability. Without a
reconciliation layer that maintains persistent, scored, lifecycle-managed situations,
operators either miss important changes or drown in alerts that reset on every data pull.

### 4.3 Trust and auditability deficit

Many environmental analytics systems embed non-deterministic behavior, opaque scoring, or
write-on-read side effects that make outputs difficult to reproduce, audit, or defend in
regulatory or legal contexts. Organizations that must justify decisions require
intelligence they can explain.

### 4.4 Extension cost

Adding a new **forest incident category** to an existing monitoring stack typically
requires new pipelines, new alert logic, and new UI — duplicating engineering effort and
increasing long-term maintenance cost. Platforms that hard-code category assumptions
cannot scale across the full spectrum of forest ecosystem risk.

ForestWatch addresses these four problems through a unified **Forest Intelligence
Platform**, not through incremental feature additions to a single-category tool.

---

## 5. Market Opportunity

This section describes the commercial opportunity qualitatively. **No market-size
estimates or financial projections are stated.** Where quantitative claims would
normally appear, strategic assumptions are identified explicitly.

### 5.1 Opportunity shape

The addressable opportunity lies at the intersection of:

- organizations with **geographic forest responsibility** (national, regional, or
  site-level);
- environments where **remote sensing and automated detection** produce actionable signals;
- operational contexts where **persistent situational awareness** is more valuable than
  one-time reports or static dashboards.

*Strategic assumption:* Demand for **forest intelligence** will grow as observation
data becomes cheaper and more available, while organizational capacity to interpret that
data does not scale proportionally.

### 5.2 Domains of initial relevance

Based on the architecture roadmap and current implementation maturity, the nearest
commercial domains are:

| Forest incident category | Architecture alignment | Current platform state |
|--------------------------|------------------------|------------------------|
| Wildfire / Forest Health | Mature pipeline; Phase 0 generalizes engine | Implemented |
| Human Activity (forest loss) | Phase 2 onboarding target | Planned |
| Environmental Conditions (pests, storm, disease) | Future forest category via plug-in architecture | Not started |
| Additional forest categories (§7, `08-roadmap.md`) | Future forest product scope via extension | Not started |

*Strategic assumption:* Human Activity intelligence (forest loss, land-use change) is the
strongest near-term commercial expansion after engine generalization, because it shares
spatial and temporal patterns with the existing wildfire domain and addresses a widely
recognized operational need.

### 5.3 Geographic focus

The current implementation includes Romania-specific enrichment and seed data. The
platform architecture is not geographically limited.

*Strategic assumption:* Initial commercial traction will concentrate on geographies where
(a) remote-sensing and alert data sources are accessible, (b) regulatory or conservation
pressure creates operational demand, and (c) the organization has capacity to act on
intelligence rather than merely consume reports.

No specific geography is claimed as validated market entry at this stage.

### 5.4 What this section deliberately excludes

- TAM/SAM/SOM estimates
- Revenue forecasts
- Growth rate statistics
- Competitor market-share figures

These require primary research and are outside the scope of this strategy document.

---

## 6. Platform Positioning

### 6.1 Category definition

ForestWatch occupies the category **Forest Intelligence Platform** — distinct from:

| Adjacent category | How ForestWatch differs |
|-------------------|-------------------------|
| GIS / mapping platform | ForestWatch derives and maintains tracked forest situations; it is not primarily a visualization or data-layers tool |
| Single-category alert system (fire-only, loss-only) | ForestWatch supports multiple forest incident categories through one engine; wildfire is one detector among many |
| Generic environmental intelligence platform | ForestWatch is scoped exclusively to forest ecosystems, not to air, marine, urban, or general environmental domains |
| Deforestation monitoring application | Forest loss is one category within a broader forest intelligence scope |
| Data marketplace / feed aggregator | ForestWatch normalizes and reconciles; it does not merely resell raw observations |
| General-purpose BI / analytics | ForestWatch is purpose-built for geospatial forest lifecycle intelligence with deterministic scoring |
| Research / academic tooling | ForestWatch is designed for sustained operational use, investigations, and command-center workflows |

### 6.2 Forest intelligence scope

ForestWatch covers the incident categories that describe different aspects of the same
forest ecosystem. The long-term scope includes, without being limited to:

- Forest loss and illegal logging
- Tree theft
- Wildfires
- Forest degradation
- Storm damage
- Pest outbreaks and forest diseases
- Protected-area violations within forest contexts
- Habitat fragmentation
- Reforestation monitoring
- Biodiversity within forests
- Carbon forests and forest carbon compliance
- Forest compliance and forest ecosystem health

Each category is onboarded through the architecture's domain plug-in and detector
framework (ADR-004, ADR-005). Wildfire is an observation domain and a detector — not
the product.

**Explicitly outside ForestWatch strategic scope** — and reserved for potential future
independent products:

- Air quality
- Marine environments and oceans
- Urban pollution
- Water management and general water quality
- Climate intelligence outside the forest ecosystem

*Strategic assumption:* Organizations needing both forest intelligence and unrelated
environmental monitoring will prefer integrated suites from separate specialized products
rather than a single diluted platform.

### 6.3 Positioning statement

**For organizations responsible for forest stewardship across large or complex geographies,
ForestWatch is the Forest Intelligence Platform that transforms multi-source forest
observations into persistent, scored, auditable tracked situations — so teams can
understand, monitor, investigate, explain, and report forest ecosystem change without
correlating fragmented single-category alerts.**

### 6.4 Positioning constraints (architectural)

The following positioning boundaries are non-negotiable and derive from architecture
invariants:

- ForestWatch **derives** intelligence; it does not author conclusions.
- ForestWatch **does not** replace human judgment for legally or ethically loaded
  determinations (investigations quarantine those conclusions per INV-13).
- ForestWatch **does not** position as an autonomous enforcement or prosecution system.
- ForestWatch **does not** claim predictive certainty beyond what deterministic analytics
  and configured detectors support.
- ForestWatch **does not** expand commercial scope beyond forest ecosystems without a
  deliberate product and architecture decision recorded through the ADR process.

The architecture taxonomy in `docs/architecture/00-platform-vision.md` and future forest
categories in `docs/architecture/08-roadmap.md` §7 describe product scope. Engine
extensibility for non-forest categories is documented in `08-roadmap.md` §8 as
**architectural extension capability, not product scope**.

---

## 7. Why ForestWatch Exists

ForestWatch exists because the forest monitoring industry has optimized for **data
acquisition** at the expense of **operational forest intelligence**.

Organizations responsible for forests already have access to observation data — satellite
feeds, fire detections, forest-loss alerts, CSV imports, field reports, government APIs.
What they lack is a system that:

1. **Maintains state** — tracking a forest situation across cycles rather than re-alerting
   from scratch on every pull.
2. **Segments by incident category without contamination** — so forest-loss signals do
   not corrupt wildfire baselines, pest signals do not mask degradation trends, and vice
   versa.
3. **Scales by extension** — so adding a forest category (disease, compliance, theft) is
   configuration and registration, not a new product rebuild.
4. **Produces auditable output** — deterministic analytics that can be reproduced and
   defended in regulatory, conservation, or legal-adjacent contexts.
5. **Connects intelligence to action** — through investigations, reports, notifications,
   and a command center designed for forest operators, not analysts alone.

ForestWatch is the platform layer that sits between raw forest observations and
organizational response. Without this layer, data volume increases operational burden
rather than reducing it — and forest stewards continue to correlate fire systems, loss
alerts, and compliance tools manually while the ecosystem degrades unnoticed between
categories.

---

## 8. Long-term Competitive Advantages

These advantages derive from architectural decisions documented in Architecture v1.0 and
its ADRs. They are structural, not marketing claims. ForestWatch competes as a **forest-
vertical intelligence platform** — not as a horizontal environmental tool.

### 8.1 Unified forest intelligence engine

A single reconciliation authority, canonical identity model, and category-independent
scoring engine (ADR-001, ADR-002, INV-3) means all forest incident categories share one
lifecycle semantics. Competitors built as collections of single-category tools — fire
systems, loss alerts, compliance dashboards — cannot achieve cross-category forest
intelligence without fundamental rearchitecture.

### 8.2 Extension-without-modification within forest scope

The domain plug-in architecture (ADR-005, INV-10) means new forest incident categories are
added through registration — providers, detectors, aggregators, report sections — without
editing engine internals. This reduces time-to-market for categories such as pest
outbreak, storm damage, or forest compliance and lowers long-term maintenance cost
relative to forked forest-monitoring pipelines.

### 8.3 Deterministic, auditable analytics

Deterministic analytics (INV-4) and idempotent reconciliation (INV-16) produce
reproducible outputs given identical inputs. For forest customers in regulatory,
conservation, or legal-adjacent contexts — illegal logging investigations, protected-
area compliance, carbon forest reporting — explainability is a procurement requirement,
not a feature nice-to-have.

### 8.4 Spatial intelligence as a shared forest service

The Spatial Engine (ADR-003, INV-9) consolidates geospatial computation for forest
context: protected areas, land cover, forest boundaries, jurisdictions. Forest categories
share enrichment and overlay logic rather than reimplementing geometry operations. This
compounds as forest spatial datasets accumulate across deployments.

### 8.5 Operational workflow integration

Investigations, reporting, and the Command Center are first-class bounded contexts — not
afterthoughts bolted onto a map. This integrates forest intelligence into organizational
workflow — field investigation, compliance reporting, operational briefing — rather than
leaving it as a standalone dashboard.

### 8.6 Multi-tenancy readiness

The reserved `tenant` identity dimension (ADR-010) positions the platform for commercial
multi-organization deployment — forestry agencies, NGO networks, commercial operators —
without a late, costly identity and persistence migration, provided multi-tenancy is
implemented when the first such deployment requires it.

### 8.7 Compounding forest configuration assets

Each onboarded forest category, spatial overlay, detector configuration, and investigation
workflow adds to the platform's operational asset base. Because intelligence is derived
from observations plus configuration — not hard-coded per customer — operational knowledge
of forest monitoring accumulates in reusable platform configuration rather than in
bespoke code.

### 8.8 Scope discipline as strategic moat

By refusing to dilute into generic environmental monitoring, ForestWatch concentrates
product depth, detector libraries, spatial overlays, and customer workflows on forest
ecosystems. Horizontal environmental platforms spread thin; ForestWatch compounds
vertical expertise in a category with sustained regulatory, conservation, and commercial
demand.

*Strategic assumption:* These structural advantages translate to commercial advantage
only if the engineering roadmap is executed and customers value auditable, multi-category
forest operational intelligence over simpler single-category tools or generic
environmental dashboards.

---

## 9. Target Customer Categories

Customer categories are defined by **operational need**, not by industry labels alone.
The following categories are strategic targets; none is claimed as an existing customer
base at this stage.

### 9.1 Government agencies and forestry authorities

Organizations with statutory responsibility for forest health, land use, fire management,
or forest compliance across defined jurisdictions — including national ministries, regional
forestry administrations, and forest guard services.

**Primary need:** Persistent situational awareness, auditable intelligence, cross-category
visibility, exportable reports for internal and inter-agency communication.

*Strategic assumption:* Procurement cycles are long; trust and auditability are decisive
factors.

### 9.2 Environmental NGOs

Organizations monitoring protected areas, forest biodiversity, and human activity impacts
across multiple sites or regions.

**Primary need:** Affordable multi-category forest monitoring, investigation workflows for
field teams, alert routing, evidence preservation for advocacy and grant reporting.

*Strategic assumption:* Budget sensitivity is high; value must be demonstrable without
large implementation teams.

### 9.3 Corporate forestry

Companies managing forestry assets, commercial forest estates, or extractive operations
with forest compliance obligations.

**Primary need:** Early detection of anomalies affecting operational or compliance
status, documented investigation trails, integration with existing operational rhythms.

*Strategic assumption:* Willingness to pay correlates with direct financial or regulatory
exposure from undetected forest incidents.

### 9.4 Certification organizations

Forest certification bodies, audit firms assessing forest management practices, and
assurance providers evaluating chain-of-custody or carbon forest claims.

**Primary need:** Reproducible intelligence, exportable point-in-time reports, and
investigation records that support assessment without substituting for auditor judgment.

*Strategic assumption:* Certification bodies may consume reports and exports rather than
operate full monitoring workflows daily.

### 9.5 Research institutions

Academic, inter-agency, or multi-stakeholder programs that produce or consume forest
observation data and need an operational layer above raw datasets.

**Primary need:** Reproducible analytics, multi-source ingestion, exportable artifacts,
and historical analysis for publication and grant reporting.

*Strategic assumption:* Research customers may prefer flexibility over polished UX;
commercial pricing models may differ from operational customers.

### 9.6 Platform and integration partners

Organizations that embed **forest intelligence** into broader systems — forestry
management platforms, supply-chain traceability, insurance risk tools, or emergency
coordination systems with forest mandate.

**Primary need:** Stable integration contracts, deterministic outputs, forest category
extensibility, white-label or embedded deployment options.

*Strategic assumption:* Partner revenue may be indirect (licensing, integration fees) and
requires multi-tenancy and integration maturity not yet implemented.

### 9.7 Explicit non-targets (current stage)

- Consumer / general-public alert applications
- Retail environmental lifestyle products
- Autonomous enforcement or legal-evidence systems without human investigation workflow
- Pure data reselling without intelligence layer

---

## 10. Revenue Model Overview

This section describes **revenue model categories**, not pricing, forecasts, or
financial targets. Specific pricing requires market validation and is deferred.

### 10.1 Primary model directions

| Model | Description | Fit |
|-------|-------------|-----|
| **Subscription (SaaS)** | Recurring fee for platform access scoped by geography, domain, user seats, or data volume tier | Operational customers with sustained monitoring need |
| **Enterprise license** | Annual or multi-year license for self-hosted or dedicated deployment | Government and large operators with data-sovereignty requirements |
| **Domain/module add-ons** | Additional fee per onboarded forest incident category or premium spatial overlay | Aligns with plug-in architecture; customers pay as scope expands |
| **Professional services** | Implementation, custom domain onboarding, training, investigation workflow design | Early-stage deployments before self-service maturity |
| **API / integration access** | Usage-based or tiered access for partner embedding | Requires API stability and multi-tenancy maturity |

### 10.2 Freemium commercial model

ForestWatch **SHALL** pursue a **freemium commercial model** aligned with
`docs/business/EDITION_STRATEGY.md` and `docs/business/GO_TO_MARKET_STRATEGY.md`:

| Layer | Commercial role |
|-------|-----------------|
| **Public transparency** | Deliberate trust asset — open derived intelligence, reports, and maps build credibility and widen awareness without account or payment |
| **Community Edition** | Deliberate funnel asset — free registered personal access for individual evaluation and bounded exploration |
| **Professional and Enterprise** | Revenue capture — organizational operations, investigations, collaboration, compliance, integration, automation, and private deployment |

Public intelligence and Community Edition **SHALL NOT** substitute for paid operational
capability. Revenue **SHALL** capture **operational, organizational, integration, and
deployment** value — not unrestricted access to public transparency scope.

### 10.3 Revenue principles

1. **Price on operational intelligence value, not raw data volume alone.** Public
   transparency and Community Edition provide derived situational awareness at no charge;
   paid revenue reflects reconciliation, lifecycle, and organizational operational
   workflow — not terabytes ingested alone.
2. **Category expansion is a natural upsell path.** Each new forest incident category
   registered on the platform represents incremental commercial scope aligned with
   architecture.
3. **Trust is a premium attribute.** Deterministic, auditable analytics may justify
   higher pricing in regulatory-adjacent segments — *strategic assumption, not validated*.
4. **Services bridge the maturity gap.** Until self-service onboarding exists, professional
   services will likely subsidize platform development — *strategic assumption*.

### 10.4 What this section deliberately excludes

- Price points
- ARR/MRR targets
- Customer acquisition cost
- Lifetime value calculations
- Funding requirements

---

## 11. Product Evolution Strategy

Product evolution **must** follow the architectural roadmap
(`docs/architecture/08-roadmap.md`). Commercial priorities shall not reorder engineering
phases in ways that violate phase dependencies or onboard domains before the engine can
support them without corrupting existing domains.

### 11.1 Phase-aligned product evolution

| Architecture phase | Product capability unlocked | Commercial implication |
|--------------------|----------------------------|----------------------|
| **Phase 0 — Engine Generalization** | Multi-category-ready engine; wildfire behavior preserved | Platform credibility; foundation for all future forest categories |
| **Phase 1 — Spatial Engine** | Reusable spatial enrichment and overlays | Protected areas, land cover, jurisdiction context for any forest category |
| **Phase 2 — Human Activity Domain** | Forest-loss intelligence as second category | First commercial expansion beyond wildfire; deforestation/land-use positioning |
| **Phase 3 — Surface Layer** | Map layers, filters, category watch cards, Command Center activation | First user-visible multi-category product (Version 1.0.0 target per release notes) |
| **Future forest categories** | Pest/disease, storm damage, carbon compliance, fragmentation, etc. (§7, `08-roadmap.md`) | Progressive forest product expansion through extension, not rebuild |

### 11.2 Product principles

1. **Engine before category.** Never commercialize a forest category before the engine supports it.
2. **Extension before modification.** New capabilities arrive through registration and
   configuration.
3. **Operational depth before feature breadth.** A reliable wildfire + forest-loss
   operational workflow outweighs a shallow multi-category demo.
4. **Investigations are the human layer.** Product shall always preserve the distinction
   between derived intelligence and human conclusions.
5. **Command Center is the daily surface.** Reporting is the export/audit surface. Map is
   the spatial exploration surface. All three are projections, not intelligence engines.
6. **Freemium before monetization.** Public transparency and Community Edition establish
   trust and individual evaluation paths; organizational revenue follows Professional and
   Enterprise adoption (§10.2).

### 11.3 Delivery roadmap relationship

The product delivery roadmap (`docs/ROADMAP.md`, Delivery Phases 1–9) tracks feature
and integration milestones (FIRMS ingestion, scheduler, UI, data sources). The
architectural phase roadmap governs **intelligence platform capability**. Both must
advance, but architectural phase completion is the binding constraint on domain
commercialization.

*Strategic assumption:* Customers will accept phased domain availability if the platform
demonstrates clear operational value in the first one or two domains.

---

## 12. Network Effects (if applicable)

ForestWatch is primarily a **vertical intelligence platform**, not a consumer network.
Traditional user-to-user network effects are limited. However, several **data and
ecosystem effects** may apply as the platform scales.

### 12.1 Spatial overlay accumulation

Each polygon provider and spatial overlay registered on the Spatial Engine (protected
areas, jurisdictions, land cover, custom boundaries) benefits all domains that consume
spatial enrichment. New customers in a geography may inherit overlay configuration
already built for others — reducing onboarding cost over time.

*Strategic assumption:* Overlay assets can be shared or templated across customers without
violating data-licensing constraints.

### 12.2 Detector and threshold configuration library

As more domains and geographies are operationalized, detector configurations and
per-category thresholds form a reusable library. Operational knowledge encoded in
configuration — not bespoke code — compounds across deployments.

### 12.3 Source and provider ecosystem

Each ingestion provider integrated (FIRMS, GLAD, government APIs, CSV, scrapers) expands
the observation surface for all domains. Provider integration is a platform asset, not a
per-customer cost.

### 12.4 Cross-domain correlation (future)

The architecture recognizes a future cross-domain correlation layer over Intelligence
Events. If implemented, situations that span domains (e.g., fire followed by logging in the
same region) would become visible only on a unified platform — a effect that
single-domain tools cannot replicate.

*Strategic assumption:* Cross-domain correlation becomes commercially meaningful only
after at least two domains are operational on the same geography.

### 12.5 Limitations

- ForestWatch does **not** rely on user-generated content network effects.
- Multi-tenancy is not yet implemented; cross-customer data sharing is **not** assumed
  and would require explicit architectural and contractual design.
- Network effects are **secondary** to product correctness and trust; they shall not
  drive architecture decisions prematurely.

---

## 13. Strategic Risks

### 13.1 Engineering and product risks

| Risk | Description | Mitigation direction |
|------|-------------|---------------------|
| **Engine generalization failure** | Phase 0 does not preserve wildfire behavioral equivalence | Golden oracle regression gates; engineering protocol enforcement |
| **Domain onboarding delay** | Phase 2/3 take longer than commercial timeline assumes | Services revenue bridge; narrow initial geographic scope |
| **Single-category perception** | Market continues to perceive ForestWatch as a wildfire tool | Positioning discipline; Phase 3 multi-category surface as proof point |
| **Self-service gap** | Platform requires engineering effort per deployment | Professional services; progressive self-service tooling |

### 13.2 Market and commercial risks

| Risk | Description | Mitigation direction |
|------|-------------|---------------------|
| **Long government sales cycles** | Revenue timing unpredictable in primary target segment | Diversify across NGO and commercial segments; services revenue |
| **Free public data alternatives** | Customers use raw NASA/GFW feeds without intelligence layer | Compete on operational workflow, persistence, auditability — not data access alone |
| **Incumbent GIS platforms** | Esri and similar expand into alert/intelligence features | Differentiate on deterministic reconciliation and multi-category engine, not mapping |
| **Budget constraints in NGO segment** | Price sensitivity limits revenue per customer | Tiered offering; geographic scope limits; grant-aligned pricing *— assumption* |

*Strategic assumption:* Competitive responses from incumbents will accelerate as the
**forest intelligence** product category matures.

### 13.3 Trust and regulatory risks

| Risk | Description | Mitigation direction |
|------|-------------|---------------------|
| **False positive / alert fatigue** | Poor detector tuning erodes operator trust | Deterministic thresholds; per-category configuration; investigation workflow |
| **Legal misuse of intelligence output** | Customers treat derived intelligence as legal evidence without investigation | Product positioning; investigation quarantine (INV-13); export disclaimers |
| **Data licensing constraints** | Third-party data sources restrict commercial use or redistribution | Provider-level license tracking; customer responsibility boundaries in contracts |

### 13.4 Organizational risks

| Risk | Description | Mitigation direction |
|------|-------------|---------------------|
| **Architecture drift under commercial pressure** | Sales commitments force domain shortcuts that violate invariants | Implementation Protocol stop conditions; architecture gate reviews |
| **Premature multi-tenancy or infrastructure** | Commercial demand drives Redis, microservices, or tenant isolation before ADR approval | ADR process; non-goals in Implementation Protocol |
| **Team capacity** | Engineering roadmap exceeds available capacity | Strict phase sequencing; defer future domains until prior phase complete |

---

## 14. Five-Year Strategic Objectives

These objectives define directional targets for approximately 2026–2031. They are
**strategic objectives**, not financial commitments. Progress shall be measured against
Section 15 success metrics.

### Year 1 (2026–2027) — Foundation

1. Complete Phase 0 engine generalization with verified wildfire behavioral equivalence.
2. Complete Phase 1 Spatial Engine generalization.
3. Onboard Human Activity domain (Phase 2) with forest-loss intelligence operational in
   at least one geography.
4. Ship Version 1.0.0 surface layer (Phase 3) with multi-category Command Center.
5. Establish first operational deployment (paid or pilot) with documented investigation
   workflow in use.

### Year 2 (2027–2028) — Validation

1. Demonstrate second geography or second customer segment without engine modification.
2. Implement multi-tenancy when first multi-organization deployment requires it (ADR-010).
3. Expand ingestion providers (beyond FIRMS and CSV) aligned with Delivery Roadmap.
4. Achieve self-service onboarding for at least one domain/geography configuration template.
5. Publish auditable report exports used in at least one external stakeholder process.

### Year 3 (2028–2029) — Expansion

1. Onboard third **forest incident category** through plug-in architecture (candidate:
   pest/disease or forest degradation — subject to market validation).
2. Activate cross-category visibility in Command Center for all onboarded forest
   categories.
3. Establish partner/integration channel with stable API access.
4. Reduce professional-services dependency for standard deployments.

### Year 4 (2029–2030) — Scale

1. Operate platform across multiple tenants with domain-scoped authorization.
2. Onboard at least two additional **forest incident categories** from `08-roadmap.md` §7.
3. Introduce pipeline observability and operational metrics as a product capability.
4. Evaluate cross-domain correlation layer for commercial differentiation.

### Year 5 (2030–2031) — Platform maturity

1. ForestWatch recognized (within target segments) as a **Forest Intelligence Platform**,
   not a single-category tool.
2. Category onboarding achievable through configuration and registration with minimal
   custom engineering.
3. Product evolution driven by forest category plug-ins and spatial overlays, not engine
   redesign.
4. Sustainable commercial model validated across at least two customer categories.

*Strategic assumption:* The five-year timeline is achievable with sustained engineering
investment and at least one successful early deployment that validates operational value.

---

## 15. Success Metrics

Success metrics are organized by category. Targets are **directional indicators**, not
financial quotas. Baselines will be established as the platform enters commercial
deployment.

### 15.1 Platform and engineering metrics

| Metric | Indicator of success |
|--------|---------------------|
| Phase completion on roadmap | Phases 0–3 complete per architecture roadmap |
| Golden oracle regression pass rate | 100% pass before each phase gate |
| Domain onboarding without engine edits | New forest category added via registration only |
| Deterministic output reproducibility | Identical inputs produce identical intelligence outputs in test and production |
| Engine uptime / cycle reliability | Scheduler cycles complete without data corruption |

### 15.2 Product and operational metrics

| Metric | Indicator of success |
|--------|---------------------|
| Active Intelligence Events under management | Non-trivial count of persistent tracked situations per deployment |
| Investigation completion rate | Human workflows initiated and closed on intelligence events |
| Command Center daily active use | Operators return to Command Center as primary situational surface |
| Report export frequency | Reports generated and used in external processes |
| Time from observation to tracked situation | Cycle latency within agreed operational bounds |

### 15.3 Commercial metrics (qualitative until baselines exist)

| Metric | Indicator of success |
|--------|---------------------|
| Paying or committed pilot customers | At least one per target category within five years |
| Domain expansion revenue | Customers add forest categories or geographies after initial deployment |
| Services-to-subscription ratio | Declining over time as self-service matures |
| Customer retention | Renewals or continued pilot expansion *— requires baseline* |
| Partner integrations | At least one embedded or API integration *— Year 3+ target* |

### 15.4 Trust and quality metrics

| Metric | Indicator of success |
|--------|---------------------|
| False-positive rate per domain | Below operator-defined threshold; tracked per category |
| Audit reproducibility | Customer can reproduce intelligence output from documented inputs |
| Investigation evidence integrity | Investigation records link to intelligence events without orphaning |

### 15.5 Metrics explicitly deferred

The following require commercial baselines not yet available and **shall not** be
reported until data exists:

- Annual recurring revenue
- Customer acquisition cost
- Net revenue retention
- Market share
- Net promoter score

---

## Document Control

| Field | Value |
|-------|-------|
| Created | 2026-07-17 |
| Status | Pending review |
| Reconciliation | CMR-004 applied 2026-07-22 |
| Related architecture | `docs/architecture/00-platform-vision.md`, `08-roadmap.md`, ADR-005, ADR-010 |
| Related business | `docs/business/EDITION_STRATEGY.md`, `docs/business/GO_TO_MARKET_STRATEGY.md` |
| Related engineering | `docs/engineering/IMPLEMENTATION_PROTOCOL.md`, Phase 0 specification |
| Next documents | None until this document is reviewed and approved |

---

*End of Business Strategy.*
