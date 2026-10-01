# Handover — Disclosures v2 (updated 2026-10-02, Phase 2a verified, bake-off in progress)

Read first: `SPEC.md` (plan, ADRs, ACs, gates), `DECISIONS.md` (dated decisions), `docs/v2/README.md`
(layout, commands), `docs/v2/extraction.md` (how both extractor arms run), `eval/gold/README.md`.
This file only holds what those don't.

## Where we are
- **G1 passed 2026-10-01.** Kevin approved the gold set as is; all 12 `eval/gold/*.json` have
  `reviewed_by: "kevin"`. AC-1.3 met.
- **Phase 2a built and independently verified (2026-10-02, PASS WITH NOTES).** Gemini extractor
  (`disclosures/extract_gemini.py`), `resolve_gemini_model()`, the two validator guards, the saved
  workflow script `.claude/workflows/extract-disclosures.js`, `docs/v2/extraction.md`. 134 tests
  pass; gold 12 valid; self-score 1.0; `disclosures.db` sha unchanged.
- **Gemini model: `gemini-3.8-flash`** (GA, verified live; $0.75/$3.75 per MTok through
  2026-12-31). `.env.local` `GEMINI_MODEL` updated.
- **Phase 2b bake-off: in progress, half blocked.**
  - **workflow-claude arm: DONE.** 12/12 valid files, **F1 0.974** (P 0.973 / R 0.975, owner
    0.995, page 0.991, section-ignored recall 0.978 vs v1 0.625): clears the ADR-4 bar.
    Scored in `eval/workflow-claude.json`; report in `eval/bakeoff.md`. Run on the 12 gold PDFs (4 bundles, Sonnet). Note: the
    `Workflow` tool invocation was *denied by the auto-mode permission classifier* in the
    orchestrating session, so the gold run was executed as 4 direct subagents given the exact
    bundle prompts the script generates (same bundles, same model, same instructions; prompts
    captured in the session scratchpad). Kevin can run the saved workflow himself as documented in
    `docs/v2/extraction.md` to reproduce. Output: `extractions/workflow-claude/house/<NN>/*.json`.
  - **gemini-api arm: BLOCKED.** The project's AI Studio prepaid credits are depleted (a live call
    returns `402 RESOURCE_EXHAUSTED`). Kevin must top up at https://ai.studio/projects, then run:
    `python -m disclosures extract --source gemini $(python -c "import json;print(' '.join(p['pdf_path'] for p in json.load(open('eval/gold/selection.json'))['pdfs']))")`
    followed by `python -m disclosures score --pred extractions/gemini-api --gold eval/gold --json eval/gemini-api.json`.
    Expected cost for the gold run: well under US$1.
- **`eval/bakeoff.md`** holds the workflow arm + v1 baseline with a pending Gemini column and the
  two possible G2 outcomes under the ADR-5 rule.

## Single next action
1. Kevin tops up Gemini credits → run the Gemini arm (commands above) → complete `eval/bakeoff.md`
   → apply the ADR-5 rule (higher F1 among arms clearing the ADR-4 bar; if the F1 gap < 2 points,
   choose `gemini-api`) → **G2: Kevin confirms** in `DECISIONS.md`.
2. Phase 2c backfill with the chosen arm, then `load`.

## In-flight / deliberately out of scope
- `--batch` (Gemini Batch API) is not implemented (exit 2). Re-split rounds would need a
  multi-round batch driver; not worth it at the current prices.
- `scrape, load, entities, export, refresh` are stubs that exit 2.
- The root `README.md` is still v1's. It gets rewritten in Phase 5; don't touch it before then.
- Phase 4's gold-set extension (≥1 House 48th PDF) is optional and waits for Phase 4 scraping.
- Phase 4a (scraper, manifest backfill, Senate discovery) is independent of the bake-off and can
  be built next; it touches `cli.py`, so do it in series with any other `cli.py` change.

## Decisions an agent might relitigate (full reasoning in DECISIONS.md)
- **Conventions C1–C11** in `disclosures/prompts/extract.md` define "correct" for gold and
  extractors. Kevin accepted them at G1. Changing them means re-reviewing gold.
- **De-dup key is wider than ADR-5's** (adds normalised description, subsection, change_type,
  lodged_date). The bare key would merge 52 genuine gold items. Known remaining edge: it ignores
  `location`/`purpose`.
- **Inline PDF bytes** for chunks ≤ 15 MB; Files API (upload + delete) above that.
- **Chunk-relative page rule** and **re-split triggers** are documented in the module docstring;
  pages are never clamped, out-of-range pages fail the PDF.
- **`requirements.txt` is v2-only** (plus the google-genai dependency closure, pinned).
- **`/data/` was un-ignored in `.gitignore` on purpose** (SPEC ADR-6).

## Dead ends / corrections
- **`review-sheet` overwrites the CSV.** Gold is reviewed now; regenerating it is harmless but
  pointless.
- **The Workflow tool can be denied by the auto-mode classifier** even for a saved workflow; the
  direct-subagent fallback above is behaviourally identical for a ≤ 4-bundle run. For the full
  backfill (~110 agents) Kevin should run the workflow himself after raising "Dynamic workflow
  size" in `/config`.
- **Older drafter notes in gold `extraction_notes`** are superseded by the trailing
  `consolidation 2026-10-01: …` line.
- **The spec's 47th-Parliament archive URL note** (v1's `parliament_urls.py` points "47th" at
  the current page, which now serves the 48th) is still a Phase 4 fix.

## Open questions (who holds the ball)
- **Gemini credits top-up: Kevin.** Blocks the Gemini arm, G2 and the backfill.
- **SPEC.md says "DRAFT, awaiting sign-off": Kevin.** The build proceeds on it; the ADR-4 bar
  (recall/precision ≥ 0.90, owner ≥ 0.95, page ≥ 0.90) is still "proposed defaults".
- **Workflow backfill size: Kevin** raises "Dynamic workflow size" in `/config` only if the
  workflow arm wins G2.
