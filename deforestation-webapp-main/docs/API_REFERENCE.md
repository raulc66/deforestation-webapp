# ForestWatch — API Reference

**Base URL:** `/api`  
**Auth:** Most endpoints require `get_current_user` — cookie `access_token` or `Authorization: Bearer <token>`  
**Verified route count:** 70 endpoints  
**Source:** Inspected route files registered in `backend/server.py`

Legend:
- **Auth:** Yes = requires authentication; No = public
- **Side effects:** MongoDB writes, file I/O, external HTTP, notifications

---

## Root

| Method | Path | Auth | Request | Response | Services | Side Effects |
|--------|------|------|---------|----------|----------|--------------|
| GET | `/api/` | No | — | `{service, version, status}` | — | None |
| GET | `/api/health` | No | — | `{status: healthy}` | — | None |

---

## Auth (`app/api/auth_routes.py`)

| Method | Path | Auth | Request Model | Response | Services | Repositories | Side Effects |
|--------|------|------|---------------|----------|----------|--------------|--------------|
| POST | `/api/auth/register` | No | `RegisterRequest` | `UserPublic` + cookies | `AuthService` | `UserRepository` | Insert user; set JWT cookies |
| POST | `/api/auth/login` | No | `LoginRequest` | User fields + `access_token` | `AuthService` | `UserRepository` | Set JWT cookies |
| POST | `/api/auth/logout` | No | — | `{ok: true}` | — | — | Clear cookies |
| GET | `/api/auth/me` | Yes | — | `UserPublic` | `AuthService` | `UserRepository` | None |
| POST | `/api/auth/refresh` | No | cookie `refresh_token` | `{ok: true}` | `AuthService` | `UserRepository` | Refresh access cookie |

---

## Data Sources (`app/api/data_source_routes.py`)

| Method | Path | Auth | Request | Response | Services | Side Effects |
|--------|------|------|---------|----------|----------|--------------|
| GET | `/api/data-sources/types` | No | — | `list[str]` | — | None |
| GET | `/api/data-sources` | Yes | Query: `type`, `status` | `list[DataSourcePublic]` | `DataSourceService` | None |
| POST | `/api/data-sources` | Yes | `DataSourceCreate` | `DataSourcePublic` | `DataSourceService` | Insert |
| GET | `/api/data-sources/{source_id}` | Yes | — | `DataSourcePublic` | `DataSourceService` | None |
| PATCH | `/api/data-sources/{source_id}` | Yes | `DataSourceUpdate` | `DataSourcePublic` | `DataSourceService` | Update |
| DELETE | `/api/data-sources/{source_id}` | Yes | — | 204 | `DataSourceService` | Delete |

---

## Events (`app/api/event_routes.py`)

| Method | Path | Auth | Request | Response | Services | Side Effects |
|--------|------|------|---------|----------|----------|--------------|
| GET | `/api/events/event-types` | No | — | event type list | — | None |
| GET | `/api/events/stats` | Yes | — | `dict` | `ForestEventService` | None |
| GET | `/api/events/recent` | Yes | Query: `days`, `limit` | `list[ForestEventPublic]` | `ForestEventService` | None |
| GET | `/api/events/range` | Yes | Query: `start`, `end`, `limit` | `list[ForestEventPublic]` | `ForestEventService` | None |
| GET | `/api/events/nearby` | Yes | Query: lat/lng/radius/limit | `list[ForestEventPublic]` | `ForestEventService` | None |
| GET | `/api/events/bbox` | Yes | Query: bbox/limit | `list[ForestEventPublic]` | `ForestEventService` | None |
| GET | `/api/events/map` | Yes | Query: `limit` | `{events: [...]}` | `ForestEventService` | None |
| GET | `/api/events` | Yes | Query filters | `list[ForestEventPublic]` | `ForestEventService` | None |
| POST | `/api/events` | Yes | `ForestEventCreate` | `ForestEventPublic` | `ForestEventService` | Insert + land cover classify |
| GET | `/api/events/{event_id}` | Yes | — | `ForestEventPublic` | `ForestEventService` | None |
| PATCH | `/api/events/{event_id}` | Yes | `ForestEventUpdate` | `ForestEventPublic` | `ForestEventService` | Update |
| DELETE | `/api/events/{event_id}` | Yes | — | 204 | `ForestEventService` | Delete |

---

## Alerts — Legacy (`app/api/alert_routes.py`)

