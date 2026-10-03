# Public site for the Registers of Interests dataset — SPEC

Status: DRAFT, awaiting Kevin's sign-off · Author: Fable planner · Date: 2026-10-03
Repo: `aus-govt-transparency` (branch for the build: `build/2026-10-03-public-site` from `main`)
Also touched: `k-r-a-s-s/kevinrassool.com` (one draft branch, never pushed by the build)
Owner / human-in-the-loop: Kevin · Research and measurements: `RESEARCH.md` beside this file

---

## 0. Read this first (cold-start context)

The dataset is finished and published (v2 SPEC signed off 2026-10-03, G4 done): 50,936 disclosed
interests of Australian federal MPs and senators, 43rd–48th House plus 48th Senate, in
`site/disclosures_v2.db` (31.9 MB SQLite) and on Kaggle. Its only public face is a one-page GitHub
Pages site with a coverage table and a Datasette Lite link that downloads the whole database into
the browser. There is no page per MP, no page per company, no chart, no filter, no API, no
machine-readable metadata, and the site shares nothing with Kevin's personal site.

This plan moves the public face off GitHub Pages onto Cloudflare Workers static assets on Kevin's
**personal** Cloudflare account (the same hosting as kevinrassool.com and the planned zombie-trials
explorer), as its own subdomain of kevinrassool.com, and makes the dataset browsable: a permalink
for every member and every standardised entity, an interactive explorer, charts, downloads in
several formats, a static JSON API, Datasette Lite and an in-page SQL console, and the metadata
that lets search engines and data catalogues find it.

### Facts the plan rests on (checked 2026-10-03, details in RESEARCH.md)

- The whole item table compresses to **1.4 MB** (gzip) as dictionary-encoded columnar JSON, so
  all filtering and charting can run in the browser from one static file. No server is needed.
- Workers static assets: 20,000 files per version and **25 MiB per file** on the free plan; asset
  requests are free and unlimited. The 31.9 MB DB cannot be a static asset. It goes on **R2**
  (10 GB, zero egress, CORS and `Range` supported) under its own hostname.
- A Worker route on a hostname takes precedence over a custom domain *and* over an R2 custom
  domain on that hostname. So: the site on `interests.kevinrassool.com`, the bucket on
  `data.kevinrassool.com`, nothing shared.
- `documents.source_url` is NULL in the DB; the source URLs are in `pdfs/manifest.csv`
  (995/995). House 44th–47th links are direct PDFs (deep-linkable with `#page=N`); 43rd links go
  through an APH redirector; 48th House links are the interests-register API (returns the PDF);
  Senate links return JSON.
- kevinrassool.com deploys with `wrangler` and a personal-account API token in a gitignored
  `.env` (its `DEPLOY.md`). The token there has no R2 permission yet.
- The zombie-trials graph explorer SPEC (same day) chose: Python builds the static site + small
  esbuild bundle, Workers static assets only, `deploy.sh --preview|--production` with fail-closed
  gates, Playwright tests, blog draft on a `draft/…` branch. This plan uses the same shape so the
  two sites share conventions.
- Wrangler in the planning container had no Cloudflare credentials; nothing here was deployed or
  inspected on the account. Every account-side step is in the runbook (§6) for Kevin.

---

## 1. PRD

### What we're building

`interests.kevinrassool.com`: a static site generated from `disclosures_v2.db` by a new
`python -m disclosures web` command, deployed as a Cloudflare Worker (static assets, no script),
with the downloadable data on an R2 bucket at `data.kevinrassool.com`. In scope:

1. **Pages with permalinks.** `/` overview; `/members/<member_id>/` for all 408 members;
   `/entities/<entity_id>/` for every entity with ≥ 2 items (≈ 4,450); `/sections/<1–14>/`;
   `/parliaments/<chamber>-<n>/`; `/about/` (method, accuracy, limitations, licence, cite);
   `/data/` (downloads, dictionary, API, metadata). Every page works with JavaScript disabled.
2. **Explorer** at `/explore/`: filters (chamber, parliament, party, bloc, section, owner, entity
   type, change type, confidence, free text over member, entity and description), facet counts,
   a result table, charts that follow the filters, CSV download of the selection, and state in
   the URL so a view can be shared.
3. **Charts** on the overview, section, parliament, member and entity pages, rendered as SVG at
   build time (no JS needed), plus the explorer's interactive charts.
4. **Data sharing**: SQLite, CSV, CSV.gz, JSONL (and Parquet when `pyarrow` is present) on R2 in
   versioned folders with a sha256 manifest; Datasette Lite pointed at the R2 DB; an in-page SQL
   console using HTTP range requests; a static JSON API (`/data/*.json`, per-member and per-entity
   `items.json`) with CORS `*`; `datapackage.json`; schema.org `Dataset` JSON-LD; `sitemap.xml`;
   a change feed; Open Graph cards. Kaggle stays and gets the new URL.
5. **Honest labelling** on every page: transcription method and measured accuracy, confidence per
   item, source link to the PDF page, entity match method, the known limitations.
6. **Deployment**: `web/wrangler.jsonc`, `web/deploy.sh` with gates, a GitHub Actions workflow that
   replaces `pages.yml`, an R2 publish command, and a redirect page left on GitHub Pages so old
   links keep working.
7. **Integration with kevinrassool.com**: a `Data` entry in the site nav, a `/data/` hub page that
   lists this dataset and (later) the WHO evidence graph, and a draft post, all on a draft branch.

### Why

