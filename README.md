# Australian Parliament Registers of Interests (Disclosures v2)

A pipeline and dataset covering every interest Australian federal MPs and senators disclosed in
the Registers of Members' and Senators' Interests. Each disclosed item (a shareholding, a gift, a
trip, a directorship, …) becomes one row, tagged with its register section (1–14), its owner
(self, spouse, dependent child), the source page, the member's party for that parliament, and a
standardised entity (company, organisation, trust).

Output: `disclosures_v2.db` (SQLite) and `exports/disclosures_v2.csv` (one row per item, plus a
Kaggle package in `exports/kaggle/`). Design and acceptance criteria:
`plans/2026-10-01-disclosures-v2/SPEC.md`.

## Public site

- **Live:** https://interests.kevinrassool.com (Cloudflare Workers static assets, personal
  account): a page per member and per entity, section and parliament pages, the explorer
  (filters, table, charts, CSV of a selection, and a member-entity network graph at
  `/explore/?view=graph`), and a static JSON API. Data files (DB, CSV, CSV.gz, JSONL.gz, README,
  datapackage, MANIFEST) are on R2 at https://data.kevinrassool.com/interests/latest/, with
  versioned copies under `interests/v2.<date>/`; Datasette Lite opens the DB from there.
- **Build and deploy:** `python -m disclosures web build|check|publish-data`, code in
  `disclosures/web/` and `web/`; steps in `web/wrangler.jsonc` and `docs/v2/web.md`; plan,
  ADRs and log in `plans/2026-10-03-public-site/`.
- **Interim:** GitHub Pages (https://k-r-a-s-s.github.io/aus-govt-transparency/, `site/` via
  `pages.yml`) stays up until it is turned into a redirect (ADR-W11). Build new site features in
  the Cloudflare build, not in `site/`. Kaggle:
  https://www.kaggle.com/datasets/kevrass/australian-parliament-registers-of-interests.

## Coverage

| chamber | parliament | members | statements | items |
|---|---|---|---|---|
| house | 43 (2010–2013) | 150 | 150 | 7,784 |
| house | 44 (2013–2016) | 152 | 152 | 8,511 |
| house | 45 (2016–2019) | 153 | 158 | 9,426 |
| house | 46 (2019–2022) | 153 | 153 | 7,461 |
| house | 47 (2022–2025) | 155 | 155 | 9,070 |
| house | 48 (2025–) | 151 | 151 | 6,704 |
| senate | 48 (2025–) | 76 | 76 | 1,980 |

50,936 items and 11,544 standardised entities (as of 2026-10-02). House statements are the APH
PDFs (archived registers for the 43rd–47th, the live register for the 48th), tracked in `pdfs/`
with `pdfs/manifest.csv` recording each file's source URL and sha256. Senate 48th statements come
from the senators' interests API (JSON, `pdfs/senate/48/`).

## How it works

1. **Scrape** (`scrape`): download statements and update the manifest.
2. **Extract** (`extract`): House PDFs are transcribed by `google/gemini-3.8-flash` (via
   OpenRouter) into a strict JSON schema, with `anthropic/claude-sonnet-5.5` taking any pages
   Gemini refuses. On a 12-PDF hand-checked gold set this scored F1 0.987. Senate JSON is mapped
   directly, no LLM.
3. **Validate** (`validate`): schema plus completeness (every page covered, every item on a real
   page).
4. **Load** (`load`): validated extractions into `disclosures_v2.db`; members matched across
   parliaments and chambers to one `member_id`; party per term from `data/overrides/`.
5. **Entities** (`entities`): normalise names, then resolve via a curated alias table, the ASX
   listed-companies snapshot, a cached LLM grouping of variants, and finally one entity per
   one-off name.
6. **Export** (`export`): CSV, Kaggle package and the interim GitHub Pages site (`site/`; the
   Cloudflare site replaces it, see *Public site* above).

## Setup

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m pytest -q          # no network, no API calls
```

Paid steps (extraction, online entity grouping) need `OPENROUTER_KEY` in the environment or in
`.env.local` (copy `.env.example`; never commit it). Everything else runs offline.

## Commands

All commands run from the repository root (`python` = `.venv/bin/python`).

```sh
python -m disclosures --help

# Scrape: House 48th or Senate 48th; --verify re-downloads and checks every sha
python -m disclosures scrape --chamber house --parliament 48 [--verify]
python -m disclosures scrape --chamber senate --parliament 48

