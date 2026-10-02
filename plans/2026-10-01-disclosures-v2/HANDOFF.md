# Handover — Disclosures v2 (updated 2026-10-03: T5.6 final rebuild and AC sweep done; V5 then G4 remain)

Read first: `SPEC.md` (plan, ADRs, ACs, gates), `DECISIONS.md` (dated decisions, incl. G1/G2/G3),
`README.md` (v2 overview, every command), `docs/v2/README.md` (layout), `docs/v2/extraction.md`,
`docs/v2/loading.md`, `docs/v2/scrape.md`, `docs/v2/senate_source.md`, `data/overrides/README.md`,
`eval/entities_report.md`, `eval/final_acceptance.md` (every SPEC §3 AC, with evidence),
`plans/2026-10-02-ralph-phases-3-5/PROGRESS.md` (one line per task).
This file only holds what those don't.

## Loop state (2026-10-03, branch `claude/ralph-proxmox`, PR #2 → `v2-upgrade`)
G3 approved (0 fixes), T1.6 dropped (accept self-only), T2.9 and V2 done. T5.6 rebuilt everything
from committed inputs and ran every SPEC §3 AC: **all pass** (`eval/final_acceptance.md`). Left:
V5 (cold verification of the export and site, US$0), then G4 (Kevin).
OpenRouter credit left: **US$12.40 of 70** (US$57.60 used). Nothing left in the plan is paid.

## Waiting on Kevin
### 1. G4: publish (after V5)
1. Choose the licence and Kaggle id, then regenerate: `.venv/bin/python -m disclosures export
   --site site --license NAME --kaggle-id USER/SLUG` (current values are placeholders; DECISIONS
   2026-10-03 T5.1). Commit `site/` and `exports/kaggle/README.md` + `dataset-metadata.json`.
2. Merge PR #2 into `v2-upgrade`, then `v2-upgrade` into `main`.
3. Enable GitHub Pages with source "GitHub Actions" (`.github/workflows/pages.yml` publishes `site/`);
   check the Datasette Lite link on the page loads the DB.
4. Upload `exports/kaggle/` (`kaggle datasets create -p exports/kaggle`), then announce.
5. Record G4 in DECISIONS.md and sign off SPEC.md (`Status:` line), see open questions.

## Open questions for Kevin (none blocks an AC)
- **Sandakan-trek sponsors (SPEC-DELTA D1).** In `morrisons_43p` / `oakeshottr_43p`, v2 reads the
  trek's sponsor list (BHP Billiton, Interlink Roads, …) as a covering letter with no items,
  because the member paid their own way (C2). v1 logged the sponsors as travel gifts. Itemise
  them or not? Left as is.
- **Untyped singletons (SPEC-DELTA D2).** 7,037 of 11,542 entities are one-off names with
  `entity_type` empty (documented in the Kaggle README and `docs/v2/entities.md`). Typing them
  through the LLM is ≈ 10k names; not done. Accept, or fund a typing pass later?
- **Reused ASX tickers.** The ASX stage matches against today's snapshot; V2 fixed the known
  cases with curated rows, but other old tickers could still map to the current holder
  (Known limitations in `docs/v2/entities.md`).

## Where we are
- **M1 attachment fix done:** rule C12 / prompt v1 (gold F1 0.984), 7 attachment files re-extracted (+210 items).
- **Phase 3 entities done and cold-verified (V2):** curated aliases (heads 1–200), ASX snapshot,
  cached LLM long tail; G3 approved with 0 fixes; V2 added 9 curated rows for reused tickers.
  11,542 entities over the full DB, AC-3.3 0, AC-3.4 pass.
- **Phase 4 done and cold-verified (V3):** `pdfs/manifest.csv` (sha + source_url), `scrape`
  (House 48th, 151 PDFs, US$4.03 to extract), Senate 48th via its JSON API (76 senators, 1,980
  items, free), `refresh`. The DB has 919 House docs + 76 Senate, 50,936 items. Senate archives
  before the 48th are scanned tabled volumes: documented in T3.9's notes, not built (≈ US$18–25).
- **Phase 5 prep done:** `export` (`exports/disclosures_v2.csv`, 50,936 rows, 33 cols; `exports/kaggle/`),
  `site/` (index + Datasette Lite DB) with the Pages workflow (not enabled), README rewritten,
  v1 code removed (`git show 66377df:src/...` to read it), and the fresh-venv install passes (T5.5).
- **T5.6 final sweep:** rebuilt from committed inputs (deterministic: item-id hash `88fb48c0…`
  before and after), `site/` and `exports/` regenerated, every AC-0 to AC-5 passes
  (`eval/final_acceptance.md`).
- 322 tests pass (1 skipped). v1 `disclosures.db` sha unchanged.
- **PR #2** (`claude/ralph-proxmox` → `v2-upgrade`) is open; nothing pushed to `main`/`v2-upgrade`.

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

## Other open questions (who holds the ball)
- **Fallback cost (Kevin, optional).** 14% of files needed the Sonnet fallback and it took
  ~58% of the spend. If re-extraction is ever needed at scale, a cheaper fallback model for
  blocked chunks only is the lever; not pursued (G2 says Sonnet).
- **SPEC.md "DRAFT, awaiting sign-off": Kevin.** ADR-4 bar still "proposed defaults"; ADR-5's
  "any other finish reason fails" wording should get the fallback caveat when SPEC is signed.
- **Luna's date bug**: not pursued. If cost ever matters more than dates, a one-line prompt
  change ("ignore PROCESSED/received stamps") might fix it; untested.
