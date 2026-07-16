# ForestWatch — Project Structure

**Root:** `deforestation-webapp-main/`  
**Verified:** 2026-07-07

---

## Top-Level Layout

```
deforestation-webapp-main/
├── backend/          # FastAPI application
├── frontend/         # React SPA
├── docs/             # Developer documentation (this directory)
└── ...
```

---

## Backend (`backend/`)

### Entry point
| Path | Role |
|------|------|
| `server.py` | FastAPI app, router composition, startup/shutdown, seeding, scheduler |

### `app/core/` — Infrastructure

| Path | Responsibility |
|------|----------------|
| `config.py` | `Settings` from environment variables |
| `database.py` | Motor MongoDB client (`get_db`, `close_db`) |
| `security.py` | Password hashing, JWT create/decode |
| `errors.py` | `AppError`, `AuthError`, `NotFoundError`, `ConflictError`, handlers |
| `logging_config.py` | Structured logging setup |
| `migrations.py` | Datetime migration, GeoJSON backfill |
| `ecosystem/` | Ecosystem intelligence domain models (see below) |
| `geography/` | Romania bbox, regions, country detection |
| `ingestion/` | Shared ingestion metadata helpers |

### `app/models/` — Domain models

| File | Models |
|------|--------|
| `base.py` | `BaseDocument`, `utcnow`, `PyObjectId` |
| `enums.py` | `Severity`, `EventType`, `EventStatus` |
| `geo.py` | `GeoJSONPoint` |
| `user.py` | User, auth request/response models |
| `forest_event.py` | `ForestEvent`, CRUD/public models |
| `data_source.py` | Data source models |
| `notification.py` | In-app notification models |
| `import_job.py` | CSV import job models |
| `intelligence_event.py` | `IntelligenceEvent` |
| `investigation.py` | Investigation + timeline models |

### `app/repositories/` — Persistence

One repository per collection (mostly):

| Repository | Collection |
|------------|------------|
| `UserRepository` | `users` |
| `DataSourceRepository` | `data_sources` |
| `ForestEventRepository` | `forest_events` |
| `NotificationRepository` | `notifications` |
| `ImportJobRepository` | `import_jobs` |
| `IngestionRunsRepository` | `ingestion_runs` |
| `NotificationHistoryRepository` | `notification_history` |
| `WeatherCacheRepository` | `weather_cache` |
| `InvestigationRepository` | `investigations` |
| `InvestigationTimelineRepository` | `investigation_timeline` |

Module-local repositories in `app/modules/analytics/` and `app/modules/reports/`.

### `app/services/` — Cross-cutting business logic

| Service | Role |
|---------|------|
| `auth_service.py` | Registration, login, token validation, admin seed |
| `forest_event_service.py` | Event CRUD, geo queries, demo seed |
| `data_source_service.py` | Source catalog CRUD + seed |
| `notification_service.py` | In-app user notifications |
| `alert_service.py` | Legacy alert adapter over forest events |
| `scheduler_service.py` | Background ingestion + intelligence cycle |
| `intelligence_notification_service.py` | Outbound webhook notifications |
| `weather_service.py` | Weather cache + refresh |
| `weather_provider.py` | `OpenMeteoProvider` |
| `gis_loader.py` | GeoJSON spatial index |
| `gis_land_cover_service.py` | Point-in-polygon land cover |
| `land_cover_service.py` | Backward-compatible facade |
| `romania_seed_service.py` | Deterministic Romania demo dataset |

### `app/api/` — HTTP routes (non-module)

| File | Prefix |
|------|--------|
| `auth_routes.py` | `/auth` |
| `data_source_routes.py` | `/data-sources` |
| `event_routes.py` | `/events` |
| `alert_routes.py` | `/alerts` |
| `notification_routes.py` | `/notifications` |
| `import_routes.py` | `/import` |
| `module_routes.py` | `/modules` |
| `deps.py` | FastAPI dependency factories |

### `app/modules/` — Feature packages

#### `analytics/` — Intelligence & analytics engine

| File | Role |
|------|------|
| `analytics_routes.py` | All `/api/analytics/*` endpoints |
| `analytics_service.py` | Aggregations, anomalies, baselines, alerts, land cover |
| `analytics_repository.py` | Mongo aggregations on forest_events |
| `intelligence_events_service.py` | Intel event reconcile, scoring, escalation |
| `intelligence_events_repository.py` | `intelligence_events` persistence |
| `history_service.py` | Daily/regional/hotspot/monthly history |
| `history_repository.py` | History queries |
| `risk_service.py` | Regional fire risk engine |
| `risk_repository.py` | `risk_history` snapshots |
| `threat_assessment_service.py` | Threat scoring from intel events |
| `command_center_service.py` | Ecosystem command center snapshot |
| `incident_aggregation.py` | Pluggable incident aggregators |
| `romania.py` | Shim re-exporting `core/geography/romania` |

