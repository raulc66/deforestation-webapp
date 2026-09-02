# ForestWatch — Edition Strategy

**Status:** Strategic document — pending review.
**Audience:** Commercial leadership, product, sales, customer success, and partnership
stakeholders defining what ForestWatch offers at each commercial tier.
**Authority:** This document is the **authoritative definition** of ForestWatch commercial
editions — what is free, what is paid, and how organizations progress through the platform.
It is subordinate to `docs/architecture/` and its ADRs for platform invariants, and
consistent with `docs/business/BUSINESS_STRATEGY.md`, `docs/business/PRODUCT_STRATEGY.md`,
`docs/business/GO_TO_MARKET_STRATEGY.md`, `docs/product/PLATFORM_CAPABILITIES.md`, and
`docs/product/INVESTIGATION_FRAMEWORK.md`. Where edition definitions and architecture
disagree, architecture governs what the platform may do; this document governs what each
edition **includes commercially**.

**Document type:** Edition strategy. This is not a pricing schedule, financial forecast,
implementation specification, or contract template. It contains no price points, revenue
estimates, or technical deployment detail.

**Product identity:** ForestWatch is a **Forest Intelligence Platform** scoped to forest
ecosystems. Wildfire is one forest incident category among many — not the primary product
definition.

**Language:** The key words **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**,
**SHOULD NOT**, **MAY**, and **OPTIONAL** in this document are to be interpreted as
described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## 1. Edition Philosophy

### 1.1 Why editions exist

ForestWatch editions exist to align **commercial access** with **operational value** without
compromising the platform's forest intelligence mission or architecture invariants.

Editions **SHALL** solve three problems simultaneously:

1. **Trust at scale** — the public must be able to verify that ForestWatch produces credible,
   cross-category, derived forest intelligence without purchasing access.
2. **Accessible entry** — individual stewards, small NGOs, and researchers must be able to
   explore the platform without financial barrier.
3. **Operational value capture** — organizations that **use intelligence operationally**
   (investigate, collaborate, comply, integrate, automate, and deploy privately) **SHALL**
   pay for Professional or Enterprise capability.

Editions are **capability tiers**, not separate products. All editions share one Forest
Intelligence Platform engine, one investigation workflow model (when licensed), and one
extension path for new forest incident categories.

### 1.2 Core commercial principles

| Principle | Meaning |
|-----------|---------|
| **Public intelligence creates trust** | Open derived intelligence, reports, and maps demonstrate platform capability and forest change transparency |
| **Operational intelligence creates value** | Organizations pay to **act** on intelligence — not merely to **see** it |
| **Organizations pay for operational use** | Paid editions license organizational workflow, privacy, scale, and integration |
| **Community must not compete with Professional** | Free tier **MUST NOT** substitute for team operations, compliance, automation, or APIs |
| **Community must encourage upgrades** | Free tier **SHALL** expose upgrade paths when scope, collaboration, or compliance needs emerge |
| **Public reports and maps are strategic assets** | Permanently free; they build credibility and funnel organizational adoption |
| **Investigations are operational workflows** | Full investigation capability is **organizational** and **paid** — not a free personal feature |
| **Collaboration is always organizational** | Team assignment, shared cases, and multi-user administration require Professional or Enterprise |
| **Automation is never free** | Scheduled intelligence delivery, scheduled reports, and automated notification routing are paid |
| **APIs are never free** | Programmatic integration access requires Enterprise |
| **Compliance is never free** | Compliance workflows and configuration require Professional minimum |

### 1.3 Edition stack

ForestWatch commercial access comprises **four layers**. The first requires no account;
the others are named editions.

| Layer | Name | Cost | Role |
|-------|------|------|------|
| **0** | Public transparency | Free, no account | Trust, discovery, education |
| **1** | Community Edition | Free, registered | Personal exploration and evaluation |
| **2** | Professional Edition | Paid | Organizational forest operations |
| **3** | Enterprise Edition | Paid | Scale, isolation, integration, and private deployment |

---

## 2. Community Edition

### 2.1 Purpose

Community Edition **SHALL** provide **free, registered personal access** for individuals
evaluating ForestWatch, conducting limited personal forest monitoring, or supporting
education and research — without granting **organizational operational capability**.

It exists to:

