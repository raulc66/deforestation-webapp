# ForestWatch — Product Strategy

**Status:** Strategic document — pending review.
**Audience:** Product leadership, design, commercial teams, and customer-facing stakeholders.
**Authority:** This document defines ForestWatch as a **commercial product**. Its identity
is **Forest Intelligence Platform** — consistent with `docs/business/BUSINESS_STRATEGY.md`
and `docs/architecture/00-platform-vision.md` §2.1. The domain-independent intelligence
engine described in architecture documents is **implementation architecture**, not product
identity. This document is subordinate to business strategy for commercial direction and
to `docs/architecture/` and its ADRs for platform capability boundaries. Where product
scope and architecture disagree, architecture governs what the product may do; business
strategy governs what the product shall pursue commercially. Edition capability
boundaries and free/paid rules are authoritative in `docs/business/EDITION_STRATEGY.md`
per `docs/DOCUMENT_HIERARCHY.md` §4.2; §9 below is product-oriented overview only.

**Document type:** Product strategy. This is not a business plan, technical specification,
marketing brochure, or implementation roadmap. It contains no pricing, financial
projections, or implementation detail.

**Relationship to Business Strategy:** `docs/business/BUSINESS_STRATEGY.md` defines *why*
ForestWatch exists commercially, *who* the market is, and *how* the business competes.
This document defines *what* the product is, *who* uses it, *what problems* it solves for
each user segment, and *how* product capabilities evolve over time.

**Language:** The key words **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**,
**SHOULD NOT**, **MAY**, and **OPTIONAL** in this document are to be interpreted as
described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

**Terminology:** This document uses **forest incident category** for a class of forest
situation the product tracks (e.g. wildfire, forest loss, pest outbreak). Architecture
documents use **ecosystem domain grouping** for taxonomy organization; that is an
implementation concept, not a broader commercial scope. **Product module** names user-
facing capability areas; they map to architecture bounded contexts and may compose
multiple contexts (see §8).

---

## 1. Product Identity

ForestWatch is a **Forest Intelligence Platform** delivered as an operational product for
organizations responsible for forest ecosystems.

As a product, ForestWatch:

- **understands** forest change by reconciling diverse observations into persistent tracked
  situations;
- **monitors** forest ecosystems across incident categories — not a single threat type;
- **investigates** tracked situations through structured human workflows;
- **explains** intelligence through auditable evidence and reproducible scoring;
- **reports** forest status, incidents, and outcomes to internal and external stakeholders.

ForestWatch is **not** a wildfire product, a deforestation dashboard, a map viewer, or a
generic environmental monitoring suite. Wildfire is one incident category within the
product. Forest loss is one category. The product identity is the full forest ecosystem.

The product serves a single vertical — **forests** — with many incident categories that
describe different aspects of the same ecosystem. Categories the product shall support over
its lifetime include forest loss, illegal logging, tree theft, wildfire, degradation, storm
damage, pest and disease outbreaks, protected-area violations, habitat fragmentation,
reforestation, forest biodiversity, carbon forest compliance, and forest ecosystem health.

The product shall **not** expand into air quality, marine environments, urban pollution,
general water management, or climate intelligence outside forest ecosystems.

---

## 2. Product Vision

**Operators open ForestWatch each morning knowing what changed in their forests, what
requires attention, and what can wait — across every category that matters to their
mission.**

The product vision describes the daily experience of forest stewardship at scale:

- A forestry authority sees active situations ranked by operational priority, not a raw
  feed of satellite detections.
- A conservation team opens an investigation linked to a tracked situation with full
  evidence history, not a screenshot of a map.
- A compliance officer exports a point-in-time report that can be reproduced and defended,
  not a manually assembled spreadsheet.
- A corporate forester monitors asset compliance and loss across managed land without
  switching between fire, loss, and compliance tools.

The product shall make forest intelligence **continuous**, **cross-category**, and
**actionable** — replacing the daily burden of manual correlation across fragmented tools.

---

## 3. Product Principles

These principles govern product decisions. They derive from architecture invariants and
business strategy scope. Every product feature shall be evaluated against them.

