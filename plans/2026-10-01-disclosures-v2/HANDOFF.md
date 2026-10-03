# Handover — Disclosures v2 (updated 2026-10-03 night: published; public site moving to Cloudflare; next = port the graph explorer)

## Now (read this first)
v2 is finished and published (G4 below). The public site is moving from GitHub Pages to
Cloudflare Workers; README "Public site: moving to Cloudflare" has the summary. That build has
its own plan and log: `plans/2026-10-03-public-site/{SPEC,BUILDLOG,DESIGN}.md` on branch
`build/2026-10-03-public-site`, worktree `.claude/worktrees/cf-data-explorer-plan`.

**Next action: port the Pages explorer into the Cloudflare build's explorer (Phase C).**
- What to port (on `main`): `disclosures/explore.py` (builds `explore.json`: the top 60
  organisations per view, member-organisation links, bloc split, items, years; `person` entities
  excluded) and `disclosures/site_assets/explore.html`. The page combines a force-directed network
  graph (force-graph 1.52 + d3-force collide; hovering highlights neighbours, a click pins a detail
  panel with a Datasette link, labels are de-overlapped in a post-render pass) with a stacked
  bar chart by bloc and hover tooltips. Tests: `tests/test_export.py::test_site_explorer`. Live
  now: https://k-r-a-s-s.github.io/aus-govt-transparency/explore.html.
- Where it goes: SPEC ADR-W7 / AC-C1–C5 explorer (`web/src/explore.ts`,
  `disclosures/web/templates/explore.html`, Observable Plot charts). ADR-W7 has **no network
  graph and no hover tooltips**: add the graph as an extra view on `/explore/` (follow its filter
  state if cheap), add tooltips to the Plot bars, and keep the ADR-W7 JS budget (≤ 250 KB gzip)
  in mind, since force-graph alone is about 60 KB gzip. Record the addition in that SPEC's
  decisions log. Restyle with that build's `DESIGN.md` tokens (its bloc colours, not mine:
  mine are dataviz slots 1–3 blue/orange/aqua, validated all-pairs).
- **Before touching the worktree:** it held about 660 uncommitted lines of Phase C work at
  21:59 on 2026-10-03 (`web/src/explore.ts`, `templates/explore.html`, `bundle.py`, …), probably
  from another live Claude session. Check `git -C .claude/worktrees/cf-data-explorer-plan status`
  and ask Kevin whether that session is still running. Don't overwrite or stash its work.
- The build branch is **local only** (never pushed). It forked from `9df8f7b`; `main` has since
  moved (explorer + gitignore commits), and both touch `disclosures/export.py` and `.gitignore`, so
  expect a small conflict when it rebases or merges. Phase D turns `export --site` into a redirect.

