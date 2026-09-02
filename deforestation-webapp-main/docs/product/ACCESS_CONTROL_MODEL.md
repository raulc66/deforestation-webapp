# ForestWatch — Access Control Model

**Status:** Strategic product document — pending review.
**Audience:** Product leadership, security, commercial, engineering, and governance
stakeholders defining who may perform which actions across the Forest Intelligence Platform.
**Authority:** This document defines the **authorization model** — WHO may perform WHICH
actions. It is subordinate to `docs/architecture/` and its ADRs for platform invariants,
to `docs/business/EDITION_STRATEGY.md` for edition entitlements, to
`docs/product/PLATFORM_CAPABILITIES.md` for capability boundaries, and to
`docs/product/INVESTIGATION_FRAMEWORK.md` for investigation workflow rules. Where access
rules and architecture disagree, architecture governs. Where access rules and edition
entitlements disagree, **EDITION_STRATEGY** governs commercial capability gates.

**Document type:** Product and governance authorization model. This is not an
implementation specification. It does not define databases, JWT claims, API endpoints,
middleware, database schemas, or code.

**Product identity:** ForestWatch is a **Forest Intelligence Platform** scoped to forest
ecosystems. Wildfire is one forest incident category among many.

**Language:** The key words **MUST**, **MUST NOT**, **SHALL**, **SHALL NOT**, **SHOULD**,
**SHOULD NOT**, **MAY**, and **OPTIONAL** in this document are to be interpreted as
described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## 1. Purpose

ForestWatch authorization governs five distinct **actor classes**:

1. **Anonymous public users** — no account; public transparency layer only.
2. **Registered Community users** — free personal accounts; no organization.
3. **Professional organizations** — paid organizational operational access.
4. **Enterprise organizations** — paid organizational access plus isolation, integration, and extended administration.
5. **Platform administrators** — ForestWatch operator staff governing platform-wide policy and public publication.

This document defines:

- **WHO** may perform **WHICH** actions across intelligence, investigations, reporting,
  administration, collaboration, and integration.
- **WHAT** each actor may **view**, **create**, **edit**, **publish**, and **own**.
- **HOW** organization membership, roles, permission inheritance, and delegation work.
- **HOW** the model aligns with future **multi-tenancy** (ADR-010) without redesign.

Authorization **SHALL** enforce edition entitlements and architecture invariants. No actor
**MAY** mutate Intelligence Event lifecycle through product actions (INV-1, ADR-011).
Human conclusions **MAY** be recorded only through authorized investigation workflow
(INV-13).

---

## 2. Design Principles

| ID | Principle |
|----|-----------|
| **AC-1** | **Least privilege** — grant minimum permissions required for role and edition. |
| **AC-2** | **Edition gates capability; role gates action** — e.g., investigations require Professional organization; within that, role determines create/edit/close. |
| **AC-3** | **Public trust is not paywalled** — public intelligence, open reports, and public maps remain free without authentication. |
| **AC-4** | **Organizations own operational data** — investigations, private reports, and org configuration belong to the organization. |
| **AC-5** | **Investigations are organizational and human** — formal cases require Professional or Enterprise; conclusions are human-authored (INV-13). |
| **AC-6** | **Intelligence is read-only for all product actors** — no user, API, or admin role mutates Intelligence Event lifecycle (INV-1). |
| **AC-7** | **Tenant-ready boundaries** — organization maps to reserved tenant dimension when multi-tenancy activates (ADR-010). |
| **AC-8** | **Audit consequential actions** — membership, investigation, admin, integration, and public publication changes are auditable. |
| **AC-9** | **Platform vs. organization administration** — platform admins govern public scope; org admins govern members and org configuration only. |
| **AC-10** | **Collaboration is organizational** — multi-user teamwork requires Professional or Enterprise; Community is single-user personal workspace. |
| **AC-11** | **Fail closed** — if entitlement, membership, role, or scope cannot be verified, deny access. |

