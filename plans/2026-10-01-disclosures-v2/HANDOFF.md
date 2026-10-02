# Handover — Disclosures v2 (updated 2026-10-02 evening: OpenRouter bake-off done, G2 recommendation ready, backfill not started)

Read first: `SPEC.md` (plan, ADRs, ACs, gates), `DECISIONS.md` (dated decisions, incl. G1/G2),
`docs/v2/README.md` (layout, commands), `docs/v2/extraction.md` (both extractor arms, both
transports), `docs/v2/loading.md` (loader), `data/overrides/README.md`, `eval/bakeoff.md`. This
file only holds what those don't.

## Where we are
- **Phases 1, 2a, 2c-loader: built, verified, committed.** `disclosures.db` (v1) sha unchanged.
- **Extractor B now has an OpenRouter transport** (`disclosures/openrouter.py`, `--provider
  openrouter`, default when `OPENROUTER_KEY` is set), `--workers N`, and a per-chunk
  `--fallback-model`. 182 tests pass (26 new, all mocked; ADR-11). Docs updated.
- **Bake-off re-run with four arms on the gold set (`eval/bakeoff.md`).** All clear the ADR-4
  bar. F1: gemini-api 0.987 (Gemini 3.8 Flash on OpenRouter flex + Sonnet 5.5 fallback),
  Sonnet 5.5 0.977, workflow-claude 0.974, GPT-6 Luna 0.962. ADR-5 picks **gemini-api**
  outright. Gold outputs are committed under `extractions/gemini-api/`,
  `extractions/openrouter-gpt-6-luna/`, `extractions/openrouter-claude-sonnet-5.5/` (12 files
  each) with reports `eval/<source_id>.json`.
- **G2 is revisited but not confirmed.** `DECISIONS.md` has the dated "G2 revisited" entry with
  the recommendation; Kevin has not yet confirmed it.
- **Backfill: still 23 of 768** (the committed workflow-claude files). Nothing has been run on
  the non-gold PDFs.
- **OpenRouter credit ≈ US$17.5 of 30 remains** (check: `curl -H "Authorization: Bearer
  $OPENROUTER_KEY" https://openrouter.ai/api/v1/credits`). The backfill at the recommended
  configuration is ≈ US$22 (scaled from US$0.48 for the 289 gold pages), so it needs a top-up
  of ≈ US$10 or will stop part-way (idempotent: just re-run after topping up).

## Single next action
1. **Kevin confirms G2** (or overrules) in `DECISIONS.md`: a dated line under the "G2 revisited"
   entry. Also decide the spend: top up OpenRouter by ≈ US$10, or accept a part-way stop.
2. **Backfill** (only after 1). The statement list is `eval/pdf_stats.csv` rows with
   `is_statement=1` (768). In zsh use `${=VAR}` or inline the `$(...)` (zsh does not
   word-split `$VAR`; this silently broke three runs this session):
   ```sh
   .venv/bin/python -m disclosures extract --source gemini --provider openrouter \
       --model google/gemini-3.8-flash --provider-order google-ai-studio/flex \
       --fallback-model anthropic/claude-sonnet-5.5 --workers 8 \
       $(.venv/bin/python -c "import csv;print(' '.join(r['pdf_path'] for r in csv.DictReader(open('eval/pdf_stats.csv')) if r['is_statement']=='1'))") \
       2>&1 | tee -a eval/backfill-gemini.log
   ```
   It skips valid existing output (the 12 gold files), so re-run until
   `python -m disclosures validate extractions/gemini-api/house` is 0 invalid. Expect
   ≈ 660 chunks; at 4 workers the gold set (18 chunks) took ≈ 4 min, so budget a few hours at 8.
   Watch the log for `note … fallback` lines (RECITATION blocks) and `FAILED` lines.
3. Write `eval/extraction_failures.md` (AC-2.6): failed PDFs with reasons, plus the 6
   non-statements under "excluded: not a statement" (`interestsr_44..47p.pdf`,
   `explanatory_notes___booklet_1.pdf` ×2); 774 = valid + excluded + failed, ≤ 5 failures.
4. `python -m disclosures load --source gemini-api` and check AC-2.7–2.10; list the AC-2.7
   early-dated count in `eval/bakeoff.md`. Do not mix sources in one load.

## In-flight / deliberately out of scope
- `extractions/workflow-claude/` (23 files) stays committed as bake-off evidence and fallback.
- A `--reasoning-effort low` Gemini variant was being scored for cost at handover time
  (scratch output, not committed); if it lands, its numbers go in `eval/bakeoff.md` as a note.
  If its F1 holds within a point of 0.987, use it for the backfill to cut the thinking-token
  cost (Gemini's output tokens were 155k vs 186k input on the gold set).
- Gemini `--batch` is still not implemented (exit 2). OpenRouter's `:batch` is a separate async
  API; `provider.order google-ai-studio/flex` already gives the 50% price synchronously.
- `scrape, entities, export, refresh` are stubs (exit 2). Phase 4a is independent.
- Loader verifier notes left open (none block the backfill): alias fallback doesn't reorder
  "SURNAME Given"; a failing AC-2.7 hard gate still installs the DB (exit 1); some party-term
  labels are inconsistent for mid-term defectors.
- The root `README.md` is still v1's (rewritten in Phase 5).

## Decisions made this session (reasoning in DECISIONS.md)
- **Provider shortlist** (Kevin: "check a few different providers before committing"):
  Gemini 3.8 Flash, GPT-6 Luna, Claude Sonnet 5.5; others dominated on cost or capability.
- **Flex tier for Gemini** (Kevin: "flex is the right choice for this async stuff").
- **Per-chunk fallback model** added after Gemini's RECITATION block on morrison_47p p23 could
  not be cleared by re-splitting; the SPEC's "any other finish reason fails the PDF" rule now
  reads "… unless a fallback model is set". Provenance: `model` = `primary+fallback`,
  `extraction_notes` names the pages.
- **GPT-6 Luna rejected** despite being 3× cheaper: breaks convention C4 (stamp date instead of
  signed date; lodged_date accuracy 0.765).

## Dead ends / corrections
- **Gemini RECITATION is a hard block**, not a chunk-size effect (fails at 9, 5 and 1 pages on
  morrison p23). Don't retry it; use the fallback.
- **`openai/*` models reject `temperature`**; the transport omits it for them.
  `provider.require_parameters` + `temperature` returned 404 "No endpoints found" until fixed.
- **zsh `$GOLD` word-splitting** (see step 2). Three gold runs printed `pdfs=1` and "PDF not
  found" with 12 paths in one argument; no cost was incurred.
- **Running 20 Sonnet subagents at once** (workflow arm) burns the subscription cap in ~1 hour;
  the workflow arm is now the fallback of last resort only.
- **The AI Studio key is not usable** (prepaid credits depleted). Don't retry it.

## Open questions (who holds the ball)
- **G2 confirmation and the ≈ US$10 top-up: Kevin.**
- **SPEC.md "DRAFT, awaiting sign-off": Kevin.** ADR-4 bar still "proposed defaults"; ADR-5's
  "any other finish reason fails" wording should get the fallback caveat when SPEC is signed.
- **Luna's date bug**: not pursued. If cost ever matters more than dates, a one-line prompt
  change ("ignore PROCESSED/received stamps") might fix it; untested.
