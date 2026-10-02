# Extraction instructions — Register of Members' Interests (v1, schema 2.0)

You are transcribing ONE Australian parliamentary "Statement of Registrable Interests" PDF
(including any later "Notification of Alteration of Interests" pages bound into it) into a
single JSON object. The output MUST validate against `schema/extraction.schema.json`.
Output JSON only — no prose, no markdown fences.

## Work page by page
- Read EVERY page, 1 to the last. `pages_covered` must list every page number you read,
  sorted, with no gaps (`[1, 2, …, page_count]`). Pages with nothing to record still count.
- Many pages are scanned images (no text layer) and handwriting is common. Read the image.
- `page` on each item is the 1-based page number of the SOURCE PDF the item appears on
  (not a page number printed on the form).

## Document-level fields
- `schema_version`: `"2.0"`. `source_id`, `model`, `extracted_at`, `pdf_path`, `pdf_sha256`,
  `page_count`, `chamber`, `parliament`: supplied by the caller — copy them exactly, never guess.
- `member_name_as_printed`: the member's name as written on the form.
- `electorate_or_state`: the electorate (House) or state (Senate) as written; `""` if absent.
- `statement_date`: the date the initial statement was signed/lodged (`YYYY-MM-DD`) or `null`.
- `extraction_notes`: short free text about problems (illegible pages, odd layout); may be `""`.
- Do not add any field that is not in the schema.

## The 14 sections (use the official number in `section`)
1. Shareholdings (in public and private companies)
2. Family and business trusts and nominee companies —
   `subsection` `"2(i)"` = beneficial interest; `"2(ii)"` = trustee
3. Real estate — put the place in `location` and the stated purpose in `purpose`
4. Registered directorships of companies
5. Partnerships
6. Liabilities — nature of the liability and the creditor (creditor → `entity_name`)
7. Bonds, debentures and like investments
8. Saving or investment accounts (bank/institution → `entity_name`)
9. The nature of any other assets (excluding household and personal effects) over $7,500
10. The nature of any other substantial sources of income
11. Gifts
12. Any sponsored travel or hospitality received over $300
13. Membership of any organisation where a conflict of interest could arise
14. Any other interests where a conflict of interest could arise

Use `subsection` only where the form itself sub-divides a section (e.g. `"2(i)"`, `"2(ii)"`);
otherwise `null`. If a later alteration notice names its section in words, map it to the number.

## Owner
Each section's table has rows for **Self**, **Spouse/partner** and **Dependent children**.
`owner` = `"self"`, `"spouse"` or `"dependent_child"` according to the row the entry is in.
Use `"unknown"` only when the row genuinely cannot be determined.

## One item per interest
- A row/cell that says "Not Applicable", "N/A", "Nil", "None", "-", or is blank → NO item.
- A cell listing several companies/accounts/properties → ONE item PER company/account/property.
- `entity_name`: the company, bank, organisation, person or trust named, as printed
  (keep "Pty Ltd" etc.). `null` if the item names no entity (e.g. "Residential home").
- `description`: the text of THIS item only (verbatim-ish: fix obvious OCR noise, do not
  paraphrase, do not copy neighbouring items). Never empty.
- `location` / `purpose`: section 3 only; otherwise `null`.

## Initial statement vs alteration notices
- Items from the initial statement: `is_alteration=false`, `change_type="initial"`,
  `lodged_date` = `statement_date` (see C4), `null` only if no date or stamp is legible.
- Later pages headed e.g. "Notification of Alteration of Interests" (or a letter notifying a
  change): every item on them has `is_alteration=true`; `change_type` from the wording:
  acquired / new / added / commenced / received → `"added"`;
  disposed / sold / ceased / closed / resigned / removed / deleted → `"removed"`;
  changed / varied / increased / decreased / updated → `"varied"`; unclear → `"unknown"`.
  `lodged_date` = the date of that notice (date received/signed), not the statement's date.
- Gifts, travel or hospitality notified by an alteration notice are still `"added"` items.

## Dates
- Format `YYYY-MM-DD`, real calendar dates only.
- Full date → `date_precision="day"`. Month and year only → day `01`, `date_precision="month"`.
  Year only → `MM-DD` = `01-01`, `date_precision="year"`. No date → `lodged_date=null`,
  `date_precision="unknown"` — and `"unknown"` ONLY then (the validator rejects other pairings).
- Australian forms write dates day-first: `3/4/2017` is 3 April 2017.

## Confidence
- `"high"`: clearly legible and unambiguous. `"medium"`: legible but the section/owner/row
  assignment or the reading needed judgement. `"low"`: illegible or partly illegible — give
  your best reading in `description` and set `"low"`. Never drop an item because it is hard
  to read.

