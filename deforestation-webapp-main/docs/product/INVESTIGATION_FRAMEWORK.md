# ForestWatch — Investigation Framework

**Status:** Strategic product document — pending review.
**Audience:** Product leadership, forest operators, analysts, compliance officers, and
stakeholders defining how human response works in the Forest Intelligence Platform.
**Authority:** This document defines the **investigation workflow** as a product
capability. It is subordinate to `docs/architecture/` and its ADRs for platform
invariants, and to `docs/business/PRODUCT_STRATEGY.md` for product module context. Where
this document and architecture disagree, architecture governs.

**Document type:** Investigation framework. This is not an implementation specification,
technical design, or API reference. It describes *how ForestWatch supports human
investigations* after intelligence has been derived — not *how investigations are built*.

**Scope:** Forest ecosystem investigations only, consistent with the Forest Intelligence
Platform identity defined in `docs/business/BUSINESS_STRATEGY.md`.

**Language:** The key words **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**,
**SHOULD NOT**, **MAY**, and **OPTIONAL** in this document are to be interpreted as
described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## 1. Purpose

ForestWatch derives **Intelligence Events** — persistent, scored, lifecycle-managed
tracked situations — from forest observations through deterministic reconciliation. Derived
intelligence is necessary but not sufficient for forest stewardship. Organizations must
**investigate** situations before acting, reporting, or reaching conclusions that carry
legal, regulatory, ethical, or operational weight.

This document defines the investigation framework: the product workflow through which
human analysts and field teams **respond** to derived intelligence, **collect evidence**,
**assess** situations, **decide** on outcomes, and **close** cases with a complete audit
record.

The investigation framework exists to:

1. Separate **derived intelligence** from **human judgment** (INV-13).
2. Provide a structured, repeatable workflow for forest incident response.
3. Ensure every human conclusion is **evidence-backed**, **explainable**, and **auditable**.
4. Integrate human response with Monitoring, Intelligence, Reporting, Command Center,
   and Compliance product modules without violating architecture invariants.

Investigations are a **bounded context** in the platform architecture. They **MUST NOT**
create, update, or resolve Intelligence Events. They annotate the human response to a
tracked situation.

---

## 2. Investigation Philosophy

### 2.1 Intelligence is not the final output

The Intelligence Engine produces **derived assertions** — operationally significant
situations detected from observations, scored and tracked over time. These assertions
are:

- **Statistical and rule-based**, not observational fact at a single point in time.
- **Category-segmented**, not legally or ethically definitive.
- **Continuously updated** as new observations arrive through reconciliation cycles.

A derived Intelligence Event answers: *"Does the platform detect a persistent situation
of concern in this forest category at this location, at this score, with this trend?"*

It does **not** answer:

- *"Has a crime occurred?"*
- *"Is this harvest permitted?"*
- *"Should enforcement action be taken?"*
- *"Is this reportable under regulation X?"*

Those questions belong to **human investigation**. The platform derives intelligence to
**direct attention**; humans investigate to **establish understanding and decide action**.

### 2.2 Why separation matters

Forest stewardship operates in contexts where conclusions carry consequence — regulatory
proceedings, certification audits, conservation advocacy, corporate liability, and
inter-agency coordination. Conflating derived intelligence with human conclusion:

- erodes trust when detections prove false on inspection;
- creates legal and ethical exposure when alerts are treated as findings;
- bypasses the evidence chain required for defensible decisions;
- removes accountability for judgment from the humans who must act.

ForestWatch **shall** maintain this separation permanently. Legally or ethically loaded
conclusions **MUST** be produced only through the Investigation workflow (INV-13). The
engine **MUST NOT** emit such conclusions automatically.

### 2.3 Investigation as accountability

An investigation is the product record of **who** examined a situation, **what** evidence
they considered, **how** they assessed it, **what** they concluded, and **when** the case
closed. It is the accountability layer that makes forest intelligence operationally and
organizationally usable.

---

## 3. Investigation Lifecycle

The investigation lifecycle describes the complete human response path from the moment
derived intelligence warrants attention through case closure. It is a **product workflow**;
it does not modify intelligence lifecycle state owned by the Reconciliation Engine
(ADR-006).

### 3.1 Lifecycle overview

```
Detection (Intelligence Event)
        ↓
Investigation opened
        ↓
Evidence collection
        ↓
Assessment
        ↓
Decision (human conclusion)
        ↓
Closure
```