- lower adoption friction for NGOs, researchers, students, and pilot evaluators;
- convert public-trust exposure into registered product experience;
- create **natural upgrade pressure** when personal use becomes organizational need.

Community Edition **MUST NOT** function as a free substitute for Professional operational
deployment.

### 2.2 Target users

| User type | Typical use |
|-----------|-------------|
| **Individual conservation advocates** | Monitor a bounded forest area of personal concern |
| **Researchers and students** | Reproduce intelligence methodology; export for academic use |
| **NGO field coordinators (solo)** | Evaluate platform before organizational purchase |
| **Pilot evaluators** | Assess fit before procurement or Professional subscription |
| **Journalists and analysts** | Explore public intelligence with personal saved context |

Community Edition **SHALL NOT** target sustained **organizational** daily operations across
teams — that is Professional.

### 2.3 Capabilities

Community Edition **SHALL** include:

| Capability | Community scope |
|------------|-----------------|
| **Public intelligence access** | Full access to public derived intelligence (see §2.4) |
| **Public reports and maps** | Full access to open reports and public maps (see §2.5–2.6) |
| **Personal workspace** | Saved geographies, watchlists, personal annotations, and session preferences tied to individual account |
| **Bounded intelligence views** | Read intelligence for **one configured geography** and **limited forest incident categories** |
| **Monitoring (read)** | View observation intake status for bounded scope |
| **Command Center (bounded)** | Single-geography operational snapshot — read-only |
| **Historical Analysis (limited)** | Temporal views within **defined retention period** |
| **Reporting (manual, personal)** | On-demand export of **personal-scope** reports using **core report sections** — not scheduled, not compliance-oriented |
| **Manual observation intake** | Limited personal submission of supported observation types for bounded scope |

### 2.4 Public intelligence access

Community users **SHALL** have the same access to **public intelligence** as unauthenticated
users, plus personal workspace overlays (saved views, annotations).

Public intelligence **SHALL** remain **free and unrestricted** within platform-configured
public scope — Community Edition does not add exclusive intelligence beyond personal
organization of public content.

### 2.5 Public reports

Community users **SHALL** access all **open report snapshots** published by ForestWatch.

Community users **MAY** generate **personal manual reports** for their bounded scope using
core sections. Personal reports **MUST NOT** include compliance sections, investigation
summaries from organizational cases, or enterprise audit export formats.

### 2.6 Public maps

Community users **SHALL** access **public maps** for spatial exploration of public
intelligence — category filters and regional views for configured public geographies.

Community maps **MUST NOT** include private organizational overlays, custom boundaries,
Compliance layers, or operational investigation map integration.

### 2.7 Personal workspaces

A **personal workspace** **SHALL** provide:

- saved geographies and category filters within Community bounds;
- personal watchlists on public and bounded intelligence;
- personal notes and bookmarks (not organizational audit records);
- export history for personal manual reports.

Personal workspaces **SHALL NOT** constitute an **organization** — no shared membership,
no team assignment, no role-based administration.

### 2.8 Personal investigations

**Personal investigations are not included in Community Edition.**

Investigations are **operational workflows** requiring organizational accountability
(INVESTIGATION_FRAMEWORK). Community Edition **MUST NOT** offer:

- investigation case creation with audit timeline;
- assignment to other users;
- team-visible investigation status;
- investigation outcomes recorded as organizational conclusions;
- investigation exports for external audit or compliance.

Individual users **MAY** annotate public or bounded intelligence in their personal workspace.
Annotation **SHALL NOT** be treated as an investigation record.

**Upgrade trigger:** When a user needs to **open, assign, progress, or close** formal
investigation cases, they **MUST** adopt Professional Edition under an **organization**.

### 2.9 Limitations

Community Edition **SHALL NOT** include:

| Excluded capability | Rationale |
|--------------------|-----------|
| **Operational investigations** | Paid organizational workflow (§2.8) |
| **Team collaboration** | Organizational capability |
| **Compliance workflows** | Never free |
| **Automation** (scheduled reports, scheduled intelligence, notification routing) | Never free |
| **API access** | Never free |
| **Multi-geography operational scope** | Professional expansion path |
| **Full forest category set** | Limited categories — platform-supported subset |
| **Organizational Administration** | User roles, org-wide configuration, retention policy |
| **Private deployment** | Enterprise |
| **Multi-tenancy / multi-organization isolation** | Enterprise |
| **Premium spatial overlays and custom boundaries** | Professional minimum |
| **Priority support and dedicated onboarding** | Enterprise |
| **Integration and white-label embedding** | Enterprise |

