# Release checklist

## Always include

- `LICENSE`, `NOTICE`, `README.md`
- `backend/` source and **tests** (including Phase 0 goldens)
- `frontend/` source and tests
- `docs/` (architecture + packaging overlay + getting-started)
- `docker/`, `docker-compose.yml`
- `scripts/` (create_release)
- `backend/scripts/` (determinism harness)
- `RELEASE_MANIFEST.md`

## Never include

Listed in `scripts/release-exclusions.txt`:

- `.env`, `*.env` except `*.env.example`
- `.venv/`, `node_modules/`
- `test_reports/`, `memory/`
- runtime `reports/`
- Mongo data, `dist/`, `build/`, coverage
- `.gitconfig` (developer identity)
- IDE folders `.idea/`, `.vscode/`
- `.emergent/`, root `test_result.md`, empty root `tests/` (agent/scaffold leftovers)

## Create a zip (Windows)

From the package root:

```powershell
powershell -File scripts/create_release.ps1 -Version v1.0.0
```

The script copies the working tree (not a git archive) to `dist/forestwatch-geospatial-intelligence/`, applies `scripts/release-exclusions.txt`, and writes `dist/forestwatch-source-<version>.zip` plus an adjacent `.sha256` file. Without `-Version`, the filename uses a `yyyyMMdd` stamp. It does not rewrite git history or create a tag.

Ambiguous names such as `reports` are excluded only at the **package root**, so `backend/app/modules/reports` ships. `!.env.example` keeps example env files.

## Operator checks before a paying customer receives a build

- [ ] LICENSE draft reviewed by counsel (or marked draft)
- [ ] NOTICE verification complete
- [ ] No `.env` in the zip
- [ ] Offline pytest + frontend tests + Phase 0 recorded
- [ ] Goldens unchanged
- [ ] Stripe documented as optional/unvalidated
- [ ] `FORESTWATCH_ENV=production` documented for public hosts
