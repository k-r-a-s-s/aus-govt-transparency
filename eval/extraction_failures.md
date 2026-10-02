# Extraction failures — gemini-api backfill (AC-2.6)

Backfill of every tracked House PDF (parliaments 43–47) with the G2 configuration:
`google/gemini-3.8-flash` on OpenRouter `google-ai-studio/flex`, `--fallback-model
anthropic/claude-sonnet-5.5`, `--ignore-providers azure`, 8 workers. Run 2026-10-02 from a
Claude Code cloud session (`eval/backfill-gemini.log`, three passes).

| Outcome | PDFs |
|---|---|
| valid extraction in `extractions/gemini-api/house/` (`validate`: 768 valid, 0 invalid) | 768 |
| excluded: not a statement | 6 |
| failed | 0 |
| **total tracked PDFs** | **774** |

## Failed PDFs

None. Every PDF that failed in pass 1 or 2 succeeded on re-run (the command skips valid
existing output, so re-running is idempotent):

- 293 PDFs in pass 1 failed with HTTP 402 (OpenRouter credit exhausted mid-run); re-run after a
  top-up.
- 5 PDFs in pass 1 (`dathy_43p`, `abbotta_44p`, `hayesc_44p`, `palmerc_44p`, `turnbullm_44p`)
  failed because the Sonnet fallback chunk was routed to OpenRouter's Azure endpoint, which
  returned HTTP 400 `no_content_length_header`. Root cause: only the Azure endpoints list the
  `temperature` parameter, so `require_parameters` pinned every Sonnet call to Azure. Fixed in
  the transport (`--ignore-providers`, and no `temperature` for `anthropic/*`), see
  `docs/v2/extraction.md`.
- 10 PDFs in pass 2 failed with HTTP 404 "No endpoints found" (the interim fix ignored Azure
  before the temperature change landed); pass 3 cleared them.

## Excluded: not a statement

These six files are tracked under `pdfs/` but are not a member's statement. `eval/pdf_stats.csv`
has `is_statement=0` and `data/overrides/pdf_members.csv` has `source=non_member` for each.

| PDF | What it is |
|---|---|
| `pdfs/44/interestsr_44p.pdf` | House resolution text on the registration of interests (2 pages) |
| `pdfs/45/interestsr_45p.pdf` | same |
| `pdfs/46/interestsr_46p.pdf` | same |
| `pdfs/47/interestsr_47p.pdf` | same |
| `pdfs/46/explanatory_notes___booklet_1.pdf` | the form's explanatory notes booklet |
| `pdfs/47/explanatory_notes___booklet_1.pdf` | same |

## Fallback usage (for the record, not failures)

108 of 768 files (14%) have `model = google/gemini-3.8-flash+anthropic/claude-sonnet-5.5`: at
least one chunk was refused by Gemini (`finish_reason ERROR`, native `RECITATION`) and
transcribed by Sonnet 5.5 instead. By parliament: 43rd 37/150, 44th 29/152, 45th 35/158, 46th
3/153, 47th 4/155. The scanned early parliaments trip the block far more often than the gold
set suggested (1 of 12 PDFs). `extraction_notes` names the pages in each affected file.
