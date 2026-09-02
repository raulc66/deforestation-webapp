# ForestWatch — Commercial Model Reconciliation

**Status:** Reconciliation analysis — pending review.
**Audience:** Product leadership, commercial leadership, engineering leadership, and
documentation maintainers.
**Authority:** This document **does not override** any other document. It catalogs
**unresolved contradictions** discovered across the commercial and product documentation
stack, recommends canonical resolutions, and defines a **prioritized reconciliation backlog**.
Implementation **MUST NOT** treat this document as normative until contradictions are
resolved through the processes in `docs/DOCUMENT_HIERARCHY.md`.

**Document type:** Reconciliation analysis. Not strategy, not architecture, not
implementation specification.

**Scope:** Contradictions accumulated across reviews of:

- `docs/business/BUSINESS_STRATEGY.md`
- `docs/business/PRODUCT_STRATEGY.md`
- `docs/business/GO_TO_MARKET_STRATEGY.md`
- `docs/business/EDITION_STRATEGY.md`
- `docs/product/PLATFORM_CAPABILITIES.md`
- `docs/product/INVESTIGATION_FRAMEWORK.md`
- `docs/product/ACCESS_CONTROL_MODEL.md`
- `docs/DOCUMENT_HIERARCHY.md`

**Related but out of scope for detailed re-analysis:** as-built development docs
(`docs/ARCHITECTURE.md`), frozen `docs/architecture/CHANGELOG.md` v1.0 summary text,
`docs/engineering/IMPLEMENTATION_PROTOCOL.md` open items C-5 and C-6 — cited where they
block readiness estimates.

**Language:** The key words **MUST**, **MUST NOT**, **SHALL**, **SHOULD**, and **MAY**
are interpreted per RFC 2119 where used in recommendations.

---

## 1. Purpose

ForestWatch accumulated a commercial and product documentation stack rapidly during the
transition from architecture completion to commercial definition. Multiple review cycles
(PC, EDT, GTM, ACM, DH, IC) reported **recurring contradictions** that were **documented
but not resolved**, because reconciliation instructions explicitly forbade modifying
source documents during those passes.

This document:

1. Consolidates **every repeatedly reported contradiction** into one registry.
2. Classifies each item as real contradiction, terminology difference, hierarchy issue,
   or intentional transition.
3. Recommends **one canonical resolution** per item.
4. Lists **documents requiring modification** and the **authoritative document after reconciliation**.
5. Produces a **prioritized reconciliation backlog** with impact classification.

**No source document is modified by this analysis.**

---

## 2. Reconciliation Principles

When applying recommended resolutions:

| Principle | Rule |
|-----------|------|
| **Architecture wins on technical truth** | No commercial doc may require invariant violations. |
| **Single canonical owner per question type** | See `DOCUMENT_HIERARCHY.md` §4.2 — amended after this reconciliation. |
| **Edition capability questions** | Resolve to **one** business owner after hierarchy fix (CMR-003). |
| **Community model** | Resolve to **one** actor model: personal vs. organizational (CMR-001, CMR-002). |
| **Pending review ≠ approved** | Strategic docs marked pending review **MUST NOT** drive entitlement implementation until reconciled and approved. |
| **Intentional transitions** | Newer freemium/public-layer model **SHOULD** supersede older subscription-only implied models — but **must be written back** into authoritative docs. |

---

## 3. Contradiction Registry

Each entry uses a unique identifier **CMR-NNN**. **Repeat count** indicates how many
independent review passes reported the same issue.

---

### CMR-001 — Community Edition includes investigations vs. investigations are paid-only

| Field | Value |
|-------|-------|
| **Repeat count** | 6 (PC-1, EDT-1, GTM-5, ACM-1, DH conflict table, EDITION vs PRODUCT) |
| **Classification** | **Real contradiction** |
| **Priority** | **Critical** |
| **Impact** | Business, Product, Implementation, Documentation |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **PRODUCT_STRATEGY §9.1** | Community includes **“Basic Investigations workflow.”** |
| **EDITION_STRATEGY §2.8** | **“Personal investigations are not included in Community Edition.”** Operational investigations require Professional. |
| **ACCESS_CONTROL_MODEL §4.1, §11** | Community users **cannot** create or edit investigations. |
| **GO_TO_MARKET_STRATEGY §1.1, §7.3** | Organizations pay for **investigations**; free tier is visibility, not operational response. |
| **DOCUMENT_HIERARCHY §5.3** | Explicit conflict: Community investigations — report and resolve. |

**Recommended canonical resolution:**

Community Edition **does not** include operational investigation workflow. Personal
workspace annotations **are not** investigations. **Professional minimum** is required
to open, assign, progress, close, and audit investigation cases.

**Documents to modify:**

1. `docs/business/PRODUCT_STRATEGY.md` §9.1 — remove “Basic Investigations workflow”; clarify personal workspace vs. investigations.
2. `docs/business/GO_TO_MARKET_STRATEGY.md` — align Community descriptions (see CMR-002).
3. `docs/DOCUMENT_HIERARCHY.md` — mark resolved after PRODUCT_STRATEGY update.

**Do not modify:** `EDITION_STRATEGY.md`, `ACCESS_CONTROL_MODEL.md`, `INVESTIGATION_FRAMEWORK.md` (already aligned with recommended resolution).

**Authoritative after reconciliation:** **EDITION_STRATEGY.md** for edition capability matrix; **INVESTIGATION_FRAMEWORK.md** for workflow rules; **ACCESS_CONTROL_MODEL.md** for authorization.

---

### CMR-002 — Community Edition actor model: personal vs. organizational

| Field | Value |
|-------|-------|
| **Repeat count** | 5 (EDT-2, GTM-2, ACM-2, ACM-3, GTM internal) |
| **Classification** | **Real contradiction** |
| **Priority** | **Critical** |
| **Impact** | Business, Product, Documentation |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **GO_TO_MARKET §1.1** | Community = **“Free — organizational access with limited operational scope.”** |
| **GO_TO_MARKET §8.1** | Community = **“free permanently for eligible organizational use.”** |
| **EDITION_STRATEGY §2** | Community = **free registered personal access**; **not** organizational operations. |
| **ACCESS_CONTROL_MODEL §4–6** | Community = **single-user personal workspace**; collaboration requires Professional organization. |
| **EDITION_STRATEGY §9.3** | **Second user → Professional** — no multi-user Community. |

