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

## 44th

| file | verdict | evidence |
|---|---|---|
| broadbentr_44p | itemised_ok | p8 "ATTACHMENT" (super fund holds CBA, Telstra) has its 2 items on p8; same layout as the 43rd. |
| coultonm_44p | **attachment_not_itemised** | p2 s1 self+spouse "MM & RA Coulton Self-Managed Super Fund (see attached list)"; p8 is the fund's portfolio (2 cash, 5 managed funds, 9 listed shares, 1 REIT). 0 items on p8, though the notes name the page. |
| fletcher_44p | itemised_ok | p20 alteration "See Attachment 1/2" for s12/s13; Attachment 1 (p21, 16 Qantas/Virgin upgrades) and Attachment 2 (p22, 10 memberships) are itemised. The p20 placeholder items are left over; C12 would drop them. |
| grayg_44p | attachment_not_in_pdf | p32/p33 s11 wine gifts "details attached": the next pages are further alteration forms, so the details sheets aren't in the PDF. Each gift is recorded. |
| huntg_44p | **attachment_not_itemised** | p10 alteration (19 Mar 2014) "Revised membership list – see attached"; p11 is the list (4 memberships, 8 community groups, 3 sponsorships). 0 items on p11. The "membership resignations – see attached" list isn't in the PDF. |
| perrettg_44p | itemised_ok | p11 gift "see attached ticket stubs"; p10 is a photo of the two State of Origin tickets. The gift is recorded, and the stubs add no interest. |
| pynec_44p | **attachment_not_itemised** | p6 s13 self "LIST ATTACHED"; p8–10 is a Sept 2013 CV whose "Community and other activities" list (≈ 50 entries) gives the memberships. 0 items on p8–10. |
| turnbullm_44p | attachment_not_in_pdf | p33/p37 s11 gifts "surrendered … as per the attached Declaration": the following pages (p34, p38) are other alteration forms. Gifts are recorded. |

Re-extract (44th): `pdfs/44/coultonm_44p.pdf`, `pdfs/44/huntg_44p.pdf`, `pdfs/44/pynec_44p.pdf`.

Odd: `pynec_44p`'s "attachment" is a full CV. Most entries are past roles with end dates
(e.g. "Royal Adelaide Golf Club, 1988–2012"). Under C12 it should yield one s13 item per
organisation listed, but T1.5 should only expect the open-ended ones (the `expected` names are
all current). `coultonm` misses the same super-fund page in both the 43rd and 44th, so the
45th copy probably has the same gap. `huntg_45p` is a candidate too (T1.2c).
