# 07 — Reporting and Command Center

## 1. Purpose

This document specifies the Reporting subsystem and the Command Center. Both are
read-only projections of platform state.

## 2. Read-Only Projection Rule

Reporting and the Command Center shall render intelligence. They shall not compute or
mutate intelligence. Neither subsystem shall invoke reconciliation.

## 3. Reporting Subsystem

### 3.1 Responsibility
The Reporting subsystem is responsible for composing point-in-time artifacts from
read-only projections and exporting them in supported formats.

### 3.2 Section Registry
Report content is composed from registered report sections. Each report section
declares its key, its data source, and an optional ecosystem domain association.

Adding a report section shall occur through registration. Report composition shall not
require modification to incorporate a new section.

### 3.3 Composition
The Reporting subsystem gathers section data through the registered sections. Section
fetching shall be isolated so that the failure of one section does not prevent
composition of the remainder.

### 3.4 Export Formats
The Reporting subsystem shall support export in PDF, CSV, and JSON. Export format
support shall be extensible without modifying report composition.

### 3.5 Scheduled Reports
The scheduler is responsible for triggering scheduled report generation. Report
generation logic resides in the Reporting subsystem. The scheduler shall invoke it and
shall contain no report composition logic.

## 4. Command Center

### 4.1 Responsibility
The Command Center provides a live operational projection of platform state. It
assembles domain status, incident aggregation, active intelligence counts, threat
summaries, and investigation statistics.

### 4.2 Domain Catalog
The Command Center presents a domain catalog describing the status of each ecosystem
domain. Domain status shall be supplied through configuration.

### 4.3 Generalized Aggregation
The Command Center consumes the generalized aggregation registry. The registry shall
merge the contributions of all registered aggregators generically. A new domain's
aggregation contribution shall appear without modification to the aggregation merge
logic.

### 4.4 Composition
The Command Center composes its snapshot from read-only projections of:

- Domain catalog status.
- Incident aggregation by category.
- Active intelligence counts by category.
- Threat distribution and origin summary.
- Investigation statistics.

## 5. Consistency

Reporting and the Command Center reflect the most recently reconciled intelligence
state. They shall not trigger reconciliation to obtain fresh state. Freshness is a
function of the scheduler cycle.

## 6. Invariants

1. Reporting and the Command Center are read-only projections.
2. Report sections and aggregators are added by registration.
3. Neither subsystem invokes reconciliation.
4. Domain representation is configuration, not modification.