**Recommended canonical resolution:**

Community Edition is a **registered personal account** with bounded individual scope —
**not** an organization. NGOs and small teams **enter** via Community individually and
**upgrade to Professional** when collaboration, investigations, or org scope is needed.

**Documents to modify:**

1. `docs/business/GO_TO_MARKET_STRATEGY.md` §1.1, §8.1, §5.4, §7.1 — replace “organizational access” with “personal registered access.”
2. `docs/business/PRODUCT_STRATEGY.md` §9.1 intended segment — clarify solo/individual entry, not org deployment.

**Authoritative after reconciliation:** **EDITION_STRATEGY.md** (actor and edition model); **ACCESS_CONTROL_MODEL.md** (authorization).

---

### CMR-003 — Business document precedence: PRODUCT_STRATEGY vs. EDITION_STRATEGY

| Field | Value |
|-------|-------|
| **Repeat count** | 4 (EDT-13, ACM-5, DH-2, EDITION §13.2) |
| **Classification** | **Hierarchy issue** |
| **Priority** | **High** |
| **Impact** | Documentation, Business |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **DOCUMENT_HIERARCHY §3.4** | Business precedence: (1) BUSINESS_STRATEGY, (2) **PRODUCT_STRATEGY**, (3) **EDITION_STRATEGY**, (4) GO_TO_MARKET. |
| **EDITION_STRATEGY §13.2** | Where PRODUCT_STRATEGY §9 and EDITION differ, **EDITION_STRATEGY is authoritative** pending PRODUCT revision. |
| **ACCESS_CONTROL_MODEL §1** | Subordinate to **EDITION_STRATEGY** for edition gates. |

**Recommended canonical resolution:**

Adopt explicit split ownership:

| Topic | Authoritative document |
|-------|------------------------|
| Product identity, modules, principles, vision | **PRODUCT_STRATEGY.md** |
| Edition capability matrix, free/paid boundaries, upgrade/downgrade | **EDITION_STRATEGY.md** |
| Customer motion, acquisition, adoption | **GO_TO_MARKET_STRATEGY.md** |
| Authorization (who may do what) | **ACCESS_CONTROL_MODEL.md** |

Update **DOCUMENT_HIERARCHY** to state: EDITION_STRATEGY **overrides PRODUCT_STRATEGY §9 only** for edition entitlements — not for product identity or module definitions.

**Documents to modify:**

1. `docs/DOCUMENT_HIERARCHY.md` §3.4, §4.2 — explicit split ownership table.
2. `docs/business/EDITION_STRATEGY.md` §13.2 — reference DOCUMENT_HIERARCHY instead of self-declared override.
3. `docs/business/PRODUCT_STRATEGY.md` header or §9 — cross-reference EDITION_STRATEGY as edition authority.

**Authoritative after reconciliation:** **DOCUMENT_HIERARCHY.md** for precedence rules; **EDITION_STRATEGY.md** for edition matrix only.

---

### CMR-004 — Freemium and public transparency layer absent from BUSINESS_STRATEGY

| Field | Value |
|-------|-------|
| **Repeat count** | 4 (GTM-1, GTM-10, EDT-17, ACM-1 context) |
| **Classification** | **Intentional transition** (incompletely propagated) |
| **Priority** | **High** |
| **Impact** | Business, Documentation |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **BUSINESS_STRATEGY §10** | Revenue models: subscription, enterprise license, add-ons, services, API — **no free tier or public intelligence layer**. |
| **GO_TO_MARKET §1, §8** | **Public transparency free**; Community free; paid operational value. |
| **EDITION_STRATEGY §1.3, §7** | Four-layer stack: Public + Community + Professional + Enterprise. |
| **BUSINESS_STRATEGY §10.2** | “Price on intelligence value” — tension with free public intelligence. |

**Recommended canonical resolution:**

Amend **BUSINESS_STRATEGY** to document the **freemium commercial model**:

- Public layer and Community Edition are **deliberate trust and funnel assets**.
- Revenue captures **operational, organizational, integration, and deployment** value.
- “Price on intelligence value” applies to **operational intelligence**, not public transparency scope.

**Documents to modify:**

1. `docs/business/BUSINESS_STRATEGY.md` §10, §11 — add freemium model subsection referencing EDITION_STRATEGY and GO_TO_MARKET.

**Authoritative after reconciliation:** **BUSINESS_STRATEGY.md** (commercial direction); **EDITION_STRATEGY.md** (tier boundaries).

---

### CMR-005 — Customer segment granularity: merged vs. split government/forestry

| Field | Value |
|-------|-------|
| **Repeat count** | 3 (R-4, EDT-4, DH context) |
| **Classification** | **Terminology difference** (granularity, not capability conflict) |
| **Priority** | **Medium** |
| **Impact** | Business, Documentation |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **BUSINESS_STRATEGY §9.1** | **Government agencies and forestry authorities** — single merged segment. |
| **PRODUCT_STRATEGY §5.1–5.2** | **Separate** government agencies and forestry authorities with distinct roles and edition fit. |
| **GO_TO_MARKET §2.1** | Separate primary customer rows for government and forestry authorities. |

**Recommended canonical resolution:**

**PRODUCT_STRATEGY and GO_TO_MARKET granularity wins** for sales and product motion.
**BUSINESS_STRATEGY** should use merged segment for **market-level** narrative with a
footnote that product/GTM treat them as distinct operational segments.

**Documents to modify:**

1. `docs/business/BUSINESS_STRATEGY.md` §9.1 — split or add cross-reference to PRODUCT_STRATEGY §5.1–5.2.

**Authoritative after reconciliation:** **PRODUCT_STRATEGY.md** for segment definitions; **BUSINESS_STRATEGY.md** for market-level strategy.

---

### CMR-006 — Public transparency layer vs. “not a consumer/public alert app”

