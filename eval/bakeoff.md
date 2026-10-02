# Extractor bake-off — gold set (12 PDFs, 790 gold items, 289 pages)

Status: **G2 confirmed 2026-10-02 (Kevin): gemini-api = Gemini 3.8 Flash on OpenRouter flex + Claude Sonnet 5.5 fallback.** Four arms scored the same day; **backfill complete 2026-10-02 (768/768 valid, see "Backfill actuals" below and `eval/extraction_failures.md`).**
Date: 2026-10-02 · Scorer: `python -m disclosures score` (ADR-4; token_set_ratio ≥ 85, section-strict
matching, micro-averaged). Gold reviewed by Kevin at G1 (2026-10-01).

Earlier status (same day, superseded): G2 was first decided as workflow-claude because the Gemini
arm could not run (AI Studio credits depleted). The workflow backfill then hit the Claude
subscription session cap after 11 of 745 PDFs, Kevin asked for a multi-provider comparison via
OpenRouter, and the three OpenRouter arms below were run. Provider selection and the probe
numbers are in `plans/2026-10-01-disclosures-v2/DECISIONS.md` (2026-10-02 entries).

## Results

| Metric | ADR-4 bar | v1 (`disclosures.db`) | workflow-claude (Sonnet, Claude Code) | gemini-api (`google/gemini-3.8-flash` flex + Sonnet 5.5 fallback) | `openai/gpt-6-luna` | `anthropic/claude-sonnet-5.5` |
|---|---|---|---|---|---|---|
| Items predicted (gold 790) | | 577 | 791 | 791 | 783 | 784 |
| Matched (section-strict) | | n/a (v1 has no sections) | 770 | 780 | 757 | 769 |
| Precision | ≥ 0.90 | n/a | **0.973** ✅ | **0.986** ✅ | **0.967** ✅ | **0.981** ✅ |
| Recall | ≥ 0.90 | n/a | **0.975** ✅ | **0.987** ✅ | **0.958** ✅ | **0.973** ✅ |
| F1 | | n/a | 0.974 | **0.987** | 0.962 | 0.977 |
| Section-ignored precision | | 0.856 | 0.977 | 0.989 | 0.986 | 0.999 |
| Section-ignored recall | > v1 (0.625) | 0.625 | **0.978** ✅ | **0.990** ✅ | **0.977** ✅ | **0.991** ✅ |
| Section-ignored F1 | | 0.723 | 0.978 | 0.989 | 0.982 | 0.995 |
| Owner accuracy (matched) | ≥ 0.95 | n/a | **0.995** ✅ | **1.000** ✅ | **0.995** ✅ | **0.997** ✅ |
| Page accuracy (matched) | ≥ 0.90 | n/a | **0.991** ✅ | **1.000** ✅ | **0.992** ✅ | **1.000** ✅ |
| change_type accuracy | | n/a | 0.981 | 0.997 | 0.992 | 0.995 |
| is_alteration accuracy | | n/a | 0.991 | 1.000 | 0.997 | 1.000 |
| lodged_date accuracy | | n/a | 0.988 | 0.968 | 0.765 | 0.999 |
| **ADR-4 bar** | | fails (recall) | **PASS** | **PASS** | **PASS** | **PASS** |
| Gold-run cost (12 PDFs, 289 pp) | | — | within subscription; see below | US$0.48 (reported by OpenRouter) | US$0.17 | US$2.38 |
| Backfill estimate (768 PDFs, 13,183 pp, scaled by pages) | | — | ≈ 60+ five-hour subscription windows | ≈ US$22 | ≈ US$7.5 | ≈ US$108 |

Full reports: `eval/workflow-claude.json`, `eval/gemini-api.json`, `eval/openrouter-gpt-6-luna.json`,
`eval/openrouter-claude-sonnet-5.5.json`, `eval/v1_baseline.json`.

### Per-PDF recall (section-strict / section-ignored)

