# Public site for the Registers of Interests dataset: research notes

Date: 2026-10-03 · Author: Fable planner · Companion to `SPEC.md` in this folder.
These are the measurements, the options weighed and the external facts the SPEC rests on.
Everything marked *verified* was checked on 2026-10-03; sources are at the end.

## 1. What exists today

| Piece | State (2026-10-03) |
|---|---|
| Dataset | `site/disclosures_v2.db` (31.9 MB SQLite, 50,936 items, 408 members, 995 statements, 11,542 entities) and `exports/kaggle/` (CSV 30.7 MB + README). Rebuilt by `python -m disclosures export --site site`. |
| Public site | GitHub Pages at `k-r-a-s-s.github.io/aus-govt-transparency/`: one hand-styled `index.html` (coverage table, cite, licence) and the DB file, deployed by `.github/workflows/pages.yml` on push to `main` touching `site/`. The only interactive path is a Datasette Lite link that loads the whole 32 MB DB into the browser via Pyodide. |
| Kaggle | `kevrass/australian-parliament-registers-of-interests`, public, CC BY 4.0. |
| Personal site | `k-r-a-s-s/kevinrassool.com`: static HTML/CSS in `site/`, posts built by `tools/build.py` (Python 3.11), hosted on **Cloudflare Workers static assets** (no Worker script) on the personal account, custom domains `kevinrassool.com` + `www`, deployed with `npm run deploy` using a `.env` token (DEPLOY.md). Design: Young Serif / Atkinson Hyperlegible Next / JetBrains Mono, tokens `--paper --ink --muted --rule --accent(#176b50) --yellow(#f2c42b)`, light and dark. |
| Sibling project | `k-r-a-s-s/zombie-trials` graph explorer (`plans/2026-10-03-graph-explorer/SPEC.md`, written today): Python builds a static site + a small esbuild TypeScript bundle, Workers static assets only, Worker `who-evidence-graph` on `evidence.kevinrassool.com`, `deploy.sh --preview|--production` with fail-closed gates, Playwright tests, blog draft on a `draft/…` branch. ADR-36 there rejected R2 + DuckDB for *that* dataset (1–3 GB, blobs that must not ship). |

Two facts matter for the move off Pages:

- **`documents.source_url` is NULL for every row in the DB.** Source URLs live only in
  `pdfs/manifest.csv` (995/995 statements have one); `export.py` joins them in via
  `manifest_urls()`. The web build must do the same. House 44th–47th URLs are direct
  `static.aph.gov.au/...pdf?rev=…&hash=…` links (deep-linkable with `#page=N`); 43rd URLs go
  through an APH committee redirector; 48th House URLs are the interests-register API
  (`/api/members/<id>/statement/48`, serves the PDF); Senate URLs are an Azure Front Door API
  that returns JSON, not a PDF.
- **The DB (31.9 MB) is over the 25 MiB static-asset file limit.** It cannot be a Workers static
  asset. gzip gets it to 8.6 MB, but Workers static assets serve a `.gz` file as
  `application/gzip` (no transparent decoding), so Datasette Lite and `sql.js-httpvfs` could not
  read it. The DB has to live somewhere that serves raw bytes with CORS and `Range`: R2.

## 2. Measurements (this container, `site/disclosures_v2.db`)

| Artefact | Raw | gzip -9 | xz (≈ brotli) |
|---|---|---|---|
| Whole DB | 31.90 MB | 8.59 MB | — |
| All 50,936 items, columnar JSON, dictionary-encoded ids (18 columns: member, chamber, parliament, section, subsection, owner, entity as printed, entity id, description, location, purpose, alteration, change type, lodged date, precision, page, confidence, document) | 7.54 MB | **1.41 MB** | 0.92 MB |
| Same, row-wise JSON | 13.39 MB | 1.64 MB | — |

Other counts that size the site:

| | n |
|---|---|
| Members | 408 (231 served in more than one parliament) |
| Entities | 11,542; 4,448 with ≥ 2 items; 1,282 held by ≥ 2 members; 7,037 singletons, untyped |
| Items without an entity | 8,684 (addresses, generic terms) |
| Statements / PDF pages | 995 / 15,943 |
| Biggest member by items | Jason Clare 811, Malcolm Turnbull 797, Paul Fletcher 633 |
| Avg / max description length | 56 / 1,717 chars |
| Items by owner | self 35,548 · spouse 13,903 · dependent child 1,276 · unknown 209 |
| Items by change | initial 30,170 · added 17,683 · removed 2,687 · varied 277 · unknown 119 |
| Confidence | high 43,908 · medium 6,937 · low 91 |

