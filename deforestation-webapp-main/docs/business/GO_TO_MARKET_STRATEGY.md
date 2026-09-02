# ForestWatch — Go-To-Market Strategy

**Status:** Strategic document — pending review.
**Audience:** Commercial leadership, product, partnerships, sales, and customer-facing
stakeholders responsible for how ForestWatch reaches and serves customers.
**Authority:** This document defines **how ForestWatch reaches customers** — market
entry, acquisition, adoption, edition strategy, and commercial motion. It is subordinate
to `docs/business/BUSINESS_STRATEGY.md` for long-term commercial direction,
`docs/business/PRODUCT_STRATEGY.md` for product identity and editions,
`docs/product/PLATFORM_CAPABILITIES.md` for capability boundaries, and
`docs/architecture/` and its ADRs for what the platform may do. Where go-to-market
strategy and architecture disagree, architecture governs platform capability; where
go-to-market and business strategy disagree, business strategy governs commercial
direction.

**Document type:** Go-to-market strategy. This is not a business plan, financial forecast,
marketing campaign brief, implementation specification, or pricing schedule. It contains
no market-size estimates, revenue projections, or price points.

**Product identity:** ForestWatch is a **Forest Intelligence Platform** scoped to forest
ecosystems. Wildfire is one forest incident category among many — not the product
definition.

**Language:** The key words **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**,
**SHOULD NOT**, **MAY**, and **OPTIONAL** in this document are to be interpreted as
described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## 1. Commercial Philosophy

### 1.1 Forest intelligence is a public good; operational response is a paid service

ForestWatch shall pursue a commercial model built on a deliberate split:

| Layer | Access | Commercial role |
|-------|--------|-----------------|
| **Public transparency** | Open — publicly accessible derived intelligence, public reports, and public map views for configured geographies and categories | Builds trust, demonstrates capability, widens awareness of forest change |
| **Community Edition** | Free — personal registered access with bounded individual scope | Lowers adoption barrier for individual stewards, researchers, and pilot evaluators |
| **Professional and Enterprise** | Paid — full operational, collaborative, compliance, integration, and deployment capability | Where organizations pay for sustained forest stewardship at scale |

The platform **derives** intelligence; it does **not** author legal or enforcement
conclusions (INV-13). Public intelligence is **derived situational awareness**, not
human investigation findings. Public reports **SHALL** present derived intelligence and
aggregation — not investigation outcomes, private organizational data, or conclusions
that carry legal weight unless explicitly published by the owning organization through
its own processes.

### 1.2 Trust before transaction

ForestWatch competes on **operational forest intelligence** — persistence, cross-category
coherence, determinism, and investigation workflow — not on exclusive access to raw
observation data. Public intelligence and open reports **SHALL** increase trust and
adoption. They **MUST NOT** substitute for the paid capabilities organizations need to
**operate**: private investigations, team collaboration, compliance workflows, enterprise
reporting, administration, automation, integrations, and private deployment.

### 1.3 Free edition complements paid editions

Community Edition and the public transparency layer **SHALL** function as **top-of-funnel
and credibility assets**, not as replacements for Professional or Enterprise. The free
tier **MUST**:

- demonstrate Forest Intelligence Platform identity across multiple forest incident
  categories over time;
- expose enough derived intelligence for public and grant-funded stewards to validate
  value;
- create natural upgrade paths when organizations require operational depth, privacy,
  collaboration, or compliance.

The free tier **MUST NOT**:

- offer full multi-geography operational deployment;
- offer enterprise administration, private deployment, or multi-organization isolation;
- offer unrestricted API access, automation at scale, or compliance-grade audit exports;
- position ForestWatch as a consumer alert application or general-public safety product.

### 1.4 Engine before market promise

Commercial motion **SHALL** follow architecture phase ordering
(`docs/architecture/08-roadmap.md`). Forest incident categories **MUST NOT** be marketed
as available until intelligence, investigation, and reporting workflows are operational
for that category (PRODUCT_STRATEGY §10.2). Commercial urgency **MUST NOT** reorder
engineering phases or violate architecture invariants (IMPLEMENTATION_PROTOCOL).

### 1.5 Organizations, not consumers

ForestWatch serves **organizations responsible for forest ecosystems**. Go-to-market
motion targets institutional buyers and institutional users — governments, forestry
authorities, NGOs, corporate operators, certification bodies, research programs, and
integration partners. The public transparency layer serves **transparency and discovery**
for those organizations and the public — not a consumer product strategy.

---

## 2. Target Market

### 2.1 Primary customers

Primary customers are organizations with **sustained operational need** for forest
intelligence — daily or weekly use of Command Center, Investigations, and Reporting
across meaningful geography.

