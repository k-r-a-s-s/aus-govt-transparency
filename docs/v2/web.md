# The public site (`python -m disclosures web`)

A static site generated from `disclosures_v2.db` for `interests.kevinrassool.com` (SPEC:
`plans/2026-10-03-public-site/SPEC.md`). This page covers what exists after phase C: the pages,
the labels they carry, the explorer, the data bundle and static API, and how to rebuild and check
the site. Deploying (phase D) and the SQL console (phase E) are added here when they land.

## Rebuild and check

```
python -m disclosures web build --db site/disclosures_v2.db --manifest pdfs/manifest.csv \
    --out web/sites/preview-<date> --mode preview
python -m disclosures web check web/sites/preview-<date> --db site/disclosures_v2.db
```

`build` options:

| Option | Default | Meaning |
|---|---|---|
| `--db` | `disclosures_v2.db` | The v2 DB, opened read-only. The frozen v1 DB is refused. |
| `--manifest` | `pdfs/manifest.csv` | Source URLs by sha256. A document without a URL, or with a URL of no known class, fails the build (exit 2). |
| `--out` | (required) | Must not exist or be empty. The site is staged in `<out>/.staging-<pid>` and moved up when complete; nothing is written or deleted outside `--out`. |
| `--mode` | `preview` | `preview` adds `noindex` (meta and `X-Robots-Tag`), a "Preview build, not the published dataset" banner and a disallow-all `robots.txt`. `production` has none of them. |
| `--data-base` | `https://data.kevinrassool.com/interests/` | Where the R2 data files live; `/data/` and the JSON-LD link `<data-base>latest/<file>`. |
| `--site-url` | `https://interests.kevinrassool.com` | The public origin, for canonical URLs, Open Graph, `sitemap.xml`, `robots.txt` and JSON-LD. |
| `--doi` | none | A dataset DOI (`10.x/y` or `https://doi.org/...`). Adds it to the footer, the cite block and the JSON-LD `identifier`. |
| `--data-files` | none | A local folder holding the R2 files (e.g. a `publish-data` output). When given, `/data/` prints each file's size and sha256; otherwise those cells say "published with the dataset" and point at `MANIFEST.json`. Read only. |

The build is deterministic: the same inputs give the same bytes, except `built_at` in
`web-manifest.json` (set `SOURCE_DATE_EPOCH` to pin it). It fails (exit 2) if the site would
exceed 12,000 files or 300 MiB.

Browser JavaScript is optional. Run `npm ci && npm run build` in `web/` first to include it;
the build copies `web/dist/*.js` to `assets/<name>.<sha256-8>.js`. Without it every page still
works (the index filter box simply stays hidden). See `web/README.md` for the Playwright tests.

`check` exits 0 when every rule passes, 1 naming each failed rule, 2 on bad input. Rules:
`forbidden-file` (`.db`, `.sqlite`, `.sqlite3`, `.csv`, `.csv.gz`, `.jsonl`, `.jsonl.gz`,
`.parquet`), `file-too-large` (20 MiB), `too-many-files` (12,000), `site-too-large` (300 MiB),
`html-too-large` (2 MiB), `footer-missing`, `external-asset` (any absolute or
protocol-relative script, stylesheet or preload URL), `noindex-in-production`,
`noindex-missing-in-preview`, `manifest-mismatch`, `canonical-missing`,
`sitemap-missing-page`, and with `--db`: `member-json-missing`, `member-page-missing`,
`entity-page-missing` (every entity with 2 or more items).

Real build (2026-10-03, Mac): about 6 s; 9,765 files, 200.3 MiB (HTML 96.6 MiB in 4,884 pages;
per-page JSON 94.1 MiB; `data/` 7.5 MiB). The largest page is `entities/qantas_airways/`
(1.2 MB).

## Pages

