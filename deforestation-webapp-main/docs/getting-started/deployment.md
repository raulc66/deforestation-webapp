# Deployment notes

This is not a complete operations runbook (`docs/operations/` is reserved and empty). It records **actual** production-relevant behavior so a licensee does not copy development defaults.

## Do not copy development settings

| Topic | Development | Production |
|-------|-------------|------------|
| `FORESTWATCH_ENV` | unset or `development` | `production` (or `prod`) |
| `JWT_SECRET` | example strings allowed | Unique, ≥32 characters; examples refused |
| `ADMIN_PASSWORD` | fallback `admin123` if unset | Unique; known examples refused |
| `CORS_ORIGINS` | may be `*` | Explicit origins; `*` refused |
| Cookies | `Secure` + `SameSite=None` | Requires HTTPS termination |
| Stripe | `ENABLE_BILLING=false` | Still optional; use your Stripe account if you enable it |
| MongoDB | local | Your hardened cluster; this app does not make Mongo optional |

If `FORESTWATCH_ENV=production` and a refused default is present, `get_settings()` raises `RuntimeError` and the API will not start.

## Process model

- API: `uvicorn server:app` (one process includes the asyncio scheduler).
- Frontend: static files from `npm run build` (Compose uses nginx) or `npm start` for development only.
- MongoDB: separate. Not replaced by another database in this package.

There is no Redis, Celery, or extra worker architecture.

## Reverse proxy

Put TLS in front of API and UI. Align `FRONTEND_URL`, `CORS_ORIGINS`, and `REACT_APP_BACKEND_URL` (rebuild the frontend after changing the API public URL).

## Scheduler and seed

Startup seeds admin, catalog data, demo events, and Romania intelligence. Romania seed is not fully idempotent across restarts (known limitation). Live providers stay mock/off unless you set keys and enable flags.

## Stripe

Do not enable billing as a prerequisite for install. Live validation of Stripe is **out of scope** for this package. See `docs/engineering/STRIPE_TEST_MODE_VALIDATION.md`.
