# ForestWatch

ForestWatch is a **source-available, commercially licensed, multi-tenant geospatial intelligence platform** with a **forest-monitoring reference implementation**.

It turns environmental observations into organization-scoped intelligence: ingestion, reconciliation, evidence, investigations, alerts, and a Command Center. The included forestry and Romania materials demonstrate that architecture. They are a reference vertical and a reference geography — not the definition of the platform.

This package is for **download, local installation, private deployment, and extension**. It is not a hosted ForestWatch SaaS subscription.

**License:** proprietary source-available draft — see [LICENSE](LICENSE) (for legal review). Third-party software and datasets remain under their own terms — see [NOTICE](NOTICE).

**Packaging (what is being sold):** [docs/packaging/](docs/packaging/README.md)  
**How the engine works:** [docs/architecture/](docs/architecture/00-platform-vision.md)  
**Install:** [docs/getting-started/](docs/getting-started/README.md)

---

## What is included

| Layer | What ships |
|-------|------------|
| Backend | FastAPI application (`backend/server.py`) |
| Frontend | React SPA (Create React App + CRACO) |
| Persistence | MongoDB (licensee-operated) |
| Auth | Registration, login, JWT cookies, admin seed |
| Organizations | Memberships, `X-Organization-Id`, organization isolation |
| AOIs | Forest monitoring areas |
| Ingestion | Provider registry; FIRMS (mock when unkeyed); opt-in EEA / CEMS / EFFIS / GFW |
| Observations | Forest events / domain observations |
| Intelligence | Reconciliation, intelligence events, detectors, anomaly evaluation |
| Evidence | Evidence summaries and optional provenance |
| Investigations | Cases and timeline |
| Alerts | Customer alert policies, channels, history |
| Entitlements | Plan/trial capacity enforcement |
| Demo | Interactive demo control plane (Romanian forest stands as the worked example) |
| Trial | Authenticated 14-day trial on the user's personal organization (not Stripe) |
| Billing | Optional Stripe module, **disabled by default**, **not validated against a live Stripe account in this package** |
| Tests | Backend pytest, frontend Jest, Phase 0 golden oracle, determinism harness |

Placeholder modules `ai_predictions`, `satellite`, `scraping`, and `alerting` exist as `STATUS = "planned"`. They are **not** implemented products.

---

## Platform, reference vertical, reference geography

| Layer | Meaning in this package |
|-------|-------------------------|
| **Platform** | Ingestion contracts, detectors, reconciliation, intelligence events, AOIs, organizations, Command Center, investigations, alerts, entitlements |
| **Reference vertical** | Forest ecosystem taxonomy, forest monitoring areas, forestry UI copy, FIRMS/GFW-oriented providers |
| **Reference geography** | Romania seed data, demo catalog (Harghita / Suceava / Maramureș), simplified CORINE-derived GeoJSON, default `GEOGRAPHIC_SCOPE=romania` |

Licensees can extend the platform to other geographies and (with engineering work) other domains. Those domains are **not** already implemented as complete products.

---

## What it is useful for

**Existing capability** supports private deployments of geospatial monitoring with a working forest-intelligence application: GIS and environmental startups, research groups, agencies, and companies that want a foundation rather than a greenfield build.

**Extension opportunity** (not claimed as finished product): other land-change verticals, additional providers, additional geographies, the licensee's own billing. See [docs/EXTENDING_FORESTWATCH.md](docs/EXTENDING_FORESTWATCH.md).

---

## What it is not

- Legal proof of illegal activity, or guaranteed illegal-logging detection
- A government-certified monitoring system
- A satellite image processing engine
- A live all-provider environmental data service
- A hosted SaaS subscription or production-hardened deployment for every environment
- An AI-powered everything platform

Observations, intelligence, and evidence are **not** a finding of illegal harvest.

---

## Provider status

| Provider | Default in this package |
|----------|-------------------------|
| NASA FIRMS | Always registered. Empty `FIRMS_API_KEY` uses the bundled mock dataset. Live data requires the licensee's key. |
| Open-Meteo | Used for weather enrichment. No key in this package. |
| EEA Air Quality | Off (`ENABLE_EEA_AIR_QUALITY=false`). Token optional depending on EEA access. |
| Copernicus EMS Rapid Mapping | Off (`ENABLE_CEMS_RAPID_MAPPING=false`). |
| EFFIS | Off (`ENABLE_EFFIS_WILDFIRE_CONTEXT` / `ENABLE_EFFIS_LIVE`). |
| GFW integrated alerts | Off (`ENABLE_FOREST_DISTURBANCE=false`). Live use requires `GFW_API_KEY`. |
| CLMS / CORINE | Bundled simplified Romania reference GeoJSON; not an official full CLC export. |