---

## 3. Public Access Model

### 3.1 Actor: Anonymous public user

An **anonymous public user** has no ForestWatch account. This actor accesses the **public
transparency layer** only (EDITION_STRATEGY §1.3 Layer 0).

#### 3.1.1 Actor authorization profile

| Dimension | Anonymous public user |
|-----------|----------------------|
| **Information that may be viewed** | Public derived intelligence; open public report snapshots; public maps; public methodology explainability for configured scope |
| **Intelligence that may be accessed** | **Public intelligence only** — platform-operated derived intelligence in configured public geography and forest incident categories |
| **Investigations — create** | **No** |
| **Investigations — edit** | **No** |
| **Reports — generate** | **No** private or personal reports |
| **Reports — publish publicly** | **No** — may view platform-published open reports only |
| **APIs — use** | **No** |
| **Administration** | **No** |
| **Collaboration** | **No** |
| **Ownership — public intelligence** | **Platform-owned**; public user has view-only access, no ownership |
| **Ownership — private intelligence** | **No access**; no ownership |
| **Ownership — investigations** | **No access**; no ownership |
| **Ownership — reports** | **No ownership**; may view open public report snapshots only |

#### 3.1.2 Permitted and prohibited actions

**Permitted:** view public intelligence, open reports, public maps; register for Community
Edition.

**Prohibited:** all organizational, operational, private, API, and administrative actions.

Public users **MUST NOT** be implied to hold operational or emergency-response authority.

---

## 4. Registered User Model

### 4.1 Actor: Registered Community user

A **registered Community user** has a free ForestWatch account with a **personal workspace**
only. Community users **SHALL NOT** belong to an organization (EDITION_STRATEGY §2.7–2.8).

#### 4.1.1 Actor authorization profile

| Dimension | Registered Community user |
|-----------|---------------------------|
| **Information that may be viewed** | All public-layer content; personal workspace (saved views, watchlists, annotations); bounded monitoring and Command Center for **one geography**; Historical Analysis within **limited retention**; core-section personal manual reports |
| **Intelligence that may be accessed** | **Public intelligence** (full) plus **Community bounded intelligence** (one geography, limited forest incident categories) |
| **Investigations — create** | **No** — personal annotations are not investigation records |
| **Investigations — edit** | **No** |
| **Reports — generate** | **Yes** — manual **personal** reports (core sections, bounded scope); **No** compliance sections, investigation summaries, or enterprise audit formats |
| **Reports — publish publicly** | **No** — may view platform open reports; cannot publish to public layer |
| **APIs — use** | **No** |
| **Administration** | **No** organizational administration; personal workspace preferences only |
| **Collaboration** | **No** — single-user personal workspace; second user requires Professional organization |
| **Ownership — public intelligence** | **Platform-owned**; user has view access |
| **Ownership — private intelligence** | **No org-private intelligence**; personal bounded views are user-scoped, not organizational |
| **Ownership — investigations** | **None** — annotations in personal workspace are not investigations |
| **Ownership — reports** | **Personal manual reports** owned by user; not organizational audit artifacts |

#### 4.1.2 Upgrade boundary

When a Community user requires **formal investigations**, **team collaboration**,
**Compliance**, **automation**, **multi-geography scope**, or **organizational
administration**, they **MUST** join or create a **Professional or Enterprise organization**.

### 4.2 Registered user with organization membership

Users with Professional or Enterprise membership are covered in Sections 5 and 6 as
**organizational members**. A single human **MAY** simultaneously be a Community user
(personal workspace) and a member of one or more organizations; permissions **SHALL** be
evaluated in **explicit context** (personal vs. organization).

---

## 5. Organization Model

### 5.1 Definition

An **organization** is the unit of **commercial entitlement**, **operational data
ownership**, and **collaboration** for Professional and Enterprise customers.

### 5.2 Organization attributes (conceptual)