| Field | Value |
|-------|-------|
| **Repeat count** | 4 (EDT-9, ACM-6, GTM boundary, PRODUCT §12) |
| **Classification** | **Terminology difference** (requires explicit boundary language) |
| **Priority** | **Medium** |
| **Impact** | Business, Product, Documentation |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **PRODUCT_STRATEGY §12** | ForestWatch is **“Not a consumer or public alert app.”** |
| **BUSINESS_STRATEGY §9.7** | Consumer/general-public alert applications are **non-targets**. |
| **GO_TO_MARKET / EDITION / ACCESS** | **Public intelligence, open reports, public maps** are strategic free assets for everyone including anonymous users. |

**Recommended canonical resolution:**

Add explicit **product boundary clarification** (all affected docs):

ForestWatch **operates a public transparency layer** for forest derived intelligence.
This is **not** a consumer emergency alert product, **not** a lifestyle app, and **not**
a substitute for organizational operational systems. Public access builds **trust**;
**Professional/Enterprise** owns **operational response**.

**Documents to modify:**

1. `docs/business/PRODUCT_STRATEGY.md` §12 — add public transparency exception.
2. `docs/business/BUSINESS_STRATEGY.md` §9.7 — same clarification.
3. `docs/business/GO_TO_MARKET_STRATEGY.md` §1.5 — strengthen distinction (partially present).

**Authoritative after reconciliation:** **PRODUCT_STRATEGY.md** (product boundaries); **EDITION_STRATEGY.md** (public layer rules).

---

### CMR-007 — PRODUCT_STRATEGY file location vs. DOCUMENT_HIERARCHY product category

| Field | Value |
|-------|-------|
| **Repeat count** | 3 (IC-5, DH-5, ACM-12 context) |
| **Classification** | **Hierarchy issue** |
| **Priority** | **Medium** |
| **Impact** | Documentation only |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **DOCUMENT_HIERARCHY §3.5** | Product category scope: `docs/product/` only. |
| **Filesystem** | **PRODUCT_STRATEGY.md** lives under `docs/business/`. |
| **DOCUMENT_HIERARCHY §3.4** | Lists PRODUCT_STRATEGY under Business internal precedence. |

**Recommended canonical resolution:**

**Option A (recommended):** Update DOCUMENT_HIERARCHY to define **Business–Product split**:

- `docs/business/PRODUCT_STRATEGY.md` — product identity and module strategy (business folder, product authority for identity).
- `docs/product/` — capability, workflow, and authorization product docs.

**Option B:** Move PRODUCT_STRATEGY to `docs/product/` (larger filesystem change).

**Documents to modify:**

1. `docs/DOCUMENT_HIERARCHY.md` §2, §3.4, §3.5 — explicit PRODUCT_STRATEGY placement rule.
2. `docs/archive/README.md` — update index (optional, low priority).

**Authoritative after reconciliation:** **DOCUMENT_HIERARCHY.md**.

---

### CMR-008 — Capability taxonomy: five vs. seven vs. eight modules

| Field | Value |
|-------|-------|
| **Repeat count** | 3 (PC-1, EDT-15, DH context) |
| **Classification** | **Terminology difference** |
| **Priority** | **Medium** |
| **Impact** | Product, Documentation |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **PRODUCT_STRATEGY §4** | **Five** foundational capabilities (Observe → Derive → Act thesis). |
| **PRODUCT_STRATEGY §8** | **Seven** product modules (adds Compliance, Historical Analysis). |
| **PLATFORM_CAPABILITIES §3** | **Eight** capabilities (adds **Administration**). |
| **EDITION_STRATEGY / ACCESS** | **Public transparency layer** as separate commercial layer. |

**Recommended canonical resolution:**

Document explicit **mapping table** in PLATFORM_CAPABILITIES or PRODUCT_STRATEGY:

| Layer | Taxonomy |
|-------|----------|
| Thesis-level (5) | Observation intake, Situation derivation, Operational awareness, Human response, Communication/audit |
| Module-level (7) | Monitoring, Intelligence, Investigations, Reporting, Command Center, Compliance, Historical Analysis |
| Capability catalog (8) | Above + Administration |
| Commercial layer (4) | Public, Community, Professional, Enterprise |

**Documents to modify:**

1. `docs/business/PRODUCT_STRATEGY.md` §4 — add mapping pointer to PLATFORM_CAPABILITIES.
2. `docs/product/PLATFORM_CAPABILITIES.md` §1 or new subsection — mapping table.

**Authoritative after reconciliation:** **PLATFORM_CAPABILITIES.md** (catalog); **PRODUCT_STRATEGY.md** (thesis-level identity).

---

### CMR-009 — Public transparency as fourth layer vs. three named editions in PRODUCT_STRATEGY

| Field | Value |
|-------|-------|
| **Repeat count** | 3 (EDT-4, ACM-14, EDITION vs PRODUCT) |
| **Classification** | **Intentional transition** |
| **Priority** | **Medium** |
| **Impact** | Business, Product, Documentation |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **EDITION_STRATEGY §1.3** | **Four layers:** Public + Community + Professional + Enterprise. |
| **PRODUCT_STRATEGY §9, §14.1** | **Three** editions; success criteria reference three tiers only. |
| **ACCESS_CONTROL_MODEL** | **Anonymous public** as distinct actor from Community. |

**Recommended canonical resolution:**

PRODUCT_STRATEGY §9 **SHOULD** acknowledge **Public transparency layer** (Layer 0) as
non-edition commercial surface, with three **named editions** above it.

**Documents to modify:**

1. `docs/business/PRODUCT_STRATEGY.md` §9 introduction, §14.1.

**Authoritative after reconciliation:** **EDITION_STRATEGY.md** (commercial layers); **ACCESS_CONTROL_MODEL.md** (actors).

---

### CMR-010 — Platform Administrator role undefined outside ACCESS_CONTROL

| Field | Value |
|-------|-------|
| **Repeat count** | 3 (ACM-4, ACM-5, ACCESS reviews) |
| **Classification** | **Intentional transition** (new governance concept) |
| **Priority** | **Medium** |
| **Impact** | Product, Documentation |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **ACCESS_CONTROL_MODEL §6.5, §13** | **Platform Administrator** publishes public reports, configures public scope, break-glass access. |
| **PLATFORM_CAPABILITIES §3.8** | **Administration** = organizational configuration only. |
| **00-platform-vision §5** | No platform-operator bounded context. |

**Recommended canonical resolution:**