The dataset is only useful if people can find the MP or company they care about and check the
source in two clicks. Today that takes a 32 MB download and SQL. Permalinks make the data
quotable and indexable; the explorer answers the common questions (who holds what, which party
declares what, what changed) without a download; downloads, API and metadata serve people who
want to build on it. Static hosting on Kevin's own account costs nothing, needs no upkeep, and
puts the dataset next to his writing.

### Users

- Readers from Reddit, journalists, researchers, the MP's constituents ("what does my member
  own").
- Data users: CSV/SQLite/Parquet downloaders, Datasette users, people pulling per-member JSON.
- Kevin, rebuilding after each `refresh` with one command and one push.

### In scope

Phases A–F (§4): data layer and bundle; static pages and charts; explorer; deploy scaffolding
and R2; sharing extras (SQL console, datapackage, feed); blog integration.

### Non-goals

- No Worker script, no D1, no server-side API in v1 (RESEARCH §4 B records the path if wanted).
- No change to the pipeline, the DB schema or the published data. The web build is read-only.
- No analytics, cookies or third-party runtime requests (same rule as the sibling site).
- No user accounts, comments, alerts or scheduled refresh.
- No monetary values, no inference beyond what the register states.
- Kevin performs every outward action: creating the bucket and tokens, DNS, first deploy,
  pushing the blog, disabling GitHub Pages, Zenodo. The build prepares and dry-runs; it never
  deploys or pushes to another repo.

---

## 2. ADRs

### ADR-W1 — Own subdomain, static-assets-only Worker on the personal account
**Decision.** Worker `aus-interests` (name is in `web/wrangler.jsonc`), `assets.directory` = the
build output, `not_found_handling: "404-page"`, `html_handling: "auto-trailing-slash"`,
`workers_dev: true`, route `interests.kevinrassool.com` with `custom_domain: true`. Auth as the
blog: `web/.env` (`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, gitignored; `.env.example`
committed). A separate Worker `aus-interests-preview` (workers.dev only) takes preview builds.
**Rationale.** Zero cost and no quota on asset requests; nothing to keep running; identical to
kevinrassool.com and the planned `evidence.kevinrassool.com`.
**Rejected.** Mounting under `kevinrassool.com/interests/*` with a route (two Workers on one
hostname, relative-URL and caching complications, and the blog's `404-page` handling would need
coordination); Cloudflare Pages (Cloudflare steers new projects to Workers); keeping GitHub Pages.
**Open for Kevin:** the subdomain word. Default `interests`; alternatives `register`, `disclosures`.

### ADR-W2 — Two-part build: Python renders pages, numbers and the data bundle; a small TypeScript bundle adds the explorer
**Decision.** New package `disclosures/web/` (`cli.py`, `dataset.py` read-only access,
`bundle.py`, `pages.py` + Jinja2 templates in `disclosures/web/templates/`, `charts.py` static
SVG, `metadata.py` JSON-LD/datapackage/sitemap/feed, `check.py`). `python -m disclosures web
build --db site/disclosures_v2.db --manifest pdfs/manifest.csv --out <dir> --mode preview|production
[--data-base URL]` writes the whole site. `web/` holds the browser code (`web/src/*.ts`, esbuild to
one ES module per entry, pinned deps, `package-lock.json` committed); `web build` copies the built
bundle in. Every page is complete without JS; JS adds the explorer, client-side search on index
pages, and the SQL console.
**Rationale.** One source of numbers (static charts and JSON come from the same Python module the
pages use); crawlable permalinks; small, testable JS. Same split as zombie-trials ADR-35.
**Dependencies.** `Jinja2` (pinned) joins `requirements.txt`; `pyarrow` is optional and only
read by `publish-data`. The web build must import nothing heavier than Jinja2 and the stdlib
(no PyMuPDF, no google-genai), so a CI runner can build the site after `pip install Jinja2`
alone; a test imports `disclosures.web` with those modules blocked.
**Rejected.** Observable Framework / Astro / Evidence (second build system for ~8 templates); a
pure SPA (no-JS readers and link previews get nothing); extending `export --site` in place (the
f-string renderer is fine for one page, not fifty templates).

### ADR-W3 — Data delivery: one compact bundle plus per-page JSON on static assets; the full files on R2
**Decision.** The build emits:
- `data/items.json`: all items, columnar, dictionary-encoded ids and strings (member, entity,
  document, enums), raw ≤ 8 MB, served compressed by Cloudflare (expected ≈ 1.4 MB over the wire);
  `data/members.json`, `data/entities.json` (entities with ≥ 2 items plus every typed or ASX
  entity), `data/documents.json` (sha, path, chamber, parliament, pages, source URL),
  `data/search.json` (member and entity names for the index-page search box), `data/summary.json`
  (every number the overview prints), `data/schema.json` (the bundle's column contract, versioned
  `web_bundle_version`).
- `members/<id>/items.json` and `entities/<id>/items.json`: the page's items as plain row objects
  with the published CSV column names (the static API).
- `_headers`: `Access-Control-Allow-Origin: *` on `/data/*` and `/*/items.json`; long cache on
  hashed JS/CSS; `X-Robots-Tag: noindex` in preview mode.
- `web-manifest.json`: input DB sha256, manifest sha256, mode, build time, sha256 + size of every
  output file.
Limits checked by `web check`: ≤ 12,000 files, each ≤ 20 MiB, HTML ≤ 2 MiB each, total ≤ 300 MiB.
The DB, CSV, CSV.gz, JSONL and optional Parquet go to R2 by `web publish-data` (ADR-W6), never
into the asset directory (`web check` fails on any `.db`, `.csv` or `.parquet` in it).
**Rationale.** 50k rows filter in milliseconds in plain JS; no WASM query engine, no CORS to the
site itself, no server. Big files live where range requests and zero egress are free.
**Rejected.** DuckDB-WASM + Parquet (2–5 MB WASM for a 50k-row table; Firefox range bug); D1
(fails closed at the daily limit; a second data copy to sync); serving the DB as an asset (over
the 25 MiB limit; a `.gz` would not be transparently decoded).

### ADR-W4 — Pages, routes and what each shows
| Route | Content |
|---|---|
| `/` | What this is, in two sentences. Headline numbers (items, members, statements, parliaments, entities, data date). Four static charts: items per section split by bloc; top 15 entities by distinct members; items per parliament by owner; share of alterations per parliament. Entry points: explorer, members, entities, downloads. Cite + licence summary. |
| `/members/` | Table of 408 members: name, chamber, parliaments served, party per term, item count; client-side filter box; links. |
| `/members/<member_id>/` | Name, chamber, electorate/state and party per term (table). Coverage: statements (one per parliament) with page count and source link. Items grouped by section, each row: owner, entity (link to entity page when it has one), description, change type, lodged date, confidence badge, `page N` link to the PDF (ADR-W5). A static bar chart of items per section. Alterations in a dated list ("added", "removed", "varied"). Footer sentence: how this was transcribed and how to check it. Link to `items.json`. |
| `/entities/` | Entities with ≥ 2 items: canonical name, type, ASX code, members, items, match method; filter box; a note that 7,037 one-off names have no page and are searchable in the explorer. |
| `/entities/<entity_id>/` | Canonical name, type, ASX code, how it was matched (`curated`/`asx`/`llm`), the printed variants folded into it (from `entity_aliases`). Members holding it, by parliament and bloc (static chart: distinct members per parliament by bloc). Items table as on the member page. Link to `items.json`. |
| `/sections/<n>/` | The official section wording (House form) and the Senate category mapped onto it. Items by parliament and bloc; top entities in this section; link to the explorer prefiltered. |
| `/parliaments/house-43/` … `/parliaments/senate-48/` | Coverage, dates, members list with party and item count, items by section; the known limitations of that register (scan quality, prompt version). |
| `/explore/` | ADR-W7. |
| `/sql/` | ADR-W8 (phase E). |
| `/data/` | Downloads (version, size, sha256, licence) linking to R2; the field dictionary (rendered from `export.COLUMNS`, the same source as the Kaggle README); the static API (routes, example `curl`, CORS note, the `web_bundle_version` contract); Datasette Lite button; `datapackage.json`; JSON-LD; change feed link; Kaggle link; how to cite; licences (CC BY 4.0 for the dataset, CC BY-NC-ND 4.0 for the APH documents, attribution text). |
| `/about/` | Method (collect, transcribe, validate, load, standardise), the gold-set accuracy numbers (F1 0.987, owner and page accuracy 100%), prompt versions, known limitations (verbatim from the Kaggle README source), contact, repo link, changelog. |
| `/404.html`, `/robots.txt`, `/sitemap.xml`, `/changes.xml`, `/opensearch.xml` (optional) | Plumbing. |

Every HTML page carries: `<title>`, description, canonical URL, Open Graph tags (a generated SVG
or PNG card per member/entity is optional, phase B stretch), the footer (dataset version, data
date, "transcribed from the Parliament of Australia registers; CC BY 4.0; check the source", repo
link), and in preview mode `<meta name="robots" content="noindex,nofollow">`.

### ADR-W5 — Source deep links, by URL class, verified by a sampled probe
**Decision.** Each item's source link is built from the manifest URL for its document:
- `static.aph.gov.au/...pdf?...` (House 44th–47th): `href="<url>#page=<page>"`, text "page N".
- `interests-register-api-public.aph.gov.au/api/members/<id>/statement/<p>` (House 48th): same
  `#page=` form (the API serves the PDF); text "page N".
- `www.aph.gov.au/.../House_of_Representatives_Committees?url=pmi/declarations/<file>` (43rd):
  link to the URL as given, text "page N of the PDF" (the redirector may drop the fragment).
- Senate API URLs (JSON, not a PDF): link to the Senate register page for that senator where the
  manifest or members table gives one, else the register index; text "Senate register (structured
  source, no page)".
