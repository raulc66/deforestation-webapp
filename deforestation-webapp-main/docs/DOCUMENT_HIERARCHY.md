# ForestWatch — Documentation Hierarchy

**Status:** Normative meta-document — pending review.
**Audience:** All contributors — engineering, product, commercial, operations, and
documentation maintainers.
**Authority:** This document defines the **authority hierarchy** of all ForestWatch
documentation. It governs which documents are authoritative, how conflicts are resolved,
and how documents are created, reviewed, frozen, updated, and archived. No document **MAY**
silently override another. Overrides **MUST** occur only through the processes defined here.

**Document type:** Documentation governance. This is not product, business, architecture,
or implementation content.

**Language:** The key words **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**,
**SHOULD NOT**, **MAY**, and **OPTIONAL** in this document are to be interpreted as
described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## 1. Purpose

ForestWatch documentation spans architecture, engineering, business strategy, product
definition, as-built development guides, operational runbooks, marketing materials, and
historical archives. Without an explicit hierarchy, contributors may:

- implement against the wrong document;
- resolve contradictions informally or silently;
- treat living or archived documents as canonical;
- allow commercial or product documents to redefine architecture.

This document exists to:

1. Define **documentation categories**, their purpose, scope, and authority.
2. Establish **document precedence** across the full stack.
3. Define **conflict resolution** and **contradiction handling**.
4. Classify documents as **frozen**, **living**, or **append-only**.
5. Define **review**, **approval**, and **versioning** requirements.
6. Define the **document lifecycle** from creation through archival.

**Core rule:** Architecture and ADRs remain the **highest authority for technical
decisions**. Business documents define commercial direction but **cannot alter
architecture**. Product documents define user-facing behavior but **cannot contradict
business strategy** or **architecture invariants**. Engineering documents define
implementation execution but **cannot redefine architecture**. Archive documents have
**no authority**.

---

## 2. Complete Documentation Hierarchy

Precedence is **highest at the top**. A lower row **MUST NOT** override a higher row
unless an explicit override is approved through Section 6.

| Rank | Category | Location | Authority level | Modification class |
|------|----------|----------|-----------------|-------------------|
| **1** | **Architecture** | `docs/architecture/` (numbered `00`–`10`, `CHANGELOG.md`) | Highest — technical platform truth | Frozen (v1.0) |
| **2** | **ADRs** | `docs/architecture/adr/` | Highest — binding decisions | Frozen |
| **3** | **Engineering** | `docs/engineering/` | Execution authority — how work is done | Frozen per artifact |
| **4** | **Business** | `docs/business/` | Commercial direction — not technical truth | Strategic — pending review until approved |
| **5** | **Product** | `docs/product/` | User-facing behavior and capability semantics | Strategic — pending review until approved |
| **6** | **Development** | `docs/` (as-built guides, API reference, structure) | Descriptive — what is built and how to develop | Living |
| **7** | **Operations** | `docs/operations/` *(reserved)* | Runbooks and operational procedure | Living |
| **8** | **Marketing** | `docs/marketing/` *(reserved)* | External messaging and campaigns | Living — non-normative |
| **9** | **Archive** | `docs/archive/` | Historical reference only | Immutable snapshot |
| — | **Packaging** | `docs/packaging/` | Authoritative for **what is being sold** (source-license distribution). Does not override Architecture for engine behavior. | Living |
| — | **Meta** | `docs/DOCUMENT_HIERARCHY.md` (this document) | Governs all categories | Living — meta approval required |
| — | **Status** | `docs/PROJECT_STATE.md`, `docs/RELEASE_NOTES.md` | Current execution and release status | Living |
| — | **Changelog** | `docs/CHANGELOG.md` | Project-visible change history | Append-only |

### 2.1 Cross-cutting status documents

These documents sit beside the category hierarchy. They **MUST NOT** override frozen
architecture or ADRs.