| Segment | Why primary | Edition fit | Near-term category relevance |
|---------|-------------|-------------|------------------------------|
| **Government agencies** | Jurisdictional forest mandate; briefing and inter-agency coordination; auditability requirements | Professional → Enterprise | Wildfire (mature); forest loss (Phase 2); future categories per roadmap |
| **Forestry authorities** | Day-to-day public forest operations across fire, loss, health, and compliance | Professional → Enterprise | Same as government; often first operational reference customers |
| **Corporate forestry** | Asset exposure, certification, and regulatory risk on managed forest land | Professional → Enterprise | Loss, fire, compliance categories |

*Strategic assumption:* Primary revenue concentrates in organizations that treat ForestWatch
as an **operational system of record** for forest situational awareness, not a periodic
reporting tool.

### 2.2 Secondary customers

Secondary customers derive significant value but **MAY** adopt later, consume exports
rather than operate daily, or require lighter deployment scope.

| Segment | Why secondary | Edition fit | Commercial motion |
|---------|---------------|-------------|-------------------|
| **Environmental NGOs** | Budget sensitivity; often single-geography; high Community Edition fit | Community → Professional | Community and public layer first; upgrade when scope or collaboration grows |
| **Certification organizations** | May consume reports and investigation exports from auditees rather than operate monitoring | Professional → Enterprise | Partner and export-led motion; reproducibility and audit artifacts |
| **Research institutions** | Reproducibility and export over operational UX; grant-aligned adoption | Community → Professional | Academic and open-data channels; citation and methodology trust |

### 2.3 Future customers

Future customers require **platform maturity** not yet available or validated commercially.

| Segment | Dependency | Target horizon |
|---------|------------|----------------|
| **Platform and integration partners** | Stable API contracts, multi-tenancy (ADR-010), white-label or embedded deployment | Year 3+ per BUSINESS_STRATEGY §14 |
| **Multi-organization networks** | Tenant isolation, domain-scoped authorization, partner onboarding | Year 2–4 when first multi-tenant deployment requires it |
| **National-scale deployments across many categories** | Phase 3 surface complete; three or more forest categories operational | Year 3–5 |

*Strategic assumption:* Partner and embedded revenue becomes meaningful only after
Professional and Enterprise reference deployments exist.

### 2.4 Explicit non-targets

Consistent with BUSINESS_STRATEGY §9.7 and PRODUCT_STRATEGY §12:

- Consumer and lifestyle environmental applications
- General-public emergency alert products without organizational operational context
- Pure data reselling without intelligence and workflow value
- Autonomous enforcement or legal-evidence systems without human investigation workflow
- Non-forest environmental domains (air, marine, urban pollution, general water)

---

## 3. Market Positioning

### 3.1 Category

ForestWatch occupies **Forest Intelligence Platform** — the operational layer between raw
forest observations and organizational response across forest incident categories.

### 3.2 Positioning statement

**For organizations responsible for forest stewardship across large or complex geographies,
ForestWatch is the Forest Intelligence Platform that transforms multi-source forest
observations into persistent, scored, auditable tracked situations — with a free public
transparency layer for trust and a paid operational platform for investigations,
compliance, collaboration, and enterprise deployment.**

### 3.3 Positioning pillars

| Pillar | Message |
|--------|---------|
| **Cross-category forest intelligence** | Fire, loss, disease, compliance, and future categories in one product — not a wildfire or deforestation-only tool |
| **Persistent situations, not alert feeds** | Tracked intelligence with history, trend, and lifecycle — not ephemeral detections |
| **Human accountability** | Investigations quarantine judgment; derived intelligence is not legal conclusion |
| **Open trust, paid operations** | Public intelligence builds credibility; organizations pay to operate on it privately |
| **Auditable and deterministic** | Intelligence outputs reproducible from documented inputs — decisive in regulatory and certification contexts |
| **Extensible without replacement** | New forest categories extend the same product through configuration |

### 3.4 Positioning discipline

ForestWatch **MUST NOT** be marketed as:

- a wildfire alert platform (wildfire is one category);
- a deforestation-only dashboard (forest loss is one category);
- a generic environmental intelligence suite;
- a GIS or map-first product (maps support exploration; intelligence and workflow are core);
- a substitute for field verification, legal process, or auditor judgment.

---

## 4. Ideal Customer Profile

An **ideal customer** for paid adoption exhibits most of the following:

### 4.1 Organizational fit

- Statutory, contractual, or mission-driven responsibility for **forest ecosystems** over
  defined geography
- Operational team (not only research or IT) that acts on forest change — dispatch,
  compliance, conservation response, or estate management
- Capacity to assign analysts or field staff to **investigations**, not only to view alerts

### 4.2 Problem fit

