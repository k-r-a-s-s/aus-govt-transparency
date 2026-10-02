# data/overrides — member identity and party tables (ADR-7)

Hand-curated tables the loader (`python -m disclosures load`, see `docs/v2/loading.md`) joins
against. They carry v1's curated assets forward (v1 code was deleted in Phase 5).

**These CSVs are the source of truth and are edited by hand** (or appended by
`python -m disclosures.members` for new parliaments/chambers). v1's code was removed in Phase 5
(T5.4), so they can no longer be regenerated from v1.

They were seeded on 2026-10-02 by `scripts/seed_v2_overrides.py` (removed in T5.4; it is in git
history before that commit and needs v1's `src/cleaning/*.py` checked out to run), which read v1
read-only: `disclosures.db` (`mps`, and `disclosures.pdf_filename` -> `mp_id`), the dict
literals in `src/cleaning/*.py` (parsed, not imported) and `output/all_mps_*.csv` (v1's
Wikipedia scrapes). Its `MANUAL_*` tables held the hand fixes. It only derived v1's parliaments
(43rd–47th): rows for the 48th on (`pdf_members`/`party_terms`/`unknown_party` rows of
parliament ≥ 48 and `member_aliases` rows with `source=aph_*`) were written by
`python -m disclosures.members`.

`member_id` is the slug of the canonical full name: lower case, ASCII-folded, each run of
non-alphanumerics becomes `_` (`Clare O'Neil` -> `clare_o_neil`). The canonical full name is
the member's Wikipedia name as v1 scraped it (`Chris Bowen`, `Bert van Manen`). All 303
people who own a tracked PDF have one.

| File | Columns | What / provenance |
|---|---|---|
| `pdf_members.csv` | `pdf_path, member_id, canonical_full_name, electorate_or_state, source` | One row per tracked PDF (925), sorted by path. This is the main way a document gets its member. `source=v1`: from v1 `disclosures.pdf_filename` -> `mps` (759). `source=stem`: v1 loaded no rows for the PDF, so the member comes from the filename stem and the first page (9). `source=non_member`: not a member's statement, `member_id` is empty (6: `interestsr_4Np.pdf` is the House resolution text, `explanatory_notes___booklet_1.pdf` is the form's notes). `source=aph_48`: 48th PDFs from `python -m disclosures.members --parliament 48` (151: 118 returning, 33 new); the electorate is the listing's. `source=aph_senate_48`: one row per Senate 48th source document (`pdfs/senate/48/*_48s.json`, 76: 4 ex-MPs who keep their House `member_id`, 72 new) from `python -m disclosures.members --chamber senate --parliament 48`; `electorate_or_state` is the state. `electorate_or_state` is v1's electorate for that record. It is v1's most-recent seat name for the member, so renamed seats carry the later name even on older PDFs (Wilkie's 43rd–45th PDFs print Denison, the column says Clark). The loader prefers the extraction's printed electorate and only falls back to this column. |
| `member_aliases.csv` | `name_variant, electorate_or_state, member_id, canonical_full_name, source` | Name variants -> member. It holds every v1 `mps.full_name` and `mps.mp_id`, the v1 manual merge overrides (`merge_duplicate_mps.py:29-50`), both sides of `MP_NAME_SPECIAL_CASES`, and each canonical name. `source=aph_48`: one row per new 48th member (listing name), plus hand rows for printed names no variant matched (`Robert Katter` -> bob_katter, `Joshua Wilson` -> josh_wilson, `Thomas French` -> Tom French, Wikipedia's form). `source=aph_senate_48`: one row per new senator (listing name, state). Matching uses a normalised name (see `norm_person_name`), with the electorate first and then without it. An empty electorate means the row applies anywhere. |
| `party_terms.csv` | `member_id, chamber, parliament, party, political_bloc, source` | Party per (member, parliament) for every member term that has a PDF. `source` says where the party came from (see below). |
| `unknown_party.csv` | `member_id, chamber, parliament, note` | (member, parliament) pairs with no known party. Empty for House 43rd–48th and Senate 48th. |
| `party_mapping.csv` | `variant, canonical_party` | v1 `PARTY_MAPPING`, plus four variants from v1's Wikipedia CSVs that it lacked (`Palmer United`, `Xenophon/Centre Alliance`, `Nationals WA`, `Liberal / Independent`), and `Country Liberal Party` from the Senate API. The extras came from the seed script's `EXTRA_PARTY_MAPPING`. |
| `political_blocs.csv` | `party, bloc` | v1 `COALITION_PARTIES` -> `Coalition` and `LABOR_PARTIES` -> `Labor`. Any party not listed is `Crossbench`. This includes the Greens: v1 had a separate `Greens` bloc, but v2 uses three blocs. |

## How party per term was derived (`party_terms.source`)

v1 only knew each person's party in their most recent parliament: `all_mps_debug.csv`
covers up to the 47th and `all_mps_most_recent_party.csv` up to the 46th. Wikipedia
footnote markers (`[a]`) produce a few extra per-term rows. Party names go through
`party_mapping.csv`.

- `wikipedia_NN`: v1's Wikipedia scrape has a row for that very parliament.
- `wikipedia_48`: the 48th House (151 rows), written by
  `python -m disclosures.members --parliament 48 --party-terms --wiki-revision 1303424746 --wiki-revision 1377733140`.
  Revision 1303424746 (2025-07-30) of "Members of the Australian House of Representatives,
  2025–2028" gives the start-of-term party; 1377733140 (2026-09-30) only adds David Farley
  (Farrer by-election 2026, One Nation). A Queensland Liberal or National is `Liberal National
  Party`, as in v1. So Barnaby Joyce is National (he joined One Nation mid-term), and Allegra
  Spender and Zali Steggall are Independent (they later formed Community Strong).
- `aph_senate_api`: the Senate 48th (76 rows), written by
  `python -m disclosures.members --chamber senate --parliament 48 --party-terms`. It takes
  `senatorParty` from each saved API payload, through `party_mapping.csv`, with the same
  Queensland LNP rule. This is the party at scrape time (2026-10-02), not at the start of the
  term. See `docs/v2/senate_source.md`.
- `wikipedia_NN_carried_back`: an earlier term takes the party from the person's latest
  Wikipedia row. A latest party of `Liberal/Independent`, `Liberal / Independent`,
  `National / Independent` or `Labor/Independent` means the person defected during that last
  term, so earlier terms get the plain party.

The convention is the party at the start of the term, which is when the statement was
lodged. A defector keeps v1's compound label for the term of the defection (for example
`Liberal/Independent`), and its bloc comes from v1's sets.

Known gaps (no web lookups were made when seeding):
- A party change between parliaments that isn't a defection in the latest term isn't
  captured. Example: Bob Katter was elected as an Independent in 2010 and formed KAP in
  2011, but his 43rd term is carried back as `Katter's Australian Party`.
- v1's `PARTY_MAPPING` merges Palmer United into `United Australia Party`, which affects Clive
  Palmer in the 44th.
- `Nationals WA` maps to `National Party of Australia` (bloc Coalition), but Tony Crook sat on
  the crossbench in the 43rd.