| Document | Role | Precedence vs. categories |
|----------|------|-------------------------|
| `docs/PROJECT_STATE.md` | Current phase, work package, task, risks | Subordinate to Engineering frozen specs and Architecture |
| `docs/RELEASE_NOTES.md` | User-visible release history and planned scope | Subordinate to Architecture phase roadmap for engineering timing |
| `docs/CHANGELOG.md` | Notable project changes | Append-only record; not normative specification |
| `docs/ROADMAP.md` | Product/feature delivery roadmap | Subordinate to `docs/architecture/08-roadmap.md` for phase ordering |
| `docs/packaging/` | Commercial source-package definition (positioning, what ships, license model) | Authoritative for distribution claims; **cannot** alter Architecture or ADRs |

---

## 3. Documentation Categories

Each category defines: **purpose**, **ownership**, **scope**, **authority**, **may
define**, and **may never define**.

---

### 3.1 Architecture

| Field | Definition |
|-------|------------|
| **Purpose** | Define the canonical ForestWatch platform — vision, invariants, engines, contracts, bounded contexts, dependency law, and phased evolution. |
| **Ownership** | Platform architecture / principal engineering |
| **Scope** | `docs/architecture/00-platform-vision.md` through `10-dependency-rules.md`; `docs/architecture/CHANGELOG.md` |
| **Authority** | **Highest technical authority.** All implementation **MUST** conform. |
| **May define** | Platform invariants; canonical data model; engine responsibilities; information flow; dependency rules; architectural phase roadmap; non-negotiable guarantees; forest ecosystem scope boundaries at architecture level |
| **May never define** | Pricing; revenue; marketing copy; UI mockups; edition tiers; sales motion; as-built code paths; operational runbooks |

**Current state:** Architecture v1.0 — **Frozen** (2026-07-15).

---

### 3.2 ADRs (Architecture Decision Records)

| Field | Definition |
|-------|------------|
| **Purpose** | Record binding architectural decisions with context, alternatives, and consequences. |
| **Ownership** | Platform architecture |
| **Scope** | `docs/architecture/adr/ADR-001` through `ADR-011` and future ADRs |
| **Authority** | **Equal to Architecture** for the decisions they record. An ADR **MUST NOT** be contradicted by lower documents. |
| **May define** | Specific architectural decisions; accepted alternatives; consequences; reserved future dimensions (e.g. tenant in ADR-010) |
| **May never define** | Implementation code; product edition boundaries; commercial strategy; marketing claims; retroactive changes without supersession |

**Amendment rule:** Existing ADRs **MUST NOT** be edited in place. Changes require a
**new ADR** or a formal **supersession record** in `docs/architecture/CHANGELOG.md`.

---

### 3.3 Engineering

| Field | Definition |
|-------|------------|
| **Purpose** | Define **how implementation work is executed** — phase specifications, work packages, backlogs, protocols, and implementation records. |
| **Ownership** | Engineering leadership / implementation agents |
| **Scope** | `docs/engineering/IMPLEMENTATION_PROTOCOL.md`; `docs/engineering/PHASE-*-*.md`; `docs/engineering/IMPLEMENTATION_LOG.md` |
| **Authority** | **Authoritative for implementation process and phase execution.** Subordinate to Architecture and ADRs for *what* is built. |
| **May define** | Work package scope; task definitions; verification requirements; stop conditions; git and documentation update policy during implementation; append-only implementation log entries |
| **May never define** | New architectural invariants; changes to ADRs; product edition rules; commercial direction; override of frozen architecture |

**Frozen engineering artifacts:**

| Document | Status |
|----------|--------|
| `IMPLEMENTATION_PROTOCOL.md` | Frozen |
| `PHASE-*-ENGINE-GENERALIZATION.md` | Frozen per phase |
| `PHASE-*-IMPLEMENTATION-BACKLOG.md` | Frozen per phase |
| `IMPLEMENTATION_LOG.md` | Append-only |

---