- Currently correlates **multiple single-category tools** or raw feeds manually
- Suffers **alert fatigue** or **situation amnesia** from non-persistent alerting
- Must produce **defensible reports** for leadership, regulators, donors, or certification
- Needs **cross-category visibility** (e.g., fire followed by logging in same region)

### 4.3 Technical and data fit

- Operates in geographies where **configured observation sources** are accessible
- Accepts that intelligence is **derived and deterministic**, not a black-box prediction
- Willing to configure geography, categories, and thresholds — or engage services for
  initial setup

### 4.4 Commercial fit

- Budget for **sustained operational software**, not one-time analysis
- Path to **Professional or Enterprise** when pilot proves daily Command Center use and
  investigation closure
- For Enterprise: data-sovereignty, multi-site, or multi-organization requirements

### 4.5 Anti-profile (poor fit)

- Seeks only a **free public map** with no organizational operational intent
- Requires **non-forest environmental monitoring** as core scope
- Expects **autonomous enforcement findings** without investigation workflow
- Needs full capability before **architecture phase** delivers the relevant forest category

---

## 5. Customer Acquisition Strategy

Acquisition **SHALL** combine trust-building through the public layer with targeted
institutional outreach. No channel **SHALL** promise capabilities outside architecture
phase readiness.

### 5.1 Organic

**Motion:** Public intelligence, open reports, public maps, documentation, and
demonstrable reproducibility attract inbound interest from stewards who discover forest
change through ForestWatch before contacting sales.

**Tactics:**

- Publish **public derived intelligence** and **open report snapshots** for configured
  reference geographies as categories become operational
- Content explaining **forest incident categories**, reconciliation, and investigation
  separation — not feature lists alone
- Case narratives (when available) emphasizing **cross-category operational outcomes**
- SEO and discovery around **forest intelligence** — not wildfire-only keywords

**Guardrail:** Organic reach **MUST NOT** position public views as operational systems
for emergency response without organizational adoption.

### 5.2 Partnerships

**Motion:** Forest management platforms, supply-chain traceability, insurance risk tools,
emergency coordination systems with forest mandate, and conservation networks embed or
recommend ForestWatch intelligence.

**Tactics:**

- **Certification and audit ecosystems** — reproducible reports and investigation exports
  as assessment inputs
- **Conservation networks** — Community Edition adoption at site level with network-level
  Professional upgrade path
- **Technology partners** — API and integration access (Enterprise; Year 3+ target)

**Dependency:** Partner channel **SHALL** remain secondary until API stability and
multi-tenancy maturity per ADR-010 and BUSINESS_STRATEGY §14 Year 3 objective.

### 5.3 Government

**Motion:** Pilot and procurement-led adoption for jurisdictional forest situational
awareness — ministries, regional agencies, park services, civil protection with forest
mandate.

**Tactics:**

- **Reference geography pilots** aligned with Phase 2–3 readiness (wildfire + forest loss)
- Emphasis on **audit reproducibility**, investigation records, and scheduled briefing reports
- **Public transparency layer** as credibility during long procurement cycles — citizens
  and oversight bodies see derived intelligence while agency operational workflow remains
  on paid deployment
- Alignment with **public procurement** processes (Section 6.4)

**Assumption:** Government cycles are long; public trust assets and forestry authority
references reduce perceived risk during evaluation.

### 5.4 NGOs

**Motion:** Individual registration on Community Edition and public layer as entry;
upgrade to Professional when organizational scope, geography, collaboration, or compliance
needs emerge.

**Tactics:**

- **Grant-aligned positioning** — ForestWatch as operational evidence for donor reporting
- Protected-area and advocacy use cases leveraging **Phase 1 spatial overlays**
- Training and lightweight onboarding — NGOs lack dedicated GIS staff (PRODUCT_STRATEGY §6.3)
- **Open reports** for public advocacy timing without exposing private investigation records

**Upgrade trigger:** Multi-site monitoring, team investigation assignment, scheduled
reporting, or compliance overlay configuration.

### 5.5 Enterprise

**Motion:** Direct enterprise sales for corporate forestry, large public estates, and
national agencies requiring private deployment, extended compliance, and integration.

**Tactics:**

- **Proof of operational depth** — Command Center daily use, investigation closure rates,
  report exports in external processes
- **Private deployment and data sovereignty** as Enterprise differentiators
- **Category expansion** as natural land-and-expand — additional forest incident
  categories registered on same deployment
- Executive briefings using **public intelligence** for context and **private operational
  views** for action

### 5.6 API ecosystem

**Motion:** Developers and partners build on deterministic intelligence outputs — not raw
observation reprocessing.

**Tactics:**

- Tiered **API access** as paid Enterprise capability (BUSINESS_STRATEGY §10.1)
- Developer documentation emphasizing **read-only intelligence projections** and
  investigation boundaries
- **Developer community** seeded through Community Edition and public data views;
  production integration on Professional/Enterprise