| PDF | gold | workflow-claude | gemini-api (+fallback) | gpt-6-luna | claude-sonnet-5.5 |
|---|---|---|---|---|---|
| butlerm_44p | 32 | 0.938 / 0.969 | 0.969 / 1.000 | 0.969 / 1.000 | 0.969 / 1.000 |
| gosling_47p | 39 | 0.974 / 0.974 | 0.949 / 0.949 | 0.949 / 0.949 | 1.000 / 1.000 |
| husice_45p | 26 | 0.962 / 0.962 | 0.962 / 0.962 | 1.000 / 1.000 | 0.962 / 0.962 |
| kingm_47p | 207 | 0.952 / 0.952 | 1.000 / 1.000 | 0.937 / 0.937 | 1.000 / 1.000 |
| morrison_47p | 97 | 0.979 / 0.979 | 1.000 / 1.000 (pp 21–29 via fallback) | 1.000 / 1.000 | 1.000 / 1.000 |
| morton_46p | 62 | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 | 0.935 / 0.935 |
| plibersekt_43p | 46 | 0.978 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 | 0.978 / 1.000 |
| prenticej_45p | 72 | 1.000 / 1.000 | 0.931 / 0.931 | 1.000 / 1.000 | 1.000 / 1.000 |
| royw_43p | 13 | 0.769 / 0.846 | 0.923 / 1.000 | 0.923 / 1.000 | 1.000 / 1.000 |
| thistlethwaitem_44p | 71 | 1.000 / 1.000 | 1.000 / 1.000 | 0.789 / 0.972 | 0.831 / 1.000 |
| tink_47p | 77 | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 | 1.000 / 1.000 |
| wilkie_46p | 48 | 1.000 / 1.000 | 1.000 / 1.000 | 0.979 / 0.979 | 0.958 / 0.958 |

Worst misses (from the scorer):
- **gemini-api:** `husice_45p` p4 s6 "AMEX" (garbled multi-bank credit-card cell, same miss as
  every other arm); `gosling_47p` p9 s12 "AALD" and p8 "Chief Ministers Marquee" (description
  wording below the 85 ratio); `prenticej_45p` p25 s11 five "Parliamentary hosts (delegation to
  Taiwan)" rows (gold splits them per host, Gemini merged them; ratio 57). No handwriting miss:
  royw (fully handwritten) is 13/13 section-ignored, where workflow-claude got 11/13.
- **gpt-6-luna:** `thistlethwaitem_44p` p6 s13 clubs (ratio 81–84, near misses) and 15 items
  mis-sectioned there; `kingm_47p` p44 s6 banks and p50 s3 real estate dropped; plus the C4 date
  convention failure described below.
- **claude-sonnet-5.5:** `morton_46p` p4 s9 PSS/GESB and s11 VIRGIN ×2, `wilkie_46p` s12 Virgin
  Australia ×2, `thistlethwaitem_44p` s13 (12 items mis-sectioned, 1.000 section-ignored).

### Run details

- **workflow-claude** (unchanged from the first bake-off, 2026-10-02): 4 bundles
  (91 / 72 / 110 / 16 pages), model `sonnet`, one agent per bundle, ≈ 863k agent tokens, ≈ 31 min
  wall-clock; all 12 files valid first time. Backfill abandoned after a 19-agent wave hit the
  subscription's 5-hour session cap at 11 of 745 PDFs (see `DECISIONS.md`).
