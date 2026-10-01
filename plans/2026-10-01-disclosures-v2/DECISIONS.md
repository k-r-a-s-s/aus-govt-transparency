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

### G1 — gold review: PENDING (2026-10-01)
Kevin reviews `eval/gold/review.csv` (790 rows; how-to in `eval/gold/README.md`), then runs
`python -m disclosures.gold apply-review`. Until every gold file has `reviewed_by: "kevin"`,
AC-1.3 is not met and Phase 2's bake-off must not start.

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
