# Disclosures v2 — SPEC

Status: DRAFT, awaiting sign-off · Author: Fable planner · Date: 2026-10-01
Progress (2026-10-03): Phases 1–4 built and verified; Phase 5 built up to G4. Gates G1–G3 passed; every AC in §3 passes (`eval/final_acceptance.md`). Waiting on cold verification (V5), then G4 (Kevin) — see `HANDOFF.md` and `DECISIONS.md`.
Repo: `aus-govt-transparency` (public, `github.com/k-r-a-s-s/aus-govt-transparency`) · Branch: `v2-upgrade`
Owner / human-in-the-loop: Kevin

---

## 0. Read this first (cold-start context)

This repo turns the Australian Parliament's Register of Members' Interests (one PDF per MP per
Parliament, published by APH) into a queryable SQLite dataset. v1 was built in early 2025 with
Gemini 2.0 Flash and "just works", has had public interest (Reddit), but has data-quality problems
that a reviewer found on 2026-10-01. v2 rebuilds extraction, entity standardisation, coverage and
publishing **alongside** v1 — v1's `disclosures.db` is left untouched.

### Current state (measured 2026-10-01)

- `pdfs/{43,44,45,46,47}/*.pdf` — **774 PDFs, 13,205 pages**, median 14 pp, p90 29, max 81, largest
  file 18.7 MB. ~65% of pages have **no text layer** (scanned typed forms / handwritten alteration
  notices) and must be read as images. All 774 are tracked in git (and stay that way — ADR-8).
- `disclosures.db` (v1, SQLite, 14 MB): `mps` 338, `disclosures` 29,223, `entities` 11,718.
  sha256 at spec time: `5e6a18cc80a7123276e8aa3d229a370733cd9aeec5f983706e77b85199ae5079`.
- v1 defects (verified):
  - Gemini output not schema-enforced (Pydantic models in `src/parsing/pdf_gemini_pipeline.py`
    are never passed to the API) → ~380 rows have subcategory values in `category`; 15 malformed
    dates (`N/A`, `Unknown`, a 2027); 140 exact duplicate rows.
  - Post-processing (`post_process_disclosures`) keys on fields that no longer exist → no-op.
  - Truncated responses return `{}` silently; ~15 PDFs on disk have no rows.
  - No `parliament`, `page`, `owner` (self/spouse/dependent), or alteration fields; parliament is
    inferred from inconsistent filenames (`leeser46p.pdf`, `_46p.pdf`, `45p_2.pdf`).
  - `raw_description` often holds a whole list (e.g. 19 companies) duplicated on every row.
  - Entity dedup is weak exactly where it matters: `CBA` (181) / `Commonwealth bank` (185) /
    `COMMONWEALTH BANK OF AUSTRALIA` (83); `NAB` (261) / `NATIONAL AUSTRALIA BANK` (139); `ANZ` /
    `Australian and New Zealand Banking Group`; `Virgin` / `Virgin Australia Airlines Pty Ltd` are
    all separate entities. 3,894 rows have no entity.
  - `src/main.py` is broken (imports nonexistent `gemini_pdf_processor`, half-deleted function).
    ~450 lines of `src/preparation/db_handler.py` (≈ lines 761–1213) query columns that don't
    exist. `src/cleaning/link_entities.py` calls that broken code. README documents deleted
    scripts. `requirements.txt` lists the legacy `google-generativeai` SDK but code imports
    `google-genai`; `pydantic`, `sentence-transformers`, `networkx`, `python-louvain`, `torch`,
    `rapidfuzz` are imported but missing. **No tests exist.**
  - No 48th Parliament (elected May 2025), no Senate, no refresh mechanism.
- Reusable hand-curated assets in v1 (carry forward into `data/overrides/`):
  - `src/cleaning/get_mp_party_affiliations.py:39-76` `PARTY_MAPPING`, `:79-113`
    `MP_NAME_SPECIAL_CASES`, `:116-183` `FALLBACK_MP_PARTIES` (party data scraped from Wikipedia)
  - `src/cleaning/merge_duplicate_mps.py:29-50` manual MP merge overrides
  - `src/cleaning/add_political_bloc.py:18-31` `COALITION_PARTIES` / `LABOR_PARTIES`
  - `output/all_mps_most_recent_party.csv` (282 rows)

### External facts (verified live 2026-10-01 by research agent)

- **House register, current (48th)**: `https://www.aph.gov.au/senators_and_members/members/register`
  — one row per member (151 rows) with date / name+electorate / PDF link. PDFs at
  `https://static.aph.gov.au/-/media/03_Senators_and_Members/32_Members/Register/48p/{AB|CF|GJ|KN|OR|SZ}/{Surname}_48P.pdf?...`.
  Some rows instead link `https://interests-register-api-public.aph.gov.au/api/members/{id}/statement/{parl}`
  (undocumented; GET 200, HEAD 405).
- **47th archive** (slug breaks the older pattern):
  `https://www.aph.gov.au/Senators_and_Members/Members/Register/Previous_Parliaments/47th_Parliament_Register_of_Members_interests`.
  43rd–46th: `.../Register/Previous_Parliaments/{NN}P_Members_Interest_Statements`.
  **v1's `parliament_urls.py` maps "47th" to the current URL, which now serves the 48th — fix.**
- **APH WAF**: requests with no `User-Agent` get 403 / "Page Blocked by WAF". A normal desktop
  browser UA string is sufficient (no JS challenge). Same for the ASX CSV.