### 3.4 Business

| Field | Definition |
|-------|------------|
| **Purpose** | Define **commercial direction** — why ForestWatch exists commercially, who the market is, how the business competes, reaches customers, and tiers editions. |
| **Ownership** | Commercial leadership / business strategy |
| **Scope** | `docs/business/BUSINESS_STRATEGY.md`; `docs/business/PRODUCT_STRATEGY.md`; `docs/business/GO_TO_MARKET_STRATEGY.md`; `docs/business/EDITION_STRATEGY.md`; future pricing and sales guides derived from these |
| **Authority** | **Authoritative for commercial direction** within architecture limits. **Cannot alter architecture.** |
| **May define** | Market positioning; customer segments; revenue model categories (not price points); go-to-market motion; edition free/paid boundaries; upgrade/downgrade principles; commercial success metrics |
| **May never define** | Platform invariants; engine internals; API contracts; database schemas; new bounded contexts; investigation lifecycle invariants owned by architecture |

**Internal business precedence** (within Business category — highest first):

| Rank | Document | Authoritative for |
|------|----------|-----------------|
| 1 | `BUSINESS_STRATEGY.md` | Long-term commercial direction and competitive context |
| 2 | `PRODUCT_STRATEGY.md` | Product identity, modules, principles |
| 3 | `EDITION_STRATEGY.md` | Edition capability matrix, free/paid boundaries, upgrade/downgrade |
| 4 | `GO_TO_MARKET_STRATEGY.md` | Customer acquisition, sales, and adoption motion |

**Edition entitlement split:** `PRODUCT_STRATEGY.md` §9 provides product-oriented edition
overview. For **edition capability lists, free/paid boundaries, and upgrade triggers**,
`EDITION_STRATEGY.md` is authoritative and **overrides PRODUCT_STRATEGY §9 only** on
those questions — not on product identity, module definitions, or principles. See §4.2.

When business documents conflict, **MUST NOT** silently override. Apply Section 6.
Conflicts **MUST** be reported until reconciled through the process in §5.2.

---

### 3.5 Product

| Field | Definition |
|-------|------------|
| **Purpose** | Define **user-facing product behavior** — capabilities, workflows, and product semantics without implementation detail. |
| **Ownership** | Product leadership |
| **Scope** | `docs/product/PLATFORM_CAPABILITIES.md`; `docs/product/INVESTIGATION_FRAMEWORK.md`; future product workflow and UX strategy documents |
| **Authority** | **Authoritative for product behavior and capability semantics.** Subordinate to Architecture for platform limits; subordinate to Business Strategy for commercial direction. |
| **May define** | Product capabilities; investigation workflow; capability boundaries and interactions; user interaction model; product-phase evolution at capability level |
| **May never define** | Architecture invariants; engine contracts; microservice topology; API endpoints; database schemas; pricing; edition pricing; override of BUSINESS_STRATEGY scope |

**Internal product precedence:**

| Rank | Document | Authoritative for |
|------|----------|-----------------|
| 1 | `PLATFORM_CAPABILITIES.md` | Capability catalog, ownership, and interactions |
| 2 | `INVESTIGATION_FRAMEWORK.md` | Investigation workflow detail |

Product documents **MUST NOT** contradict **BUSINESS_STRATEGY.md** on commercial scope
or product identity. Product documents **MUST NOT** require architecture violations.

---

### 3.6 Development

| Field | Definition |
|-------|------------|
| **Purpose** | Describe **what is built** and **how developers work with the codebase** — as-built maps, API reference, pipeline guides, project structure. |
| **Ownership** | Engineering / developer experience |
| **Scope** | `docs/ARCHITECTURE.md`; `docs/INTELLIGENCE_PIPELINE.md`; `docs/EXTENDING_FORESTWATCH.md`; `docs/API_REFERENCE.md`; `docs/DATABASE.md`; `docs/DEPENDENCIES.md`; `docs/PROJECT_STRUCTURE.md` |
| **Authority** | **Descriptive authority only** — reflects current implementation. Subordinate to canonical Architecture for target design. |
| **May define** | Current code layout; verified as-built behavior; API surface as implemented; developer onboarding; extension how-to aligned with architecture |
| **May never define** | New architectural invariants; override of frozen architecture; commercial edition rules; product strategy; normative investigation workflow changes |