### P-1 — Intelligence over data
The product shall prioritize tracked situations and their lifecycle over raw observation
volume. Users shall encounter intelligence first; observations shall be accessible as
evidence, not as the primary surface.

### P-2 — Category segmentation without contamination
The product shall present forest incident categories distinctly. Baselines, detections, and
tracked situations in one category shall not silently affect another. Users shall trust
that wildfire intelligence and forest-loss intelligence are independently sound.

### P-3 — Determinism and explainability
The product shall produce intelligence that can be explained. Given the same observations
and configuration, the product shall produce the same intelligence. Users shall be able to
answer *why* a situation exists, *why* it scored as it did, and *what* evidence supports it.

### P-4 — Human judgment is irreplaceable
The product shall derive intelligence; it shall not author legal, ethical, or enforcement
conclusions. Investigations are the product surface for human judgment. Derived intelligence
and human conclusions shall remain visibly distinct.

### P-5 — Extension, not reinvention
New forest categories shall appear as product capabilities through configuration and
registration. The product shall not require users to adopt a new tool when a new category
is added.

### P-6 — Operational first
The product shall be designed for sustained daily use by forest operators, not occasional
analysis by specialists. The Command Center shall be the primary operational surface;
reporting shall serve audit and communication; investigations shall serve response.

### P-7 — Forest scope discipline
The product shall deepen forest capability rather than broaden into unrelated environmental
domains. Scope expansion beyond forests requires explicit product and architecture review.

---

## 4. Core Product Capabilities

ForestWatch delivers five foundational capabilities that mirror the platform thesis
(Observe → Derive → Act). These are product-level descriptions, not technical components.

| Capability | Product meaning |
|------------|-----------------|
| **Observation intake** | Accept forest-related observations from configured sources; preserve provenance, location, time, and source identity. |
| **Situation derivation** | Transform observations into persistent, scored, lifecycle-managed tracked situations keyed by forest incident category and location. |
| **Operational awareness** | Present active situations, priorities, trends, and cross-category summaries for daily decision-making. |
| **Human response** | Enable structured investigation workflows bound to tracked situations, with assignment, status, outcome, and audit history. |
| **Communication and audit** | Compose point-in-time reports and exports for internal briefings, compliance, advocacy, and external stakeholders. |

All capabilities operate within forest ecosystem scope. The product shall not expose
capabilities that imply monitoring of non-forest environmental domains.

---

## 5. Target Users

ForestWatch serves organizations, not individual consumers. Users within each segment have
distinct roles, permissions, and daily workflows. The product shall accommodate these
differences through configuration, not through separate products.

### 5.1 Government agencies

**Organizations:** National and regional ministries, environmental agencies, civil
protection authorities with forest mandate, park services, and inter-agency coordination
bodies.

**Typical users:** Duty officers, regional coordinators, policy analysts, agency directors,
inter-agency liaisons.

**Product role:** Primary operational system for jurisdictional forest situational
awareness. The product shall support multi-region visibility, priority-ranked active
situations, scheduled reporting for briefings, and investigation coordination across
agency units.

**Edition fit:** Professional or Enterprise.

### 5.2 Forestry authorities

**Organizations:** State forestry administrations, forest management directorates, forest
guard services, and public forest estate managers.

**Typical users:** Forest inspectors, district foresters, fire management coordinators,
forest health specialists, estate managers.

**Product role:** Day-to-day forest operations — fire, loss, disease, compliance, and
estate health across managed public forest. The product shall support category-specific
monitoring, field investigation dispatch, and exportable records for administrative
proceedings.

**Edition fit:** Professional or Enterprise.

### 5.3 Environmental NGOs

**Organizations:** Conservation NGOs, land-trust networks, protected-area watchdogs, and
forest advocacy organizations.

**Typical users:** Field coordinators, protected-area managers, campaign researchers,
grant reporting officers.

**Product role:** Affordable sustained monitoring of priority forest areas; investigation
workflows for field verification; reports for donors, boards, and advocacy. The product
shall deliver operational value without requiring dedicated technical staff.

**Edition fit:** Community or Professional.

### 5.4 Corporate forestry

**Organizations:** Timber companies, forest asset managers, carbon forest operators, and
commercial landowners with forest compliance obligations.