- **OpenRouter arms** (2026-10-02): `python -m disclosures extract --source gemini --provider
  openrouter --model <id> --workers 4 <12 gold PDFs>`; 18 calls each (20-page chunks; kingm = 5
  chunks); every file validated first time; costs are OpenRouter's `usage.cost`.
  - **gemini-api:** `google/gemini-3.8-flash` pinned to `google-ai-studio/flex` ($0.38 / $1.88 per
    MTok, half price, slower). 186k input / 155k output tokens for 11 PDFs (output is mostly
    thinking tokens). **morrison_47p failed with `finish_reason ERROR (RECITATION)` on pages 21–29**,
    and page 23 alone (a typed travel-alteration notice) is still refused as a 1-page chunk, so
    re-splitting cannot clear it. It was re-run with `--fallback-model anthropic/claude-sonnet-5.5`:
    the blocked chunk went to Sonnet, the file's `model` is
    `google/gemini-3.8-flash+anthropic/claude-sonnet-5.5` and `extraction_notes` records it. Cost
    US$0.36 (11 PDFs) + 0.01 (royw smoke) + 0.10 (morrison with fallback) = US$0.48; a further
    US$0.13 was spent diagnosing the block (5-page and 1-page retries) and is not counted.
    Without the fallback the arm scores recall 0.865 (one PDF missing) and fails the bar.
  - **gpt-6-luna:** 880k input tokens (≈ 3,000 per page, OpenAI renders PDF pages large) but at
    $0.10 / $0.50 per MTok; US$0.158 + 0.007 (smoke). `temperature` omitted (rejected by GPT-6).
    **Systematic date error:** on typed 47th-Parliament files it reports the "received" stamp
    date instead of the signed date required by convention C4 (tink 25→26 Aug 2022, gosling
    22→23 Aug 2022, plibersek 18→22 Oct 2010; 164 of 757 matched items), hence lodged_date 0.765.
  - **claude-sonnet-5.5:** 557k input tokens (≈ 1,900 per page); US$2.304 + 0.074 (smoke). The
    most precise section-ignored arm (0.999) and the best lodged_date (0.999); every miss is a
    mis-sectioning or a split/merge difference, none a misread.
- **`--reasoning-effort low` variant (gemini-api, same fallback; scratch run, not committed):**
  F1 0.977 (P 0.980, R 0.975), section-ignored recall 0.984, owner 1.000, page 1.000,
  lodged_date 0.997; 215k input / 118k output tokens, US$0.356 for all 12 PDFs (≈ US$16 for
  the backfill, vs ≈ US$22 at the default effort). It clears the bar and reads dates slightly
  better, but loses 1 F1 point (morton 0.935, plibersek 0.913 section-strict, tink 74/77
  items). Not recommended unless the budget forces it: the saving is ≈ US$6.
- Early-dated items check (AC-2.7, informational), full gemini-api load (768 files, 42,042 items):
  **4**, all in `grayg_43p` (Gary Gray, 43rd), all plausibly genuine dates on a first statement:
  p8 s11 "Sustainable World Technologies" 2008-12-04 (high); p9 s12 "Competitive Foods Ltd"
  2009-05-25 (high); p10 s12 "Australian Capital Equity" 2009-10-13 (high); p11 s14 "The West
  Australian" 2009-10-13 (medium). (The earlier count of 2 was on 23 workflow-claude files.)

## Decision (ADR-5 rule)

ADR-5: among arms that clear the ADR-4 bar, choose the higher F1; if the F1 gap is < 2 points,
choose `gemini-api` (unattended, reproducible, cheap re-runs).

- All four arms clear the bar. Highest F1 is **gemini-api at 0.987** (Sonnet 5.5 0.977,
  workflow-claude 0.974, Luna 0.962), so gemini-api wins outright; the tie-break is not needed.
- The gemini-api figure includes the Sonnet 5.5 fallback on 1 of its 18 chunks. The fallback is
  part of the configuration being chosen: Gemini's RECITATION filter will block some backfill
  PDFs and the fallback is the only way to keep them (≈ US$0.10–0.20 per blocked chunk). In the
  backfill it blocked 14% of files (see "Backfill actuals"), not the few per cent expected.
- Luna is 3× cheaper but breaks the C4 date convention and loses items on dense pages; Sonnet
  5.5 is the best on dates and sections but ≈ 5× the cost of Gemini for 1 F1 point less.