Each stage is described below. Stages **MAY** be revisited — for example, new evidence
may require returning to collection before reassessment. The audit timeline **MUST**
record all transitions.

### 3.2 Detection (trigger — not an investigation stage)

**What happens:** The platform reconciles observations and produces or updates an
Intelligence Event — a tracked forest situation with identity, score, trend, escalation,
and supporting evidence metadata.

**Investigation role:** Detection is the **trigger** for investigation, not part of the
investigation workflow itself. An analyst or operator observes derived intelligence through
the Intelligence module or Command Center and determines that human response is warranted.

**Invariant:** Opening an investigation **MUST NOT** mutate Intelligence Event lifecycle
state. Intelligence continues to update independently through reconciliation cycles while
an investigation is open.

### 3.3 Investigation opened

**What happens:** A human opens an investigation in response to derived intelligence (or,
in exceptional cases, without a linked Intelligence Event — see §4). The investigation
receives assignment, an initial scope, and an audit timeline entry.

**Entry criteria (product):** An investigation **SHOULD** be opened when:

- an active Intelligence Event exceeds operator priority threshold;
- a notification routes a situation for human review;
- a compliance obligation requires verification of a detected situation;
- a field report corroborates or contradicts derived intelligence.

**Outputs:** Investigation record with workflow status, assignee, link to Intelligence
Event (when applicable), and timestamped audit entry.

### 3.4 Evidence collection

**What happens:** Assigned analysts gather evidence from platform and external sources
(§5). Evidence is attached to the investigation audit timeline — not to Intelligence Event
lifecycle state.

**Principles:**

- Evidence **SHALL** be attributed to a source and collection timestamp.
- Evidence **MAY** include platform-derived material (observations, intelligence history,
  spatial overlays) and externally sourced material (field reports, permits, imagery).
- Collection **MAY** span multiple sessions and multiple contributors.
- New platform observations arriving during collection **MAY** appear in linked
  Intelligence Event updates; the investigation **SHOULD** reference them explicitly when
  assessed.

**Outputs:** Evidence entries on the audit timeline; optional structured notes on
provenance and relevance.

### 3.5 Assessment

**What happens:** Analysts evaluate collected evidence against the derived intelligence
assertion and the operational question the investigation addresses. Assessment is
analytical, not conclusory — it interprets evidence; it does not substitute for decision.

**Assessment questions (illustrative):**

- Does field evidence confirm, partially confirm, or refute the derived situation?
- Are there permit, ownership, or protected-area facts that contextualize the signal?
- Is the intelligence score and trend consistent with observed conditions?
- Are there data gaps that limit confidence?

**Outputs:** Assessment notes on the audit timeline; updated workflow status; optional
request for additional evidence (return to collection).

### 3.6 Decision (human conclusion)

**What happens:** The assigned analyst or authorized decision-maker records a **human
conclusion** — the investigation outcome. This is the only product stage where legally
or ethically loaded determinations **MAY** be recorded (INV-13).

**Decision types (illustrative, not exhaustive):**

- Confirmed — situation verified; action required.
- Unconfirmed — insufficient evidence; monitoring continues.
- False positive — derived intelligence not supported by evidence.
- Permitted activity — situation explained by authorized activity.
- Referred — escalated to external authority or parallel process.
- Inconclusive — investigation closed without definitive finding.

**Principles:**

- Every decision **MUST** reference the evidence considered.
- Decision **MUST NOT** automatically resolve or modify the linked Intelligence Event.
- Decision **MAY** recommend operational follow-up; follow-up **SHOULD** be recorded.

**Outputs:** Investigation outcome recorded; audit timeline entry with decision rationale.

### 3.7 Closure

**What happens:** The investigation is closed with a final resolution status. Closure
finalizes the audit record and updates investigation statistics visible in the Command
Center and Reporting modules.

**Closure requirements:**

- Outcome **MUST** be recorded before closure unless explicitly marked incomplete with
  reason.
- Audit timeline **MUST** be complete and immutable (append-only after closure).
- Linked Intelligence Event **MAY** remain active, resolved, or updated independently
  per reconciliation — investigation closure does not govern intelligence lifecycle.

**Outputs:** Closed investigation with complete audit trail; notification of closure
where configured; inclusion in investigation statistics and reports.

---

## 4. Investigation Object

An **Investigation** is the product representation of a human response case. It is
defined conceptually below. Implementation details are outside this document.

### 4.1 What an investigation represents

An investigation represents:

- a **human-initiated response** to a forest situation requiring judgment beyond derived
  intelligence;