| Attribute | Purpose |
|-----------|---------|
| **Identity** | Unique organization identifier |
| **Edition** | Professional or Enterprise |
| **Tenant key** | Reserved; equals organization when multi-tenancy is active (ADR-010) |
| **Geographic scope** | Operational regions and boundaries entitled for private intelligence |
| **Category scope** | Forest incident categories entitled for operational use |
| **Configuration** | Sources, overlays, schedules, compliance templates — org-owned |
| **Membership roster** | Users, roles, delegation records |

### 5.3 Community is not an organization

A Community personal workspace **SHALL NOT** be modeled as an organization. Collaboration,
shared investigations, and org administration **require** a paying organization.

### 5.4 Professional vs. Enterprise (organization-level)

Both are **organizations** with members and roles. **Enterprise** adds API access,
integration administration, extended security/audit administration, multi-tenant
isolation when implemented, and private deployment options (EDITION_STRATEGY §4).

---

## 6. Organization Membership

### 6.1 Membership rules

| Rule | Description |
|------|-------------|
| **Entry** | Organization administrators **SHALL** invite or provision members; self-join **MAY** occur only through approved invite flows |
| **Minimum edition** | **Professional** minimum for any multi-user organization |
| **Multiple organizations** | A user **MAY** belong to multiple organizations; permissions evaluated **per organization context** |
| **Removal** | Revokes org permissions immediately; historical audit **SHALL** retain attributed actions |
| **Suspension** | Administrators **MAY** suspend members without deleting audit history |
| **Context switching** | Users **SHALL** explicitly select organization context when acting on org resources |

### 6.2 Membership vs. role vs. permission

```
User account
    → Organization membership (entry)
        → Role assignment(s) (bundle of permissions)
            → Effective permissions (union of roles, minus separation-of-duties restrictions)
                → Scoped to org geography, category, and tenant boundary
```

### 6.3 Permission inheritance

| Rule | Description |
|------|-------------|
| **Role union** | Multiple roles **SHALL** combine permissions as the **union** of granted actions unless org policy applies separation of duties |
| **Hierarchical roles** | **Organization Owner** **SHALL** inherit **Organization Administrator** permissions unless explicitly restricted |
| **Viewer baseline** | **Viewer** is the minimal read role; higher roles **SHALL** inherit Viewer read access to org-scoped intelligence and Command Center |
| **Edition ceiling** | No role **MAY** grant permissions excluded by organization edition (e.g., API on Professional) |
| **Scope inheritance** | Permissions apply only within organization's entitled geography and category scope |
| **No cross-org inheritance** | Membership in Organization A **MUST NOT** grant access to Organization B resources |

### 6.4 Delegation

| Delegation type | Rules |
|-----------------|-------|
| **Investigation assignment** | Operations Lead, Compliance Officer, or Administrator **MAY** assign cases to Analysts; assignees gain `investigation:edit_assigned` on assigned cases |
| **Temporary elevation** | Organization Owner **MAY** grant time-bound role elevation (e.g., Acting Operations Lead) — **MUST** be audited |
| **Decision authority** | `investigation:decide` **MAY** be delegated to assigned Analysts by org policy; **MUST NOT** delegate to automation or API without human-in-the-loop controls (INV-13) |
| **Administration delegation** | Owner **MAY** delegate member management to Organization Administrator; Owner retains ultimate entitlement and ownership transfer |
| **Integration delegation** | Enterprise: Integration Administrator manages API credentials; **MUST NOT** share credentials across organizations |
| **Prohibited delegation** | **MUST NOT** delegate platform publication, intelligence lifecycle mutation, or cross-tenant access to customer roles |

### 6.5 Administrator responsibilities

#### Organization Owner

- ultimate accountability for organization entitlement and data;
- may transfer ownership;
- inherits full Organization Administrator permissions;
- approves high-risk policy (retention, audit export, integration scope on Enterprise).

