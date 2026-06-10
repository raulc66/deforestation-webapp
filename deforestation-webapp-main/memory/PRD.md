# ForestWatch — Product Requirements

## Problem Statement
Build a scalable full-stack deforestation monitoring platform using React, FastAPI, and MongoDB.
Implement only: Authentication, Dashboard, Interactive map page, Database models, REST API
structure, Service layer architecture, Repository pattern, Configuration management, Logging,
Error handling. Do not implement satellite ingestion / scraping / ML / notifications / analytics
yet — create placeholder modules. Use clean architecture; every module independently extensible.

## User Choices (locked)
- Database: MongoDB
- Stack: React (JS) + FastAPI (Python)
- Auth: JWT (httpOnly cookies, bcrypt)
- Map: Leaflet + OpenStreetMap
- Sample data: seeded on startup

## User Personas
- **Conservation analyst** – signs in, scans alerts on the dashboard & live map.
- **Platform admin** – seeded `admin@forestwatch.io`; same surfaces today, will manage modules later.
- **Field reporter** – will submit/triage alerts once alerting module ships.

## Architecture
```
/app/backend/
  server.py
  app/
    core/         config, logging_config, database, security, errors
    models/       base, user, alert  (PyObjectId / BaseDocument)
    repositories/ base, user_repository, alert_repository
    services/     auth_service, alert_service
    api/          deps, auth_routes, alert_routes, module_routes
    modules/      ingestion, scraping, satellite, alerting, analytics, ai_predictions (placeholders)
/app/frontend/src/
  context/AuthContext.jsx
  components/layout/AppLayout.jsx, ProtectedRoute.jsx
  pages/LoginPage.jsx, RegisterPage.jsx, DashboardPage.jsx, MapPage.jsx, ModulesPage.jsx
  lib/api.js
```

## What's been implemented (2026-06-06)
- Backend: layered clean architecture (config → logging → db → repo → service → api),
  JWT auth (httpOnly cookies + Bearer fallback), bcrypt hashing, admin seeding,
  20 demo alerts seeded, MongoDB indexes, global error handlers, 6 placeholder modules,
  /api/auth (register/login/me/refresh/logout), /api/alerts, /api/alerts/stats,
  /api/modules, /api/modules/{name} (404 on miss), /api/health.
- Frontend: Login + Register, AuthContext + ProtectedRoute, Dashboard (4 KPIs, severity
  distribution bar, recent activity table, 6 roadmap-module cards), Live Map (Leaflet,
  CircleMarkers colored by severity, popups, severity filter), Modules page,
  glassmorphism map controls, organic earthy theme, Manrope/IBM Plex.
- Testing: 16/16 backend pytest passing, full E2E frontend flows passing.

## Refactor (2026-06-07) — ForestEvent canonical domain
- New `ForestEvent` model is the central domain: `id, title, country, region, latitude,
  longitude, event_type, severity, affected_area_ha, confidence, source_id, detected_at,
  status, metadata`. Event types: `logging, wildfire, mining, agriculture,
  road_construction, urban_expansion, unknown`.
- New `ForestEventRepository` (collection `forest_events`), `ForestEventService`,
  and `/api/events` routes (GET list with filters severity / event_type / country /
  status, GET /stats with by_severity + by_event_type, GET /event-types catalogue,
  GET/POST/PATCH/DELETE /events/{id}).
- Old `Alert` model retired → `Notification` model (collection `notifications`) that
  references `ForestEvent`. New `/api/notifications` GET + `/{id}/read`.
- Legacy `/api/alerts` + `/api/alerts/stats` kept as a thin adapter over
  ForestEventService — frontend dashboard/map unchanged.
- Old `alerts` collection auto-dropped on startup; `forest_events` seeded with 20 records.
- Testing: 28/28 backend pytest, frontend smoke passing.

## DataSource domain (2026-06-07)
- New `DataSource` model: `id, name, type, provider, status, created_at, updated_at`.
  Types: `csv, api, satellite, scraper, manual`. Statuses: `active, inactive, error, paused`.
- `DataSourceRepository` (collection `data_sources`, unique index on `name`),
  `DataSourceService` with idempotent demo seed of 6 sources (GLAD-S2, Hansen,
  MapBiomas, InfoAmazonia, Community Reports, Sentinel Hub NDVI).
- `/api/data-sources` REST routes (GET list with type+status filters, GET /types,
  POST, GET/PATCH/DELETE by id; 409 on duplicate name, 422 on invalid type).
- `ForestEvent.source_id` now references a real `DataSource` id (FK). ForestEvent
  responses include joined `source_name`. Startup re-seeds events if any reference
  stale source_ids (safe upgrade path).
- Legacy `/api/alerts` `source` field now exposes the human DataSource name.
- Testing: 40/40 backend pytest, frontend smoke passing.

## Datetime refactor (2026-06-07)
- All datetime fields are now timezone-aware UTC `datetime` objects across models,
  repositories, services, and API responses (Pydantic v2 emits ISO-8601 with `Z`).
- Motor client opened with `tz_aware=True`; `BaseDocument.to_mongo` uses
  `mode="python"` so BSON stores datetimes natively (enables proper sort + range).
- New `app/core/migrations.py::migrate_datetime_strings` runs idempotently on
  startup; migrated 41 legacy string fields (7 users + 14 data-sources + 20 events).
- New endpoints:
  - `GET /api/events/recent?days=7&limit=200` — events in the last N days
    (`days∈[1,365]`).
  - `GET /api/events/range?start=...&end=...&limit=500` — inclusive UTC range;
    400 + `invalid_range` when `start > end`.