- an **accountability record** of assignment, evidence, assessment, decision, and closure;
- an **optional binding** to one Intelligence Event that triggered or contextualizes the
  case;
- an **append-only audit timeline** of all actions and evidence over the investigation
  lifetime.

An investigation **does not** represent:

- the derived intelligence itself (that is an Intelligence Event);
- a raw observation (that is a Forest Event / observation);
- an automated detection (that is a Detection consumed by reconciliation);
- a legal filing, enforcement order, or regulatory determination — though it **MAY**
  support preparation of such artifacts through Reporting.

### 4.2 Core attributes (conceptual)

| Attribute | Meaning |
|-----------|---------|
| **Identity** | Unique investigation identifier, distinct from Intelligence Event identity. |
| **Title / reference** | Human-readable case label for operational use. |
| **Linked Intelligence Event** | Optional binding to the tracked situation that prompted investigation. Architecture permits investigations without a link for ad-hoc or externally triggered cases. |
| **Forest incident category** | The forest category under examination (e.g. wildfire, forest loss, compliance), derivable from linked intelligence or explicitly set. |
| **Location context** | Geographic and jurisdictional context (region, coordinates, protected area membership) derived from linked intelligence and spatial enrichment. |
| **Assignment** | Analyst, team, or role responsible for the investigation. |
| **Workflow status** | Current stage in the investigation lifecycle (§3). |
| **Resolution** | How the investigation was closed (e.g. completed, withdrawn, merged). |
| **Outcome** | Human conclusion from the decision stage (§3.6). |
| **Audit timeline** | Ordered, append-only record of events, evidence attachments, status changes, notes, and decisions. |
| **Timestamps** | Created, last updated, closed — for operational and audit purposes. |

### 4.3 Relationship to Intelligence Events

When bound to an Intelligence Event, an investigation **annotates** the human response to
that tracked situation. It **MUST NOT**:

- create a new Intelligence Event;
- resolve, escalate, or score an Intelligence Event;
- alter Intelligence Event identity or lifecycle state.

Multiple investigations **MAY** bind to the same Intelligence Event over time (e.g. initial
field check followed by compliance review), subject to organizational policy. The platform
**SHOULD** preserve chronological audit separation between them.

---

## 5. Investigation Sources

Evidence in an investigation **MAY** come from any source the organization trusts.
ForestWatch provides platform-native sources; organizations **MAY** attach external
material to the audit timeline.

### 5.1 Platform-native sources

| Source | What it provides |
|--------|------------------|
| **Linked Intelligence Event** | Current and historical score, trend, escalation, detection count, severity, and engine evidence metadata. |
| **Historical detections** | Prior observations and intelligence history for the same location and category. |
| **Forest observations** | Underlying Forest Events that contributed to derived intelligence — timestamps, sources, confidence, severity. |
| **Satellite and remote imagery context** | Observation provenance from configured ingestion sources; spatial context from enrichment (not a substitute for visual interpretation by the analyst). |
| **Protected areas** | Spatial overlay membership — whether the situation falls within a protected forest boundary. |
| **Land cover and forest context** | Spatial enrichment classifying location context (forest, near-forest, etc.). |
| **Ownership and jurisdiction overlays** | When configured — administrative boundaries, management units, tenure context. |
| **Permits and compliance datasets** | When registered as spatial or reference overlays — authorized activity context for compliance investigations. |
| **Historical analysis** | Temporal trends, baseline deviation history, and resolved situation records from the Historical Analysis product module. |
| **Prior investigations** | Closed investigation outcomes and audit timelines for the same location or linked intelligence. |

### 5.2 External sources

Organizations **MAY** attach external evidence to the audit timeline:

- field inspection reports and photographs;
- ground survey measurements;
- witness or community reports;
- government registry extracts (permits, citations, cadastral records);
- third-party audit or certification documents;
- legal or enforcement correspondence.

External evidence **SHOULD** record source, collector, date, and relevance. The platform
**MAY** store references or attachments according to product edition capabilities; the
audit timeline **MUST** record that evidence was considered even when stored externally.

### 5.3 Source principles

- No evidence source **MAY** silently override derived intelligence lifecycle — evidence
  informs human conclusion only.
- Spatial enrichment **SHALL** be treated as additive context (INV-12), not as a
  conclusion.
- Absence of evidence **SHALL** be explicitly noted in assessment when it limits decision
  confidence.

---

## 6. Investigation Timeline