#### Organization Administrator

- manage membership, roles, invitations, suspensions;
- configure geography, category scope, sources, overlays, schedules;
- ensure edition entitlements are not exceeded;
- **MUST NOT** publish to public layer or access other organizations' data.

#### Integration Administrator (Enterprise)

- issue, rotate, revoke API credentials;
- configure integrations and embedding within org scope;
- **MUST NOT** grant API access outside Enterprise or record investigation decisions via integration.

#### Security Administrator (Enterprise)

- configure retention, audit export, and access review policies;
- review security audit logs;
- **MUST NOT** mutate intelligence lifecycle or publish public content.

#### Platform Administrator

- govern public intelligence scope and open public report publication;
- manage platform operator staff accounts;
- perform **audited break-glass** access when contractually permitted;
- **MUST NOT** record customer investigation decisions or merge private org data into public scope without publication workflow.

---

## 7. Roles

Roles are assigned **within an organization** (or at platform level for platform staff).

### 7.1 Organizational roles (Professional and Enterprise)

| Role | Summary |
|------|---------|
| **Organization Owner** | Full org authority; entitlement owner |
| **Organization Administrator** | Day-to-day membership and configuration |
| **Operations Lead** | Daily operations; create, assign, close investigations |
| **Analyst / Investigator** | Assigned case work; evidence and assessment |
| **Compliance Officer** | Compliance workflows and compliance-oriented cases |
| **Reporter** | Generate and schedule organizational reports |
| **Viewer** | Read-only org intelligence and non-restricted investigations |

### 7.2 Enterprise-only roles

| Role | Summary |
|------|---------|
| **Integration Administrator** | API and integration lifecycle |
| **Security Administrator** | Retention, audit export, security policy |

### 7.3 Platform roles

| Role | Summary |
|------|---------|
| **Platform Administrator** | Public scope, publication, platform policy |
| **Platform Support** | Audited read-only diagnostic access — no investigation decisions |

Organizations **MAY** use custom role labels mapping to these permission sets.

---

## 8. Permissions

Permissions are **atomic actions**. Roles bundle permissions. Edition gates whether a
permission can exist at all.

### 8.1 Permission catalog

| Permission | Description |
|------------|-------------|
| `intelligence:view_public` | View public-scope derived intelligence |
| `intelligence:view_org` | View organization's private intelligence scope |
| `intelligence:view_community_bounded` | View Community bounded personal intelligence |
| `monitoring:view` | View observation intake for entitled scope |
| `command_center:view` | View Command Center for entitled scope |
| `historical:view` | View Historical Analysis for entitled scope |
| `investigation:create` | Open investigation case |
| `investigation:view` | View investigation cases per visibility policy |
| `investigation:edit_assigned` | Edit assigned investigations |
| `investigation:edit_any` | Edit any open org investigation |
| `investigation:assign` | Assign or reassign investigations |
| `investigation:decide` | Record human decision outcome (INV-13) |
| `investigation:close` | Close investigation with complete audit |
| `report:generate_personal` | Community manual personal report |
| `report:generate_org` | Generate private organizational report |
| `report:schedule` | Configure scheduled report delivery |
| `report:export_audit` | Enterprise audit-grade export |
| `compliance:view` | View Compliance module |
| `compliance:configure` | Configure compliance overlays and templates |
| `notification:configure` | Configure notification routing |
| `automation:configure` | Configure scheduled intelligence and automation |
| `admin:manage_members` | Invite, remove, assign roles |
| `admin:configure_org` | Geography, sources, overlays, category visibility |
| `admin:configure_enterprise` | Retention, audit export, security policy |
| `integration:manage` | API keys and integration configuration |
| `api:access` | Programmatic API use |
| `observation:submit_personal` | Community limited observation intake |
| `observation:configure_sources` | Configure organizational ingestion sources |
| `platform:publish_public` | Publish or retire public intelligence/report scope |