Conclusion: the whole item table fits in one ~1.4 MB compressed file, so **every filter and
chart can run in the browser from static files with no database server**. A page count of
roughly 400 member pages + 4,450 entity pages + 14 section pages + 7 parliament pages +
indexes is about 5,000 files, a quarter of the free-plan limit.

## 3. Cloudflare facts (verified 2026-10-03)

| Fact | Value | Why it matters |
|---|---|---|
| Workers static assets | 20,000 files per Worker version on Free (100,000 Paid), **25 MiB per file**; asset requests are free and unlimited; Worker *invocations* 100,000/day on Free | Site is static-only: zero cost, no quota exposure. The DB can't be an asset. |
| Workers Builds (Git integration) | Free, open beta; build image has Python 3.13 and Node 22/24; 20 GB disk | Could build on push; GitHub Actions is the alternative (the repo already runs Actions). |
| R2 | 10 GB storage, 1M Class A + 10M Class B ops per month free, **zero egress**; public access via a custom domain (the `r2.dev` subdomain is rate-limited and throttles with 429); CORS set per bucket (`wrangler r2 bucket cors set`); `Range` requests served | Home for the downloadable DB/CSV/Parquet and for Datasette Lite / `sql.js-httpvfs`. |
| Worker routes vs custom domains | A route on the same hostname takes precedence over a custom domain and over an **R2 custom domain**; more specific paths win | Give the R2 bucket its own hostname (`data.kevinrassool.com`), never a path under a Worker's hostname. |
| D1 | Free: 5M rows read/day, 100k rows written/day, 5 GB total, 500 MB per DB; since 2026-09-01 queries *fail* past the daily limit | Would work for a JSON API, but adds a Worker script, a sync step and a quota that fails closed. Not needed for v1. |
| Workers Analytics Engine | Free: 100k data points/day, 10k reads/day | Only usable from a Worker script; not applicable to a static-only Worker. |

## 4. Options weighed

### A. Static-first (recommended; this is the SPEC)
Python renders every page (overview, member, entity, section, parliament, about, data) and the
compact data bundle; a small bundled script adds the interactive explorer (filters, facets,
charts, CSV of the current selection, URL-encoded state). DB/CSV/Parquet downloads on R2 with
CORS, which also powers Datasette Lite and an in-page SQL console (`sql.js-httpvfs`, HTTP range
requests, fetches only the SQLite pages a query touches). No Worker script, no database service.
- For: zero running cost, nothing to keep alive, crawlable permalinks for every MP and entity
  (the SEO/shareability win the dataset lacks today), identical architecture to the zombie-trials
  explorer so the two sites share tooling, tests and deploy gates.
- Against: ad-hoc SQL depends on the browser (Datasette Lite is slow on first load; the SQL
  console needs the range-request DB); per-member JSON is pre-rendered, not queryable.

### B. Worker + D1 API
Import the DB into D1, expose `/api/items?...` (Hono), render member/entity pages on request.
- For: a real JSON API with arbitrary filters; one Worker.
- Against: 100k invocations/day and 5M row reads/day fail closed on the free plan; a crawler
  or a Reddit spike can take the site down for the day; a second copy of the data to sync on
  each refresh; more code to test. **Rejected for v1, kept as the documented path if an API is
  wanted later** (the static per-member/per-entity JSON covers most API uses).

### C. Keep GitHub Pages + add a Workers front
Rejected: the user wants off Pages; splitting hosting splits caching, CORS and deploys.

### D. Observable Framework / Astro / Evidence.dev
A data-app framework would give the explorer quickly, but adds a second build system to a
Python repo, a framework for ~8 page templates, and (Framework) a slowing release cadence.
Same reasoning as zombie-trials ADR-35. Rejected; Observable **Plot** (the charting library,
ISC licence, bundled locally) is kept for the interactive charts.

### E. DuckDB-WASM + Parquet
Great for ad-hoc analytics, but the dataset is 50k rows: plain JavaScript over the 1.4 MB
bundle does every filter in a few milliseconds, with no 2–5 MB WASM download and no
Firefox range-request bug. Parquet is still offered as a *download* format if `pyarrow` is
installed at build time.