You must use **your own** credentials for any live provider. Attribution: [NOTICE](NOTICE).

---

## Stripe (optional, unvalidated)

- Billing code exists (`/api/billing/*`, frontend Billing page).
- **`ENABLE_BILLING` defaults to false.** No Stripe credentials are required to install or run the demo.
- With billing disabled, the catalog can still render; plans without Stripe price IDs are **not purchasable**, so checkout is unavailable rather than calling Stripe.
- This package **has not been validated against a live Stripe account**.
- If you enable billing, you must use **your** Stripe account and keys. See `docs/engineering/STRIPE_TEST_MODE_VALIDATION.md` (all live-validation checkboxes remain open).

Do not treat Stripe as a guaranteed production billing system.

---

## Quick start

**Simplest path:** Docker Compose (MongoDB + API + frontend).

```bash
docker compose up --build
```

Then open the commercial landing at [http://localhost:3000/](http://localhost:3000/) and the interactive demo at [http://localhost:3000/explore](http://localhost:3000/explore). API: [http://localhost:8000/api/health](http://localhost:8000/api/health).

**Native path** (MongoDB already running on `localhost:27017`):

```bash
# backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
copy .env.example .env          # Windows
# cp .env.example .env          # macOS / Linux
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

```bash
# frontend (second terminal)
cd frontend
copy .env.example .env          # Windows
# cp .env.example .env
npm install
npm start                       # http://localhost:3000
```

Full steps, demo walkthrough, tests, and production-safety notes: **[docs/getting-started/](docs/getting-started/README.md)**.

### Required environment (backend)

| Variable | Role |
|----------|------|
| `MONGO_URL` | MongoDB connection (required) |
| `DB_NAME` | Database name (required) |
| `JWT_SECRET` | Token signing secret (required) |

Copy `backend/.env.example`. Development defaults are **unsafe for production**. Set `FORESTWATCH_ENV=production` only with a unique JWT secret, unique admin password, and explicit `CORS_ORIGINS` — the process will **refuse to start** on known development defaults. See [docs/getting-started/configuration.md](docs/getting-started/configuration.md).

Frontend: `REACT_APP_BACKEND_URL` (default `http://localhost:8000`), baked in at `npm start` / `npm run build`.

---

## Tests

From `backend/` (MongoDB not required for the offline suite; `MONGO_URL`, `DB_NAME`, and `JWT_SECRET` must still be set because `get_settings()` reads them):

```bash
python -m pytest --ignore=tests/backend_test.py --ignore=tests/test_analytics.py --ignore=tests/test_ingestion.py
```

Phase 0 oracle (do not modify golden files):

```bash
python -m pytest tests/test_phase0_oracle_integrity.py tests/test_phase0_golden_outputs.py tests/test_phase0_fixture.py tests/test_wildfire_baseline_detector.py tests/test_romania_intelligence_seed.py
```

Determinism (PowerShell):

```bash
powershell -File scripts/determinism_check.ps1
```

Frontend:

```bash
cd frontend
# Windows PowerShell
$env:CI='true'; npx craco test --watchAll=false
```

Live HTTP tests (`backend_test.py`, `test_analytics.py`, `test_ingestion.py`) need a running backend. They are not part of the offline suite.

---

## Documentation map

| Need | Document |
|------|----------|
| What is being sold | [docs/packaging/](docs/packaging/README.md) |
| Architecture (frozen) | [docs/architecture/](docs/architecture/00-platform-vision.md) |
| Extension recipes | [docs/EXTENDING_FORESTWATCH.md](docs/EXTENDING_FORESTWATCH.md) |
| API surface | [docs/API_REFERENCE.md](docs/API_REFERENCE.md) |
| Configuration | [docs/getting-started/configuration.md](docs/getting-started/configuration.md) |
| Release exclusions | [docs/packaging/release-checklist.md](docs/packaging/release-checklist.md) |

`docs/business/` contains historical hosted-SaaS strategy drafts. They are **not** the current commercial definition of this source package.

---

## Security

Auth cookies are `HttpOnly`, `Secure`, and `SameSite=None` (`backend/app/api/auth_routes.py`). Production needs HTTPS. Development CORS must not be `*` in production (`FORESTWATCH_ENV=production` refuses that combination). Rotate `JWT_SECRET` and `ADMIN_PASSWORD` before any public exposure. Admin users are seeded on startup from environment variables.

---

## Support and license tiers

Developer, Commercial, Agency/Customization, and Exclusive Acquisition are described in [LICENSE](LICENSE) and [docs/packaging/license-model.md](docs/packaging/license-model.md). Counsel must review the draft before a sale.
