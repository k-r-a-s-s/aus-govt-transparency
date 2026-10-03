# Progress log (append one line per iteration; newest last)

`<UTC timestamp> | <task ID> | done/blocked/partial | spent US$x.xx | <one-line result or blocker>`

2026-10-02T11:30Z | (setup) | done | spent US$0.00 | Plan written in an interactive session after reviewing PR #1. Local baseline: 184 tests pass; load 768 docs / 303 members / 763 terms / 42,042 items; AC-2.8 hash f69d40da…; OpenRouter credit US$18.87.
2026-10-02T12:37Z | T0.1 | done | spent US$0.00 | skipif(root) on test_unwritable_target_exits_2; 198 tests pass (uid 1000)
2026-10-02T12:38Z | T0.2 | done | spent US$0.00 | Baseline: 198 tests pass; load 768 docs / 303 members / 763 terms / 42,042 items, exit 0, hard AC-2.7 all 0, AC-2.9 0 null party; AC-2.8 hash f69d40da…; credit US$18.87
2026-10-02T12:39Z | T1.1 | done | spent US$0.00 | scripts/find_attachment_gaps.py -> eval/attachment_gaps.csv, 29 candidates incl. all 12 D1 files; 2 tests; 200 pass
2026-10-02T12:42Z | T1.2a | done | spent US$0.00 | Split T1.2 by parliament (29>25). 43rd: 2 confirmed gaps (coultonm_43p, nevillep_43p), 6 ok, 1 not in PDF; eval/attachment_gaps.md started
2026-10-02T12:44Z | T1.2b | done | spent US$0.00 | 44th: 3 confirmed gaps (coultonm_44p, huntg_44p, pynec_44p), 3 ok, 2 not in PDF; eval/attachment_gaps.md ## 44th
2026-10-02T12:47Z | T1.2c | done | spent US$0.00 | 45th/47th: 2 confirmed gaps (coultonm_45p, odowdk45p); summary 7 not_itemised / 14 ok / 5 not in PDF / 3 false positives; re-extract list in eval/attachment_gaps.md
2026-10-02T12:49Z | T1.3 | done | spent US$0.00 | Prompt v1: C12 (attachments) + checklist 7; wording widened for fund-only refs, CV/adviser letters, totals; DECISIONS + docs updated; 200 pass
2026-10-02T12:56Z | T1.4 | done | spent US$0.47 | prompt v1 gold F1 0.984 (v0 0.987), ADR-4 PASS; plibersekt p8 unchanged; eval/bakeoff.md section added
2026-10-02T13:05Z | T1.5 | done | spent US$0.48 | 7 attachment files re-extracted with prompt v1: 315→525 items, all expected names present; validate 768/0; load 42,252 items, hard AC-2.7 0; AC-2.8 hash 465f1071…
2026-10-02T13:07Z | V1 | done | spent US$0.00 | Cold verifier: all hard checks pass; 4 small findings → md wording fixed, huntg change_type decided, nevillep spouse owners → T1.6; round 2 PASS
2026-10-02T13:09Z | T1.6 | blocked | spent US$0.05 | re-extract still self-only for 19 p8 holdings; file restored; Kevin: accept self-only or allow owner override?
2026-10-02T13:15Z | T2.1 | done | spent US$0.00 | entities command: normalise+generic+pluggable stages (curated live, asx/llm no-op)+singleton; real DB 11,165 entities, AC-3.3 0, deterministic; 212 tests pass
2026-10-02T13:19Z | T2.2 | done | spent US$0.00 | ASX snapshot 2,048 cos committed; asx stage (name, then ticker; section-1 scope; exclusions): 309 aliases / 4,370 items; 222 tests pass
2026-10-02T13:22Z | T2.3 | done | spent US$0.00 | entities --draft-candidates -> data/entities/alias_candidates.csv: 200 heads + token_set>=90 variants + ASX code; all AC-3.1 groups present; 225 tests pass
2026-10-02T13:28Z | T2.4 | done | spent US$0.00 | aliases.csv heads 1-100: 330 aliases -> 72 entities, 12,597 items curated, 15 flagged; AC-3.1 groups one entity each; ASX stage defers to curated codes; 229 tests pass
2026-10-02T13:33Z | T2.5 | done | spent US$0.00 | aliases.csv heads 101-200: 522 aliases -> 153 entities, 24 flagged; AC-3.2 coverage 100% printed + tested; 232 tests pass
2026-10-02T13:47Z | T2.6 | done | spent US$1.16 | long-tail LLM: 3,322 blocks cached (104 requests), offline llm 4,090 aliases / 14,128 items, AC-3.3 0; listed_company→ASX code rule; 245 tests pass
2026-10-02T13:53Z | T2.7 | done | spent US$0.00 | entities --report -> eval/entities_report.md; AC-3.3 0, AC-3.4 PASS; top 20 no dups after join-by-name (34 merges, 10,185 entities); 252 tests pass
2026-10-02T13:56Z | T2.8 | done | spent US$0.00 | entities --g3-review -> eval/entities_g3_review.csv 101 rows (top 50 + 24 flagged + 31 llm-medium); How to review G3 in report; HANDOFF: G3 waiting on Kevin; 253 tests pass
2026-10-02T14:00Z | T3.1 | done | spent US$0.00 | sources.py: URLs 43–48 (43rd → committee page, §0 URL 404s), UA+retry fetch, parser; fixtures 48th 151 rows / 46th 152 / 43rd 150; 266 tests pass
2026-10-02T14:04Z | T3.2 | done | spent US$0.00 | pdfs/manifest.csv 774 rows (= git ls-files); source_url matched 770/774 (99.5%), all member statements; AC-4.3 sha test; 273 tests pass
2026-10-02T14:13Z | T3.3a | done | spent US$0.00 | scrape house 48: 151 PDFs (147 api/4 static, 85 MB) + manifest rows; bytes stable (sha), 2nd run 0 new, 0 changed; docs/v2/scrape.md; 282 tests pass
2026-10-02T14:18Z | T3.3b | done | spent US$0.00 | disclosures.members: 151 48th pdf_members rows (118 returning, 33 new, 0 collisions); Katter/Wilson/French hand aliases; 286 tests pass
2026-10-02T14:24Z | T3.4 | done | spent US$0.00 | 48th party_terms 151 rows (wikipedia_48, pinned start-of-term rev), 0 unknown; seed --check fixed for 48th; cover test includes 48th parties; 288 tests pass
2026-10-02T14:52Z | T3.5 | done | spent US$4.03 | House 48th: 151/151 valid, 0 failed, 0 fallback; 48,956 items; AC-2.7/2.8/2.9 ok, AC-4.7 151; entities offline waits on T3.10
2026-10-02T15:05Z | T3.6 | done | spent US$0.00 | Senate 48th adapter: 76 payloads saved + manifest rows, 76/76 valid senate-json extractions (1,980 items); validate accepts .json sources; 297 tests pass
2026-10-02T15:13Z | T3.7 | done | spent US$0.00 | Senate pdf_members/party_terms 76 each (4 cross-chamber); load --source repeatable, members.chamber = latest term; AC-4.6 76, AC-2.9 0; senate_source.md; 301 pass
2026-10-02T15:20Z | T3.8 | done | spent US$0.00 | refresh --dry-run/gemini/workflow; AC-4.5 test (1 sha differs -> only that file); live dry-run: house 151 unchanged, senate 76 unchanged, 0 new/changed; 308 pass
2026-10-02T15:30Z | T3.9 | done | spent US$0.00 | Senate archives: API current-only (no parliament param); 44th/45th per-senator scans 62+75; tabled volumes 43rd–47th 40 PDFs/6,456 pp; follow-up splitter + ≈US$18–25; docs only (ADR-9)
2026-10-02T15:34Z | T3.10 | done | spent US$0.27 | entities full DB: 26 requests, 11,544 entities, AC-3.3 0, AC-3.4 PASS; top 50 all curated; G3 pack regenerated 114 rows; 313 pass
2026-10-02T15:42Z | V3 | done | spent US$0.00 | cold verify Phase 4: PASS, no findings; rebuild deterministic, manifest/refresh/senate mapping/validate all hold; 313 pass
2026-10-02T15:47Z | T5.1 | done | spent US$0.00 | export: 50,936 rows = items, 33 cols, Kaggle README (dictionary/method/limitations) + dataset-metadata.json; source_url via manifest; 319 pass
2026-10-02T15:50Z | T5.2 | done | spent US$0.00 | export --site: site/index.html (coverage, cite, Datasette Lite link) + site/disclosures_v2.db (31.9 MB copy); pages.yml valid; local http.server check ok; 322 pass
2026-10-02T15:52Z | T5.3 | done | spent US$0.00 | README.md rewritten for v2 (what/coverage/commands/refresh/dictionary/limitations/v1 snapshot); AC-5.3 grep ok; 322 pass
2026-10-02T15:54Z | T5.4 | done | spent US$0.00 | removed src/, examples/, test_output.json, setup_pipeline.sh, seed script, v1 docs; overrides README = CSVs source of truth; 'from src.' grep empty; 322 pass
2026-10-02T15:56Z | T5.5 | done | spent US$0.00 | fresh venv: install + pip check ok, freeze == pins, 322 pass/1 skip, all modules import; no requirement changes
2026-10-02T22:30Z | T2.9 | done | spent US$0.00 | G3: 0 fixes to apply; load+entities --offline 11,544 entities, AC-3.3 0, coverage 97.7%, report unchanged; G3 in DECISIONS; 322 pass
2026-10-02T22:41Z | V2 | done | spent US$0.00 | cold verify Phase 3: ACs pass, deterministic; fixed reused tickers (ore/map/cim/agi/apt) + comm bank via 9 curated rows, G3 header, known limitations; 11,542 entities; 322 pass
2026-10-02T22:46Z | T5.6 | done | spent US$0.00 | final rebuild (995 files, 50,936 items, 11,542 entities) + export/site; every AC-0..AC-5 passes -> eval/final_acceptance.md; HANDOFF/DECISIONS/SPEC progress updated
2026-10-02T22:55Z | V5 | done | spent US$0.00 | final cold verify: PASS, no findings; 10/10 sampled items traced to source; export/site/dictionary consistent; 322 pass
2026-10-03T00:40Z | G4 | done | spent US$0.00 | Mac session: licence CC BY-NC 4.0 (APH is CC BY-NC-ND), V5 polish, PR #2 merged, main ff to cee0ba3, Pages live (Datasette Lite loads, 50,936 items), Kaggle kevrass/australian-parliament-registers-of-interests public; 322 pass