---

## 3. Professional Edition

### 3.1 Purpose

Professional Edition **SHALL** be the **primary paid edition** for organizations that
**operate** on forest intelligence daily — monitoring, investigating, reporting, and
coordinating response across teams and geographies.

Professional is where **operational intelligence creates commercial value**.

### 3.2 Target users

| Segment | Role |
|---------|------|
| **Forestry authorities** | Public forest operations across fire, loss, health, and estate management |
| **Regional government agencies** | Jurisdictional situational awareness and briefing |
| **Corporate forestry operators** | Managed land monitoring and compliance response |
| **Active conservation NGOs** | Multi-site team operations beyond Community bounds |
| **Certification assessors (operating)** | Organizations running assessment workflows — not export-only consumption |

### 3.3 Operational investigations

Professional **SHALL** include the **full Investigation workflow**
(INVESTIGATION_FRAMEWORK):

- open, assign, progress, and close investigation cases;
- optional binding to Intelligence Events;
- evidence collection from platform and external sources;
- assessment, human decision, and closure with append-only audit timeline;
- investigation statistics in Command Center and Reporting;
- notification routing on investigation lifecycle transitions.

Investigation conclusions **SHALL** remain human-authored (INV-13). Professional
**MUST NOT** present derived intelligence as investigation outcome.

### 3.4 Team collaboration

Professional **SHALL** support **organizational collaboration**:

- multiple users under one organization;
- role-based access within organizational scope;
- investigation assignment to analysts and teams;
- shared visibility of organizational intelligence and open investigations;
- coordinated reporting for briefings and external communication.

Collaboration **SHALL** always be **organizational** — tied to a paying organization,
never a free multi-user Community workspace.

### 3.5 Reporting

Professional **SHALL** include:

- full Reporting capability with extended export formats;
- **scheduled report generation and delivery**;
- registered report sections for onboarded forest categories;
- investigation summaries in organizational reports;
- private organizational reports — distinct from public open reports.

### 3.6 Command Center

Professional **SHALL** include:

- Command Center with **multi-category and multi-region** views;
- live read-only operational snapshot across organizational scope;
- cross-category forest situational awareness;
- investigation statistics and navigation to active cases.

Command Center **SHALL** remain read-only per architecture (ADR-011).

### 3.7 Historical Analysis

Professional **SHALL** include:

- extended retention for temporal views;
- trend analysis, lifecycle history, and baseline comparison over organizational scope;
- historical context usable as investigation evidence.

### 3.8 Compliance support

Professional **SHALL** include **Compliance** as a product composition (Intelligence +
Investigations + Reporting + spatial overlays):

- compliance-relevant category monitoring;
- protected-area and jurisdictional overlay configuration;
- compliance-oriented investigation and report workflows;
- human findings routed through Investigation decision stages — never automated violations.

Compliance **SHALL NOT** be available in Community Edition.

### 3.9 Administration

Professional **SHALL** include **organizational Administration**:

- user and role management within the organization;
- observation source configuration for organizational scope;
- geography and monitoring scope configuration;
- domain catalog and category visibility for the organization;
- spatial overlay registration within product-supported limits;
- notification and report schedule configuration;
- edition entitlement enforcement.

Professional Administration **SHALL NOT** include Enterprise-only policies (multi-tenant
isolation, self-hosted deployment control, enterprise audit export policy, API key
governance at scale).

### 3.10 Scheduled intelligence

Professional **SHALL** include **automation** for operational rhythm:

- scheduled reconciliation-aligned intelligence refresh visibility;
- scheduled report generation;
- automated notification routing for intelligence changes and investigation transitions.

Automation **SHALL NOT** be offered in Community Edition.

### 3.11 Notifications

Professional **SHALL** include **notification routing** — outbound alerts derived from
reconciliation change-sets and investigation lifecycle transitions. Notifications **SHALL**
alert humans to act; they **MUST NOT** record conclusions (INV-13).

---

## 4. Enterprise Edition

### 4.1 Purpose

