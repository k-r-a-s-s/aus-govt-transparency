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

## Phase A: data layer, bundle, check, fixture (2026-10-03)

### What landed

- `disclosures/web/`: `__init__.py` (`WEB_BUNDLE_VERSION = "1"`), `cli.py` (subcommands
  `build`, `check`, `publish-data`, `make-fixture`, `probe-links`), `dataset.py` (read-only DB +
  manifest access, sha256 of both, id assertions), `urls.py` (ADR-W5 classes and
  `source_link(url, page)`), `bundle.py` (`data/*.json`, per-member and per-entity
  `items.json`), `build.py` (out guard, staging, `_headers`, `web-manifest.json`), `check.py`
  (deploy rules), `fixture.py` (`make-fixture`).
- `disclosures/cli.py`: `web` appended to `ORDER`/`HELP`, lazy import; `main()` has a fast path
  for `argv[0] == "web"` that skips `build_parser()`.
- `disclosures/dbconst.py` (new): `DEFAULT_DB`, `V1_DB_NAME`, `CATEGORY`, `_guard_v1` moved out
  of `load.py`, which re-exports them unchanged; `export.py` imports them from `dbconst`.
- `tests/fixtures/web/{mini.db, mini-manifest.csv, README.md}`; `tests/web/` (87 tests);
  `tests/test_cli.py` `COMMANDS` gains `web`.

### Commands and results

| AC | Command / test | Result |
|---|---|---|
| A1 | `python -m disclosures --help`; `python -m disclosures web --help` (`tests/web/test_web_cli.py`) | lists `web`; lists `{build,check,publish-data,make-fixture,probe-links}`. `publish-data` and `probe-links` print "not implemented in phase A" and exit 2. |
| A2 | `python -m disclosures web make-fixture --db site/disclosures_v2.db --manifest pdfs/manifest.csv --out tests/fixtures/web --members 6 --seed 1` (`test_web_fixture.py`) | two runs into tmp dirs give identical sha256 for both files, equal to the committed ones (`mini.db` sha256 `4e282a3b…`, `mini-manifest.csv` `547c52d9…`). Schema equals `load.DDL` (columns, types, PKs, indexes) and the real DB's `sqlite_master` SQL; `meta.fixture = 1`; `integrity_check` ok. `mini.db` 716,800 bytes (limit 2 MB). |
| A3 | `test_web_build.py::test_build_on_read_only_inputs`, `::test_non_empty_out_exits_2_and_writes_nothing` | build from a `chmod a-w` dir (files and dir) exits 0; sha256, mtime_ns and mode of DB and manifest unchanged; no file added beside them. Non-empty `--out` exits 2; `--out` contents, mtimes and the parent listing unchanged. |
| A4 | `test_web_bundle.py::test_items_json_on_real` (+ `_on_mini`, all rows) | Real: `n = 50936`, all 18 schema columns present, every dict index in range or -1, 200 seeded-random rows decode equal to SQL field by field, `web_bundle_version = "1"`. `data/items.json` 6,158,531 bytes raw (limit 8 MB), 1,386,456 bytes gzip -9. |
| A5 | `test_web_check.py` (one test per planted fault, on copies of the mini site, manifest resealed so only the planted rule fires) | exit 1 naming: `forbidden-file` (.db, .csv, .parquet, .sqlite, .csv.gz), `file-too-large` (20 MiB + 1), `too-many-files` (12,001 extra), `site-too-large`, `html-too-large`, `footer-missing`, `external-asset` (script src, protocol-relative, stylesheet, modulepreload), `noindex-in-production` (header and meta), `noindex-missing-in-preview` (header and meta), `member-page-missing`, plus `member-json-missing` and `manifest-mismatch`. Bad input exits 2. |
| A6 | `test_web_urls.py::test_every_real_document_resolves_to_a_url_class` | 995/995 documents have a manifest URL and a class. `senate-json` 76 = Senate documents 76. `house-redirect` 150 (all House 43rd), `house-pdf` 622 (House 44th-47th, 618, plus 4 House 48th), `house-api` 147 (House 48th). |
| ADR-W2 | `test_web_cli.py::test_web_imports_and_builds_with_heavy_modules_blocked` | with `pymupdf`, `fitz`, `google`, `google.genai`, `pydantic`, `pydantic_core`, `numpy`, `scipy`, `rapidfuzz`, `httpx` set to `None` in `sys.modules`, `disclosures.web.*` imports and `python -m disclosures web build` + `web check` on the fixture exit 0. |

