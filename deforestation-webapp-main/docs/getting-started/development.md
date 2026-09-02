# Native development

Use this when you are not using Docker Compose. Commands are those used by this repository.

Working directories: `backend/` and `frontend/` under the package root.

## Backend

Entry point: `backend/server.py` (`uvicorn server:app`).

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Health: `GET http://127.0.0.1:8000/api/health`

Routers are mounted under `/api` (auth, events, alerts, analytics, monitoring-areas, organizations, customer-alerts, billing, demo, trial, reports, investigations, modules, import, notifications, data-sources). See `docs/API_REFERENCE.md` (verify against `server.py` if you add routes).

The scheduler is asyncio in-process (`ENABLE_BACKGROUND_INGESTION`). This package does not include Celery or Redis.

## Frontend

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm start
```

`package.json` scripts: `start` → `craco start`, `build` → `craco build`, `test` → `craco test`. Lockfile: `package-lock.json` (npm). `packageManager` also names Yarn; this getting-started path uses **npm** because the lockfile is npm's.

`REACT_APP_BACKEND_URL` is read at webpack compile time. Restart `npm start` after changing it.

## CORS and cookies

`CORS_ORIGINS` must include the UI origin (`http://localhost:3000` in `.env.example`). Axios uses `withCredentials: true`. Cookies are `Secure` + `SameSite=None`.

## Demo and trial

Demo: `POST /api/demo/start` from Explore. Trial: register → `/trial/setup` → `POST /api/trial/start` as implemented in `trial_routes.py`. Do not convert the demo organization (`kind=demo`) — trial upgrades the user's personal org.

## Stripe

Leave `ENABLE_BILLING=false` in development. Do not add live keys to source control.
