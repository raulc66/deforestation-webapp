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
| Developer | $199 |
| Commercial | $399 (Recommended) |
| Agency | $699 |
| Acquisition | Contact |

Checkout is **not** implemented. License CTAs read URLs from `COMMERCIAL` /
`REACT_APP_PURCHASE_*`. Empty values fall back to `#licenses`.

Lemon Squeezy: set `REACT_APP_PURCHASE_DEVELOPER_URL`,
`REACT_APP_PURCHASE_COMMERCIAL_URL`, `REACT_APP_PURCHASE_AGENCY_URL`, and
`REACT_APP_ACQUISITION_CONTACT_URL` in `frontend/.env` (see `.env.example`).
Rebuild the frontend after changing them (CRA inlines `REACT_APP_*` at build).

## Screenshots

Product captures live in `frontend/public/sales/` and are served as `/sales/<file>.png`
in production builds (Create React App copies `public/` to the site root).

| Showcase section | File | Notes |
|------------------|------|--------|
| Command Center | `frontend/public/sales/forestwatch-command-center.png` | Active Intelligence queue and monitoring status |
| Intelligence Map | `frontend/public/sales/forestwatch-intelligence-map.png` | Monitored forests and geospatial overlays |
| Investigation | `frontend/public/sales/forestwatch-investigation.png` | Investigation open, with evidence and intelligence details |
| Alert management | `frontend/public/sales/forestwatch-alerts.png` | Demonstration alert policies and channel tabs |
| Product landing | `frontend/public/sales/forestwatch-sales-page.png` | Commercial sales-page hero |

The Product showcase is wired in `frontend/src/components/sales/ProductShowcase.jsx`.
There is no dedicated trial-workspace screenshot in the current set; do not
invent a placeholder for that surface.

To replace a screenshot in a later version:

1. Capture the running application (no fabricated UI).
2. Overwrite the matching file under `frontend/public/sales/` (keep the filename, or
   update `src`, `width`, `height`, `alt`, title, and caption in `ProductShowcase.jsx`
   together).
3. Preserve native aspect ratio in CSS (`object-fit: contain`; do not crop or stretch).
4. Keep NOTICE / third-party screenshot rights in mind (map tiles, etc.).

## Launch checklist

- [ ] Counsel has issued the license text referenced on the page
- [ ] Lemon Squeezy (or other) checkout URLs set and rebuilt
- [ ] Acquisition contact URL is a real mailbox or form
- [ ] Optional published docs URL (`REACT_APP_DOCS_URL`)
- [x] Real product screenshots replace placeholders (see Screenshots)
- [ ] `/explore` demo still starts
- [ ] Frontend tests including `SalesPage.test.jsx` pass
