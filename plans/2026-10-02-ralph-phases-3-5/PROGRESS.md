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
