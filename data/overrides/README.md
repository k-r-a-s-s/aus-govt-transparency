# data/overrides — member identity and party tables (ADR-7)

Hand-curated tables the loader (`python -m disclosures load`, see `docs/v2/loading.md`) joins
against. They carry v1's curated assets forward so v1 code can be deleted in Phase 5.

They were seeded on 2026-10-02 by `scripts/seed_v2_overrides.py`, which reads v1 read-only:
`disclosures.db` (`mps`, and `disclosures.pdf_filename` -> `mp_id`), the dict literals in
`src/cleaning/*.py` (parsed, not imported) and `output/all_mps_*.csv` (v1's Wikipedia
scrapes). The script's `MANUAL_*` tables hold the hand fixes. `--check` exits 1 if a CSV here
differs from what the script would write. After Phase 5 removes v1 the script stops working.
From then on these CSVs are the source of truth and are edited by hand.

`member_id` is the slug of the canonical full name: lower case, ASCII-folded, each run of
non-alphanumerics becomes `_` (`Clare O'Neil` -> `clare_o_neil`). The canonical full name is
the member's Wikipedia name as v1 scraped it (`Chris Bowen`, `Bert van Manen`). All 303
people who own a tracked PDF have one.

| File | Columns | What / provenance |
|---|---|---|
| `pdf_members.csv` | `pdf_path, member_id, canonical_full_name, electorate_or_state, source` | One row per tracked PDF (774), sorted by path. This is the main way a document gets its member. `source=v1`: from v1 `disclosures.pdf_filename` -> `mps` (759). `source=stem`: v1 loaded no rows for the PDF, so the member comes from the filename stem and the first page (9). `source=non_member`: not a member's statement, `member_id` is empty (6: `interestsr_4Np.pdf` is the House resolution text, `explanatory_notes___booklet_1.pdf` is the form's notes). `electorate_or_state` is v1's electorate for that record. It is v1's most-recent seat name for the member, so renamed seats carry the later name even on older PDFs (Wilkie's 43rd–45th PDFs print Denison, the column says Clark). The loader prefers the extraction's printed electorate and only falls back to this column. |
| `member_aliases.csv` | `name_variant, electorate_or_state, member_id, canonical_full_name, source` | Name variants -> member. It holds every v1 `mps.full_name` and `mps.mp_id`, the v1 manual merge overrides (`merge_duplicate_mps.py:29-50`), both sides of `MP_NAME_SPECIAL_CASES`, and each canonical name. Matching uses a normalised name (see `norm_person_name`), with the electorate first and then without it. An empty electorate means the row applies anywhere. |
| `party_terms.csv` | `member_id, chamber, parliament, party, political_bloc, source` | Party per (member, parliament) for every member term that has a PDF. `source` says where the party came from (see below). |
| `unknown_party.csv` | `member_id, chamber, parliament, note` | (member, parliament) pairs with no known party. Empty for House 43rd–47th. Phase 4 adds the 48th. |
| `party_mapping.csv` | `variant, canonical_party` | v1 `PARTY_MAPPING`, plus four variants from v1's Wikipedia CSVs that it lacked (`Palmer United`, `Xenophon/Centre Alliance`, `Nationals WA`, `Liberal / Independent`). |
| `political_blocs.csv` | `party, bloc` | v1 `COALITION_PARTIES` -> `Coalition` and `LABOR_PARTIES` -> `Labor`. Any party not listed is `Crossbench`. This includes the Greens: v1 had a separate `Greens` bloc, but v2 uses three blocs. |

## How party per term was derived (`party_terms.source`)

v1 only knew each person's party in their most recent parliament: `all_mps_debug.csv`
covers up to the 47th and `all_mps_most_recent_party.csv` up to the 46th. Wikipedia
footnote markers (`[a]`) produce a few extra per-term rows. Party names go through
`party_mapping.csv`.

- `wikipedia_NN`: v1's Wikipedia scrape has a row for that very parliament.
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
