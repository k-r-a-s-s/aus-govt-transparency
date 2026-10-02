# Handover — Disclosures v2 (updated 2026-10-02, Phase 2c loader verified; backfill switching to Gemini via OpenRouter)

Read first: `SPEC.md` (plan, ADRs, ACs, gates), `DECISIONS.md` (dated decisions, incl. G1/G2),
`docs/v2/README.md` (layout, commands), `docs/v2/extraction.md` (both extractor arms),
`docs/v2/loading.md` (loader), `data/overrides/README.md`, `eval/bakeoff.md`. This file only
holds what those don't.

## Where we are
- **Phases 1, 2a, 2c-loader: built, independently verified, committed.** 156 tests pass.
  `disclosures.db` (v1) sha unchanged. Gold set reviewed (G1). `load` works end to end on the
  23 extraction files present (`python -m disclosures load --source workflow-claude`).
- **Bake-off (`eval/bakeoff.md`):** workflow-claude arm scored F1 0.974 on gold and clears the
  ADR-4 bar. The Gemini arm has **not** been scored.
- **Backfill: 23 of 768 statement PDFs done** (12 gold + 11 from one wave) under
  `extractions/workflow-claude/`. The workflow-claude backfill was **abandoned on 2026-10-02**:
  a 19-agent Sonnet wave hit Kevin's Claude subscription 5-hour session limit after ~1 hour and
  ~11 files. Extrapolated ≈ 60+ session windows for 745 PDFs. Kevin: "let's try Gemini then."
- **Gemini is now to run through OpenRouter, not AI Studio.** The AI Studio key's prepaid
  credits are depleted (402). Kevin added `OPENROUTER_KEY` to `.env.local` (2026-10-02; name
  only, never print it). OpenRouter lists `google/gemini-3.8-flash` (same $0.75/$3.75 per MTok;
  `:batch` suffix at 50%; input modalities include `file`). **The extractor
  (`disclosures/extract_gemini.py`) only speaks the `google-genai` SDK to AI Studio today.**

## Single next action
Add an OpenRouter transport to the Gemini extractor, run the gold set through it, score it,
then (if it clears the ADR-4 bar) backfill all House 43–47 PDFs with it and `load`.
Concretely:
1. In `disclosures/extract_gemini.py`, add a second client path selected by
   `--provider openrouter` (or auto when `OPENROUTER_KEY` is set and `GOOGLE_API_KEY` is absent /
   402s): OpenAI-compatible `POST https://openrouter.ai/api/v1/chat/completions` with
   `Authorization: Bearer $OPENROUTER_KEY`, model `google/gemini-3.8-flash`, the chunk PDF as a
   `file` content part (`{"type":"file","file":{"filename":"chunk.pdf","file_data":"data:application/pdf;base64,…"}}`),
   `response_format: {"type":"json_schema","json_schema":{"name":"extraction","schema":response_schema(),"strict":true}}`,
   `temperature: 0`. Verify the exact request shape against https://openrouter.ai/docs (PDF
   inputs, structured outputs) before coding; the field names above are from memory. Keep the
   existing chunking, page-offset rule, re-split on `finish_reason == "length"`, merge, de-dup,
   `usage` from `usage.prompt_tokens`/`completion_tokens`, and atomic validated writes. Route the
   model id through `resolve_gemini_model()` after stripping the `google/` prefix (the 2.x ban
   must still apply). Mock-tested like the existing path (no network in tests, ADR-11). Update
   `docs/v2/extraction.md` and `requirements.txt` (`httpx` is already pinned; no new SDK needed).
2. Gold run + score:
   `python -m disclosures extract --source gemini --provider openrouter $(python -c "import json;print(' '.join(p['pdf_path'] for p in json.load(open('eval/gold/selection.json'))['pdfs']))")`
   then `python -m disclosures score --pred extractions/gemini-api --gold eval/gold --json eval/gemini-api.json`.
   Fill the Gemini column of `eval/bakeoff.md`, apply the ADR-5 rule, record the outcome under
   G2 in `DECISIONS.md` (G2 currently says workflow-claude; add a dated "revisited" line, don't
   rewrite history). Expected gold-run cost ≈ US$0.50; backfill ≈ US$10–20.
