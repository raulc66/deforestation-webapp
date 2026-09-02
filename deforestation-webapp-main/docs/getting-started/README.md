# Getting started

This guide is for a technically competent developer installing ForestWatch from source. It documents **actual** commands, ports, and routes in this repository.

**What you are installing:** a multi-tenant geospatial intelligence platform with a forest-monitoring reference application. Romania seed data and the interactive demo are the reference geography, not a hosted SaaS.

Related:

- [configuration.md](configuration.md) — environment variables
- [development.md](development.md) — native backend/frontend
- [verification.md](verification.md) — tests and smoke path
- [deployment.md](deployment.md) — production considerations (not a full operations runbook)

Packaging / license: [../packaging/README.md](../packaging/README.md)

---

## Prerequisites

| Dependency | Used for |
|------------|----------|
| Docker Engine + Compose v2 | Simplest full-stack path |
| Python 3.11+ (native path) | FastAPI backend (`backend/requirements.txt`) |
| Node.js 18+ and npm (native path) | Frontend (`frontend/package.json`, `package-lock.json`) |
| MongoDB 6/7 (native path) | Required persistence. This application does not run without MongoDB. |

The native Windows path used during runtime stabilization was:

```text
backend/.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000
cd frontend; npm start     # PORT defaults to 3000
```

---

## 1. Obtain the source

Clone or unzip the commercial distribution so that this file is at `docs/getting-started/README.md` (repository root contains `backend/`, `frontend/`, `docker-compose.yml`).

Do not copy real `.env` files from another machine into a release zip. Use `.env.example` only.

---

## 2. Path A — Docker Compose (recommended first install)

Requires a running Docker Engine. `docker compose config` validates this file; image builds need the daemon.

From the package root (the directory that contains `docker-compose.yml`, `backend/`, and `frontend/`):

```bash
docker compose up --build
```

Compose starts:

| Service | Image / build | Host port | Role |
|---------|----------------|-----------|------|
| `mongo` | `mongo:7` | none (internal) | MongoDB 7 |
| `backend` | `docker/backend.Dockerfile` | **8000** | `uvicorn server:app --host 0.0.0.0 --port 8000` |
| `frontend` | `docker/frontend.Dockerfile` | **3000** | nginx serving the CRA production build |

Browser:

- Commercial landing: http://localhost:3000/
- Interactive demo: http://localhost:3000/explore
- API health: http://localhost:8000/api/health → `{"status":"healthy"}`

The frontend build bakes `REACT_APP_BACKEND_URL=http://localhost:8000` so the **browser** calls the published API. CORS is set to `http://localhost:3000`. `FORESTWATCH_ENV=development`. `ENABLE_BILLING=false`.

Stop: `Ctrl+C`, then `docker compose down`. Data persists in the `forestwatch-mongo` volume until you `docker compose down -v`.

If Docker cannot be used, use Path B.

---

## 3. Path B — Native processes

### 3.1 MongoDB

Run MongoDB so `mongodb://localhost:27017` accepts connections. ForestWatch does not embed MongoDB.

### 3.2 Backend

```bash
cd backend
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

`server.py` loads `backend/.env` via `python-dotenv`. Required keys: `MONGO_URL`, `DB_NAME`, `JWT_SECRET`.

Startup seeds admin (from `ADMIN_EMAIL` / `ADMIN_PASSWORD`), data sources, demo forest events, Romania intelligence seed, then starts the in-process scheduler. `GET /api/health` does not wait on external providers.

### 3.3 Frontend

Second terminal:

```bash
cd frontend
```

Windows:

```powershell
Copy-Item .env.example .env
npm install
npm start
```

macOS / Linux:

```bash
cp .env.example .env
npm install
npm start
```

`npm start` runs `craco start` (`frontend/package.json`). CRA serves **http://localhost:3000**. `REACT_APP_BACKEND_URL` must be `http://localhost:8000` with no trailing slash (`frontend/.env.example`).

`ENABLE_HEALTH_CHECK` in the frontend `.env` is optional and defaults off (`frontend/craco.config.js`).

---

## 4. Use the application

1. Open http://localhost:3000/ (commercial landing for signed-out visitors) and http://localhost:3000/explore (interactive demo). Signed-in `/` still redirects to `/dashboard`.
2. **Demo:** "Start interactive demo" → `POST /api/demo/start` → Command Center at `/dashboard`. Demo uses reserved demo organization data (Romanian stands). Leave demo from the product UI when finished.
3. **Register:** `/register` → continues to `/trial/setup` (`RegisterPage.jsx`).
4. **Login:** `/login`. Session cookies: `access_token`, `refresh_token` (`HttpOnly`, `Secure`, `SameSite=None`).
5. **Organization:** personal org is bootstrapped on first use; switcher uses `X-Organization-Id`.
6. **Trial / AOI:** `/trial/setup` creates a monitoring area (bbox). Trial is not Stripe.
7. **Command Center:** `/dashboard`.
8. **Map:** organization intelligence overlay from Command Center; `/map` is the unscoped platform feed (not promoted in customer nav).
9. **Investigations:** `/investigations`.
10. **Alerts:** `/alerts` (policies, channels, history). Trial email-only constraints apply in code.
11. **Billing disabled:** `/billing` loads plan catalog; without Stripe price IDs, `purchasable` is false (`plan_catalog.py` `is_checkout_ready`) so checkout buttons are not offered. `ENABLE_BILLING=false` means no live Stripe account is used.

Unauthenticated calls to organization/trial/billing APIs return **401**.

---

## 5. Verify

See [verification.md](verification.md).