Add **Platform Administration** as product governance concept in PLATFORM_CAPABILITIES
(§3.8 extension or §3.9) — distinct from organizational Administration. Not an architecture
bounded context; a **product/commercial governance** role.

**Documents to modify:**

1. `docs/product/PLATFORM_CAPABILITIES.md` — Platform Administration subsection.
2. `docs/product/ACCESS_CONTROL_MODEL.md` — cross-reference only (already defined).

**Authoritative after reconciliation:** **ACCESS_CONTROL_MODEL.md** (permissions); **PLATFORM_CAPABILITIES.md** (capability definition).

---

### CMR-011 — Personal workspace absent from PRODUCT_STRATEGY and PLATFORM_CAPABILITIES

| Field | Value |
|-------|-------|
| **Repeat count** | 2 (EDT-8, ACCESS reviews) |
| **Classification** | **Intentional transition** |
| **Priority** | **Medium** |
| **Impact** | Product, Documentation |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **EDITION_STRATEGY §2.7** | **Personal workspace** core to Community Edition. |
| **ACCESS_CONTROL_MODEL §4.1** | Personal workspace permissions and ownership defined. |
| **PRODUCT_STRATEGY / PLATFORM_CAPABILITIES** | **Not named** as product surface. |

**Recommended canonical resolution:**

Add **Personal Workspace** to PRODUCT_STRATEGY §9.1 and PLATFORM_CAPABILITIES as
Community-only product surface — distinct from organization and from investigations.

**Documents to modify:**

1. `docs/business/PRODUCT_STRATEGY.md` §9.1.
2. `docs/product/PLATFORM_CAPABILITIES.md` — new subsection or Community composition note.

**Authoritative after reconciliation:** **EDITION_STRATEGY.md** (entitlement); **PLATFORM_CAPABILITIES.md** (definition).

---

### CMR-012 — Legacy “Environmental Intelligence Platform” identity in frozen/historical docs

| Field | Value |
|-------|-------|
| **Repeat count** | 4+ (R-1, R-2, R-3, DH-6, DH-7) |
| **Classification** | **Real contradiction** (identity drift) |
| **Priority** | **High** |
| **Impact** | Documentation, Implementation (developer confusion) |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **00-platform-vision §2.1, BUSINESS/PRODUCT/EDITION/GTM** | **Forest Intelligence Platform** |
| **architecture/CHANGELOG.md v1.0 summary** | **“multi-domain Environmental Intelligence Platform”** (frozen) |
| **docs/ARCHITECTURE.md** | **“ForestWatch Ecosystem Intelligence Platform”** / environmental intelligence platform in body |
| **RELEASE_NOTES.md** (per prior reviews) | “multi-domain environmental intelligence” language |

**Recommended canonical resolution:**

- **Living docs** (`ARCHITECTURE.md`, `RELEASE_NOTES.md`): update to Forest Intelligence Platform with as-built divergence notes.
- **Frozen CHANGELOG v1.0 summary:** add **non-normative historical note** at Phase gate OR architecture PATCH clarifying §2.1 commercial identity was refined post-freeze without changing invariants — requires **architecture review** (not silent edit).

**Documents to modify:**

1. `docs/ARCHITECTURE.md` — title and identity wording.
2. `docs/RELEASE_NOTES.md` — identity wording.
3. `docs/architecture/CHANGELOG.md` — PATCH entry or gate-reviewed clarifying note (architecture process).
4. `docs/DOCUMENT_HIERARCHY.md` §11.5 — cite as resolved when complete.

**Authoritative after reconciliation:** **00-platform-vision.md §2.1** (commercial identity); frozen architecture docs for **technical** identity unchanged.

---

### CMR-013 — Platform/integration partners: strategic target vs. future customer

| Field | Value |
|-------|-------|
| **Repeat count** | 2 (GTM-5, BUSINESS vs GTM) |
| **Classification** | **Terminology difference** (timing, not denial) |
| **Priority** | **Low** |
| **Impact** | Business, Documentation |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **BUSINESS_STRATEGY §9.6** | Platform and integration partners are **strategic targets**. |
| **GO_TO_MARKET §2.3** | Partners are **future customers** (Year 3+). |

**Recommended canonical resolution:**

Harmonize: partners are **strategic segment, future commercial motion** until API and
multi-tenancy maturity. Not a capability conflict.

**Documents to modify:**

1. `docs/business/BUSINESS_STRATEGY.md` §9.6 — add timing caveat referencing GO_TO_MARKET §2.3.

**Authoritative after reconciliation:** **GO_TO_MARKET_STRATEGY.md** (motion timing); **BUSINESS_STRATEGY.md** (segment existence).

---

### CMR-014 — Threat Assessment and Risk: architecture consumers vs. product catalog

| Field | Value |
|-------|-------|
| **Repeat count** | 2 (PC-6, reviews) |
| **Classification** | **Terminology difference** |
| **Priority** | **Low** |
| **Impact** | Product, Documentation |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **02-intelligence-engine.md §9** | **Threat Assessment** and **Risk** are downstream Intelligence Event consumers. |
| **PLATFORM_CAPABILITIES / ACCESS** | Not listed as user-facing product capabilities; Command Center includes “threat distribution.” |

**Recommended canonical resolution:**

Document in PLATFORM_CAPABILITIES §8 notes: Threat Assessment and Risk are **engine
projections** surfaced through Command Center and Reporting — **not** separate product
modules.

**Documents to modify:**

1. `docs/product/PLATFORM_CAPABILITIES.md` §8 Architectural Alignment notes.

**Authoritative after reconciliation:** **PLATFORM_CAPABILITIES.md** (product surfacing); **02-intelligence-engine.md** (architecture).

---

### CMR-015 — Investigation AI (INVESTIGATION_FRAMEWORK §11) absent from ACCESS and PLATFORM

| Field | Value |
|-------|-------|
| **Repeat count** | 2 (IC-4, ACM-19) |
| **Classification** | **Intentional transition** (future capability) |
| **Priority** | **Low** |
| **Impact** | Product, Documentation |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **INVESTIGATION_FRAMEWORK §11** | Future **investigation AI assistance** permitted with INV-13 controls. |
| **ACCESS_CONTROL_MODEL / PLATFORM_CAPABILITIES** | No AI assistance permissions or capability entry. |

**Recommended canonical resolution:**

