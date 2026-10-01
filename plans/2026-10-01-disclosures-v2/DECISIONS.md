# Decisions log — Disclosures v2

Dated, append-only record of decisions taken during the build (see `SPEC.md` for the plan).
Newest entries at the bottom of each section.

## Phase 1 (gold set and harness)

### 2026-10-01 — Gold conventions C1–C11 adopted
The four Phase 1b drafters followed slightly different conventions on ambiguous cases. These
included joint self+spouse entries, sections on unnumbered alteration notices, which date to
use, staff gifts and covering letters. A gold set has to be internally consistent, otherwise
the extractor bake-off measures drafter disagreement rather than extractor quality. So the
rules C1–C11 were written into `disclosures/prompts/extract.md` ("Conventions for ambiguous
cases"). Gold drafters and extractors share that prompt. All 12 gold files were brought into
line, with each edit noted in the file's `extraction_notes`
(`consolidation 2026-10-01: ...`). The result: 762 → 790 items (+28 spouse copies under C1),
plus section, owner, date and confidence corrections.

Interpretations taken while applying them (Kevin may overrule at G1):
- **C4 `statement_date`.** The initial statement pages carry no signature on any of the 12
  forms (43rd–47th). Page 1 says interests are declared "at p.2-6 … AND at p.7 alterations".
  So the statement's only signature/date is the one on the bound-in "since dissolution or date
  of election" page, and that date is used as the statement's "signed date". The page-1 stamp
  is used only when that page is undated. Seven drafters already did this. gosling, kingm and
  prenticej were changed from the stamp to the signed date: 2022-08-23 → 22, 2022-08-23 → 22,
  2016-09-30 → 26.
- **C4 legible but implausible dates.** plibersekt p10 is signed "7.5.11" although it discloses
  a 15 June ball and is stamped 6 JUL 2011. The legible signed date (2011-05-07) is used.
  thistlethwaitem p22, where the year is overwritten, keeps the stamp-informed reading.
- **C1 scope.** A split is made only when both people are named: "with Mr Prentice", "for Mr &
  Mrs Prentice", "for myself and Mrs Morrison", "joint … with spouse/partner". Not split:
  gosling p8 "Family tickets" (the handoff pointed at gosling p8, but the "for both Mr and
  Mrs" wording is in prenticej p11/p22/p24/p31, and those were split). Also not split:
  plibersekt spouse-row "(jointly)" property and mortgage, which do not name the member.
- **C3 confidence.** Every item on a notice with no section number is `medium`. Items printed
  under a section their content does not fit get `medium` too (thistlethwaitem's "11" tickets,
  kingm "11. Gifts" tickets/flights, tink p11 lounges under 12, morrison p19 hospitality under
  11). Sections stay as printed. Two unnumbered items were re-sectioned by meaning: butlerm p13
  festival passes 11 → 12, and plibersekt p12 National Press Club membership 11 → 13.
- **C6.** A single gift jointly provided by several bodies (kingm p12 CME/MCA/APPEA) stays one
  item. C6 targets cells that list several separate holdings.

### 2026-10-01 — `requirements.txt` is v2-only
`requirements.txt` was rewritten for the v2 package only. The v1 dependencies were dropped
on purpose: v1 (`src/`) is frozen, is not run by the v2 build, and is deleted in Phase 5. Dev
tools live in `requirements-dev.txt`.

### 2026-10-01 — Validator uses strict types
`disclosures/schema.py` models use Pydantic `strict=True`. Lax mode accepted `"section": "5"`,
`"page": "2"`, `"is_alteration": "true"` and `"section": true`, all of which the committed
JSON Schema rejects, so `validate` and `schema/extraction.schema.json` disagreed. The
generated schema is unchanged. Pydantic strict also rejects a float such as `2.0` for an int,
which JSON Schema allows. That disagreement is in the safe direction. The validator also now
rejects `pdf_path` values that contain `..` or resolve outside the repo root, and it enforces
`lodged_date is null` ⇔ `date_precision == "unknown"`.

### 2026-10-01 — Form-era finding: section numbering is stable
On the gold set (43rd–47th House forms), sections 1–14 have the same numbers and headings in
every parliament, and section 2 is split into 2(i)/2(ii) throughout. Differences: owner row
labels ("Spouse" on 43rd/44th forms, "Spouse/partner" later), and notices in older parliaments
are often letters or have a free-text "Item" column with no section number (see C3). The
46th/47th typed notices print the section ("12. Travel or hospitality"). No per-era section
mapping is needed.

## Human gates

### G1 — gold review: PASSED (2026-10-01)
Phase 1 passed independent verification on 2026-10-01 (air-gapped verifier: every AC-0/AC-1
criterion met except AC-1.3; gold spot-check 418/418 items agree with the PDF pages across all
12 files, four scanned PDFs read in full). Kevin reviewed `eval/gold/review.csv` (790 rows)
and approved the set as is ("it all looks good enough to me, let's go").
- Date reviewed: 2026-10-01
- Rows changed via `kevin_fix`: 0. All 790 rows ticked `kevin_ok=y` on Kevin's blanket
  approval; `apply-review` set `reviewed_by: "kevin"`, `reviewed_at: 2026-10-01` on all 12
  files; `validate eval/gold` 12 valid. AC-1.3 met.
- Convention decisions (C4 statement_date, plibersekt p10 date, non-splits, C3 confidence):
  all five judgement calls in `HANDOFF.md` accepted as applied; C3 confidence for lounge
  memberships under section 12 stays uneven (not scored).

## Phase 2 (extractors)

### 2026-10-01 — Gemini model: `gemini-3.8-flash` (verified live)
`client.models.list()` with the project key on 2026-10-01 lists `gemini-3.8-flash` (display
name "Gemini 3.8 Flash", GA, no `-preview` suffix; actions generateContent, countTokens,
createCachedContent, batchGenerateContent; 1,048,576 in / 65,536 out). Older 3.x Flash ids
(3.5/3.6/3.7) and `gemini-2.5-*` are still listed; 2.5 shuts down mid-Oct 2026 and all 2.x
ids are banned by `resolve_gemini_model()`. Pricing page (fetched 2026-10-01), paid tier per
MTok: **$0.75 in / $3.75 out through 2026-12-31**, then $1.50 / $7.50 from 2027-01-01;
Batch API 50% off. These two numbers are the cost basis for `eval/bakeoff.md`.
`.env.local` `GEMINI_MODEL` was changed from `gemini-2.0-flash` to `gemini-3.8-flash`
(value only). SDK: `google-genai==2.26.0` (added to `requirements.txt`).

**Blocker found:** a live smoke call returned `402 RESOURCE_EXHAUSTED: Your prepayment credits
are depleted` (AI Studio project billing). The Gemini arm of the bake-off cannot run until
Kevin tops up the prepaid credits at https://ai.studio/projects. The gold-set run needs
roughly 286 pages ≈ 75k input + ~100k output tokens ≈ US$0.50; the full backfill ≈ US$10–20.

### 2026-10-02 — Phase 2a extractor decisions (choices the spec left open)
- **De-dup key extended.** ADR-5 de-duplicates on (section, owner, normalised
  entity/description, page). Chunks don't overlap, and an item outside its chunk's range is an
  error, so a key that contains `page` can only match items from the same chunk. On the gold
  set that bare key matches 52 of 790 genuine distinct items: two Westpac loans on one page,
  several gifts from one body, and similar. Merging would delete them all, costing about 6.6
  points of recall. The key is therefore extended with the normalised description,
  subsection, change_type and lodged_date (0 gold matches). It still removes exact repeats.
  See `extract_gemini.dedup_key`.
  Known edge (Phase 2a verifier): the key still ignores `location`, `purpose`, `confidence`
  and `date_precision`, so two same-page items with an identical bare description that differ
  only in location/purpose would collapse. Zero such cases in gold (section-3 descriptions
  embed the location); watch for it in the backfill validate/score reports.
- **Inline bytes, not the Files API**, for chunks of 15 MB or less (inline limit 20 MB).
  Larger chunks are uploaded and deleted after the call.
- **Chunk-relative page rule.** The model is told to give absolute pages. If a chunk starts
  after page 1 and every returned page is within 1..chunk_len, the pages are shifted by
  start-1; otherwise they are trusted. When halving, the first half gets the extra page, so
  every chunk that starts after page 1 starts after its own length, and the rule can't misfire
  (tested). A page outside the chunk fails the PDF; pages are never clamped.
- **Re-split triggers:** `MAX_TOKENS`, or unparseable or wrong-shaped JSON. Other non-STOP
  finish reasons fail the PDF straight away.
- **`--max-retries` default 4** (at most 5 tries per call; 429 and 5xx only). `usage.output_tokens`
  includes thinking tokens, which are billed as output.
- **Writes are atomic:** temp file, then `validate_file`, then rename. An earlier valid output
  survives a failed `--force` re-run.
- **`statement_date`:** an unparseable value from the model is set to null, with a note.
  It isn't scored, and it shouldn't sink a whole file. Bad item dates still fail the file.
- **`--batch` skipped.** It exits 2 (`NotImplementedError` in `extract_pdfs`). Re-split rounds
  would need a multi-round batch driver, and at about US$0.50 for the gold run the 50%
  discount isn't worth it yet.
- **Validator guards added** (Phase 1 verifier gaps): `is_alteration` ⇔ `change_type != "initial"`;
  `date_precision` `month` ⇒ day 01, `year` ⇒ `-01-01`. All 12 gold files still pass.
- **`requirements.txt`** also pins `cryptography`, `cffi` and `pycparser`. google-auth needs
  them, and they were missing from the Phase 2 dependency list.

### G2 — extractor choice: _pending_
- Date:
- Bake-off F1 (workflow-claude vs gemini-api), cost:
- Choice:
- Gemini model id (verified GA, not `gemini-[0-2].*`): `<TBD>`

### G3 — entity spot-check: _pending_
- Date:
- Notes:

### G4 — publish (Pages + push): _pending_
- Date:
- Notes:
