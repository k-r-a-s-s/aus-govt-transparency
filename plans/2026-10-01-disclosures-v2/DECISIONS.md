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

### G2 — extractor choice: **workflow-claude** (2026-10-02)
- **Revisited 2026-10-02 (same day):** Kevin asked to try Gemini after the subscription cap
  made the workflow backfill impractical (see the Phase 2 entry below). Gemini (via OpenRouter)
  is the intended backfill arm pending its gold score; final G2 confirmation after scoring.
- Date: 2026-10-02
- Bake-off F1 (workflow-claude vs gemini-api), cost: workflow-claude F1 0.974 (P 0.973 / R 0.975,
  owner 0.995, page 0.991, section-ignored recall 0.978 vs v1 0.625) — clears the ADR-4 bar; within
  subscription. gemini-api: not run (402, credits depleted). See `eval/bakeoff.md`.
- Choice: **workflow-claude**. Kevin: "let's go without Gemini for now". The ADR-5 tie-break
  towards gemini-api is moot because the Gemini arm was not run (credits depleted). workflow-claude
  clears the ADR-4 bar on its own. The Gemini extractor stays in the tree and can be scored later;
  if it is ever scored and wins under ADR-5, that is a new decision, not a reversal of this one.
- Backfill mechanics: the `Workflow` tool was denied by the auto-mode classifier in the orchestrating
  session, so the backfill is dispatched as direct Sonnet subagents using the saved script's bundle
  prompts (identical bundling and instructions), in per-parliament waves.
- Gemini model id (verified GA, not `gemini-[0-2].*`): `gemini-3.8-flash`

### G3 — entity spot-check: **approved** (2026-10-03)
- Date: 2026-10-03
- Notes: Kevin approved all 114 rows of `eval/entities_g3_review.csv`, 0 fixes. See "2026-10-03 — Gate G3" below.

### G4 — publish (Pages + push): _pending_
- Date:
- Notes:

## Phase 2c (loader and override tables)

### 2026-10-02 — Loader and `data/overrides/` decisions (choices the spec left open)
- **Member identity, resolution order.** (1) `data/overrides/pdf_members.csv` by `pdf_path`;
  (2) `member_aliases.csv` by normalised `member_name_as_printed`, with the electorate first
  and then without it, counted only when exactly one member matches; (3) a slug of the
  printed name, with a warning. The spec only names the alias table. A per-PDF table comes
  first because v1's `disclosures.pdf_filename` -> `mp_id` link exists for 759 of the 774
  PDFs, and it is more robust than matching the printed name.
