# Verification

Confirm the package runs and that the frozen oracle is intact. Do not modify files under `backend/tests/fixtures/golden/` or `ORACLE_MANIFEST.json`.

## Runtime smoke (manual)

With MongoDB + backend + frontend (Compose or native):

1. `GET /api/health` → `{"status":"healthy"}`
2. Browser http://localhost:3000/ (sales landing) and http://localhost:3000/explore (demo)
3. Start interactive demo → `/dashboard` (Command Center)
4. Register / login → `/trial/setup` → create an AOI → Command Center
5. Open investigations and alerts
6. Open `/billing` with `ENABLE_BILLING=false`: catalog can render; checkout is not purchasable without Stripe price IDs

Unauthenticated `/api/organizations` and `/api/billing/status` return 401.

## Backend offline suite

From `backend/`, with `MONGO_URL`, `DB_NAME`, and `JWT_SECRET` set (the settings object reads them even when tests do not open Mongo). PowerShell example:

```powershell
$env:MONGO_URL='mongodb://localhost:27017'
$env:DB_NAME='forestwatch_offline'
$env:JWT_SECRET='offline-regression-secret'
python -m pytest --ignore=tests/backend_test.py --ignore=tests/test_analytics.py --ignore=tests/test_ingestion.py
```

Those three ignored files are **live HTTP** tests against a running server.

## Phase 0 oracle

```powershell
python -m pytest tests/test_phase0_oracle_integrity.py tests/test_phase0_golden_outputs.py tests/test_phase0_fixture.py tests/test_wildfire_baseline_detector.py tests/test_romania_intelligence_seed.py
```

## Determinism

From `backend/`:

```powershell
powershell -File scripts/determinism_check.ps1
```

The script sets `MONGO_URL`, `DB_NAME`, and `JWT_SECRET` itself. Goldens must stay byte-identical.

## Frontend

From `frontend/`:

```powershell
$env:CI='true'
npx craco test --watchAll=false
```

## Production-safety unit tests

```powershell
python -m pytest tests/test_production_safety.py
```

These assert that `FORESTWATCH_ENV=production` rejects documented development defaults and that `development` still allows them.

## What tests do not prove

| Need | Tests |
|------|--------|
| MongoDB + running app | Manual smoke / Compose |
| Live backend HTTP | `backend_test.py`, `test_analytics.py`, `test_ingestion.py` |
| Live Stripe | None in this package (see Stripe runbook; checkboxes open) |
| Live FIRMS/GFW/EEA/EFFIS | Opt-in; not required for demo |
| SMTP | Not required for demo simulate / trial policy UI |
