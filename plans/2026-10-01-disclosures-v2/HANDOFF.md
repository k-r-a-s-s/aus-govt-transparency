# Handover — Disclosures v2 (updated 2026-10-01, Phase 1 verified, paused at G1)

Read first: `SPEC.md` (plan, ADRs, ACs, gates), `DECISIONS.md` (dated decisions), `docs/v2/README.md`
(layout, commands), `eval/gold/README.md` (gold workflow, how Kevin reviews). This file only
holds what those don't.

## Where we are
- Phase 1 (contract, validator, scorer, gold set, v1 baseline) is built **and independently
  verified** (air-gapped Fable verifier, 2026-10-01): all AC-0 and AC-1 criteria met except
  AC-1.3, which is pending the human gate. Gold spot-check: 418 of 790 items compared against
  the rendered PDF pages across all 12 PDFs (the four handwritten/scanned ones read cover to
  cover), 0 discrepancies. Status: `pytest -q` 96 passed; `validate eval/gold` 12 valid;
  self-score 1.0; v1 baseline section-ignored P 0.856 / R 0.625 / F1 0.723; `disclosures.db`
  sha unchanged.
- **Single next action: human gate G1.** Kevin reviews `eval/gold/review.csv` (790 rows; the
  213 `medium`-confidence rows first, then the five judgement calls below), applies any
  `kevin_fix` edits to the JSON by hand, then runs `python -m disclosures.gold apply-review`.
  The Phase 2 bake-off must not start until every gold file has `reviewed_by: "kevin"`.
- What an agent can do while Kevin reviews: **Phase 2a** (shared prompt is done; Gemini
  extractor with mocked-client tests; saved workflow script `.claude/workflows/extract-disclosures.js`;
  verify the live Gemini 3.x model id and record it in `DECISIONS.md`; update `GEMINI_MODEL`
  in `.env.local` — value only, never print the key). Also **Phase 4a** (scraper, manifest
  backfill, Senate discovery) is independent of the gold review. Do not regenerate
  `eval/gold/review.csv` while Kevin is reviewing — it would wipe his ticks.

## Judgement calls for Kevin at G1 (verifier found no transcription errors; these are conventions)
1. **C4 `statement_date`** = signed date on the bound-in "since dissolution" page, not the
   page-1 stamp. Moved gosling, kingm, prenticej by 1–4 days.
2. **plibersekt p10** uses the legible signed "7.5.11" (2011-05-07) although the notice is
   stamped 6 JUL 2011 and discloses a 15 June event.
3. **Not C1-split**: plibersekt p3/p4 spouse-row "(jointly)" property and mortgage, and
   gosling p8 "Family tickets" — neither names the member. Add `self` rows if you disagree.
4. **C3 confidence is uneven** for lounge memberships printed under section 12 on initial
   statements: prenticej p6 and morrison p5 are `high`, tink p11 is `medium`. Pick one.
5. **`electorate_or_state` format** varies (electorate only vs "Electorate, State"). Harmless
   now; only matters if that field is ever scored.

## In-flight / deliberately out of scope
- `reviewed_by` is null (or absent in gosling/prenticej/thistlethwaitem — `apply-review` adds
  it) on all 12 gold files. `kevin_fix` notes are applied by hand, never by a command.
- Two validator guard gaps the verifier reported, not fixed (gold data is consistent, so no
  data bug): `is_alteration` vs `change_type` is not cross-checked
  (`is_alteration:true, change_type:"initial"` passes); `date_precision:"month"` with a
  full-day date passes. Worth adding in Phase 2a before extractor output is gated by `validate`.
- `scrape, extract, load, entities, export, refresh` are stubs that exit 2.
- The root `README.md` is still v1's. It gets rewritten in Phase 5; don't touch it before then.
- Phase 4's gold-set extension (≥1 House 48th PDF) is optional and waits for Phase 4 scraping.

## Decisions an agent might relitigate (full reasoning in DECISIONS.md)
- **Conventions C1–C11** in `disclosures/prompts/extract.md` are the definition of "correct"
  for both the gold set and the extractors. Change them only via G1, and if you do, re-apply
  to all 12 gold files (the traceable edit script was `scratchpad/phase1c/consolidate.py`,
  session-local; gold edits are also noted per file in `extraction_notes`).
- **C3:** sections are kept as printed even when wrong, with `medium` confidence.
- **C6:** one gift from several co-providers (kingm p12) stays one item.
- **`requirements.txt` is v2-only.** The v1 deps were dropped on purpose.
- **`/data/` was un-ignored in `.gitignore` on purpose:** v2 commits `data/overrides/`,
  `data/entities/` and `data/reference/` (SPEC ADR-6).
- **Pydantic strict vs JSON Schema.** Strict rejects `2.0` for an int; JSON Schema accepts it.
  Expected, safe direction.
- **Gold drafting method** (if the set is ever extended): one Opus agent per 3–4 PDFs
  (~75 pages each), reading with `Read` in ≤20-page ranges, writing disjoint `eval/gold/<stem>.json`
  files; then one consolidation pass for conventions; then a verifier spot-check against the
  PDFs. Give each parallel agent its own scratchpad subdirectory — they collided on `build.py`.

## Dead ends / corrections
- **Superseded drafter notes.** Older drafter text in `extraction_notes` (e.g. prenticej's
  "recorded as owner=self (one item)") is superseded by the trailing
  `consolidation 2026-10-01: …` line. The JSON items follow the consolidation line.
- **`review-sheet` overwrites the CSV, wiping Kevin's ticks.** Don't regenerate mid-review.
- **The pre-Phase-1c `eval/v1_baseline.json` covered only 1 PDF.** The committed one covers 12
  and matches a fresh run exactly.
- **The spec's 47th-Parliament archive URL note** (v1's `parliament_urls.py` points "47th" at
  the current page, which now serves the 48th) is still a Phase 4 fix; nothing in Phase 1
  touches scraping.

## Open questions (who holds the ball)
- **G1 gold review: Kevin** (items 1–5 above, plus any `kevin_fix` rows).
- **SPEC.md says "DRAFT, awaiting sign-off": Kevin.** The build proceeded on it; the ADR-4
  bar (recall/precision ≥ 0.90, owner ≥ 0.95, page ≥ 0.90) is still "proposed defaults".
- **Gemini model id and price: next agent** (Phase 2a) — verify live with
  `client.models.list()`; `gemini-[0-2].*` is banned by `resolve_gemini_model()` (to be written).
- **Workflow backfill size: Kevin** raises "Dynamic workflow size" in `/config` only if the
  workflow arm wins G2.