**Typical users:** Forest asset managers, compliance officers, operational supervisors,
sustainability reporting leads.

**Product role:** Monitor managed forest assets for loss, fire, degradation, and compliance
failure; maintain investigation trails for certification and regulatory response; produce
auditable reports for internal and external assurance.

**Edition fit:** Professional or Enterprise.

### 5.5 Certification organizations

**Organizations:** Forest certification bodies, audit firms assessing forest management
practices, and assurance providers evaluating chain-of-custody or carbon forest claims.

**Typical users:** Auditors, certification assessors, technical reviewers, report reviewers.

**Product role:** Independent review surface — reproducible intelligence, exportable
point-in-time reports, and investigation records that support assessment without the
product substituting for auditor judgment. The product shall emphasize explainability and
audit reproducibility for this segment.

**Edition fit:** Professional or Enterprise.

*Strategic assumption:* Certification bodies may consume reports and investigation exports
rather than operate the full monitoring workflow daily.

### 5.6 Research institutions

**Organizations:** Universities, forest research institutes, inter-agency monitoring
programs, and longitudinal forest study projects.

**Typical users:** Research scientists, data analysts, project leads, graduate field teams.

**Product role:** Operational layer above raw datasets — reproducible intelligence derivation,
multi-source observation intake, exportable artifacts for publication and grant reporting,
historical analysis over defined study periods. The product shall prioritize reproducibility
and export over polished operational UX for this segment.

**Edition fit:** Community or Professional.

---

## 6. Customer Problems

This section describes what each user segment **actually struggles with** — the problems
the product must solve. These are operational problems, not feature requests.

### 6.1 Government agencies

| Problem | Manifestation |
|---------|---------------|
| **Jurisdictional blind spots** | Incidents in remote or under-monitored regions are discovered late or only after external reporting. |
| **Inter-agency fragmentation** | Fire, loss, and health data live in separate systems; no shared situational picture for coordination. |
| **Briefing burden** | Staff manually compile situational reports for leadership; reports are stale by the time they are presented. |
| **Accountability gap** | Decisions cannot be traced to reproducible intelligence; audit requests expose gaps in evidence chains. |
| **Alert fatigue** | Raw detection feeds produce volume without priority; operators cannot distinguish urgent from background. |

### 6.2 Forestry authorities

| Problem | Manifestation |
|---------|---------------|
| **Category silos** | Fire teams, loss teams, and health teams use different tools; cross-category patterns (fire then logging) are missed. |
| **Situation amnesia** | Each data pull produces new alerts; persistent situations lose history between cycles. |
| **Field dispatch inefficiency** | Inspectors are sent without structured case context, evidence, or prior investigation history. |
| **Administrative record burden** | Proceedings require documented timelines; manual reconstruction from spreadsheets and emails is error-prone. |
| **Baseline drift** | Anomaly detection without category segmentation produces false signals that erode operator trust. |

### 6.3 Environmental NGOs

| Problem | Manifestation |
|---------|---------------|
| **Resource constraint** | Small teams cannot operate enterprise GIS and multiple alert systems simultaneously. |
| **Donor accountability** | Grant reporting requires evidence of monitoring activity; manual evidence assembly consumes program budget. |
| **Verification gap** | Satellite alerts cannot be converted into field-verified cases with audit trail. |
| **Geographic overload** | Monitoring many sites produces unmanageable alert volume without prioritization. |
| **Advocacy timing** | Incidents are documented too late for timely advocacy or intervention. |

### 6.4 Corporate forestry

| Problem | Manifestation |
|---------|---------------|
| **Asset exposure** | Undetected loss, fire, or degradation on managed land creates financial and reputational risk. |
| **Compliance surprise** | Certification or regulatory failures discovered at audit, not during operations. |
| **Operational fragmentation** | Fire monitoring, loss monitoring, and compliance tracking are separate vendor relationships. |
| **Evidence for disputes** | Boundary disputes, theft, or illegal activity lack documented intelligence history. |
| **Reporting overhead** | Sustainability and compliance reports assembled manually from multiple sources. |

### 6.5 Certification organizations