The **audit timeline** is the chronological record of an investigation's evolution. It is
append-only: entries **MUST NOT** be deleted or rewritten after recording. Corrections
**SHOULD** be made by adding a superseding entry with explanation.

### 6.1 Timeline entry types

| Entry type | Description |
|------------|-------------|
| **Created** | Investigation opened; initial assignment and scope. |
| **Assigned / reassigned** | Responsibility transferred. |
| **Status change** | Workflow status transition (§3). |
| **Evidence attached** | Source reference, summary, and attachment metadata. |
| **Note** | Analyst observation, assessment commentary, or internal coordination. |
| **Assessment recorded** | Structured assessment summary before decision. |
| **Decision recorded** | Human outcome with rationale and evidence references. |
| **Escalated** | Case referred to senior analyst, external authority, or parallel process. |
| **Closed** | Investigation closure with resolution status. |

### 6.2 Evolution patterns

Investigations typically evolve through one or more of these patterns:

- **Linear** — open → collect → assess → decide → close in a single pass.
- **Iterative** — multiple evidence collection and assessment cycles as new information
  arrives (including updated Intelligence Event state from reconciliation).
- **Escalated** — initial investigation closed or suspended; new investigation or external
  process continues.
- **Long-running** — investigation remains open across many reconciliation cycles while
  intelligence persists or evolves; timeline accumulates periodic review entries.

The timeline **SHALL** reflect the actual path taken, not an idealized single-pass workflow.

### 6.3 Concurrent intelligence updates

While an investigation is open, the linked Intelligence Event **MAY** receive new
detections, score updates, trend changes, or resolution through normal reconciliation.
The investigation timeline **SHOULD** record when material intelligence changes occur during
an open case, and assessment **SHOULD** account for them before decision.

---

## 7. Human-in-the-loop

Human participation is **mandatory** at defined decision points. Automation **MAY**
assist; it **MUST NOT** replace human judgment for conclusions quarantined by INV-13.

### 7.1 Required human participation

| Stage | Human role |
|-------|------------|
| **Open investigation** | A human **MUST** decide to open a case (directly or by acting on a routed notification). |
| **Assignment** | A human **MUST** accept or be assigned responsibility. |
| **Evidence selection** | A human **MUST** determine which sources are relevant and sufficient. |
| **Assessment** | A human **MUST** interpret evidence against the operational question. |
| **Decision** | A human **MUST** record the outcome and rationale. |
| **Closure** | A human **MUST** authorize closure. |

### 7.2 Optional human participation

| Activity | Human role |
|----------|------------|
| **Prioritization** | Operators **MAY** use intelligence priority scores to decide which situations to investigate first; score **MUST NOT** auto-open investigations. |
| **Notification response** | Humans **MAY** act on notifications by opening investigations; notifications **MUST NOT** record conclusions. |
| **Report review** | Humans **MAY** use reports as investigation inputs; reports **MUST NOT** substitute for investigation workflow. |

### 7.3 Roles (illustrative)

Organizations **MAY** map product assignment to operational roles:

- **Duty officer** — monitors Command Center; opens and triages investigations.
- **Field analyst** — collects field evidence; updates timeline from inspections.
- **Senior analyst** — assesses evidence; records decisions for complex cases.
- **Compliance officer** — leads compliance-category investigations; exports audit artifacts.
- **Supervisor** — reassigns, escalates, and authorizes closure.

Role definitions are organizational; the product **SHALL** support assignment and audit
attribution regardless of role model.

---

## 8. Explainability

Every human conclusion recorded in an investigation **SHALL** be explainable to a third
party — supervisor, auditor, regulator, or court — without requiring access to platform
internals.

### 8.1 Explainability requirements

1. **Intelligence linkage** — When bound, the investigation **SHALL** reference the
   Intelligence Event identity and the derived attributes (category, location, score,
   trend) that prompted response.
2. **Evidence enumeration** — The decision **SHALL** identify which evidence entries
   were considered.
3. **Rationale** — The decision **SHALL** include human-readable reasoning connecting
   evidence to outcome.
4. **Engine transparency** — Where platform-derived intelligence contributed, the
   investigation **SHOULD** reference the deterministic inputs (observation counts,
   deviation, detection metadata) available from the Intelligence Event — not opaque
   model scores alone.
5. **Negative findings** — False positive and unconfirmed outcomes **SHALL** be
   explainable with equal rigor to confirmed findings.

### 8.2 Prohibited patterns

- Recording a decision without evidence reference.
- Treating intelligence score as sole justification for conclusion.
- Black-box automated conclusion presented as investigation outcome.
- Retroactive alteration of audit timeline to match a desired conclusion.