**Guardrail:** API consumers **MUST NOT** present derived intelligence as human legal
findings; integration terms **SHOULD** reflect INV-13.

### 5.7 Academic

**Motion:** Research institutions adopt Community Edition for reproducible operational
tracking during study periods; contribute methodological credibility.

**Tactics:**

- **Educational usage** — courses and research programs using public intelligence and
  Community Edition for reproducibility exercises
- **Export artifacts** for publication and grant reporting (Historical Analysis, Reporting)
- Partnerships with forest research institutes as **reference methodologies** for
  deterministic reconciliation

**Commercial path:** Research programs that become operational monitoring programs
upgrade to Professional; academic citation **SHALL** increase public layer credibility.

---

## 6. Sales Strategy

Sales motion **SHALL** match customer segment, edition, and deployment maturity. No sale
**SHALL** commit to forest categories or integrations not yet supported by architecture
phase completion.

### 6.1 Self-service

**Fit:** Community Edition — NGOs, small stewards, research pilots, single-geography
operators.

**Motion:**

- Self-registration for **free Community Edition**
- Guided setup for geography scope and supported categories within edition limits
- In-product upgrade prompts when usage exceeds Community boundaries (multi-geography,
  collaboration, compliance configuration, scheduled reporting at scale, API access)

**Maturity note:** Full self-service onboarding **MAY** require professional services
bridge until Year 2 self-service template objective (BUSINESS_STRATEGY §14). Until then,
self-service **SHALL** be supplemented by documented setup and optional services.

### 6.2 Enterprise sales

**Fit:** National agencies, large forestry estates, corporate operators, certification
bodies at scale.

**Motion:**

- Discovery against ideal customer profile (Section 4)
- Pilot scoped to **one geography and operational categories available per roadmap**
- Proof-of-value metrics: Command Center adoption, investigations opened and closed,
  reports used externally
- Expansion proposal: additional categories, geographies, Compliance configuration,
  private deployment, SLAs

**Enterprise paid capabilities include:**

- Private operational deployment (self-hosted or dedicated)
- Multi-geography and multi-organization scope when multi-tenancy is available
- Extended Compliance and enterprise Reporting
- Full Administration — users, roles, retention, audit export policies
- API, integrations, and automation
- Dedicated support and SLA commitments

### 6.3 Partner sales

**Fit:** Integration partners, certification ecosystems, regional resellers with forest
sector expertise.

**Motion:**

- Partner enables customer on Professional or Enterprise
- Partner delivers vertical workflow integration; ForestWatch delivers forest intelligence
  layer
- Revenue share or licensing model — defined commercially outside this document

**Prerequisite:** Partner program **SHOULD NOT** launch before Year 3 partner channel
objective and API maturity.

### 6.4 Public procurement

**Fit:** Government agencies and public forestry authorities.

**Motion:**

- Transparent **public intelligence** during evaluation — demonstrates capability without
  exposing private operational data
- Procurement packages emphasizing **deterministic audit trail**, investigation workflow,
  and export reproducibility
- Phased contract alignment with **roadmap-delivered categories** — avoid committing
  future categories by fixed date without engineering gate
- Professional services for deployment, investigation workflow design, and training where
  required

**Principle:** Public procurement **SHALL** separate **public transparency deliverables**
(open reports, public maps) from **operational system deliverables** (private
investigations, administration, integrations).

---

## 7. Adoption Strategy

### 7.1 How organizations begin

Typical adoption paths:

| Entry path | First experience | Paid conversion driver |
|------------|------------------|------------------------|
| **Public discovery** | Public map and open reports | Organization needs private investigations and team workflow |
| **Community Edition** | Free personal registered access in bounded geography | Organizational scope, collaboration, investigations, or compliance exceeds Community limits |
| **Pilot (Professional)** | Paid or committed pilot with services support | Pilot proves daily operations; expands geography and categories |
| **Enterprise RFP** | Procurement evaluation with public + private demo | Contract for private deployment and full Administration |

**Phase 0–1:** Adoption **SHALL** emphasize wildfire operational continuity and trust
preservation — no positioning regression.

**Phase 2–3:** Adoption **SHALL** lead with **two-category forest intelligence** (wildfire
+ forest loss) as proof of Forest Intelligence Platform identity.

**First operational habits to establish:**

1. Command Center as **daily situational surface** (PRODUCT_STRATEGY P-6)
2. Intelligence Events as **unit of attention**, not raw detections
3. Investigations for situations requiring **human judgment** (INVESTIGATION_FRAMEWORK)
4. Reports exported into **at least one external process** (briefing, grant, audit)

### 7.2 How organizations expand usage

Land-and-expand **SHALL** follow natural platform extension — aligned with ADR-005 plug-in
model:

