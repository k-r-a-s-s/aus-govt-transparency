# BUILDLOG: public site build

Branch `build/2026-10-03-public-site` (from the plan branch, which is `main` + the SPEC commit).
One entry per phase: commands run, results, deviations from SPEC. Nothing here deploys or
pushes; owner steps are SPEC §6.

## Session setup (2026-10-03)

- Mac, project venv `.venv` (Python 3.11.9); `Jinja2==3.1.6` + `MarkupSafe==3.0.4` installed and
  pinned in `requirements.txt`. `pyarrow` not installed (Parquet output is optional per ADR-W6).
- Node v24.7.0, npm 11.5.1, wrangler 4.141.0 (global, via nvm). `actionlint` not installed.
- `npx wrangler whoami` from the blog repo (its `.env`) resolves to the personal account
  (`Kevin.rassool@gmail.com's Account`, id `d06d0928…`). The token has no R2 permission yet
  (runbook step 1). Nothing on the account was changed.
- `.gitignore`: `*.db` is ignored repo-wide, so `!tests/fixtures/web/mini.db` was added; build
  outputs under `web/sites/` are ignored.
- `zombie-trials` has only the explorer SPEC on disk (no `explorer/` code yet), so conventions
  are mirrored from its SPEC text, not copied code.
