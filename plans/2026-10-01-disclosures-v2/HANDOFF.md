# Handover — Disclosures v2 (updated 2026-10-01, end of Phase 1c)

Read first: `SPEC.md` (plan, ADRs, ACs, gates), `DECISIONS.md` (dated decisions), `docs/v2/README.md`
(layout, commands), `eval/gold/README.md` (gold workflow, how Kevin reviews). This file only
holds what those don't.

## Where we are
- Phase 1 (contract, validator, scorer, gold set, v1 baseline) is built. Status at handover:
  `pytest -q`: 96 passed, 0 skipped. `validate eval/gold`: 12 valid. Self-score is 1.0.
  v1 baseline, section-ignored: P 0.856 / R 0.625 / F1 0.723. The `disclosures.db` sha matches AC-0.2.
- Phase 1c (consolidation: strict types, path-traversal check, normaliser fixes, date/precision
  check, gold conventions C1–C11) was finished but **has not had an independent verifier pass
  yet**. The Phase 1a/1b code passed one earlier.
- **Single next action:** run an independent verification of Phase 1c using the checks below.
  Then stop for **G1**: Kevin reviews `eval/gold/review.csv`. The Phase 2 bake-off must not start
  until every gold file has `reviewed_by: "kevin"` (AC-1.3). Phase 2a (extractor code,
  mock-tested) does not depend on gold review and may proceed in parallel.

Verification checks (from the repo root, using `.venv/bin/python`):
`-m pytest -q -rs`; `-m disclosures validate eval/gold`; `-m disclosures.schema --check`;
`-m disclosures score --pred eval/gold --gold eval/gold` (all 1.000);
`-m disclosures score --v1 disclosures.db --gold eval/gold --json eval/v1_baseline.json`;
`shasum -a 256 disclosures.db`.

## In-flight / deliberately out of scope
- `reviewed_by` is null on all 12 gold files (G1). `kevin_fix` notes are applied by hand, never
  by a command.
- C10 (items spanning a page break) was checked only where drafters noted it (kingm). Pages
  were not re-read exhaustively. Sections on scanned notices were checked against drafter
  notes plus a sample of rendered pages.
- `scrape, extract, load, entities, export, refresh` are still stubs that exit 2.
- The root `README.md` is still v1's. It gets rewritten in Phase 5; don't touch it before then.

## Decisions an agent might relitigate (full reasoning in DECISIONS.md)
- **`statement_date`** = the signed date on the bound-in "since dissolution or date of
  election" page, because it is the statement's only signature. The page-1 stamp is used only
  if that page is undated. This is not "always the stamp".
- **C1 splits** only where both the member and the spouse are named. gosling p8 "Family tickets"
  and plibersekt's spouse-row "(jointly)" items are intentionally NOT split.
- **C3:** sections are kept as printed even when wrong, with `medium` confidence. Every item on
  an unnumbered notice is `medium`.
- **C6:** one gift from several co-providers (kingm p12) stays one item.
- **`requirements.txt` is v2-only.** The v1 deps were dropped on purpose.
- **`/data/` was un-ignored in `.gitignore` on purpose:** v2 commits `data/overrides/`,
  `data/entities/` and `data/reference/` (SPEC ADR-6).

## Dead ends / corrections
- **The Phase 1c handoff pointed at gosling p8 for "for both Mr and Mrs".** That wording is not
  on that page; it is in prenticej, which was split.
- **Superseded drafter notes.** Older drafter text in `extraction_notes`, e.g. prenticej's
  "recorded as owner=self (one item)" or wilkie's "Joint items … recorded as owner=self", is
  superseded by the trailing `consolidation 2026-10-01: …` line. The JSON items follow the
  consolidation line.
- **Pydantic strict vs JSON Schema.** Pydantic strict rejects `2.0` for an int; JSON Schema
  accepts it. This is expected; the test only checks Pydantic for that case.
- **`review-sheet` overwrites the CSV, wiping Kevin's ticks.** Don't regenerate mid-review.
- **The pre-Phase-1c `eval/v1_baseline.json` covered only 1 PDF.** Its numbers are meaningless now.

## Open questions (who holds the ball)
- **G1 gold review: Kevin.** That includes whether he accepts the C4 `statement_date` reading,
  the plibersekt p10 date (the legible "7.5.11" was used over the 6 JUL 2011 stamp) and the
  non-splits above.
- **SPEC.md says "DRAFT, awaiting sign-off": Kevin.** The build proceeded on it anyway.
- **G2 extractor choice and the Gemini model id: later.** The placeholders are in DECISIONS.md.