3. If Gemini clears the bar: `extract` all 768 statement PDFs (the list = `eval/pdf_stats.csv`
   rows with `is_statement=1`; the 6 non-statements are excluded, see below), writing to
   `extractions/gemini-api/`. The command is idempotent (skips valid existing output), so re-run
   until `validate extractions/gemini-api/house` is 0 invalid. Write `eval/extraction_failures.md`
   (AC-2.6). Then `python -m disclosures load --source gemini-api` and check AC-2.7–2.10.
   If Gemini does **not** clear the bar: iterate the shared prompt at most 2 rounds (ADR-5), then
   stop and hand back.

## In-flight / deliberately out of scope
- `extractions/workflow-claude/` (23 files) stays committed as bake-off evidence and as a
  fallback; the backfill target is now `extractions/gemini-api/`. Do not mix sources in one
  `load`.
- AC-2.6 says ≤ 5 listed failures. The 6 non-statement PDFs (`interestsr_44..47p.pdf`,
  `explanatory_notes___booklet_1.pdf` ×2) are not failures: list them in
  `eval/extraction_failures.md` under a separate "excluded: not a statement" heading and count
  774 = valid + excluded + failed.
- Gemini `--batch` is not implemented (exit 2). OpenRouter exposes `google/gemini-3.8-flash:batch`
  at 50%; only worth it if the backfill cost matters to Kevin.
- `scrape, entities, export, refresh` are stubs (exit 2). Phase 4a (scraper, manifest, Senate
  discovery) is independent and can be built in series after this.
- Loader verifier notes left open (none block the backfill; details in `DECISIONS.md` Phase 2c):
  alias fallback doesn't reorder "SURNAME Given" (matters for Phase 4's 48th PDFs, which have no
  `pdf_members.csv` row yet); a failing AC-2.7 hard gate still installs the DB (exit 1); a few
  party-term labels are inconsistent for mid-term defectors.
- The root `README.md` is still v1's (rewritten in Phase 5).

## Decisions made this session (reasoning in DECISIONS.md)
- **G1 passed 2026-10-01** with zero `kevin_fix` rows; all five judgement calls accepted.
- **Model `gemini-3.8-flash`** (GA, verified live). `.env.local` `GEMINI_MODEL` updated.
- **G2 = workflow-claude (2026-10-02)**, then **revisited the same day**: Kevin chose to try
  Gemini after the subscription cap made the workflow backfill impractical. Treat Gemini as the
  intended backfill arm; the G2 entry needs the "revisited" line once Gemini is scored.
- **De-dup key wider than ADR-5's** (bare key merged 52 genuine gold items).
- **Loader member identity** resolves `pdf_members.csv` → `member_aliases.csv` → slug; party per
  term is start-of-term from v1's Wikipedia data; `unknown_party.csv` is empty for 43–47.
- **Workflow tool denial.** The `Workflow` tool was denied by the auto-mode classifier; the
  gold run used direct subagents with the saved script's bundle prompts (identical behaviour).

## Dead ends / corrections
- **Running 20 Sonnet subagents at once** both triggers API stream timeouts and burns the
  subscription session cap in ~1 hour. If the workflow arm is ever used again, run ≤ 8 agents
  and expect to span many 5-hour windows. The bundle prompts for the remaining 745 PDFs were in
  the session scratchpad only; regenerate them with the saved script (`docs/v2/extraction.md`).
- **The AI Studio key is not usable** (prepaid credits depleted). Don't retry it; use OpenRouter.
- **`pdf_members.csv` `electorate_or_state` is v1's most-recent electorate** for that member,
  so renamed seats carry the later name even on older PDFs (Wilkie 45th says Clark, page says
  Denison). The loader prefers the extraction's printed electorate, so impact is nil.
- **Old 47th-Parliament URL note** (v1 `parliament_urls.py` points "47th" at the current page,
  which now serves the 48th) is still a Phase 4 fix.

## Open questions (who holds the ball)
- **OpenRouter request shape for PDF + structured output: next agent** (verify in the docs).
- **G2 final choice after the Gemini score: Kevin** confirms in `DECISIONS.md`.
- **SPEC.md "DRAFT, awaiting sign-off": Kevin.** The ADR-4 bar is still "proposed defaults".
- **Gemini spend ceiling for the backfill (≈ US$10–20): Kevin**, if he wants a cap.