`web probe-links --site <out> --sample 30` (network, `WEB_NETWORK_TESTS=1`) GETs a sample of
House links and reports the share returning 200/206 with `application/pdf`; results go in
BUILDLOG, never fixed by hand.
**Rationale.** Readers must reach the printed page; URL shapes differ per register and the DB
does not store the URL. Same approach as zombie-trials ADR-41.

### ADR-W6 — R2 bucket for the data files, versioned, with CORS; Datasette Lite points there
**Decision.** Bucket `aus-interests-data`, custom domain `data.kevinrassool.com`, public, CORS
`GET, HEAD` from `*` with `Range`, `Content-Length`, `Content-Range`, `ETag` exposed. Layout:
`interests/<version>/{disclosures_v2.db, disclosures_v2.csv, disclosures_v2.csv.gz,
disclosures_v2.jsonl.gz, disclosures_v2.parquet?, README.md, datapackage.json, MANIFEST.json}` and
`interests/latest/` (same files, overwritten). `<version>` = `v2.<loaded_at date>` from `meta`
(e.g. `v2.2026-10-02`). `python -m disclosures web publish-data --db … --version auto [--dry-run]`
writes the files to a temp dir, prints the `wrangler r2 object put` commands, and runs them only
without `--dry-run`. The Datasette Lite link becomes
`https://lite.datasette.io/?url=https://data.kevinrassool.com/interests/latest/disclosures_v2.db`.
**Rationale.** The only place the 32 MB DB can live with CORS, `Range` and no egress bill;
versioned folders give stable citation targets; `latest/` gives one link for the site.
**Rejected.** GitHub Releases as the download host (no guaranteed CORS/range; ties downloads to
GitHub); the `r2.dev` subdomain (rate-limited, throttles with 429).
**Account step for Kevin (§6):** add `Account > Workers R2 Storage > Edit` to the personal token.

