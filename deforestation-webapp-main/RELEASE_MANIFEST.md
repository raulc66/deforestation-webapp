# ForestWatch source release

| Field | Value |
|-------|--------|
| Product | ForestWatch Geospatial Intelligence Platform |
| Artifact | commercially licensed source-code package |
| Version | v1.0.0 |
| Date | 2026-09-02 |
| Archive name | `forestwatch-source-v1.0.0.zip` |

This file describes the zip a buyer receives. It does not replace [README.md](README.md) or [LICENSE](LICENSE).

## Contents

- FastAPI backend and React frontend source
- Multi-tenant organizations, AOIs, ingestion, intelligence, investigations, alerts
- Forest-monitoring reference implementation (Romania demo/seed as the worked geography)
- Docker Compose local stack (`docker-compose.yml`, `docker/`)
- Buyer docs: `docs/getting-started/`, `docs/packaging/`, architecture docs
- Automated tests, including the Phase 0 intelligence oracle
- `LICENSE` (draft), `NOTICE`

## Prerequisites

- Docker Engine + Compose v2, **or** Python 3.11+, Node.js 18+, and MongoDB 6/7
- Disk space for `npm ci` / `pip install` and a MongoDB volume

## Default local ports

| Surface | URL |
|---------|-----|
| Commercial landing | http://localhost:3000/ |
| Interactive demo | http://localhost:3000/explore |
| API health | http://localhost:8000/api/health |

Compose maps frontend host **3000** → nginx **80**, backend **8000**.

## Optional integrations (not required to install)

- NASA FIRMS live key (empty key uses bundled mock)
- Opt-in EEA / CEMS / EFFIS / GFW providers
- Stripe billing (`ENABLE_BILLING` defaults to false; not live-validated in this package)
- Sales-page checkout URLs (`REACT_APP_PURCHASE_*`) — placeholders until a store is configured

## Known limitations

- Hosting and provider accounts are not included
- Provider availability is not guaranteed
- Stripe must be independently validated before any production billing use
- No proprietary satellite-image processing pipeline
- Intelligence output is not a legal determination
- `LICENSE` is a draft pending counsel review
- Production public hosts need HTTPS (auth cookies are `Secure` + `SameSite=None`) and `FORESTWATCH_ENV=production`

## Documentation entry

Start at [README.md](README.md), then [docs/getting-started/README.md](docs/getting-started/README.md).

## Checksum

A SHA-256 file is published **beside** the zip (`forestwatch-source-v1.0.0.zip.sha256`), not inside it.

```powershell
Get-FileHash .\forestwatch-source-v1.0.0.zip -Algorithm SHA256
```

Compare the hex digest to the adjacent `.sha256` file.
