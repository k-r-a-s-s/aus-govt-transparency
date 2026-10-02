# Implementation plan: attachment fix, Phase 3 (entities), Phase 4 (scraper/48th/Senate/refresh), Phase 5 (prepare publish)

Tasks are in **priority order**. `python3 scripts/ralph/status.py` picks the next one: the first
`todo` task, owned by the agent, whose deps are all `done` or `dropped`. Work exactly one task
per iteration (PROMPT.md).

**Format.** status.py parses these lines, so keep them exact:
- `### <ID> — <title>`
- `- status: todo | done <YYYY-MM-DD> | blocked (<kevin|network|agent>): <why + what unblocks it> | dropped: <why>`
- `- owner: kevin` marks a human gate, which you never mark done yourself.
- `- deps: <IDs> | none`
- `- attempts: <n>`

Everything else in a block is free text for you: `do`, `done when`, `budget`, `spent`, `notes`.

**The plan is disposable; the acceptance criteria are not.** If a task is wrong, too big or
missing a step, edit it: split it (T2.4 → T2.4a/T2.4b), add a task, or reorder. Write one line
under the task's `notes:` saying why. Never weaken a SPEC acceptance criterion. If one can't be
met, block the task with evidence. Prune long `notes:` once a task is done.

Always-checks for every task (on top of its own `done when`): `.venv/bin/python -m pytest -q`
all green; `bash scripts/ralph/bootstrap.sh` reports v1 unchanged (AC-0.2);
`git grep -I -nE 'AIza[0-9A-Za-z_-]{30,}|sk-or-v1-[0-9a-f]{20,}' -- ':!pdfs' ':!*.db'` empty (AC-0.5;
`-I` and the excludes matter: a plain `git grep` over 2 GB of PDFs gets killed);
`python3 scripts/ralph/status.py` exits 0 or 3 (the plan still parses).

---

## M0 — Baseline

### T0.1 — Skip the root-only test when running as root
- status: done 2026-10-02
- deps: none
- attempts: 1
- budget: US$0 · network: none
- do: `tests/test_load.py::test_unwritable_target_exits_2` relies on chmod, which root ignores
  (cloud containers run as root). Add `@pytest.mark.skipif(hasattr(os, "geteuid") and
  os.geteuid() == 0, reason="root ignores chmod")`. `tests/test_ralph_status.py` already exists:
  just run it.
- done when: the full suite passes with zero failures, including as root in the cloud.
- notes: skipif added; 198 passed as uid 1000 (Proxmox, not root), test_ralph_status 14 passed. Root skip path not exercised locally.