| Problem | Manifestation |
|---------|---------------|
| **Assessor reproducibility** | Audit conclusions cannot be independently verified from the same source data. |
| **Point-in-time ambiguity** | Forest status at assessment date is unclear; retrospective reconstruction is unreliable. |
| **Evidence provenance** | Submitted evidence from auditees lacks chain of custody from observation to conclusion. |
| **Scope limitation** | Assessors review samples; continuous monitoring between audits is absent. |
| **Category blindness** | Assessment focuses on one dimension (e.g., harvest compliance) while fire or loss signals are ignored. |

### 6.6 Research institutions

| Problem | Manifestation |
|---------|---------------|
| **Operational gap** | Research produces datasets but lacks a system for sustained operational tracking during study periods. |
| **Reproducibility demand** | Published analysis requires that intelligence outputs be reproducible from documented inputs. |
| **Multi-source integration** | Combining satellite, field, and imported data requires manual normalization. |
| **Longitudinal continuity** | Study periods lose situation continuity when alerts reset between analysis runs. |
| **Publication lag** | Exportable artifacts for papers and grant reports require manual assembly. |

---

## 7. Product Value Proposition

ForestWatch is valuable because it converts forest observation volume into **operational
forest intelligence** that organizations can trust, investigate, and report — across
categories, over time, and at scale.

### 7.1 Core value statement

**ForestWatch gives forest stewards one place to know what changed, what matters, and
what to do next — with intelligence they can explain and evidence they can defend.**

### 7.2 Value by outcome

| Outcome | Value delivered |
|---------|-----------------|
| **Situational clarity** | Persistent tracked situations replace ephemeral alerts; operators see what is active, escalating, improving, or resolved. |
| **Cross-category coherence** | Fire, loss, disease, and compliance intelligence coexist without mutual contamination; patterns across categories become visible. |
| **Operational efficiency** | Daily briefing, dispatch, and reporting workflows are integrated; manual correlation across tools is eliminated. |
| **Trust and defensibility** | Intelligence is deterministic and explainable; reports and investigations support regulatory, legal-adjacent, and certification contexts. |
| **Scalable scope** | New forest categories and geographies extend the product without replacing it. |
| **Human accountability** | Investigations preserve the boundary between derived intelligence and human judgment. |

### 7.3 Value the product explicitly does not claim

- ForestWatch does **not** claim to replace field inspection or human verification.
- ForestWatch does **not** claim autonomous enforcement or prosecution capability.
- ForestWatch does **not** claim to provide raw data access as its primary value — data
  sources remain available independently; the product value is intelligence and workflow.
- ForestWatch does **not** claim predictive certainty beyond configured detection logic.

---

## 8. Product Modules

Product modules are the long-term functional areas users experience. Each module maps to
platform bounded contexts defined in architecture, or composes them into a user-facing
capability. Modules described here are **product surfaces**, not technical subsystems.

| Product module | Architecture basis |
|----------------|-------------------|
| Monitoring, Intelligence, Investigations, Command Center | Direct bounded contexts |
| Reporting | Reporting subsystem (read-only projection) |
| Compliance | **Product composition** of Intelligence, Investigations, Reporting, and spatial overlays for compliance workflows — not a separate engine |
| Historical Analysis | **Product composition** of read-only temporal projections over observations and intelligence history — not a separate engine |

### 8.1 Monitoring

**Purpose:** Visibility into forest observations and ingestion health across configured
sources and geographies.

**User experience:** Users see what observations have arrived, from which sources, covering
which geographies and categories. Monitoring confirms that the product's observation layer
is active and complete; it does not replace intelligence as the primary decision surface.

**Architectural basis:** Ingestion bounded context; observation persistence.

### 8.2 Intelligence

**Purpose:** The core product module — persistent, scored, lifecycle-managed tracked
situations derived from observations.

**User experience:** Users see active and resolved situations ranked by priority; each
situation carries category, location, score, trend, escalation, severity, detection history,
and supporting evidence. Intelligence is the unit of operational attention.

**Architectural basis:** Intelligence Engine; reconciliation; detector framework; canonical
identity per ADR-001 and ADR-006.

### 8.3 Investigations

**Purpose:** Structured human response to tracked situations.

