# Handover — Disclosures v2 (updated 2026-10-03: the Ralph loop stopped at G3; Phases 3–5 built up to the gates)

Read first: `SPEC.md` (plan, ADRs, ACs, gates), `DECISIONS.md` (dated decisions, incl. G1/G2),
`README.md` (v2 overview, every command), `docs/v2/README.md` (layout), `docs/v2/extraction.md`,
`docs/v2/loading.md`, `docs/v2/scrape.md`, `docs/v2/senate_source.md`, `data/overrides/README.md`,
`eval/entities_report.md`, `plans/2026-10-02-ralph-phases-3-5/PROGRESS.md` (one line per task).
This file only holds what those don't.

## Loop state (2026-10-03, branch `claude/ralph-proxmox`)
`status.py`: `STOP nothing-ready`, 35 done, 1 blocked (T1.6), 1 waiting on Kevin (G3),
6 todo, all downstream of G3: T2.9 → V2, and T2.9 + T5.5 → T5.6 → V5 → G4.
OpenRouter credit left: **US$12.40 of 70** (US$57.60 used). Nothing left in the plan is paid
(T2.9, T5.6, V2, V5 budget US$0).

## Waiting on Kevin
### 1. G3: entity review (unblocks everything else)
1. Open `eval/entities_g3_review.csv` (114 rows: the top 50 aliases, 24 flagged curated rows and
   the medium-confidence LLM aliases in entities with >= 5 items, over House 43rd–48th + Senate 48th).
2. Per row, put `y` in `kevin_ok`, or write the correction in `kevin_fix`
   (`canonical_name=…;entity_type=…;asx_code=…`, or `own` / `generic`). Full instructions:
   `eval/entities_report.md`, "How to review G3".
3. Approve: set the G3 block in `plans/2026-10-02-ralph-phases-3-5/IMPLEMENTATION_PLAN.md` to
   `- status: done <date>` and commit it with the CSV (or tell a session "G3 approved").
4. Restart the loop (`scripts/ralph/loop.sh 60`). It runs T2.9 (apply fixes), V2, T5.6 (final
   rebuild + `eval/final_acceptance.md`), V5, then stops at G4.

### 2. T1.6: nevillep_43p spouse holdings (decision only)
The p5 s9 fund is joint, but the 19 p8 holdings are filed under self only, and a G2 re-extraction
(US$0.05) gave the same result. Decide: accept self-only, or allow a hand override (e.g. a
`data/overrides` owner rule duplicating the 19 p8 items for spouse). Write the answer into the T1.6
block and set it back to `todo` (override allowed) or `dropped: accepted self-only`.

### 3. G4: publish (after V5)
Merge to main, enable Pages (`.github/workflows/pages.yml` publishes `site/`), upload `exports/kaggle/`
to Kaggle, announce. First choose the licence and Kaggle id:
`python -m disclosures export --license NAME --kaggle-id USER/SLUG` (the current values are
placeholders; DECISIONS 2026-10-03 T5.1).

## Where we are
- **M1 attachment fix done:** rule C12 / prompt v1 (gold F1 0.984), 7 attachment files re-extracted (+210 items).
- **Phase 3 entities built to G3:** curated aliases (heads 1–200), ASX snapshot, cached LLM long
  tail; 11,544 entities over the full DB, AC-3.3 0, AC-3.4 pass.
- **Phase 4 done and cold-verified (V3):** `pdfs/manifest.csv` (sha + source_url), `scrape`
  (House 48th, 151 PDFs, US$4.03 to extract), Senate 48th via its JSON API (76 senators, 1,980
  items, free), `refresh`. The DB has 919 House docs + 76 Senate, 50,936 items. Senate archives
  before the 48th are scanned tabled volumes: documented in T3.9's notes, not built (≈ US$18–25).
- **Phase 5 prep done:** `export` (`exports/disclosures_v2.csv`, 50,936 rows, 33 cols; `exports/kaggle/`),
  `site/` (index + Datasette Lite DB) with the Pages workflow (not enabled), README rewritten,
  v1 code removed (`git show 66377df:src/...` to read it), and the fresh-venv install passes (T5.5).
- 322 tests pass (1 skipped: the root-only chmod test). v1 `disclosures.db` sha unchanged.
- **No PR yet:** this branch is pushed to `origin/claude/ralph-proxmox`. A PR against
  `v2-upgrade` is opened at this stop (see below if it failed).

## In-flight / deliberately out of scope
- `extractions/workflow-claude/` (23 files), `extractions/openrouter-gpt-6-luna/` and
  `extractions/openrouter-claude-sonnet-5.5/` (12 each) stay committed as bake-off evidence.
- A `--reasoning-effort low` Gemini variant was scored (scratch output, not committed):
  F1 0.977 for ≈ 25% less (≈ US$16 backfill vs 22). Recorded in `eval/bakeoff.md`; not
  recommended unless budget forces it (the saving is ≈ US$6 for 1 F1 point).
- Gemini `--batch` is still not implemented (exit 2). OpenRouter's `:batch` is a separate async
  API; `provider.order google-ai-studio/flex` already gives the 50% price synchronously.
- Loader verifier notes left open (none block the backfill): alias fallback doesn't reorder
  "SURNAME Given"; a failing AC-2.7 hard gate still installs the DB (exit 1); some party-term
  labels are inconsistent for mid-term defectors.

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
- **Sandakan-trek sponsors (Kevin).** In `morrisons_43p` / `oakeshottr_43p`, v2 reads the trek's
  sponsor list (BHP Billiton, Interlink Roads, …) as a covering letter with no items, because the
  member paid their own way (C2). v1 logged the sponsors as travel gifts. Itemise them or not?
  (SPEC-DELTA D1.)
- **Fallback cost (Kevin, optional).** 14% of files needed the Sonnet fallback and it took
  ~58% of the spend. If re-extraction is ever needed at scale, a cheaper fallback model for
  blocked chunks only is the lever; not pursued (G2 says Sonnet).
- **SPEC.md "DRAFT, awaiting sign-off": Kevin.** ADR-4 bar still "proposed defaults"; ADR-5's
  "any other finish reason fails" wording should get the fallback caveat when SPEC is signed.
- **Luna's date bug**: not pursued. If cost ever matters more than dates, a one-line prompt
  change ("ignore PROCESSED/received stamps") might fix it; untested.
