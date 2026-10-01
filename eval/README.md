# eval/

| Path | What |
|---|---|
| `pdf_stats.csv` | per-PDF stats for every `pdfs/*/*.pdf` (pages, no-text-layer pages, heuristics, sha256). Rebuild: `python -m disclosures.gold stats --force` |
| `gold/selection.json` | the seeded, stratified gold PDF selection (ADR-3). Rebuild: `python -m disclosures.gold select --seed <seed> --n <12-15>` |
| `gold/<stem>.json` | gold extractions, one per selected PDF, in the ADR-2 contract (`source_id: "gold"`). Drafted in Phase 1b, reviewed by Kevin (gate G1) |
| `gold/review.csv` | flat review sheet generated from the gold JSON |
| `v1_baseline.json` | v1 DB scored section-ignored against the gold set: `python -m disclosures score --v1 disclosures.db --gold eval/gold --json eval/v1_baseline.json` |

Scoring: `python -m disclosures score --pred extractions/<source_id> --gold eval/gold --json eval/<source_id>.json`.
Metrics with a zero denominator (e.g. no gold items yet) are reported as `null`.