1. **Geography expansion** — additional regions within same categories
2. **Category expansion** — new forest incident categories as architecture onboard them
3. **Workflow depth** — Compliance module, scheduled reporting, notification routing
4. **Collaboration** — multi-user investigation assignment and cross-team visibility
5. **Integration** — API and partner systems feeding or consuming intelligence
6. **Historical depth** — extended retention and retrospective analysis for audit and research

Each expansion **SHALL** reuse the same product modules (PLATFORM_CAPABILITIES §7) —
not a new product sale.

### 7.3 Edition progression

| From | To | Typical triggers |
|------|-----|------------------|
| **Public only** | **Community** | Individual registers for personal workspace and bounded intelligence views |
| **Community** | **Professional** | Multi-region scope; full category set; collaboration; Compliance; scheduled reporting; notifications |
| **Professional** | **Enterprise** | Private deployment; multi-organization isolation; API/integration; custom category onboarding; SLA; advanced audit policy |

Edition boundaries **SHALL** follow PRODUCT_STRATEGY §9 capability lists, interpreted
through the commercial model in Section 1:

- **Free (Community + public layer):** intelligence visibility, public reports, bounded
  personal workspace — not organizational operations or investigations
- **Paid (Professional + Enterprise):** full operational use, investigations at organizational
  scale, collaboration, compliance workflows, enterprise reporting, administration, APIs,
  integrations, automation, private deployment

*Strategic assumption:* Edition definitions **MAY** be refined as deployments validate
upgrade triggers; refinement **MUST NOT** collapse paid operational value into the free tier.

---

## 8. Community Strategy

### 8.1 Free Community Edition

Community Edition **SHALL** be **free permanently** for eligible personal registered
use within defined capability limits (`docs/business/EDITION_STRATEGY.md` §2;
PRODUCT_STRATEGY §9.1 for product context). It exists to:

- lower adoption friction for NGOs, researchers, and pilot stewards;
- produce **reference users** and methodological credibility;
- feed Professional upgrade pipeline when scope grows.

Community Edition **SHALL NOT** include full Enterprise administration, private deployment,
unrestricted API access, or multi-organization tenant isolation.

### 8.2 Open reports

ForestWatch **SHALL** publish **open report snapshots** — point-in-time, read-only
artifacts derived from public intelligence configuration. Open reports:

- demonstrate **Reporting capability** and deterministic composition;
- support advocacy, journalism, and public oversight with **derived intelligence only**;
- **MUST NOT** include private investigation outcomes or organization-specific compliance
  findings unless explicitly authorized for publication by the owning organization.

Paid customers retain **private report generation**, scheduled delivery, compliance
sections, and audit export policies not available in open reports.

### 8.3 Public intelligence

**Public intelligence** is derived, reconciled forest situational data — Intelligence
Events and aggregations configured for public visibility. It **SHALL**:

- show **persistent tracked situations** across onboarded public categories;
- include scoring, trend, and category segmentation with appropriate disclaimers (derived
  intelligence, not legal finding);
- update on the same reconciliation cadence as operational deployments for configured
  public scope.

Public intelligence **MUST NOT** expose private organizational investigations, internal
administration configuration, or tenant-partitioned data.

### 8.4 Public maps

Public maps **SHALL** provide spatial exploration of public intelligence — category filters,
regional views, and domain status for configured public geographies. Maps are an
**exploration surface** (PRODUCT_STRATEGY §12), not the product core.

Paid editions add **operational map integration** — linking map context to private
investigations, Compliance overlays, custom boundaries, and administration-controlled scope.

### 8.5 Developer ecosystem

A **developer ecosystem** **SHALL** emerge from:

- public intelligence and open report formats as **reference outputs**;
- Community Edition for experimentation;
- paid API access on Enterprise for production integrations.

Developers **SHALL** be encouraged to build applications that consume **read-only
intelligence projections** — not to reimplement reconciliation or violate investigation
boundaries.

### 8.6 Educational usage

Educational usage **SHALL** be permitted and encouraged through Community Edition and
public assets:

- university forest monitoring and GIS courses;
- research methods training on deterministic reconciliation;
- grant-funded student projects with bounded geography.

Educational adoption **SHALL** prioritize **reproducibility and methodology** — aligned
with research segment needs (PRODUCT_STRATEGY §5.6).

### 8.7 Why the public version increases commercial value

The public and Community layers **SHALL** increase commercial value — not compete with it —
through:

| Mechanism | Commercial effect |
|-----------|-------------------|
| **Trust and verification** | Prospects validate intelligence quality before procurement |
| **Category credibility** | Public multi-category views prove Forest Intelligence Platform identity beyond wildfire |
| **Reduced sales friction** | Evaluators compare paid operational workflow against known public baseline |
| **NGO and academic funnel** | Free tier produces upgrades when operational scope grows |
| **Partner confidence** | Integrators test against stable public outputs before Enterprise API commitment |
| **Mission alignment** | Transparency supports conservation and public forest stewardship narratives — strengthening brand with primary government and NGO buyers |
| **Differentiation from data feeds** | Public layer shows **reconciled intelligence value**, not raw observation republishing — clarifying why organizations pay for operations |

**Critical boundary:** Value capture **SHALL** occur at **organizational operational
capability** — investigations, collaboration, compliance, private reporting, administration,
integrations, automation, and deployment — not at access to basic derived intelligence
for public transparency.

---

## 9. Enterprise Strategy

### 9.1 Private deployments

Enterprise customers **MAY** require **self-hosted or dedicated deployment** for data
sovereignty, air-gapped operation, or contractual isolation (PRODUCT_STRATEGY §9.3).

**Commercial principles:**

- Private deployment **SHALL** carry the full operational capability set — not a reduced
  feature fork
- Public transparency layer **MAY** coexist — organization chooses what intelligence is
  published publicly vs. held privately
- Deployment options **SHALL NOT** fragment the intelligence engine or violate architecture
  invariants

### 9.2 Multi-tenancy

Multi-organization isolation **SHALL** follow ADR-010: reserved identity dimension,
implemented when first deployment requires tenant boundaries — target Year 2 per
BUSINESS_STRATEGY §14.

Enterprise go-to-market **SHALL NOT** promise multi-tenant production isolation before
ADR-010 implementation is complete. Sales **MAY** commit to **roadmap-aligned delivery**
with explicit phase gates.

### 9.3 Security

Enterprise security positioning **SHALL** emphasize:

- deterministic, auditable intelligence pipeline;
- investigation and administration audit trails;
- access control within organizational scope;
- no mutation of intelligence from read paths (ADR-011);
- data provider license boundaries respected at ingestion.

Security claims **MUST NOT** imply autonomous legal-evidence certification without human
investigation workflow.

### 9.4 Compliance

Enterprise Compliance **SHALL** leverage the product composition model (Intelligence +
Investigations + Reporting + spatial overlays) — not a separate engine. Sales **SHALL**
position compliance as:

- continuous monitoring between audits;
- investigation-backed human findings for certification and regulatory response;
- exportable point-in-time compliance reports;
- protected-area and jurisdictional overlay context (Phase 1+).

Compliance conclusions **MUST** flow through Investigations (INV-13) in all editions.

### 9.5 Support

Enterprise **SHALL** include dedicated onboarding and operational support (PRODUCT_STRATEGY
§9.3). Support scope **SHALL** cover:

- deployment and configuration assistance;
- investigation workflow design for organizational policy;
- category and geography expansion within product scope;
- escalation path for operational cycle failures.

Community Edition **SHALL** rely on community documentation and optional paid services —
not enterprise SLA support.

### 9.6 SLAs

Enterprise SLAs **SHALL** address **operational reliability** — scheduler cycle
completion, intelligence pipeline integrity, report generation availability — not
predictive accuracy of detections. SLA framing **SHALL** align with architecture: freshness
follows reconciliation cadence; read paths do not trigger reconciliation.

Specific SLA terms are commercial contracts — outside this document.

---

## 10. Competitive Positioning

Without naming competitors, ForestWatch **SHALL** differentiate against these
**alternative approaches**:

| Alternative | ForestWatch response |
|-------------|---------------------|
| **Single-category alert tools** (fire-only, loss-only) | Cross-category forest intelligence in one operational product; persistent situations across categories |
| **Raw data feeds and portals** | Reconciled intelligence with lifecycle, scoring, and explainability — public layer proves value above raw access |
| **General-purpose GIS platforms** | Purpose-built forest intelligence and investigation workflow — maps support, not define, the product |
| **Generic environmental dashboards** | Forest vertical depth; refuses non-forest scope dilution |
| **Ephemeral alert systems** | Situation continuity across cycles; Historical Analysis and audit reproducibility |
| **Black-box analytics** | Deterministic outputs; evidence and provenance exposed |
| **Dashboard-only exports** | Point-in-time composed reports for external audit and briefing |
| **Automated enforcement platforms** | Human investigation layer; derived intelligence separated from legal conclusion |

**Competitive moat sources** (from BUSINESS_STRATEGY §8): unified engine, extension model,
deterministic auditability, spatial service compounding, operational workflow integration,
scope discipline.

**Competitive vulnerability** (acknowledged): long government cycles, free public data
alternatives, incumbent GIS expansion — mitigated by operational workflow depth and public
trust strategy (BUSINESS_STRATEGY §13.2).

---

## 11. Growth Strategy (Years 1–5)

