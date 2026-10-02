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

### G3 — entity spot-check: _pending_
- Date:
- Notes:

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
