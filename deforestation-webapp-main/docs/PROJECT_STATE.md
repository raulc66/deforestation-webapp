# ForestWatch — Project State

**Last updated:** 2026-06-10  
**API version:** 0.3.0  
**Repository root:** `deforestation-webapp-main/`

---

## Executive summary

ForestWatch is a full-stack deforestation monitoring platform (React + FastAPI + MongoDB). The **MVP core platform is complete**: authentication, dashboard, interactive map, canonical `ForestEvent` domain, `DataSource` registry, geospatial queries, CSV ingestion, and analytics aggregations. Placeholder modules exist for scraping, satellite processing, alerting automation, and AI predictions.

External data providers (NASA FIRMS, Global Forest Watch, etc.) and the provider-based ingestion framework are **designed but not implemented**.

---

## Implemented functionality

### Authentication & users
- JWT auth with httpOnly cookies (`access_token`, `refresh_token`) and `Authorization: Bearer` fallback
- Register, login, logout, refresh, `/api/auth/me`
- bcrypt password hashing; admin user seeded on startup (`ADMIN_EMAIL` / `ADMIN_PASSWORD`)
- `ProtectedRoute` on all frontend app pages except login/register

### Domain model — ForestEvent (canonical)
- Collection: `forest_events`
- Fields: title, country, region, latitude/longitude, GeoJSON `location`, event_type, severity, affected_area_ha, confidence, source_id, detected_at, status, metadata
- Event types: `logging`, `wildfire`, `mining`, `agriculture`, `road_construction`, `urban_expansion`, `unknown`
- Severity: `low`, `medium`, `high`, `critical`
- Status: `open`, `investigating`, `resolved`
- 20 demo events seeded on empty database at startup

### DataSource registry
- Collection: `data_sources`
- Types: `csv`, `api`, `satellite`, `scraper`, `manual`
- CRUD at `/api/data-sources`; 6 demo sources seeded (GLAD-S2, Hansen CSV, MapBiomas, InfoAmazonia, Community Reports, Sentinel Hub NDVI)
- `ForestEvent.source_id` references real DataSource IDs; responses include joined `source_name`

### Geospatial
- GeoJSON `Point` on every event (`[longitude, latitude]` per RFC 7946)
- 2dsphere index on `forest_events.location`
- `GET /api/events/nearby` — `$nearSphere` radius search (meters)
- `GET /api/events/bbox` — bounding-box `$geoWithin`
- Idempotent startup backfill for legacy events missing `location`

### Events API (canonical)
- `GET/POST /api/events`, `GET/PATCH/DELETE /api/events/{id}`
- Filters: severity, event_type, country, status, source_id
- `GET /api/events/stats`, `/recent`, `/range`, `/event-types`
- Timezone-aware UTC datetimes (BSON + ISO-8601 `Z` responses)

### Legacy alerts adapter
- `GET /api/alerts`, `GET /api/alerts/stats` — thin adapter over `ForestEventService`
- Preserves legacy shape (`area_ha`, `location.{lat,lng}`, `source`) for unchanged dashboard/map clients

### Notifications
- Collection: `notifications`
- `GET /api/notifications`, `POST /api/notifications/{id}/read`
- Model references `forest_event_id` (alert-centric notifications planned for future)

### CSV ingestion (live)
- `POST /api/import/csv` — multipart upload, optional `source_id`
- `GET /api/import/status`, `GET /api/import/status/{job_id}`
- Synchronous processing: max 5 MB, 10,000 rows
- Per-row validation and error capture; job statuses: `completed`, `partial`, `failed`
- Imported events tagged in `metadata` (`import_job_id`, `imported_from`)

### Analytics (live)
- `GET /api/analytics/overview`
- `GET /api/analytics/countries`
- `GET /api/analytics/event-types` (7-entry zero-filled taxonomy)
- `GET /api/analytics/severity` (4-bucket zero-filled)
- `GET /api/analytics/trends` (day/week/month via `$dateTrunc`, default last 30 days)
- Pure MongoDB aggregation pipelines; no materialized views

### Module registry
- `GET /api/modules`, `GET /api/modules/{name}`
- **Active:** `ingestion` (CSV), `analytics`
- **Planned:** `scraping`, `satellite`, `alerting`, `ai_predictions`

### Operations & infrastructure
- Startup: MongoDB indexes, datetime migration, geo backfill, admin + demo seed
- Centralized config via `backend/.env` (`MONGO_URL`, `JWT_SECRET`, CORS, etc.)
- Global error handlers (`AppError`, validation, unhandled)
- Structured logging via `app/core/logging_config.py`

---

## Backend status

| Area | Status | Notes |
|------|--------|-------|
| Layered architecture | ✅ Complete | `core` → `models` → `repositories` → `services` → `api` → `modules` |
| Auth & security | ✅ Complete | JWT + bcrypt; cookies use `secure=True`, `samesite=none` |
| ForestEvent CRUD | ✅ Complete | Canonical write path for all ingestion |
| DataSource CRUD | ✅ Complete | Demo seed + FK integrity on startup |
| Geospatial queries | ✅ Complete | nearby + bbox + 2dsphere index |
| CSV ingestion | ✅ Complete | `CsvImporter` + `ImportJob` audit |
| Analytics | ✅ Complete | Repository + service + routes |
| Notifications | ✅ Basic | List + mark read; no dispatch pipeline |
| Scheduler | 🟡 Scaffold only | In-memory registry; no runner |
| NASA FIRMS | ⬜ Not started | MVP design documented |
| Provider framework | ⬜ Not started | Full design documented |
| Scraping / satellite / AI | ⬜ Placeholders | `module_info()` only |