- **Senate register**: `https://www.aph.gov.au/Parliamentary_Business/Committees/Senate/Senators_Interests/Senators_Interests_Register`
  is a React SPA; alterations render inline per category; backend API host **not yet identified**
  (needs network-tab capture). Archives e.g. `.../Senators_Interests/Register44thparl`,
  `.../Register45thparl` (not fetched). Senate Form B (spouse/dependants) is **confidential** — only
  Form A (senator's own) is public.
- **Official House form — 14 numbered sections**, each a table with rows **Self / Spouse/Partner /
  Dependent Children** ("Not Applicable" when empty):
  1 Shareholdings · 2 Family and business trusts and nominee companies (2(i) beneficial interest,
  2(ii) trustee) · 3 Real estate (location, purpose) · 4 Directorships · 5 Partnerships ·
  6 Liabilities (nature, creditor) · 7 Bonds, debentures and like investments · 8 Saving or
  investment accounts · 9 Other assets > $7,500 · 10 Other substantial sources of income ·
  11 Gifts · 12 Sponsored travel or hospitality > $300 · 13 Memberships (potential conflict) ·
  14 Any other interests. Senate uses the same 1–14 numbering with differently-worded 11 and 13.
  Older parliaments' forms may word headings differently; numbering is assumed stable — **Phase 1
  must confirm on the gold set.**
- **ASX list**: `https://www.asx.com.au/asx/research/ASXListedCompanies.csv` (header line then
  `Company name, ASX code, GICS industry group`; ~2,050 rows; current listings only — no delisted).
- **Gemini**: `gemini-2.0-flash` was shut down 2026-06-01 (v1's default model no longer works);
  `gemini-2.5-flash` shuts down ~2026-10-16/20. Current GA Flash family is Gemini 3.x (research
  reported `gemini-3.8-flash` ≈ $0.75/$3.75 per MTok in/out, Batch API −50%; **unconfirmed — verify
  with `client.models.list()` and the pricing page at build time**). PDFs ≤ 50 MB / 1,000 pages;
  ~258 tokens/page; `response_schema` structured output supported.
  Order-of-magnitude cost of a full backfill on Gemini Flash: ~3.4M input + ~2–4M output tokens
  ≈ **US$10–20** (less with Batch).
- **Claude Code `Read` tool** reads PDFs at most **20 pages per call** (PDFs > 10 pages require the
  `pages` parameter) — workflow agents must read in page ranges.
- **Datasette Lite** (`https://lite.datasette.io/?url=<CORS-enabled .db URL>`) runs Datasette
  client-side; GitHub Pages serves the needed CORS header. No server, no billing.

---

## 1. PRD

### What we're building

A v2 pipeline that produces `disclosures_v2.db` (+ CSV/Kaggle export + a browsable Datasette Lite
site) covering the **House 43rd–48th Parliaments and the Senate 48th Parliament** (Senate archives
best-effort, see ADR-9), where:

1. Every row is **one registrable interest item**, tagged with the official **section (1–14)**,
   **owner** (self / spouse / dependent child), **page** in the source PDF, **alteration** status,
   and a **date with explicit precision** — traceable back to the PDF.
2. Extraction is **schema-enforced and complete**: every page of every PDF is accounted for, and a
   failed/truncated extraction is a visible error, never silent data loss.
3. Extraction is **source-agnostic**: any extractor (a Claude Code dynamic Workflow running on
   Kevin's subscription, or the Gemini API) writes the same validated JSON contract; the loader
   doesn't care which produced it.
4. Accuracy is **measured, not asserted**: a human-reviewed gold set and a scoring harness decide
   which extractor is used for the backfill, and prove v2 beats v1.
5. Entities are standardised **deterministically first** (normalisation, ASX ticker match,
   curated alias table for the top ~200), with an LLM only for the long tail, and each entity has
   a **type**.
6. A local `refresh` command re-scrapes, detects new/changed PDFs by sha256, and extracts only
   those.

### Why

Published numbers are currently wrong in ways a reader notices first (the big banks and airlines
are split across 2–3 entities each); the dataset stops in early 2025; v1's model is dead; and
nothing can be verified because there's no ground truth. v2 fixes correctness, coverage and
verifiability so the dataset can be re-shared with confidence.

### Users

- Public readers (Reddit/Kaggle/journalists) browsing or downloading the data.
- Kevin, maintaining it with an occasional manual refresh.

### In scope

- Phase 1: gold set (12–15 PDFs) + scoring harness + v1 baseline score.
- Phase 2: v2 extraction contract (JSON Schema), two extractors (Workflow/Claude subscription;
  Gemini API), bake-off on the gold set, backfill of all House PDFs with the winner, loader into
  `disclosures_v2.db`, MP/member table with carried-forward overrides.
- Phase 3: entity standardisation (normalise → ASX → curated aliases → LLM long tail), entity types.
- Phase 4: scraper v2 (UA header, correct URLs, manifest with sha256), House 48th PDFs, Senate
  48th, incremental `refresh`.
- Phase 5: CSV + Kaggle package export, Datasette Lite site on GitHub Pages (prepared, enabled by
  Kevin), README rewrite, requirements fix, deletion of dead v1 code.

### Non-goals

- No web app/API/frontend beyond Datasette Lite.
- No CI cron or unattended scheduled refresh (extraction may need the subscription; refresh is a
  local command Kevin runs).
- No Claude API arm in the bake-off (Kevin's decision; no Anthropic API key).
- No change to or deletion of v1 `disclosures.db`, and no git history rewrite (PDFs stay tracked).
- No monetary-value extraction (the register doesn't give values beyond thresholds).
- No ABN Lookup integration (optional future enrichment; not required).
- No re-use of v1's vector/Louvain entity grouping (`vector_match.py`) in the v2 path.
- Senate Form B data (confidential, not public) is out of scope by definition.
- Kevin performs all outward-facing actions: `git push`, enabling GitHub Pages, Kaggle upload,
  Reddit posts. The build prepares them; it never does them.

---

## 2. ADRs

### ADR-1 — Build v2 alongside v1 in a new package; v1 frozen until Phase 5 cleanup
- **Context:** v1 code is partly broken and its DB is the currently-shared artifact.
- **Decision:** New Python package `disclosures/` at repo root with one CLI
  `python -m disclosures <command>`. New DB `disclosures_v2.db`. v1 `src/` and `disclosures.db`
  are not modified in Phases 1–4. In Phase 5, v1 code is deleted except what's migrated (override
  tables → `data/overrides/*.csv`); `disclosures.db` stays in the repo as a v1 snapshot.
- **Rejected:** patching v1 in place (schema change touches everything; no tests to protect it);
  a separate repo (loses history/issues/Reddit links).

### ADR-2 — Extraction contract = JSON Schema generated from Pydantic, one file per PDF
- **Decision:** `disclosures/schema.py` defines Pydantic v2 models; `schema/extraction.schema.json`
  is generated from them (committed; a test asserts it's in sync). Every extractor writes
  `extractions/<source_id>/<chamber>/<parliament>/<pdf_stem>.json`. `python -m disclosures validate
  <path-or-dir>` validates files. The loader only reads validated files.
- **Document-level fields:** `schema_version` ("2.0"), `source_id` (e.g. `workflow-claude`,
  `gemini-api`), `model` (string), `extracted_at` (ISO), `pdf_path` (repo-relative), `pdf_sha256`,
  `page_count`, `pages_covered` (sorted list of 1-based page numbers the extractor looked at),
  `chamber` (`house`|`senate`), `parliament` (int 43–48, **from the manifest/path, not the model**),
  `member_name_as_printed`, `electorate_or_state`, `statement_date` (nullable ISO date),
  `items` (list), `extraction_notes` (free text, may be empty).
- **Item fields:** `section` (int 1–14), `subsection` (nullable string, e.g. `"2(i)"`, `"2(ii)"`),
  `owner` (`self`|`spouse`|`dependent_child`|`unknown`), `entity_name` (nullable — the
  company/bank/organisation/person/trust named, as printed), `description` (verbatim-ish text of
  **this item only**), `location` (nullable; section 3), `purpose` (nullable; section 3),
  `is_alteration` (bool), `change_type` (`initial`|`added`|`removed`|`varied`|`unknown`),
  `lodged_date` (nullable ISO date), `date_precision` (`day`|`month`|`year`|`unknown`),
  `page` (int, 1-based page of the **source PDF**), `confidence` (`high`|`medium`|`low`).
- **Rules (also in the extraction prompt):** "Not Applicable"/nil rows produce no item; a cell
  listing several companies produces one item per company; dates given as month/year use day 01
  with `date_precision="month"`; illegible text → best reading + `confidence="low"`; no invented
  fields.
- **Completeness:** a file is **invalid** if `pages_covered != [1..page_count]` or
  `pdf_sha256` doesn't match the file on disk.
- **Rejected:** keeping v1's invented category taxonomy (section numbers are the official
  standard and remove a whole class of classification errors; a derived `category` is computed in
  the loader for convenience — mapping table in ADR-6).

### ADR-3 — Gold set: agent drafts, Kevin reviews (human gate G1)
- **Decision:** 12–15 PDFs chosen by a script with a recorded seed, stratified to include: every
  House parliament 43–47 plus ≥1 House 48th once Phase 4 scraping lands (gold set may be extended
  then; not blocking), ≥3 PDFs > 30 pages incl. the 81-page max, ≥3 PDFs where > 70% of pages lack
  a text layer, ≥2 with spouse/dependent entries, ≥2 with many alteration pages. An Opus agent
  transcribes each **page by page** into the ADR-2 contract → `eval/gold/<stem>.json`, plus a flat
  review sheet `eval/gold/review.csv` (one row per item: stem, page, section, owner, entity_name,
  description, change_type, lodged_date, `kevin_ok` blank, `kevin_fix` blank). Kevin reviews;
  corrections are applied back to the JSON; files get `"reviewed_by": "kevin"` and
  `"reviewed_at"`. **Build pauses at G1** — nothing in Phase 2's bake-off runs until all gold files
  are reviewed.
- **Rejected:** two-agent consensus without a human (shared model blind spots); Kevin hand-labelling
  everything (too much of his time).

### ADR-4 — Scoring harness and metrics
- **Decision:** `python -m disclosures score --pred extractions/<source_id> --gold eval/gold
  [--json out.json]`. Per PDF, match predicted items to gold items with a maximum-weight bipartite
  matching (`scipy.optimize.linear_sum_assignment`) where a pair is eligible only if
  `section` equal (v1 baseline: section ignored, see below) and
  `rapidfuzz.fuzz.token_set_ratio(norm(entity_name or description))` ≥ 85 on the same
  normalisation as ADR-6 step 1, falling back to description when entity_name is null on either side.
- **Metrics (micro-averaged across all gold items):** item precision, recall, F1; and on matched
  pairs: `owner` accuracy, `change_type` accuracy, `is_alteration` accuracy, `page` accuracy
  (exact), `lodged_date` accuracy (exact on non-null gold). Report also per-PDF recall and the
  10 worst misses with page numbers. Section accuracy is implicit (section must match to pair);
  additionally report recall with section ignored, to separate "missed" from "mis-sectioned".
- **v1 baseline:** `python -m disclosures score --v1 disclosures.db --gold eval/gold` converts v1
  rows for the gold PDFs (by `pdf_filename`) to items with `section=None` and scores
  section-ignored recall/precision only.
- **Bar to backfill with an extractor (proposed defaults — Kevin may adjust at sign-off):**
  item recall ≥ 0.90, precision ≥ 0.90, owner accuracy ≥ 0.95, page accuracy ≥ 0.90,
  and section-ignored recall strictly greater than v1's.

### ADR-5 — Two extractors and the bake-off rule
- **Context:** Kevin wants to try Claude via his Claude Code subscription using dynamic Workflows,
  compared against the Gemini API. A Gemini Flash full backfill costs roughly US$10–20, so cost
  barely discriminates; reproducibility and accuracy do.
- **Extractor A — `workflow-claude`:** a saved, named workflow script
  `.claude/workflows/extract-disclosures.js` taking `args = { pdfs: [repo-relative paths],
  out_root: "extractions/workflow-claude", model?: "sonnet"|"opus" }`. It bundles PDFs into groups
  of ≤ ~120 pages, one agent per bundle (default model `sonnet`; `opus` selectable). Each agent:
  reads each PDF in ≤ 20-page `Read` ranges, writes the ADR-2 JSON, runs
  `python -m disclosures validate <file>`, fixes until valid (max 2 retries), and reports per-file
  status. The workflow returns a summary (files ok / invalid / failed, agent token totals,
  wall-clock). **Only the orchestrating session or Kevin can invoke Workflow; implementer
  subagents cannot.** The gold-set run fits under the default workflow size guideline; the full
  backfill needs ~110 agents and Kevin must raise "Dynamic workflow size" in `/config` first, then
  run it per parliament (~2,600 pages / ~22 agents each).
- **Extractor B — `gemini-api`:** `python -m disclosures extract --source gemini --model <id>
  <paths...>` using `google-genai` with `response_schema`/`response_mime_type=application/json`,
  temperature 0. PDFs are sent in chunks of ≤ 20 pages (PyMuPDF split) with the chunk's absolute
  page offset in the prompt so `page` is source-absolute; chunk results are merged and
  de-duplicated on (section, owner, normalised entity/description, page). Uploaded files are
  deleted after use. Retries on 429/5xx with exponential backoff; a chunk whose finish reason is
  max-tokens is re-split in half down to 1 page, then recorded as an error (file invalid, never
  silently partial). Model id is configurable (`GEMINI_MODEL` env / `--model`); default = newest
  GA Flash model reported by `client.models.list()` at build time, recorded in
  `plans/2026-10-01-disclosures-v2/DECISIONS.md`. **Gemini 2.x is banned** (2.0 is shut down,
  2.5 shuts down mid-Oct 2026): every Gemini call site (extractor and the ADR-6 long-tail LLM)
  goes through one `resolve_gemini_model()` helper that raises if the id matches `^gemini-[0-2]\.`,
  regardless of whether it came from `--model`, `GEMINI_MODEL` or the default. Kevin's existing
  `.env.local` sets `GEMINI_MODEL` (likely a 2.x id) — the build must update it to the chosen
  3.x id (value only; never print or commit the key). Token usage per file is written into
  `extraction_notes`-adjacent field `usage` (input/output tokens) for cost reporting.
  Optional `--batch` uses the Gemini Batch API.
- **Shared prompt:** both extractors use the same instruction text, `disclosures/prompts/extract.md`.
- **Bake-off rule:** run both on the gold PDFs; write `eval/bakeoff.md` with the ADR-4 metrics
  side by side + v1 baseline + cost (Gemini $ from tokens × verified price; workflow: tokens and
  wall-clock, "within subscription"). Among extractors that clear the ADR-4 bar, choose the higher
  F1; **if the F1 difference is < 2 points, choose `gemini-api`** (unattended, reproducible,
  cheap re-runs when the prompt changes). If neither clears the bar: iterate the prompt (max 2
  rounds), then stop and hand back with the report. **Human gate G2:** Kevin confirms the choice
  before the backfill.
- **Rejected:** Claude API arm (no key; Kevin's call); agentic multi-pass extraction for every
  page (cost/complexity; ADR-4 makes targeted re-runs possible instead).

### ADR-6 — Entity standardisation pipeline
- **Decision:** `python -m disclosures entities` runs, in order, writing `entities` and
  `entity_aliases` in `disclosures_v2.db`:
  1. **Normalise** `entity_name` (fallback: nothing — items without entity_name get no entity):
     NFKC, casefold, `&`→`and`, strip punctuation, collapse whitespace, strip leading `the`, strip
     trailing legal suffixes repeatedly (`pty ltd`, `pty limited`, `pty`, `ltd`, `limited`, `inc`,
     `plc`, `nl`, `corporation`, `corp`, `co`) — but **not** `group`/`holdings`/`bank`.
  2. **Generic descriptors** (`data/entities/generic_terms.csv`, e.g. `family trust`,
     `self managed super fund`, `smsf`, `n/a`, `nil`, `various`, `superannuation`) → alias row
     with `entity_id=NULL`, `method='generic'`.
  3. **Curated aliases** `data/entities/aliases.csv` (`alias, canonical_name, entity_type,
     asx_code`) — drafted by an agent covering the **top 200 normalised names by item count**
     after step 1, plus all variants of each of those found by token-set fuzzy search (≥ 90);
     Kevin spot-checks (human gate G3, light: he reviews the top 50 rows and any flagged
     uncertain rows).
  4. **ASX match** for section 1 items not resolved yet: exact normalised match against the ASX
     CSV company names (normalised identically) or exact ticker match (e.g. `BHP`, `CBA`) →
     `method='asx'`, `entity_type='listed_company'`, `asx_code` set. Snapshot saved to
     `data/reference/asx_listed_companies_<date>.csv`.
  5. **Long tail LLM** for remaining normalised names with ≥ 2 items: block by first token +
     rapidfuzz ≥ 85 candidates, ask the LLM (Gemini, schema-enforced) to merge/keep/type each
     block → `method='llm'`, `confidence`. Singletons with 1 item become their own entity
     (`method='singleton'`).
- **Entity types (enum):** `listed_company`, `private_company`, `bank_or_financial`, `airline`,
  `sporting_body`, `media_or_entertainment`, `government_body`, `union`, `political_party`,
  `association_or_ngo`, `education`, `person`, `trust_or_fund`, `other`.
- **Precedence:** curated > asx > llm > singleton. Every item's resolution is explainable via
  `entity_aliases.method`.
- **Rejected:** v1 MiniLM + Louvain (semantic similarity can't learn `CBA` = Commonwealth Bank);
  ABN Lookup now (needs GUID; low marginal value vs ASX + curated).

### ADR-7 — `disclosures_v2.db` schema
```
documents(pdf_sha256 PK, pdf_path, chamber, parliament, member_id, page_count, source_url,
          fetched_at, statement_date, extraction_source, model)
members(member_id PK, full_name, chamber)            -- stable slug, overrides applied
member_terms(member_id, chamber, parliament, electorate_or_state, party, political_bloc,
             PRIMARY KEY(member_id, chamber, parliament))
items(item_id PK, pdf_sha256 FK, member_id FK, chamber, parliament, section, subsection,
      category, owner, entity_name_raw, entity_id FK NULL, description, location, purpose,
      is_alteration, change_type, lodged_date, date_precision, page, confidence)
entities(entity_id PK, canonical_name UNIQUE, entity_type, asx_code NULL)
entity_aliases(alias_normalised PK, entity_id NULL, method, confidence NULL)
```
- `category` derived from section: 1→Shareholding, 2→Trust, 3→Real estate, 4→Directorship,
  5→Partnership, 6→Liability, 7→Bond/debenture, 8→Account, 9→Other asset, 10→Income, 11→Gift,
  12→Sponsored travel/hospitality, 13→Membership, 14→Other interest.
- `member_id` = slug of canonical full name, with v1 `merge_duplicate_mps` overrides and
  `MP_NAME_SPECIAL_CASES` carried forward as `data/overrides/member_aliases.csv`. Party per term
  from `data/overrides/party_*.csv` (carried forward) + v1's `all_mps_most_recent_party.csv`;
  48th-Parliament parties must be added (source: Wikipedia list for the 48th, same method as v1).
- Item ids are deterministic: sha1 of (pdf_sha256, page, section, owner, normalised
  entity/description, ordinal) so re-loads are idempotent.
- `python -m disclosures load --source <source_id>` rebuilds `disclosures_v2.db` from scratch
  from validated extraction files (+ entity tables if present); it never touches `disclosures.db`.

### ADR-8 — PDFs stay in git; a manifest records provenance
- **Decision (Kevin):** keep PDFs tracked. New PDFs go under `pdfs/48/` (House) and
  `pdfs/senate/48/`. Replaced versions overwrite in place, so **git history becomes the version
  history of each statement**. `pdfs/manifest.csv` columns: `chamber, parliament, member_name,
  electorate_or_state, source_url, listed_date, pdf_path, pdf_sha256, page_count, fetched_at`.
  GitHub's 100 MB per-file limit is far above the largest PDF (18.7 MB); the scraper refuses to
  write files > 95 MB and reports them.
- New-file naming: `{surname}{first-initial}_{NN}p.pdf` lowercase ASCII (existing v1 filenames are
  not renamed; the manifest is the source of truth for parliament/member, not the filename).
- **Rejected (by Kevin):** history rewrite; moving PDFs to Releases/object storage.

### ADR-9 — Senate: discover, then adapter; archives best-effort
- **Context:** the Senate register is a React SPA with an unidentified backend; data may be JSON
  rather than PDF.
- **Decision:** Phase 4 starts with a discovery task: capture the SPA's network calls (Playwright
  allowed as a dev dependency) and document the endpoint(s) and payload shape in
  `docs/v2/senate_source.md`. If structured JSON is available, write a **direct adapter** that
  maps it to the ADR-2 contract with `source_id='senate-json'` (no LLM; `page` = null is **not**
  allowed by the schema, so set `page=1` and record `extraction_notes="structured source"`; owner
  always `self`). If only PDFs/images are available, they go through the chosen extractor like
  House PDFs. Required: Senate **48th**. Senate 43rd–47th archives: attempt; if the archive format
  differs per parliament and would need > 1 additional adapter, document it in
  `docs/v2/senate_source.md` as a follow-up and stop there — this is an accepted outcome, not a
  failure.
- **Rejected:** skipping Senate entirely (Kevin wants it); HTML scraping of rendered pages
  without understanding the data source.

### ADR-10 — Publishing
- **Decision:** `python -m disclosures export` writes `exports/disclosures_v2.csv` (one row per
  item, joined with member/term/entity; human-readable column names) and
  `exports/kaggle/` (`disclosures_v2.csv`, `README.md` with field dictionary + method + known
  limitations, `dataset-metadata.json` per Kaggle CLI format). `site/` contains a static
  `index.html` (what this is, how to cite, links) and `disclosures_v2.db`, deployed by a GitHub
  Actions Pages workflow `.github/workflows/pages.yml` (on push to `main` touching `site/`).
  The page links to `https://lite.datasette.io/?url=<pages-url>/disclosures_v2.db`. Kevin enables
  Pages and pushes (human gate G4). (`docs/` is not used for Pages because it holds markdown docs.)
- **Rejected:** Vercel/Cloud Run/Fly Datasette (billing + maintenance for a static dataset).

### ADR-11 — Tooling
- Python 3.11 (installed). Dependencies in `requirements.txt` (pinned with `==`, regenerated);
  dev deps in `requirements-dev.txt` (`pytest`, `playwright` if needed). Tests in `tests/`,
  run with `python -m pytest -q`. Tests must not call live APIs or the network (fixtures and
  recorded responses only); live calls are behind explicit CLI commands.
- Secrets: `.env.local` (`GOOGLE_API_KEY`, `GEMINI_MODEL`); never committed (already gitignored).

---

## 3. Acceptance criteria

All commands run from the repo root in the project venv. "Pass" means exit code 0 unless stated.
`$V2 = disclosures_v2.db`.

### AC-0 Global
- **AC-0.1** `python -m pytest -q` passes, with ≥ 1 test per module in `disclosures/` (schema,
  validate, score, extract-gemini (mocked client), load, entities, scrape (recorded HTML), export).
- **AC-0.2** `shasum -a 256 disclosures.db` still equals
  `5e6a18cc80a7123276e8aa3d229a370733cd9aeec5f983706e77b85199ae5079` at the end of every phase.
- **AC-0.3** `python -m disclosures --help` lists subcommands: `scrape, extract, validate, score,
  load, entities, export, refresh`.
- **AC-0.4** `git ls-files pdfs | wc -l` ≥ 774 (no PDF removed from tracking).
- **AC-0.5** No secret in tracked files: `git grep -nE 'AIza[0-9A-Za-z_-]{30,}'` returns nothing.

### AC-1 Gold set & harness (Phase 1)
- **AC-1.1** `schema/extraction.schema.json` exists and `python -m pytest -q tests/test_schema.py`
  includes a test that regenerating it from `disclosures/schema.py` produces an identical file.
- **AC-1.2** `eval/gold/selection.json` lists 12–15 PDFs with the seed and the stratum each
  satisfies; a test asserts the ADR-3 strata are all covered (parliaments 43–47 each present,
  ≥ 3 with > 30 pages, ≥ 3 with > 70% no-text-layer pages, ≥ 2 spouse/dependent, ≥ 2
  alteration-heavy — the latter two judged from the gold content).
- **AC-1.3** Every `eval/gold/*.json` passes `python -m disclosures validate eval/gold` and has
  `reviewed_by == "kevin"` (gate G1). `eval/gold/review.csv` exists.
- **AC-1.4** `python -m disclosures score --pred eval/gold --gold eval/gold` reports precision =
  recall = F1 = 1.0 and all field accuracies = 1.0 (self-consistency).
- **AC-1.5** A unit test with a hand-built pred/gold pair asserts exact expected P/R/F1 for:
  one missed item, one extra item, one mis-sectioned item, one wrong owner.
- **AC-1.6** `python -m disclosures score --v1 disclosures.db --gold eval/gold --json
  eval/v1_baseline.json` runs and the file contains section-ignored precision/recall.
- **AC-1.7** `python -m disclosures validate` rejects (non-zero exit, message naming the file and
  reason) a file whose `pages_covered` misses a page, and one whose `pdf_sha256` mismatches
  (tests with fixtures).

### AC-2 Extraction, bake-off, backfill, load (Phase 2)
- **AC-2.1** `.claude/workflows/extract-disclosures.js` exists, begins with a literal
  `export const meta = {...}`, and a dry description in `docs/v2/extraction.md` states how Kevin
  runs it (args shape, per-parliament waves, the `/config` workflow-size step).
- **AC-2.2** `python -m disclosures extract --source gemini --model <id> <gold pdfs>` writes one
  valid file per gold PDF under `extractions/gemini-api/...` (verified by `validate`), and the
  mocked-client tests cover: chunk page offsets → absolute `page`; max-tokens chunk re-split;
  failure at 1-page chunk → no output file written + non-zero exit + error listed.
- **AC-2.2a** A test asserts `resolve_gemini_model()` raises for `gemini-2.0-flash`,
  `gemini-2.5-flash`, `gemini-1.5-pro` (from arg and from env) and accepts a `gemini-3.*` id;
  `git grep -nE 'gemini-(1|2)\.[0-9]' -- disclosures/` matches only that test.
  `DECISIONS.md` records the 3.x model id used.
- **AC-2.3** Workflow arm has produced one valid file per gold PDF under
  `extractions/workflow-claude/...` (`validate` passes).
- **AC-2.4** `eval/bakeoff.md` exists with, for each arm + v1: P/R/F1, owner/page/change_type/
  date accuracy, section-ignored recall, cost line, the bar from ADR-4 marked pass/fail, the
  chosen arm and the ADR-5 rule that chose it. `plans/2026-10-01-disclosures-v2/DECISIONS.md`
  records the Gemini model id used and Kevin's G2 confirmation (date).
- **AC-2.5** The chosen arm meets the ADR-4 bar on the gold set (re-runnable:
  `python -m disclosures score --pred extractions/<chosen> --gold eval/gold`).
- **AC-2.6** Backfill complete: `python -m disclosures validate extractions/<chosen>/house`
  reports 0 invalid files, and valid files + PDFs listed in `eval/extraction_failures.md` (each
  with a reason) = **774 for parliaments 43–47** (plus the 48th after Phase 4), with ≤ 5 listed
  failures.
- **AC-2.7** `python -m disclosures load --source <chosen>` builds `$V2` with the ADR-7 tables;
  `sqlite3 $V2 "select count(*) from documents"` equals the number of valid extraction files;
  `select count(*) from items where section not between 1 and 14 or owner not in
  ('self','spouse','dependent_child','unknown') or page < 1` = 0; `select count(*) from items i
  join documents d using(pdf_sha256) where i.page > d.page_count` = 0; `select count(*) from
  items where lodged_date is not null and (lodged_date < '1990-01-01' or lodged_date > date('now')
  or lodged_date not glob '[12][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]')` = 0; and
  `select count(*) from items where lodged_date < '2010-01-01' and confidence != 'low'` is listed
  in `eval/bakeoff.md` for review (not a hard gate — early-dated interests can be genuine).
- **AC-2.8** Re-running `load` produces identical `items` (compare
  `sqlite3 $V2 "select item_id from items order by 1" | shasum` before/after).
- **AC-2.9** Every member in `members` has a `member_terms` row with non-null `party` for each
  parliament they appear in, except rows listed in `data/overrides/unknown_party.csv` (≤ 5).
- **AC-2.10** The v1 duplicate-MP cases are unified: Chris/Christopher Bowen (McMahon) and the
  other `merge_duplicate_mps.py:29-50` overrides each resolve to a single `member_id`
  (test enumerates them).

### AC-3 Entities (Phase 3)
- **AC-3.1** After `python -m disclosures entities`, these each resolve to **one** entity
  (query `select count(distinct entity_id) from items i join entity_aliases a ...` per group, or a
  test over `$V2`): {CBA, Commonwealth Bank, Commonwealth Bank of Australia}; {NAB, National
  Australia Bank}; {ANZ, Australia and New Zealand Banking Group}; {Qantas, Qantas Airways};
  {Virgin Australia, Virgin Australia Airlines}; {Westpac, Westpac Banking Corporation};
  {Telstra, Telstra Corporation}. (Variants that don't occur in v2 data are skipped by the test,
  but each group must occur.)
- **AC-3.2** Every alias in `data/entities/aliases.csv` has a non-empty `entity_type` from the
  ADR-6 enum; the file covers ≥ 95% of the item count of the top 200 normalised names
  (script prints coverage; test asserts).
- **AC-3.3** `select count(*) from items where entity_name_raw is not null and entity_id is null
  and entity_name_raw not in (select ... generic)` — i.e. non-generic named items without an
  entity — is 0.
- **AC-3.4** `select method, count(*) from entity_aliases group by 1` shows all of
  `curated, asx, generic` > 0; every `listed_company` entity has a non-null `asx_code` that
  exists in the saved ASX snapshot.
- **AC-3.5** Gate G3 recorded in DECISIONS.md (Kevin reviewed top-50 aliases + flagged rows).
- **AC-3.6** Top-20 entities by item count (`select canonical_name, count(*) ... limit 20`) are
  printed in `eval/entities_report.md` alongside v1's top-20, showing no two rows that are the
  same organisation (verifier judges by inspection).

### AC-4 Scraper, 48th, Senate, refresh (Phase 4)
- **AC-4.1** `disclosures/sources.py` maps House 43–47 to the archive URLs in §0 (47th uses the
  `47th_Parliament_Register_of_Members_interests` slug) and 48th to the current URL; all HTTP
  requests send a browser `User-Agent`; a test with recorded HTML for the 48th page extracts
  150–155 member rows.
- **AC-4.2** `python -m disclosures scrape --chamber house --parliament 48` downloads 48th PDFs to
  `pdfs/48/`, handles both static PDF links and `interests-register-api-public` links, and appends
  manifest rows; `grep -c ',house,48,' pdfs/manifest.csv` (or equivalent column check) is 150–155.
- **AC-4.3** `pdfs/manifest.csv` has a row for every tracked PDF (v1's 774 back-filled with
  `source_url` where resolvable, else empty, and correct `parliament`); a test asserts every
  `pdf_sha256` matches the file.
- **AC-4.4** Running `scrape` twice in a row downloads 0 changed files the second time (log line
  `0 new, 0 changed`).
- **AC-4.5** `python -m disclosures refresh --dry-run` lists new/changed PDFs by comparing live
  listings + downloaded sha256 to the manifest; `refresh` (non-dry) with the gemini source
  extracts only those and reloads `$V2`; with the workflow source it prints the exact Workflow
  invocation (args JSON with the changed paths) for Kevin to run. Test with a fixture manifest
  where one sha differs → exactly that file is selected.
- **AC-4.6** `docs/v2/senate_source.md` documents the Senate data source (endpoints, payload
  shape, sample) and which parliaments are covered. Senate 48th items are in `$V2`
  (`select count(distinct member_id) from items where chamber='senate' and parliament=48`
  between 70 and 80; there are 76 senators, allow churn).
- **AC-4.7** House 48th extractions are valid and loaded (`select count(distinct member_id) from
  items where chamber='house' and parliament=48` between 145 and 155).

### AC-5 Publish & cleanup (Phase 5)
- **AC-5.1** `python -m disclosures export` writes `exports/disclosures_v2.csv` whose row count
  equals `select count(*) from items`, and `exports/kaggle/{disclosures_v2.csv,README.md,
  dataset-metadata.json}`; the README has a field dictionary covering every CSV column.
- **AC-5.2** `site/index.html` and `site/disclosures_v2.db` exist; `.github/workflows/pages.yml`
  exists and is valid YAML (`python -c "import yaml,sys;yaml.safe_load(open(sys.argv[1]))"
  .github/workflows/pages.yml`); index links to the Datasette Lite URL. Local check:
  `python -m http.server -d site 8000` then `curl -s localhost:8000/ | grep lite.datasette.io`.
- **AC-5.3** README.md rewritten: describes v2 only (what, coverage, how to run each command,
  how to refresh, data dictionary pointer, known limitations, v1 snapshot note). Every command in
  README exists (`grep -oE 'python -m disclosures [a-z]+' README.md | sort -u` ⊆ AC-0.3 list).
- **AC-5.4** Dead v1 code removed: `src/main.py`, `src/parsing/`, `src/cleaning/`,
  `src/preparation/db_handler.py`, `examples/`, `test_output.json`, `setup_pipeline.sh` (or the
  whole `src/` tree) are deleted; override tables live in `data/overrides/`; `git grep -n
  "from src\." -- '*.py'` returns nothing.
- **AC-5.5** `pip install -r requirements.txt -r requirements-dev.txt` in a fresh venv succeeds
  and `python -m pytest -q` passes in it.
- **AC-5.6** Nothing has been pushed, no Pages enabled, nothing uploaded to Kaggle by the build
  (`git log origin/main..v2-upgrade` non-empty is expected; `git status` clean; G4 left for Kevin).

---

## 4. Human gates (build must pause and hand back at each)

| Gate | When | Kevin does | Unblocks |
|---|---|---|---|
| G1 | End of Phase 1 drafting | Review `eval/gold/review.csv`, fix rows | Bake-off |
| G2 | After bake-off | Confirm chosen extractor; if workflow: raise workflow size in `/config` and run the per-parliament waves (or let the orchestrator run them) | Backfill |
| G3 | Phase 3 | Spot-check top-50 aliases + flagged rows | Final entity load |
| G4 | End | Push, enable Pages, Kaggle upload, announce | Publication |

---

## 5. Phase plan (draft)

Serial unless marked independent.

1. **Phase 1 — Contract, harness, gold set.** `disclosures/` package skeleton + CLI; `schema.py`
   + generated JSON Schema + `validate`; `score` (+ v1 baseline mode); gold selection script; Opus
   agent drafts gold JSON + `review.csv`. → **G1.**
2. **Phase 2a — Extractors.** Shared prompt; Gemini extractor (mock-tested); saved workflow
   script. Verify current Gemini model id + price; record in DECISIONS.md.
3. **Phase 2b — Bake-off.** Run both arms on gold; `eval/bakeoff.md`. → **G2.**
4. **Phase 2c — Backfill + load.** Chosen extractor over 43–47 (workflow: per-parliament waves);
   `load`; member/party overrides migrated to `data/overrides/`.
5. **Phase 3 — Entities.** Normalise, generic list, curated alias draft (→ **G3**), ASX snapshot
   + match, LLM long tail, `entities_report.md`.
6. **Phase 4 — Scraper / 48th / Senate / refresh.** *Independent of Phases 2–3 once Phase 1's
   contract exists* — can run in a parallel worktree: sources + scraper + manifest backfill +
   refresh; Senate discovery + adapter. Then extract House 48th (and Senate if PDF-based) with the
   chosen extractor and reload (depends on 2b's choice).
7. **Phase 5 — Publish & cleanup.** Export, site, Pages workflow, README, delete v1 code,
   requirements. → **G4.**

Long pole: the backfill (13k pages). With the workflow arm it spans several sessions/usage
windows; with Gemini it's an unattended run of roughly an hour or two.

### Risks
- **Older forms differ** from the 14-section 48th form → section mapping ambiguity. Mitigation:
  gold set spans 43–47; prompt includes per-era heading variants found during gold drafting.
- **Alteration semantics**: whether later PDFs repeat or supersede earlier items is unconfirmed;
  v2 records items as printed (with change_type) and does **not** attempt to compute "current
  holdings" — that's a future analysis layer.
- **Senate source** may be awkward (ADR-9 bounds it).
- **Subscription limits** may slow a workflow backfill; ADR-5's tie-break favours Gemini partly
  for this reason.