**Rule:** When as-built Development documents diverge from Architecture, **Architecture
governs the target**; Development documents **MUST** document divergence explicitly and
**MUST** reference canonical sources rather than restate architecture.

---

### 3.7 Operations

| Field | Definition |
|-------|------------|
| **Purpose** | Define **how the platform is operated in production** — deployment, monitoring, incident response, backup, and SLA operational procedures. |
| **Ownership** | Operations / site reliability / platform engineering |
| **Scope** | `docs/operations/` *(directory reserved — not yet populated)* |
| **Authority** | **Authoritative for operational procedure** only. Subordinate to Architecture and Engineering for system behavior. |
| **May define** | Runbooks; deployment procedures; on-call playbooks; environment configuration guides; operational checklists; SLA measurement procedure |
| **May never define** | Architecture; product capabilities; edition entitlements; engine logic; override of invariants |

Until `docs/operations/` exists, operational content **MUST NOT** be treated as
authoritative if it appears elsewhere without explicit relocation and approval.

---

### 3.8 Marketing

| Field | Definition |
|-------|------------|
| **Purpose** | External **messaging, campaigns, and market-facing content** derived from approved business and product documents. |
| **Ownership** | Marketing / commercial |
| **Scope** | `docs/marketing/` *(directory reserved — not yet populated)* |
| **Authority** | **Non-normative for platform behavior.** Must reflect approved Business and Product documents. Lowest prescriptive authority. |
| **May define** | Messaging guides; campaign briefs; website copy source; positioning summaries for external use |
| **May never define** | Platform capabilities not approved in Product documents; architectural claims; edition entitlements contradicting EDITION_STRATEGY; pricing unless approved in commercial pricing documents; legally binding technical guarantees |

Marketing **MUST NOT** position ForestWatch as wildfire-only or as a generic
environmental platform. Marketing **MUST** align with Forest Intelligence Platform
identity per `BUSINESS_STRATEGY.md` and `PRODUCT_STRATEGY.md`.

---

### 3.9 Archive

| Field | Definition |
|-------|------------|
| **Purpose** | Preserve **historical documentation snapshots** for audit and reference. |
| **Ownership** | Documentation maintainer |
| **Scope** | `docs/archive/`; `docs/archive/README.md` |
| **Authority** | **None.** Archive documents are **not** current truth. |
| **May define** | Historical snapshots only |
| **May never define** | Current behavior; override any living or frozen document; be updated in place |

**Rule:** Do not edit archived documents. Create new living documents or amend canonical
sources through the correct process.

---

## 4. Document Precedence

### 4.1 Global precedence rules

When documents conflict, apply precedence in this order:

1. **Architecture** (`docs/architecture/`) and **ADRs**
2. **Engineering** frozen specifications and **IMPLEMENTATION_PROTOCOL**
3. **Business Strategy** — commercial direction
4. **Product Strategy** — product identity
5. **Edition Strategy** — edition capability matrix *(within approved business stack)*
6. **Platform Capabilities** and **Investigation Framework**
7. **Go-To-Market Strategy** — customer motion
8. **Development** as-built documents
9. **Operations** runbooks
10. **Marketing** materials
11. **Archive** — no precedence

**Status documents** (`PROJECT_STATE.md`, `RELEASE_NOTES.md`) **MUST** reflect higher
authority; they **MUST NOT** redefine it.

### 4.2 Domain-specific precedence