Defer until product approves investigation AI. When approved, add to INVESTIGATION_FRAMEWORK
and ACCESS_CONTROL as **assist-only** permissions — never `investigation:decide` for automation.

**Documents to modify:** None until feature approved.

**Authoritative after reconciliation:** **INVESTIGATION_FRAMEWORK.md** when feature is product-approved.

---

### CMR-016 — Investigation lifecycle stage vocabulary vs. canonical architecture attributes

| Field | Value |
|-------|-------|
| **Repeat count** | 2 (IC-1, reviews) |
| **Classification** | **Terminology difference** |
| **Priority** | **Medium** |
| **Impact** | Product, Documentation |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **INVESTIGATION_FRAMEWORK §3** | Product stages: Open → Evidence → Assessment → Decision → Closure. |
| **02-intelligence-engine.md §4.5** | Canonical attributes: workflow status, resolution, outcome, audit timeline — **no named stages**. |

**Recommended canonical resolution:**

Add mapping appendix to INVESTIGATION_FRAMEWORK: product stages are **views** over
canonical attributes — not separate architecture entities.

**Documents to modify:**

1. `docs/product/INVESTIGATION_FRAMEWORK.md` — appendix mapping stages to attributes.

**Authoritative after reconciliation:** **INVESTIGATION_FRAMEWORK.md** (product workflow); **02-intelligence-engine.md** (canonical model).

---

### CMR-017 — Optional Intelligence Event binding for investigations

| Field | Value |
|-------|-------|
| **Repeat count** | 2 (IC-2, ACCESS reviews) |
| **Classification** | **Terminology difference** (policy vs. capability) |
| **Priority** | **Low** |
| **Impact** | Product |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **INVESTIGATION_FRAMEWORK §4** | Investigations **may** exist without linked Intelligence Event. |
| **ACCESS / GTM flows** | Emphasize intelligence-triggered operational path as common case. |

**Recommended canonical resolution:**

No doc conflict — clarify in INVESTIGATION_FRAMEWORK that optional binding is **org policy**;
default UX may encourage binding without requiring it.

**Documents to modify:**

1. `docs/product/INVESTIGATION_FRAMEWORK.md` §4 — one paragraph on default UX vs. architecture optional.

**Authoritative after reconciliation:** **INVESTIGATION_FRAMEWORK.md**.

---

### CMR-018 — Command Center investigation statistic freshness

| Field | Value |
|-------|-------|
| **Repeat count** | 2 (IC-13, reviews) |
| **Classification** | **Terminology difference** |
| **Priority** | **Low** |
| **Impact** | Product, Documentation |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **INVESTIGATION_FRAMEWORK §10.4** | Investigation statistics freshness follows **same reconciliation cadence** as Command Center. |
| **07-reporting-and-command-center.md §5** | Freshness follows **reconciliation cycle** for intelligence; investigations are **not** reconciled. |

**Recommended canonical resolution:**

Revise INVESTIGATION_FRAMEWORK §10.4: investigation statistics refresh on **investigation
workflow events** and **projection read cycle** — aligned with but not identical to
reconciliation cadence.

**Documents to modify:**

1. `docs/product/INVESTIGATION_FRAMEWORK.md` §10.4.

**Authoritative after reconciliation:** **07-reporting-and-command-center.md** (projection rules); **INVESTIGATION_FRAMEWORK.md** (product integration wording).

---

### CMR-019 — Cross-category correlation promised in Enterprise editions but not in PLATFORM_CAPABILITIES

| Field | Value |
|-------|-------|
| **Repeat count** | 2 (PC-14, reviews) |
| **Classification** | **Intentional transition** (future capability) |
| **Priority** | **Low** |
| **Impact** | Product, Business |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **PRODUCT_STRATEGY §9.3 / EDITION_STRATEGY §4.8** | Enterprise **advanced Historical Analysis including cross-category correlation when available**. |
| **PLATFORM_CAPABILITIES §7** | Future extensibility lists categories only — not correlation. |
| **08-roadmap.md §9** | Cross-category correlation is **future platform layer**. |

**Recommended canonical resolution:**

Mark as **future Enterprise feature** in PLATFORM_CAPABILITIES §7 with roadmap reference;
not available until architecture layer exists.

**Documents to modify:**

1. `docs/product/PLATFORM_CAPABILITIES.md` §7.

**Authoritative after reconciliation:** **08-roadmap.md** (technical readiness); **EDITION_STRATEGY.md** (commercial promise gated on availability).

---

### CMR-020 — Map as daily surface vs. “not a map product”

| Field | Value |
|-------|-------|
| **Repeat count** | 2 (PC-5, reviews) |
| **Classification** | **Terminology difference** |
| **Priority** | **Medium** |
| **Impact** | Business, Product, Documentation |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **BUSINESS_STRATEGY §11.2** | **Map** is one of three daily surfaces (Command Center, Reporting, Map). |
| **PRODUCT_STRATEGY §12** | **Not a map or GIS product** — maps are exploration surfaces. |
| **EDITION / GTM / ACCESS** | **Public maps** and Phase 3 map-integrated exploration are strategic. |

**Recommended canonical resolution:**

Harmonize wording everywhere: **“Map is an exploration surface, not product core.”**
Public and operational maps are **surfaces** within Forest Intelligence Platform.

**Documents to modify:**

1. `docs/business/PRODUCT_STRATEGY.md` §12 — add exploration surface clarification (partially present).
2. `docs/business/BUSINESS_STRATEGY.md` §11.2 — align wording with PRODUCT_STRATEGY.

**Authoritative after reconciliation:** **PRODUCT_STRATEGY.md** (product boundaries).

---

### CMR-021 — Notifications: cross-cutting subsystem vs. Professional+ entitlement

| Field | Value |
|-------|-------|
| **Repeat count** | 2 (EDT-7, PLATFORM vs EDITION) |
| **Classification** | **Terminology difference** |
| **Priority** | **Medium** |
| **Impact** | Product, Business |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **PLATFORM_CAPABILITIES §4.4** | Notifications are **cross-cutting architecture subsystem**, not separate product capability. |
| **EDITION_STRATEGY / ACCESS** | **Notification routing** is **Professional+** only; excluded from Community. |

**Recommended canonical resolution:**