## 5. What "open dataset sharing" can mean here (menu; the SPEC picks)

| Lever | In SPEC? | Notes |
|---|---|---|
| Permalink per member and per entity, with every item and its source page | Yes (B) | The feature journalists and Reddit readers actually want: "what does my MP hold" and "who holds CBA". |
| Interactive explorer: filters, facets, charts, shareable URL, CSV of selection | Yes (C) | Client-side. |
| Downloads: SQLite, CSV, CSV.gz, JSONL, Parquet (optional), with sha256 manifest and version folders | Yes (A/D) | On R2, `data.kevinrassool.com/interests/<version>/…` plus `latest/`. |
| Datasette Lite link | Yes (D) | Pointed at the R2 DB; CORS is the only requirement. |
| In-page SQL console (`sql.js-httpvfs`) with example queries | Yes, stretch (E) | Range requests against the R2 DB; no server. |
| Static JSON API (`/data/*.json`, `/members/<id>/items.json`, `/entities/<id>/items.json`) with a stable documented schema and CORS `*` | Yes (B/D) | Via `_headers`. |
| Field dictionary, method, accuracy numbers, limitations, licence, cite | Yes (B) | Already written for Kaggle; rendered from the same source. |
| schema.org `Dataset` JSON-LD (Google Dataset Search), `sitemap.xml`, Open Graph cards | Yes (B) | Name + description required; licence, distribution, identifier recommended. |
| Frictionless `datapackage.json` | Yes (D) | Cheap; machine-readable schema. |
| Change feed (`/changes.xml`, RSS) on each refresh | Yes (D) | Tells data users when the register moved. |
| Zenodo DOI via GitHub release | Owner step (runbook) | Footer and cite block show it once set. |
| Hugging Face dataset mirror; Croissant metadata | Open question | Low effort, extra audience; Kaggle already covers one audience. |
| Kaggle | Already live | README gets the new URL. |

## 6. Design constraints carried over

- Match kevinrassool.com: same fonts (self-hosted), same tokens, light and dark, 375 px first,
  16 px gutters, no horizontal scroll, plain English, no em dashes in copy.
- "Calm and typographic, not dashboard-y" (zombie-trials SPEC §7) still applies, but this site
  is data-first: tables and small charts are the content.
- Honest labels, as zombie-trials ADR-40: every item shows its extraction confidence and a link
  to the source page; every page says the House data is an LLM transcription with measured
  F1 0.987 and that readers should check the PDF; party is party at start of term; Senate is
  48th only; singleton entities are untyped.
- No third-party runtime requests, no cookies, no analytics in v1 (same as the sibling site).
- The build reads the DB and the manifest only; it never calls the network.

## 7. Sources

- Workers static assets limits and the 2025-09-02 increase: https://developers.cloudflare.com/workers/platform/limits/ · https://developers.cloudflare.com/changelog/2025-09-02-increased-static-asset-limits/ · https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/
- Workers pricing (asset requests free; 100k invocations/day Free): https://developers.cloudflare.com/workers/platform/pricing/
- Workers Builds and build image: https://developers.cloudflare.com/workers/ci-cd/builds/ · https://developers.cloudflare.com/workers/ci-cd/builds/git-integration/
- R2 limits, free tier, public buckets: https://developers.cloudflare.com/r2/platform/limits/ · https://developers.cloudflare.com/r2/ (llms-full) · https://nubbo.app/blog/cloudflare-r2-free-tier/
- Routes vs custom domains precedence: https://developers.cloudflare.com/workers/platform/routing/routes/ · https://dev.to/lucian_tudor_303e1e12b9e5/cloudflare-r2-custom-domain-returns-404-a-worker-wildcard-route-was-eating-it-1g35
- D1 limits and the 2026-09-01 enforcement: https://developers.cloudflare.com/d1/platform/limits/ · https://developers.cloudflare.com/changelog/post/2026-09-01-d1-free-tier-limit-enforcement/
- Workers Analytics Engine pricing: https://developers.cloudflare.com/analytics/analytics-engine/pricing/
- sql.js-httpvfs: https://github.com/phiresky/sql.js-httpvfs · https://recca0120.github.io/en/2026/03/07/sql-js-httpvfs-static-hosting/
- Google Dataset Search structured data: https://developers.google.com/search/docs/data-types/dataset