#### `ingestion/` — Data ingestion

| File | Role |
|------|------|
| `providers/firms.py` | NASA FIRMS provider (**active**) |
| `csv_importer.py` | CSV upload pipeline |
| `persist.py` | Shared persist + dedupe path |
| `dedupe.py` | Dedup key generation |
| `validation.py` | CSV row validation |
| `scheduler.py` | **Scaffold only** — not the active scheduler |

#### `reports/` — Operational reporting

| File | Role |
|------|------|
| `report_routes.py` | Report CRUD + download |
| `report_service.py` | Generation orchestration |
| `report_repository.py` | `reports` collection |
| `report_models.py` | Pydantic models |
| `report_sections.py` | Pluggable section registry (15 sections) |
| `pdf_generator.py` | ReportLab PDF export |
| `csv_export.py`, `json_export.py` | Other formats |

#### `investigations/` — Investigation management

| File | Role |
|------|------|
| `investigation_routes.py` | Investigation REST API |
| `investigation_service.py` | Lifecycle, timeline, stats, notifications |

#### Placeholder modules (registry only)

| Module | Status |
|--------|--------|
| `scraping/` | `module_info()` placeholder — `planned` |
| `satellite/` | placeholder |
| `alerting/` | placeholder — email/SMS/Slack |
| `ai_predictions/` | placeholder |

### `app/data/` — Static data

| Path | Role |
|------|------|
| `gis/romania_corine_simplified.geojson` | CORINE land cover polygons |
| `romania_landcover.py` | Legacy bbox data (tests only) |

### `backend/tests/` — 36 test files (flat directory)

See test file listing in audit output. No `conftest.py` verified.

---

## Frontend (`frontend/`)

### Structure

```
frontend/src/
├── App.js                 # Routes
├── index.js               # React root + QueryClientProvider
├── context/AuthContext.jsx
├── lib/api.js             # Axios client
├── api/                   # Backend API wrappers
│   ├── analytics.js
│   ├── reports.js
│   └── investigations.js
├── pages/                 # Route-level pages
├── components/
│   ├── layout/            # AppLayout
│   ├── dashboard/         # Analytics charts
│   ├── intelligence/      # Command center UI
│   ├── investigations/    # Investigation widgets
│   ├── ui/                # shadcn/Radix primitives (46 files)
│   └── ProtectedRoute.jsx
├── constants/testIds/
└── test-utils/
```

### Pages

| Page | Route | API clients used |
|------|-------|------------------|
| `LoginPage` | `/login` | auth via `AuthContext` |
| `RegisterPage` | `/register` | auth via `AuthContext` |
| `DashboardPage` | `/dashboard` | `analytics.js` |
| `MapPage` | `/map` | legacy alerts (not intelligence map) |
| `ModulesPage` | `/modules` | `/api/modules` |
| `ReportsPage` | `/reports` | `reports.js` |
| `InvestigationsPage` | `/investigations`, `/investigations/:id` | `investigations.js` |

### Frontend tests — 16 test files (co-located `__tests__/`)

**Not tested (verified gap):** `MapPage`, `ModulesPage`, `LoginPage`, `RegisterPage`, most `ui/` primitives.

---

## Tests

| Area | Location | Count |
|------|----------|-------|
| Backend unit/integration | `backend/tests/` | 36 files |
| Frontend component/page | `frontend/src/**/__tests__/` | 16 files |

**Backend run command (verified):**
```bash
pytest tests/ --ignore=tests/backend_test.py --ignore=tests/test_analytics.py --ignore=tests/test_ingestion.py
```

**Frontend run command (verified):**
```bash
npx craco test --watchAll=false
```

---

## Documentation

| File | Status |
|------|--------|
| `docs/ARCHITECTURE.md` | Current (this audit) |
| `docs/DATABASE.md` | Current |
| `docs/API_REFERENCE.md` | Current |
| `docs/PROJECT_STRUCTURE.md` | Current |
| `docs/INTELLIGENCE_PIPELINE.md` | Current |
| `docs/EXTENDING_FORESTWATCH.md` | Current |
| `docs/DEPENDENCIES.md` | Current |
| `docs/PROJECT_STATE.md` | Pre-audit snapshot — may be stale |
| `docs/ROADMAP.md` | Pre-audit roadmap — may be stale |
| `backend/app/core/ecosystem/ARCHITECTURE.md` | Ecosystem module design notes |