**Entry point:** `backend/server.py`  
**Python deps:** `backend/requirements.txt`  
**Local env template:** `backend/.env.example`

---

## Frontend status

| Area | Status | Notes |
|------|--------|-------|
| Login / Register | ✅ Complete | Cookie-based auth via `AuthContext` |
| Dashboard | ✅ Complete | Uses legacy `/api/alerts` + `/api/alerts/stats` (not `/api/analytics`) |
| Map | ✅ Complete | Leaflet + OSM tiles; severity filters; legacy `/api/alerts` |
| Modules page | ✅ Complete | Lists backend module metadata from `/api/modules` |
| Analytics UI | ⬜ Not wired | Backend endpoints exist; no charts consuming them |
| CSV upload UI | ⬜ Not built | Import via API only |
| DataSource management UI | ⬜ Not built | API only |
| Automated tests | ⬜ None | No Jest/RTL test files in `frontend/src` |

**Stack:** React 19, CRA + Craco, Tailwind, Radix/shadcn UI components, react-leaflet, TanStack Query (provider wired in `index.js`), axios.

**Routes:** `/login`, `/register`, `/dashboard`, `/map`, `/modules`  
**Local env template:** `frontend/.env.example` (`REACT_APP_BACKEND_URL`)

---

## Test status

### Backend (pytest)

| Suite | File | Tests | Type |
|-------|------|-------|------|
| Core API | `tests/backend_test.py` | 85 | Integration (live HTTP) |
| Ingestion | `tests/test_ingestion.py` | 26 | Integration |
| Analytics | `tests/test_analytics.py` | 27 | Integration |
| **Total** | | **138** | |

**Last verified (CI / iteration 7):** 138 passing, 0 failing (~18.5s against deployed preview API).

**Local run requirements:**
- Running FastAPI server reachable at `REACT_APP_BACKEND_URL`
- Env var `REACT_APP_BACKEND_URL` set, or readable from `frontend/.env`
- MongoDB with seeded data (tests assume ~20 `forest_events`)

```bash
cd backend
# set REACT_APP_BACKEND_URL=http://localhost:8000
python -m pytest tests/ -v
```

**Note:** Tests are **integration tests**, not isolated unit tests. Collection fails if `REACT_APP_BACKEND_URL` is unset and no `frontend/.env` is found.

### Frontend
- Manual / agent smoke tests documented in `test_reports/iteration_*.json`
- No automated frontend test suite in the repository

### Test credentials (seeded)
- Email: `admin@forestwatch.io`
- Password: `ForestAdmin2026!`

---

## Known limitations

### Product & features
- Dashboard and map use **legacy `/api/alerts`**, not `/api/analytics` or `/api/events`
- No UI for CSV import, analytics charts, or DataSource administration
- No real-time external data feeds (FIRMS, GFW, satellite, scrapers)
- No scheduled ingestion; `scheduler.py` is a registry stub only
- No duplicate detection on CSV re-import (same row creates duplicate events)
- Notifications exist but no alerting/dispatch workflow
- Placeholder modules (`scraping`, `satellite`, `alerting`, `ai_predictions`) have no implementation

### API & security
- Auth cookies require `secure=True` + `samesite=none` — local HTTP dev may need browser exceptions or HTTPS proxy
- `GET /api/data-sources/types` and `GET /api/events/event-types` are **unauthenticated**
- `GET /api/modules/{name}` returns 200 with `not_found` payload instead of HTTP 404 for unknown modules
- No role-based access control (all authenticated users share same capabilities)
- No rate limiting on import or auth endpoints

### Ingestion
- CSV import is **synchronous** in the request thread (5 MB / 10k row caps)
- No idempotency keys for imported rows
- `ImportJob` schema is CSV-oriented (`filename` field reused for all run types)

### Analytics
- Aggregations computed on every request (no cache)
- Trend series does not zero-fill missing time buckets
- No per-`source_id` analytics breakdown

### Operations
- `README.md` at repo root is a stub
- Duplicate Python venvs may exist (`backend/.venv` and root `.venv`) — use `backend/.venv` for backend work
- Root `packageManager` field specifies Yarn but project uses `package-lock.json` / npm

### Documentation
- `memory/PRD.md` is a historical log; `docs/` is the canonical reference going forward

---

## Repository layout (summary)

```
deforestation-webapp-main/
├── backend/
│   ├── server.py              # FastAPI entrypoint
│   ├── app/                   # Application code
│   ├── tests/                 # pytest integration suites
│   ├── requirements.txt
│   ├── .env.example
│   └── .venv/                 # Python virtual environment
├── frontend/
│   ├── src/                   # React application
│   ├── package.json
│   ├── .env.example
│   └── node_modules/
├── docs/
│   ├── PROJECT_STATE.md       # this file
│   ├── ROADMAP.md
│   └── ARCHITECTURE.md
├── memory/PRD.md              # historical product log
└── test_reports/              # iteration test summaries
```

---

## Related documents

- [ROADMAP.md](./ROADMAP.md) — phased future work
- [ARCHITECTURE.md](./ARCHITECTURE.md) — system design, flows, and open decisions