Enterprise Edition **SHALL** serve organizations requiring **maximum scale, isolation,
integration, and contractual assurance** — national agencies, large estates, multi-
organization networks, certification bodies at scale, and integration partners.

Enterprise includes **all Professional capabilities** plus enterprise-only extensions.

### 4.2 Target organizations

| Organization type | Enterprise need |
|-------------------|-----------------|
| **National government agencies** | Multi-region, multi-agency scope; procurement-grade assurance |
| **Large public forestry estates** | Geographic scale; dedicated deployment options |
| **Multi-organization networks** | Tenant isolation between distinct organizations |
| **Certification bodies at scale** | Extended compliance configuration; audit export policy |
| **Platform and integration partners** | API access; embedded or white-label deployment |
| **Corporate operators with sovereignty requirements** | Private deployment; air-gapped or dedicated hosting |

### 4.3 Private deployments

Enterprise **MAY** include **self-hosted or dedicated deployment** options for data
sovereignty, air-gapped operation, or contractual isolation.

Private deployment **SHALL** deliver the full Enterprise capability set — not a reduced
engine fork. Architecture invariants **MUST** hold in all deployment modes.

### 4.4 Multi-tenancy

Enterprise **SHALL** support **multi-organization deployment** when multi-tenancy is
implemented per ADR-010:

- tenant-scoped intelligence identity `(tenant, incident_category, spatial_key)`;
- partitioned data and access control between organizations;
- domain-scoped authorization within tenants.

Enterprise **MUST NOT** be sold with multi-tenant isolation promises before ADR-010
implementation is complete.

### 4.5 API

Enterprise **SHALL** include **API access** for partner systems and organizational
automation:

- read-only consumption of intelligence projections;
- organizational investigation and reporting integration within contract bounds;
- deterministic output guarantees for downstream systems.

API access **MUST NOT** be offered in Community or Professional Editions for production
integration use.

### 4.6 Integrations

Enterprise **SHALL** include **integration capability**:

- partner system embedding;
- white-label or co-branded deployment options where contractually agreed;
- custom forest category onboarding within product scope (with services engagement as needed);
- external data provider integration at organizational boundary.

### 4.7 Automation

Enterprise **SHALL** include **advanced automation** beyond Professional:

- organization-wide automated workflows spanning intelligence, notification, and reporting;
- configurable retention and archival automation;
- integration-triggered operational pipelines within API contract scope.

All automation **SHALL** respect read-only projection rules and INV-13.

### 4.8 Enterprise reporting

Enterprise **SHALL** include **extended reporting**:

- enterprise audit export policies;
- compliance-grade report packages for regulatory and certification frameworks;
- advanced Historical Analysis including cross-category correlation views when available;
- configurable report retention and access control.

### 4.9 Security

Enterprise **SHALL** address security as a **commercial assurance layer**:

- organizational access control and audit logging;
- deployment-isolation options;
- contractual data-handling and provider-license boundaries;
- export and investigation audit trail integrity.

Security positioning **MUST NOT** claim autonomous legal-evidence certification without
human investigation workflow.

### 4.10 Administration

Enterprise **SHALL** include **full Administration**:

- all Professional administration capabilities;
- multi-geography and multi-organization governance;
- configurable retention, access control, and audit export policies;
- API key and integration governance;
- custom overlay and category onboarding administration.

### 4.11 Compliance

Enterprise **SHALL** include **extended Compliance configuration**:

- regulatory and certification framework templates;
- multi-jurisdiction overlay management;
- enterprise compliance reporting packages;
- investigation audit exports for external assessors.

Compliance findings **MUST** flow through Investigations (INV-13) in all cases.

### 4.12 Support

Enterprise **SHALL** include **dedicated onboarding and operational support**:

- deployment assistance;
- investigation workflow design for organizational policy;
- category and geography expansion guidance;
- escalation path for pipeline and operational issues.

### 4.13 SLAs

Enterprise **SHALL** offer **service level agreements** addressing operational
reliability — scheduler cycle completion, pipeline integrity, report generation
availability — not detection accuracy or predictive certainty.

SLA terms are contractual — outside this document. SLA framing **SHALL** align with
architecture: intelligence freshness follows reconciliation cadence; read paths do not
trigger reconciliation (ADR-011).

---

## 5. Edition Progression