| Question type | Authoritative source |
|---------------|---------------------|
| Platform invariant, engine contract, bounded context | Architecture + ADRs |
| Phase scope, work package, implementation process | Engineering frozen specs + IMPLEMENTATION_PROTOCOL |
| Commercial scope, market, competitive direction | BUSINESS_STRATEGY |
| Product identity, modules, principles | PRODUCT_STRATEGY |
| Edition entitlements (capability matrix, free/paid, upgrade/downgrade) | EDITION_STRATEGY — overrides PRODUCT_STRATEGY §9 **only** for edition capability lists |
| Customer acquisition and sales motion | GO_TO_MARKET_STRATEGY |
| Capability purpose, boundaries, interactions | PLATFORM_CAPABILITIES |
| Investigation workflow | INVESTIGATION_FRAMEWORK |
| Authorization (who may do what by edition and role) | ACCESS_CONTROL_MODEL |
| What the code does today | Development as-built docs |
| How to deploy and operate | Operations *(when exists)* |
| External messaging | Marketing *(when exists)* |

### 4.3 Implementation precedence

When implementing code:

```
Architecture + ADRs
        ↓
Engineering phase spec + backlog + IMPLEMENTATION_PROTOCOL
        ↓
Development as-built guides (for current state only)
        ↓
Business / Product / Marketing (MUST NOT drive architecture changes)
```

Implementation agents **MUST** stop when Business or Product documents imply behavior
that violates Architecture (IMPLEMENTATION_PROTOCOL §4).

---

## 5. Conflict Resolution Rules

### 5.1 No silent override

No contributor **MAY** resolve a conflict by:

- editing a lower-precedence document to match preference;
- implementing around an architectural conflict;
- treating archive, marketing, or as-built docs as override;
- assuming "most recent document wins" without approval.

### 5.2 Resolution process

| Step | Action |
|------|--------|
| **1. Identify** | Name both documents, sections, and the specific conflict |
| **2. Classify** | Technical (architecture/engineering) vs. commercial (business) vs. product behavior vs. descriptive (development) |
| **3. Apply precedence** | Use Section 4 unless an approved override exists |
| **4. Stop if blocked** | Implementation **MUST** stop if technical conflict affects frozen specs (IMPLEMENTATION_PROTOCOL §4.1) |
| **5. Report** | Record contradiction — implementation log for engineering; contradiction report for strategic docs |
| **6. Amend** | Update the **lower-precedence** document through review/approval — **never** silently edit higher authority |
| **7. Override (exceptional)** | Higher document changed only through its formal process (new ADR, architecture version bump, approved strategy revision) |

### 5.3 Cross-category conflict examples

| Conflict | Resolution |
|----------|------------|
| Product doc requires behavior violating INV-* | Product doc **MUST** be amended; architecture wins |
| Business doc promises category before architecture phase | Business/GTM **MUST** be amended or marked assumption; engineering phase gates win |
| EDITION_STRATEGY vs. PRODUCT_STRATEGY on Community investigations | **Resolved (2026-07-22, CMR-001):** EDITION_STRATEGY authoritative; PRODUCT_STRATEGY §9.1 amended — Community excludes operational investigations |
| As-built `ARCHITECTURE.md` vs. canonical architecture | Canonical architecture is target; as-built documents divergence |
| `ROADMAP.md` vs. `08-roadmap.md` phase ordering | `08-roadmap.md` wins for architecture phases |
| Marketing claim vs. PRODUCT_STRATEGY boundary | Marketing **MUST** be corrected |

### 5.4 Explicit override approval

A lower document **MAY** override a higher document **only** when:

1. The override is **explicitly recorded** (ADR, architecture CHANGELOG entry, or approved amendment to the higher document);
2. The override is **approved** by the owner of the higher category (Section 8);
3. The override is **not silent** — a contradiction report or changelog entry **MUST** exist.

**Example:** A new ADR explicitly supersedes a prior ADR — approved override through
architecture process.

---

## 6. Contradiction Handling

### 6.1 Definition