**User experience:** Users open, assign, progress, and close investigations bound to
intelligence situations. Investigations carry workflow status, outcome, notes, and audit
timeline. Legally or ethically loaded conclusions are recorded here — not in intelligence.

**Architectural basis:** Investigation bounded context; INV-13 human judgment quarantine.

### 8.4 Reporting

**Purpose:** Point-in-time composition and export of forest intelligence artifacts.

**User experience:** Users generate reports from registered sections covering intelligence,
aggregation, investigations, and domain status. Reports export in standard document and
data formats for briefings, compliance, advocacy, and audit. Scheduled reports support
recurring stakeholder communication.

**Architectural basis:** Reporting subsystem; read-only projection per
`docs/architecture/07-reporting-and-command-center.md`.

### 8.5 Compliance

**Purpose:** Product capability for forest compliance workflows — not a separate intelligence
engine.

**User experience:** Users monitor forest compliance categories (certification requirements,
protected-area rules, carbon forest obligations, harvest regulations); link compliance
situations to investigations; export compliance-oriented reports for auditors and
regulators. Compliance is a **product composition** of Intelligence, Investigations, and
Reporting applied to compliance-relevant incident categories and configured overlays
(protected areas, management boundaries, jurisdictional rules).

**Architectural basis:** Incident categories, spatial overlays, investigations, and report
sections — composed for compliance use cases. No separate compliance engine exists or
shall be introduced.

### 8.6 Command Center

**Purpose:** Daily operational surface — live forest situational awareness.

**User experience:** Users open the Command Center for a unified snapshot: domain and
category status, active intelligence counts, threat distribution, incident aggregation,
and investigation statistics. The Command Center is read-only; it reflects the most recently
derived intelligence state.

**Architectural basis:** Command Center per `docs/architecture/07-reporting-and-command-center.md`;
generalized aggregation registry.

### 8.7 Historical Analysis

**Purpose:** Temporal views over forest observations and intelligence history.

**User experience:** Users analyze trends over defined periods — observation volume,
category distribution, situation lifecycles, resolved event history, regional baselines, and
deviation patterns. Historical Analysis supports retrospective review, research, audit
preparation, and long-term forest health assessment. It shall not mutate intelligence state;
it reads historical projections.

**Architectural basis:** Read-only temporal aggregation over observations and intelligence
events; consistent with deterministic analytics (INV-4). Historical views reflect
reconciled state at the time of each cycle, not recomputed intelligence on read.

---

## 9. Product Editions

Editions describe **capability tiers**, not pricing. Specific pricing is defined
commercially and is outside this document. Edition entitlement boundaries **SHALL** follow
`docs/business/EDITION_STRATEGY.md`; where §9 and EDITION_STRATEGY differ on edition
capabilities, EDITION_STRATEGY governs per `docs/DOCUMENT_HIERARCHY.md` §4.2.

### 9.1 Community

**Intended segment:** Individual stewards, researchers, students, and NGO field evaluators
exploring ForestWatch in a bounded personal scope — not organizational deployment.
Organizations requiring team collaboration or operational investigations **SHALL** adopt
Professional (EDITION_STRATEGY §2.8).

**Capabilities included:**

- Core Monitoring and Intelligence for a limited number of forest incident categories
- Command Center for a single geography or bounded area (read-only operational snapshot)
- Personal workspace (saved geographies, watchlists, personal annotations)
- Standard Reporting with core report sections (personal-scope, manual)
- Historical Analysis for defined retention period
- Manual observation intake from supported sources

**Capabilities excluded or limited:**

- Operational Investigations workflow (Professional minimum)
- Multi-geography deployment
- Advanced Compliance module configuration
- Scheduled and automated report delivery at scale
- Multi-organization tenant isolation
- Premium spatial overlays and custom boundaries
- Priority support and dedicated onboarding

### 9.2 Professional

**Intended segment:** Forestry authorities, regional agencies, corporate forestry operators,
and active conservation organizations with sustained operational need.

**Capabilities included:**