**Chosen arm: gemini-api** = `google/gemini-3.8-flash` on `google-ai-studio/flex` with
`--fallback-model anthropic/claude-sonnet-5.5`, default reasoning effort (G2 confirmed by Kevin
2026-10-02, recorded in `plans/2026-10-01-disclosures-v2/DECISIONS.md`). Budget: ≈ US$22 for
the backfill; OpenRouter credit topped up to ≈ US$27.3 the same day.

## Backfill actuals (2026-10-02, cloud session)

- 768 of 768 statement PDFs extracted and valid; 0 failures (`eval/extraction_failures.md`).
  42,042 items; 1,035 OpenRouter calls; 11.1M input / 9.2M output tokens (output includes
  Gemini thinking and the Sonnet fallback).
- **Cost: ≈ US$38 as billed by OpenRouter** (completed passes reported US$27.42 + US$8.71; an
  aborted pass and probes ≈ US$2), against the ≈ US$22 estimate. The 365 PDFs that stayed on
  Gemini flex cost US$10.96 (US$0.030 each, exactly the flex price for their tokens), so the
  overrun is entirely the fallback: 108 files (14%) had at least one chunk refused by Gemini
  (`RECITATION`), and a Sonnet chunk costs ≈ 5× a Gemini chunk (fallback files averaged
  US$0.163). The block rate is 20–25% on the scanned 43rd–45th parliaments and ≈ 2% on the
  typed 46th–47th; the gold set (1 of 12 PDFs) under-sampled it.
- Transport fixes found during the run (`docs/v2/extraction.md`): `--ignore-providers`, and no
  `temperature` for `anthropic/*` (OpenRouter lists `temperature` only on Sonnet's Azure
  endpoints, so `require_parameters` had pinned every fallback to Azure, which intermittently
  returned HTTP 400 `no_content_length_header`).
- AC-2.7–2.10 on the load: documents 768 = valid files; the three hard queries 0; AC-2.8 item-id
  hash identical across two loads (`f69d40da…`, 42,042 ids); AC-2.9 0 terms without party;
  AC-2.10 duplicate-MP cases resolve to one `member_id` each (`tests/test_load.py`).

## Prompt v1 (C12) regression (2026-10-02)

Gold set re-extracted with prompt v1 (rule C12 + checklist item 7, attachments) using the G2
config, `--source-id gemini-api-promptv1` into `.ralph/scratch/gold-promptv1` (scratch, not
committed). Scores: `eval/gemini-api-promptv1.json`.

| Metric | ADR-4 bar | gemini-api, prompt v0 | gemini-api, prompt v1 |
|---|---|---|---|
| Items predicted (gold 790) | | 791 | 791 |
| Matched (section-strict) | | 780 | 778 |
| Precision | ≥ 0.90 | 0.986 | **0.984** ✅ |
| Recall | ≥ 0.90 | 0.987 | **0.985** ✅ |
| F1 | (T1.4: ≥ 0.980) | 0.987 | **0.984** ✅ |
| Section-ignored recall | > v1 (0.625) | 0.990 | **0.987** ✅ |
| Owner accuracy | ≥ 0.95 | 1.000 | **1.000** ✅ |
| Page accuracy | ≥ 0.90 | 1.000 | **1.000** ✅ |
| change_type / is_alteration / lodged_date | | 0.997 / 1.000 / 0.968 | 0.997 / 1.000 / 0.968 |
| **ADR-4 bar** | | PASS | **PASS** |
| Gold-run cost | | US$0.48 | US$0.47 (1 Sonnet fallback chunk: morrison_47p p21–29) |

- Only prenticej_45p changed (recall 0.931 → 0.903). On p29 (section 11, gifts), v1 named
  the gift brands ("H.jin", "Chunmarc") as `entity_name` instead of the giver, "Minister
  for Health and Welfare, South Korea". That's run-to-run variance in naming, not C12. The
  other 11 PDFs have the same per-PDF counts and matches as v0.
- plibersekt_43p p8 (the gold attachment precedent: section 13 "see attached"): all three
  have the same 13 section-13 self items, ALP NSW Branch through Women's International League
  for Peace and Freedom. C12 doesn't break a list that was already itemised.