| Route | Shows |
|---|---|
| `/` | Two sentences on what this is; headline numbers (items, members, statements, parliaments, entities, data date); coverage table; four charts, each with its table: items per section by bloc, top 15 entities by distinct members, items per register by owner, alteration share per register; entry points; cite and licence summary; schema.org JSON-LD. |
| `/members/` | Every member: name, chamber, parliaments, electorate or state, party per term, item count. Filter box with JS. |
| `/members/<member_id>/` | Terms (parliament, electorate or state, party and bloc at the start of the term, items); statements (date, page count, items, source link); a chart of items per section; every item grouped by section (parliament, owner, entity, description, change, lodged date, confidence badge, source link); alterations by date lodged; how the items were made; link to `items.json`. |
| `/entities/` | Entities with 2 or more items: name, type, ASX code, members, items, match method; filter box with JS; the number of one-off names that have no page. |
| `/entities/<entity_id>/` | Name, type (or "untyped"), ASX code, match method in words; the printed names folded into it (with item counts) and the alias-table entries; distinct members per register by bloc (chart and table); members naming it; every item grouped by section; link to `items.json`. |
| `/sections/<1-14>/` | The House form's wording and the Senate register's category; items per register by bloc (chart and table); top entities in the section; items with no entity; link to `/explore/?section=N`. |
| `/parliaments/<chamber>-<n>/` | `house-43` to `house-48` and `senate-48`: years, members, statements, items, alterations, statement dates, source and model; the register's known limitations; items per section (chart and table); members with party, bloc and items. |
| `/explore/` | Without JS: the counts per register and per section, and a pointer to the member and entity indexes. With JS: the explorer (below). |
| `/data/` | Downloads (version, size, sha256, licence) on the data host; Datasette Lite button; Kaggle link; field dictionary (from `export.COLUMNS`); the static API (routes, example `curl`, CORS, `web_bundle_version`); datapackage, JSON-LD and change-feed links; how to cite; licences and attribution. |
| `/about/` | What the registers are; method and gold-set accuracy, prompt versions and known limitations (the Kaggle README's text, from `export.README_METHOD` and `export.README_LIMITATIONS`); how to read the labels; contact; changelog. |
| `/404.html` | Not found, with links to the indexes. |

Plumbing: `robots.txt`, `sitemap.xml` (every HTML page except `404.html`, absolute URLs),
`changes.xml` (RSS 2.0, one entry per dataset version, dated from `meta.loaded_at`), `_headers`,
`web-manifest.json`.

Every HTML page has a title, description, canonical URL, Open Graph tags,
`<meta name="color-scheme" content="light dark">`, the two main fonts preloaded, one
content-hashed stylesheet, a skip link, the header (`kr.` wordmark linking to
kevinrassool.com; nav Overview, Explore, Members, Entities, Data, About with `aria-current`),
and the footer (`<footer class="site-footer">`): "Transcribed from the Parliament of Australia
registers. Check the source before relying on any item.", the dataset version and data date,
CC BY 4.0 for the dataset and CC BY-NC-ND 4.0 for the source documents, and links to the about
page and the repository. Every asset URL is root-relative and same-origin; the pages make no
third-party request and set no cookie.

## Explorer (ADR-W7, phase C)

`web/src/explore.ts` mounts on `<div id="explorer">` and loads `data/items.json`,
`members.json`, `entities.json`, `documents.json` and `summary.json` once; filtering runs on
the main thread (about 60 ms for 50,936 rows).

- **Filters:** text (member, entity canonical and printed name, description), chamber,
  parliament, bloc, party (start of term), section, owner, entity type, change, confidence.
  Facet counts are over the selection with that facet's own filter lifted.
- **URL state:** every filter is in the query string, multi-values comma-separated:
  `?parliament=47&section=1,2&bloc=Coalition&q=qantas`. Section, member and entity pages link
  in with `section=N`, `member=<id>`, `entity=<id>`. `view=graph` opens the network graph.
- **Table and charts view:** the result table (same columns and links as the member page, 200
  rows then "Show more") and three Observable Plot charts with a tooltip per bar: items per
  section by bloc, distinct members per register, top entities.
- **Network graph view** (`web/src/explore-graph.ts`, its own bundle, imported from
  `data-graph-src` the first time the view opens): the 60 entities the most members
  declared in the selection, the members who declared them, and a link per (member, entity).
  Every entity type is included. Member dots take the bloc colour of
  their latest term, organisations are grey. Hover highlights neighbours. A click pins a
  panel with the stats, the members or organisations, the entity or member page, and "show
  these items in the table", which sets the `entity` or `member` filter. Beside it is a bar
  list of the top 20 by members, split by bloc, linked to the graph, with a table version.
  Ported from the GitHub Pages explorer (`disclosures/explore.py`,
  `site_assets/explore.html`), which reads `explore.json` and has fixed views (gifts and
  travel, shareholdings, memberships, everything). Here the filters do that job.
- **Everyday banking in the visualisations:** a checkbox, on by default, leaves sections 6
  (Liability: mortgages, credit cards; 3,685 items) and 8 (Account; 4,521 items) out of the
  charts and the graph. Those items otherwise push the big four banks to the top of every view,
  and they say little about influence. The table, counts and CSV keep them. Turning it off adds
  `banking=show` to the URL. A banking section picked in the section filter is drawn regardless.
- **CSV of the selection:** every published column (`export.HEADER`), built in the browser
  from the bundle plus `data/items-extra.json` (item ids, entity names/types/ASX codes, match
  methods, categories), which is fetched only on download.
- **Budget (AC-C3):** `explore.js` ≈ 94 KB gzipped (with Plot), `explore-graph.js` ≈ 64 KB
  (force-graph). The ADR-W7 limit is 250 KB for both together. A production `web check` fails
  (`explorer-bundle-missing`) if either bundle is missing from the site.

## Labels (ADR-W9)

- **Version**: `v2.<loaded_at date>` from `meta`, e.g. `v2.2026-10-02`.
- **Confidence**: items with `medium` or `low` extraction confidence carry a badge with the word;
  `high` is not marked.
- **Change**: `initial` "Initial statement", `added` "Added", `removed` "Removed", `varied`
  "Varied", `unknown` "change not stated".
- **Owner**: "Self", "Spouse or partner", "Dependent child", "Not stated".
- **Lodged**: the date; month-only dates as `YYYY-MM`; "not stated" when none is printed.
- **Party and bloc** are always "at the start of the term".
- **Senate**: 48th parliament only, the senator's own interests only.
- **Source links** (ADR-W5, `disclosures/web/urls.py`): House 44th to 48th PDFs and the House
  48th register API link to `<url>#page=N` ("page N"); the House 43rd APH redirector links to
  the URL as given ("page N of the PDF"); Senate items link to the Senate register ("Senate
  register (structured source, no page)").
- **Entity links** appear only when the entity has a page (2 or more items). Match method in
  words: "curated alias table", "matched by the ASX listed-companies list", "LLM grouping of
  spelling variants".
- **Section wording**: the House form's 14 sections; the Senate category is the Senate
  interests API key with a plain reading for 11 and 13, the two worded differently.
- Copy describes what was declared. Counts are counts of items, not of value. No page infers
  wealth, conflict or wrongdoing.

## Charts

Static SVG, inline in the page, from `disclosures/web/charts.py`: horizontal bars, stacked by
bloc or owner where there is more than one series, one value axis, a legend for two or more
series, the row total as a direct label, a 2px gap between stacked segments, 4px rounded
data ends. Each has `<title>` and `<desc>` (the desc lists every row's value). Colour comes only
from CSS classes (`bloc-labor`, `bloc-coalition`, `bloc-crossbench`, `seq-1` to `seq-4`) and
`currentColor`, so one SVG works in light and dark mode. Tokens and validated colours:
`plans/2026-10-03-public-site/DESIGN.md`.

## Data bundle and static API (ADR-W3)

Served with `Access-Control-Allow-Origin: *`:

| Path | Contents |
|---|---|
| `/data/items.json` | Every item, columnar: `{web_bundle_version, n, columns, dict, cols}`. String columns are dictionary-encoded (sorted values; `-1` is null); `dict.member` and `dict.document` are aligned with `members.json` and `documents.json`. Rows are in the published CSV's order. |
| `/data/members.json` | Members sorted by id, with terms, item count and statements. |
| `/data/entities.json` | Entities with 2 or more items, plus every typed or ASX-coded entity. |
| `/data/documents.json` | Statements sorted by sha256, with source URL and URL class. |
| `/data/search.json` | Member and entity names for search. |
| `/data/summary.json` | Every number the overview prints. |
| `/data/schema.json` | The bundle contract. |
| `/members/<member_id>/items.json` | The member's items as row objects with the published CSV columns. |
| `/entities/<entity_id>/items.json` | The same for an entity with 2 or more items. |

`web_bundle_version` is `"1"`; it changes whenever the layout of these files changes.

## Code

`disclosures/web/`: `cli.py` (subcommands), `dataset.py` (read-only DB and manifest),
`bundle.py` (JSON), `pages.py` (HTML, Jinja2 templates in `templates/`), `charts.py` (SVG),
`metadata.py` (JSON-LD, sitemap, robots, feed), `urls.py` (source links), `build.py`, `check.py`,
`fixture.py`; `static/` (CSS and the fonts with their OFL notices). The package imports only the
standard library and Jinja2. Tests: `tests/web/` (pytest) and `web/tests/` (Playwright).