### T0.2 — Verify the baseline in this environment
- status: done 2026-10-02
- deps: T0.1
- attempts: 1
- budget: US$0 · network: pypi (venv), openrouter.ai (credit check only, free)
- do: Run `bash scripts/ralph/bootstrap.sh`, the full test suite, and a DB rebuild
  (`.venv/bin/python -m disclosures load --source gemini-api`). Then the AC-2.7 and AC-2.9
  queries in `docs/v2/loading.md`, and the AC-2.8 id hash computed with the AGENTS.md
  one-liner (expect `f69d40da…`; the `| shasum` form in loading.md gives `ba764fdc…` for the
  same ids, so don't use it). Record the baseline in PROGRESS.md: test count, documents/members/
  terms/items, the hash, and the remaining credit from `python3 scripts/ralph/credit.py`.
- done when: load prints `loaded 768 files, skipped 0 (source gemini-api) -> disclosures_v2.db`
  then `members 303, member_terms 763, items 42042`, and exits 0 with all three hard AC-2.7
  queries at 0. PROGRESS.md has the baseline line.
- notes: 198 tests pass; load exit 0, hard AC-2.7 = 0/0/0 (informational 4); AC-2.9 null party 0; hash f69d40da; credit US$18.87.

---

## M1 — Attachment fix (prompt v1, rule C12) — SPEC-DELTA D1

### T1.1 — Attachment-gap detector and candidate list
- status: done 2026-10-02
- deps: T0.2
- attempts: 1
- budget: US$0 · network: none
- do: Write `scripts/find_attachment_gaps.py` (reads `extractions/gemini-api/house/**`, and
  v1's `disclosures.db` read-only). A file is a candidate if (a) a v2 item's description points
  at an attachment (see attach/attached/Attachment X/annexure/schedule/"as per list") and that
  section+owner has ≤ 2 items on later pages, or (b) `extraction_notes` mentions an attachment,
  schedule, broker or portfolio statement and ≥ 3 distinct v1 named entities have no v2 match
  (`rapidfuzz.fuzz.partial_ratio` < 85 against entity_name + description). Write
  `eval/attachment_gaps.csv`: stem, pdf_path, reason, referencing page/section/owner, v2 item
  count, v1-unmatched sample, `verdict` (blank). Add a small unit test with a fixture.
  D1 lists the files it must find; `odowdk45p` has to be in the output.
- done when: the script runs in < 2 min; the CSV exists with every D1-listed file plus whatever
  else the rules catch (expect ≈ 10–30 rows); the test passes.
- notes: 29 rows (<1 s): 23 rule (a), 10 rule (b), all 12 D1 files incl. odowdk45p (21 v1 unmatched). Extra rule-(a) hits like turnbullm_44p/grayg_44p are likely 'schedule' false positives for T1.2 to rule out.

### T1.2a — Confirm the 43rd candidates by looking at the pages
- status: done 2026-10-02
- deps: T1.1
- attempts: 1
- budget: US$0 (you read the PDFs yourself with the Read tool, ≤ 20 pages per call) · network: none
- do: For each candidate in the 43rd (9 rows), open the referencing page and the attachment pages. Set `verdict`
  to `attachment_not_itemised` (attachment bound in, items missing), `itemised_ok`,
  `attachment_not_in_pdf`, or `other: <what>`. For `attachment_not_itemised`, note in an
  `expected` column 3–5 entity names from the attachment, which T1.5 will check for.
  Add a `## 43rd` section to `eval/attachment_gaps.md`: verdict per file, the list to
  re-extract, and anything odd.
- done when: every in the 43rd (9 rows) row in `eval/attachment_gaps.csv` has a verdict; `eval/attachment_gaps.md`
  has its section.
- notes: T1.2 split 2026-10-02 (29 candidates > 25) by parliament, per its own instruction. 43rd: 2 attachment_not_itemised (coultonm_43p, nevillep_43p), 6 itemised_ok, 1 attachment_not_in_pdf (somlyaya). Added `expected` column to CSV + FIELDS.

### T1.2b — Confirm the 44th candidates by looking at the pages
- status: done 2026-10-02
- deps: T1.2a
- attempts: 1
- budget: US$0 (you read the PDFs yourself with the Read tool, ≤ 20 pages per call) · network: none
- do: For each candidate in the 44th (8 rows), open the referencing page and the attachment pages. Set `verdict`
  to `attachment_not_itemised` (attachment bound in, items missing), `itemised_ok`,
  `attachment_not_in_pdf`, or `other: <what>`. For `attachment_not_itemised`, note in an
  `expected` column 3–5 entity names from the attachment, which T1.5 will check for.
  Add a `## 44th` section to `eval/attachment_gaps.md`: verdict per file, the list to
  re-extract, and anything odd.
- done when: every in the 44th (8 rows) row in `eval/attachment_gaps.csv` has a verdict; `eval/attachment_gaps.md`
  has its section.
- notes: 44th: 3 attachment_not_itemised (coultonm_44p, huntg_44p, pynec_44p, a CV as the s13 list), 3 itemised_ok, 2 attachment_not_in_pdf (grayg, turnbullm gift details).

### T1.2c — Confirm the 45th/47th candidates and summarise
- status: done 2026-10-02
- deps: T1.2b
- attempts: 1
- budget: US$0 (you read the PDFs yourself with the Read tool, ≤ 20 pages per call) · network: none
- do: For each candidate in the 45th and 47th (12 rows), open the referencing page and the attachment pages. Set `verdict`
  to `attachment_not_itemised` (attachment bound in, items missing), `itemised_ok`,
  `attachment_not_in_pdf`, or `other: <what>`. For `attachment_not_itemised`, note in an
  `expected` column 3–5 entity names from the attachment, which T1.5 will check for.
  Add a `## 45th and 47th` section to `eval/attachment_gaps.md`: verdict per file, the list to
  re-extract, and anything odd. Then write the summary at the top: counts per verdict across all 29 and the full re-extract list.
- done when: every in the 45th and 47th (12 rows) row in `eval/attachment_gaps.csv` has a verdict; `eval/attachment_gaps.md`
  has its section. The summary lists the confirmed files (expect ≤ 15).
- notes: 45th/47th: 2 attachment_not_itemised (coultonm_45p, odowdk45p ×2 attachments), 5 itemised_ok, 2 not in PDF (pynec_45p, smitht_45p), 3 false positives. Total: 7 to re-extract (listed in eval/attachment_gaps.md summary). For T1.3: say an attachment continues the referencing item, not the next alteration form (smitht_45p).

### T1.3 — Add rule C12 to the extraction prompt (prompt v1)
- status: done 2026-10-02
- deps: T1.2c
- attempts: 1
- budget: US$0 · network: none
- do: Add C12 and checklist item 7 to `disclosures/prompts/extract.md`, worded as in
  SPEC-DELTA D1, and change the header from v0 to v1. If T1.2 found an attachment pattern
  D1's wording doesn't cover, adjust the wording and say why. Add a DECISIONS.md entry
  (`plans/2026-10-01-disclosures-v2/DECISIONS.md`) with the finding, the rule, the gold
  precedent (plibersekt_43p) and the re-extraction scope. Update `docs/v2/extraction.md` where
  it describes the prompt.
- done when: the prompt has C12; tests pass (some may pin prompt text: update them only if
  they test wording, never behaviour).
- notes: C12 + checklist 7 added, header v1. Wording widened beyond D1 (fund-only reference, adviser letter/CV/membership list, not the next form, no totals/ended entries); see DECISIONS 2026-10-02. No test pins prompt text; 200 pass. Workflow JS now says C1-C12.

### T1.4 — Gold regression with prompt v1 (paid)
- status: done 2026-10-02
- deps: T1.3
- attempts: 1
- budget: cap US$1.20 including one wording revision (est. 0.50 per run) · network: openrouter.ai
- spent: US$0.47
- do: `credit.py --min 3` first. Run the G2 extract command (AGENTS.md) on the 12 gold PDFs
  (`eval/gold/selection.json`) with `--source-id gemini-api-promptv1 --out-root
  .ralph/scratch/gold-promptv1` (gitignored; scratch, not committed). Score:
  `.venv/bin/python -m disclosures score --pred .ralph/scratch/gold-promptv1 --gold eval/gold
  --json eval/gemini-api-promptv1.json`. Compare with `eval/gemini-api.json` (F1 0.987). Add a
  section "Prompt v1 (C12) regression" to `eval/bakeoff.md`: the metrics side by side,
  plibersekt_43p's p8 items, and the cost.
- done when: F1 ≥ 0.980 and every ADR-4 bar metric still passes. If not, revise the wording
  once and re-run (within the US$1.20 cap). If it fails twice: `blocked (kevin): prompt v1 regresses
  gold (numbers…); keep v0 or accept?` and revert the prompt to v0 so later tasks aren't built
  on it.
- notes: v1 F1 0.984 (v0 0.987), P 0.984 R 0.985, owner/page 1.000; ADR-4 PASS, no revision needed. Only diff prenticej_45p p29 entity naming (variance). plibersekt p8 13 items identical.

### T1.5 — Re-extract the confirmed files with prompt v1 (paid)
- status: done 2026-10-02
- deps: T1.4
- attempts: 1
- budget: cap US$3.00 (est. 1.50) · network: openrouter.ai
- spent: US$0.48
- do: `credit.py --min 3`. Run the G2 extract command with `--force` on the
  `attachment_not_itemised` files, in batches of ≤ 10 per Bash call. `validate` the directory.
  For each file, check that T1.2's `expected` names are now present, and record before/after
  item counts in `eval/attachment_gaps.md`. Rebuild the DB and run AC-2.7/2.8/2.9 (item ids
  change for re-extracted files only; that's expected, so record the new hash). Add a
  "Re-extracted with prompt v1 (C12)" section to `eval/extraction_failures.md`. Commit the
  changed extraction JSON.
- done when: `validate extractions/gemini-api/house` reports 0 invalid; every re-extracted file
  contains its expected names (or the file is listed with a reason); the load hard queries
  are 0.
- notes: 7 files, 315 → 525 items (+210), 35/35 expected names found (pynec's "Diddatico" was a typo in the CSV). validate 768/0; load 42,252 items, hard AC-2.7 0, AC-2.9 0; new AC-2.8 hash 465f1071…. Extraction JSON has no prompt-version field: the v1 file list in eval/extraction_failures.md is the record (T5.1 README needs it).

### V1 — Cold verification of M1
- status: done 2026-10-02
- deps: T1.5
- attempts: 1
- budget: US$0 · network: none
- do: Spawn ONE fresh subagent (general-purpose). Give it only this block's checklist plus file
  paths, not your reasoning. Ask it to reproduce and try to break: C12 is in the prompt;
  `eval/attachment_gaps.md` matches the CSV; each re-extracted file has its expected items on
  the attachment pages with the referencing section/owner; validate 0 invalid; load hard
  queries 0; the suite is green; v1 sha unchanged. Fix small findings now. Add a task for any
  large finding.
- done when: the subagent reports no unresolved finding (paste its verdict line into notes).
- notes: Round 1 verdict "FAIL — 4 findings", all small: F1 nevillep_43p joint-fund holdings filed
  under self only (→ T1.6); F2 huntg_44p p11 `varied` vs ADDITION (kept, DECISIONS 2026-10-02);
  F3/F4 wording in eval/attachment_gaps.md (fixed). All hard checks passed: validate 768/0, load
  42,252 items, hard AC-2.7 0, hash 465f1071…, 200 tests. Round 2: "VERDICT: PASS — no
  unresolved findings".

### T1.6 — nevillep_43p: joint-fund attachment holdings for the spouse too
- status: blocked (kevin): G2 re-extraction (--force, US$0.05) again gave the 19 p8 s9 holdings to self only (85 items, same as before), so the earlier file was restored from git. Decide: accept self-only for nevillep_43p, or allow a hand correction/override (e.g. a data/overrides owner rule) that duplicates the 19 p8 items for spouse?
- deps: V1
- attempts: 1
- budget: US$0.25 · network: openrouter
- do: V1 F1. In `extractions/gemini-api/house/43/nevillep_43p.json` the p5 s9 fund is joint (the
  spouse row says "as above with same riders"), but the 19 p8 holdings are filed under self only.
  coultonm_43p/44p/45p have both owners (DECISIONS 2026-10-02, "joint-fund owners"). Re-extract
  this one file with `--force` on the G2 config (one paid call, ≈ US$0.03–0.16). If the result
  still lacks the spouse rows, don't hand-edit the model output. Restore the earlier file from git
  and set `blocked (kevin): accept self-only, or allow a hand correction/override for owner?`.
- spent: US$0.05
- notes: 2026-10-02 attempt 1: re-extract 85 items, p8 (8,9,self)=19, no spouse rows; file restored.
- done when: 19 p8 s9 items for self and 19 for spouse; the other ≈ 66 non-p8 items still there; validate 768/0; load exit 0, hard AC-2.7
  0; AC-2.8 hash recorded in AGENTS.md; the T1.5 table in `eval/attachment_gaps.md` updated.

---

## M2 — Phase 3: entities (SPEC ADR-6, AC-3; SPEC-DELTA D2)

### T2.1 — `entities` command skeleton: normalise, generic terms, DB writes, determinism
- status: done 2026-10-02
- deps: T0.2
- attempts: 1
- budget: US$0 · network: none
- do: Create `disclosures/entities.py` and wire it into `disclosures/cli.py` (replacing the
  stub). Implement steps 1 and 2 of ADR-6: `normalise_entity`, and
  `data/entities/generic_terms.csv` (start from ADR-6's examples, then add the obvious generic
  descriptors you find in the data's top 300 normalised names). Implement the curated / asx /
  llm / singleton stages as pluggable steps, with singletons only for now. Write `entities`,
  `entity_aliases` and `items.entity_id`, with ids per D2. Write `docs/v2/entities.md` (run
  order, inputs, methods). Tests: normalisation reuse, generic → NULL entity, singleton,
  determinism (two runs → identical tables), NULL entity_name → no entity.
- done when: `.venv/bin/python -m disclosures entities --offline` runs on the real DB and prints
  method counts; tests pass.
- notes: real DB: 35,880 named items -> 11,165 entities; generic 6 aliases/16 items, singleton 11,181 aliases/35,864 items; AC-3.3 0; 16 same-slug merges (all true). Curated stage already reads aliases.csv; asx/llm are no-op stages (T2.2, LLM task). Until LLM lands, singleton also catches >=2-item aliases. Full .dump sha identical over 2 runs. 13 tests, 212 pass.

### T2.2 — ASX snapshot and ASX matching
- status: done 2026-10-02
- deps: T2.1
- attempts: 1
- budget: US$0 · network: www.asx.com.au
- do: `entities --fetch-asx` downloads `https://www.asx.com.au/asx/research/ASXListedCompanies.csv`
  with the browser User-Agent (AGENTS.md) to `data/reference/asx_listed_companies_<date>.csv`
  (the first line is a title, then the header `Company name, ASX code, GICS industry group`).
  Implement ADR-6 step 4 per D2 (exact normalised name or exact ticker; `asx_code` set;
  `entity_type='listed_company'`). Fixture-based tests.
- done when: the snapshot is committed (≈ 2,000 rows); `entities --offline` reports `asx` > 0;
  tests pass. If the host is blocked: `blocked (network): run 'python -m disclosures entities
  --fetch-asx' locally and commit the CSV`.
- notes: snapshot 2026-10-02, 2,048 companies. Real DB: asx 309 aliases / 4,370 items (117 ticker
  matches), 11,101 entities, AC-3.3 0. `ing` excluded (Inghams vs ING Bank, asx_exclusions.csv).
  For T2.4: curate ANZ/NAB/CBA canonicals; ASX canonical = commonest raw spelling (DECISIONS).

### T2.3 — Candidate list for the curated aliases (top 200 plus variants)
- status: done 2026-10-02
- deps: T2.2
- attempts: 1
- budget: US$0 · network: none
- do: `entities --draft-candidates` writes `data/entities/alias_candidates.csv`: the top 200
  normalised names by item count (after generic removal), each with its item count, sections,
  sample raw spellings, and every other normalised name with `token_set_ratio` ≥ 90 to it
  (ADR-6 step 3). Include the ASX match if any. Test it on a fixture.
- done when: the CSV exists and covers 200 heads; the AC-3.1 names all appear (CBA,
  Commonwealth Bank, NAB, ANZ, Qantas, Virgin Australia, Westpac, Telstra variants present in
  the data).
- notes: `entities --draft-candidates [CSV] [--top N]` (read-only on the DB). 200 heads from 11,181
  non-generic names; variants median 3, max 53 (vanguard); all 7 AC-3.1 groups present (test
  `test_real_candidates_cover_ac31`). Heads 1-6: qantas 1,362, westpac 772, nab 607, commonwealth
  bank 595, anz 577, cba 540. 225 tests pass.

### T2.4 — Curate aliases.csv: heads 1–100
- status: done 2026-10-02
- deps: T2.3
- attempts: 1
- budget: US$0 (your own judgment, no API) · network: none
- do: Write `data/entities/aliases.csv` (columns per D2) for heads 1–100 and their true
  variants. Reject fuzzy variants that are different organisations (e.g. "Westpac" vs "Westfield").
  Choose `canonical_name` (the organisation's proper current name), `entity_type` (ADR-6 enum)
  and `asx_code` (from the snapshot; leave blank if unlisted). Set `review_flag=1` with a `note`
  wherever you're unsure. AC-3.1 groups must collapse to one canonical each.
- done when: rows for heads 1–100 exist; `entities --offline` uses them (`curated` > 0); an
  AC-3.1 test passes for every group that occurs.
- notes: 330 aliases → 72 entities (all 100 heads); curated 12,597 items, asx 279/1,067 left; 15 rows review_flag=1. ASX stage now reuses a curated row's canonical for the same code (no splits). Rules in DECISIONS 2026-10-02 (T2.4).

### T2.5 — Curate aliases.csv: heads 101–200, coverage test
- status: done 2026-10-02
- deps: T2.4
- attempts: 1
- budget: US$0 · network: none
- do: Same as T2.4 for heads 101–200. Add the AC-3.2 test: every row has an enum
  `entity_type`, and coverage is ≥ 95% of the item count of the top 200. The script prints
  coverage.
- done when: the AC-3.2 test passes; coverage is printed and ≥ 95%.
- notes: +192 rows → 522 aliases / 153 entities, 24 flagged; curated 14,641 items; coverage 13,576/13,576 = 100% (printed by `entities`; `curated_coverage()`); 232 tests pass. Rules in DECISIONS 2026-10-02 (T2.5).

### T2.6 — Long-tail LLM step with a committed cache (paid)
- status: done 2026-10-02
- deps: T2.5
- attempts: 1
- budget: cap US$3.00 (est. 1–2) · network: openrouter.ai
- spent: US$1.16 (104 requests; credit 17.86 → 16.86)
- do: Implement ADR-6 step 5 per D2. Blocking first, then dry-run to count blocks and estimate
  cost before any call; if the estimate exceeds the cap, tighten blocking or raise the item
  threshold, and note it. Add a text-mode JSON call to `disclosures/openrouter.py` (strict
  `json_schema`, flex, model via `resolve_gemini_model`). Cache to
  `data/entities/llm_decisions.jsonl`. `--offline` = cache only. Mocked tests: request shape,
  cache hit = no HTTP, offline + missing block → exit 1. `credit.py --min 3` before the live
  run, then run it in chunks so a crash loses little.
- done when: the online run completes within budget; `entities --offline` then succeeds with
  `llm` > 0; tests pass; spend recorded.
- notes: dry run: 4,090 aliases / 14,128 items, 3,322 blocks (417 with > 1 name), 104 requests.
  Result: 3,822 groups (232 merges, 3,567 high), 0 bad replies; offline llm 4,090 aliases,
  singleton 6,305 (1-item only), AC-3.3 0, two offline runs identical. AC-3.4 rule: LLM
  listed_company without an exact snapshot match → other (303 groups); one entity per ASX code.

### T2.7 — Entities report and AC-3.3/3.4/3.6
- status: done 2026-10-02
- deps: T2.6
- attempts: 1
- budget: US$0 · network: none
- do: Write `eval/entities_report.md`: method counts, entity-type counts, and the top 20 entities
  by item count next to v1's top 20 (`disclosures.db`, read-only), plus the AC-3.3 and AC-3.4
  query results. Add tests for AC-3.3 (non-generic named items without an entity = 0) and
  AC-3.4 (curated, asx and generic all > 0; every listed_company has an asx_code that's in the
  snapshot). Look at the top 20 yourself: no two rows should be the same organisation. If
  they are, fix the aliases.
- done when: the report exists; the AC-3.3/3.4 tests pass; the top 20 has no duplicates.
- notes: `entities --report` regenerates the marked block of eval/entities_report.md (method/type
  counts, AC-3.3 0, AC-3.4 PASS: 243 listed_company all coded, v2 vs v1 top 20); hand review below it.
  Review found LLM-minted dups of curated names (qf->"Qantas", west pac->"Westpac") -> join-by-name
  post-pass (DECISIONS): 34 merges, 10,219 -> 10,185 entities; Tower Ltd/Tower Australia kept apart.
  tests/test_entities_report.py (7); 252 pass.

### T2.8 — G3 review pack for Kevin
- status: done 2026-10-02
- deps: T2.7
- attempts: 1
- budget: US$0 · network: none
- do: Write `eval/entities_g3_review.csv` per D2: the top 50 by item count plus every
  `review_flag` row, plus LLM merges with confidence ≠ high touching ≥ 5 items. Add a short
  "How to review G3" section to `eval/entities_report.md`: what to check, how to fill
  `kevin_ok` / `kevin_fix`, how to approve (D6). Update HANDOFF.md: G3 is waiting on Kevin,
  with the row count.
- done when: the CSV exists and HANDOFF.md says what Kevin must do.
- notes: `entities --g3-review` -> 101 rows (50 top, 24 flagged with 4 in the top 50, 31
  llm-medium), 10,381 items; keeps kevin_* on regenerate; kevin_fix format in the report.

### G3 — Kevin reviews the top-50 aliases and flagged rows
- status: todo
- owner: kevin
- deps: T2.8
- notes: Kevin: fill `kevin_ok`/`kevin_fix` in `eval/entities_g3_review.csv`, then change this
  status line to `done <date>` (or tell the cloud session "G3 approved" and it records your
  message here).

### T2.9 — Apply G3 fixes; final entity load
- status: todo
- deps: G3
- attempts: 0
- budget: US$0 · network: none
- do: Apply every `kevin_fix` to `data/entities/aliases.csv` (and any LLM cache overrides,
  as a curated row). Re-run `load` then `entities --offline`. Re-check AC-3.1–3.6 and refresh
  `eval/entities_report.md`. Record G3 in DECISIONS.md (AC-3.5), with the date and what Kevin
  changed.
- done when: all AC-3 tests pass; DECISIONS has the G3 entry.

### V2 — Cold verification of Phase 3
- status: todo
- deps: T2.9
- attempts: 0
- budget: US$0 · network: none
- do: As V1, with a fresh subagent and only AC-3.1–3.6 plus D2: reproduce each check, rebuild
  from scratch (`load` → `entities --offline`) twice and compare the entity tables, and look
  for duplicate organisations in the top 50.
- done when: no unresolved finding.

---

## M3 — Phase 4: scraper, House 48th, Senate 48th, refresh (SPEC ADR-8/9, AC-4; SPEC-DELTA D3)

### T3.1 — `disclosures/sources.py`: URLs, User-Agent, register parser, recorded fixtures
- status: done 2026-10-02
- deps: T0.2
- attempts: 1
- budget: US$0 · network: www.aph.gov.au (record fixtures once)
- do: URL map for House 43rd–48th (SPEC §0 and D3; the 47th has its own slug), a browser UA on
  every request, polite retries and backoff. Record fixtures once:
  `tests/fixtures/aph/house_48_register.html` and one archive page (e.g. the 46th). Parse rows
  into (listed_date, member name, electorate, statement URL). Tests run offline on the fixtures.
- done when: the AC-4.1 test passes (the 48th fixture yields 150–155 rows, each with a statement
  URL of either kind).
- notes: 48th fixture 151 rows (147 api + 4 static). 43rd §0 URL 404s, so it maps to the committee page
  the 48th links (`?url=pmi/declarations.htm`, 150 links = v1 stems); fixture recorded for T3.2.
  Archive counts: 44th 151, 45th 158, 46th 152, 47th 155. DECISIONS 2026-10-02 (T3.1).

### T3.2 — `pdfs/manifest.csv` for the 774 tracked PDFs
- status: done 2026-10-03
- deps: T3.1
- attempts: 1
- budget: US$0 · network: www.aph.gov.au (archive listings)
- do: Build the ADR-8 manifest (columns in SPEC ADR-8) for every tracked PDF. Take
  sha256/page_count from the file (or `eval/pdf_stats.csv`) and parliament from the path. Get
  member/electorate from `data/overrides/pdf_members.csv`. Match source_url and listed_date from
  the archive listings where you can; leave them empty otherwise, and print the count matched.
  Test: every manifest sha matches its file (AC-4.3), and the row count equals `git ls-files
  pdfs | grep -c '\.pdf$'`.
- done when: the AC-4.3 test passes; the matched-URL rate is printed in PROGRESS.md.
- notes: `disclosures/manifest.py` (`python -m disclosures.manifest --backfill`); 774 rows,
  source_url 770 (99.5%), all member statements; 4 misses = unlinked `interestsr_*p.pdf`.
  Parser gaps for T3.3a: `sources.parse_register` skips rows with no "Member for" (44th Hastie
  "for Canning", 46th McBain "Member Eden-Monaro") and leaves a footnote in the seat
  ("Bennelong, NSW¹", 45th) so `state` is None.

### T3.3a — `scrape --chamber house --parliament 48`: download, manifest, idempotency
- status: done 2026-10-03
- deps: T3.2
- attempts: 1
- budget: US$0 · network: www.aph.gov.au, interests-register-api-public.aph.gov.au, static.aph.gov.au
- do: Implement `scrape` per ADR-8 and D3. **First** download one API statement twice and
  compare sha256 (D3), then design change detection to match. Download both link kinds to
  `pdfs/48/`, name files per D3, refuse anything > 95 MB, and append manifest rows. Write
  `docs/v2/scrape.md`. Recorded-response tests for both link kinds and for idempotency. Commit
  the PDFs in one commit with the manifest.
- done when: AC-4.2 (150–155 house/48 manifest rows) and AC-4.4 (a second run logs
  `0 new, 0 changed`) pass.
- notes: D3 sha check: the same API statement (316915) and the same static PDF downloaded twice
  gave identical bytes; `--verify` over all 151 found 0 changed → sha256 is the signal, and
  the listing link+date gate the download. 151 PDFs (147 api, 4 static), 85 MB, 0 refused;
  `grep -c '^house,48,' pdfs/manifest.csv` = 151; second run `0 new, 0 changed, 151 unchanged`.
  eval/pdf_stats.csv now has 925 rows. pdf_members coverage test excludes 48 until T3.3b.

### T3.3b — Member identity for the 48th PDFs
- status: done 2026-10-03
- deps: T3.3a
- attempts: 1
- budget: US$0 · network: en.wikipedia.org (canonical names for new members)
- do: Per D3's new-members rule: a `pdf_members.csv` row for every 48th PDF, returning MPs
  matched through `member_aliases.csv` (normalised name plus electorate), new MPs given a
  member_id and a `member_aliases.csv` row (`source=aph_48`). Print how many were matched vs
  new, and eyeball every "new" one: a returning MP misread as new would split their history.
- done when: every `pdfs/48/*.pdf` has exactly one pdf_members row; no 48th member_id
  duplicates a 43rd–47th person (check by normalised name).
  Also remove the `pdfs/48/` exclusion that T3.3a put in
  `tests/test_load.py::test_real_overrides_cover_all_tracked_pdfs`; it must pass over every
  tracked PDF again.
- notes: `python -m disclosures.members --parliament 48`: 151 rows, 118 returning, 33 new, 0
  collisions. Hand aliases: Robert Katter→bob_katter, Joshua Wilson→josh_wilson, Thomas
  French→tom_french (Wikipedia). tests/test_members.py; party check in the cover test skips 48 until T3.4.

### T3.4 — 48th House party terms
- status: done 2026-10-03
- deps: T3.3b
- attempts: 1
- budget: US$0 · network: en.wikipedia.org
- do: Per D3, add `party_terms.csv` rows (`source=wikipedia_48`) for every 48th House member;
  put misses in `unknown_party.csv`. Also extend `scripts/seed_v2_overrides.py --check` (or
  document in `data/overrides/README.md` that 48th rows are hand-maintained, since the seed
  script only knows v1).
- done when: every 48th member_id has a party row or an unknown_party row, and AC-2.9's ≤ 5
  holds across all terms. Remove the `< 48` filter T3.3b put in the party loop of
  `tests/test_load.py::test_real_overrides_cover_all_tracked_pdfs`; it must pass for the 48th.
- notes: `members --party-terms` from pinned Wikipedia revs 1303424746 (start of term) +
  1377733140 (Farley by-election only): 151 rows, 0 unknown (94 ALP, 16 LNP, 18 LIB, 9 NAT,
  14 crossbench). Joyce = National, Spender/Steggall = Independent (start of term). seed
  `--check` now derives 43rd-47th only and keeps 48th+/aph_* rows verbatim (it had failed since
  T3.3a). 48th member_terms reach the DB only after T3.5 extracts; the overrides test covers AC-2.9 now.

### T3.5 — Extract the House 48th (paid)
- status: done 2026-10-03
- deps: T1.5, T3.4
- attempts: 1
- budget: cap US$8.00 (est. 5–6) · network: openrouter.ai
- spent: US$4.03
- do: `credit.py --min 3` before each batch. Run the G2 extract command (AGENTS.md; prompt v1)
  on `pdfs/48/*.pdf` in batches of ≤ 20 per Bash call (each call < 10 min), and re-run until
  valid (idempotent). Validate. Add a "48th Parliament" section to `eval/extraction_failures.md`
  (valid + failed with reasons = PDFs in the manifest; ≤ 5 failures). Rebuild the DB, check
  AC-2.7–2.9, and AC-4.7 (`select count(distinct member_id) from items where chamber='house'
  and parliament=48` between 145 and 155). Commit the extractions in waves.
- done when: those checks pass and spend is recorded.
- notes: 151/151 valid first pass, 0 failures, 0 Sonnet fallback; validate 919/0; 48,956 items
  (6,704 48th); AC-2.7 hard 0, AC-2.9 0, AC-2.8 hash c4888789… stable; AC-4.7 151.
  `entities --offline` now exits 1 (554 uncached long-tail blocks from new names) until T3.10
  runs online, so 5 DB-state entity tests skip meanwhile.

### T3.6 — Senate 48th adapter (`senate-json`)
- status: done 2026-10-03
- deps: T3.1
- attempts: 1
- budget: US$0 · network: www.aph.gov.au, pbs-apim-aqcdgxhvaug7f8em.z01.azurefd.net
- do: Per D3: fetch the list and all 76 statements and save the raw payloads to
  `pdfs/senate/48/`. Map keys to sections (an unmapped key is an error). Write
  `extractions/senate-json/senate/48/<stem>.json`. Make `validate` accept `.json` source
  documents (D3), and add a DECISIONS.md entry. Recorded-payload fixtures (the list plus 2
  senators, including one with alterations) for offline tests of the mapping, alteration
  types and dates. Add Senate rows to `pdfs/manifest.csv` (chamber senate, listed_date =
  lastDateUpdated).
- done when: `validate extractions/senate-json` reports 76 valid, 0 invalid; tests pass.
- spent: US$0.00
- notes: `disclosures/senate.py`; `scrape --chamber senate` -> 76 payloads + manifest rows
  (2nd run 0 new, 0 changed); `extract --source senate-json` -> 76 valid, 1,980 items (1,328
  initial, 597 added, 55 removed). Keys: the 14 D3 ones only. Dates = Sydney date of UTC stamps.
  AC-4.3 test now covers `pdfs/senate/**.json`. For T3.7: no pdf_members rows yet; Urquhart and
  Small (now House) left the Senate list.

### T3.7 — Senate members, parties, multi-source load, source doc
- status: done 2026-10-03
- deps: T3.6, T3.5
- attempts: 1
- budget: US$0 · network: none
- do: `pdf_members.csv` rows for the Senate source docs. Senators who were MPs resolve to their
  existing member_id via `member_aliases.csv`; check the 43rd–47th House names. Add
  `party_terms.csv` senate/48 rows (`source=aph_senate_api`). Make `load` take a repeatable
  `--source`, and apply the D3 `members.chamber` rule. Update `docs/v2/loading.md`. Write
  `docs/v2/senate_source.md` (endpoints, payload shape with a sample, section mapping,
  coverage, the reCAPTCHA note). Tests for the multi-source load.
- done when: `load --source gemini-api --source senate-json` exits 0; AC-4.6
  (`select count(distinct member_id) from items where chamber='senate' and parliament=48`
  between 70 and 80) and AC-2.9 pass.
- notes: 76 senate pdf_members rows (4 ex-MPs keep House ids: ananda_rajah, henderson,
  deborah_o_neill, dave_sharma; 72 new) + 76 party_terms (aph_senate_api, 0 unknown). load
  gemini-api+senate-json exit 0: 995 files, 408 members (76 senate), 50,936 items; AC-4.6 76,
  AC-2.9 0; House hash c4888789 unchanged, full 88fb48c0 stable. 301 tests pass.

### T3.8 — `refresh` (dry-run and real)
- status: todo
- deps: T3.7
- attempts: 0
- budget: US$0 to build (the live dry-run is free) · network: aph hosts for the dry-run
- do: Implement `refresh` per SPEC AC-4.5 and D3: `--dry-run` lists new/changed House 48th
  statements and Senate statements against the manifest. A non-dry run with the gemini source
  scrapes the new/changed, extracts only those (G2 config), runs the Senate adapter for changed
  senators, then `load` (all sources) and `entities`. With the workflow source it prints the
  exact Workflow args JSON for Kevin. Test with a fixture manifest where one sha differs →
  exactly that file is selected. Run `refresh --dry-run` live once and record its output in
  PROGRESS.md. Don't run a non-dry refresh here.
- done when: the AC-4.5 test passes; the live dry-run output is recorded.

### T3.9 — Senate archives 43rd–47th: discovery only
- status: todo
- deps: T3.7
- attempts: 0
- budget: US$0 · network: www.aph.gov.au, the senators API host
- do: Per D3: find out whether `queryStatements` filters by parliament, and what the archive
  pages contain. Document the findings in `docs/v2/senate_source.md` with a follow-up estimate
  (count, format, cost if PDFs). If the API serves earlier parliaments as the same JSON, add
  them through the adapter (free) and reload. Otherwise stop at documentation (ADR-9 accepted
  outcome).
- done when: senate_source.md has an "Archives" section with the evidence.

### T3.10 — Entities over the full dataset (paid, small)
- status: todo
- deps: T3.7, T2.7
- attempts: 0
- budget: cap US$1.00 (est. 0.50) · network: openrouter.ai
- spent: US$0.00
- do: `load` all sources, then `entities` (online; only new uncached blocks hit the LLM;
  `credit.py --min 3` first). Re-check AC-3.3/3.4, and refresh `eval/entities_report.md` with
  the 48th and Senate included. If the new top 50 contains uncurated heads, curate them
  (`review_flag=1`). If G3 is already approved, add them to the pack as a G3 addendum and
  mention it in HANDOFF.
- done when: AC-3.3/3.4 pass on the full DB; report refreshed.

### V3 — Cold verification of Phase 4
- status: todo
- deps: T3.5, T3.7, T3.8, T3.9, T3.10
- attempts: 0
- budget: US$0 · network: none (offline checks only)
- do: As V1, with a fresh subagent and only AC-4.1–4.7, AC-2.6 for the 48th, and D3. Rebuild
  from scratch, run every check, try to break the manifest (sha mismatch), validate, the
  Senate mapping (spot-check 5 senators' JSON against their payloads) and refresh's selection.
- done when: no unresolved finding.

---

## M5 — Phase 5: prepare publication (SPEC ADR-10, AC-5). Kevin publishes (G4).

### T5.1 — `export`
- status: todo
- deps: V3
- attempts: 0
- budget: US$0 · network: none
- do: Implement `export` per ADR-10/AC-5.1: `exports/disclosures_v2.csv` (one row per item,
  joined with member, term and entity; readable column names) and `exports/kaggle/`
  (`disclosures_v2.csv`, a README with a field dictionary covering every column plus method and
  known limitations, including D2's untyped singletons and D1's prompt-v0/v1 split, and
  `dataset-metadata.json`). Tests on a small fixture DB.
- done when: the AC-5.1 checks pass on the real DB (CSV rows = `select count(*) from items`).

### T5.2 — `site/` and the Pages workflow
- status: todo
- deps: T5.1
- attempts: 0
- budget: US$0 · network: none
- do: Per ADR-10/AC-5.2: `site/index.html` (what it is, coverage, how to cite, Datasette Lite
  link), `site/disclosures_v2.db`, and `.github/workflows/pages.yml` (on push to `main`
  touching `site/`). Add a `.gitignore` exception (`!site/disclosures_v2.db`), since `*.db` is
  ignored. Check it locally with `python -m http.server -d site 8000` and curl. Don't enable
  Pages. If a cloud push is refused because the token lacks `workflow` scope, keep the commit
  and block `(kevin): push .github/workflows/pages.yml from a local clone`.
- done when: the AC-5.2 checks pass.

### T5.3 — Rewrite README.md for v2
- status: todo
- deps: T5.2
- attempts: 0
- budget: US$0 · network: none
- do: Per AC-5.3: v2 only (what it is, coverage incl. 48th and Senate, every command, how to
  refresh, a data-dictionary pointer, known limitations, a v1 snapshot note). Remove v1's dead
  instructions.
- done when: the AC-5.3 grep check passes (every `python -m disclosures <cmd>` in README is a
  real subcommand).

### T5.4 — Remove dead v1 code
- status: todo
- deps: T5.3
- attempts: 0
- budget: US$0 · network: none
- do: Per AC-5.4: delete `src/` (or the listed parts), `examples/`, `test_output.json` and
  `setup_pipeline.sh`. Keep `disclosures.db` and `output/`. Retire `scripts/seed_v2_overrides.py`
  (delete it, or keep it with a header saying it needs v1 from git history), and update
  `data/overrides/README.md` to say the CSVs are now the source of truth. Make sure no test
  or doc still references removed paths.
- done when: `git grep -n "from src\." -- '*.py'` is empty; the suite is green.

### T5.5 — Requirements: fresh-venv install
- status: todo
- deps: T5.4
- attempts: 0
- budget: US$0 · network: pypi
- do: Per AC-5.5: make sure `requirements.txt` / `requirements-dev.txt` list everything v2
  imports (pinned). In a scratch venv (`.ralph/scratch/venv`), install both and run the suite.
- done when: the fresh-venv install and the suite pass.

### T5.6 — Final rebuild, full AC sweep, handover
- status: todo
- deps: T2.9, T3.10, T5.5
- attempts: 0
- budget: US$0 · network: none
- do: Rebuild everything from committed inputs: `load` (all sources) → `entities --offline` →
  `export` → copy the DB into `site/`. Run every AC in SPEC §3 (AC-0 to AC-5) and write the
  results as a table in `eval/final_acceptance.md`. Update HANDOFF.md (state, what G4 needs from
  Kevin, open questions incl. D1's Sandakan case and D2's untyped singletons), DECISIONS.md
  (the phases closed) and SPEC.md's `Progress` line. Leave its `Status: DRAFT, awaiting
  sign-off` alone: sign-off is Kevin's. For AC-0.5, use the always-check's `git grep -I …` form,
  which is equivalent but doesn't choke on the PDFs.
- done when: every AC row is pass, or "Kevin" for G4 items (AC-5.6 means: nothing pushed to
  main/v2-upgrade, no Pages, no Kaggle).

### V5 — Final cold verification
- status: todo
- deps: T5.6
- attempts: 0
- budget: US$0 · network: none
- do: A fresh subagent gets only SPEC §3 and `eval/final_acceptance.md`, re-runs every check,
  and tries to break the export and site (row counts, column dictionary, the Datasette link,
  a sample of 10 items traced back to their PDF page).
- done when: no unresolved finding.

### G4 — Kevin publishes
- status: todo
- owner: kevin
- deps: V5
- notes: Kevin: merge to main, enable Pages, upload to Kaggle, announce (SPEC G4).