Growth **SHALL** align with BUSINESS_STRATEGY §14 and architecture Phases 0–3. Commercial
identity remains **Forest Intelligence Platform** throughout.

### Year 1 (2026–2027) — Foundation and first trust assets

**Engineering gate:** Phase 0–1 complete; Phase 2 forest-loss onboarding underway; Phase 3
surface targeting Version 1.0.0.

**Go-to-market:**

- Establish **public intelligence and open reports** for reference geography as categories
  become operational
- Launch **free Community Edition** for NGO and research entry
- Close **first paid pilot or operational deployment** with investigation workflow in use
- Sales focus: forestry authorities and regional agencies; one government pilot path
- Messaging shift: from single-category perception toward **forest intelligence** language

**Success signal:** At least one organization uses Command Center and Investigations in
real operations — not demonstration alone.

### Year 2 (2027–2028) — Validation and self-service

**Engineering gate:** Phase 3 complete (v1.0.0); multi-tenancy if required by deployment;
expanded ingestion providers.

**Go-to-market:**

- **Two-category operational proof** — wildfire and forest loss in public and paid deployments
- Self-service onboarding template for at least one geography/category configuration
- Expand NGO and corporate forestry Community → Professional conversion motion
- First **public procurement** completion or advanced stage
- Reduce services dependency for standard Professional deployments

**Success signal:** Second geography or segment without engine modification; external report
used in stakeholder process.

### Year 3 (2028–2029) — Expansion and partners

**Go-to-market:**

- Onboard **third forest incident category** commercially (candidate: pest/disease or
  degradation — market validation)
- Launch **partner/API channel** with Enterprise integration customers
- Enterprise sales for national-scale and multi-site corporate forestry
- Cross-category Command Center as standard sales narrative

**Success signal:** Partner integration live; three categories operational in at least one
paid deployment.

### Year 4 (2029–2030) — Scale

**Go-to-market:**

- Multi-tenant deployments with domain-scoped authorization
- Two additional forest categories from roadmap §7
- Enterprise SLAs and private deployment as standard Enterprise offer
- Certification body and audit-firm channel matured

**Success signal:** Multiple tenants; category onboarding primarily via configuration.

### Year 5 (2030–2031) — Platform maturity

**Go-to-market:**

- ForestWatch recognized in target segments as **Forest Intelligence Platform**
- Category expansion as **upsell**, not new product sale
- Sustainable mix: Community funnel, Professional operational core, Enterprise strategic accounts
- Public layer and Community Edition remain **free trust assets** — paid revenue from
  operational depth

**Success signal:** Commercial model validated across at least two customer categories;
services-to-subscription ratio declining.

---

## 12. Success Metrics

Metrics are **directional** until deployment baselines exist. No financial quotas are set
here.

### 12.1 Commercial KPIs

| Metric | Indicates |
|--------|-----------|
| Paid organizations (Professional + Enterprise) | Core revenue-bearing customer count |
| Community → Professional conversion rate | Free tier funnel effectiveness |
| Professional → Enterprise expansion rate | Land-and-expand success |
| Pilot-to-paid conversion | Sales motion effectiveness |
| Category/geography expansion within accounts | Natural upsell aligned with plug-in architecture |
| Partner-sourced opportunities (Year 3+) | Channel maturity |
| Public procurement wins or advanced pipeline | Government motion progress |
| Services-to-subscription ratio (declining) | Self-service maturity |

*Deferred until baselines exist:* ARR, CAC, NRR, market share (BUSINESS_STRATEGY §15.5).

### 12.2 Product KPIs

| Metric | Indicates |
|--------|-----------|
| Public intelligence and open report engagement | Trust asset reach |
| Command Center daily active use (paid deployments) | Operational adoption |
| Investigations opened, progressed, and closed | Human workflow adoption — paid value |
| Report exports used in external processes | Audit and briefing value realization |
| Multi-category usage in single deployment | Forest Intelligence Platform identity |
| False-positive rate within operator tolerance | Trust maintenance |
| Audit reproducibility demonstrations | Deterministic value in sales and retention |

### 12.3 Adoption KPIs

| Metric | Indicates |
|--------|-----------|
| Community Edition registered organizations | Top-of-funnel volume |
| Time from registration to first operational session | Onboarding effectiveness |
| Geography and category scope growth per account | Expansion health |
| API/integration consumers (Enterprise) | Ecosystem adoption |
| Educational and research program adoption | Methodology credibility |
| Reference customers willing to provide public case narrative | Market proof |

---

## 13. Non-Goals

This go-to-market strategy **deliberately excludes** and **SHALL NOT** pursue:

| Non-goal | Rationale |
|----------|-----------|
| **Market-size or revenue projections** | Requires primary research; deferred |
| **Pricing and packaging detail** | Defined in separate commercial documents |
| **Implementation, APIs, or infrastructure** | Engineering and architecture domains |
| **Consumer alert product GTM** | Organization-focused; public layer is transparency not consumer app |
| **Non-forest environmental market entry** | Outside Forest Intelligence Platform scope |
| **Wildfire-only marketing** | Contradicts product identity |
| **Selling raw data access as primary value** | Intelligence and workflow are the product |
| **Autonomous enforcement GTM** | Violates INV-13 and product boundaries |
| **Promising categories before architecture readiness** | Violates phase ordering |
| **Competing with paid editions via free tier** | Free tier builds trust; operations are paid |
| **Naming or attacking specific competitors** | Positioning by category, not vendor warfare |

---

## 14. Relationship with Architecture

Architecture **enables** commercialization; it **does not define** it.

| Architecture provides | Go-to-market consumes |
|-----------------------|----------------------|
| Multi-category intelligence engine (Phases 0–3) | Credible Forest Intelligence Platform narrative |
| Domain plug-in extension (ADR-005) | Category expansion upsell without new product |
| Deterministic reconciliation (INV-4) | Audit and procurement differentiation |
| Investigation bounded context (INV-13) | Paid operational workflow; public layer excludes private findings |
| Read-only Command Center and Reporting (ADR-011) | Public projections vs. private operational deployment |
| Multi-tenancy reservation (ADR-010) | Enterprise multi-organization promise — when implemented |
| Forest-only product scope (00-platform-vision §2.1) | Positioning discipline |

**Hierarchy:**

1. **Architecture and ADRs** — what the platform **may** do; invariants that **must** hold
2. **Business strategy** — long-term commercial direction and competitive context
3. **Product strategy and platform capabilities** — what users experience; edition capability
4. **This go-to-market strategy** — how customers are reached, adopt, and pay
5. **Implementation protocol and engineering phases** — when capabilities become real

Commercial commitments **MUST NOT** force architecture violations. Sales **MUST** stop
and escalate when a deal requires capabilities outside phase readiness or invariants
(IMPLEMENTATION_PROTOCOL stop conditions).

The **public transparency layer** is a **commercial and product policy** choice to publish
selected read-only intelligence projections — not an architecture subsystem. Architecture
permits read-only projections; go-to-market defines which projections are public vs. private.

---

## 15. Document Authority

### 15.1 This document governs

- Customer acquisition channels and segment priority
- Edition and free-tier commercial motion
- Public intelligence, open reports, and Community Edition strategy
- Sales motion by segment (self-service, enterprise, partner, procurement)
- Adoption and land-and-expand patterns
- Enterprise positioning (deployment, support, SLA framing)
- Go-to-market phase alignment with Years 1–5
- Commercial success metrics for GTM review

### 15.2 This document does not govern

- Product capability definitions → `PRODUCT_STRATEGY.md`, `PLATFORM_CAPABILITIES.md`
- Investigation workflow → `INVESTIGATION_FRAMEWORK.md`
- Platform invariants and engineering execution → `docs/architecture/`, `docs/engineering/`
- Pricing, contracts, and financial targets → future commercial documents

### 15.3 Future documents that SHOULD derive from this one

| Future document | Derives |
|-----------------|---------|
| **Pricing and packaging guide** | Edition boundaries and paid capability split from Sections 1, 7, 8, 9 |
| **Sales playbook** | ICP, positioning, segment motion, competitive framing (Sections 3–6, 10) |
| **Partner program guide** | Partnership and API ecosystem strategy (Sections 5.2, 5.6, 6.3) |
| **Community and developer program guide** | Public layer, Community Edition, educational and developer motion (Section 8) |
| **Enterprise procurement kit** | Public vs. private deliverables, compliance, SLA framing (Sections 6.4, 9) |
| **Marketing messaging guide** | Positioning pillars, category language, wildfire-as-one-category discipline (Section 3) |
| **Customer success and adoption playbook** | Adoption paths, expansion triggers, edition progression (Section 7) |

*Strategic assumption:* These documents **SHOULD NOT** be created until this strategy is
reviewed and approved.

---

## Document Control

| Field | Value |
|-------|-------|
| Created | 2026-07-17 |
| Status | Pending review |
| Reconciliation | CMR-001, CMR-002 applied 2026-07-22 |
| Related business | `BUSINESS_STRATEGY.md`, `PRODUCT_STRATEGY.md`, `EDITION_STRATEGY.md` |
| Related product | `PLATFORM_CAPABILITIES.md`, `INVESTIGATION_FRAMEWORK.md` |
| Related architecture | `00-platform-vision.md`, `08-roadmap.md`, ADR-005, ADR-010, ADR-011 |
| Related engineering | `IMPLEMENTATION_PROTOCOL.md` |

---

*End of Go-To-Market Strategy.*