### ADR-W7 — Explorer: client-side, URL-addressable, honest about what it shows
**Decision.** `/explore/` loads `data/items.json` (+ members/entities/documents) once, builds
typed arrays and inverted indexes in a Web Worker, and renders:
- a filter rail: chamber, parliament, bloc, party, section, owner, entity type, change type,
  confidence, text query (member name, entity canonical and printed name, description); facet
  counts update with the selection;
- a virtualised result table (default sort: parliament desc, member, section) with the same
  columns and links as the member page; a "download CSV of this selection" button (built in the
  browser, published column names);
- three charts that follow the selection, drawn with Observable Plot bundled locally: items by
  section split by bloc; distinct members per parliament; top entities in the selection;
- state in the query string (`?parliament=47&section=1&bloc=Coalition&q=qantas`), so section and
  entity pages can link into a prefiltered view;
- a persistent note: counts are counts of disclosed items, not of value; transcription errors of
  roughly 1–2% exist; confidence is shown per row.
Budget: explorer JS ≤ 250 KB gzipped including Plot; first interactive ≤ 3 s on a 2020 laptop
over a 10 Mbit connection (Playwright measures transfer and `data-ready`).
**Rationale.** Everything a Datasette facet view does, for a 50k-row table, at zero server cost
and with URLs people can share.
**Rejected.** Server-side search (needs a Worker + D1); loading per-filter shards (the whole
table is 1.4 MB; sharding adds complexity for no gain).