Real build (`web build --db site/disclosures_v2.db --manifest pdfs/manifest.csv --out <tmp>`):
2.5 s on the Mac; 4,865 files, 107.3 MB (102.3 MiB): `data/` 7.8 MB, `members/*/items.json`
58.1 MB (408 files), `entities/*/items.json` 40.5 MB (4,448 files). Two builds are identical
file for file (only `web-manifest.json`'s `built_at` differs; `SOURCE_DATE_EPOCH` pins it).
`web check <real> --db site/disclosures_v2.db` exits 0 in 0.4 s, in both modes.

Full suite: `pytest -q` 402 passed, 6 skipped, 1 failed: `tests/test_entities.py::test_cli_missing_db`
fails only because this worktree has no `.env.local` (the `entities` command checks the
OpenRouter key before the DB path). Unrelated to phase A; with `OPENROUTER_KEY=dummy` the whole
suite passes.

### Fixture (seed 1)

`ken_o_dowd` (House 43, redirector URL), `russell_broadbent` (House 47, static PDF),
`josh_wilson` (House 48, API URL), `richard_colbeck` (Senate 48, JSON), `nicolette_boele`
(spouse + dependent-child items), `wayne_swan` (161 alterations). 1,043 items, 19 statements,
318 entities, 667 aliases; all three blocs; one `low`-confidence item. Reasons in
`tests/fixtures/web/README.md`.

### Deviations and decisions

1. **Light imports.** `export.py` imported `load`, which imports `schema` and so pydantic. The
   shared constants moved to the stdlib-only `disclosures/dbconst.py`; `load` re-exports them
   (its tests, including the `monkeypatch` of `load.CATEGORY`, pass unchanged); `export`'s
   public behaviour is unchanged. `disclosures/cli.py`'s `build_parser()` imports every
   pipeline module (numpy, scipy via `score`), so `main()` dispatches `web ...` straight to
   `disclosures.web.cli.main` without building the full parser. `python -m disclosures --help`
   still lists `web` through the full parser.
2. **House 48th has 4 static PDFs.** ADR-W5 says 48th House links are the API; 4 of the 151
   are `static.aph.gov.au` PDFs (e.g. `Albanese_48P.pdf`). They classify as `house-pdf`, which
   links the same way (`#page=N`). The AC-A6 test allows `house-pdf` for House 44th-48th.
3. **Senate links.** The manifest and `members` carry no per-senator register page, so every
   `senate-json` link goes to the Senate register index (`urls.SENATE_REGISTER_INDEX`), as
   ADR-W5's fallback says. The Senate API host comes from `sources.SENATE_API_BASE`.
4. **Fail closed on URLs.** A document with no manifest URL, or a URL with no class, makes
   `build` exit 2 before anything is written.
5. **Extra check rules** beyond AC-A5: `manifest-mismatch` (every file listed in
   `web-manifest.json` with matching sha256 and size, so a site edited after build fails) and
   `member-json-missing` (with `--db`). `forbidden-file` also covers `.sqlite`, `.sqlite3` and
   `.csv.gz`. `external-asset` treats any absolute or protocol-relative URL in `<script src>`
   or `<link rel=stylesheet|preload|modulepreload href>` as another origin: phase B templates
   must use root-relative asset URLs.
6. **Member-page rule in phase A.** Phase A writes `members/<id>/items.json` but no
   `index.html`, so `member-page-missing` is reported as skipped (exit 0) while no
   `members/*/index.html` exists at all; as soon as one member page exists, every DB member
   needs one.
7. **Footer marker** for phase B: `<footer class="site-footer" ...>` whose text contains
   `CC BY 4.0` (`check.FOOTER_MARKER`, `check.FOOTER_LICENCE`).
8. **Bundle layout.** `items.json` = `{web_bundle_version, n, columns, dict, cols}`; every
   string column is dictionary-encoded (sorted values, `-1` = null), including description;
   `dict.member` and `dict.document` are aligned with `members.json` (sorted by id) and
   `documents.json` (sorted by sha256). Rows follow `export.QUERY`'s order. No `item_id` in the
   bundle (not in the 18 columns; it is in the per-page `items.json`).
9. **Summary keys.** `parliaments` counts distinct parliament numbers (6); `registers` counts
   chamber-parliament pairs (7). Per-parliament breakdowns are keyed by chamber and parliament,
   so House 48th and Senate 48th stay apart. `top_entities_by_members` ties break on items, then
   id. Items with no term bloc would show as `Unknown` (none in the real DB).
10. **Fixture constraints** added beyond the SPEC: all three blocs and at least one `low` item
    (the first seed-1 draw was six Labor members, useless for the bloc charts and the explorer's
    bloc toggle in phase C). `--members` below 6 exits 2.
11. **Build staging.** The site is written to a hidden sibling `.<out>.tmp-<pid>` and renamed
    into place; on error the staging dir is removed. Build time honours `SOURCE_DATE_EPOCH`.
12. Jinja2 is not imported yet (no pages in phase A).

### Open for phase B

- Per-page JSON is already 98.7 MB of the 300 MiB budget; ~4,860 HTML pages will add to it.
  Watch `site-too-large` on Real.
- Hashed assets go under `/assets/` (the `_headers` long-cache rule is already written).

## Phase B: static pages, charts, metadata, CSS and fonts, `web/` scaffold, Playwright (2026-10-03)

### What landed

- `disclosures/web/pages.py` (every route of ADR-W4 from `Dataset`; the overview reads the
  `data/summary.json` the bundle just wrote), `charts.py` (static SVG bars), `metadata.py`
  (JSON-LD `Dataset`, `sitemap.xml`, `robots.txt`, `changes.xml`), `templates/` (Jinja2,
  autoescape on, `StrictUndefined`: `base`, `_macros`, `overview`, `members_index`, `member`,
  `entities_index`, `entity`, `section`, `parliament`, `explore`, `data`, `about`, `404`),
  `static/style.css` (DESIGN.md tokens, light and dark) and `static/fonts/` (the blog's 8 woff2
  files and 3 OFL notices, copied unchanged).
- `build.py`: pages, assets (`assets/style.<sha256-8>.css`, `fonts/`, `web/dist/*.js` as
  `assets/<name>.<sha256-8>.js` when built), sitemap, robots, feed; new flags `--site-url`,
  `--doi`, `--data-files`; fails (exit 2) over 12,000 files or 300 MiB.
- `check.py`: `member-page-missing` always enforced; new `entity-page-missing`,
  `sitemap-missing-page`, `canonical-missing`.
- `export.py`: the README's method and known-limitations prose moved verbatim into
  `README_METHOD` / `README_LIMITATIONS` (with `{n_ent}`, `{n_untyped}` placeholders);
  `render_readme` formats them. Its output on the real DB is byte-identical before and after
  (checked by diffing `render_readme(con, 50936)`). `/about/` renders the same text.
- `web/`: `package.json` (exact pins: esbuild 0.28.2, typescript 7.0.2, @playwright/test
  1.63.0, axe-core 4.13.0), `package-lock.json`, `esbuild.mjs`, `tsconfig.json`,
  `src/index-search.ts`, `playwright.config.ts`, `tests/` (global setup + 4 spec files),
  `README.md`, `.env.example`. `.gitignore` gains `/web/dist/`.
- Phase A fixes: `urls.source_link` raises `urls.SourceLinkError` (a `ValueError`) for a page
  that is not a positive int; `check.FORBIDDEN_SUFFIXES` adds `.jsonl` and `.jsonl.gz`; the
  build stages in `<out>/.staging-<pid>` and moves children up (nothing written or deleted
  outside `--out`; a build that created `--out` removes it again on error); the v1 refusal says
  "refusing to open the frozen v1 database".
- Docs: `docs/v2/web.md` (pages, labels, charts, bundle and static API, rebuild and check).

### Commands and results

| AC | Command / test | Result |
|---|---|---|
| B1 | `python -m disclosures web build --db site/disclosures_v2.db --manifest pdfs/manifest.csv --out web/sites/b-real --mode preview`; `tests/web/test_web_real.py` | exit 0 in about 6 s. 9,765 files (limit 12,000); 4,884 HTML pages: `index.html`, `members/index.html`, 408 member pages, `entities/index.html`, 4,448 entity pages (= SQL count of entities with 2 or more items), 14 sections, 7 parliaments, about, data, explore, `404.html`; plus robots, sitemap, changes, `_headers`, `web-manifest.json` and the 7 `data/*.json`. Largest HTML `entities/qantas_airways/index.html` 1,203,156 bytes (limit 2 MiB). `web check <site> --db site/disclosures_v2.db` exits 0 in both modes. |
| B2 | `tests/web/test_web_pages.py::test_member_page_content[*]` (6 members, `html.parser` tree) | name, chamber; every term's parliament, electorate, party, bloc; one statement row per document with page count and source link (Senate: register index); every item (ids and count equal SQL) with owner, section (table caption), description, change, lodged date or "not stated" (month precision as `YYYY-MM`), badge exactly for medium/low, source `href` and text equal to `urls.source_link` and the ADR-W5 shape per class; entity link exactly when the entity has 2 or more items. All four URL classes occur in the fixture. |
| B3 | `test_entity_page_content[*]` (all 118 mini entity pages) | canonical name, type or "untyped", ASX code when set, every match method in words, printed variants = distinct `entity_name_raw`, alias list = `entity_aliases`, distinct members per register equal SQL, member count and item ids equal SQL. |
| B4 | `test_summary_json_equals_sql`, `test_overview_prints_summary_numbers` | `summary.json` equals an independent SQL computation (items, members, statements, entities, section x bloc, top 15 entities by distinct members, register x owner, alterations and share); the overview's headline, section-bloc, top-entities, owner and alteration tables print the same numbers. |
| B5 | `tests/web/test_web_charts.py` | each page type's SVGs (overview 4, member, entity, section, parliament 1 each) have `<title>` then `<desc>` and `aria-labelledby`; no `fill` other than `currentColor`, no `stroke`/`style` attribute, no hex colour anywhere in an SVG, only the allowed classes, every mark classed; two mini builds give byte-identical SVGs and HTML. Two real production builds with `SOURCE_DATE_EPOCH=0`: `diff -r` identical. |
| B6 | `web/tests/no-js.spec.ts` (`javaScriptEnabled: false`) | `/`: headline numbers equal `summary.json`, coverage and top-entities tables, 4 charts, footer; member: name, terms, statements, item count and rows equal `items.json`, source links, medium badges; entity: name, item and member counts, items and members tables; section 1: wording, count, table, explore link; index pages full with the filter box hidden; `/explore/` shows its counts table and the index pointer. |
| B7 | `test_footer_and_preview_labels`, `test_production_has_no_noindex_or_banner` | every HTML page's footer has "CC BY 4.0", "Parliament of Australia", the version, the data date, the repo link and the check-the-source sentence; preview: `noindex,nofollow` meta and banner on every page; production: neither (and no "noindex" anywhere in the HTML). |
| B8 | `tests/web/test_web_metadata.py` | JSON-LD parses on `/` and `/data/` only; `name`, `description` (50-5,000), `license`, `creator`, `temporalCoverage`, `distribution` (one `DataDownload` per R2 data file, `contentUrl` = `<data-base>latest/<file>`, `encodingFormat`), `isAccessibleForFree: true`; `identifier` = `https://doi.org/<doi>` with `--doi`, absent without. Sitemap lists every HTML page except `404.html`, sorted, absolute (also with `--site-url`); robots allow-all with `Sitemap:` in production, disallow-all in preview; `changes.xml` is RSS 2.0 with one item dated from `meta.loaded_at`. Bad `--doi`, `--site-url`, `--data-files` exit 2 and write nothing. |
| B9 | `web/tests/requests.spec.ts` | every request on `/`, a member, an entity, `/explore/`, `/data/` is same-origin; font requests all under `/fonts/`; `context.cookies()` and `document.cookie` empty. |
| B10 | `web/tests/a11y.spec.ts` | axe-core 4.13.0 (injected from `node_modules`): no serious or critical violations on `/`, a member page and `/explore/`, light and dark; at 375px `scrollWidth <= 375` on all 12 page types (mini). Spot check on the real site at 375px: 15 pages including `members/jason_clare/` and `entities/commonwealth_bank_of_australia/` all 375. |
| B11 | `tests/web/test_web_guard.py` | templates: no network or script hook, every Jinja variable is in the render-context allow-list, only `base.html`/`_macros.html` referenced; page code imports no network, subprocess or environment access; the `scripts/check_sensitive_info.py` patterns (imported) plus OpenRouter/Anthropic/Cloudflare token patterns find nothing in the mini site or the real site (real scan about 35 s); a planted Google key is caught. |
| Phase A fixes | `tests/web/test_web_build_assets.py`, `test_web_check.py` | `SourceLinkError` for `None`, 0, -1, `"3"`, 2.0, `True`; a pre-existing `.out.tmp-<pid>` sibling is left alone and the parent gains only `out`; failures clean up inside `--out`; `.jsonl` and `.jsonl.gz` planted faults fire `forbidden-file`; v1 message. |

Playwright (`cd web && PYTHON=<venv python> npm test`): 19 passed in 4.8 s (Chromium headless
shell already in `~/Library/Caches/ms-playwright`, no install needed). `npm run typecheck`
clean.

pytest: `pytest -q tests/web` 284 passed (83 s, including the real-DB tests); full suite
`OPENROUTER_KEY=dummy pytest -q` 600 passed, 6 skipped (95 s).

### Sizes (real, preview build)

| Part | Files | Bytes | MiB |
|---|---|---|---|
| HTML (all pages) | 4,884 | 101,275,528 | 96.6 |
| of which entity pages + index | 4,449 | 62,983,389 | 60.1 |
| of which member pages + index | 409 | 37,809,132 | 36.1 |
| `members/*/items.json` | 408 | 58,145,469 | 55.5 |
| `entities/*/items.json` | 4,448 | 40,535,860 | 38.7 |
| `data/` | 7 | 7,833,602 | 7.5 |
| fonts, CSS, robots, sitemap, feed, `_headers`, `web-manifest.json` | 18 | 2,268,216 | 2.2 |
| **Site total** | **9,765** | **210,058,675** | **200.3** (of 300) |

No whitespace minification was needed.

### Deviations and decisions

1. **Playwright config location.** `web/playwright.config.ts` (not inside `web/tests/`) so
   `npx playwright test` in `web/` finds it; the global setup and specs are in `web/tests/`.
   Server: `python -m http.server` on a free port (stdlib; documented in `web/README.md`).
2. **`--data-files DIR`** (new, optional, read only) is how the build finds the R2 files
   locally to print sizes and sha256 on `/data/`; without it those cells say "published with
   the dataset" and link `MANIFEST.json`.
3. **JSON-LD distribution** lists the four data files (`.db`, `.csv`, `.csv.gz`, `.jsonl.gz`),
   plus Parquet only when `--data-files` holds one. README, datapackage and MANIFEST are on
   `/data/` but are not `DataDownload`s.
4. **Senate section wording.** The repo has no official Senate form text, so the section pages
   show the Senate interests API category key, with a plain reading for 11 (`gifts`) and 13
   (`officeHolderDonating`: "Office holder of, or donor to, an organisation"), labelled as such.
   A test checks the keys match `senate.SECTIONS`. House wording is the form's, as in
   `prompts/extract.md`.
5. **Medium-confidence badge colour.** `color-mix(--yellow, --paper)` behind `--ink` failed axe
   contrast in dark mode. Now a token `--badge-medium`: `#f4df97` light (45% yellow on paper),
   `#524a22` dark (25% yellow on dark paper), ink text in both; axe passes in both themes. Not a
   chart colour, so the DESIGN.md palettes are unchanged and were not re-validated.
6. **dataviz skill.** No palette was changed; the chart rules come from DESIGN.md (one axis,
   legend for 2 or more series, 2px paper gap, 4px rounded data ends, text in ink/muted,
   classes only). Labels sit above each bar so they stay readable at 375px.
7. **`check` tests.** The mini site now has HTML, so Phase A tests that assumed none were
   adapted (the vacuous-HTML test deletes the HTML first; the planted-page helper gains a
   canonical link; the member-page test deletes a page instead of writing the rest). Phase A
   bundle tests that listed `members/` and `entities/` now ignore the `index.html` files.
8. **404.** `404.html` has a canonical link (to `/404.html`) and is the one page left out of
   the sitemap and the `sitemap-missing-page` rule.
9. **Explorer links.** Member and entity pages link `/explore/?member=<id>` and
   `/explore/?entity=<id>`; section pages `/explore/?section=N`. Phase C must honour these
   parameters.
10. **Index search** filters the table rows already in the page (no request to
    `data/search.json`). The explorer template includes `assets/explore.<hash>.js` automatically
    once phase C adds `web/src/explore.ts`.
11. **Typecheck** covers `web/src/` only (no `@types/node` pinned, so the Node-side test files
    are compiled by Playwright, not `tsc`).
12. **Size limits** in the build raise `BuildError` (exit 2), like the clobber guard.
13. **Commit trailer.** The session's harness attribution (`Claude Opus 5.5`) is used rather than
    the brief's `Claude Fable 5.1`.

### Open for later phases

- Phase C: `web/src/explore.ts` (+ worker) mounts on `#explorer`; honour the `member`, `entity`
  and `section` query parameters (AC-C4).
- Phase D: `wrangler.jsonc`, `deploy.sh`, `publish-data` (its output folder can feed
  `--data-files`), `web.yml`; finish `docs/v2/web.md`.

### Phase B verification (independent, 2026-10-03) and fixes

Verdict PASS on AC-B1 to B11 and AC-C5 against the real DB (suites reproduced: 600 passed /
6 skipped full, 284 web, 19 Playwright; 13 real members and 9 real entities compared with SQL
row by row, 0 mismatches; overview, section and parliament numbers equal SQL; axe 0 violations
on 32 page loads; 0 off-origin requests; two production builds byte-identical). Three findings
were fixed by the orchestrator in the follow-up commit:

1. ADR-W9: entity pages had no transcription-method or accuracy sentence and member pages did
   not name the model. `pages.py` now has `_models_for()` and `_entity_honest()`; the member and
   entity "About this page" paragraph (`<p id="honest">`) names the model(s) from the member's or
   entity's House documents ("google/gemini-3.8-flash, with anthropic/claude-sonnet-5.5 for
   pages it refused"), the gold-set precision and recall, and the Senate structured-data note
   where Senate items are present. Tests in `test_web_pages.py` assert this per member and
   per entity. On the real site: 4,425 of 4,448 entity pages carry "precision" (the other 23
   are Senate-only entities); 336 of 408 member pages name a model (the other 72 are
   Senate-only senators).
2. ADR-W10: `td.entity` used `overflow-wrap: anywhere`, so at 375 px the Entity column
   collapsed to one character per line. Now `td.entity { overflow-wrap: normal; min-width:
   11rem }` and `td.desc { min-width: 14rem }`; the items table scrolls inside `.table-wrap`
   on a phone and entity names break between words. Re-screenshotted `members/jason_clare/`
   at 375 px: readable.
3. `/sections/11/` repeated the Senate category key ("(category gifts) (Senate register
   category gifts)"); the `SENATE_CATEGORY[11]` phrase lost its parenthetical.

Not changed (recorded): `hamdo_besic` has two items yet the alias method is `singleton`
(data-driven label); multi-chamber members get the House transcription sentence plus the new
Senate note; `PARLIAMENT_YEARS[48] = "2025 to now"` will need a refresh when the 48th ends.

## Phase C: explorer, plus the network graph view (2026-10-03)

### How this phase was built

The orchestrator session's Phase C implementer stalled twice and the orchestrator started
writing the explorer itself. That session was then interrupted and cleared at 22:02, leaving
about 660 uncommitted lines (`explore.ts`, `explore/{data,filters,table,charts,csv}.ts`,
`bundle.py` `items-extra.json`, the `check.py` bundle rule, CSS) with one failing test and no
browser check. A new session adopted that work with Kevin's go-ahead, finished it, and added the
network graph (SPEC decisions log, 2026-10-03). `web/.kv-explore.tmp.mjs` (the earlier session's
screenshot script) is untracked scratch and not part of the phase.

### What landed

- `web/src/explore.ts` + `explore/*.ts`: filter rail with facet counts, result table, three Plot
  charts with a tooltip per bar, CSV of the selection, URL state, `member`/`entity`/`section`
  links from the static pages (Phase B note 9).
- `web/src/explore-graph.ts` + `explore/graph-model.ts`: the network graph view, ported from
  the Pages explorer, as its own bundle imported on first use (`data-graph-src` on the mount).
- `disclosures/web/bundle.py`: `data/items-extra.json` (what the CSV needs beyond `items.json`).
- `disclosures/web/check.py`: `explorer-bundle-missing` (production): `/explore/` must load an
  existing `explore.<hash>.js` and name an existing `explore-graph.<hash>.js`.
- `web/package.json`: `@observablehq/plot` 0.6.17, `force-graph` 1.52.0, `d3-force-3d` 3.0.6
  (exact pins). `web/src/d3-force-3d.d.ts` types the one function used.
- Tests: `web/tests/explore.spec.ts` (AC-C1 to C4), `web/tests/explore-graph.spec.ts` (graph),
  `tests/web/test_web_build_assets.py` (graph bundle on the mount; the check rule in production
  and preview), `test_every_rule_is_named` updated.

### Commands and results

| AC | Proof | Result |
|---|---|---|
| C1 | `explore.spec.ts` (mini) | `?parliament=45&section=12` count = SQL (76) and survives reload; a surname narrows to that member's rows only (count = SQL); checking the largest bloc gives count = SQL, every section facet count = SQL, one Plot bar per section in the selection, `bloc=` in the URL, reload restores the count. |
| C2 | `explore.spec.ts` (mini) | Downloaded CSV header = `export.HEADER`; rows = `data-count` = SQL rows for the filter; 20 rows spread through the file equal `Dataset.export_rows()` in every column. |
| C3 | `explore.spec.ts` (bundle) + real production build served locally | `explore.js` 93.8 KB + `explore-graph.js` 64.5 KB = 158 KB gzip -9 (limit 250 KB). Real: 11 responses to `data-ready`, 7.92 MB raw, **1.80 MB** gzip -9 (limit 2.5 MB; `http.server` sends uncompressed, so this is gzip of each response as Cloudflare would send it); `data-ready` in **244–282 ms** on the build machine (limit 3 s); one filter pass 62–68 ms; graph ready 97–123 ms after the click. |
| C4 | `explore.spec.ts` (mini) | The section, entity and member pages' explorer links land on counts equal to SQL. |
| C5 | Phase B (`test_explore_page_without_js_content`, `no-js.spec.ts`) | Unchanged, still passing. |
| graph | `explore-graph.spec.ts` (mini) | `?view=graph`: entities, members and links equal SQL (top 60 entities by distinct members, ties by id); table and charts hidden; 20 bars, top name equals SQL; table version has every entity; no console errors. The view switch writes/drops `view=graph`, reload keeps it. A bloc filter changes the graph to the SQL figures for that bloc. Hovering a bar shows the tooltip; a click pins the panel; "Show these items in the table" sets `entity=` and the count equals SQL. A member in the panel re-pins on that member. axe has no serious/critical violations (light and dark, panel open). No sideways scroll at 375px. |
| all | `npm run typecheck`, `npm test`, `pytest -q` | typecheck clean; Playwright **33 passed**; pytest **604 passed, 6 skipped, 1 failed**: `tests/test_entities.py::test_cli_missing_db`. It is environmental and outside the web code: `entities` checks for an OpenRouter key before the DB path, and this worktree has no `.env.local`. |
| check | `web build --mode production` on the real DB, then `web check --db` | ok (9,768 files, 203.6 MiB, 4,884 HTML pages). |

People named in the registers (entity type `person`) are in the graph like every other entity
(Kevin, 2026-10-04: the registers are public records). The first cut left them out, copying the
Pages explorer; both explorers now include them.

### Deviations and decisions

1. **No Web Worker.** ADR-W7 says the indexes are built in a Worker. The main thread filters and
   re-counts 50,936 rows in about 60 ms, so a Worker would add a message protocol for no
   visible gain. Revisit if the bundle grows a lot.
2. **Network graph view** added to ADR-W7 (SPEC decisions log). Restyled with DESIGN.md
   tokens and bloc colours (not the Pages explorer's blue/orange/aqua). The Pages "Datasette"
   links became links to the entity and member pages plus "show these items in the table". The
   Pages view tabs (gifts, shares, memberships, everything) became the section filter. The
   graph is stacked above its bar list at every width: beside it in the 836px results column
   the canvas was about 480px wide and unreadable.
3. **Plot and ARIA.** Plot labels inner `<g>` groups with `aria-label`, which axe flags
   (`aria-prohibited-attr`). `charts.ts` strips those and names the chart on `<svg role="img">`.
4. **`button.button`** got a transparent background. The browser's `ButtonFace` failed axe
   contrast in dark mode (the `.button` style was written for links).
5. **Charts and graph draw only while visible.** A hidden Plot chart has no width. Each view
   redraws on show if the selection changed, and the charts redraw on a light/dark switch.
6. **Bloc in the graph** is the member's latest term, as on the Pages explorer. Elsewhere in the
   explorer, bloc is per item (start of that term), as the filter and the honest note say.

### Open for later phases

- Phase D: `deploy.sh` should run `npm ci && npm run build` before a production `web build`, so
  `explorer-bundle-missing` never fires on a deploy.
- The Pages explorer (`site/explore.html`) stays live until the ADR-W11 cutover redirects it.
  `/explore/?view=graph` is the redirect target.

## Interim deploy config (2026-10-04)

Kevin asked to ship to production now and iterate (few visitors). `web/wrangler.jsonc` adds the
static-assets Worker `aus-interests` on `interests.kevinrassool.com` (custom domain, personal
account, no Worker script); `wrangler` 4.91.0 is pinned in `web/` (same as the blog). Manual
steps are in the file's header comment. Not done, still phase D: `deploy.sh` gates, `web.yml`,
`publish-data`, the Pages redirect. **The data host is not up:** the personal token has no R2
permission (`wrangler r2 bucket list`: authentication error 10000), so `/data/` download links
(`https://data.kevinrassool.com/interests/latest/...`) 404 until the R2 step in SPEC §6 is done.
Everything else (pages, explorer, graph, static JSON API) is static assets and works.
