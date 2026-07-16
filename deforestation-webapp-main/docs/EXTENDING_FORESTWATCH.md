# Extending ForestWatch

Developer guide for adding capabilities using **verified extension points only**.  
Do not modify core business logic when extending — register hooks and wire dependencies.

> **Canonical architecture:** The rules that make extension possible — domains are added
> by extension and configuration, never by modification of engine internals — are defined
> canonically in `docs/architecture/06-domain-plugin-architecture.md` and
> `docs/architecture/adr/ADR-005-domain-plugin-architecture.md`. The dependency rules
> that every extension must obey are in `docs/architecture/10-dependency-rules.md`. This
> document is the **as-built recipe guide**: it shows the concrete files, signatures, and
> steps for each extension point. For the authoritative onboarding model of a new
> ecosystem domain, follow the canonical plug-in architecture; the recipes below
> implement it.

### Extension point → canonical specification

| Extension recipe (below) | Canonical specification |
|--------------------------|-------------------------|
| 1. New Ingestion Provider | `06-domain-plugin-architecture.md` (Provider); `15` anti-corruption invariant in `01-architecture-principles.md` |
| 2. New Report Section | `07-reporting-and-command-center.md` |
| 3. New Notification Provider | `07-reporting-and-command-center.md`; `09-system-context.md` |
| 4. New Intelligence Domain | `06-domain-plugin-architecture.md` |
| 5. New Incident Category | `02-intelligence-engine.md`; `06-domain-plugin-architecture.md` |
| 6. New Threat Category | `02-intelligence-engine.md` |
| 7. New Dashboard Card | `07-reporting-and-command-center.md` |
| 8. New Analytics Endpoint | `10-dependency-rules.md` (Route/Service/Repository responsibilities) |
| 9. New Scheduler Task | `adr/ADR-007-scheduler-responsibilities.md` |
| 10. New Investigation Workflow Step | `02-intelligence-engine.md` |
| New Detector | `04-detector-framework.md`; `adr/ADR-009-detection-contract.md` |

---

## 1. New Ingestion Provider

### Verified extension point

Create a provider class following `FIRMSProvider` pattern:

**Reference:** `app/modules/ingestion/providers/firms.py`

**Shared pipeline:**
- `app/modules/ingestion/persist.py` — `persist_import_event()`
- `app/modules/ingestion/dedupe.py` — dedup key generation
- `app/modules/ingestion/validation.py` — row validation (for tabular sources)

### Steps

1. Create `app/modules/ingestion/providers/your_provider.py`
2. Implement `async def run(events_service, events_repo, source_id) -> dict` returning counts
3. Normalize records to `ForestEventCreate` with `metadata.ingestion` block (`app/core/ingestion/ingestion_metadata.py`)
4. Register a `DataSource` entry (seed or admin API)
5. Wire into scheduler or expose via import route

### Scheduler integration

Add a call in `SchedulerService._run_cycle()` after FIRMS step, or compose multiple providers in startup.

**Note:** `app/modules/ingestion/scheduler.py` is a scaffold registry only — the active scheduler is `app/services/scheduler_service.py`.

### Module registry

Update `app/modules/ingestion/__init__.py` → `module_info()` to reflect new capabilities.

---

## 2. New Report Section

### Verified extension point

**Registry:** `app/modules/reports/report_sections.py`

```python
from app.modules.reports.report_sections import register_report_section, ReportSectionSpec

async def _my_section(ctx):
    return await ctx.analytics.some_method()  # or any ctx service

register_report_section(ReportSectionSpec(
    key="my_section",
    description="Human-readable description",
    fetcher=_my_section,
    ecosystem_domain="forest_health",  # optional
))
```

### Context available (`ReportGatherContext`)

| Field | Service |
|-------|---------|
| `analytics` | `AnalyticsService` |
| `intel_svc` | `IntelligenceEventsService` |
| `risk_svc` | `RiskService` |
| `history_svc` | `HistoryService` |
| `notif_history_repo` | `NotificationHistoryRepository` |
| `runs_repo` | `IngestionRunsRepository` |
| `weather_svc` | `WeatherService` |
| `threat_svc` | `ThreatAssessmentService` |
| `investigation_svc` | `InvestigationService` |

### Steps

1. Register section via `register_report_section()` (call at module import time)
2. Add test in `tests/test_report_sections.py`
3. PDF/CSV/JSON exporters automatically include all registered sections in `gather_report_data()`

**Do not modify** `ReportService.gather_report_data()` core loop.

---

## 3. New Notification Provider

### Verified extension point

**File:** `app/services/intelligence_notification_service.py`

1. Subclass `NotificationProvider` (ABC)
2. Implement `name: str` and `async def send(payload: NotificationPayload) -> bool`
3. Register in `build_providers()`:

```python
def build_providers(discord_webhook_url="", generic_webhook_url="") -> list[NotificationProvider]:
    providers = []
    # ... existing providers ...
    providers.append(MyProvider(...))
    return providers
```

4. History is recorded automatically via `NotificationHistoryRepository.create_entry()`

### New trigger types

Add a method on `IntelligenceNotificationService`:

```python
async def notify_my_event(self, data: dict) -> None:
    payload = NotificationPayload(event_type="my_event", ...)
    await self._dispatch(payload)
```

Call from the appropriate service lifecycle method.

**Tests:** `tests/test_notifications.py`

---

## 4. New Intelligence Domain (Ecosystem)

### Verified extension point

**Enum:** `app/core/ecosystem/domains.py` → `EcosystemDomain`

1. Add enum member
2. Update `CommandCenterService._domain_catalog()` with a `DomainModuleStatus` entry
3. Optionally tag report sections with `ecosystem_domain=` in `ReportSectionSpec`

**Design doc:** `backend/app/core/ecosystem/ARCHITECTURE.md`

---

## 5. New Incident Category

### Verified extension point

**File:** `app/core/ecosystem/incident_categories.py`

1. Add member to `IncidentCategory` enum
2. Update mapping helpers (`from_event_type()`, `normalize()`, etc.) if needed
3. Update `app/core/ecosystem/threat_mapping.py` → `map_incident_to_threat()`
4. `IntelligenceEventsService` will normalize `incident_category` on create/read

**Tests:** `tests/test_ecosystem_incident_categories.py`

---

## 6. New Threat Category

### Verified extension point

**File:** `app/core/ecosystem/threat_categories.py`

1. Add member to `ThreatCategory` (and `ThreatOrigin` grouping if applicable)
2. Update `threat_mapping.py` incident → threat mapping
3. `ThreatAssessmentService.assess_from_intelligence_event()` picks up changes automatically

**Tests:** `tests/test_threat_categories.py`, `tests/test_threat_assessment_service.py`

---

## 7. New Dashboard Card

### Verified extension point (frontend)

1. Create component in `frontend/src/components/intelligence/YourCard.jsx`
2. Add API call in `frontend/src/api/analytics.js` (follow existing `fetchX()` pattern)
3. Import and render in `IntelligenceSection.jsx`
4. Add test in `frontend/src/components/intelligence/__tests__/YourCard.test.jsx`

**Patterns:**
- Mock `@/lib/api` and `@/api/analytics` in tests
- Use `data-testid` attributes for test selectors
- Mock child components that fetch independently

### Backend endpoint (if new data needed)

Add route in `analytics_routes.py` + service method + `deps.py` factory if new service dependency.

---

## 8. New Analytics Endpoint

### Verified extension point

1. Add method to appropriate service (`AnalyticsService` or dedicated service)
2. Add route handler in `analytics_routes.py`:

```python
@router.get("/intelligence/my-endpoint")
async def my_endpoint(
    _: UserPublic = Depends(get_current_user),
    svc: MyService = Depends(my_service_dep),
):
    return await svc.my_method()
```

3. Add `*_service_dep` in `deps.py` if new service
4. Add frontend `fetchMyEndpoint()` in `analytics.js`
5. Add backend test (service unit test + optional route test)

---

## 9. New Scheduler Task

### Verified extension point

**File:** `app/services/scheduler_service.py` → `_run_cycle()`

Add a best-effort step after existing steps:

```python
if self._my_svc is not None:
    try:
        await self._my_svc.do_work()
    except Exception:
        logger.exception("My task failed — continuing cycle")
```

Wire service in `server.py` startup and pass to `SchedulerService.__init__()`.

**Tests:** `tests/test_scheduler.py` — call `_run_cycle()` directly with mocks

**Do not use** `modules/ingestion/scheduler.py` — it has no runner.

---

## 10. New Investigation Workflow Step

### Verified extension points

**Timeline events:** append via `InvestigationService._append_timeline()` with a `TimelineEventType` enum value.

To add a new timeline event type:
1. Add to `TimelineEventType` in `app/models/investigation.py`
2. Call `_append_timeline()` from the appropriate service method
3. Update frontend `InvestigationTimeline.jsx` display if needed

**New service methods:** add to `investigation_service.py`, expose via `investigation_routes.py`.

**Notifications:** add trigger method on `IntelligenceNotificationService` and call from service.

**Report data:** extend `get_summary_report()` or register a new report section.

**Tests:** `tests/test_investigations.py`

---

## Extension Anti-Patterns (Avoid)

| Anti-pattern | Why |
|--------------|-----|
| Duplicating anomaly detection logic | Use `AnalyticsService.get_anomalies()` |
| Direct MongoDB access from routes | Use repository pattern |
| Modifying `ReportService` gather loop | Use `register_report_section()` |
| Using `modules/ingestion/scheduler.py` | Not wired — use `SchedulerService` |
| Assuming in-app notifications are displayed | No frontend UI verified |

---

## Wiring Checklist

When adding any backend extension:

- [ ] Service/repository in appropriate layer
- [ ] `deps.py` factory if needed by routes
- [ ] Route handler with `get_current_user` if protected
- [ ] MongoDB index in `server.py` startup if new collection
- [ ] Unit tests
- [ ] Frontend API client + component (if user-facing)