PLATFORM_CAPABILITIES should state: notifications exist as **engine subsystem**; **routed
notification delivery to users** is **Professional+ product entitlement**.

**Documents to modify:**

1. `docs/product/PLATFORM_CAPABILITIES.md` §4.4 — add edition entitlement note.

**Authoritative after reconciliation:** **EDITION_STRATEGY.md** (entitlement); **PLATFORM_CAPABILITIES.md** (subsystem vs. product feature).

---

### CMR-022 — Administration capability vs. edition-gated org/platform admin

| Field | Value |
|-------|-------|
| **Repeat count** | 2 (EDT-6, ACM-6) |
| **Classification** | **Terminology difference** |
| **Priority** | **Medium** |
| **Impact** | Product, Business |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **PLATFORM_CAPABILITIES §3.8** | Administration as **cross-cutting capability** for all orgs with generic edition limits. |
| **EDITION_STRATEGY / ACCESS** | **Organizational Administration Professional+**; **Platform Administration** separate; Community **none**. |

**Recommended canonical resolution:**

Split Administration in PLATFORM_CAPABILITIES: **Personal preferences (Community)**,
**Organizational Administration (Professional+)**, **Enterprise Administration extensions**,
**Platform Administration (operator)**.

**Documents to modify:**

1. `docs/product/PLATFORM_CAPABILITIES.md` §3.8.

**Authoritative after reconciliation:** **ACCESS_CONTROL_MODEL.md** (permissions); **EDITION_STRATEGY.md** (entitlements).

---

### CMR-023 — All strategic documents “pending review” vs. authoritative claims in headers

| Field | Value |
|-------|-------|
| **Repeat count** | 3 (DH-9, ACM-9, multiple docs) |
| **Classification** | **Hierarchy issue** |
| **Priority** | **High** |
| **Impact** | Documentation, Business, Product |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **All business/product strategic docs** | Status: **pending review**. |
| **EDITION_STRATEGY §13**, **ACCESS §1**, **DOCUMENT_HIERARCHY** | Documents claim **authoritative** roles for edition, access, hierarchy. |
| **DOCUMENT_HIERARCHY §10.3** | Pending review docs **must not** be treated as fully approved for overrides. |

**Recommended canonical resolution:**

Conduct **single cross-functional review pass** to approve as a **bundle**:

1. BUSINESS_STRATEGY (amended per CMR-004, CMR-005, CMR-006)
2. PRODUCT_STRATEGY (amended per CMR-001, CMR-008, CMR-009, CMR-011)
3. EDITION_STRATEGY (amended per CMR-003 cross-ref only if needed)
4. GO_TO_MARKET (amended per CMR-002, CMR-006)
5. PLATFORM_CAPABILITIES, INVESTIGATION_FRAMEWORK, ACCESS_CONTROL_MODEL, DOCUMENT_HIERARCHY

Update all statuses to **Approved** simultaneously.

**Documents to modify:** All eight scoped documents — status field only after content reconciliation.

**Authoritative after reconciliation:** **DOCUMENT_HIERARCHY.md** governs approval process.

---

### CMR-024 — Enterprise multi-tenancy commercial promises vs. ADR-010 not implemented

| Field | Value |
|-------|-------|
| **Repeat count** | 3 (EDT-15, ACM-7, ACCESS §15) |
| **Classification** | **Intentional transition** |
| **Priority** | **Medium** |
| **Impact** | Architecture, Implementation, Business |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **ADR-010** | Multi-tenancy **reserved, not implemented**; access control within single org scope today. |
| **EDITION / GTM / ACCESS / BUSINESS Year 2** | Enterprise **multi-organization deployment** when ADR-010 implemented. |

**Recommended canonical resolution:**

No commercial doc change required if **guardrails remain**. Sales and entitlement
implementation **MUST NOT** promise tenant isolation until ADR-010 activation recorded.

**Documents to modify:** None until implementation — optionally add explicit **“when available”** flag consistency pass on Enterprise docs.

**Authoritative after reconciliation:** **ADR-010** (technical gate); **EDITION_STRATEGY.md** (commercial promise with guardrail).

---

### CMR-025 — ACCESS_CONTROL and EDITION models vs. as-built application auth

| Field | Value |
|-------|-------|
| **Repeat count** | 2 (ACM-8, implementation reviews) |
| **Classification** | **Intentional transition** (product ahead of implementation) |
| **Priority** | **High** |
| **Impact** | Implementation |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **ACCESS_CONTROL_MODEL** | Five actor classes, org RBAC, Enterprise API policy, Platform Admin. |
| **docs/ARCHITECTURE.md** | Cookie/JWT auth, seeded admin user, no org/tenant/edition model described. |

**Recommended canonical resolution:**

Treat ACCESS_CONTROL and EDITION as **target entitlement model**. Implementation **SHALL
NOT** proceed on entitlement gating until CMR-001–003 resolved and **Approved**. As-built
doc should note **divergence** explicitly when entitlement work begins.

**Documents to modify (when implementation starts):**

1. `docs/ARCHITECTURE.md` — entitlement divergence section.
2. Future `docs/product/` entitlement specification (derived doc, not yet created).

**Authoritative after reconciliation:** **ACCESS_CONTROL_MODEL.md** + **EDITION_STRATEGY.md** for target; **ARCHITECTURE.md** for as-built.

---

### CMR-026 — IMPLEMENTATION_PROTOCOL hierarchy vs. DOCUMENT_HIERARCHY

| Field | Value |
|-------|-------|
| **Repeat count** | 2 (DH-1, DOCUMENT_HIERARCHY §13) |
| **Classification** | **Hierarchy issue** |
| **Priority** | **Medium** |
| **Impact** | Documentation |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **IMPLEMENTATION_PROTOCOL §1.3, §7** | Partial 6-row documentation hierarchy. |
| **DOCUMENT_HIERARCHY** | Full 9-category hierarchy; claims to extend protocol. |

**Recommended canonical resolution:**

Add reference from IMPLEMENTATION_PROTOCOL §1.3 to DOCUMENT_HIERARCHY — requires
**frozen protocol amendment** via engineering review.

**Documents to modify:**

1. `docs/engineering/IMPLEMENTATION_PROTOCOL.md` §1.3 — pointer to DOCUMENT_HIERARCHY (engineering review required).

