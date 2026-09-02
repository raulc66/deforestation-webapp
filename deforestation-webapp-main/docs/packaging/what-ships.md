# What ships

Classification matches the commercial packaging audit. Paths are relative to the package root.

## Core platform

Reusable engine and multi-tenant product surfaces:

- `backend/server.py` — FastAPI composition, startup, scheduler
- `backend/app/core/` — config, security, DB, ingestion contracts, geography policy, commercial types
- `backend/app/modules/ingestion/` — provider registry and adapters
- `backend/app/modules/analytics/` — reconciliation, detectors, intelligence events, Command Center
- `backend/app/modules/investigations/`, `backend/app/modules/reports/`
- `backend/app/api/` — HTTP routes including organizations, monitoring areas, alerts
- `backend/app/services/`, `backend/app/repositories/`, `backend/app/models/`
- `frontend/src/` — Command Center, map, investigations, alerts, auth, organization context

## ForestWatch reference domain

Forest semantics on the engine:

- Incident taxonomy (`illegal_logging`, deforestation, wildfire, …) in `backend/app/core/ecosystem/`
- Forest monitoring areas
- FIRMS and GFW-oriented providers
- Forestry-oriented UI copy

Do not strip this layer to “genericize” the product.

## Romania / reference data

- `backend/app/core/geography/romania.py`, default `GEOGRAPHIC_SCOPE=romania`
- `backend/app/services/romania_seed_service.py`
- `backend/app/core/demo/catalog.py` (Harghita / Suceava / Maramureș)
- `backend/app/data/gis/romania_corine_simplified.geojson` (simplified CLC-derived reference)

## Development / testing assets (included)

- `backend/tests/` including **Phase 0 goldens** (`tests/fixtures/golden/`, `ORACLE_MANIFEST.json`)
- `frontend/src/**/__tests__/`
- `backend/scripts/determinism_check.ps1`
- `RELEASE_MANIFEST.md`
- `docs/architecture/`, ADRs, `docs/EXTENDING_FORESTWATCH.md`

These are part of the commercial value. Do not omit them from a source license zip.

## Optional commercial / SaaS surfaces

- Demo control plane (`/api/demo`, demo UI)
- Trial (`/api/trial`, `/trial/setup`)
- Billing/Stripe (`ENABLE_BILLING=false` by default; unvalidated live Stripe)
- Entitlement and plan catalog

## Excluded from distribution

See [release-checklist.md](release-checklist.md) and `scripts/release-exclusions.txt`:

- `.env` and other local secrets
- `.venv/`, `node_modules/`
- `test_reports/`, `memory/`
- runtime `reports/` PDFs
- MongoDB data volumes
- build artifacts
- tracked developer `.gitconfig` (removed from the tree; ignore going forward)

Placeholder modules under `backend/app/modules/{ai_predictions,satellite,scraping,alerting}/` **remain in the tree** as planned stubs. Do not advertise them as features.
