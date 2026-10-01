# Gold set

1. `selection.json` lists the PDFs (seeded; strata recorded per PDF). The spouse/dependent and
   alteration-heavy strata are heuristic at selection time and confirmed from gold content by
   `tests/test_gold_selection.py`; if short, extend the selection towards 15 PDFs.
2. A drafter transcribes each selected PDF page by page into `<stem>.json`, following
   `disclosures/prompts/extract.md` (including its "Conventions for ambiguous cases" C1–C11),
   with `source_id: "gold"`, `reviewed_by: null`.
   Check with `python -m disclosures validate eval/gold`.
3. `python -m disclosures.gold review-sheet` writes `review.csv` (one row per item, columns
   `stem, page, section, subsection, owner, entity_name, description, change_type,
   lodged_date, confidence, kevin_ok, kevin_fix`; the last two blank). Regenerating it
   overwrites any ticks, so copy the sheet first if you have started reviewing.
4. Kevin reviews: put anything (e.g. `y`) in `kevin_ok` for correct rows; describe corrections
   in `kevin_fix`. **`kevin_fix` edits are not applied by any command** — an agent or Kevin
   applies them to the JSON by hand, then ticks `kevin_ok` on those rows (see "How to review").
5. `python -m disclosures.gold apply-review` sets `reviewed_by: "kevin"` and `reviewed_at: <today>`
   on every gold file whose rows ALL have `kevin_ok` filled, and prints the stems still
   unreviewed. A gold file with zero items has no rows and must be marked reviewed by hand.

## How to review (Kevin, gate G1)

Open `eval/gold/review.csv` in a spreadsheet and keep the PDF open (`pdfs/<parliament>/<stem>.pdf`;
`page` is the PDF page, not the number printed on the form).

1. **Medium/low confidence rows first.** Sort or filter on `confidence` (`low`, then `medium`).
   These are the judgement calls: joint self+spouse splits (C1), sections assigned by meaning or
   printed under an odd section (C3), staff gifts (C8), re-declarations (`varied`, C7). The rules
   are listed in `disclosures/prompts/extract.md`; per-file consolidation notes are in each JSON's
   `extraction_notes`; interpretations are in `plans/2026-10-01-disclosures-v2/DECISIONS.md`.
2. **Then one PDF end to end.** Pick one (e.g. `wilkie_46p`, 14 pages) and check every page: is an
   item missing, invented, on the wrong page, or under the wrong owner/section? A missing item has
   no row, so write it in `kevin_fix` on a neighbouring row ("missing: p5 s13 self Rotary").
3. Skim the remaining high-confidence rows per PDF.

Columns to fill:
- `kevin_ok`: any mark (e.g. `y`) means "this row is correct as is". Leave it blank on rows that
  need a fix.
- `kevin_fix`: free text describing the correction ("section 12", "owner spouse", "date 2014-03-21",
  "delete: duplicate", "missing: ..."). The agent applying it to the JSON then ticks `kevin_ok` on
  that row in the same sheet (do not regenerate the sheet mid-review: that clears the ticks).

When done:

```sh
python -m disclosures.gold apply-review   # marks every stem whose rows ALL have kevin_ok
```

It prints which stems are reviewed and which are not. `kevin_fix` notes are **not** applied
automatically: an agent applies them to the JSON, re-runs `python -m disclosures validate eval/gold`,
and keeps `reviewed_by` as set. Gate G1 passes when all 12 files have `reviewed_by: "kevin"`.
