# ForestWatch — Release Notes

User-visible releases of the ForestWatch platform.

Engineering milestone completion (Architecture Phases 0–3) is tracked separately in
`docs/PROJECT_STATE.md` and `docs/engineering/IMPLEMENTATION_PROTOCOL.md`. Engineering
milestones **MAY** coincide with a release but are not the same as release version numbers.

---

## Version 1.0.0 (2026-09-02)

**Status:** Commercial source-package release.

v1.0.0 is the ForestWatch **source-code product** for licensed download: multi-tenant
geospatial intelligence platform plus forest-monitoring reference implementation,
Docker Compose local stack, tests, and buyer documentation.

It is **not** a hosted SaaS subscription. Architecture Phase 3 as a future hosted
surface-layer launch is **not** claimed by this zip. Counsel has not issued a
final LICENSE; the draft in the package remains subject to legal review.

---

## Pre-1.0 engineering milestones (not hosted-SaaS releases)

The following engineering completions **do not** constitute Version 1.0.0. They **MAY**
be marked with git tags (`phase-<N>-complete`) per the Implementation Protocol but **SHOULD
NOT** be announced as product releases unless explicitly scoped:

| Engineering milestone | Architecture phase | Release implication |
|-----------------------|-------------------|---------------------|
| Oracle frozen | WP0 complete | None — test artifact only |
| Phase 0 complete | Engine Generalization | Internal/engineering only; wildfire behavior preserved |
| Phase 1 complete | Spatial Engine | Internal/engineering only |
| Phase 2 complete | First Human Activity Domain | May warrant a pre-release or beta if product decides |
| Phase 3 complete | Surface Layer | Separate from this source zip; not required to install v1.0.0 |