- Full Monitoring and Intelligence across all product-supported forest categories
- Command Center with multi-category and multi-region views
- Full Investigations workflow with assignment and audit timeline
- Full Reporting including scheduled reports and extended export formats
- Compliance module with configured protected-area and jurisdictional overlays
- Historical Analysis with extended retention
- Multiple configured observation sources
- Notification routing for intelligence changes

**Capabilities excluded or limited:**

- Multi-tenant organization isolation
- Self-hosted or air-gapped deployment
- Custom domain onboarding without services engagement
- White-label or embedded deployment

### 9.3 Enterprise

**Intended segment:** National government agencies, large forestry estates, certification
bodies at scale, and multi-organization deployments.

**Capabilities included:**

- All Professional capabilities
- Multi-geography and multi-organization deployment (when multi-tenancy is available per
  ADR-010)
- Self-hosted or dedicated deployment option
- Custom forest category onboarding within product scope
- Extended Compliance configuration for regulatory and certification frameworks
- Advanced Historical Analysis including cross-category correlation views (when available)
- Integration access for partner systems
- Configurable retention, access control, and audit export policies
- Dedicated onboarding and operational support

**Capabilities excluded:**

- Capabilities outside forest ecosystem scope
- Autonomous enforcement or legal-evidence substitution
- Non-forest environmental monitoring domains

*Strategic assumption:* Edition boundaries may be refined as product maturity and market
validation progress. Edition capability lists are directional, not contractual.

---

## 10. Product Expansion Strategy

New forest intelligence domains become product capabilities **by extension**, not by
product redesign. This strategy aligns with the domain plug-in architecture (ADR-005) and
the architecture phase roadmap.

### 10.1 How a new forest category becomes a product capability

When a new forest incident category (e.g., pest outbreak, storm damage, carbon compliance)
is ready for product inclusion, the following product surfaces shall be extended — in
this order:

1. **Monitoring** — observation intake from the category's configured sources.
2. **Intelligence** — category-segmented detection and tracked situations appearing in
   the Intelligence module and Command Center.
3. **Command Center** — category represented in domain catalog and aggregation views.
4. **Investigations** — no module change; existing workflow binds to new category situations.
5. **Reporting** — new report sections registered for the category.
6. **Compliance** — category included in compliance views where regulatory or
   certification relevance applies.
7. **Historical Analysis** — category included in temporal views and trend summaries.

Users shall experience new categories as **new lenses on the same product**, not as a new
product installation.

### 10.2 Product expansion constraints

- A forest category shall **not** be offered as a product capability until the intelligence
  engine supports category-segmented analysis without contaminating existing categories.
- Product marketing shall **not** announce a category before operational workflow (intelligence,
  investigation, reporting) is usable for that category.
- Categories outside forest ecosystem scope shall **not** be added to the product regardless
  of technical extensibility.
- Product expansion shall follow architecture phase ordering; commercial urgency shall
  not reorder phase dependencies.

### 10.3 Phase-aligned product expansion

| Architecture phase | Product expansion delivered |
|--------------------|----------------------------|
| Phase 0 | Intelligence module generalized; wildfire category preserved; foundation for all forest categories |
| Phase 1 | Spatial context (protected areas, land cover, boundaries) enriches all modules |
| Phase 2 | Forest loss / Human Activity category live across all product modules |
| Phase 3 | Multi-category surface — map layers, filters, category watch cards; first full product release |
| Future (`08-roadmap.md` §7) | Additional forest incident categories (pest, storm, carbon, fragmentation, etc.) via extension |

Non-forest categories listed in `docs/architecture/08-roadmap.md` §8 are engine
extensibility only and **shall not** appear on the product roadmap.

---

## 11. Product Differentiators

These differentiators describe what makes ForestWatch **as a product** distinct from
alternatives. They are product-experienced outcomes of architectural strengths.

### 11.1 Persistent situations, not ephemeral alerts

Competing products reset on every data pull. ForestWatch maintains tracked situations
with history, trend, escalation, and resolution. Users experience continuity — a fire
situation that persists and evolves is one object, not fifty alerts.

### 11.2 Cross-category forest intelligence in one product

Users operate fire, loss, disease, and compliance intelligence in one Command Center
without manual correlation. The product differentiator is experienced unity, enabled by
category-segmented engine architecture.