# Extract: House PDFs (paid; the configuration used for the published data)
python -m disclosures extract --source gemini --provider openrouter \
    --model google/gemini-3.8-flash --provider-order google-ai-studio/flex \
    --fallback-model anthropic/claude-sonnet-5.5 --ignore-providers azure --workers 8 <pdfs...>
# Extract: Senate API payloads (free)
python -m disclosures extract --source senate-json pdfs/senate/48/*.json

# Validate extraction JSON (exit 1 if any file is invalid)
python -m disclosures validate extractions/gemini-api/house

# Score predictions (or the v1 DB) against the gold set
python -m disclosures score --pred <dir> --gold eval/gold [--json out.json]

# Load validated extractions into disclosures_v2.db
python -m disclosures load --source gemini-api --source senate-json

# Entity standardisation (offline uses the committed LLM cache)
python -m disclosures entities --offline [--report eval/entities_report.md]
python -m disclosures entities --llm-dry-run      # how many uncached blocks / requests
python -m disclosures entities [--llm-limit 40] [--workers 8]   # online, paid

# Export: CSV + Kaggle package (+ Pages site)
python -m disclosures export [--site site] [--kaggle-id USER/SLUG] [--license NAME]
```

Extractions are idempotent: files that already validate are skipped (`--force` redoes them).
Full option lists are in `docs/v2/README.md`; topic docs: `docs/v2/scrape.md`,
`docs/v2/extraction.md`, `docs/v2/loading.md`, `docs/v2/entities.md`,
`docs/v2/senate_source.md`.

## Refreshing

```sh
python -m disclosures refresh --dry-run      # list new/changed House 48th + Senate statements; writes nothing
python -m disclosures refresh                # scrape, extract only those, load, entities
python -m disclosures export --site site     # regenerate the CSV, Kaggle package and site
```

`refresh` compares downloaded files with the sha256s in `pdfs/manifest.csv` and extracts only
new or changed statements. New House members also need override rows
(`python -m disclosures.members --chamber house --parliament 48`, see `data/overrides/README.md`).

## Data dictionary

The field dictionary for the published CSV (33 columns), the method and the limitations are in
`exports/kaggle/README.md` (generated from `disclosures/export.py`, `COLUMNS`). The database
schema and item-id scheme are in `docs/v2/loading.md`.

## Known limitations

- **Senate before the 48th parliament is missing.** The senators' interests API serves current
  senators only; earlier registers exist only as tabled volumes (`docs/v2/senate_source.md`).
- **Transcription is not perfect.** Expect roughly 1–2% of items missed or misread, more on the
  scanned 43rd–45th registers; `extraction_confidence` flags doubtful items. Check anything
  important against the source (`source_url`, `page`).
- **Two prompt versions.** Most 43rd–47th House statements used prompt v0; only the 7 found
  with un-itemised attachments were re-run on v1. A few v0 statements may still describe an
  attachment in a single item.
- **One-off entities are untyped**, and ASX matching is name-based.
- **Party** is the party at the start of each term; mid-term defections are not tracked.

## Layout

| Path | What |
|---|---|
| `disclosures/` | the v2 package and CLI |
| `pdfs/` | source statements + `manifest.csv` |
| `extractions/` | validated extraction JSON, `<source>/<chamber>/<parliament>/<stem>.json` |
| `data/overrides/` | member identity and party-per-term tables |
| `data/entities/`, `data/reference/` | curated aliases, generic terms, LLM cache, ASX snapshots |
| `eval/` | gold set, baselines, entity report |
| `exports/`, `site/` | published CSV, Kaggle package, interim Pages site (frozen until the Cloudflare cutover) |
| `docs/v2/` | how each stage works |
| `tests/` | pytest suite |

## v1 snapshot

`disclosures.db` is the frozen v1 database, kept read-only as a snapshot for comparison (the
`score --v1` baseline). v1's pipeline scripts were removed once v2 replaced them (`git show 66377df:src/...` to
read them).

## Source and licence

Parliament of Australia, Register of Members' Interests and Register of Senators' Interests
(aph.gov.au). Material on aph.gov.au is published under
[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/), credited as "Parliament
of Australia website"; the PDFs in `pdfs/` are unaltered copies under that licence. The
published dataset (`exports/`, `site/`, Kaggle) is
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) to the extent we hold rights in it:
it records the facts the statements disclose, not the statements themselves.