**Authoritative after reconciliation:** **DOCUMENT_HIERARCHY.md** (full stack); **IMPLEMENTATION_PROTOCOL.md** (implementation subset).

---

### CMR-027 — Compliance: “never free” vs. PRODUCT_STRATEGY “Advanced Compliance excluded”

| Field | Value |
|-------|-------|
| **Repeat count** | 2 (EDT-12, EDITION vs PRODUCT) |
| **Classification** | **Terminology difference** |
| **Priority** | **Low** |
| **Impact** | Business, Product |

**Conflicting statements:**

| Source | Statement |
|--------|-----------|
| **EDITION_STRATEGY §1.2** | **Compliance workflows never free.** |
| **PRODUCT_STRATEGY §9.1** | Excludes **“Advanced Compliance module configuration”** — implies basic compliance context may exist. |

**Recommended canonical resolution:**

Community has **no Compliance module**. Intelligence in compliance-relevant categories
in public/bounded views is **not** Compliance workflow.

**Documents to modify:**

1. `docs/business/PRODUCT_STRATEGY.md` §9.1 exclusions — say **“Compliance module (all workflows)”**.

**Authoritative after reconciliation:** **EDITION_STRATEGY.md**.

---

## 4. Prioritized Reconciliation Backlog

Ordered by priority and dependency. **Do not start implementation entitlement work until
Critical items are resolved and strategic bundle approved (CMR-023).**

| Priority | ID | Summary | Type | Docs to modify | Blocks |
|----------|-----|---------|------|----------------|--------|
| **P0** | CMR-023 | Approve strategic doc bundle after reconciliation | Hierarchy | All 8 scoped docs (status) | Public MVP, entitlements, sales |
| **P0** | CMR-001 | Remove Community investigations from PRODUCT_STRATEGY | Real | PRODUCT_STRATEGY | Entitlements, ACCESS implementation |
| **P0** | CMR-002 | Fix Community personal vs. organizational in GTM | Real | GO_TO_MARKET, PRODUCT_STRATEGY §9.1 | GTM, Community UX, ACCESS |
| **P1** | CMR-003 | Fix EDITION vs. PRODUCT vs. DH precedence | Hierarchy | DOCUMENT_HIERARCHY, EDITION §13.2, PRODUCT header | All edition questions |
| **P1** | CMR-004 | Add freemium model to BUSINESS_STRATEGY | Transition | BUSINESS_STRATEGY §10–11 | Commercial narrative |
| **P1** | CMR-012 | Fix legacy Environmental Intelligence identity in living docs | Real | ARCHITECTURE.md, RELEASE_NOTES; CHANGELOG via arch process | Developer/marketing confusion |
| **P1** | CMR-025 | Track entitlement divergence in as-built docs when coding | Transition | ARCHITECTURE.md (when implementing) | Implementation |
| **P2** | CMR-006 | Clarify public transparency vs. consumer app boundary | Terminology | PRODUCT §12, BUSINESS §9.7, GTM | Marketing, public launch |
| **P2** | CMR-007 | Fix PRODUCT_STRATEGY folder vs. hierarchy | Hierarchy | DOCUMENT_HIERARCHY | Doc maintenance |
| **P2** | CMR-008 | Add capability taxonomy mapping table | Terminology | PRODUCT §4, PLATFORM_CAPABILITIES | Product coherence |
| **P2** | CMR-009 | Add Public layer to PRODUCT_STRATEGY §9 | Transition | PRODUCT_STRATEGY | Edition clarity |
| **P2** | CMR-010 | Add Platform Administration to PLATFORM_CAPABILITIES | Transition | PLATFORM_CAPABILITIES | ACCESS alignment |
| **P2** | CMR-011 | Add Personal Workspace to PRODUCT and PLATFORM | Transition | PRODUCT §9.1, PLATFORM_CAPABILITIES | Community UX |
| **P2** | CMR-016 | Map investigation stages to canonical attributes | Terminology | INVESTIGATION_FRAMEWORK | Engineering clarity |
| **P2** | CMR-020 | Harmonize map surface wording | Terminology | PRODUCT §12, BUSINESS §11.2 | Positioning |
| **P2** | CMR-021 | Notifications subsystem vs. entitlement | Terminology | PLATFORM_CAPABILITIES §4.4 | Entitlements |
| **P2** | CMR-022 | Split Administration types in PLATFORM_CAPABILITIES | Terminology | PLATFORM_CAPABILITIES §3.8 | Entitlements |
| **P2** | CMR-026 | Link IMPLEMENTATION_PROTOCOL to DOCUMENT_HIERARCHY | Hierarchy | IMPLEMENTATION_PROTOCOL (frozen review) | Engineering docs |
| **P3** | CMR-005 | Split government/forestry in BUSINESS_STRATEGY | Terminology | BUSINESS_STRATEGY §9.1 | Segment clarity |
| **P3** | CMR-013 | Partner segment timing caveat | Terminology | BUSINESS_STRATEGY §9.6 | Partner GTM |
| **P3** | CMR-014 | Threat Assessment/Risk product note | Terminology | PLATFORM_CAPABILITIES §8 | Catalog completeness |
| **P3** | CMR-017 | Optional investigation binding UX note | Terminology | INVESTIGATION_FRAMEWORK §4 | UX policy |
| **P3** | CMR-018 | Investigation stats freshness wording | Terminology | INVESTIGATION_FRAMEWORK §10.4 | Product accuracy |
| **P3** | CMR-027 | Compliance never free wording in PRODUCT | Terminology | PRODUCT_STRATEGY §9.1 | Edition clarity |
| **P4** | CMR-015 | Investigation AI (when approved) | Transition | Deferred | Future feature |
| **P4** | CMR-019 | Cross-category correlation future note | Transition | PLATFORM_CAPABILITIES §7 | Enterprise promise |
| **P4** | CMR-024 | Multi-tenancy “when available” consistency | Transition | Optional Enterprise pass | Enterprise sales |

---

## 5. Impact Summary by Domain