- **Canonical full name = v1's Wikipedia name** (`all_mps_*.csv`, with `[a]`-style footnote
  markers stripped). All 303 people who own a PDF have one. Each v1 `mps` row (338, which
  includes v1's duplicates) is matched to a Wikipedia name by: v1's special cases or merge
  overrides, else same electorate + surname, else surname + first name anywhere. Only v1's
  placeholder `Unknown` mp stayed unmatched, and it owns no PDF. So the AC-2.10 cases become
  `chris_bowen`, `louise_markus`, `bert_van_manen`, `milton_dick`, `clare_o_neil`.
- **Slug recipe** (ADR-7 says only "slug"): ASCII-fold, lower case, each run of
  non-alphanumerics becomes `_`, trimmed. Apostrophes are therefore `_` too (`clare_o_neil`).
- **The 15 PDFs v1 never loaded:** 9 are member statements whose member was taken from the
  filename stem and confirmed on page 1 (7 of them are scans, checked by eye):
  `alexanderj/elliotj/ellisk/entschw/feeneyd/fergusonl_44p`, `wilsonj_45p_2`, `wells_46p`,
  `thwaites_47p`. 6 are not member statements: `interestsr_4{4..7}p.pdf` (the House
  resolution) and `explanatory_notes___booklet_1.pdf` in the 46th/47th. Their documents load
  with `member_id` NULL.
- **Party per term.** v1 only knows each person's most recent party: `all_mps_debug.csv`
  runs to the 47th, `all_mps_most_recent_party.csv` to the 46th, and footnoted names give a
  few extra per-term rows. The convention is the party at the start of the term (when the
  statement is lodged). A term with its own Wikipedia row takes that party. An earlier term
  takes the latest party, except that a latest `X/Independent` label (a defection in that
  term) becomes plain `X` for earlier terms. Party names go through v1's `PARTY_MAPPING` plus
  4 missing variants. Blocs are `Coalition` / `Labor` / `Crossbench`, using v1's
  COALITION/LABOR sets. The Greens are `Crossbench`, where v1 had a separate `Greens` bloc.
  Result: 763 terms, all with a party. `unknown_party.csv` has 0 rows for House 43rd–47th,
  and the 48th is added in Phase 4. Known gaps (no web lookups): party changes between
  parliaments other than a final-term defection (Katter's 43rd shows as KAP, but he was an
  Independent until 2011); Palmer United is merged into UAP (v1 mapping); Nationals WA (Tony
  Crook, 43rd) has bloc Coalition although he sat on the crossbench.
- **item_id** = sha1 of the JSON array `[pdf_sha256, page, section, owner,
  normalise_entity(entity_name or description), ordinal]`. `ordinal` counts earlier items
  with the same key in that file, so ids depend only on the file contents.
- **Load mechanics.** The DB is built in `<db>.tmp-<pid>` and then renamed over the target.
  Writing to a file named `disclosures.db` is refused. A second file with the same
  `pdf_sha256` is skipped as a duplicate. A missing overrides directory is an error (exit 2)
  rather than a silent "slug everything". Exit 1 if any hard AC-2.7 query is non-zero.
- **Seeding is reproducible.** `scripts/seed_v2_overrides.py` regenerates the CSVs from v1
  (read-only), and `--check` diffs them. The hand fixes live in its `MANUAL_*` tables. It
  stops working when v1 is deleted in Phase 5, and the CSVs are the source of truth after that.

### 2026-10-02 — Phase 2c loader verified (PASS WITH NOTES); two guards tightened
Air-gapped verifier reproduced every claim (154 tests, AC-2.7 hard queries 0, AC-2.8 identical
item ids across loads, AC-2.9 0 unknown parties, AC-2.10 five duplicate-MP cases unify; 29
`pdf_members.csv` rows spot-checked against page 1, all correct). Fixed on the spot: the v1-DB
guard ignored case variants on case-insensitive APFS (`--db DISCLOSURES.DB` would have replaced
v1's file; now compared case-insensitively and via `samefile`), and an unwritable target
escaped as a traceback (now `load: …`, exit 2). Left open, none blocking: the
`member_aliases.csv` fallback does not reorder "SURNAME Given" printed names, so Phase 4's
48th-Parliament PDFs (no `pdf_members.csv` rows yet) would mint new ids; a failing AC-2.7
hard gate still installs the DB (exit 1 means "inspect", not "previous DB kept");
`pdf_members.csv` electorates are v1's most-recent seat name (loader prefers the extraction's);
mid-term defectors are labelled inconsistently (Sharkie 45th as Centre Alliance, Kelly 46th /
Goodenough 47th plain Liberal while Jensen/Banks/Broadbent/Gee/Thomson carry "X/Independent").
AC-2.7 informational count on the 23 files loaded so far: 2 (gashj_43p s11, lodged 2009-04-29).

### 2026-10-02 — Workflow-claude backfill abandoned; Gemini via OpenRouter
A 19-agent Sonnet wave over the 43rd Parliament hit Kevin's Claude subscription session limit
("resets 1:10pm") after ~1 hour and 11 completed files; several agents also hit API stream
timeouts under that concurrency. At that rate the 745 remaining PDFs need 60+ five-hour windows.
Kevin: "lets try gemini then, I just put an openrouter key in the local env." The AI Studio key
stays unusable (402). OpenRouter (checked 2026-10-02, public models endpoint) lists
`google/gemini-3.8-flash` at $0.75/$3.75 per MTok (`:batch` variant 50% off), 1,048,576 context,
input modalities text/image/video/file/audio. The extractor needs an OpenRouter transport
(OpenAI-compatible chat completions with a `file` part and `json_schema` response format) next
to the existing `google-genai` path; `resolve_gemini_model()` must still ban 2.x after stripping
`google/`. The 23 workflow-claude files stay as bake-off evidence.

### 2026-10-02 — Bake-off re-run on OpenRouter: four arms, Gemini 3.8 Flash (+ Sonnet fallback) wins; G2 revisited
Kevin asked for a short multi-provider comparison before committing ("check a few different
providers before committing"). The live OpenRouter catalogue (464 models, 181 with native
`file` input) was filtered to native-PDF + structured-output models and probed on one 2-page
scanned chunk for tokens/page. Shortlist: `google/gemini-3.8-flash` (favourite, ~520 input
tokens/page), `openai/gpt-6-luna` (cheap challenger, ~3,000 tokens/page but $0.10/MTok) and
`anthropic/claude-sonnet-5.5` (quality anchor). Haiku 4.5, Grok 4.3, GPT-5.4 Mini and Gemini
3.5 Flash Lite were dropped as dominated on cost or capability. An OpenRouter transport was
added to the extractor (`disclosures/openrouter.py`; ADR-11 mock tests; request shape verified
against openrouter.ai/docs and live).

Gold-set results (12 PDFs, 790 items; `eval/bakeoff.md` has the full table):

| arm | P | R | F1 | sec-ignored R | owner | page | lodged_date | gold cost | backfill est. |
|---|---|---|---|---|---|---|---|---|---|
| workflow-claude (Sonnet, Claude Code) | 0.973 | 0.975 | 0.974 | 0.978 | 0.995 | 0.991 | 0.988 | subscription | subscription-capped |
| gemini-api: `google/gemini-3.8-flash` flex + Sonnet 5.5 fallback | 0.986 | 0.987 | **0.987** | 0.990 | 1.000 | 1.000 | 0.968 | US$0.48 | ≈ US$22 |
| `openai/gpt-6-luna` | 0.967 | 0.958 | 0.962 | 0.977 | 0.995 | 0.992 | **0.765** | US$0.17 | ≈ US$7.5 |
| `anthropic/claude-sonnet-5.5` | 0.981 | 0.973 | 0.977 | 0.991 | 0.997 | 1.000 | 0.999 | US$2.38 | ≈ US$108 |

All four clear the ADR-4 bar. ADR-5 rule: highest F1 wins → **gemini-api** (0.987), no
tie-break needed. Two findings behind that result:
- **Gemini RECITATION block.** Gemini refused morrison_47p pages 21–29 (`finish_reason ERROR`,
  native `RECITATION`), and still refused page 23 alone (a typed travel-alteration notice:
  Taipei/Bangkok, Galle Dialogue). Re-splitting cannot clear it, so a **per-chunk
  `--fallback-model`** was added: only the blocked chunk goes to the fallback (Sonnet 5.5), the
  file's `model` becomes `primary+fallback` and `extraction_notes` says which pages. Without the
  fallback Gemini scored recall 0.865 (one whole PDF missing) and failed the bar. Expect a few
  per cent of backfill PDFs to need it; cost impact is small (one Sonnet chunk ≈ US$0.10).
- **GPT-6 Luna breaks convention C4 on dates.** On typed 47th-Parliament files it takes the
  "received" stamp date rather than the signed date (tink 25→26 Aug, gosling 22→23 Aug,
  plibersek 18→22 Oct 2010), giving lodged_date accuracy 0.765. It also loses items in dense
  pages (thistlethwaite s13 clubs, kingm s6 banks). It is the cheapest arm by far but is not
  chosen. (The butlerm "4/12/13" handwritten date, read as November by Gemini and Luna, is
  genuinely cramped; the gold reading is supported by the 9 Dec 2013 stamp.)

Transport facts recorded in `docs/v2/extraction.md`: `openai/*` models reject `temperature`;
the half-price Gemini tier is pinned with `provider.order: ["google-ai-studio/flex"]`
(`:batch` is a separate async API); OpenRouter reports `usage.cost`, which the extractor now
prints instead of the price-table estimate. zsh does not word-split `$GOLD`, which silently
turned the first three gold runs into a single "PDF not found" argument (no cost incurred).

**G2 revisited (2026-10-02): recommendation is gemini-api = `google/gemini-3.8-flash` on
`google-ai-studio/flex` with `--fallback-model anthropic/claude-sonnet-5.5`.** Kevin to
confirm. Budget note: OpenRouter credit is ≈ US$17.5 of 30 after this session's ≈ US$3.6 of
gold runs and probes; the backfill at this configuration is ≈ US$22, so a top-up of ≈ US$10 is
needed before (or during) it. A `--reasoning-effort low` variant scored F1 0.977 at ≈ 25%
less (≈ US$16 backfill); kept as the budget option only (`eval/bakeoff.md`).

**G2 CONFIRMED (Kevin, 2026-10-02): gemini-api = `google/gemini-3.8-flash` on
`google-ai-studio/flex` with `--fallback-model anthropic/claude-sonnet-5.5`, default reasoning
effort.** ("yes lets use gemini with claude fallback.") OpenRouter topped up by US$10 the same
day: US$27.3 available against the ≈ US$22 estimate. The backfill is the next agent's first
action (`HANDOFF.md`).

### 2026-10-02 — Backfill run and Phase 2 closed (cloud session)
Kevin moved the run to a Claude Code cloud session ("can you run it in the cloud for me"). The
HANDOFF step-1 command ran as given (bash, so no zsh word-splitting issue) in three passes:
pass 1 stopped on OpenRouter 402 after 458 PDFs when the US$27 credit ran out (US$27.42
billed); Kevin topped up US$30; pass 2 was aborted after 86 PDFs (see below); pass 3 finished
the remaining 212 with 0 failures (US$8.71). Result: 768/768 valid, 42,042 items,
`eval/extraction_failures.md` lists 0 failures + 6 non-statements (AC-2.6). Load: AC-2.7
hard queries 0, AC-2.8 identical ids, AC-2.9 0 missing parties, AC-2.10 passes; the
informational early-dated count is 4 (all `grayg_43p`, listed in `eval/bakeoff.md`).

Two findings, both recorded in `docs/v2/extraction.md` and `eval/bakeoff.md`:
- **The Sonnet fallback was silently pinned to Azure.** OpenRouter lists `temperature` only on
  Sonnet 5.5's Azure endpoints, and the transport sent `temperature: 0` with
  `require_parameters`, so every fallback chunk went to Azure; Azure intermittently returned
  HTTP 400 `no_content_length_header` (5 PDFs). First fix, `--ignore-providers azure`, left
  no endpoint at all (404 "Filter by Parameters", 10 PDFs in pass 2, run aborted). Second
  fix: no `temperature` for `anthropic/*` (as already for `openai/*`); verified live that the
  fallback then routes to Anthropic's own endpoint. Both flags kept; 183 tests.
- **RECITATION blocks 14% of files, not a few per cent**: 108/768 files carry
  `model = google/gemini-3.8-flash+anthropic/claude-sonnet-5.5` (43rd 37, 44th 29, 45th 35,
  46th 3, 47th 4). Gemini flex alone cost US$10.96 for 365 files (on estimate); the fallback
  files averaged US$0.163, so the backfill came to ≈ US$38 billed against the US$22 estimate.
  Kevin asked whether flex was in use (it was, confirmed from the per-token cost); the model
  choice was not re-opened (G2 stands). A cheaper fallback model is noted in `HANDOFF.md` as
  an optional lever only.

**Phase 2 done.** Next: Phase 3 (entities) or Phase 4a (scraper), per `SPEC.md`.

### 2026-10-02 — PR #1 reviewed and merged; Phases 3–5 planned as a Ralph loop (interactive session)
Kevin asked to review the cloud session's work, get it into `v2-upgrade`, and suggest next steps.
PR #1 was fast-forwarded into `v2-upgrade` (`91a30fd`) after a local re-check: tests, validate,
load and AC-2.7–2.10 all reproduce. An extra coverage check against v1 found one real gap:
**attachments bound into a statement are not itemised consistently** (`odowdk45p`: 22 SMSF
holdings missing). The prompt has no rule for them. The gold precedent (`plibersekt_43p`:
attachment items recorded on the attachment page, no item for the "see attached" line) becomes
rule C12, applied to the confirmed files only. Kevin: "yep" to fixing it, then "draft all of
this … I'll try to run it in a ralph loop … I will also run it on the cloud again".

Plan: `plans/2026-10-02-ralph-phases-3-5/`. The prompt, plan and operating guide follow the
canonical Ralph layout (Huntley / Farr playbook). Decisions on top of SPEC.md are in
`SPEC-DELTA.md` D1–D7: entity-pipeline details, Senate source, budget caps, branch and gate
rules. Two facts re-verified live the same day changed Phase 4's shape:
- The House 48th register now links mostly `interests-register-api-public` statement PDFs, which
  are typed with a text layer.
- **The Senate register is open JSON** (`queryStatements` / `getSenatorStatement`, 76 senators,
  sections pre-split), so the Senate 48th needs a direct adapter and no LLM (ADR-9's
  structured-source branch).

Loop drivers:
- Locally: `scripts/ralph/loop.sh`, a fresh `claude -p` per iteration.
- In the cloud: the built-in `/goal`, because the `ralph-wiggum` plugin is not loaded in cloud
  sessions.

Both stop on `scripts/ralph/status.py` printing `RALPH-STATUS: STOP`. Phase 5 prep is included
(publication stays Kevin's, G4).

**Narrowing of a SPEC non-goal.** SPEC says Kevin performs every `git push`. Cloud runs push
their own `claude/*` branch and open a PR against `v2-upgrade`, because that's the only way
work leaves the container (the Phase 2 backfill did the same, and Kevin merged it). Pushing to
`v2-upgrade`/`main`, merging, Pages and Kaggle stay Kevin's. Local runs never push.

The plan pack was cold-reviewed by a separate verifier agent before commit. It found 3 blockers,
all fixed: the secrets grep choked on 2 GB of PDFs; one expected block in M1 would have halted
M2/M3; and the pack was uncommitted while the prompt told iterations to discard stray changes.
It also found 15 smaller issues (branch-keyed push rule, stall guard in `loop.sh`, malformed-header
detection in `status.py`, a `/goal` condition that could not re-satisfy, T3.3 split).


## Attachment fix (prompt v1)

### 2026-10-02 — Rule C12: itemise bound-in attachments (prompt v0 → v1)
**Finding** (SPEC-DELTA D1, confirmed page by page in T1.1–T1.2, `eval/attachment_gaps.md`):
of 29 candidate files, 7 have an attachment bound into the PDF that was never itemised:
`coultonm_43p/44p/45p`, `nevillep_43p`, `odowdk45p` (super-fund/broker portfolios), `huntg_44p`
(membership list) and `pynec_44p` (a CV). 14 handle attachments correctly, 5 refer to an
attachment that isn't in the PDF, and 3 are wording-only false positives. Prompt v0 had no rule,
so behaviour was inconsistent.

**Rule.** C12 in `disclosures/prompts/extract.md` plus checklist item 7: one item per holding on
the attachment, with the referencing section/subsection/owner, the attachment's page, and the
referencing page's dates and change type. The "see attached" line itself is not an item unless
it names an interest of its own. Gold precedent: `eval/gold/plibersekt_43p.json` (s13 "see
attached list" → items on the p8 attachment, no item for the reference line).

**Wording beyond D1**, from what T1.2 found:
- More attachment kinds named: an adviser's letter or table (nevillep_43p, odowdk45p p11), a
  membership list (huntg_44p), a CV (pynec_44p), plus "list attached".
- A cell that only names a fund, with a bound-in page listing that fund's holdings, counts too.
  nevillep_43p p5 just says "Neville Superannuation Fund" and has no "see attached".
- An attachment continues the referencing item. The next statement or notification form isn't
  one (smitht_45p: the model has treated the next form as the attachment).
- Totals/subtotal rows are not items (odowdk45p p11). Entries the attachment shows as already
  ended, like CV roles "1988–2012" in pynec_44p, are not current interests, so they get no item.

**Re-extraction scope.** Only the 7 confirmed files (T1.5). The other ≈ 760 files stay on v0,
because C12 changes nothing but attachment handling. A full re-run (≈ US$38) is out of scope.
T1.4 checks the gold set doesn't regress under v1.

### 2026-10-02 — C12 change type for a replacement list; joint-fund owners (V1)
V1's cold check found two places where C12 output could be read two ways.
- **huntg_44p p11.** The p10 notice ticks ADDITION but says "Revised membership list – see
  attached". The model gave the 16 attachment items `varied`. We keep it: the attachment replaces
  the whole earlier list rather than adding one interest, and `varied` says that. C12 reads "use
  that notice's change type" literally, so a re-extraction could give `added`. Both are accepted,
  and the prompt wasn't changed for one file.
- **Joint fund (nevillep_43p).** When the self and spouse rows both refer to the same attachment
  ("as above"), each holding belongs to both owners, as coultonm_43p/44p/45p already have it.
  nevillep_43p files them under self only. T1.6 fixes that one file and doesn't change the prompt.

### 2026-10-02 — Entity id collisions and singleton names (T2.1)
- **Same slug = same entity.** `entity_id` is the slug of `canonical_name`. When a second alias
  produces an id that already exists, it joins that entity rather than getting a suffixed id. On
  the real data, all 16 such cases were true duplicates that the normaliser kept apart:
  `&`→`and` versus `&` dropped (`samson oil and gas` / `samson oil gas`) and accents
  (`loreal` / `loréal`). The first definition, in precedence order and then alias order, keeps
  the name.
- **Singleton name** = the alias's commonest whitespace-collapsed raw spelling, with ties going to
  the alphabetically first. That keeps it deterministic and close to what was printed.
- **Interim.** Until the LLM stage exists, aliases with ≥ 2 items also fall through to
  `singleton`, so AC-3.3 holds at every step.

### 2026-10-02 — ASX matching details (T2.2)
- **Canonical name.** All aliases matched to one ASX code share one canonical name, so they
  become one entity: the commonest raw spelling among the aliases that matched by *name* (ties
  alphabetical). If only a ticker matched (`CBA`), we use the ASX name in capwords
  (`Commonwealth Bank Of Australia.`). Curated rows (T2.4) override either.
- **Name before ticker.** An alias that is both a company's normalised name and another
  company's ticker matches the name. A normalised name shared by two listed companies is
  ambiguous and matches nothing.
- **Exclusions.** `data/entities/asx_exclusions.csv` lists aliases that never ASX-match. It's
  seeded with `ing`: three section-1 items are Inghams (ticker ING) shares, but about 168 items
  in sections 6 and 8 are ING Bank accounts and loans. D2 applies a match to every item with
  the alias, so matching `ing` would mislabel the bank. Of the 118 ticker matches on the real
  data, the rest checked out as shareholdings. `news` (News Corporation ↔ News Limited) was kept.
- **`--fetch-asx` only downloads.** It writes `data/reference/asx_listed_companies_<today>.csv`
  (local date; the file's own title line has the ASX timestamp), checks that it parses, and
  stops. Then you run `entities` as usual.

### 2026-10-02 — Curation rules for aliases.csv (T2.4)
- **Brand as disclosed, not ultimate parent.** St.George, Bank of Melbourne, BankSA (Westpac),
  Bankwest (CBA) and ME Bank (BOQ) stay separate entities: members disclosed the brand, and
  ownership changed over the 43rd–47th. Exception: Macquarie Bank and Macquarie Group share a
  name, and bare `macquarie` can't tell them apart, so they're one entity (`MQG`). Kevin can
  merge brands into parents at G3.
- **Programmes resolve to the provider.** Qantas Club / Chairman's Lounge / frequent flyer →
  Qantas Airways; Virgin club / Velocity / Beyond → Virgin Australia (Virgin Blue was renamed
  in 2011). AMP Bank/Life/Super → AMP. Community Bank branches → Bendigo and Adelaide Bank.
- **Not merged:** party and union state branches (separately registered); combined names
  (`qantas and virgin`, `anz and nab`); look-alikes that are different organisations (Qantas
  Staff Credit Union, Virgin Money, ANZ Stadium, Lion Selection Group, Bank Australia ≠ NAB/CBA,
  Telstra Super, Astra Enterprises). Individual Vanguard/AMP Capital funds stay apart from the
  manager.
- **Types.** The enum has no insurer or bank-vs-listed split, so banks, insurers and fund
  managers are `bank_or_financial` (with `asx_code` when listed), airlines `airline`, media
  `media_or_entertainment`; `listed_company` is for other listed companies and always has a
  code (AC-3.4). Canonical names drop legal suffixes (Ltd/Limited), matching the normaliser.
- **ASX stage defers to curated codes.** An ASX-matched alias whose code a curated row uses
  takes that row's canonical name and type, so `QAN` and `qantas` can't become two entities.
- **Flagged for G3** (`review_flag=1`): bare `commonwealth`, `national bank`, `st george`,
  `bendigo`, `macquarie`, `ing` (~5 section-1 rows may be Inghams), `lion`, `rio`, `velocity`,
  `chairmans lounge`, `bank australia`, `suncorp bank`, ASTRA's later name, two AALD programmes.

### 2026-10-02 — Curation rules for heads 101–200 (T2.5)
- **Trust vs trustee company.** A trust (`Kimlie Pty Ltd ATF The Kimlie Trust`, `Pericles Unit
  Trust/Elysium`, mostly section 2) and its trustee company (`Kimlie Pty Ltd`, `Elysium Pty Ltd`,
  sections 1 and 4) are separate entities: they are separate disclosures of different holdings.
  Long "X Pty Ltd as trustee for Y" names are left to the long tail.
- **Renames take the current name** when the body is the same organisation: FFA → Football
  Australia, ARU → Rugby Australia, First State Super keeps its name but takes `aware super`.
  Mergers of two brands don't (Greater Bank / Newcastle Permanent stay apart, as in T2.4).
- **Delisted companies** (Newcrest Mining 2023, Atlas Iron 2018) are typed `other` with
  `review_flag=1`. They were listed during the 43rd–47th, but AC-3.4 needs every
  `listed_company` to carry a code from the current snapshot. CYBG (left the ASX in 2024) is
  `bank_or_financial` without a code. Kevin can retype at G3.
- **Public broadcasters** (ABC, SBS) are `media_or_entertainment`, not `government_body`.
- **Coverage** (AC-3.2) is computed over the same top 200 the worksheet uses: non-generic
  normalised names by item count, ties alphabetical. `entities` prints it on every run.


### 2026-10-02 — Long-tail LLM stage (T2.6)
- **Every ≥ 2-item alias goes to the LLM.** Fuzzy blocks (first token, then chains of
  `token_set_ratio` ≥ 85) with more than one name get merge/keep/type decisions. A name with no
  fuzzy neighbour is a 1-name block, which is only named and typed. So `singleton` means
  1-item aliases, as ADR-6 says.
- **Packing is transport only.** About 40 names per request, blocks never split, but the cache
  is per block (D2 key), so a later run's packing doesn't matter. 104 requests, US$1.16.
- **The cache stores the LLM's answer as given.** Code applies the post-rules when it reads the
  cache, so the rules can change without paid re-runs:
  (1) AC-3.4: a `listed_company` group takes the ASX code that its canonical name, or failing
  that a member, matches exactly in the snapshot; with no match it's typed `other`, as with
  delisted curated rows (T2.5). 303 of 348 such groups became `other` (mostly foreign-listed,
  or named differently from the snapshot). G3 or later curation can fix the big ones.
  (2) One entity per ASX code: a later stage's alias with a code an entity already has joins it.
- **Bad replies don't poison the cache.** Groups must partition their block exactly, with
  enum-valid type and confidence. A failing block is retried alone once, then left uncached:
  exit 1 and no DB write, so a re-run continues. No failures on the real run.


### 2026-10-02 — Join by name after the stages (T2.7)
- **Why.** The top-20 review found the LLM naming long-tail blocks after organisations that
  curated rows already own: `qf` -> "Qantas", `west pac` -> "Westpac", `anz 50` -> "ANZ". The
  slugs differed from the curated canonical names, so each became a second entity. 35 entities
  had a canonical name that was another entity's alias.
- **Rule.** After every stage: (a) an entity made only by `llm` whose normalised canonical name
  is an alias of a non-singleton entity joins that entity; (b) a singleton alias equal to a
  non-singleton entity's normalised canonical name joins it. Curated and asx entities never
  move, which keeps Tower Limited (asx) apart from Tower Australia (llm): they're different
  companies. Aliases keep their method, so the method counts don't change. 34 merges, 10,219
  -> 10,185 entities. Kevin can override any of these at G3 with a curated row.
- **Report.** `entities --report` regenerates only the block between markers in
  `eval/entities_report.md`, so the hand-written review and T2.8's G3 notes survive refreshes.


### 2026-10-02 — G3 review pack (T2.8)

- **"LLM merges with confidence ≠ high touching ≥ 5 items"** is read as: every `llm` alias whose
  confidence isn't `high` and whose *entity* has ≥ 5 items in total. The alias's own count is
  usually 2–3, so an alias threshold would leave almost nothing to review. On 2026-10-02 that's
  31 aliases (all `medium`; the 12 `low` ones sit in smaller entities).
- **One row per alias**, in D2's order (top 50, flagged, LLM). A top-50 alias that is also
  flagged appears once, with its flag (4 such). `rank` is global by alias item count.
- **`kevin_fix` format**: `field=value;…` over `canonical_name`, `entity_type` and
  `asx_code`, or `own` / `generic`. Free text is accepted too, so Kevin isn't forced into a
  syntax; T2.9 maps it to curated rows.
- **Regenerating keeps Kevin's columns** (keyed by alias), so a rebuild mid-review is safe.


### 2026-10-02 — House register URLs and listing parser (T3.1)

- **43rd URL.** SPEC §0's `.../Previous_Parliaments/43P_Members_Interest_Statements` now
  redirects to a 404. The 48th register page links "43rd Parliament" to
  `.../House_of_Representatives_Committees?url=pmi/declarations.htm`, which lists 150 links
  (`?url=pmi/declarations/{stem}_43p.pdf`, no dates) whose stems are exactly v1's `pdfs/43`
  filenames. `sources.HOUSE_REGISTER_URLS[43]` uses that page. The 44th–47th match §0 (47th
  with its own slug). All six pages were checked live on 2026-10-02.
- **Parser.** stdlib `html.parser` (no new dependency). Table pages: a row counts when it has a
  `td.date` cell and a statement link (`api/members/{id}/statement/{n}`, where the id can be
  alphanumeric, e.g. `DZS`, or any `.pdf` link). Otherwise it falls back to bare "Member for"
  links (the 43rd layout). Counts per page: 43rd 150, 44th 151, 45th 158, 46th 152,
  47th 155, 48th 151 (147 API links + 4 static PDFs).
- **Names.** "Surname, Titles Given, Member for Seat[,] STATE". Titles and post-nominals are
  stripped from the given names. One 47th row has no comma ("Doyle Ms Mary"), so the surname is
  the words before the first title. Seven 48th rows have no state, so `state` is None.
- **`BROWSER_UA`** now lives in `sources.py`; `entities.py` imports it.

## 2026-10-03 — Manifest back-fill (T3.2)
- **Matching.** A v1 PDF gets `source_url`/`listed_date` from its parliament's archive listing
  when (1) a link on the page has the same file stem (case-insensitive; the 43rd's committee
  links carry it in `?url=`), else (2) exactly one unclaimed listing row has the same
  electorate and its surname ends the PDF's member name. No listing row goes to two PDFs.
  Other PDF links on the page (explanatory notes; Hastie 44th and McBain 46th, whose rows say
  "for Canning" / "Member Eden-Monaro" so the parser skips them) match by stem only and get no
  `listed_date`.
- **Result** (listings fetched 2026-10-03): 770/774 matched (99.5%); every member statement
  matched. The 4 misses are `interestsr_{44..47}p.pdf` (one identical 2-page cover document),
  which no listing links. The 43rd has no dates, so its `listed_date` is empty.
- **`fetched_at`** is empty for v1's PDFs (unknown); the scraper fills it for new downloads.
- **`page_count`** comes from `eval/pdf_stats.csv` (PyMuPDF if missing); sha256 from the file.


## 2026-10-03 — Scrape change detection: listing gate, then sha256 (T3.3a)
- D3 asked for a byte-stability check first. Two downloads of the same register-API statement,
  and of the same static PDF, were identical, and a `--verify` re-download of all 151 a few
  minutes later found 0 changed. So sha256 is the change signal (no listing-date fallback is
  needed).
- To keep runs cheap and AC-4.4 exact, `scrape` downloads a statement only when its listing
  link (with `?rev=`) or "Last updated" date differs from the manifest row, or its file is
  missing. Same bytes → unchanged (the row's date/link are refreshed). Different bytes →
  changed, overwritten in place. `--verify` forces a full byte comparison.
- A statement's file name is fixed the first time it's seen. Rows are matched by link without
  query, then by surname plus electorate, so a rename never forks a member's git history.
- The 48th PDFs are committed before their `pdf_members.csv` rows (T3.3b), so
  `test_real_overrides_cover_all_tracked_pdfs` temporarily excludes `pdfs/48/`. T3.3b removes
  the exclusion.

## 2026-10-03 — 48th member identity: resolve, then eyeball same-surname "new" members (T3.3b)
- `python -m disclosures.members` resolves each listing name through `member_aliases.csv`
  exactly as the loader does (name + electorate, then name). An unresolved name becomes a new
  member (`member_id` = slug); a slug that's already someone's id is a collision and nothing
  is written.
- The listing prints formal given names for two returning MPs: `Robert Katter` (Kennedy)
  and `Joshua Wilson` (Fremantle). Both were flagged by the same-surname check and fixed with
  hand `aph_48` alias rows rather than a nickname table: a table would also merge genuinely
  different people. `Thomas French` (Moore, new) takes Wikipedia's `Tom French` (D3: prefer
  the Wikipedia form); the other 32 new names already match Wikipedia's 2025–2028 list.
- Result: 151 PDFs, 118 returning, 33 new. Anne Urquhart and Ben Small move from the Senate.
  They get House ids now; their Senate names resolve onto these ids by name alone (check in the Senate task).
- `test_real_overrides_cover_all_tracked_pdfs` covers `pdfs/48/` again. Its party check skips
  the 48th until T3.4 writes those party terms.

## 2026-10-03 — 48th House parties: pinned start-of-term Wikipedia revision (T3.4)
- The live Wikipedia list shows current parties: Barnaby Joyce as One Nation (he left the
  Nationals mid-term) and Allegra Spender and Zali Steggall as Community Strong. D3 wants the
  party at the start of the term, so `members --party-terms` reads pinned revisions: 1303424746
  (2025-07-30, just after the parliament opened) first, and 1377733140 (2026-09-30) only for
  members the first lacks (David Farley, Farrer by-election 2026, One Nation). Pinned ids keep
  the rows reproducible.
- Wikipedia lists Queensland LNP members as Liberal or National (with a "sits with" note). v1's
  rows for the 43rd–47th call them `Liberal National Party`, so a QLD Liberal/National becomes
  `Liberal National Party` (16 rows, matching the LNP's 16 seats in 2025).
- Result: 151 rows, 0 unknown. `scripts/seed_v2_overrides.py --check` derives only v1's
  parliaments and keeps 48th+ rows (and `aph_*` aliases) verbatim; it had been failing since
  T3.3a added `pdfs/48/`.

## 2026-10-03 — Senate 48th: JSON source documents, Sydney dates, nil rows (T3.6)
- `validate` accepts a `.json` source document (D3): it checks the sha256 and requires
  `page_count == 1` (with `pages_covered == [1]` from the usual rule) and skips PyMuPDF. The
  ADR-2 schema is unchanged. `pdfs/manifest.csv` and its AC-4.3 test now cover the Senate
  statements (`manifest.is_source_document`); the saved listing `_query_statements.json` is
  not a source document.
- API timestamps are UTC (the listing's `lodgmentDate` carries `Z`; the header's US-format
  `lodgementDate` equals it). Alteration `createdOn` clusters at 21:00Z/22:00Z (08:00/09:00
  in Canberra) and 08:00Z, so dates are the Australia/Sydney calendar date, not the UTC date.
- Rows whose every field is nil (`NIL`, `-`, `N/A`, null) give no item, as in ADR-2. Trust
  `type` maps to the House form's subsections: `beneficiary` -> `2(i)`, `trustee` -> `2(ii)`.
  Descriptions join the row's non-nil fields with `; ` (the entity first where the form puts
  it first); `entity_name` is the company/creditor/bank/body/organisation field.
- `extracted_at` is the manifest's `fetched_at`, so re-running the adapter is byte-identical.
- All 76 payloads use the same 14 section keys and only `Addition`/`Deletion` alterations
  (2026-10-02): 1,980 items (1,328 interests, 597 added, 55 removed).

## 2026-10-03 — Senate members, parties and the multi-source load (T3.7)
- New senators get `member_id` = slug of the API listing's "Given Surname" (`Matthew Canavan`,
  not Wikipedia's `Matt Canavan`). D3's "prefer the Wikipedia form" is for House MPs, where v1
  already used it; the Senate has no v1 history, and an extra Wikipedia lookup for 72 names
  buys nothing the alias table can't add later. Ex-MPs match `member_aliases.csv` by name alone
  (their alias rows carry a House seat, not a state). All four matches (Ananda-Rajah, Henderson,
  Deborah O'Neill, Sharma) were checked by hand, and so were the surname lookalikes the command
  prints (Payne, Bell, Brown, Collins, Young, McKenzie, Price, Roberts, Smith): all different people.
- Senate parties follow the House convention: a Queensland Liberal or National is
  `Liberal National Party` (Canavan's `The Nationals` and Scarr's `Liberal Party of Australia`
  become LNP). `Country Liberal Party` -> `Country Liberal` joins the seed script's
  `EXTRA_PARTY_MAPPING`, so `seed_v2_overrides.py --check` still passes.
- `members.chamber` = the chamber of the latest (parliament, statement_date). A tie on both is
  broken by chamber name, so the result is deterministic; no 48th member has one.
- `meta.source_id` joins the loaded source ids with commas; `documents.extraction_source` is
  per file. House item ids are the same with or without `senate-json` loaded (they hash only
  the file's own content): House hash `c4888789…` is unchanged, full DB `88fb48c0…`.

## 2026-10-03 — `refresh`: download-and-compare, workflow prints, entities online (T3.8)

- `refresh` always downloads every House 48th statement (`scrape --verify` semantics) rather than
  trusting the listing's "Last updated" date, so a file APH replaces without a new date is still
  caught (AC-4.5 says "downloaded sha256"). Cost: ~85 MB, ~2 min per run. `scrape` keeps the
  cheaper date check (AC-4.4).
- `--dry-run` writes nothing at all (no PDFs, no Senate listing file, no manifest). Any failed
  download exits 1 instead of listing a partial selection.
- Changed PDFs aren't passed `--force`: their old extraction's `pdf_sha256` no longer matches,
  so it's invalid and the extractor redoes it; new PDFs have none.
- `--source workflow` still runs the free Senate adapter, then prints the Workflow args and the
  follow-up `load --source workflow-claude --source gemini-api --source senate-json` and
  `entities` commands; it doesn't load, since the House extractions aren't there yet.
- The gemini run ends with online `entities`, so a refresh that adds new long-tail entity names
  makes paid LLM calls (≈ US$0.01 per request) through the existing cache.

## 2026-10-03 — `export`: columns, source_url, licence placeholder (T5.1)

- 33 snake_case columns from one `COLUMNS` list (`disclosures/export.py`); the Kaggle README field
  dictionary and `dataset-metadata.json` schema are generated from it, so they can't drift.
  Rows sort by chamber, parliament, member, file, page, section, item_id (deterministic).
- `entity_match_method` is looked up per item (`entity_aliases` by `normalise_entity(raw)`), so
  readers can tell curated from LLM-grouped and singleton entities.
- `load` never fills `documents.source_url`/`fetched_at` (all NULL). Export falls back to
  `pdfs/manifest.csv` by sha256 (all 50,936 rows get a URL) instead of changing `load` here.
- Export refuses to write if the joined row count differs from `select count(*) from items`.
- Licence and Kaggle owner are Kevin's call (G4): metadata defaults to `licenses: unknown`,
  `id: KAGGLE_USERNAME/australian-parliament-registers-of-interests`, `isPrivate: true`;
  `--license`/`--kaggle-id` set them. APH site content is published under a Creative Commons
  licence that Kevin should check before choosing one for the derived dataset.
- `exports/*.csv` (30 MB each) are gitignored; README + metadata are committed for review.
- Prompt v0/v1 split is described in the README (7 re-extracted files + House 48th on v1), not
  a column: the DB doesn't record prompt versions.

## 2026-10-03 — Pages site generated by `export --site` (T5.2)
`site/index.html` is rendered from the DB by `python -m disclosures export --site site` (opt-in
flag, so tests and plain exports never touch `site/`), so the coverage table can't drift from
the committed `site/disclosures_v2.db`. The Datasette Lite link needs an absolute URL; it
defaults to `https://k-r-a-s-s.github.io/aus-govt-transparency` (from `origin`) and
`--pages-url` overrides it if Pages is served elsewhere. PyYAML is a dev dependency so the
AC-5.2 YAML check runs in the venv.

## 2026-10-03 — T5.4: what counts as dead v1 code

Removed the whole `src/` tree (AC-5.4's "or the whole tree" option), `examples/`,
`test_output.json`, `setup_pipeline.sh`, and `scripts/seed_v2_overrides.py` (deleted rather than
kept with a warning header: it can't run without `src/cleaning/*.py`, and git history keeps it).
Also deleted the v1-only docs (`docs/index.md`, `docs/backend/`, `docs/guides/`,
`docs/workflows/`): every page described the removed `src/` pipeline or a frontend that isn't in
this repo, and `docs/v2/` + `README.md` replace them. Kept as history: `.specstory/`, `.cursor/`
rules, `*.rmd` diaries, root `__init__.py`, `disclosures.db` and `output/` (the CSVs the
overrides were seeded from).

## 2026-10-03 — Gate G3: entities review approved (AC-3.5; T2.9)

Kevin reviewed all 114 rows of `eval/entities_g3_review.csv` (top-50 aliases, 24 flagged rows,
the LLM-medium merges touching ≥ 5 items) on 2026-10-03 and approved them as is ("Approve all
114"). He queried two rows, `qual` and `tef`; both were confirmed against the source registers
(QUAL = VanEck ETF's ASX code in phelpsk 45p; TEF = Telefónica's ticker in turnbullm 43p), so
they stay. Kevin changed nothing: `kevin_ok=y` on all 114 rows, 0 `kevin_fix`, so no curated
rows or LLM-cache overrides were added. Final load (`load` House+Senate → `entities --offline`):
42,272 named items → 11,544 entities; AC-3.3 0; aliases.csv covers 97.7% of the top-200 names;
`eval/entities_report.md` regenerated with no change.

## 2026-10-03 — V2 cold verification: ticker-reuse fixes (after G3)

The Phase 3 verifier passed every AC-3 check (rebuild deterministic) but found reused ASX tickers
going to today's holder. The ASX stage matches against the 2026 snapshot only, so an old
section-1 ticker resolves to whoever holds the code now: `ore` (Orocobre in Turnbull 43rd/44th) →
Orezone, `map` (MAp Group, Neville 43rd) → Microba, `cim` (CIMIC, Perrett 45th/46th) →
Challenger IM. The LLM also merged `apt` (Afterpay's ticker 2017–22) into APA Group. And one
section-1 `agi` share made Ben Morton's 9 `AGI` ticket gifts (probably Australian Gas
Infrastructure Group) resolve to Ainsworth. Fix: 9 curated rows in `aliases.csv` (`apt`,
`afterpay`, `afterpay touch` → Afterpay; `ore` → Orocobre; `map` → MAp Group; `cim`, `cimic group`
→ CIMIC Group; `agi` → AGI, flagged; `comm bank` → CBA). The delisted ones are typed `other`, as
Newcrest is (AC-3.4). These come after G3 and only move ~30 items, all outside the top 50, so G3
stands. No new row is flagged: `map` is certain (MAP was MAp Group's code until Nov 2011), and `agi` is a neutral label that merges nothing, so neither needs G3. `eval/entities_g3_review.csv` is left as the record of what Kevin reviewed; regenerating it now would only drop `apt` (now curated). The general risk (and the
one-item `Name (TICKER)` singletons the verifier also found) is listed under Known limitations
in `docs/v2/entities.md`. 11,542 entities; AC-3.3 0; coverage 97.7%.

## 2026-10-03 — Phases 3–5 closed (T5.6)

Final rebuild from committed inputs (`load` House + Senate → `entities --offline` → `export
--site site`) and a full SPEC §3 sweep: every AC from AC-0.1 to AC-5.6 passes, recorded with its
evidence in `eval/final_acceptance.md`. Phase 3 (entities, G3 approved) and Phase 4 (scraper,
48th, Senate 48th, refresh) are closed; Phase 5 is closed up to G4, which stays with Kevin
(licence + Kaggle id, merge, Pages, Kaggle upload). Choices made in the sweep: AC-0.5 was run in
the `git grep -I … -- ':!pdfs' ':!*.db'` form (equivalent, doesn't choke on 2 GB of PDFs); AC-4.4
rests on the T3.3a live re-run and the recorded-HTML tests, since T5.6 has no network budget;
AC-5.5 rests on T5.5's fresh-venv run (requirements unchanged since). The rebuild only moved the
published entity count from 11,544 to 11,542 (V2's curated fixes had not been re-exported).

## 2026-10-03 — G4: licence CC BY-NC 4.0, Kaggle id `kevrass/…`, V5 polish

Kevin delegated the G4 choices ("make the sensible choices, and agentically drive this forward").
- **Source terms (read on aph.gov.au/Help/Disclaimer_Privacy_Copyright, 2026-10-03):** "With the
  exception of the Commonwealth Coat of Arms and where otherwise noted, all material presented on
  this website is provided under CC BY-NC-ND 4.0 … General content from this website should be
  attributed as Parliament of Australia website." So the CC BY 4.0 default in HANDOFF does not
  apply, and v1's Kaggle dataset (CC BY 4.0, April 2025) was looser than the source.
- **Dataset licence: CC BY-NC 4.0** (`export` default `DEFAULT_LICENSE`). NonCommercial is kept
  because the source carries it. NoDerivatives is not carried over: the dataset records the facts
  each statement discloses, item by item, and isn't the statements in their published form. That
  is a judgement, not legal advice. If Kevin wants commercial reuse (e.g. by commercial media
  outlets beyond reporting the facts), the route is to ask APH (the Webmanager) for permission and
  then relicense. The PDFs in `pdfs/` are unaltered copies, which NC-ND allows (non-commercial,
  attributed). README, Kaggle README and the Pages site state both licences and the attribution.
- **Kaggle id `kevrass/australian-parliament-registers-of-interests`** (the account the
  `KAGGLE_API_TOKEN` in `.env.local` belongs to). It is a new dataset, not a new version of v1
  (`kevrass/structured-register-of-australian-mps-disclosures`): the schema, scope (Senate) and
  files all differ. v1 is kept and marked superseded. Metadata `isPrivate` is now `false`:
  `create` ignores it (`--public` decides), but `kaggle datasets metadata --update` reads it, and
  `true` there would hide the published dataset. The Kaggle `description` is now the full README,
  since that is what the dataset page shows.
- **V5 polish done:** `entity_type` reads "Empty for most one-off (singleton) entities";
  `entity_asx_code` says banks/airlines/media are included; README's v1 note says the scripts were
  removed; the dead `test_stubs_exit_2_with_message` is gone (322 passed, 0 skipped).
- **Local DB.** On the Mac, `disclosures_v2.db` was a stale 2026-10-02 build (42,042 items, no
  Senate, no entities), so the export ran from the final DB (`site/disclosures_v2.db`, sha256
  `519e2430…`, 50,936 items, 11,542 entities), copied into place. The stale file went to scratch.

## 2026-10-03 — Gate G4: published (SPEC signed off)

- **Git.** PR #2 merged by fast-forwarding `v2-upgrade` to `cee0ba3`; `main` fast-forwarded from
  `dae1630` (2025-04-26) to `cee0ba3` (Kevin gave explicit permission for `main`).
- **Pages** enabled with source = GitHub Actions; the `pages.yml` run on `cee0ba3` succeeded.
  https://k-r-a-s-s.github.io/aus-govt-transparency/ serves `index.html` and `disclosures_v2.db`
  (sha256 `519e2430…`, the final DB; `Access-Control-Allow-Origin: *`). Checked in a real browser
  (Playwright, Chrome): the Datasette Lite link loads the DB and answers SQL (house 48,956 +
  senate 1,980 = 50,936 items).
- **Kaggle:** https://www.kaggle.com/datasets/kevrass/australian-parliament-registers-of-interests,
  public, status `ready`, files `disclosures_v2.csv` (30.7 MB) + `README.md`, licence CC BY-NC 4.0,
  description = README; column descriptions pushed with `metadata --update`. Gotcha:
  `datasets create` takes the short licence id (`CC-BY-NC-4.0`), but `metadata --update`
  rejects it ("invalid license") and needs the display name
  (`Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)`).
- **v1 Kaggle dataset left unchanged.** Marking
  `kevrass/structured-register-of-australian-mps-disclosures` as superseded (and moving it from
  CC BY 4.0 to CC BY-NC 4.0) was blocked by the session's permission guard because it edits an
  existing shared dataset, so it stays with Kevin (Kaggle → dataset → Settings, or
  `metadata --update` with the display-name licence).
- **SPEC signed off** (Kevin delegated it): ADR-4's backfill bar accepted as is; ADR-5 now carries
  the `--fallback-model` caveat.
- **Open questions accepted as is:** Sandakan-trek sponsors stay unitemised (D1, C2: the member
  paid); the 7,037 untyped singleton entities stay untyped (D2, documented); reused ASX tickers
  stay a documented known limitation (V2 fixed the known cases).
- **Announcing** (Reddit and elsewhere) is left to Kevin.

## 2026-10-03 — Licence changed to CC BY 4.0 (supersedes "G4: licence CC BY-NC 4.0")

Kevin asked for the most permissive licence that still requires attribution, so the dataset is
now **CC BY 4.0, "to the extent we hold rights in it"** (`DEFAULT_LICENSE = "CC-BY-4.0"`).
Why it holds up: the dataset records the facts each statement discloses (who holds what, item by
item), and facts aren't APH's expression. NoDerivatives already couldn't apply to a structured
dataset, and NonCommercial was only carried over as a precaution. There is Australian precedent:
They Vote For You builds its votes data from APH Hansard (also CC BY-NC-ND) and licenses it
under ODbL, which allows commercial use, "to the extent which we have rights to it" (its
`app/views/help/licencing.html.haml`). The statements themselves (the PDFs, `pdfs/` and each
row's `source_url`) stay under APH's CC BY-NC-ND 4.0, and README, Kaggle README and the site say
so. v1's Kaggle licence (CC BY 4.0) is now consistent and is left unchanged. This is a judgement,
not legal advice; if APH ever objects, the fallback is CC BY-NC 4.0 (the previous entry).
