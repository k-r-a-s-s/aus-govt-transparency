# eval/

| Path | What |
|---|---|
| `pdf_stats.csv` | per-PDF stats for every `pdfs/*/*.pdf` (pages, no-text-layer pages, heuristics, sha256). Rebuild: `python -m disclosures.gold stats --force` |
| `gold/selection.json` | the seeded, stratified gold PDF selection (ADR-3). Rebuild: `python -m disclosures.gold select --seed <seed> --n <12-15>` |
| `gold/<stem>.json` | gold extractions, one per selected PDF, in the ADR-2 contract (`source_id: "gold"`). Drafted in Phase 1b, reviewed by Kevin (gate G1) |
| `gold/review.csv` | flat review sheet generated from the gold JSON |
| `workflow-claude.json` | workflow-claude arm scored against gold (2026-10-02) |
| `bakeoff.md` | Phase 2b bake-off report (AC-2.4): all arms + v1, ADR-4 bar, ADR-5 decision; backfill actuals |
| `extraction_failures.md` | AC-2.6: backfill outcome per PDF class (768 valid + 6 excluded + 0 failed = 774), fallback usage |
| `backfill-gemini.log` | the backfill's console log (three passes, 2026-10-02; force-added, `*.log` is otherwise ignored) |
| `v1_baseline.json` | v1 DB scored section-ignored against the gold set: `python -m disclosures score --v1 disclosures.db --gold eval/gold --json eval/v1_baseline.json` |

Scoring: `python -m disclosures score --pred extractions/<source_id> --gold eval/gold --json eval/<source_id>.json`.
Metrics with a zero denominator (e.g. no gold items yet) are reported as `null`.
