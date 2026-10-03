# Web test fixture

`mini.db` and `mini-manifest.csv` are a deterministic subset of `site/disclosures_v2.db` and
`pdfs/manifest.csv` for the public-site tests (`tests/web/`, SPEC ADR-W12). Regenerate with:

    python -m disclosures web make-fixture --db site/disclosures_v2.db \
        --manifest pdfs/manifest.csv --out tests/fixtures/web --members 6 --seed 1

Same inputs and seed give the same bytes (`tests/web/test_web_fixture.py` checks this against
the committed files whenever the real DB is present). If the real DB changes, regenerate and
commit both files.

`mini.db` has the real DB's schema, the six members' rows in `members`, `member_terms`,
`documents` and `items`, the entities their items name, the aliases of those entities plus the
aliases their printed names normalise to, and `meta` copied with `fixture = 1`.
716,800 bytes; 1,043 items, 19 statements, 18 terms, 318 entities, 667 aliases.

## The six members (seed 1)

| member_id | slot | why |
|---|---|---|
| `ken_o_dowd` | house-43 | House 43rd statement: scanned PDF behind the APH redirector (`house-redirect` URL class). Coalition, 43rd to 46th. |
| `russell_broadbent` | house-47 | House 47th statement: `static.aph.gov.au` PDF (`house-pdf`). Coalition, 43rd to 47th; spouse items. |
| `josh_wilson` | house-48 | House 48th statement from the interests-register API (`house-api`). Labor, 45th to 48th; spouse and dependent-child items. |
| `richard_colbeck` | senate-48 | Senate 48th statement from the Senate API (`senate-json`, no page links). Coalition. |
| `nicolette_boele` | family | Spouse and dependent-child items. Crossbench, House 48th. |
| `wayne_swan` | alterations | Many alterations (161; the slot needs at least 129, the 90th percentile of all members). Labor, 43rd to 45th; the only `low`-confidence item. |

Selection rule (`disclosures/web/fixture.py`): one member per slot, chosen by
`random.Random(seed)` among the members with at most 300 items that meet the slot's
constraint; the draw repeats until the six cover the Labor, Coalition and Crossbench blocs and
include at least one `low`-confidence item.