| Domain | Contradictions affecting | Critical count |
|--------|-------------------------|----------------|
| **Architecture** | CMR-012 (CHANGELOG), CMR-024 | 0 direct — identity note only |
| **Business** | CMR-001–006, CMR-013, CMR-023 | 2 (via CMR-001, CMR-002) |
| **Product** | CMR-001–011, CMR-016–022, CMR-027 | 2 |
| **Implementation** | CMR-001, CMR-025, CMR-024 | 2 (entitlement gating blocked) |
| **Documentation only** | CMR-003, CMR-007, CMR-023, CMR-026 | 1 (CMR-023) |

---

## 6. Authoritative Document Map (After Reconciliation)

| Question | Authoritative document (target state) |
|----------|--------------------------------------|
| Commercial direction and market | **BUSINESS_STRATEGY.md** |
| Product identity, modules, principles | **PRODUCT_STRATEGY.md** |
| Edition tiers, free/paid, public layer | **EDITION_STRATEGY.md** |
| GTM, acquisition, adoption | **GO_TO_MARKET_STRATEGY.md** |
| Capability catalog and boundaries | **PLATFORM_CAPABILITIES.md** |
| Investigation workflow | **INVESTIGATION_FRAMEWORK.md** |
| Authorization (who may do what) | **ACCESS_CONTROL_MODEL.md** |
| Documentation precedence and approval | **DOCUMENT_HIERARCHY.md** |
| Platform invariants and engines | **docs/architecture/** + ADRs |

---

## 7. Readiness Assessments

*Qualitative estimates based on current documentation state, Phase 0 progress per
`docs/PROJECT_STATE.md`, and unresolved CMR backlog. Not financial or schedule commitments.*

### 7.1 Remaining documentation maturity

| Area | Maturity | Notes |
|------|----------|-------|
| **Architecture + ADRs** | **High (frozen)** | v1.0 complete; identity summary in CHANGELOG needs PATCH (CMR-012). |
| **Engineering protocol + Phase 0** | **High (frozen)** | WP0.1 complete; protocol C-5/C-6 open. |
| **Business strategy stack** | **Medium** | Complete drafts; **Critical contradictions** CMR-001–004 unresolved; all **pending review**. |
| **Product capability stack** | **Medium–High** | Comprehensive; missing Platform Admin, personal workspace, taxonomy map; pending review. |
| **Authorization model** | **Medium–High** | Coherent with EDITION; blocked on CMR-001–003 approval before implementation. |
| **Documentation governance** | **Medium** | DOCUMENT_HIERARCHY exists; hierarchy conflicts and pending approval reduce enforceability. |
| **As-built / dev docs** | **Low–Medium** | Identity drift (CMR-012); no entitlement model; pre–Phase 0 alignment. |

**Overall documentation maturity: Medium** — architecture strong; commercial/product stack
content-rich but **not yet internally consistent or approved**.

---

### 7.2 Estimated readiness for implementation

| Dimension | Readiness | Blockers |
|-----------|-----------|----------|
| **Phase 0 engine generalization** | **Ready to continue** | Architecture frozen; engineering specs frozen; commercial contradictions **do not block** engine work if scope stays Phase 0. |
| **Edition/entitlement implementation** | **Not ready** | CMR-001, CMR-002, CMR-003, CMR-023, CMR-025. |
| **Investigation workflow implementation** | **Conditionally ready** | INVESTIGATION_FRAMEWORK usable; Community vs. Professional gate must follow CMR-001 resolution. |
| **Public layer implementation** | **Not ready** | CMR-006, CMR-009, CMR-010, CMR-012 — public scope and publisher role undefined in product catalog. |

**Overall implementation readiness: Medium for Phase 0 engine; Low for commercial entitlements.**

Estimate: **~70% ready** for continued Phase 0 engineering; **~30% ready** for entitlement-aware feature gating.

---

### 7.3 Estimated readiness for Public MVP

Public MVP defined as: **anonymous public intelligence + open reports + public maps +
Community registration + bounded personal workspace** — without full organizational
operations (per EDITION/GTM/ACCESS target model).

| Requirement | Status |
|-------------|--------|
| Architecture Phase 3 surface (map, filters, multi-category) | **Not complete** — Phase 0 in progress |
| Public layer product definition | **Drafted** across EDITION/GTM/ACCESS — **not approved** |
| Community actor model | **Contradicted** (CMR-001, CMR-002) |
| Platform publication governance | **Drafted** in ACCESS — **not in PLATFORM_CAPABILITIES** (CMR-010) |
| Identity/marketing consistency | **Blocked** (CMR-012) |

**Overall Public MVP readiness: Low–Medium (~35%)**

Public MVP **SHOULD NOT** be marketed or entitlement-coded until **P0–P1 reconciliation
backlog** complete and Phase 3 surface engineering advances.

---

### 7.4 Estimated readiness for Enterprise development

Enterprise defined as: **multi-organization tenant isolation, API access, integration
administration, extended compliance/audit, private deployment, SLA**.

| Requirement | Status |
|-------------|--------|
| ADR-010 multi-tenancy implementation | **Not started** |
| ACCESS Enterprise roles and API policy | **Documented** — pending approval |
| EDITION Enterprise matrix | **Documented** — pending approval |
| Phase 0–3 platform maturity | **Phase 0 partial** |
| Professional reference deployments | **None documented** |

**Overall Enterprise development readiness: Low (~20%)**

Enterprise commercial docs are **aspirationally complete** but **implementation and
architecture prerequisites** (multi-tenancy, API stability, Phase 3 surface, Professional
reference) are not met. Enterprise sales **SHOULD** remain design-partner / roadmap-gated.

---

## 8. Recommended Reconciliation Sequence

```
Week 1 — Critical content fixes
  CMR-001 → CMR-002 → CMR-004 → CMR-003

Week 2 — Product catalog alignment
  CMR-008, CMR-009, CMR-010, CMR-011, CMR-021, CMR-022, CMR-006

Week 3 — Identity and governance
  CMR-012 → CMR-007 → CMR-026 → CMR-023 (bundle approval)

Parallel — Engineering (unblocked)
  Phase 0 WP0.2+ continues under architecture authority
  Do NOT implement edition gates until CMR-023 approved
```

---

## Document Control

| Field | Value |
|-------|-------|
| Created | 2026-07-22 |
| Status | Pending review |
| Modifies other documents | **None** — analysis only |
| Related | All documents listed in §1 Scope |

---

*End of Commercial Model Reconciliation.*
