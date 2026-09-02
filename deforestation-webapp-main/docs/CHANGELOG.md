# Changelog

All notable changes to the ForestWatch project documentation and releases are recorded
in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] — 2026-09-02

Commercial source-code package for licensed download (`forestwatch-source-v1.0.0.zip`).
Forest monitoring remains the included reference implementation. `LICENSE` is a draft
pending counsel review.

## [Unreleased]

### Added

- Commercial packaging foundation: proprietary `LICENSE` draft, `NOTICE`, buyer
  `README.md`, `docs/getting-started/`, `docs/packaging/`, Docker Compose
  (`docker-compose.yml`), and `scripts/create_release.ps1`.
- `FORESTWATCH_ENV=production` fail-closed checks for known development JWT,
  admin password, and wildcard CORS (`backend/app/core/config.py`).
- Public commercial sales page at `/` (`frontend/src/pages/SalesPage.jsx`).
- `RELEASE_MANIFEST.md` and versioned source zip process (`scripts/create_release.ps1 -Version`).
- Architecture v1.0 canonical specification under `docs/architecture/` (`00`–`10`).
- Architecture Decision Records ADR-001 through ADR-011 under `docs/architecture/adr/`.
- Architecture version changelog at `docs/architecture/CHANGELOG.md`.
- Phase 0 engineering specification at
  `docs/engineering/PHASE-0-ENGINE-GENERALIZATION.md`.
- Phase 0 implementation backlog at
  `docs/engineering/PHASE-0-IMPLEMENTATION-BACKLOG.md`.
- Living project status document at `docs/PROJECT_STATE.md`.
- Release notes tracker at `docs/RELEASE_NOTES.md`.
- Historical documentation archive at `docs/archive/`.

### Changed

- Reorganized documentation: canonical architecture in `docs/architecture/`, execution
  status in `docs/PROJECT_STATE.md`, historical snapshots in `docs/archive/`.
- Reconciled as-built guides (`ARCHITECTURE.md`, `INTELLIGENCE_PIPELINE.md`,
  `EXTENDING_FORESTWATCH.md`) to reference canonical architecture without duplicating it.

### Archived

- Pre-audit project state snapshot moved to `docs/archive/PROJECT_STATE_v0.3.md`.
