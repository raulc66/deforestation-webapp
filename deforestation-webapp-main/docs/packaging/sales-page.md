# Sales page

Public commercial landing page for the ForestWatch **source-code** product.

| Field | Value |
|-------|--------|
| Route | `/` (unauthenticated). Signed-in users are still redirected to `/dashboard`. |
| Demo | `/explore` (unchanged) |
| Component | `frontend/src/pages/SalesPage.jsx` |
| Config | `frontend/src/config/commercial.js` |

## Purpose

Sell the packaged engineering foundation to technical buyers: GIS developers,
consultancies, environmental-tech startups, agencies, research organizations,
and companies that want a geospatial intelligence head start.

## Positioning

Primary: **Build geospatial intelligence products without starting from zero.**

ForestWatch is a commercially licensed full-stack platform. Forest monitoring is
the **included reference implementation**, not the only architectural use.

Do not add, without verification:

- illegal logging detection / legal determinations
- AI satellite processing
- production-ready Stripe billing
- real-time global monitoring
- guaranteed live providers
- customer logos, testimonials, SLAs, usage statistics

## Pricing shown

| Tier | Price |
|------|--------|
| Developer | $349 |
| Commercial | $899 (Recommended) |
| Agency | $1,799 |
| Acquisition | Contact |

Checkout is **not** implemented. License CTAs read URLs from `COMMERCIAL` /
`REACT_APP_PURCHASE_*`. Empty values fall back to `#licenses`.

Lemon Squeezy: set `REACT_APP_PURCHASE_DEVELOPER_URL`,
`REACT_APP_PURCHASE_COMMERCIAL_URL`, `REACT_APP_PURCHASE_AGENCY_URL`, and
`REACT_APP_ACQUISITION_CONTACT_URL` in `frontend/.env` (see `.env.example`).
Rebuild the frontend after changing them (CRA inlines `REACT_APP_*` at build).

## Screenshots

No product screenshots are vendored in this repository. The Product section uses
labeled placeholders. To replace them:

1. Capture Command Center, Intelligence Map, Investigation, Alert management,
   and Monitored areas from a running demo (no fabricated UI).
2. Store assets under `frontend/src/assets/sales/` (or `frontend/public/sales/`).
3. Wire them in `frontend/src/components/sales/ProductShowcase.jsx` with alt text.
4. Keep NOTICE / third-party screenshot rights in mind (map tiles, etc.).

## Launch checklist

- [ ] Counsel has issued the license text referenced on the page
- [ ] Lemon Squeezy (or other) checkout URLs set and rebuilt
- [ ] Acquisition contact URL is a real mailbox or form
- [ ] Optional published docs URL (`REACT_APP_DOCS_URL`)
- [ ] Real product screenshots replace placeholders
- [ ] `/explore` demo still starts
- [ ] Frontend tests including `SalesPage.test.jsx` pass