A **contradiction** exists when two documents make ** incompatible normative claims**
about the same subject — not merely different level of detail.

### 6.2 Handling rules

| Context | Required action |
|---------|-----------------|
| **During implementation** | Stop per IMPLEMENTATION_PROTOCOL §4; log in `IMPLEMENTATION_LOG.md`; do not work around |
| **During strategic doc authoring** | Report in document review; do not fix other documents unless explicitly tasked |
| **Discovered in review** | Record in contradiction report; assign owner by category |
| **Resolved** | Update lower-precedence doc OR amend higher through formal process; record resolution with date |
| **Open / unresolved** | **MUST** be treated as active; implementers **MUST NOT** assume resolution |

### 6.3 Contradiction registry

Contradictions **SHOULD** be tracked in:

- `docs/engineering/IMPLEMENTATION_PROTOCOL.md` §15 — engineering/process contradictions
- Author review reports — strategic document contradictions
- `docs/CHANGELOG.md` — when resolution changes project-visible state

New meta-level contradictions affecting hierarchy **SHOULD** be noted in review of this
document until a dedicated registry is approved.

### 6.4 Prohibited responses

Contributors **MUST NOT**:

- pick the document they prefer;
- implement a compromise that violates invariants;
- defer resolution indefinitely while shipping conflicting behavior;
- fix contradictions by editing archive documents.

---

## 7. Deprecated Documents and Archival

### 7.1 Deprecation

A document is **deprecated** when a newer authoritative document replaces its normative
role. Deprecation **MUST** be explicit:

- add a deprecation notice at the top of the living document **or**
- move a snapshot to `docs/archive/` and update `docs/archive/README.md`

### 7.2 Archival process

| Step | Action |
|------|--------|
| 1 | Confirm replacement document is approved and referenced |
| 2 | Copy snapshot to `docs/archive/` with date suffix if not already named |
| 3 | Update `docs/archive/README.md` index |
| 4 | Remove or redirect links in living documents |
| 5 | **Do not edit** the archived snapshot |

### 7.3 Archive authority

Archive documents have **zero authority**. They **MUST NOT** be cited as current
specification in implementation, product, or commercial decisions unless explicitly
historical context is required.

---

## 8. Document Modification Classes

### 8.1 Frozen documents

**Definition:** Normative documents that **MUST NOT** change during implementation or
routine maintenance except through a formal approval process.

| Document | Approval to amend |
|----------|-------------------|
| `docs/architecture/*.md` (numbered) | Architecture version bump + CHANGELOG; may require new ADR |
| `docs/architecture/adr/*.md` | New ADR or formal supersession |
| `docs/engineering/IMPLEMENTATION_PROTOCOL.md` | Explicit engineering leadership review |
| `docs/engineering/PHASE-*-ENGINE-GENERALIZATION.md` | Phase gate review — frozen per phase |
| `docs/engineering/PHASE-*-IMPLEMENTATION-BACKLOG.md` | Phase gate review — frozen per phase |

Frozen documents **MAY** receive **non-normative delivery notes** only when explicitly
permitted by phase specification (e.g. architecture CHANGELOG delivery note).

### 8.2 Living documents

**Definition:** Documents **MAY** be updated to reflect current state. They **MUST NOT**
contradict frozen architecture. They **SHOULD** reference canonical sources instead of
duplicating architecture.

| Document | Update trigger |
|----------|----------------|
| `docs/PROJECT_STATE.md` | Work-package boundaries; phase transitions |
| `docs/RELEASE_NOTES.md` | Releases; planned release scope changes |
| `docs/ROADMAP.md` | Feature delivery progress |
| `docs/ARCHITECTURE.md` | As-built alignment changes |
| `docs/INTELLIGENCE_PIPELINE.md` | Pipeline behavior changes |
| `docs/EXTENDING_FORESTWATCH.md` | Extension point changes |
| `docs/API_REFERENCE.md`, `docs/DATABASE.md`, etc. | Implementation changes |
| `docs/DOCUMENT_HIERARCHY.md` | Governance process changes |
| `docs/operations/*` | Operational procedure changes *(when exists)* |
| `docs/marketing/*` | Campaign and messaging updates *(when exists)* |