### ADR-W8 — SQL console with `sql.js-httpvfs` against the R2 DB (phase E, optional)
**Decision.** `/sql/` loads `sql.js-httpvfs` (bundled locally, including its WASM and worker) and
opens `https://data.kevinrassool.com/interests/latest/disclosures_v2.db` read-only over HTTP range
requests. Example queries (top entities, one member's gifts, alterations in a parliament) are
buttons; results render in a table with "download CSV". A sentence explains that only the pages a
query touches are fetched, with a live byte counter. If the DB page size is not 1024 bytes, `web
publish-data` rewrites a copy with `PRAGMA page_size=1024; VACUUM;` for this purpose (the download
file is unchanged). Datasette Lite stays as the "full SQL UI" link.
**Rationale.** Ad-hoc SQL without downloading 32 MB and without a server. **Stretch:** phase E can
be deferred without affecting A–D.

### ADR-W9 — Honest labels are part of the page contract
**Decision.** On every page that lists items: the confidence badge per item (`medium`/`low`
visible, `high` implicit), the "transcribed by `<model>`" line with the measured gold-set
precision/recall, the "check the source" link per item, `party at start of term`, `Senate: 48th
parliament only`, `singleton entities untyped` where relevant, `change_type unknown` shown as
"change not stated". Entity pages state the match method in words ("matched by the ASX
listed-companies list", "curated alias table", "LLM grouping of spelling variants"). No page
infers wealth, conflict or wrongdoing; copy describes what was declared. Preview builds carry
`noindex` and a banner "preview build, not the published dataset".
**Rationale.** The dataset is about named public officials and their families; the register is
public, but the site's job is to point at the record, not editorialise. Mirrors zombie-trials
ADR-40.

### ADR-W10 — Design: the personal site's system, data-first
**Decision.** Fonts (self-hosted copies of the blog's woff2 files and OFL notices), tokens
(`--paper --ink --muted --rule --accent --yellow`, light and dark via `prefers-color-scheme`),
header (`kr.` wordmark linking to kevinrassool.com, nav: Overview, Explore, Members, Entities,
Data, About), 375 px first, 16 px gutters, no horizontal scroll, skip link, focus styles. Bloc
colours for charts: Labor red, Coalition blue, Crossbench a neutral amber, each validated for
contrast on paper and dark backgrounds with the `dataviz` skill's checker; sections and entity
types use a single sequential ramp from `--accent`. Static SVG charts use CSS classes and
`currentColor`, so one SVG serves both themes. Tables are real `<table>` elements with
`<caption>`. Copy: plain English, no em dashes. The builder loads the `dataviz` skill before any
chart and `frontend-design` if available.
**Rejected.** A dashboard look (cards, KPI tiles everywhere); political party colours for every
party (16 parties, unreadable; bloc is the level the data supports).

### ADR-W11 — Deploy: `deploy.sh` with gates, GitHub Actions replaces `pages.yml`, Pages becomes a redirect
**Decision.**
- `web/deploy.sh <site-dir> --preview|--production [--dry-run]`: `--preview` deploys to
  `aus-interests-preview` and requires `--mode preview` output; `--production` refuses unless
  `web check <site-dir>` exits 0, `web-manifest.json` says `mode=production`, the input DB sha256
  equals the sha256 of the committed `site/disclosures_v2.db` on `main`, and `data-base` points
  at `https://data.kevinrassool.com/interests/`. `--dry-run` prints the exact `wrangler deploy`
  command and exits 0 after the gates. The build session only ever runs `--dry-run`.
- `.github/workflows/web.yml`: on push to `main` touching `disclosures/web/**`, `web/**`,
  `site/disclosures_v2.db` or `pdfs/manifest.csv`, and on `workflow_dispatch`: install Python
  deps, `pytest tests/web`, `npm ci && npm run build` in `web/`, `web build --mode production`,
  `web check`, then `cloudflare/wrangler-action` deploy with repo secrets
  `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` (the personal-account token). A second job,
  only when the DB changed, runs `web publish-data` to R2. Concurrency group `web`.
- `pages.yml` keeps deploying `site/` until Kevin disables Pages; `export --site` is changed to
  write a redirect `index.html` (`<meta http-equiv="refresh">` to the new domain + canonical) and
  keep the DB copy so old Datasette Lite links work for 30 days. The Kaggle README and
  `export.py`'s `pages_url` default move to the new URL.
**Rationale.** The repo already runs Actions; tests gate deploys; secrets stay out of the repo;
Workers Builds is the documented alternative (build image has Python 3.13 and Node) if Actions
ever becomes the bottleneck.
**Rejected.** Deploying from the Mac only (no reproducible production path); Workers Builds as the
primary (one more place to configure; no test step without extra scripting).

### ADR-W12 — Tests and fixtures
**Decision.** `tests/web/` (pytest). Fixture `tests/fixtures/web/mini.db`: a deterministic subset
of the real DB made by `python -m disclosures web make-fixture --members 6 --seed 1` (6 members
spanning House 43, 47, 48 and Senate 48, all their items, the entities and aliases they touch, a
`meta` row `fixture=1`), plus a matching `mini-manifest.csv`. Browser tests: Playwright
(Chromium) in `web/` (`npm test`) against a site built from the fixture and served by `python -m
http.server` or `npx wrangler dev` (builder's choice, documented). No test touches the network
except those marked `WEB_NETWORK_TESTS=1`. The full suite (`pytest -q`) keeps passing.

### ADR-W13 — Where code lives; branches
- `disclosures/web/` (Python package, registered in `disclosures/cli.py` (`ORDER`, `HELP`,
  `add_parser`) as `web` with subcommands `build`, `check`, `publish-data`, `make-fixture`,
  `probe-links`; imported lazily like the other commands).
- `web/` (browser code and deploy: `src/`, `package.json`, `package-lock.json`, `esbuild.mjs`,
  `wrangler.jsonc`, `deploy.sh`, `.env.example`, `README.md`, `tests/` for Playwright). Built
  sites go to `--out` dirs under `web/sites/` or the scratchpad, gitignored.
- `docs/v2/web.md`: what each page shows, label rules, rebuild/deploy/publish-data steps, the
  static API contract. `README.md` gets a "Public site" section; `HANDOFF.md` a pointer.
- Branch `build/2026-10-03-public-site` from `main`, one commit per phase, PR to `main`.
- kevinrassool.com: branch `draft/interests-register`, commits only (`Data` nav entry, `/data/`
  hub page, `posts/interests-register/index.md` with `draft: true`). Not pushed, not deployed.

---

## 3. Acceptance criteria

All commands run from the repo root in the project venv. "Mini" = a site built from the fixture
DB (ADR-W12). "Real" = a site built from `site/disclosures_v2.db`. Exit codes: 0 ok, 1 check
failed, 2 bad input or clobber guard. Each AC is proven by a named test or command; the builder
records command + result in `plans/2026-10-03-public-site/BUILDLOG.md`.

### 3.1 Phase A — data layer, bundle, check, fixture
- **AC-A1** `python -m disclosures --help` lists `web`; `python -m disclosures web --help` lists
  `build`, `check`, `publish-data`, `make-fixture`, `probe-links`.
- **AC-A2** `web make-fixture --out $T/mini --members 6 --seed 1` is deterministic (two runs,
  identical sha256) and the result passes the v2 loader's schema expectations (same tables,
  `meta.fixture = 1`). `tests/fixtures/web/mini.db` is committed and ≤ 2 MB.
- **AC-A3** Read-only: `web build` on a dataset dir made `chmod -R a-w` succeeds; sha256 and mtime
  of the DB and manifest are unchanged after. A build with an `--out` that exists and is non-empty
  exits 2 and writes nothing.
- **AC-A4** Bundle contract: `data/items.json` on Real has `n = 50936`; every column in
  `data/schema.json` is present; dictionary indexes are in range; a test decodes 200 random rows
  and matches them to SQL on the DB field by field. Raw size ≤ 8 MB. `web_bundle_version` is
  `"1"`.
- **AC-A5** `web check <site>` exits 1 with a named rule on each planted fault (one test per
  fault, on copies): a `.db`/`.csv`/`.parquet` file in the site; a file > 20 MiB; > 12,000 files;
  an HTML page without the footer; an external `<script src>` or stylesheet; a production build
  with `noindex`; a preview build without it; a member page missing for a member in the DB.
- **AC-A6** Source URLs: every document in Real resolves to a manifest URL and a URL class
  (ADR-W5); the count of class `senate-json` equals the Senate document count (76).

### 3.2 Phase B — static pages and charts
- **AC-B1** `web build --db site/disclosures_v2.db --manifest pdfs/manifest.csv --out $T/site
  --mode preview` exits 0 and writes `index.html`, `members/index.html`, one
  `members/<id>/index.html` per `members` row (408), one `entities/<id>/index.html` per entity
  with ≥ 2 items (count equal to SQL), 14 `sections/<n>/`, 7 `parliaments/…/`, `about/`, `data/`,
  `explore/`, `404.html`, `robots.txt`, `sitemap.xml`, `changes.xml`, `_headers`,
  `web-manifest.json`, and the `data/*.json` files of ADR-W3. Total files ≤ 12,000; no HTML > 2 MiB.
- **AC-B2** Member page content (pytest parses HTML for every Mini member): full name, chamber,
  each term's parliament, party, bloc and electorate/state; one statement row per document with
  page count and a source link; every item of the member (count equals SQL) with owner, section
  name, description, change type, lodged date (or "not stated"), a confidence badge when
  `medium`/`low`, and a source link whose `href` follows ADR-W5 for that document's URL class.
  Entity names link to `/entities/<id>/` exactly when that entity has a page.
- **AC-B3** Entity page content: canonical name, type (or "untyped"), ASX code when set, match
  method in words, the folded printed variants (from `entity_aliases` + distinct
  `entity_name_raw`), members by parliament (counts equal SQL), items (count equals SQL).
- **AC-B4** Overview numbers equal `data/summary.json`, which equals SQL (test computes
  independently): items, members, statements, entities, items per section × bloc, top 15 entities
  by distinct members, items per parliament × owner, alteration share per parliament.
- **AC-B5** Static charts: each page type's SVG has `<title>` and `<desc>`, uses only classes and
  `currentColor` for colour (no hard-coded fills except the three bloc colours), and is
  byte-identical across two builds.
- **AC-B6** Works without JS: Playwright with `javaScriptEnabled: false` on `/`, one member, one
  entity, one section page sees the AC-B2/B3/B4 strings and the tables.
- **AC-B7** Footer on every HTML page: "CC BY 4.0", "Parliament of Australia", the dataset
  version, the data date, a link to the repository, and the "check the source" sentence. In
  preview mode every page has `noindex,nofollow` and the banner; in production neither.
- **AC-B8** Metadata: `/` and `/data/` carry a schema.org `Dataset` JSON-LD block with `name`,
  `description` (50–5,000 chars), `license`, `creator`, `temporalCoverage`, `distribution` (one
  `DataDownload` per R2 file with `contentUrl`, `encodingFormat`), `isAccessibleForFree: true`,
  and `identifier` when a DOI is configured; validated with a JSON-LD parse and a key check.
  `sitemap.xml` lists every HTML page; `robots.txt` allows all in production.
- **AC-B9** No third-party requests: Playwright records all requests on `/`, one member, one
  entity, `/explore/`, `/data/`: every URL is same-origin except the documented R2 host on
  `/data/` and `/sql/`. No cookies set. Fonts are served from `/fonts/`.
- **AC-B10** Accessibility and layout: axe-core (bundled in the Playwright test) reports no
  serious or critical violations on `/`, a member page and `/explore/`; at 375 px width no page
  has horizontal overflow (`document.documentElement.scrollWidth <= 375`).
- **AC-B11** Sensitive content guard: the build renders only DB columns and manifest URLs (grep of
  templates for any other data source is empty); `scripts/check_sensitive_info.py` style patterns
  (API keys, private keys) find nothing in the built site.

### 3.3 Phase C — explorer
- **AC-C1** `/explore/` on Mini: Playwright sets `?parliament=47&section=1` and sees the row count
  equal to SQL for that filter; typing a member's surname narrows to that member's rows; toggling a
  bloc updates the facet counts and the chart's bars (bar count equals distinct sections in the
  selection); the URL reflects every active filter and reloading it restores the same count.
- **AC-C2** CSV of the selection: the downloaded file has the published column names, one row
  per visible item, and the row count matches; values for 20 random rows equal SQL.
- **AC-C3** Budget on Real: explorer JS ≤ 250 KB gzipped (test measures the built bundle);
  bytes transferred to reach `data-ready="1"` ≤ 2.5 MB; time to `data-ready` ≤ 3 s in headless
  Chromium on the build machine (recorded in BUILDLOG; informative if the machine is loaded).
  If `data/items.json` transfers > 2.5 MB, the builder switches to a pre-compressed binary pack
  and records the decision.
- **AC-C4** Prefilter links: every section page and entity page links to `/explore/?...` with its
  own filter; following one shows the matching count.
- **AC-C5** The explorer page without JS shows the overview table of counts and a sentence
  pointing to the member and entity indexes (not a blank page).

### 3.4 Phase D — deploy scaffolding, R2, redirects
- **AC-D1** `web/wrangler.jsonc` names Worker `aus-interests`, assets-only, `404-page`,
  `auto-trailing-slash`, custom domain `interests.kevinrassool.com`; `git check-ignore web/.env`
  succeeds; `web/.env.example` exists.
- **AC-D2** `web/deploy.sh $T/site --production --dry-run` exits non-zero with a specific message
  for each failing gate (preview mode; check failure; DB sha mismatch vs `main`; wrong data base)
  and, on a passing production build, prints the exact `wrangler deploy` command and exits 0
  without network. `--preview --dry-run` names `aus-interests-preview`.
- **AC-D3** `web publish-data --db site/disclosures_v2.db --version auto --out $T/data --dry-run`
  writes `interests/v2.<date>/` with the DB, CSV, CSV.gz, JSONL.gz, README.md, datapackage.json,
  MANIFEST.json (sha256 + size per file; Parquet when `pyarrow` is importable), mirrors them in
  `interests/latest/`, prints the `wrangler r2 object put` commands and the `wrangler r2 bucket
  cors set` command with the CORS JSON, and uploads nothing. The CSV is byte-identical to
  `python -m disclosures export`'s output for the same DB.
- **AC-D4** `.github/workflows/web.yml` exists, triggers on the paths in ADR-W11, runs tests,
  build, check, deploy; `actionlint` (or a YAML parse plus a key check) passes. `pages.yml` is
  unchanged in trigger; `export --site` now writes a redirect `index.html` whose target is the
  new domain (test renders it and checks the `refresh` meta and canonical).
- **AC-D5** `_headers` sets `Access-Control-Allow-Origin: *` for `/data/*` and `/*/items.json`;
  Playwright served via `npx wrangler dev` sees the header on `/data/summary.json` (if `wrangler
  dev` is unavailable offline, a unit test parses `_headers`).
- **AC-D6** Docs: `docs/v2/web.md` covers pages, labels, bundle contract and static API, rebuild,
  check, deploy, publish-data, the R2 layout, the owner steps; `README.md` has a "Public site"
  section; the Kaggle README and `export.py` defaults point at the new URL.

### 3.5 Phase E — sharing extras (SQL console, feed, datapackage)
- **AC-E1** `/sql/` loads `sql.js-httpvfs` from same-origin files only; against a local copy of
  the fixture DB served with range support (Playwright route or `python -m http.server`), running
  `select count(*) from items` shows the fixture's count; the byte counter is < the DB size.
- **AC-E2** `datapackage.json` validates against the Frictionless Data Package schema (bundled
  JSON Schema, offline) and lists every column with the dictionary text.
- **AC-E3** `changes.xml` is valid RSS 2.0 with one entry per dataset version (initial entry from
  `meta.loaded_at`); `/data/` links it.
- **AC-E4** Deferral rule: if E is deferred, `/data/` still links Datasette Lite and the
  downloads; `web check` does not require `/sql/`.

### 3.6 Phase F — kevinrassool.com integration (draft branch only)
- **AC-F1** In the blog repo on `draft/interests-register`: the header nav of `index.html`,
  `running.html`, `404.html` and `tools/build.py`'s `page()` gets a `Data` link to `/data/`;
  `site/data/index.html` lists the Registers of Interests dataset (one paragraph, numbers from
  `summary.json`, links to `interests.kevinrassool.com`, downloads, Kaggle) with a placeholder
  entry for the WHO evidence graph marked `[OWNER: when live]`.
- **AC-F2** `posts/interests-register/index.md` exists with `draft: true`, title, date, summary,
  cover + `cover_alt`, two stills (overview chart, one member page) and `[OWNER: …]` markers for
  Kevin's prose. `npm run build` produces no `site/writing/interests-register/`; `python3.11
  tools/build.py --drafts` does.
- **AC-F3** Nothing pushed, nothing deployed: `git log origin/main..main` in the blog repo is
  unchanged; no `wrangler deploy` ran (BUILDLOG states it).

---

## 4. Phase plan

| Phase | Items | Depends on | Notes |
|---|---|---|---|
| A | `disclosures/web/` skeleton, `dataset.py`, `bundle.py`, `check.py` (core rules), `make-fixture`, fixture committed | — | Verifier: AC-A3 read-only, AC-A4 bundle equals SQL. |
| B | templates, `pages.py`, `charts.py`, `metadata.py`, CSS + fonts, `web/` scaffold (esbuild, index-page search), Playwright harness | A | Verifier: AC-B2/B3 counts equal SQL; B6 no-JS; B9 no third-party. |
| C | explorer (`web/src/explore.ts`, worker, Plot charts, CSV) | A, B | Verifier: AC-C1 counts; C3 budget. |
| D | `wrangler.jsonc`, `deploy.sh`, `publish-data`, `web.yml`, redirect in `export --site`, `_headers`, docs | B (C for the budget gate) | Verifier: every gate fails closed. |
| E | `/sql/`, `datapackage.json`, `changes.xml` | D | Optional; defer if time is short. |
| F | blog branch: nav, `/data/` hub, draft post | B (stills) | Commits only. |

Serial A→F is the default. C and D can run in parallel in worktrees after B if two sessions
are available; serial is simpler. Expected effort: A 0.5 day, B 1.5 days, C 1 day, D 0.5 day,
E 0.5 day, F 0.25 day. Money: none (free tiers, no LLM calls).

---

## 5. Data-shape notes for the builder

- DB schema: `docs/v2/loading.md` and v2 SPEC ADR-7. Tables `documents`, `members`,
  `member_terms`, `items`, `entities`, `entity_aliases`, `meta` (`schema_version`, `source_id`,
  `loaded_at`, `n_files`).
- Published column names and dictionary text: `disclosures/export.py` (`COLUMNS`, `HEADER`,
  `QUERY`, `render_readme`). Reuse them; do not duplicate the dictionary.
- Source URLs: `export.manifest_urls(Path("pdfs/manifest.csv"))` → `{pdf_sha256: url}`.
- Section names: `category` column (1 Shareholding … 14 Other interest). Official wording for
  the section pages: v2 SPEC §0 "Official House form — 14 numbered sections".
- Entity match method: `entity_aliases.method` via `normalise_entity(entity_name_raw)` (as
  `export.fetch_rows` does); `confidence` on `llm` rows.
- Items without `entity_id` (8,684) still render on member pages; they never get an entity link.
- Member ids are slugs (`tony_abbott`); entity ids are slugs (`commonwealth_bank_of_australia`).
  Both are URL-safe already; the build asserts `^[a-z0-9_]+$` and fails otherwise.
- Bloc colours and the sequential ramp: validate with the `dataviz` skill's checker in both
  themes before committing CSS.
- Mini fixture choice: pick members that cover House 43 (scanned), 47, 48 (API URL class) and
  Senate 48 (JSON class), at least one with spouse/dependent items and one with many alterations;
  record the six ids in `tests/fixtures/web/README.md`.

---

## 6. Runbook (owner steps, in order)

1. **Account.** On the personal Cloudflare account: edit the API token the blog uses (or make a
   second one) to add `Account > Workers R2 Storage > Edit`. Put it in `web/.env`
   (`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`), copied from `web/.env.example`. Check:
   `cd web && npx wrangler whoami` shows the personal account.
2. **Bucket.** `npx wrangler r2 bucket create aus-interests-data`; attach custom domain
   `data.kevinrassool.com` (dashboard: R2 > bucket > Settings > Custom Domains; the zone is on
   Cloudflare so the DNS record is created for you). Apply CORS with the command `publish-data
   --dry-run` prints.
3. **Data.** `python -m disclosures web publish-data --db site/disclosures_v2.db --version auto`
   (no `--dry-run`). Check `https://data.kevinrassool.com/interests/latest/MANIFEST.json` loads
   and the Datasette Lite link opens the DB.
4. **Preview.** `python -m disclosures web build … --mode preview --out web/sites/preview-<date>`,
   `web check`, `web/deploy.sh web/sites/preview-<date> --preview`. Open the workers.dev URL,
   check a member page, an entity page, the explorer at 375 px and desktop, light and dark. Optionally
   put Cloudflare Access on the preview Worker.
5. **Production.** Add repo secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` in GitHub
   (the personal token). Merge the build PR to `main`; `web.yml` deploys. First deploy may need
   `npx wrangler deploy` once from the Mac so Cloudflare creates the custom domain and
   certificate. Check `https://interests.kevinrassool.com/`.
6. **Redirect and Pages.** The merged `export --site` writes the redirect `index.html`; let
   `pages.yml` publish it. After 30 days, disable GitHub Pages in the repo settings and delete
   `pages.yml`; keep `site/disclosures_v2.db` as the committed published DB.
7. **Kaggle.** `kaggle datasets metadata` / update the README with the new URLs (the README is
   regenerated by `export`).
8. **DOI (optional).** Enable the Zenodo–GitHub integration for the repo, cut a release
   `v2.<date>`, put the DOI in `web build --doi` (or `meta`) and rebuild so the footer, cite
   block and JSON-LD carry it.
9. **Blog.** Review `draft/interests-register` in the blog repo, replace `[OWNER: …]`, set
   `draft: false`, `npm run deploy`.
10. **Each refresh** (`python -m disclosures refresh && export`): commit the new DB, push to
    `main`; `web.yml` rebuilds the site and publishes a new `interests/v2.<date>/` folder plus
    `latest/`; `changes.xml` gains an entry.

---

## 7. Open questions for Kevin (none blocks phases A–C)

1. **Subdomain word:** `interests` (default), `register`, or `disclosures`? Also the bucket
   hostname `data.kevinrassool.com` is proposed as the shared data host for both datasets.
2. **Entity pages for singletons:** none in v1 (7,037 pages of one row each). Fine?
3. **Hugging Face mirror and Croissant metadata:** add to `publish-data` (one extra upload) or skip?
4. **Open Graph cards per member/entity** (generated SVG→PNG at build, ~5,000 small files): worth
   it for link previews, or plain site-wide card?
5. **Analytics:** none in v1. If wanted later, Cloudflare Web Analytics is a third-party beacon
   (breaks the no-third-party rule); Workers Analytics Engine needs a Worker script.
6. **Blog hub page** `/data/` on kevinrassool.com: confirm you want the nav entry, or only a post.
7. **Zenodo DOI:** do it at launch or after the first refresh?

## 8. Decisions log

| Date | Decision |
|---|---|
| 2026-10-03 | Plan written from the v2 SPEC/HANDOFF, the kevinrassool.com repo (DEPLOY.md, build tool, tokens), the zombie-trials graph-explorer SPEC (ADR-35/36/43/45 mirrored), measurements in RESEARCH §2 and Cloudflare facts in RESEARCH §3. Static-first (no Worker script, no D1); R2 for the big files because the DB exceeds the 25 MiB asset limit; subdomain, not a path; GitHub Actions deploy replacing Pages, with a 30-day redirect. |
| 2026-10-03 | **Addition to ADR-W7 (explorer): a network graph view.** Kevin asked to port the interim GitHub Pages explorer (`disclosures/explore.py` + `site_assets/explore.html`: force-directed member–organisation graph and a hover bar chart by bloc) into this build. `/explore/` gets a "Table and charts / Network graph" switch (`view=graph` in the URL). The graph is built in the browser from the current selection, so it follows every filter (no `explore.json`, no fixed views): top 60 entities by distinct members (every entity type, people named in the registers included: Kevin, 2026-10-04, "these are from public documents, there are no privacy concerns"), member dots in their latest term's bloc colour (DESIGN.md tokens). Hover highlights neighbours, a click pins a panel linking to the entity/member page and back into the filtered table, labels are de-overlapped, and there is a linked bar list (top 20, split by bloc) with a table version. force-graph 1.52.0 (+ d3-force-3d `forceCollide`) is bundled locally as `explore-graph.js` (≈ 64 KB gzip), imported only when the view opens, so the table view's first load is unchanged; both bundles together ≈ 158 KB of the 250 KB budget. Tooltips on the Plot bars (ADR-W7 had none) are part of the same addition. Tests: `web/tests/explore-graph.spec.ts`; `web check` rule `explorer-bundle-missing` covers the graph bundle. |
| 2026-10-04 | **Explorer: bank accounts left out of the visualisations by default.** Kevin: section 8 (Account) items "pollute" the charts and graph (CBA alone has 923 of them). A checkbox, on by default, leaves section 8 out of the Plot charts and the network graph; the table, counts and CSV keep every item; `accounts=show` in the URL turns it off; a section filter including 8 overrides it. |
| 2026-10-04 | **The toggle also covers section 6 (Liability: mortgages, credit cards).** After the section-8 cut the big four banks still topped the graph through loans (CBA: 128 members via section 6). Kevin: mortgages, credit cards and accounts "basically won't influence a politician". The checkbox now leaves out sections 6 and 8; URL `banking=show` (was `accounts=show`, live less than a day). |