Organizations **SHALL** progress naturally through the edition stack as operational need
matures.

### 5.1 Typical progression path

```
Public (discovery)
    ↓
Community (personal evaluation)
    ↓
Professional (organizational operations)
    ↓
Enterprise (scale, isolation, integration)
```

### 5.2 Progression triggers

| Transition | Typical trigger |
|------------|-----------------|
| **Public → Community** | User wants saved workspace, bounded personal monitoring, or academic export |
| **Community → Professional** | Team must collaborate; formal investigations required; multi-geography scope; Compliance needed; scheduled reporting or notifications required |
| **Professional → Enterprise** | Multi-organization isolation; private deployment; API/integration; enterprise audit policy; SLA; national scale |

### 5.3 Non-linear paths

| Path | When |
|------|------|
| **Public → Professional** | Organization ready to purchase without individual Community evaluation |
| **Public → Enterprise** | Large procurement with RFP — public layer used for trust during evaluation |
| **Community → Enterprise** | Rare; large organization skips Professional only if Enterprise requirements are immediate |

### 5.4 Category and geography expansion (within edition)

Paid customers **SHALL** expand **within** Professional or Enterprise before changing
edition:

- additional forest incident categories as architecture onboard them;
- additional geographies within edition limits;
- deeper Compliance and reporting configuration.

Edition change **SHALL** be required when **isolation, API, private deployment, or SLA**
needs emerge — not when adding a forest category alone.

---

## 6. Capability Matrix

Legend: **●** included · **◐** limited · **○** not included · **—** not applicable

| Capability | Public | Community | Professional | Enterprise |
|------------|--------|-----------|--------------|------------|
| **Public intelligence** | ● | ● | ● | ● |
| **Open public reports** | ● | ● | ● | ● |
| **Public maps** | ● | ● | ● | ● |
| **Personal workspace** | — | ● | ◐ org + personal | ◐ org + personal |
| **Bounded intelligence views** | ◐ public scope | ◐ one geography | ● multi-region | ● unlimited org scope |
| **Monitoring** | ◐ public | ◐ bounded | ● | ● |
| **Command Center** | ◐ public snapshot | ◐ single geography | ● multi-category/region | ● |
| **Historical Analysis** | ◐ public history | ◐ limited retention | ● extended | ● advanced |
| **Manual personal reports** | ○ | ● core sections | ● | ● |
| **Private organizational reports** | ○ | ○ | ● | ● enterprise audit |
| **Scheduled reports / automation** | ○ | ○ | ● | ● advanced |
| **Notifications** | ○ | ○ | ● | ● |
| **Operational investigations** | ○ | ○ | ● | ● |
| **Team collaboration** | ○ | ○ | ● | ● |
| **Compliance workflows** | ○ | ○ | ● | ● extended |
| **Organizational Administration** | ○ | ○ | ● | ● full |
| **API access** | ○ | ○ | ○ | ● |
| **Integrations / embedding** | ○ | ○ | ○ | ● |
| **Private deployment** | ○ | ○ | ○ | ● |
| **Multi-tenancy** | ○ | ○ | ○ | ● when available |
| **Dedicated support / SLA** | ○ | ○ | ◐ standard | ● |

---

## 7. Capabilities That Never Become Paid

The following **SHALL** remain **free permanently** for all users, including after
Professional or Enterprise adoption:

| Forever-free capability | Rationale |
|-------------------------|-----------|
| **Public derived intelligence** | Trust and transparency; proves reconciliation value above raw feeds |
| **Open public report snapshots** | Strategic credibility asset; advocacy and public oversight |
| **Public map exploration** | Spatial discovery of public intelligence; not operational deployment |
| **Methodology visibility** | Explainability of derived intelligence — scoring inputs, provenance, category segmentation (within public scope) |
| **Educational access to public layer** | Academic and NGO trust building |

**Rules:**

- ForestWatch **MUST NOT** paywall public intelligence to force Professional purchase.
- Paid editions **SHALL** add **operational, organizational, private, and integrative**
  capability — not exclusive access to basic derived intelligence for configured public scope.
- Public layer content **SHALL** reflect **platform-operated public scope** — not
  exfiltration of private customer intelligence.

---

## 8. Capabilities Reserved for Organizations

The following **SHALL** require a **paying organization** (Professional minimum unless
noted). They **MUST NOT** be offered to individual Community users or the public layer.