### 8.3 Append-only documents

**Definition:** Documents **MAY** receive new entries at the end. Existing entries **MUST
NOT** be overwritten, deleted, or rewritten.

| Document | Entry type |
|----------|------------|
| `docs/architecture/CHANGELOG.md` | Architecture version records |
| `docs/CHANGELOG.md` | Project changelog entries |
| `docs/engineering/IMPLEMENTATION_LOG.md` | Task and work-package completion records |

Corrections to append-only entries **MUST** be made by **addendum entry**, not by editing
prior text.

---

## 9. Review Requirements

| Category | Review required | Reviewer |
|----------|-----------------|----------|
| Architecture amendment | **Mandatory** | Platform architecture + engineering leadership |
| New / superseding ADR | **Mandatory** | Platform architecture |
| Engineering protocol amendment | **Mandatory** | Engineering leadership |
| Phase spec / backlog (before freeze) | **Mandatory** | Engineering + architecture alignment check |
| Business strategy documents | **Mandatory** before "approved" status | Commercial leadership + product leadership |
| Product documents | **Mandatory** before "approved" status | Product leadership + architecture alignment check |
| Development as-built updates | **Recommended** at work-package boundary | Engineering peer review |
| Operations runbooks | **Mandatory** before production use | Operations + engineering |
| Marketing materials | **Mandatory** before external publication | Marketing + product + commercial |
| Meta hierarchy (this document) | **Mandatory** | Cross-functional documentation owner |

Strategic documents currently marked **"pending review"** **MUST NOT** be treated as
fully approved for override purposes until review completes (Section 10).

---

## 10. Approval Requirements

### 10.1 Approval statuses

| Status | Meaning |
|--------|---------|
| **Frozen** | Approved; change only through formal process (Architecture, ADRs, Engineering protocol) |
| **Approved** | Strategic document reviewed; authoritative within its domain |
| **Pending review** | Draft strategic authority; conflicts **MUST** be reported, not assumed resolved |
| **Living** | Continuously updated; no single approval gate per edit |
| **Append-only** | Entries added per protocol; no approval per entry unless policy requires |
| **Archived** | No authority |

### 10.2 Current approval snapshot

| Document / set | Status |
|----------------|--------|
| Architecture v1.0 + ADR-001–011 | **Frozen** |
| IMPLEMENTATION_PROTOCOL | **Frozen** |
| Phase 0 engineering specs | **Frozen** |
| BUSINESS_STRATEGY, PRODUCT_STRATEGY, GO_TO_MARKET, EDITION_STRATEGY | **Pending review** |
| PLATFORM_CAPABILITIES, INVESTIGATION_FRAMEWORK | **Pending review** |
| DOCUMENT_HIERARCHY | **Pending review** |
| Development as-built docs | **Living** |
| PROJECT_STATE, RELEASE_NOTES, ROADMAP | **Living** |

### 10.3 Approval gate for overrides

No document **MAY** override another until:

1. Both documents involved are at appropriate approval status for their claims; and
2. Any required cross-functional review (Section 9) is complete; or
3. An explicit override is recorded per Section 5.4.

---

## 11. Versioning Philosophy

### 11.1 Architecture versioning

Architecture versions independently from application source code
(`docs/architecture/CHANGELOG.md`):

| Bump | When |
|------|------|
| **MAJOR** | Breaking invariant, contract, or dependency rule change |
| **MINOR** | Additive architectural capability without breaking invariants |
| **PATCH** | Clarification only — no invariant or contract change |

Application release versions (`docs/RELEASE_NOTES.md`) **MUST NOT** be conflated with
architecture version numbers.

### 11.2 Engineering versioning

