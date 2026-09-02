# ForestWatch — Dependencies

External libraries from `backend/requirements.txt` and `frontend/package.json`.  
Usage verified by import analysis unless marked **listed only**.

---

## Backend Runtime

| Package | Version | Purpose | Verified Usage |
|---------|---------|---------|----------------|
| `fastapi` | 0.110.1 | HTTP API framework | `server.py`, all routes |
| `uvicorn` | 0.25.0 | ASGI server | Production/dev server |
| `motor` | 3.3.1 | Async MongoDB driver | `app/core/database.py` |
| `pymongo` | 4.5.0 | MongoDB BSON/types | Repositories |
| `pydantic` | ≥2.6.4 | Data validation/models | All models |
| `email-validator` | ≥2.2.0 | Email field validation | User registration |
| `python-dotenv` | ≥1.0.1 | `.env` loading | `server.py` |
| `pyjwt` | ≥2.10.1 | JWT tokens | `app/core/security.py` |
| `bcrypt` | 4.1.3 | Password hashing | `app/core/security.py` |
| `passlib` | ≥1.7.4 | Password utilities | Listed alongside bcrypt |
| `cryptography` | ≥42.0.8 | Crypto primitives | JWT/crypto dependency chain |
| `httpx` | ≥0.27.0 | Async HTTP client | FIRMS provider, webhooks |
| `requests` | ≥2.31.0 | Sync HTTP | FIRMS fallback paths |
| `python-multipart` | ≥0.0.9 | File upload parsing | CSV import |
| `reportlab` | ≥4.2.0 | PDF generation | `pdf_generator.py` |
| `tzdata` | ≥2024.2 | Timezone data | UTC datetime handling |

### Listed but no import found in backend code

| Package | Notes |
|---------|-------|
| `boto3` | **Listed only** — no S3/AWS usage verified |
| `requests-oauthlib` | **Listed only** |
| `python-jose` | **Listed only** — JWT handled by `pyjwt` |
| `pandas` | **Listed only** |
| `numpy` | **Listed only** |
| `jq` | **Listed only** |
| `typer` | **Listed only** — no CLI entry point verified |

---

## Backend Development / Testing

| Package | Purpose |
|---------|---------|
| `pytest` | Test runner |
| `black` | Code formatter |
| `isort` | Import sorter |
| `flake8` | Linter |
| `mypy` | Type checker |

---

## Frontend Runtime

| Package | Purpose | Verified Usage |
|---------|---------|----------------|
| `react`, `react-dom` | UI framework | All components |
| `react-scripts` | CRA build tooling | Via CRACO |
| `@craco/craco` | CRA config override | `craco.config.js`, scripts |
| `react-router-dom` | Client routing | `App.js`, pages |
| `axios` | HTTP client | `lib/api.js` |
| `leaflet`, `react-leaflet` | Maps | `MapPage`, `IntelligenceMap` |
| `leaflet.markercluster` | Map clustering | `IntelligenceMap` |
| `recharts` | Charts | Dashboard analytics components |
| `lucide-react` | Icons | Throughout UI |
| `sonner` | Toast notifications | `App.js` |
| `react-hook-form` | Form state | Login/register |
| `@hookform/resolvers` | Form validation bridge | Login/register |
| `zod` | Schema validation | Login/register |
| `tailwind-merge`, `clsx`, `class-variance-authority` | CSS utilities | shadcn components |
| `tailwindcss-animate` | Animation utilities | Tailwind config |
| `@radix-ui/react-*` (20 packages) | Headless UI | `components/ui/*` |
| `cmdk`, `vaul`, `input-otp`, `embla-carousel-react`, `react-resizable-panels`, `react-day-picker` | shadcn component deps | Subset of ui/ components |
| `next-themes` | Theme switching | Minimal/partial use |
| `cra-template` | CRA boilerplate artifact | Not functionally used |

### Listed but no import found in frontend src

| Package | Notes |
|---------|-------|
| `@tanstack/react-query` | Provider in `index.js` only — **no `useQuery`/`useMutation` in app code** |
| `swr` | **Listed only** |
| `framer-motion` | **Listed only** |
| `lodash` | **Listed only** |
| `dayjs` | **Listed only** |
| `date-fns` | **Listed only** |

---

## Frontend Development / Testing

| Package | Purpose |
|---------|---------|
| `@testing-library/react` | Component tests |
| `@testing-library/jest-dom` | DOM matchers |
| `@testing-library/user-event` | User interaction simulation |
| `@testing-library/dom` | DOM utilities |
| `eslint` + plugins | Linting (react, hooks, jsx-a11y, import) |
| `tailwindcss`, `postcss`, `autoprefixer` | CSS pipeline |
| `dotenv` | Env loading in CRACO config |
| `@babel/plugin-proposal-private-property-in-object` | CRA Babel compat |
| `@types/lodash` | Type definitions (lodash unused in src) |

---

## External Services (Not Python/NPM Packages)

| Service | Used By | Config |
|---------|---------|--------|
| MongoDB | All persistence | `MONGO_URL`, `DB_NAME` |
| NASA FIRMS API | `FIRMSProvider` | `FIRMS_API_KEY` |
| Open-Meteo API | `OpenMeteoProvider` | No key required |
| Discord Webhooks | `DiscordWebhookProvider` | `DISCORD_WEBHOOK_URL` |
| Generic HTTP Webhooks | `GenericWebhookProvider` | `GENERIC_WEBHOOK_URL` |

---

## Environment Variables

From `app/core/config.py`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `MONGO_URL` | required | MongoDB connection |
| `DB_NAME` | required | Database name |
| `JWT_SECRET` | required | Token signing |
| `FORESTWATCH_ENV` | `development` | `production` refuses known-insecure defaults |
| `ADMIN_EMAIL` | `admin@example.com` | Admin seed |
| `ADMIN_PASSWORD` | `admin123` | Admin seed |
| `FRONTEND_URL` | `http://localhost:3000` | CORS reference |
| `CORS_ORIGINS` | `*` | Allowed origins |
| `LOG_LEVEL` | `INFO` | Logging |
| `FIRMS_API_KEY` | empty | FIRMS API (mock when empty) |
| `FIRMS_POLL_INTERVAL_MINUTES` | `60` | Scheduler interval |
| `ENABLE_BACKGROUND_INGESTION` | `true` | Scheduler on/off |
| `ENABLE_NOTIFICATIONS` | `true` | Webhook notifications |
| `DISCORD_WEBHOOK_URL` | empty | Discord provider |
| `GENERIC_WEBHOOK_URL` | empty | Generic webhook provider |
| `WEATHER_CACHE_TTL_MINUTES` | `30` | Weather cache staleness |
| `WEATHER_PROVIDER` | `open_meteo` | Provider selection |
| `REPORTS_DIR` | `reports` | Report file storage |
| `ENABLE_SCHEDULED_REPORTS` | `true` | Scheduler report generation |

Frontend: `REACT_APP_BACKEND_URL` (used in `lib/api.js`)

---

## Dependency Management Notes

- Backend: `pip install -r requirements.txt`
- Frontend: npm/yarn per `package.json` (`packageManager: yarn@1.22.22`)
- Several backend requirements appear unused — consider audit before production deployment (documentation only; no changes made)
