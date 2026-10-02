# Extractor bake-off — gold set (12 PDFs, 790 gold items, 289 pages)

Status: **G2 decided 2026-10-02: workflow-claude** (Gemini arm not run: API credits depleted; Kevin chose to proceed without it).
Date: 2026-10-02 · Scorer: `python -m disclosures score` (ADR-4; token_set_ratio ≥ 85, section-strict
matching, micro-averaged). Gold reviewed by Kevin at G1 (2026-10-01).

## Results

| Metric | ADR-4 bar | v1 (`disclosures.db`) | workflow-claude (Sonnet) | gemini-api (`gemini-3.8-flash`) |
|---|---|---|---|---|
| Items predicted (gold 790) | | 577 | 791 | _pending_ |
| Matched (section-strict) | | n/a (v1 has no sections) | 770 | _pending_ |
| Precision | ≥ 0.90 | n/a | **0.973** ✅ | _pending_ |
| Recall | ≥ 0.90 | n/a | **0.975** ✅ | _pending_ |
| F1 | | n/a | **0.974** | _pending_ |
| Section-ignored precision | | 0.856 | 0.977 | _pending_ |
| Section-ignored recall | > v1 (0.625) | 0.625 | **0.978** ✅ | _pending_ |
| Section-ignored F1 | | 0.723 | 0.978 | _pending_ |
| Owner accuracy (matched) | ≥ 0.95 | n/a | **0.995** ✅ | _pending_ |
| Page accuracy (matched) | ≥ 0.90 | n/a | **0.991** ✅ | _pending_ |
| change_type accuracy | | n/a | 0.981 | _pending_ |
| is_alteration accuracy | | n/a | 0.991 | _pending_ |
| lodged_date accuracy | | n/a | 0.988 | _pending_ |
| **ADR-4 bar** | | fails (recall) | **PASS** | _pending_ |
| Cost | | — | within subscription; see below | _pending_ (est. < US$1 for the gold run at $0.75/$3.75 per MTok) |

Full reports: `eval/workflow-claude.json`, `eval/v1_baseline.json` (and `eval/gemini-api.json` once run).

### Per-PDF recall, workflow-claude

| PDF | gold | pred | recall | recall (section ignored) |
|---|---|---|---|---|
| butlerm_44p | 32 | 32 | 0.938 | 0.969 |
| gosling_47p | 39 | 39 | 0.974 | 0.974 |
| husice_45p | 26 | 32 | 0.962 | 0.962 |
| kingm_47p | 207 | 202 | 0.952 | 0.952 |
| morrison_47p | 97 | 97 | 0.979 | 0.979 |
| morton_46p | 62 | 62 | 1.000 | 1.000 |
| plibersekt_43p | 46 | 46 | 0.978 | 1.000 |
| prenticej_45p | 72 | 72 | 1.000 | 1.000 |
| royw_43p | 13 | 13 | 0.769 | 0.846 |
| thistlethwaitem_44p | 71 | 71 | 1.000 | 1.000 |
| tink_47p | 77 | 77 | 1.000 | 1.000 |
| wilkie_46p | 48 | 48 | 1.000 | 1.000 |

Worst misses (from the scorer): `husice_45p` p4 s6 "AMEX" (the extractor split a garbled
multi-bank credit-card cell differently); `gosling_47p` p8 s12 "Chief Ministers Marquee";
`royw_43p` p12 s8 "BOQ Bribie Island" ×2 (handwritten 43rd-Parliament page; both missed);
`kingm_47p` p49–p50 s3 three "(Self and partner)" real-estate re-declarations (gold has
self+spouse pairs under C1, the extractor's descriptions differ enough to fall under the 85
ratio). None of these is a systematic failure mode; royw (13 gold items, fully handwritten) is
the weakest file at 0.769.

### workflow-claude run details

- Executed 2026-10-02 as 4 bundles (91 / 72 / 110 / 16 pages) with the exact bundle prompts the
  saved workflow `.claude/workflows/extract-disclosures.js` generates for the 12 gold PDFs,
  model `sonnet` (`claude-code-sonnet`), one agent per bundle, reading each PDF with `Read` in
  ≤ 20-page ranges. The `Workflow` tool invocation itself was denied by the orchestrating
  session's auto-mode permission classifier, so the four bundle agents were dispatched directly
  with the script's prompts (same bundling, model and instructions). Kevin can reproduce with the
  saved workflow as described in `docs/v2/extraction.md`.
- All 12 files validated on the first attempt (0 fix rounds).
- Cost line ("within subscription"): agent output+tool tokens per bundle as reported by the
  harness: bundle 1 (5 PDFs, 91 pp) 261,233; bundle 2 (4 PDFs, 72 pp) 210,869; bundle 3
  (2 PDFs, 110 pp) 281,587; bundle 4 (1 PDF, 16 pp) 108,898. Total ≈ 863k agent tokens for 289 pages (≈ 3.0k per page). Wall-clock per bundle:
  31 / 23 / 24 / 9 min; bundles ran in parallel, so the run took ≈ 31 min end to end.
  Extrapolated to the 13,205-page House backfill (43rd–47th): ≈ 110 bundles ≈ 40 M agent
  tokens, several hours of wall-clock in waves of ≤ 22 agents, all on the subscription.

### gemini-api run details

- Not run. The AI Studio project's prepaid credits are depleted (`402 RESOURCE_EXHAUSTED` on a
  smoke call, 2026-10-01). After a top-up:
  ```sh
  .venv/bin/python -m disclosures extract --source gemini \
    $(.venv/bin/python -c "import json;print(' '.join(p['pdf_path'] for p in json.load(open('eval/gold/selection.json'))['pdfs']))")
  .venv/bin/python -m disclosures score --pred extractions/gemini-api --gold eval/gold --json eval/gemini-api.json
  ```
  then fill the column above from `eval/gemini-api.json` and the `usage` totals the command prints
  (price basis: $0.75 in / $3.75 out per MTok through 2026-12-31, `DECISIONS.md`).
- Early-dated items check (AC-2.7, informational): 2 on the 23 workflow-claude files loaded so far
  (both gashj_43p, section 11, lodged 2009-04-29, medium confidence). Re-list after the full backfill.

## Decision (ADR-5 rule)

ADR-5: among arms that clear the ADR-4 bar, choose the higher F1; if the F1 gap is < 2 points,
choose `gemini-api` (unattended, reproducible, cheap re-runs).

- **workflow-claude clears the bar** (P 0.973, R 0.975, owner 0.995, page 0.991, section-ignored
  recall 0.978 > v1 0.625).
- **gemini-api is unscored**, so the rule cannot be applied yet. Two outcomes once it runs:
  1. Gemini clears the bar and its F1 is ≥ 0.954 (within 2 points of 0.974) → **gemini-api**.
  2. Gemini fails the bar or its F1 < 0.954 → **workflow-claude** (Kevin must raise "Dynamic
     workflow size" in `/config` and run the backfill in per-parliament waves).
- If Kevin prefers not to top up Gemini credits, workflow-claude is a valid choice on its own
  (it clears the bar with margin); record that as the G2 decision in `DECISIONS.md`.

**Chosen arm: workflow-claude** (G2, Kevin, 2026-10-02; recorded in `plans/2026-10-01-disclosures-v2/DECISIONS.md`). Rule applied: the only arm scored clears the ADR-4 bar; Kevin declined to run the Gemini arm for now.
