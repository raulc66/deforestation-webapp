# Configuration

Values come from `backend/app/core/config.py` (`get_settings()`) and `frontend/.env` / `frontend/.env.example` (loaded by `frontend/craco.config.js` via dotenv). Backend `server.py` loads `backend/.env`.

Do not put real secrets in git. Examples below are **development only**.

`FORESTWATCH_ENV` defaults to `development`. When set to `production` or `prod`, startup **refuses** known development JWT examples, known development admin passwords, and wildcard/empty CORS. That does not change default local demo behavior.

Auth cookies are always `secure=True` and `samesite="none"` in `auth_routes.py` / `demo_routes.py`. Production needs HTTPS. Chrome may still accept them on `http://localhost`.

---

## Frontend

| Name | Required | Purpose | Dev example | Production | Secret? | External? |
|------|----------|---------|-------------|------------|---------|-----------|
| `REACT_APP_BACKEND_URL` | Yes for a working UI | Axios base; code uses ``${REACT_APP_BACKEND_URL}/api`` (`frontend/src/lib/api.js`) | `http://localhost:8000` | Public API origin, no trailing slash. **Baked in at `npm start` / `npm run build`.** | No | Calls your API |
| `ENABLE_HEALTH_CHECK` | No | Webpack health plugin (`craco.config.js`) | `false` | Leave false unless you use that plugin | No | No |
| `REACT_APP_PURCHASE_DEVELOPER_URL` | No | Sales-page Developer checkout URL (`frontend/src/config/commercial.js`) | unset → `#licenses` | Lemon Squeezy (or equivalent) checkout URL when issued | No | Store |
| `REACT_APP_PURCHASE_COMMERCIAL_URL` | No | Sales-page Commercial checkout URL | unset → `#licenses` | Same | No | Store |
| `REACT_APP_PURCHASE_AGENCY_URL` | No | Sales-page Agency checkout URL | unset → `#licenses` | Same | No | Store |
| `REACT_APP_ACQUISITION_CONTACT_URL` | No | Sales-page acquisition contact | unset → `#licenses` | Mailbox or form URL | No | Contact |
| `REACT_APP_DOCS_URL` | No | Sales-page documentation link | unset → `#architecture` | Published docs URL | No | No |

CRA default UI port is **3000** unless you set `PORT`.

---

## Backend — required

| Name | Purpose | Dev example | Production | Secret? |
|------|---------|-------------|------------|---------|
| `MONGO_URL` | MongoDB connection | `mongodb://localhost:27017` | Authenticated URI to your cluster | Yes if URI has credentials |
| `DB_NAME` | Database name | `forestwatch` | Your database | No |
| `JWT_SECRET` | HS256 signing | `change-me-to-a-long-random-secret` | Unique, ≥32 characters, not an example string | **Yes** |

Missing any of the three raises `KeyError` at import/startup (`os.environ["..."]`).

---

## Backend — deployment mode and admin

| Name | Default | Purpose | Production |
|------|---------|---------|------------|
| `FORESTWATCH_ENV` | `development` | `production` / `prod` enables fail-closed checks | Set `production` on public hosts |
| `ADMIN_EMAIL` | `admin@example.com` | Admin seed email | Unique operator mailbox |
| `ADMIN_PASSWORD` | `admin123` if unset | Admin seed password; **re-applied on startup** | Unique; not `admin123` or documented examples |
| `FRONTEND_URL` | `http://localhost:3000` | Frontend origin used in settings | Public UI origin |
| `CORS_ORIGINS` | `*` | Comma-separated origins; `*` enables any origin (`server.py`) | Explicit list, never `*` |
| `LOG_LEVEL` | `INFO` | Logging | `INFO` or `WARNING` |

JWT TTL (code defaults, not env): `access_token_minutes = 60 * 24`, `refresh_token_days = 7`, algorithm `HS256`.

---

## Backend — scheduler and notifications

| Name | Default | Purpose |
|------|---------|---------|
| `ENABLE_BACKGROUND_INGESTION` | `true` | In-process scheduler |
| `FIRMS_POLL_INTERVAL_MINUTES` | `60` | Scheduler interval |
| `RECONCILIATION_LOCK_LEASE_SECONDS` | `300` | Reconciliation lease |
| `ENABLE_NOTIFICATIONS` | `true` | Outbound notification switch |
| `DISCORD_WEBHOOK_URL` | empty | Optional Discord |
| `GENERIC_WEBHOOK_URL` | empty | Optional HTTP webhook |
| `ENABLE_SCHEDULED_REPORTS` | `true` | Scheduled PDF/reports |
| `REPORTS_DIR` | `reports` | Report file directory |

---

## Backend — providers (optional / gated)