- Route ordering preserved: `/event-types`, `/stats`, `/recent`, `/range` are
  declared BEFORE `/{event_id}`.
- Testing: 62/62 backend pytest, frontend smoke passing.

## Geospatial layer (2026-06-07)
- New `app/models/geo.py::GeoJSONPoint` (RFC 7946; coordinates in `[lng, lat]`
  with range validation) and `bbox_polygon` helper.
- `ForestEvent` now carries both flat `latitude`/`longitude` (back-compat for
  the untouched frontend) AND a canonical GeoJSON `location` field. Service
  `_sync_location()` keeps them in sync on every create / update.
- MongoDB **2dsphere index** on `forest_events.location` created at startup.
- Idempotent migration `backfill_geojson_location` backfilled the 20 existing
  events with their GeoJSON Point (zero updates on subsequent restarts).
- New endpoints:
  - `GET /api/events/nearby?latitude=&longitude=&radius=&limit=` — `$nearSphere`
    with `$maxDistance` (meters, default 50 km, capped at 20,000 km); results
    sorted by distance ASC.
  - `GET /api/events/bbox?min_lat=&min_lng=&max_lat=&max_lng=&limit=` — `$geoWithin`
    polygon; 400 + `invalid_bbox` when min > max; sorted by detected_at DESC.
- Architecture ready for clustering / geospatial analytics: the `location` field
  is already in canonical GeoJSON form and indexed for `$geoNear` aggregations.
- Testing: 85/85 backend pytest, frontend smoke (20 markers, dashboard rows) passing.

## Ingestion module (2026-06-07)
- New `app/modules/ingestion/` package: `validation.py` (header + per-field
  parsers with bounds), `csv_importer.py` (synchronous CSV → ForestEvent
  pipeline with per-row error capture, 5 MB / 10k-row caps, UTF-8 BOM support),
  `scheduler.py` (in-memory registry scaffold for future scheduled pulls).
- `ImportJob` model (collection `import_jobs`) tracks every run: status
  (`pending → running → {completed | partial | failed}`), total/success/error
  counts, per-row errors with field+message+raw, duration_ms, triggered_by_user.
- New endpoints:
  - `POST /api/import/csv` — multipart upload (`file` + optional `source_id`
    Form). Required columns: title, country, region, latitude, longitude,
    event_type, severity, affected_area_ha. Optional: confidence (default 0.8),
    detected_at (default now). Defaults to first DataSource with `type='csv'`.
  - `GET /api/import/status?limit=20` — recent jobs (newest first).
  - `GET /api/import/status/{job_id}` — single job with full per-row errors.
- Imported events carry `metadata.import_job_id` + `metadata.imported_from`
  for audit + cleanup. File-level errors use `field='__file__'` for grouping.
- Module info: `/api/modules/ingestion` now reports `status='active'` with
  `capabilities.csv_import='live'` and `capabilities.scheduled_jobs='planned'`.
- Testing: 111/111 backend pytest (85 carried + 26 new ingestion tests covering
  happy path, defaults, source resolution, every validation rule, BOM, 413,
  non-UTF-8, status endpoints, route-ordering, auth, smoke). Frontend untouched.

## Analytics module (2026-06-07)
- New `app/modules/analytics/` package: `analytics_repository.py` (pure
  MongoDB pipelines using `$group`, `$cond`, `$avg`, `$dateTrunc` with UTC
  timezone), `analytics_service.py` (shapes raw aggregations into frontend
  JSON; zero-fills the 7-entry event_type taxonomy and the 4-entry severity
  set so chart axes are stable), `analytics_routes.py`.
- New endpoints (all auth-required):
  - `GET /api/analytics/overview` → `total_events`, `total_area_affected`,
    `open_events`, `resolved_events`, `investigating_events`,
    `average_confidence`.
  - `GET /api/analytics/countries` → array of `{country, event_count,
    affected_area_ha}` sorted by `event_count` DESC.
  - `GET /api/analytics/event-types` → 7-entry zero-filled taxonomy with
    `{event_type, event_count, affected_area_ha}`.
  - `GET /api/analytics/severity` → object keyed by `low / medium / high /
    critical` with `{count, area_ha}` each.
  - `GET /api/analytics/trends?start_date&end_date&interval=day|week|month` →
    `{interval, start_date, end_date, series: [{bucket, event_count,
    affected_area_ha}, ...]}` sorted ASC. Defaults to last 30 days when
    `start_date`/`end_date` are omitted. 400 + `invalid_interval` for unknown
    intervals; 400 + `invalid_range` when start > end.
- Module info: `/api/modules/analytics` now reports `status='active'` with all
  5 capabilities `live`.
- Circular-import gotcha resolved: `analytics/__init__.py` does not eagerly
  import `analytics_routes`; `server.py` imports the router directly.
- Testing: 138/138 backend pytest (111 carried + 27 new analytics tests
  covering shape, ordering, taxonomy completeness, zero-filling, trend
  invariants across intervals, invalid interval/range, future-only range,
  both `Z`/`+00:00` formats, auth, module info, regression smoke). Frontend
  smoke 100% (dashboard 20 events, map 20 markers).







## Backlog (P0/P1/P2)
- P0: nothing pending — MVP scope is complete.
- P1: Implement first real module (e.g. satellite ingestion via STAC), per-user alert
  subscriptions, alert detail page with timeline.
- P2: Analytics rollups (daily/weekly), AI risk-score endpoint, public read-only widget,
  audit trail for admin actions.

## Next Action Items
1. Wire a first real module (satellite or scraping) behind the existing interface.
2. Add per-user roles & ACL on `/api/alerts`.
3. Add a public-facing share link for individual alerts.