| Method | Path | Auth | Response | Services | Side Effects |
|--------|------|------|----------|----------|--------------|
| GET | `/api/alerts` | Yes | legacy alert dict | `AlertService` | None |
| GET | `/api/alerts/stats` | Yes | `dict` | `AlertService` | None |

**Note:** `AlertService` adapts `ForestEventService` data. Used by frontend `MapPage.jsx`.

---

## In-App Notifications (`app/api/notification_routes.py`)

| Method | Path | Auth | Response | Services | Side Effects |
|--------|------|------|----------|----------|--------------|
| GET | `/api/notifications` | Yes | `list[NotificationPublic]` | `NotificationService` | None |
| POST | `/api/notifications/{id}/read` | Yes | `{ok: true}` | `NotificationService` | Mark read |

**Frontend consumer:** Not verified from implementation.

---

## CSV Import (`app/api/import_routes.py`)

| Method | Path | Auth | Request | Response | Services | Side Effects |
|--------|------|------|---------|----------|----------|--------------|
| POST | `/api/import/csv` | Yes | multipart: file + `source_id` | `ImportJobPublic` | `CsvImporter` | Insert events + import job |
| GET | `/api/import/status` | Yes | Query: `limit` | `list[ImportJobPublic]` | `CsvImporter` | None |
| GET | `/api/import/status/{job_id}` | Yes | — | `ImportJobPublic` | `CsvImporter` | None |

---

## Modules Registry (`app/api/module_routes.py`)

| Method | Path | Auth | Response | Side Effects |
|--------|------|------|----------|--------------|
| GET | `/api/modules` | No | list of `module_info()` | None |
| GET | `/api/modules/{name}` | No | module metadata or 404 | None |

**Registered modules:** ingestion, scraping, satellite, alerting, analytics, ai_predictions (several are placeholders — see `PROJECT_STRUCTURE.md`).

---

## Analytics (`app/modules/analytics/analytics_routes.py`)

### Core analytics

| Method | Path | Auth | Query | Services |
|--------|------|------|-------|----------|
| GET | `/api/analytics/overview` | Yes | — | `AnalyticsService.overview()` |
| GET | `/api/analytics/countries` | Yes | — | `AnalyticsService.by_country()` |
| GET | `/api/analytics/event-types` | Yes | — | `AnalyticsService.by_event_type()` |
| GET | `/api/analytics/severity` | Yes | — | `AnalyticsService.by_severity()` |
| GET | `/api/analytics/trends` | Yes | `start_date`, `end_date`, `interval` | `AnalyticsService.trends()` |
| GET | `/api/analytics/data-quality` | Yes | — | `AnalyticsService.data_quality()` |
| GET | `/api/analytics/sources` | Yes | — | `AnalyticsService.by_source()` |

### Intelligence endpoints

| Method | Path | Auth | Services / Repositories | Side Effects |
|--------|------|------|-------------------------|--------------|
| GET | `/api/analytics/intelligence/events/summary` | Yes | `IntelligenceEventsService.get_events_summary()` | None |
| GET | `/api/analytics/intelligence/events` | Yes | `AnalyticsService` + `IntelligenceEventsService.get_events()` | None |
| GET | `/api/analytics/intelligence/anomalies` | Yes | `AnalyticsService.get_anomalies()` | None |
| GET | `/api/analytics/intelligence/baselines` | Yes | `AnalyticsService.get_regional_baselines()` | None |
| GET | `/api/analytics/intelligence/temporal` | Yes | `AnalyticsService.get_temporal_intelligence()` | None |
| GET | `/api/analytics/intelligence/alerts` | Yes | `AnalyticsService.get_alerts()` | None |
| GET | `/api/analytics/intelligence/ingestion-status` | Yes | `IngestionRunsRepository` + `app.state.scheduler` | None |
| GET | `/api/analytics/intelligence/notifications` | Yes | `NotificationHistoryRepository` + `app.state.notification_svc` | None |
| GET | `/api/analytics/intelligence/land-cover` | Yes | `AnalyticsService.get_land_cover_distribution()` | None |
| GET | `/api/analytics/intelligence/history/daily` | Yes | `HistoryService.daily_activity()` | None |
| GET | `/api/analytics/intelligence/history/regions` | Yes | `HistoryService.regional_history()` | None |
| GET | `/api/analytics/intelligence/history/hotspots` | Yes | `HistoryService.hotspot_history()` | None |
| GET | `/api/analytics/intelligence/history/monthly` | Yes | `HistoryService.monthly_summary()` | None |
| GET | `/api/analytics/intelligence/risk` | Yes | `RiskService.get_risk()` | None |
| GET | `/api/analytics/intelligence/weather` | Yes | `WeatherService.get_current_weather()` | May fetch external API if cache stale |
| GET | `/api/analytics/intelligence/incidents` | Yes | `AnalyticsService.get_incident_aggregation()` | None |
| GET | `/api/analytics/intelligence/command-center` | Yes | `CommandCenterService.get_snapshot()` | None |
| GET | `/api/analytics/intelligence/threats` | Yes | `ThreatAssessmentService.get_threats()` | None |
| GET | `/api/analytics/intelligence/threat-summary` | Yes | `ThreatAssessmentService.get_threat_summary()` | None |