| Name | Default | Purpose | Secret? | Live integration? |
|------|---------|---------|---------|-------------------|
| `FIRMS_API_KEY` | empty | NASA FIRMS. Empty → bundled mock | Yes if set | Yes when set |
| `WEATHER_PROVIDER` | `open_meteo` | Weather provider id | No | Open-Meteo HTTP |
| `WEATHER_CACHE_TTL_MINUTES` | `30` | Cache TTL | No | No |
| `CLMS_DATASET_PATH` | empty | Override CLMS/CORINE path | No | Local file |
| `CLMS_REFRESH_INTERVAL_DAYS` | `30` | CLMS refresh cadence | No | No |
| `ENABLE_EEA_AIR_QUALITY` | `false` | EEA AQ ingestion | — | Opt-in |
| `EEA_AQ_API_TOKEN` | empty | EEA token | Yes if set | Opt-in |
| `EEA_AQ_POLL_INTERVAL_MINUTES` | `60` | EEA poll | No | Opt-in |
| `EEA_AQ_QUERY_WINDOW_HOURS` | `24` | EEA window | No | Opt-in |
| `EEA_AQ_COUNTRIES` | empty | Country filter | No | Opt-in |
| `ENABLE_CEMS_RAPID_MAPPING` | `false` | Copernicus EMS | No | Opt-in |
| `ENABLE_EFFIS_WILDFIRE_CONTEXT` | `false` | EFFIS context | No | Opt-in |
| `ENABLE_EFFIS_LIVE` | `false` | EFFIS live WFS | No | Opt-in |
| `EFFIS_CONTEXT_WINDOW_DAYS` | `365` | EFFIS window | No | Opt-in |
| `ENABLE_FOREST_DISTURBANCE` | `false` | GFW alerts | — | Opt-in |
| `GFW_API_KEY` | empty | GFW key | Yes if set | Required for live GFW |
| `GFW_ALERT_LOOKBACK_DAYS` | `30` | GFW lookback | No | Opt-in |
| `FOREST_DISTURBANCE_WINDOW_DAYS` | `60` | Disturbance window | No | Opt-in |
| `GEOGRAPHIC_SCOPE` | `romania` | `romania` \| `europe` \| `all` | No | Filters intelligence geography |
| `ENABLE_INTELLIGENCE_PROVENANCE` | `false` | Provenance persistence | No | Off for Phase 0 default |
| `ENABLE_CROSS_SOURCE_CORRELATION` | `false` | Cross-source correlation | No | Off for Phase 0 default |
| `CORRELATION_SPATIAL_DISTANCE_KM` | `50` | Correlation distance | No | Opt-in |
| `CORRELATION_TEMPORAL_HOURS` | `72` | Correlation time | No | Opt-in |

---

## Backend — billing and trial

Billing is **off by default**. This package has **not** been validated against a live Stripe account.

| Name | Default | Purpose | Secret? |
|------|---------|---------|---------|
| `ENABLE_BILLING` | `false` | Use live Stripe gateway when true **and** a key is set | No |
| `STRIPE_SECRET_KEY` | empty | Stripe API key | **Yes** |
| `STRIPE_WEBHOOK_SECRET` | empty | Webhook signing secret | **Yes** |
| `STRIPE_API_VERSION` | pin in `stripe_api.py` / example `2026-07-29.dahlia` | API version pin | No |
| `STRIPE_WEBHOOK_TOLERANCE_SECONDS` | `300` | Signature tolerance | No |
| `BILLING_SUCCESS_URL` | empty (service has fallbacks) | Checkout return | No |
| `BILLING_CANCEL_URL` | empty | Checkout cancel | No |
| `BILLING_PORTAL_RETURN_URL` | empty | Portal return | No |
| `STRIPE_PRICE_FOUNDATION` / `_PROFESSIONAL` / `_ENTERPRISE` | empty | Stripe price ids. Empty → plans not `purchasable` | No |
| `PLAN_*_PRICE_LABEL` | empty | Display labels | No |
| `PLAN_*_AREA_LIMIT` | 1 / 10 / 100 | Catalog capacity | No |
| `PLAN_*_PURCHASABLE` | true / true / false | Catalog flags (still need price ids for checkout) | No |
| `TRIAL_DURATION_DAYS` | `14` | Authenticated trial length (not Stripe) | No |

When `ENABLE_BILLING=false`, `build_stripe_gateway` selects `FakeStripeGateway` and no request is sent to Stripe (`stripe_gateway.py`).

---

## Docker Compose environment

See `docker-compose.yml`. Defaults are development: Mongo on the Compose network (`mongodb://mongo:27017`), API published at `localhost:8000`, UI at `localhost:3000`, billing off, `FORESTWATCH_ENV=development`.