## Item object (all keys required; use `null` where allowed)
```
{"section": 1, "subsection": null, "owner": "self", "entity_name": "BHP Group Limited",
 "description": "BHP Group Limited", "location": null, "purpose": null,
 "is_alteration": false, "change_type": "initial", "lodged_date": "2019-07-01",
 "date_precision": "day", "page": 2, "confidence": "high"}
```

## Conventions for ambiguous cases
- **C1 Joint self+spouse.** An entry that explicitly names both the member and the
  spouse/partner as owner or recipient ("myself and partner", "Self and Spouse", "joint with
  spouse/partner", "together with spouse/partner", "for Mr and Mrs X", "for Mrs King and
  husband") → TWO items, `owner="self"` and `owner="spouse"`, same description/page/dates,
  `confidence="medium"` unless the form itself labels the entry "Self and partner".
- **C2 Covering letters.** A letter that only restates the changes on the form after it
  produces no items; record each change once, on the form page.
- **C3 Section on alteration notices.** A printed section number (e.g. "11. Gifts", or the
  section named in words) is used as printed, `confidence="medium"` if the content fits
  another section better. No section number (free-text "Item" column, letters, running
  counts, dates) → assign by meaning, `confidence="medium"`: lounge memberships,
  subscriptions, physical gifts → 11; tickets, flights, upgrades, accommodation,
  hospitality → 12; organisational memberships/patronages → 13; ownership/asset/liability
  changes → the matching section 1–9.
- **C4 Dates.** `lodged_date` = the signed/handwritten date of the notice (possibly on its
  following signature page) if legible, else the Registry "received"/"PROCESSED" stamp.
  `statement_date` likewise: the statement's signed date (its only signature is often on the
  bound-in "since dissolution or date of election" page) if present, else the page-1 stamp.
  Items keep the `page` they appear on. Date errors inside item text stay verbatim in
  `description`; `lodged_date` is still the notice's date.
- **C5** The "alterations since dissolution/date of election" page bound into the initial
  statement is an alteration notice: `is_alteration=true`, `change_type="added"` (or as
  worded), `lodged_date` = that page's date.
- **C6 One item per entity.** "Westpac / Amex", multi-company or multi-account cells → one
  item each. (One gift jointly provided by several bodies stays one item.)
- **C7 Deletions.** A deletion naming a section, or "all spouse/partner details for section
  N" → one `removed` item per named section, `entity_name=null`, description as printed,
  medium. A deletion row with no section and no details → no item (say so in
  `extraction_notes`). "Changed from X to Y" under ADDITION → `varied`. A re-declaration
  that only adds detail (value, purpose) to an earlier item → `varied`, medium.
- **C8 Owner edge cases.** Gifts received by a staff member → `owner="unknown"`. "As above" /
  "Same as above" in a spouse row → a spouse copy of the referenced self item(s), medium.
- **C9 Quasi-nil text** ("None of which I am aware", "No significant", "Not applicable – see
  above") → no item. The member's own parliamentary salary under section 10 is kept.
- **C10** An item spanning a page break takes the page where it starts.
- **C11** A second statement cover page (no interests) produces no items.
- **C12 Attachments.** When a section's cell says "see attached", "see Attachment A", "as per
  attached list/schedule", "list attached", or similar, and the attachment is bound into this
  PDF (a typed list, a schedule, a broker or portfolio statement, a share-registry printout, a
  financial adviser's letter or table, a membership list, a CV): record ONE item per
  holding/account/entity listed on the attachment. The same applies when the cell only names a
  fund or portfolio and a bound-in page lists that fund's holdings. Each item takes the
  referencing section, subsection and owner, `page` = the attachment page where that line
  appears, and the dates and change type of the page that references it (an initial
  statement → `initial`; an alteration notice → that notice's change type and date). The
  "see attached" line itself produces no item, unless it also names an interest of its own
  (e.g. "XYZ Self-Managed Super Fund – see attached" → keep the fund as an item as well).
  An attachment is content that continues the referencing item; the next statement or
  notification form is not an attachment. Totals and subtotal rows produce no item, and nor do
  entries the attachment shows as already ended (e.g. a CV role "1988–2012"). If the
  attachment is not in this PDF, keep the referencing line as one item (description as
  printed, `confidence="medium"`) and say so in `extraction_notes`.

## Checklist before you answer
1. `pages_covered` == every page 1..page_count.
2. No item for nil / "Not Applicable" rows.
3. One item per company in multi-company cells.
4. Every item has the correct `page`, `section`, `owner`.
5. Alteration-notice items have `is_alteration=true` and a `change_type` other than `"initial"`.
6. Only schema fields; valid JSON.
7. Every 'see attached' reference whose attachment is in the PDF has been itemised from the attachment.
