# web/: browser code and browser tests for the public site

The site itself is built by Python (`python -m disclosures web build`, see
`docs/v2/web.md`). This folder holds the small amount of JavaScript the pages use as progressive
enhancement, and the Playwright tests that open the built pages in Chromium.

## Layout

| Path | What |
|---|---|
| `src/*.ts` | One browser entry per file. `index-search.ts`: the filter box on `/members/` and `/entities/`. Phase C adds the explorer. |
| `esbuild.mjs` | Bundles each `src/*.ts` into one minified ES module in `dist/` (no sourcemaps). |
| `dist/` | Build output (gitignored). `web build` copies `dist/*.js` into the site as `assets/<name>.<sha256-8>.js` and the pages reference them. Without `dist/` the pages still render; they just lack the enhancements. |
| `tests/` | Playwright tests (`*.spec.ts`) and `global-setup.ts`. |
| `playwright.config.ts` | Chromium only, 2 workers, list reporter. |
| `sites/` | Built sites for local checks (gitignored). |
| `.env.example` | Cloudflare credentials template for the deploy step (phase D). Copy to `.env`, never commit it. |

Pinned dev dependencies (exact versions, `package-lock.json` committed): `esbuild` 0.28.2,
`typescript` 7.0.2, `@playwright/test` 1.63.0, `axe-core` 4.13.0.

## Build and test

```
cd web
npm ci                      # or npm install the first time
npm run build               # esbuild: src/*.ts -> dist/*.js
npm run typecheck           # tsc --noEmit over src/
PYTHON=../.venv/bin/python npm test   # build, then Playwright
```

`npm test` runs `npm run build` and then `playwright test`. The global setup:

1. builds the mini site from the committed fixture (`tests/fixtures/web/mini.db` and
   `mini-manifest.csv`) with `python -m disclosures web build --mode preview` into a temp dir,
   with `SOURCE_DATE_EPOCH=0`;
2. serves it with `python -m http.server` on a free `127.0.0.1` port (stdlib, no extra
   dependency; it serves `index.html` for directory URLs, as the Workers
   `auto-trailing-slash` handling does for the pages tested);
3. passes the URL and directory to the tests as `SITE_URL` and `SITE_DIR`, and removes the
   temp dir afterwards.

Python is `$PYTHON` if set, else `<repo>/.venv/bin/python`, else `python3`; it needs Jinja2.
If Playwright asks for a newer browser build, run `npx playwright install chromium` once.

## What the browser tests check

| File | Acceptance criterion |
|---|---|
| `no-js.spec.ts` | AC-B6: with JavaScript disabled, `/`, a member, an entity and a section page show their numbers and tables; the index filter box stays hidden; `/explore/` shows its counts. |
| `requests.spec.ts` | AC-B9: every request on `/`, a member, an entity, `/explore/` and `/data/` is same-origin (the data host `data.kevinrassool.com` is allowed on `/data/` only); no cookies; fonts load from `/fonts/`. |
| `a11y.spec.ts` | AC-B10: axe-core, injected from `node_modules`, finds no serious or critical violations on `/`, a member page and `/explore/` in light and dark; at 375px no page type scrolls sideways. |
| `search.spec.ts` | The index filter narrows rows and restores them. |

No test touches the network.
