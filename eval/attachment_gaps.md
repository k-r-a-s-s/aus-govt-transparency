# Attachment gaps: page-checked verdicts (T1.2, SPEC-DELTA D1)

Candidates come from `scripts/find_attachment_gaps.py` → `eval/attachment_gaps.csv` (29 rows).
Each file was checked by looking at the page that points to the attachment and at the attachment
pages. Verdicts: `attachment_not_itemised` (attachment bound in, holdings missing),
`itemised_ok`, `attachment_not_in_pdf`, `other: <what>`. The `expected` column lists names that
T1.5 checks for after the re-extraction.

<!-- Summary (counts across all 29 + full re-extract list) is written by T1.2c. -->

## 43rd

| file | verdict | evidence |
|---|---|---|
| broadbentr_43p | itemised_ok | p8 "ATTACHMENT" (super fund holds CBA, Telstra; company is trustee): 3 items on p8. v1 unmatched names are OCR noise. |
| clarej_43p | itemised_ok | p8–10 are ministerial letters to the PM about a possible conflict (brother's employer). They hold no holdings list, so the s14 "see attached correspondence" item is all there is to record. |
| coultonm_43p | **attachment_not_itemised** | p2 s1 self+spouse "MM and RA Coulton Self-managed Super Fund (see attached list)"; p8 is the fund's portfolio (2 cash accounts, 5 managed funds, 9 listed shares, 1 REIT). 0 items on p8. |
| fletcherp_43p | itemised_ok | Attachments 1/1A on p8–16 itemised (22 items on p8, Roseville contract on p9). The p17 "Attachment 1" rows are alteration items. |
| nevillep_43p | **attachment_not_itemised** | p5 s9 "Neville Superannuation Fund"; p8 is a letter from Ulton (the financial adviser) listing 19 fund investments. 0 items on p8. |
| ripollb_43p | itemised_ok | p20 alteration says "see attached form"; p21 (the form) has 17 s13 membership items. v1 unmatched names are OCR noise of handwriting. |
| slipperp_43p | itemised_ok | p8 annexure (items 3, 6, 7, 9) has 5 items; the "attached letter" on p9 has 16 Lyniter shareholdings. |
| snowdonw_43p | itemised_ok | p8 duplicates the p6–7 membership list (recorded once); v1 unmatched (Freemantlo, APL, Shrine Rememberance, AEV) are OCR variants of gift items present on p9. |
| somlyaya_43p | attachment_not_in_pdf | p9 gift "Accommodation at Sofitel Melbourne, compliments of Puremedic (see attached tax invoice)": the invoice isn't in the PDF (10 pages, p10 is an Austar alteration). Nothing is missing, because the gift item is recorded. |

Re-extract (43rd): `pdfs/43/coultonm_43p.pdf`, `pdfs/43/nevillep_43p.pdf`.

Odd: both confirmed gaps are super-fund portfolios on a separate page headed only by the fund's
name (Coulton) or as an adviser's letter (Neville), with no "Attachment" label or section number. The ones that were itemised (broadbentr, slipperp) have an explicit
"ATTACHMENT"/"ANNEXURE" heading or a covering line naming the item.