### 8.2 Role-to-permission mapping (summary)

| Permission | Viewer | Analyst | Reporter | Compliance | Ops Lead | Org Admin | Owner | Integration Admin | Security Admin |
|------------|--------|---------|----------|------------|----------|-----------|-------|-------------------|----------------|
| `intelligence:view_org` | ● | ● | ● | ● | ● | ● | ● | ● | ● |
| `investigation:create` | ○ | ◐ | ○ | ● | ● | ● | ● | ○ | ○ |
| `investigation:edit_assigned` | ○ | ● | ○ | ● | ● | ● | ● | ○ | ○ |
| `investigation:assign` | ○ | ○ | ○ | ◐ | ● | ● | ● | ○ | ○ |
| `investigation:decide` | ○ | ◐ | ○ | ● | ● | ● | ● | ○ | ○ |
| `report:generate_org` | ○ | ○ | ● | ● | ● | ● | ● | ○ | ○ |
| `report:schedule` | ○ | ○ | ● | ○ | ○ | ● | ● | ○ | ○ |
| `compliance:configure` | ○ | ○ | ○ | ● | ○ | ● | ● | ○ | ○ |
| `admin:manage_members` | ○ | ○ | ○ | ○ | ○ | ● | ● | ○ | ○ |
| `admin:configure_org` | ○ | ○ | ○ | ○ | ○ | ● | ● | ○ | ○ |
| `integration:manage` | ○ | ○ | ○ | ○ | ○ | ◐ | ● | ● | ○ |
| `api:access` | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ● | ○ |
| `admin:configure_enterprise` | ○ | ○ | ○ | ○ | ○ | ◐ | ● | ○ | ● |

● granted · ◐ policy-dependent or delegated · ○ not granted

---

## 9. Resource Ownership

| Resource | Owner | Who may access |
|----------|-------|----------------|
| **Public intelligence** | Platform | Everyone (view); Platform Admin configures scope |
| **Open public reports** | Platform | Everyone (view); Platform Admin publishes |
| **Public maps** | Platform | Everyone (view) |
| **Community personal workspace** | Individual user | User only |
| **Community personal annotations** | Individual user | User only; not investigations |
| **Private organizational intelligence views** | Organization | Org members by role and scope |
| **Intelligence Events (derived)** | Platform engine; visibility by public/org policy | Read-only for all actors; lifecycle owned by reconciliation only |
| **Investigations** | Organization | Org members by role; assignee edits assigned cases |
| **Investigation audit timelines** | Organization | Append-only; org-access controlled |
| **Private organizational reports** | Organization | Org members by role |
| **Personal Community reports** | Individual user | User only |
| **API credentials** | Organization (Enterprise) | Integration Administrator |
| **Compliance configuration** | Organization | Compliance Officer, Administrators |

**Rule:** Private organizational resources **MUST NOT** enter the public layer without
**Platform Administrator** publication under explicit platform policy.

---

## 10. Visibility Rules

Effective access **SHALL** be computed as:

```
ALLOW if (
  actor edition entitles capability
  AND (if org action) user is member of organization in context
  AND user role grants permission
  AND resource is within org geographic/category scope
  AND (if multi-tenant) tenant boundary matches organization tenant
)
```

### 10.1 Intelligence visibility by actor

| Actor | Public intelligence | Community bounded | Org private intelligence |
|-------|---------------------|-------------------|--------------------------|
| Anonymous public | View | No | No |
| Community user | View | View (one geography) | No |
| Professional org member | View | Personal workspace if also Community user | View by role |
| Enterprise org member | View | Personal workspace if also Community user | View by role |
| Platform Administrator | View + configure public scope | No by default | No without audited break-glass |

### 10.2 Investigation visibility

Open investigations **SHALL** default to **organization-wide visibility** unless org
policy restricts to assignment-based visibility. Closed investigations **MAY** be restricted
to Administrator, Compliance, and assigned roles per policy.

