# Attachment gaps: page-checked verdicts (T1.2, SPEC-DELTA D1)

Candidates come from `scripts/find_attachment_gaps.py` → `eval/attachment_gaps.csv` (29 rows).
Each file was checked by looking at the page that points to the attachment and at the attachment
pages. Verdicts: `attachment_not_itemised` (attachment bound in, holdings missing),
`itemised_ok`, `attachment_not_in_pdf`, `other: <what>`. The `expected` column lists names that
T1.5 checks for after the re-extraction.

## Summary (all 29 candidates)

| verdict | count |
|---|---|
| attachment_not_itemised | 7 |
| itemised_ok | 14 |
| attachment_not_in_pdf | 5 |
| other: false positive (wording only, no attachment) | 3 |

Re-extract (7 files, for T1.5):

- `pdfs/43/coultonm_43p.pdf`
- `pdfs/43/nevillep_43p.pdf`
- `pdfs/44/coultonm_44p.pdf`
- `pdfs/44/huntg_44p.pdf`
- `pdfs/44/pynec_44p.pdf`
- `pdfs/45/coultonm_45p.pdf`
- `pdfs/45/odowdk45p.pdf`

Every confirmed gap is a list on its own page: a super-fund or broker portfolio (coultonm ×3,
nevillep, odowdk), a membership list (huntg_44p) or a CV (pynec_44p). The page that refers to it
says "see attached list", "Attachment 'A'" or just names the fund. In every case the
extraction notes mention the attachment page, yet 0 items come from it.

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

## 45th and 47th

| file | verdict | evidence |
|---|---|---|
| broadbentr_45p | itemised_ok | p8 "ATTACHMENT" (super fund holds CBA, Telstra) has its 3 items on p8; same layout as the 43rd/44th. |
| coultonm_45p | **attachment_not_itemised** | p2 s1 "(see attached list)"; p8 is the "MM & RA Coulton Super Fund Investment Summary Report" (2 cash, 4 managed funds, 13 listed shares, 1 listed trust). 0 items on p8, though the notes name the page. This is the third parliament with the same gap. |
| freelanderm_45p | itemised_ok | p8–9 Morgan Stanley printouts for the Pebema super fund and the spouse: 22 + 16 items. The p14 alteration's "updated list (see attached)" is the last page, so that list isn't in the PDF. v1 unmatched names are OCR noise. |
| huntg_45p | itemised_ok | p8 s13 attachment (memberships and community groups) has 15 items. v1 unmatched names are OCR noise. |
| odowdk45p | **attachment_not_itemised** | p5 s7 "SEE ATTACHMENT 'A'": p9 lists the BT portfolio (10 Australian shares, 4 international funds, 3 property trusts), 0 items. p10 alteration "Please see Attachment": p11 is a BT "My Investment Recommendation" table (≈ 23 holdings), 0 items. |
| pynec_45p | attachment_not_in_pdf | p6 and p21 s13 "LIST ATTACHED": the pages with no items (p7, p8, p23, p25, p27) are a blank alteration form and covering letters. The CV-style list from the 44th isn't bound in. |
| roberts_45p | itemised_ok | Attachment 1 on p8 (36 items), updated Attachment 1 on p19–20 and the later attachments (p30–31, p39–41) are itemised. v1 unmatched names are Greek-letter OCR noise. |
| smitht_45p | attachment_not_in_pdf | p6 s12 self+spouse "SEE ATTACHMENT": p7 is blank and p8 is a post-election alteration form (AFL tickets), so there's no attachment. The model filed the p8 item as the attachment's content. That's harmless, but it isn't one. |
| thistlethwaitem_45p | itemised_ok | p7 "See attached": p8–12 are one-gift alteration forms, one item each. v1 unmatched names are OCR variants of the s13 clubs on p6 (Malabar RSL, Souths Juniors, Coogee Legion). |
| wallacea_45p | other: false positive | The detector matched "daily schedule facilitation" in a p8 s12 sponsored-travel item. v1 unmatched names are OCR noise of the SMSF name. |
| bowen_47p | other: false positive | p3 s6 "Visa Card attached to bank account": no attachment. |
| gorman_47p | other: false positive | p9 s10 "performance rights attached to her name": no attachment. |

Re-extract (45th/47th): `pdfs/45/coultonm_45p.pdf`, `pdfs/45/odowdk45p.pdf`.

Odd: odowdk45p has two attachments, both missed. One is a plain holdings page and the other a
financial adviser's recommendation table, cut off on the right in the scan. For the p11 table,
C12 should itemise the holdings named, not the "Total" rows. `smitht_45p` shows the model will
sometimes treat the next form as the attachment. C12's wording should say an attachment is
content that continues the referencing item, not the next notification form.

## Re-extracted with prompt v1 (T1.5, 2026-10-02)

The 7 files above re-run with `--force` on the G2 config, prompt v1 (C12). US$0.48 in total.
odowdk45p needed the Sonnet 5.5 fallback for p1–18 (RECITATION).

| file | items before (v0) | items after (v1) | expected names found | where they land |
|---|---|---|---|---|
| coultonm_43p | 29 | 63 | 5/5 | p8, s1, self + spouse |
| nevillep_43p | 66 | 85 | 5/5 | p8, s9, self |
| coultonm_44p | 25 | 59 | 5/5 | p8, s1, self + spouse |
| huntg_44p | 94 | 108 | 5/5 | p8 and p11, s13, self |
| pynec_44p | 47 | 82 | 5/5 | p9, s13, self |
| coultonm_45p | 24 | 60 | 5/5 | p8, s1, self + spouse |
| odowdk45p | 30 | 68 | 5/5 | p9 (Attachment A, s7 initial) and p11 (s7/s8 added) |

pynec_44p: the `expected` column says "Centro Diddatico", a typo made when I wrote the column. The
PDF and the new extraction both say "Centro Didattico". odowdk45p puts "BT Wrap Cash Account" under
s8 (bank accounts), not s7 as the referencing line does. That's a sensible reading of a cash
account, so I left it.