| Organization-only capability | Minimum edition |
|------------------------------|-----------------|
| **Operational investigations** (open, assign, audit, close) | Professional |
| **Team collaboration and role-based access** | Professional |
| **Private organizational intelligence scope** (non-public geography configuration) | Professional |
| **Compliance workflows and configuration** | Professional |
| **Scheduled intelligence and scheduled reporting** | Professional |
| **Notification routing** | Professional |
| **Organizational Administration** | Professional |
| **Premium spatial overlays and custom boundaries** | Professional |
| **Multi-geography operational deployment** | Professional |
| **API access** | Enterprise |
| **Production integrations and embedding** | Enterprise |
| **Private / self-hosted deployment** | Enterprise |
| **Multi-tenant organization isolation** | Enterprise |
| **Enterprise audit export and retention policy** | Enterprise |
| **Dedicated support and SLA** | Enterprise |

**Principle:** Individuals **MAY** observe forest intelligence freely. **Organizations**
**SHALL** pay to **operate** on it.

---

## 9. Upgrade Principles

Upgrades **SHALL** follow these rules:

1. **Upgrade when operational need appears** — not when public intelligence quality improves.
2. **Investigation need → Professional** — any formal case workflow triggers organizational upgrade.
3. **Second user → Professional** — collaboration requires organization; Community is single-user personal workspace.
4. **Compliance need → Professional** — certification, protected-area, or regulatory workflow never starts in Community.
5. **Automation need → Professional** — scheduling and notification routing require paid edition.
6. **Integration need → Enterprise** — API and embedding are Enterprise-only.
7. **Isolation need → Enterprise** — private deployment or multi-tenancy requires Enterprise.
8. **Preserve continuity** — upgrade **SHALL** retain personal workspace history where applicable; organizational data **SHALL** begin fresh under org tenancy.
9. **No punitive downgrade of public access** — upgrading **MUST NOT** remove public layer access for any user.
10. **Category expansion does not require Enterprise** — new forest categories **SHALL** extend Professional and Enterprise; public categories **SHALL** extend public layer separately per platform policy.

---

## 10. Downgrade Principles

Downgrades **MAY** occur when organizational subscription ends. Downgrade **SHALL** follow:

1. **Organization operational data is organization-owned** — investigation records, private reports, and organizational configuration **SHALL** be exportable before downgrade where contractually required.
2. **Downgrade to Community** — user retains personal workspace and public access; **loses** team collaboration, investigations, Compliance, automation, Administration, and private organizational scope.
3. **Investigation records do not become public** — closed organizational investigations **MUST NOT** appear on public layer on downgrade.
4. **API access revoked on Enterprise exit** — integrations **MUST** cease when Enterprise ends unless renewed.
5. **Private deployment ends with Enterprise** — self-hosted deployments **SHALL** have contractual data-return provisions.
6. **No orphan intelligence mutations** — downgrade **MUST NOT** violate architecture; organizational intelligence scope **SHALL** be archived or deactivated — not merged into public scope without explicit platform publication policy.
7. **Public access unchanged** — downgrade **MUST NOT** affect public intelligence, open reports, or public maps.

---

## 11. Long-Term Edition Philosophy

### 11.1 Stable edition count

ForestWatch **SHALL** maintain **three named editions** (Community, Professional,
Enterprise) plus the **public transparency layer** for the foreseeable future. Edition
proliferation **SHOULD NOT** occur — new commercial value **SHALL** arrive through
category expansion, geography expansion, and Enterprise extensions — not new edition tiers.

### 11.2 Forest Intelligence Platform identity

Edition marketing **SHALL** emphasize **cross-category forest intelligence** as
categories onboard through architecture phases. Wildfire **MUST NOT** be positioned as
the primary or default edition story.

### 11.3 Free tier permanence

Community Edition and the public layer **SHALL** remain free permanently. ForestWatch
**SHALL NOT** adopt a strategy that eliminates free access to public intelligence to
drive revenue.

### 11.4 Operational depth as moat

Commercial differentiation **SHALL** deepen **organizational operational capability** —
investigations, collaboration, Compliance, automation, integration — not restriction of
public trust assets.

### 11.5 Architecture-aligned expansion

New forest incident categories **SHALL** extend all applicable editions per platform
publication policy:

- **Public layer** — categories designated for public transparency;
- **Community** — bounded personal views of supported categories;
- **Professional / Enterprise** — full operational workflow for organizational scope.

Investigation workflow **SHALL** remain stable across editions (INVESTIGATION_FRAMEWORK §12).

### 11.6 Edition refinement

Edition boundaries **MAY** be refined as deployments validate upgrade triggers. Refinement
**MUST NOT**:

- move Compliance, automation, or API capability into Community;
- paywall public intelligence, open reports, or public maps;
- collapse Professional operational value into Community.

---

## 12. Relationship with Architecture

Architecture **enables** edition differentiation; it **does not define** editions.

| Architecture element | Edition relevance |
|---------------------|-----------------|
| **Intelligence Engine and reconciliation** | Powers public and all editions; single engine |
| **Read-only Command Center and Reporting (ADR-011)** | Public projections free; private operational views paid |
| **Investigation bounded context (INV-13)** | Operational investigations Professional+; not Community |
| **Compliance as product composition** | Professional+ only; no compliance engine tier |
| **Domain plug-in extension (ADR-005)** | Category expansion within edition scope |
| **Multi-tenancy reservation (ADR-010)** | Enterprise when implemented |
| **Scheduler and notifications (ADR-007)** | Automation Professional+; not Community |
| **Deterministic analytics (INV-4)** | Trust asset across all editions — especially public and audit sales |

**Hierarchy:**

1. Architecture and ADRs — platform capability and invariants
2. Business, product, and platform capability documents — product definition
3. Go-to-market strategy — customer motion
4. **This edition strategy** — authoritative free/paid boundary
5. Future pricing and packaging — derives from this document

Commercial edition promises **MUST NOT** require architecture violations. Edition
definitions **MUST NOT** imply a second intelligence pipeline, autonomous legal
conclusions, or non-forest scope.

---

## 13. Document Authority

### 13.1 Authoritative for

- What Community, Professional, and Enterprise **include and exclude**
- What remains **free forever** vs. **paid organizationally**
- Edition progression, upgrade, and downgrade principles
- Capability matrix for commercial decisions
- Resolution of free-vs-paid questions in sales, product, and support

### 13.2 Subordinate to

- `docs/architecture/` and ADRs — platform invariants and capability limits
- `docs/business/BUSINESS_STRATEGY.md` — long-term commercial direction
- `docs/business/PRODUCT_STRATEGY.md` — product identity and module definitions
- `docs/product/PLATFORM_CAPABILITIES.md` — capability responsibilities and boundaries
- `docs/product/INVESTIGATION_FRAMEWORK.md` — investigation workflow rules
- `docs/DOCUMENT_HIERARCHY.md` — business document precedence and edition entitlement split (§3.4, §4.2)

Where **PRODUCT_STRATEGY §9** and this document differ on edition capability lists,
**this document is authoritative** for edition entitlements per `docs/DOCUMENT_HIERARCHY.md`
§4.2 — not for product identity or module definitions.

### 13.3 Future documents that SHOULD derive from this one

| Document | Content derived |
|----------|-----------------|
| **Pricing and packaging guide** | Edition SKUs, packaging units, contract bundles |
| **Sales edition qualification guide** | Which edition to propose by ICP and trigger |
| **Customer contract capability schedule** | Legally binding capability list per edition |
| **In-product upgrade and entitlement specification** | Feature gating rules |
| **Community program terms** | Eligibility, limits, acceptable use |
| **Enterprise SLA schedule** | Reliability commitments tied to Enterprise |
| **API and integration license terms** | Enterprise API entitlement |

---

## Document Control

| Field | Value |
|-------|-------|
| Created | 2026-07-17 |
| Status | Pending review |
| Reconciliation | CMR-003 applied 2026-07-22 |
| Related business | `BUSINESS_STRATEGY.md`, `PRODUCT_STRATEGY.md`, `GO_TO_MARKET_STRATEGY.md` |
| Related product | `PLATFORM_CAPABILITIES.md`, `INVESTIGATION_FRAMEWORK.md` |
| Related architecture | `00-platform-vision.md`, `07-reporting-and-command-center.md`, `08-roadmap.md`, ADR-010, ADR-011 |

---

*End of Edition Strategy.*