---

## 11. Investigation Permissions

Aligned with `INVESTIGATION_FRAMEWORK.md` and INV-13.

### 11.1 By actor class

| Actor | Create | Edit | Assign | Decide / close |
|-------|--------|------|--------|----------------|
| Anonymous public | No | No | No | No |
| Community user | No | No | No | No |
| Professional org — Viewer | No | No | No | No |
| Professional org — Analyst | Policy | Assigned | No | If granted |
| Professional org — Operations Lead | Yes | Any open | Yes | Yes |
| Professional org — Compliance Officer | Yes (compliance) | Compliance cases | Within compliance | Yes (compliance) |
| Professional org — Administrator | Yes | Any open | Yes | Yes |
| Enterprise org | Same as Professional + Enterprise policy extensions | Same | Same | Same |
| Platform Administrator | **No** | **No** | **No** | **No** |

Creating or editing an investigation **MUST NOT** mutate linked Intelligence Event lifecycle.

### 11.2 Investigation ownership

Investigations **SHALL** be **owned by the organization** that created them. Individual
members act through roles; assignees **SHALL NOT** personal-own cases outside the org.

---

## 12. Reporting Permissions

### 12.1 By actor class

| Actor | Generate personal report | Generate org private report | Schedule org reports | Publish to public layer |
|-------|-------------------------|----------------------------|----------------------|-------------------------|
| Anonymous public | No | No | No | No |
| Community user | Yes (core, bounded) | No | No | No |
| Professional org — Reporter+ | Yes (if Community user) | Yes | Yes | **No** |
| Enterprise org — Reporter+ | Yes (if Community user) | Yes + audit export | Yes | **No** |
| Platform Administrator | No | No | No | **Yes** (platform open reports only) |

**Publish publicly** means adding content to the **platform public catalog**. Exporting
an organizational report to external stakeholders **SHALL NOT** be treated as public
publication unless Platform Administrator explicitly publishes it.

### 12.2 Report ownership

| Report type | Owner |
|-------------|-------|
| Open public report snapshots | Platform |
| Community personal manual reports | Individual user |
| Private organizational reports | Organization |
| Scheduled report deliveries | Organization (recipients configured by org) |
| Enterprise audit export packages | Organization |

Report generation **MUST NOT** mutate intelligence or investigation state (ADR-011).

---

## 13. Administration Permissions

### 13.1 By actor class

| Actor | Org administration | Enterprise administration | Platform administration |
|-------|-------------------|---------------------------|-------------------------|
| Anonymous public | No | No | No |
| Community user | No | No | No |
| Professional org — Administrator | Yes | No | No |
| Professional org — Owner | Yes | No | No |
| Enterprise org — Security Admin | No | Yes (security/audit policy) | No |
| Enterprise org — Integration Admin | No | Yes (integrations/API) | No |
| Enterprise org — Administrator / Owner | Yes | Yes (combined) | No |
| Platform Administrator | No | No | Yes |

### 13.2 Administration actions (organizational)

Organization Administrators and Owners **MAY**: manage members and roles; configure
geography, sources, overlays, notifications, report schedules, and Compliance (with
Compliance Officer co-configuration per policy). They **MUST NOT** publish public content
or access other organizations.

---

## 14. API Access Policy

| Actor | API use | Manage credentials |
|-------|---------|-------------------|
| Anonymous public | No | No |
| Community user | No | No |
| Professional organization | **No** | No |
| Enterprise organization | Yes (Integration Admin / service principals) | Integration Administrator, Owner |
| Platform Administrator | No customer API on behalf of orgs without audit | Platform-internal only |

API credentials **SHALL** be scoped to organization tenant, entitled geographies and
categories, and granted permissions. Default API scope **SHALL** be **read-only
intelligence projections**. Autonomous investigation decision via API **SHALL** be
prohibited (INV-13).

---

## 15. Future Multi-Tenancy Alignment