### 11.3 Deterministic, explainable intelligence

Users and auditors can reproduce intelligence outputs. The product shall expose evidence,
scoring inputs, and provenance — not a black-box alert. This differentiates ForestWatch in
regulatory, certification, and legal-adjacent contexts.

### 11.4 Investigation workflow as first-class product module

Investigations are not a notes field on an alert. They are structured workflows with
assignment, status, outcome, and audit timeline — visibly separate from derived
intelligence. This differentiates the product for organizations that must act on forest
situations, not merely observe them.

### 11.5 Reporting as audit artifact, not dashboard export

Reports are composed point-in-time artifacts from registered sections, exportable in
standard formats. They are designed for external communication and audit — not screen
captures. Scheduled reporting supports recurring stakeholder obligations.

### 11.6 Extensibility without product replacement

When a new forest category is added, existing users keep their workflows, data, and
configuration. The product grows; it is not replaced. This differentiates against
single-category tools that require parallel product adoption.

### 11.7 Forest vertical depth

The product refuses horizontal dilution. Every module, workflow, and category is designed
for forest ecosystem stewardship — not adapted from a generic environmental platform.
Depth in one vertical is the differentiator against breadth-focused competitors.

---

## 12. Product Boundaries

ForestWatch as a product **is**:

- A Forest Intelligence Platform for operational forest stewardship
- A system for persistent, cross-category, explainable forest intelligence
- A workflow product for investigations, reporting, and daily situational awareness
- An extensible product that adds forest categories without architectural reinvention

ForestWatch as a product **is not**:

| Boundary | Rationale |
|----------|-----------|
| **Not a wildfire alert product** | Wildfire is one category; the product identity is the full forest ecosystem |
| **Not a deforestation-only tool** | Forest loss is one category among many |
| **Not a map or GIS product** | Maps are exploration surfaces; intelligence and workflow are the product core |
| **Not a data marketplace** | Observations are inputs; intelligence and operational workflow are the product value |
| **Not a generic environmental platform** | Air, marine, urban, and general water domains are out of scope |
| **Not an autonomous enforcement system** | Intelligence is derived; human judgment lives in investigations |
| **Not a legal evidence or prosecution system** | The product supports investigation and audit; it does not substitute for legal process |
| **Not a consumer or public alert app** | The product serves organizations with forest stewardship responsibility |
| **Not a research-only dataset tool** | Research is a user segment; the product is operational first |
| **Not a predictive oracle** | Intelligence reflects configured detection and reconciliation; certainty claims beyond that are prohibited |
| **Not a replacement for field presence** | Satellite and automated detection supplement; they do not replace ground verification |

---

## 13. Long-Term Product Evolution

Product evolution follows the architecture phase roadmap. Product identity — Forest
Intelligence Platform — remains constant across all phases. What evolves is **category
coverage**, **spatial depth**, and **surface completeness**.

### 13.1 Phase 0 — Engine foundation (product unchanged externally)

**Product state:** Wildfire intelligence continues to operate as today. Internally, the
product gains the foundation for multi-category intelligence without user-visible disruption.

**User experience:** No regression in wildfire workflows. Product credibility established
for existing users.

### 13.2 Phase 1 — Spatial depth

**Product state:** All product modules gain richer spatial context — protected areas, land
cover, forest boundaries, jurisdictions — as enrichment on observations and intelligence.

**User experience:** Situations carry clearer geographic and contextual meaning;
Compliance and Monitoring modules benefit first.

### 13.3 Phase 2 — Second forest category

**Product state:** Forest loss / Human Activity intelligence appears as a full product
capability across Monitoring, Intelligence, Command Center, Investigations, Reporting,
and Historical Analysis.

**User experience:** Users operate two forest categories in one product. Cross-category
Command Center becomes the proof of product identity.

### 13.4 Phase 3 — Full multi-category surface

**Product state:** Version 1.0.0 product — map layers, category filters, domain watch cards,
activated Command Center for all onboarded categories. First commercially complete product.

**User experience:** ForestWatch is visibly a Forest Intelligence Platform, not a fire tool
with add-ons.

### 13.5 Long-term (Years 3–5)