**Response models:** All return `dict` (JSON) — no unified Pydantic response wrapper verified for intelligence endpoints.

---

## Reports (`app/modules/reports/report_routes.py`)

| Method | Path | Auth | Request | Response | Services | Side Effects |
|--------|------|------|---------|----------|----------|--------------|
| GET | `/api/reports` | Yes | — | `{reports, total}` | `ReportService.list_reports()` | None |
| GET | `/api/reports/{report_id}` | Yes | — | report metadata `dict` | `ReportService.get_report()` | None |
| POST | `/api/reports/generate` | Yes | `GenerateReportRequest` | pending record (202) | `ReportService` + `BackgroundTasks` | Insert report; async file generation |
| DELETE | `/api/reports/{report_id}` | Yes | — | 204 | `ReportService.delete_report()` | Delete metadata + file |
| GET | `/api/reports/{report_id}/download` | Yes | — | `FileResponse` | `ReportService` | File read |

---

## Investigations (`app/modules/investigations/investigation_routes.py`)

| Method | Path | Auth | Request | Response | Services | Side Effects |
|--------|------|------|---------|----------|----------|--------------|
| GET | `/api/investigations` | Yes | Query: `status`, `priority`, `region`, `search` | `{investigations, total}` | `InvestigationService.list_investigations()` | None |
| GET | `/api/investigations/statistics` | Yes | — | stats `dict` | `InvestigationService.get_statistics()` | None |
| GET | `/api/investigations/{id}` | Yes | — | `{investigation, timeline}` | `InvestigationService.get_investigation()` | None |
| POST | `/api/investigations` | Yes | `InvestigationCreate` | investigation `dict` (201) | `InvestigationService.create()` | Insert investigation + timeline; notify |
| PATCH | `/api/investigations/{id}` | Yes | `InvestigationUpdate` | investigation `dict` | `InvestigationService.update()` | Update + timeline; notify on escalation |
| PATCH | `/api/investigations/{id}/assign` | Yes | `InvestigationAssign` | investigation `dict` | `InvestigationService.assign()` | Update + timeline; notify |
| PATCH | `/api/investigations/{id}/close` | Yes | `InvestigationClose` | investigation `dict` | `InvestigationService.close()` | Update + timeline; notify |
| DELETE | `/api/investigations/{id}` | Yes | — | 204 | `InvestigationService.archive()` | Soft archive |

**Error codes:** 404 `NotFoundError`, 409 `ConflictError` (duplicate intel event investigation)

---

## Authentication Summary

| Category | Endpoints |
|----------|-----------|
| **Public** | `/api/`, `/api/health`, auth register/login/logout/refresh, `/api/events/event-types`, `/api/data-sources/types`, `/api/modules/*` |
| **Protected** | All other endpoints listed above |

**Role-based authorization:** Not verified from implementation. All authenticated users share the same access level.

---

## Request/Response Model Index

| Model | File |
|-------|------|
| `RegisterRequest`, `LoginRequest`, `UserPublic` | `app/models/user.py` |
| `DataSourceCreate`, `DataSourceUpdate`, `DataSourcePublic` | `app/models/data_source.py` |
| `ForestEventCreate`, `ForestEventUpdate`, `ForestEventPublic` | `app/models/forest_event.py` |
| `NotificationPublic` | `app/models/notification.py` |
| `ImportJobPublic` | `app/models/import_job.py` |
| `GenerateReportRequest`, `ReportRecord` | `app/modules/reports/report_models.py` |
| `InvestigationCreate`, `InvestigationUpdate`, `InvestigationAssign`, `InvestigationClose` | `app/models/investigation.py` |

Intelligence/analytics endpoints return computed `dict` structures defined in service methods — no dedicated Pydantic response models verified.
