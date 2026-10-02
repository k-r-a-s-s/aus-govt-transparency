# Handover — Disclosures v2 (updated 2026-10-02: Phase 2 merged and re-verified locally; next is the Ralph loop in `plans/2026-10-02-ralph-phases-3-5/`)

Read first: `SPEC.md` (plan, ADRs, ACs, gates), `DECISIONS.md` (dated decisions, incl. G1/G2),
`docs/v2/README.md` (layout, commands), `docs/v2/extraction.md` (both extractor arms, both
transports), `docs/v2/loading.md` (loader), `data/overrides/README.md`, `eval/bakeoff.md`
(incl. "Backfill actuals"), `eval/extraction_failures.md`. This file only holds what those don't.

## Waiting on Kevin: G3 (entity review), since 2026-10-02 (T2.8)
Phase 3 entities are built up to the gate (AC-3.3 0, AC-3.4 pass, top 20 checked by hand). The
loop stops at G3 once nothing else is ready. What to do:
1. Open `eval/entities_g3_review.csv`: **101 rows** (the top 50 aliases, 24 flagged curated
   rows and 31 medium-confidence LLM aliases in entities with >= 5 items; 10,381 items between
   them).
2. For each row, put `y` in `kevin_ok`, or write the correction in `kevin_fix`
   (`canonical_name=…;entity_type=…;asx_code=…`, or `own` / `generic`). Full instructions:
   `eval/entities_report.md`, "How to review G3".
3. Approve: set the G3 block in `plans/2026-10-02-ralph-phases-3-5/IMPLEMENTATION_PLAN.md` to
   `- status: done <date>` and commit it with the CSV, or tell a cloud session "G3 approved".
   T2.9 then applies the fixes and does the final entity load.

Also waiting: T1.6 (`blocked (kevin)`: nevillep_43p spouse-owned holdings; see its block).

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
- **Merged and re-verified locally (2026-10-02).** PR #1 (`claude/festive-hypatia-qf43x5`) was
  fast-forwarded into `v2-upgrade` (`91a30fd`). Locally: 184 tests pass (including the root-only
  one), `validate` 768/768, load reproduces 768/303/763/42,042, AC-2.7 hard queries 0, and the
  AC-2.8 hash is `f69d40da…` (the cloud computed it as sha1 of the newline-joined ids with no
  trailing newline; `| shasum` adds one and gives `ba764fdc…` for the same ids).
- **Review finding: attachments aren't itemised consistently.** Example: `odowdk45p` notes an
  "Attachment 'A'" of SMSF holdings and records none of its 22 holdings. Rule C12 and a targeted
  re-extraction are M1 of the new plan (`plans/2026-10-02-ralph-phases-3-5/SPEC-DELTA.md` D1).
  Coverage otherwise checks out against v1: v2 has 44% more items, no empty documents, no empty
  20-page chunks, and only 1.7% of v1's named entities lack a v2 match (mostly v1 OCR noise).
- **Minor:** Sonnet fallback chunks (108 files) ran at the provider's default temperature, since
  `temperature` is omitted for `anthropic/*` (see the transport fixes above). They're less
  reproducible than the temperature-0 bake-off. Not acted on.

## Single next action
**Run the Ralph loop:** `plans/2026-10-02-ralph-phases-3-5/RUNNING.md`. Locally that's
`scripts/ralph/loop.sh 60`; in a cloud session it's the `/goal` line in RUNNING.md. It works
`IMPLEMENTATION_PLAN.md` one task per iteration:
- M1: the attachment fix.
- M2: Phase 3 entities, up to G3.
- M3: Phase 4 (manifest, House 48th, Senate 48th via its JSON API, refresh).
- M5: Phase 5 publish prep.

It stops at G3/G4 or on a block, and rewrites this section when it does. Rebuild the DB first
if it's missing: `.venv/bin/python -m disclosures load --source gemini-api`. The G2 extract
command (with `--ignore-providers azure`) and its batch rules are in
`plans/2026-10-02-ralph-phases-3-5/AGENTS.md`.

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