**Product state:** Additional forest categories (disease, storm, carbon compliance,
fragmentation, reforestation) onboarded through extension. Historical Analysis and
Compliance modules deepen. Cross-category correlation may surface linked situations.

**User experience:** The product covers the full forest incident spectrum defined in product
identity. Users who adopted for wildfire or loss retain continuity as categories expand.

**Identity invariant:** At no phase does the product become a generic environmental
platform. Phase evolution adds forest depth; it does not add horizontal breadth.

---

## 14. Success Criteria

Success criteria describe what the **product** looks like after five years. These are
product outcomes, not financial targets. Progress shall be assessed qualitatively until
deployment baselines exist.

### 14.1 Product completeness

- All product modules (Monitoring, Intelligence, Investigations, Reporting, Compliance,
  Command Center, Historical Analysis) are operational for at least three forest incident
  categories.
- Product identity is recognized by users as Forest Intelligence Platform — not wildfire
  or deforestation software.
- New forest categories can be added to a deployed product without user workflow disruption.

### 14.2 User adoption patterns

- At least one user segment in each target category (Section 5) uses the product in
  sustained daily or weekly operational rhythm.
- Command Center is the primary daily surface for operational user segments.
- Investigations are opened, progressed, and closed on tracked situations — not bypassed.
- Reports are exported and used in external processes (briefings, audits, grants, compliance).

### 14.3 Product trust

- Users can explain why a tracked situation exists and how it was scored.
- Audit reproducibility is demonstrated — identical inputs produce identical intelligence.
- False-positive rates per category are within operator-defined tolerance; trust is maintained.

### 14.4 Product scope discipline

- Product scope remains forest ecosystems; no non-forest environmental modules introduced.
- Edition capability tiers (Community, Professional, Enterprise) are defined, deployed, and
  differentiated in practice.

### 14.5 Product evolution integrity

- Product evolution occurred through architecture phases without identity change.
- No product module computes or mutates intelligence outside the intelligence engine
  (read-only projection rule preserved).
- Investigation workflow remains the human judgment surface; no automated conclusion
  features introduced.

*Strategic assumption:* Product success at five years requires at least one multi-category,
multi-module deployment used in real operational conditions — not demonstration or pilot
alone.

---

## 15. Conclusions

ForestWatch is a **Forest Intelligence Platform** product — not a software project, not a
single-category alert tool, and not a generic environmental dashboard.

The product serves organizations that steward forest ecosystems by giving them:

- **one operational surface** (Command Center) for daily forest situational awareness;
- **one intelligence model** (tracked situations) across all forest incident categories;
- **one response workflow** (Investigations) for human judgment and accountability;
- **one audit surface** (Reporting and Compliance) for external communication and assurance;
- **one historical record** (Historical Analysis) for retrospective understanding.

Product evolution adds forest categories and spatial depth through extension, following
architecture phases, without changing product identity. Edition tiers make the product
accessible to NGOs and research institutions while serving the full operational needs of
government, forestry authorities, corporate operators, and certification bodies.

The product strategy complements `docs/business/BUSINESS_STRATEGY.md`: business strategy
defines commercial direction and competitive context; this document defines what users
experience, what problems are solved, and how the product grows within forest ecosystem
scope.

Product decisions shall remain subordinate to architecture invariants. The product shall
deliver forest intelligence that organizations can trust, investigate, explain, and report
— for as long as forests require stewardship.

---

## Document Control

| Field | Value |
|-------|-------|
| Created | 2026-07-17 |
| Status | Pending review |
| Reconciliation | CMR-001, CMR-002, CMR-003 applied 2026-07-22 |
| Related business document | `docs/business/BUSINESS_STRATEGY.md`, `docs/business/EDITION_STRATEGY.md` |
| Related architecture | `docs/architecture/00-platform-vision.md` §2, `02-intelligence-engine.md`, `06-domain-plugin-architecture.md`, `07-reporting-and-command-center.md`, `08-roadmap.md` §7–§8 |
| Related ADRs | ADR-001, ADR-005, ADR-006, ADR-010, ADR-011 |
| Next documents | None until this document is reviewed and approved |

---

*End of Product Strategy.*