## Decisions this session (don't relitigate)
- New site features go in the Cloudflare build, not `site/` (Kevin: "we should be building on
  the cloudflare one"). `site/` + `pages.yml` stay live as the interim until the ADR-W11 cutover.
  The Pages explorer stays live as a stopgap (not reverted).
- Licence CC BY 4.0, to the extent we hold rights (DECISIONS 2026-10-03).
- The directorships view was dropped from the explorer: its top organisations have only 2
  members each.

## Dead ends / corrections
- `git add -A` in the main checkout committed the worktree as a gitlink (097849d). Fixed in
  5a24fe8 (`.claude/worktrees/` is now gitignored). Check `git status` before adding.
- On this Mac the root `disclosures_v2.db` had been a stale 2026-10-02 build; it is now a copy of
  `site/disclosures_v2.db` (the final DB, sha256 `519e2430…`). Always export from the final DB.
- Kaggle CLI: `datasets create` takes `CC-BY-4.0`; `metadata --update` needs the display name
  `Attribution 4.0 International (CC BY 4.0)`. Token: `KAGGLE_API_TOKEN` in `.env.local`.

## Open (ball holder)
- Announce on Reddit (Kevin; draft in that session, numbers from the DB).
- Push `build/2026-10-03-public-site` to GitHub as a backup (Kevin / the build session).
- LICENSE file for the code (Kevin, optional).

---

## G4 record (2026-10-03, Mac session)
- Licence **CC BY 4.0** (to the extent we hold rights; facts, not the statements), Kevin's call
  for "as permissive as possible" with attribution; the source PDFs stay under APH's CC BY-NC-ND
  4.0 (DECISIONS "Licence changed to CC BY 4.0"). `export` defaults to it and to the Kaggle id.
- PR #2 merged; `v2-upgrade` and `main` fast-forwarded to `cee0ba3`.
- Pages: https://k-r-a-s-s.github.io/aus-govt-transparency/ (Datasette Lite loads the DB; checked).
- Kaggle: https://www.kaggle.com/datasets/kevrass/australian-parliament-registers-of-interests (public).
- Open questions accepted as is; SPEC signed off (DECISIONS "Gate G4").
- v1 Kaggle dataset (`kevrass/structured-register-of-australian-mps-disclosures`) marked
  superseded, pointing at v2. CT 104 (`claude-runner`) stopped (`pct start 104` to resume).
- **Left for Kevin:** announce (Reddit draft in the session); optionally add a LICENSE file for
  the code (the repo has none, so the code is all-rights-reserved by default).
- On the Mac, `disclosures_v2.db` was stale (2026-10-02 build); it is now a copy of the final DB.

Everything below is the pre-G4 handover, kept for history.


Read first: `SPEC.md` (plan, ADRs, ACs, gates), `DECISIONS.md` (dated decisions, incl. G1/G2/G3),
`README.md` (v2 overview, every command), `docs/v2/README.md` (layout), `docs/v2/extraction.md`,
`docs/v2/loading.md`, `docs/v2/scrape.md`, `docs/v2/senate_source.md`, `data/overrides/README.md`,
`eval/entities_report.md`, `eval/final_acceptance.md` (every SPEC §3 AC, with evidence),
`plans/2026-10-02-ralph-phases-3-5/PROGRESS.md` (one line per task).
This file only holds what those don't.

## Loop state (2026-10-03, branch `claude/ralph-proxmox`, PR #2 → `v2-upgrade`)
G3 approved (0 fixes), T1.6 dropped (accept self-only), T2.9 and V2 done. T5.6 rebuilt everything
from committed inputs and ran every SPEC §3 AC: **all pass** (`eval/final_acceptance.md`).
V5 (fresh verifier, SPEC §3 + final_acceptance only): **PASS, no findings**. Every offline AC
reproduced; export 50,936 rows = items, 33 cols = metadata = README dictionary; `site/` DB
identical to the live DB; Datasette Lite URL matches the remote owner/repo; 10/10 sampled items
(House 43/45/47/48, Senate 48) traced to their PDF page / Senate JSON. Not checkable offline:
AC-4.4 live re-scrape, AC-5.5 fresh install (done in T5.5), AC-5.6 Pages/Kaggle state.
The loop is **stopped**: only G4 (Kevin) is left.
OpenRouter credit left: **US$12.40 of 70** (US$57.60 used). Nothing left in the plan is paid.

## Waiting on Kevin
### 1. G4: publish
1. Choose the licence and Kaggle id, then regenerate: `.venv/bin/python -m disclosures export
   --site site --license NAME --kaggle-id USER/SLUG` (current values are placeholders; DECISIONS
   2026-10-03 T5.1). Commit `site/` and `exports/kaggle/README.md` + `dataset-metadata.json`.
2. Merge PR #2 into `v2-upgrade`, then `v2-upgrade` into `main`.
3. Enable GitHub Pages with source "GitHub Actions" (`.github/workflows/pages.yml` publishes `site/`);
   check the Datasette Lite link on the page loads the DB.
4. Upload `exports/kaggle/` (`kaggle datasets create -p exports/kaggle`), then announce.
5. Record G4 in DECISIONS.md and sign off SPEC.md (`Status:` line), see open questions.

### Next session: suggested route through G4 (written 2026-10-03)
State checked 2026-10-03: PR #2 (`claude/ralph-proxmox` → `v2-upgrade`) is open and mergeable, and
both merges fast-forward (`v2-upgrade` is 0 behind the PR, `main` is 0 ahead of `v2-upgrade`).
Pages is not enabled yet (API 404). The Kaggle CLI and `~/.kaggle/` don't exist on Kevin's Mac.
The Ralph loop is finished: work locally on the Mac and don't restart it.
1. **Licence: check the source terms before choosing.** The registers are APH publications.
   Read the copyright/licence terms on aph.gov.au (don't rely on memory). If they carry a
   restriction such as NonCommercial or NoDerivatives, the dataset can't be relicensed more
   loosely than that. Propose the licence to Kevin with the source quoted. CC BY 4.0 is the
   default if APH is CC BY. Ask Kevin for his Kaggle username; the slug can stay
   `australian-parliament-registers-of-interests`.
2. **Optional polish first (cheap, ~15 min):** fix the four cosmetic V5 notes below in one commit,
   then rerun `pytest`.
3. **Regenerate with the real values** (step 1 of G4 above), commit, push the branch, and rename PR
   #2 (its title still says "stopped at G3"). Merge PR #2, then fast-forward `main` to `v2-upgrade`.
   Confirm with Kevin before merging to `main`: it's public.
4. **Pages:** confirm with Kevin, then enable it with source = GitHub Actions
   (`gh api -X POST repos/k-r-a-s-s/aus-govt-transparency/pages -f build_type=workflow`). Watch the
   `pages.yml` run, then open the site and the Datasette Lite link.
5. **Kaggle:** Kevin installs the CLI and an API token (`pip install kaggle`; kaggle.com → Settings →
   API → `~/.kaggle/kaggle.json`). He runs the upload himself or approves it explicitly.
6. Record G4 in DECISIONS.md, set G4 done in the IMPLEMENTATION_PLAN, and decide with Kevin on
   SPEC sign-off and the three open questions below (accepting them as-is is a fine answer).

## Optional polish V5 noted (cosmetic, not fixed; fix before G4 if you like)
- Kaggle README / metadata say `entity_type` is empty for singletons, but 87 singleton-matched rows
  carry a type (entity also reachable via a typed alias). Wording only.
- `README.md` "v1 snapshot" says v1 scripts "are being removed"; they're gone (AC-5.4).
- `tests/test_cli.py::test_stubs_exit_2_with_message` is permanently skipped (no stubs left): dead test.
- `entity_asx_code` is also set for banks/airlines/media (CBA, QAN…); dictionary wording says "listed company".

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