Engineering artifacts are versioned by **phase** and **work package**, not semantic
version. Phase specs are frozen when execution begins.

### 11.3 Business and product versioning

Strategic documents use **document control** metadata (created date, status, related
documents) — not semantic versioning. Material revisions **SHOULD** note revision date
in document control; prior snapshots **MAY** be archived.

### 11.4 Development / as-built versioning

As-built documents **SHOULD** record last-audited date and implementation version
verified against (e.g. `ARCHITECTURE.md` v0.3.0 as-built).

### 11.5 Single identity invariant

All categories **MUST** preserve **Forest Intelligence Platform** identity across
revisions. Wildfire **MUST** remain one forest incident category among many in all
approved documents.

---

## 12. Document Lifecycle

```
Draft → Review → Approved / Frozen → (Living: maintain) → Deprecated → Archived
                      ↓
              Append-only: accumulate entries
                      ↓
              Contradiction discovered → Stop / Report → Resolve → Continue
```

| Stage | Description |
|-------|-------------|
| **Draft** | Authoring; not authoritative for overrides |
| **Review** | Cross-functional review per Section 9 |
| **Approved** | Strategic normative within domain |
| **Frozen** | Change only through formal process |
| **Living** | Updated as state changes; must stay consistent with frozen layer |
| **Append-only** | New entries only |
| **Deprecated** | Superseded; pointer to replacement |
| **Archived** | Immutable snapshot in `docs/archive/`; zero authority |

### 12.1 Creation rules

New documents **MUST**:

1. Declare category, status, audience, and authority in header.
2. State subordination to higher-precedence documents.
3. Be placed in the correct directory per category.
4. Be indexed in `docs/PROJECT_STRUCTURE.md` or category README when materially new.
5. **Not** duplicate content that belongs in Architecture.

### 12.2 Supersession rules

When a document is superseded:

- higher-precedence replacement **MUST** be identified;
- old document **MUST** be archived or marked deprecated;
- contradictions between old and new **MUST** be explicitly resolved in review.

---

## 13. Relationship to IMPLEMENTATION_PROTOCOL

`docs/engineering/IMPLEMENTATION_PROTOCOL.md` §1.3 defines a partial hierarchy focused
on implementation. **This document supersedes and extends** that table for the full
documentation stack.

Where IMPLEMENTATION_PROTOCOL and this document overlap:

- **Agreement:** Both subordinate implementation to Architecture + ADRs.
- **Extension:** This document adds Business, Product, Operations, Marketing, Archive,
  conflict resolution, and strategic document approval rules.

IMPLEMENTATION_PROTOCOL **MUST NOT** be interpreted as granting Business or Product
documents authority over Architecture.

---

## 14. Document Authority (This Document)

### 14.1 Authoritative for

- Documentation category definitions and precedence
- Conflict resolution and contradiction handling process
- Frozen, living, and append-only classification
- Review and approval requirements for documentation
- Archival rules

### 14.2 Subordinate to

- Nothing within the documentation governance domain — this is the meta-authority.
- Architecture and ADRs **still prevail** for all **technical** truth; this document
  **does not** grant itself technical override power.

### 14.3 Future documents that SHOULD derive from this one

| Document | Purpose |
|----------|---------|
| Documentation contribution guide | How to author, place, and review new docs |
| Document template standards | Required headers and metadata |
| Contradiction registry | Central open-contradiction tracker |
| Category README files | Per-directory index and ownership |

---

## Document Control

| Field | Value |
|-------|-------|
| Created | 2026-07-17 |
| Status | Pending review |
| Reconciliation | CMR-003 applied 2026-07-22 |
| Supersedes | Partial hierarchy in `IMPLEMENTATION_PROTOCOL.md` §1.3, §7 (extended, not replaced) |
| Related | All `docs/architecture/`, `docs/business/`, `docs/product/`, `docs/engineering/` |

---

*End of Documentation Hierarchy.*