Per ADR-010, multi-tenancy is **reserved but not implemented**. This model **SHALL**
activate without redesign:

| Concept | Today | Future (Enterprise multi-tenant) |
|---------|-------|----------------------------------|
| **Isolation boundary** | Organization | Organization = Tenant |
| **Intelligence identity** | `(incident_category, spatial_key)` | `(tenant, incident_category, spatial_key)` |
| **Membership / roles** | Unchanged | Unchanged — evaluated with tenant context |
| **Cross-tenant access** | N/A | Denied by default |
| **Public layer** | Platform-global | Unchanged — not tenant-owned |

Authorization **MUST NOT** rely on access-control-layer-only isolation (ADR-010).

---

## 16. Audit Requirements

### 16.1 Audited actions

Authentication events; membership and role changes; delegation grants; investigation
lifecycle actions; report generation and schedule changes; admin configuration changes;
API credential lifecycle; platform public publication; platform break-glass access;
sensitive authorization denials (SHOULD).

### 16.2 Audit access

| Actor | May view |
|-------|----------|
| Organization Owner / Administrator | Organization audit logs |
| Security Administrator | Enterprise security and export audit logs |
| Platform Administrator | Platform audit logs; org logs under support policy only |
| Analyst / Viewer | Investigation timeline on permitted cases — not global admin audit |

Investigation audit timelines **SHALL** remain append-only (INVESTIGATION_FRAMEWORK).

---

## 17. Security Principles

| ID | Principle |
|----|-----------|
| **SP-1** | Fail closed when entitlement or scope is uncertain. |
| **SP-2** | No intelligence lifecycle mutation via any authorization grant (INV-1). |
| **SP-3** | Human conclusions quarantined to `investigation:decide` human actors (INV-13). |
| **SP-4** | Public/private separation on downgrade and export (EDITION_STRATEGY §10). |
| **SP-5** | Read paths do not trigger reconciliation (ADR-011). |
| **SP-6** | Cross-tenant access denied by default when multi-tenancy is active. |
| **SP-7** | Edition downgrade revokes org permissions; public access retained. |
| **SP-8** | Forest ecosystem product scope only. |

---

## Appendix A — Actor Comparison Matrix

| Dimension | Anonymous public | Community user | Professional org | Enterprise org | Platform Admin |
|-----------|------------------|----------------|------------------|----------------|----------------|
| **View public intelligence** | Yes | Yes | Yes | Yes | Yes |
| **View org private intelligence** | No | No | By role | By role | Break-glass only |
| **Create investigations** | No | No | By role | By role | No |
| **Edit investigations** | No | No | By role | By role | No |
| **Generate private org reports** | No | Personal only | By role | By role | No |
| **Publish public reports** | No | No | No | No | Yes |
| **Use APIs** | No | No | No | Yes | Platform-internal |
| **Org administration** | No | No | Admin roles | Admin + Enterprise roles | No |
| **Collaboration** | No | No | Yes | Yes | No |
| **Own public intelligence** | No (platform) | No (platform) | No (platform) | No (platform) | Platform operator |
| **Own private intelligence views** | No | Personal bounded | Organization | Organization | No |
| **Own investigations** | No | No | Organization | Organization | No |
| **Own reports** | No | Personal | Organization | Organization | Public catalog only |

---

## Document Control

| Field | Value |
|-------|-------|
| Created | 2026-07-17 |
| Updated | 2026-07-22 |
| Status | Pending review |
| Related business | `EDITION_STRATEGY.md`, `GO_TO_MARKET_STRATEGY.md`, `PRODUCT_STRATEGY.md` |
| Related product | `PLATFORM_CAPABILITIES.md`, `INVESTIGATION_FRAMEWORK.md` |
| Related architecture | ADR-010, ADR-011; INV-1, INV-13 |
| Related governance | `DOCUMENT_HIERARCHY.md` |

---

*End of Access Control Model.*
