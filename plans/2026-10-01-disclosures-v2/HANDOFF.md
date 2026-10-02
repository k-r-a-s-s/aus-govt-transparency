# Handover — Disclosures v2 (updated 2026-10-02 night: Phase 2 complete; backfill + load done; next is Phase 3 or 4a)

Read first: `SPEC.md` (plan, ADRs, ACs, gates), `DECISIONS.md` (dated decisions, incl. G1/G2),
`docs/v2/README.md` (layout, commands), `docs/v2/extraction.md` (both extractor arms, both
transports), `docs/v2/loading.md` (loader), `data/overrides/README.md`, `eval/bakeoff.md`
(incl. "Backfill actuals"), `eval/extraction_failures.md`. This file only holds what those don't.

## Where we are
- **Phase 2 is done.** Phases 1, 2a, 2b, 2c (loader) and the backfill are built, verified and
  committed. `disclosures.db` (v1) sha unchanged.
- **Backfill complete (2026-10-02, cloud session):** `extractions/gemini-api/house/{43..47}/`
  holds 768 valid files (150/152/158/153/155), `validate` reports 0 invalid, 42,042 items.
  0 failures; the 6 non-statements are listed in `eval/extraction_failures.md`
  (768 + 6 + 0 = 774, AC-2.6). Console log: `eval/backfill-gemini.log` (three passes).
- **Load verified:** `python -m disclosures load --source gemini-api` → `disclosures_v2.db`
  (gitignored; rebuild it), 768 documents, 303 members, 763 member_terms, 42,042 items, exit 0.
  AC-2.7 hard queries 0 (informational early-dated count 4, listed in `eval/bakeoff.md`),
  AC-2.8 identical item ids across two loads, AC-2.9 0 terms without party, AC-2.10 passes.
- **Cost:** ≈ US$38 billed (estimate was 22). Gemini flex itself was on budget; the overrun is
  the Sonnet fallback, which 14% of files needed (20–25% of the scanned 43rd–45th). OpenRouter
  credit after the run: ≈ US$19 of 70.
- **Two transport fixes landed during the run** (`disclosures/openrouter.py`, 183 tests pass):
  `--ignore-providers SLUGS` (→ `provider.ignore`, on primary and fallback) and no
  `temperature` for `anthropic/*` models. Reason: OpenRouter lists `temperature` only on Sonnet
  5.5's Azure endpoints, so `require_parameters` pinned every fallback to Azure, which returned
  intermittent HTTP 400 `no_content_length_header`; ignoring Azure alone then left no endpoint
  (404). Use `--ignore-providers azure` on any future Sonnet-fallback run.
- **Branching note:** this work was pushed from a cloud session to `claude/festive-hypatia-qf43x5`
  with draft PR #1 against `v2-upgrade` (k-r-a-s-s/aus-govt-transparency). Merge it (or
  fast-forward `v2-upgrade`) before continuing on `v2-upgrade` locally.

## Single next action
Phase 2 is closed. Pick up `SPEC.md` step 5 (**Phase 3 — Entities**: normalise, generic list,
curated alias draft → **G3**, ASX snapshot + match, LLM long tail, `entities_report.md`) or step 6
(**Phase 4a — Scraper**, independent). Both are separate specs in `SPEC.md`; nothing in Phase 2
blocks them. Before starting, rebuild the DB:
```sh
.venv/bin/python -m disclosures load --source gemini-api
```
If any PDF ever needs re-extracting, the backfill command is idempotent (skips valid output;
`--force` to redo); add `--ignore-providers azure` to the HANDOFF-step-1 command:
```sh
.venv/bin/python -m disclosures extract --source gemini --provider openrouter \
    --model google/gemini-3.8-flash --provider-order google-ai-studio/flex \
    --fallback-model anthropic/claude-sonnet-5.5 --ignore-providers azure --workers 8 \
    $(.venv/bin/python -c "import csv;print(' '.join(r['pdf_path'] for r in csv.DictReader(open('eval/pdf_stats.csv')) if r['is_statement']=='1'))") \
    2>&1 | tee -a eval/backfill-gemini.log
```
(zsh: inline the `$(...)` as above or use `${=VAR}`; bash word-splits fine.)

## In-flight / deliberately out of scope
- `extractions/workflow-claude/` (23 files), `extractions/openrouter-gpt-6-luna/` and
  `extractions/openrouter-claude-sonnet-5.5/` (12 each) stay committed as bake-off evidence.
- `tests/test_load.py::test_unwritable_target_exits_2` fails when run as root (cloud container);
  it passes locally. Not a code defect.
- A `--reasoning-effort low` Gemini variant was scored (scratch output, not committed):
  F1 0.977 for ≈ 25% less (≈ US$16 backfill vs 22). Recorded in `eval/bakeoff.md`; not
  recommended unless budget forces it (the saving is ≈ US$6 for 1 F1 point).
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
- **Fallback cost (Kevin, optional).** 14% of files needed the Sonnet fallback and it took
  ~58% of the spend. If re-extraction is ever needed at scale, a cheaper fallback model for
  blocked chunks only is the lever; not pursued (G2 says Sonnet).
- **SPEC.md "DRAFT, awaiting sign-off": Kevin.** ADR-4 bar still "proposed defaults"; ADR-5's
  "any other finish reason fails" wording should get the fallback caveat when SPEC is signed.
- **Luna's date bug**: not pursued. If cost ever matters more than dates, a one-line prompt
  change ("ignore PROCESSED/received stamps") might fix it; untested.