---

## 9. Auditability

Every investigation **SHALL** be reproducible: an independent reviewer **MUST** be able
to reconstruct what was known, what was considered, and what was decided at closure.

### 9.1 Audit properties

| Property | Requirement |
|----------|-------------|
| **Immutability** | Audit timeline entries **MUST NOT** be deleted or edited after recording. |
| **Attribution** | Every entry **MUST** record who acted and when. |
| **Completeness** | Closure **MUST NOT** occur without outcome and resolution recorded. |
| **Linkage integrity** | Reference to linked Intelligence Event **MUST** remain stable; orphaned investigations **SHOULD** be prevented by product policy. |
| **Export** | Investigation audit records **SHALL** be exportable through Reporting for external audit. |
| **Deterministic intelligence reference** | Platform-derived intelligence cited in an investigation **SHALL** be reproducible from documented inputs per INV-4. |

### 9.2 Audit use cases

- **Internal review** — supervisor validates analyst decision quality.
- **Regulatory response** — agency demonstrates due diligence on detected forest loss.
- **Certification audit** — certification body reviews investigation record for compliance
  category situations.
- **Legal-adjacent proceedings** — organization produces investigation export; platform
  **MUST NOT** claim the export is legal evidence — it is the organization's record of
  their process (consistent with product boundaries in `PRODUCT_STRATEGY.md` §12).

---

## 10. Product Integration

Investigations interact with other ForestWatch product modules as a **response layer**
downstream of derived intelligence. Integration **MUST** respect read-only projection
rules and architecture dependency direction.

### 10.1 Monitoring

**Relationship:** Monitoring provides observation intake visibility. Investigations **MAY**
reference observations that contributed to linked intelligence.

**Integration rule:** Investigations **MUST NOT** mutate observations or ingestion state.
Monitoring is read-only input to evidence collection.

### 10.2 Intelligence

**Relationship:** Intelligence Events are the primary trigger and contextual anchor for
investigations. Investigations bind optionally to one Intelligence Event.

**Integration rule:** Investigations **MUST NOT** create, update, resolve, or score
Intelligence Events (ADR-006). Intelligence continues to evolve through reconciliation
independently. Analysts **SHALL** treat intelligence as derived assertion, not conclusion.

### 10.3 Reporting

**Relationship:** Reporting composes point-in-time artifacts from read-only projections,
including investigation statistics and case exports.

**Integration rule:** Reports **MAY** include investigation summaries, timelines, and
outcomes as registered report sections. Report generation **MUST NOT** mutate
investigation or intelligence state. Scheduled reports **MAY** include open and closed
investigation counts for operational briefings.

### 10.4 Command Center

**Relationship:** Command Center presents live operational projection including
investigation statistics (open count, closure rate, assignment load).

**Integration rule:** Command Center **MUST NOT** mutate investigations or intelligence
(`docs/architecture/07-reporting-and-command-center.md`). Operators **MAY** navigate from
Command Center intelligence views to open or review investigations. Freshness of
investigation statistics follows the same reconciliation and read cycle cadence as other
Command Center data.

### 10.5 Compliance

**Relationship:** Compliance is a product composition (per `PRODUCT_STRATEGY.md` §8) of
Intelligence, Investigations, Reporting, and spatial overlays applied to compliance-
relevant forest categories.

**Integration rule:** Compliance workflows **SHALL** route legally or ethically loaded
findings through Investigation decision and closure stages. Compliance reports **SHALL**
cite investigation audit records, not raw intelligence alone. Permit and protected-area
overlays **SHOULD** be standard evidence sources for compliance investigations.

### 10.6 Notifications

**Relationship:** Notifications **MAY** dispatch on investigation lifecycle transitions
(created, assigned, escalated, closed) per `docs/architecture/09-system-context.md` §3.10.

**Integration rule:** Notifications **MUST NOT** record conclusions or mutate intelligence
state. They alert humans to act; investigation workflow records the action taken.

---

## 11. Future AI Assistance

ForestWatch **MAY** introduce AI-assisted capabilities to support investigations in
future product versions. AI assistance **MUST** comply with INV-13: AI **MUST NOT**
become the decision-maker for legally or ethically loaded conclusions.

### 11.1 Permitted AI assistance (conceptual)

AI **MAY** assist investigations by:

- summarizing large evidence collections for analyst review;
- suggesting relevant evidence sources based on incident category and location context;
- highlighting inconsistencies between field reports and derived intelligence;
- drafting preliminary assessment notes for human edit and approval;
- prioritizing open investigations by operational urgency;
- extracting structured fields from uploaded field reports or documents;
- recommending similar closed investigations for precedent comparison.

In every case, the AI output **SHALL** be presented as **assistance**, recorded on the
audit timeline as machine-generated when material to assessment, and **SHALL** require
explicit human acceptance before forming part of a decision rationale.

### 11.2 Prohibited AI patterns

AI **MUST NOT**:

- record investigation outcomes or decisions autonomously;
- close investigations without human authorization;
- resolve or modify Intelligence Events;
- present confidence scores as substitutes for human conclusion;
- bypass evidence collection or assessment stages;
- generate legally definitive findings (e.g. "illegal logging confirmed") without human
  decision entry.

### 11.3 Relationship to model-assisted detection

Architecture roadmap (`docs/architecture/08-roadmap.md` §9) recognizes **model-assisted
detection** as a future platform layer for the **Detector Framework** — producing
Detections consumed by reconciliation. That is distinct from investigation AI:

- **Detection AI** feeds the intelligence engine as observation-derived input, subject to
  deterministic reconciliation and canonical Detection contracts (ADR-009).
- **Investigation AI** assists human analysts after intelligence exists, subject to
  INV-13 quarantine.

These **MUST NOT** be conflated. A model-assisted detection **MUST NOT** auto-generate
an investigation conclusion.

---

## 12. Long-term Evolution

Investigation workflow **SHALL** remain stable across architecture phases. Domain plug-in
onboarding **MUST NOT** require investigation engine changes (ADR-005 §3.7). What evolves
is the ** richness of evidence sources**, **category coverage**, and **optional AI
assistance** — not the core lifecycle or invariants.

### 12.1 Phase 0 — Engine Generalization

**Investigation impact:** None on workflow structure. Intelligence Events generalize to
multi-category identity; investigations bind to canonical `(incident_category, spatial_key)`
like today. Audit and explainability requirements apply uniformly across categories.

### 12.2 Phase 1 — Spatial Engine Generalization

**Investigation impact:** Richer evidence sources — protected areas, land cover, forest
boundaries, jurisdictional overlays — available during evidence collection without workflow
change. Compliance investigations benefit from standardized spatial context.

### 12.3 Phase 2 — First Human Activity Domain (Forest Loss)

**Investigation impact:** Forest-loss category investigations become operational —
illegal logging, land-use change, protected-area violations. Investigation workflow
unchanged; category-specific evidence sources (e.g. GLAD/RADD observation provenance,
protected-area overlay) become standard. Report sections for forest-loss investigations
register through Reporting extension.

### 12.4 Phase 3 — Surface Layer

**Investigation impact:** User-facing investigation access integrated with multi-category
map, filters, and Command Center. Operators **MAY** open investigations from map context
and category views. Investigation statistics appear in activated Command Center domain
catalog.

### 12.5 Future forest categories and platform layers

**Investigation impact:** Each new forest incident category (§7, `08-roadmap.md`) inherits
the same investigation lifecycle automatically. Category-specific evidence sources and
report sections extend through registration. Optional investigation AI assistance (§11)
**MAY** mature. Cross-category investigations (e.g. fire followed by logging in same
location) **MAY** reference multiple linked intelligence events through organizational
policy — the platform **SHOULD** support audit linkage without merging cases.

**Invariant across all phases:** Investigations **MUST NOT** mutate intelligence
lifecycle. Human judgment **MUST** remain quarantined in investigation decisions (INV-13).
Audit timeline **MUST** remain append-only and exportable.

---

## Document Control

| Field | Value |
|-------|-------|
| Created | 2026-07-17 |
| Status | Pending review |
| Related product | `docs/business/PRODUCT_STRATEGY.md` §8.3, §10, §11 |
| Related business | `docs/business/BUSINESS_STRATEGY.md` §3, §7 |
| Related architecture | `00-platform-vision.md`, `02-intelligence-engine.md` §4.5, `06-domain-plugin-architecture.md` §3.7, `07-reporting-and-command-center.md`, `09-system-context.md` |
| Related invariants | INV-13 (human judgment quarantine), INV-4 (deterministic analytics), INV-12 (additive enrichment) |
| Related ADRs | ADR-005 (investigations unchanged on domain onboarding), ADR-006 (investigations annotate, do not own lifecycle) |

---

*End of Investigation Framework.*
