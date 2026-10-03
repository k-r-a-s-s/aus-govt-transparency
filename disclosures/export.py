"""``python -m disclosures export``: the published CSV and the Kaggle package (ADR-10, AC-5.1).

One CSV row per ``items`` row, joined with its member, the member's term (party, bloc,
electorate), its document and its entity. The same file goes to ``exports/disclosures_v2.csv``
and ``exports/kaggle/disclosures_v2.csv``, next to a README (field dictionary, method, known
limitations) and Kaggle's ``dataset-metadata.json``. With ``--site DIR`` it also writes the
static GitHub Pages site (``index.html`` + a copy of the DB for Datasette Lite). Reads the DB
read-only; writes nothing else.
"""
from __future__ import annotations

import csv
import html
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .dbconst import DEFAULT_DB, _guard_v1
from .normalise import normalise_entity

DEFAULT_OUT = "exports"
DEFAULT_MANIFEST = "pdfs/manifest.csv"
CSV_NAME = "disclosures_v2.csv"
DEFAULT_KAGGLE_ID = "kevrass/australian-parliament-registers-of-interests"
# For our compilation of the facts; the source PDFs stay under APH's CC BY-NC-ND (DECISIONS G4).
DEFAULT_LICENSE = "CC-BY-4.0"
DB_NAME = "disclosures_v2.db"
REPO_URL = "https://github.com/k-r-a-s-s/aus-govt-transparency"
DEFAULT_PAGES_URL = "https://k-r-a-s-s.github.io/aus-govt-transparency"

# (column, kaggle type, description). Order = CSV column order. The README field dictionary
# and dataset-metadata.json are generated from this list, so they always cover every column.
COLUMNS = [
    ("item_id", "string", "Stable id of the disclosed item (sha1 of the document hash and the "
     "item's content; see docs/v2/loading.md)."),
    ("chamber", "string", "`house` (House of Representatives) or `senate`."),
    ("parliament", "integer", "Parliament number (43 = 2010-2013 … 48 = 2025-)."),
    ("member_id", "string", "Stable member id (slug of the member's name, e.g. `tony_abbott`); "
     "the same person keeps one id across parliaments and chambers."),
    ("member_name", "string", "Member's full name."),
    ("party", "string", "Member's party for this parliament (start of term)."),
    ("political_bloc", "string", "`Labor`, `Coalition` or `Crossbench`, derived from party."),
    ("electorate_or_state", "string", "House: electorate. Senate: state or territory."),
    ("statement_date", "string", "Date of the member's initial statement (YYYY-MM-DD), "
     "where printed."),
    ("section", "integer", "Register section number (1-14, the House form's numbering; Senate "
     "categories are mapped onto it)."),
    ("subsection", "string", "Sub-part of the section where the form has one (`2(i)` "
     "family trusts, `2(ii)` other trusts), else empty."),
    ("category", "string", "Section name: Shareholding, Trust, Real estate, Directorship, "
     "Partnership, Liability, Bond/debenture, Account, Other asset, Income, Gift, "
     "Sponsored travel/hospitality, Membership, Other interest."),
    ("owner", "string", "Whose interest it is: `self`, `spouse`, `dependent_child` or "
     "`unknown`."),
    ("entity_name_as_printed", "string", "The company, organisation, trust or person the "
     "item names, as printed. Empty when the item names no entity (e.g. a house address)."),
    ("entity_id", "string", "Standardised entity id; items naming the same organisation in "
     "different spellings share it. Empty for no entity or a generic term (e.g. `family "
     "trust`)."),
    ("entity_name", "string", "Canonical name of the standardised entity."),
    ("entity_type", "string", "Entity type (listed_company, private_company, "
     "bank_or_financial, trust_or_fund, association_or_ngo, sporting_body, government_body, "
     "political_party, union, airline, media_or_entertainment, education, person, other). "
     "Empty for most one-off (singleton) entities."),
    ("entity_asx_code", "string", "ASX ticker when the entity matched an ASX-listed company "
     "(banks, airlines and media groups included, e.g. `CBA`, `QAN`), else empty."),
    ("entity_match_method", "string", "How the name was standardised: `curated` (hand table), "
     "`asx` (ASX listed-companies snapshot), `llm` (LLM grouping of variants), `singleton` "
     "(one-off name, its own entity) or `generic` (generic term, no entity)."),
    ("description", "string", "The item as printed on the form (the full cell text)."),
    ("location", "string", "Location, where the form gives one (real estate, travel)."),
    ("purpose", "string", "Purpose, where the form gives one (real estate, liabilities)."),
    ("is_alteration", "integer", "1 if the item comes from a later Notification of "
     "Alteration, 0 if from the initial statement."),
    ("change_type", "string", "`initial`, `added`, `removed`, `varied` or `unknown`."),
    ("lodged_date", "string", "Date the statement or alteration was lodged (YYYY-MM-DD; see "
     "date_precision)."),
    ("date_precision", "string", "`day`, `month` (day set to 01) or `unknown` (no date "
     "printed; lodged_date empty)."),
    ("page", "integer", "Page of the source PDF the item is on (1-based). Senate items: 1."),
    ("extraction_confidence", "string", "Extractor's confidence in the item: `high`, "
     "`medium` or `low` (low/medium = hard-to-read scan or ambiguous layout)."),
    ("source_file", "string", "Source document path in the repository (House PDF, or the "
     "Senate API JSON payload)."),
    ("source_sha256", "string", "sha256 of the source document."),
    ("source_url", "string", "Where the source document was downloaded from (APH)."),
    ("extraction_source", "string", "`gemini-api` (LLM transcription of the PDF) or "
     "`senate-json` (Senate interests API, no LLM)."),
    ("extraction_model", "string", "Model(s) that transcribed the PDF; `a+b` means model b "
     "handled pages model a refused."),
]
HEADER = [c[0] for c in COLUMNS]

QUERY = """
select i.item_id, i.chamber, i.parliament, i.member_id, m.full_name, t.party,
       t.political_bloc, t.electorate_or_state, d.statement_date, i.section, i.subsection,
       i.category, i.owner, i.entity_name_raw, i.entity_id, e.canonical_name, e.entity_type,
       e.asx_code, null, i.description, i.location, i.purpose, i.is_alteration,
       i.change_type, i.lodged_date, i.date_precision, i.page, i.confidence, d.pdf_path,
       i.pdf_sha256, d.source_url, d.extraction_source, d.model
from items i
join documents d on d.pdf_sha256 = i.pdf_sha256
left join members m on m.member_id = i.member_id
left join member_terms t on t.member_id = i.member_id and t.chamber = i.chamber
                        and t.parliament = i.parliament
left join entities e on e.entity_id = i.entity_id
order by i.chamber, i.parliament, i.member_id, d.pdf_path, i.page, i.section, i.item_id
"""


# The README's method and known-limitations prose (Markdown), shared with the public site's
# /about/ page (disclosures/web/pages.py) so the two never drift. Placeholders: ``n_ent`` (all
# entities) and ``n_untyped`` (entities with no type), filled by ``str.format``.
README_METHOD = """1. **Collect.** House statements are the PDFs on aph.gov.au (archived registers for the
   43rd-47th parliaments, the live register for the 48th); `source_url` points at each one.
   Senate statements come from the Parliament's senators' interests API (JSON).
2. **Transcribe.** Each House PDF (initial statement plus every alteration bound into it) was
   transcribed by `google/gemini-3.8-flash` into a strict JSON schema, one item per disclosed
   interest, with `anthropic/claude-sonnet-5.5` taking any pages Gemini refused. On a 12-PDF
   hand-checked gold set (790 items) this scored precision 0.986, recall 0.987 (F1 0.987),
   with 100% owner and page accuracy. Senate items are mapped from the API's fields; no
   model is involved.
3. **Validate and load.** Every transcription passes a schema and completeness check
   (every page covered, every item on a real page) before loading. Members are matched across
   parliaments and chambers to one `member_id`; party and bloc come from a per-term table.
4. **Standardise entities.** Entity names are normalised, then resolved in order: a curated
   alias table (the most common names), the ASX listed-companies list, an LLM grouping of
   spelling variants, and finally one entity per remaining one-off name. {n_ent:,} entities."""

README_LIMITATIONS = """- **Senate before the 48th parliament is missing.** Earlier Senate registers exist only as
  tabled volumes and are not in this release.
- **Two prompt versions.** Most House statements for the 43rd-47th parliaments were
  transcribed with prompt v0. Prompt v1 adds one rule (C12): itemise lists bound in as
  attachments ("see attached"). Only the 7 statements found to have un-itemised attachments
  were re-run on v1 (`coultonm_43p`, `nevillep_43p`, `coultonm_44p`, `huntg_44p`, `pynec_44p`,
  `coultonm_45p`, `odowdk45p`); the whole 48th House register used v1. A few other v0
  statements may still describe an attachment in one item instead of itemising it.
- **One-off entities are untyped.** {n_untyped:,} of the {n_ent:,} entities are names that
  appear once; each is its own entity with an empty `entity_type`.
- **ASX matching is name-based.** A listed company whose snapshot name differs from the name
  the LLM chose may be typed `other` with no `entity_asx_code`.
- **Transcription is not perfect.** Expect roughly 1-2% of items to be missed or misread,
  more on poor scans (43rd-45th parliaments); `extraction_confidence` flags the doubtful ones.
  Check anything important against the source PDF (`source_url`, `page`).
- **Dates.** `lodged_date` is empty when no date is printed (`date_precision = unknown`).
- **Party** is the party at the start of each term; mid-term defections are not tracked."""


def manifest_urls(path: Path) -> Dict[str, str]:
    """sha256 -> source_url from pdfs/manifest.csv (load leaves documents.source_url empty)."""
    if not path.exists():
        return {}
    with path.open(newline="") as f:
        return {r["pdf_sha256"]: r["source_url"] for r in csv.DictReader(f) if r["source_url"]}


def fetch_rows(con: sqlite3.Connection, urls: Dict[str, str]) -> List[list]:
    methods = dict(con.execute("select alias_normalised, method from entity_aliases"))
    i_raw, i_method = HEADER.index("entity_name_as_printed"), HEADER.index("entity_match_method")
    i_sha, i_url = HEADER.index("source_sha256"), HEADER.index("source_url")
    rows = []
    for r in con.execute(QUERY):
        r = list(r)
        if r[i_raw] is not None:
            r[i_method] = methods.get(normalise_entity(r[i_raw]))
        if not r[i_url]:
            r[i_url] = urls.get(r[i_sha])
        rows.append(["" if v is None else v for v in r])
    return rows


def write_csv(rows: List[list], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(HEADER)
        w.writerows(rows)
    tmp.replace(path)


def coverage(con: sqlite3.Connection) -> List[tuple]:
    return con.execute(
        "select chamber, parliament, count(distinct member_id), count(distinct pdf_sha256), "
        "count(*) from items group by 1, 2 order by 1, 2").fetchall()


def render_readme(con: sqlite3.Connection, n_rows: int) -> str:
    meta = dict(con.execute("select key, value from meta"))
    cov = "\n".join(f"| {ch} | {p} | {m:,} | {d:,} | {n:,} |" for ch, p, m, d, n in coverage(con))
    fields = "\n".join(f"| `{name}` | {typ} | {desc} |" for name, typ, desc in COLUMNS)
    n_ent = con.execute("select count(*) from entities").fetchone()[0]
    n_untyped = con.execute("select count(*) from entities where entity_type is null").fetchone()[0]
    method = README_METHOD.format(n_ent=n_ent)
    limitations = README_LIMITATIONS.format(n_ent=n_ent, n_untyped=n_untyped)
    return f"""# Australian Parliament Registers of Members' and Senators' Interests (v2)

Every interest Australian federal MPs and senators disclosed in the Registers of Interests,
transcribed item by item from the official statements and joined with the member's party and
a standardised entity (company, organisation, trust) for each item.

`{CSV_NAME}`: {n_rows:,} rows, one per disclosed item (a shareholding, a gift, a trip, a
directorship, …), {len(HEADER)} columns. Built from `disclosures_v2.db` (schema
{meta.get('schema_version', '?')}, loaded {meta.get('loaded_at', '?')}).

## Coverage

| chamber | parliament | members | statements | items |
|---|---|---|---|---|
{cov}

House: the 43rd-47th parliaments (2010-2025) from the archived registers, and the current 48th
register as scraped. Senate: the 48th parliament only (the senators' interests API serves
current senators only).

## Field dictionary

| column | type | description |
|---|---|---|
{fields}

Empty cells are nulls.

## Method

{method}

## Known limitations

{limitations}

## Source and licence

Parliament of Australia, Register of Members' Interests and Register of Senators' Interests
(aph.gov.au). Code and documentation: {REPO_URL}. Browse and query the data online
(Datasette Lite): {DEFAULT_PAGES_URL}/.

Licence: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), to the extent we hold
rights in the dataset. You may share and adapt it for any purpose, commercial included, if you
credit this dataset and the source ("Parliament of Australia website"). The dataset records the
facts each statement discloses; the statements themselves (the PDFs, linked by each row's
`source_url`) are published by the Parliament under
[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/), so reuse of the documents
follows that licence.
"""


def kaggle_metadata(kaggle_id: str, license_name: str, description: str) -> dict:
    # isPrivate matters only to `kaggle datasets metadata --update` (create uses --public).
    return {
        "title": "Australian Parliament Registers of Interests",
        "id": kaggle_id,
        "subtitle": "Every interest disclosed by federal MPs and senators, 2010 to now",
        "description": description,
        "isPrivate": False,
        "licenses": [{"name": license_name}],
        "keywords": ["politics", "government", "australia"],
        "resources": [{
            "path": CSV_NAME,
            "description": "One row per disclosed item.",
            "schema": {"fields": [{"name": n, "type": t, "description": d}
                                  for n, t, d in COLUMNS]},
        }],
    }


def datasette_lite_url(pages_url: str) -> str:
    return f"https://lite.datasette.io/?url={pages_url.rstrip('/')}/{DB_NAME}"


def render_index(con: sqlite3.Connection, pages_url: str) -> str:
    meta = dict(con.execute("select key, value from meta"))
    cov = coverage(con)
    n_items = sum(r[4] for r in cov)
    n_ent = con.execute("select count(*) from entities").fetchone()[0]
    loaded = html.escape(meta.get("loaded_at", "?"))
    year = meta.get("loaded_at", "????")[:4]
    rows = "\n".join(f"<tr><td>{ch}</td><td>{p}</td><td>{m:,}</td><td>{d:,}</td><td>{n:,}</td></tr>"
                     for ch, p, m, d, n in cov)
    lite = html.escape(datasette_lite_url(pages_url))
    db_href = html.escape(f"{pages_url.rstrip('/')}/{DB_NAME}")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Australian Parliament Registers of Interests (v2)</title>
<style>
body {{ font: 16px/1.5 system-ui, sans-serif; max-width: 46rem; margin: 2rem auto; padding: 0 1rem; color: #222; }}
table {{ border-collapse: collapse; }}
th, td {{ padding: .2rem .7rem; border-bottom: 1px solid #ddd; text-align: right; }}
th:first-child, td:first-child {{ text-align: left; }}
code, pre {{ background: #f4f4f4; }}
pre {{ padding: .6rem; overflow-x: auto; white-space: pre-wrap; }}
.button {{ display: inline-block; padding: .5rem 1rem; background: #1a5fb4; color: #fff; border-radius: 4px; text-decoration: none; }}
</style>
</head>
<body>
<h1>Australian Parliament Registers of Interests</h1>
<p>Every interest Australian federal MPs and senators disclosed in the Registers of Members' and
Senators' Interests, transcribed item by item from the official statements: {n_items:,} items
(shareholdings, trusts, property, directorships, gifts, sponsored travel, memberships, &hellip;),
each joined with the member's party and a standardised entity ({n_ent:,} entities).</p>

<p><a class="button" href="{lite}">Explore the data in Datasette Lite</a></p>
<p>Datasette Lite runs in your browser: write SQL against the <code>items</code>,
<code>members</code>, <code>member_terms</code>, <code>documents</code> and <code>entities</code>
tables, filter and facet, and download results as CSV. Or download the SQLite database:
<a href="{DB_NAME}">{DB_NAME}</a>.</p>

<h2>Coverage</h2>
<table>
<tr><th>chamber</th><th>parliament</th><th>members</th><th>statements</th><th>items</th></tr>
{rows}
</table>
<p>House: the 43rd&ndash;47th parliaments (2010&ndash;2025) from the archived registers, and the
current 48th register. Senate: the 48th parliament only. Data loaded {loaded}.</p>

<h2>Caveats</h2>
<p>The House statements were transcribed from PDFs by an LLM (precision and recall about 0.99 on
a hand-checked sample). Expect a small share of items to be missed or misread, more on the
scanned 43rd&ndash;45th parliament statements. Each item records its source document and page:
check anything important against the original on aph.gov.au. The full field dictionary, method
and known limitations are in the <a href="{REPO_URL}">project repository</a>.</p>

<h2>How to cite</h2>
<pre>Rassool, K. ({year}). Australian Parliament Registers of Interests (v2) [Data set].
Transcribed from the Parliament of Australia Register of Members' Interests and Register of
Senators' Interests. {html.escape(pages_url.rstrip('/'))}/</pre>
<p>Please also credit the source: Parliament of Australia, Registers of Members' and Senators'
Interests (aph.gov.au).</p>

<h2>Licence</h2>
<p>The dataset is released under <a href="https://creativecommons.org/licenses/by/4.0/">CC BY
4.0</a>, to the extent we hold rights in it: share and adapt it for any purpose, crediting this
dataset and the source (&ldquo;Parliament of Australia website&rdquo;). The dataset records the
facts each statement discloses; the statements themselves are published by the Parliament under
<a href="https://creativecommons.org/licenses/by-nc-nd/4.0/">CC BY-NC-ND 4.0</a>, so reuse of
the documents follows that licence.</p>

<h2>Links</h2>
<ul>
<li><a href="{lite}">Datasette Lite</a> (<code>{db_href}</code>)</li>
<li><a href="{REPO_URL}">Source code, documentation and the CSV export</a></li>
<li><a href="https://www.aph.gov.au/Senators_and_Members/Members/Register">House Register of Members' Interests</a> (aph.gov.au)</li>
<li><a href="https://www.aph.gov.au/Parliamentary_Business/Committees/Senate/Senators_Interests/Senators_Interests_Register">Senate Register of Senators' Interests</a> (aph.gov.au)</li>
</ul>
</body>
</html>
"""


def export(db_path: str | Path = DEFAULT_DB, out_dir: str | Path = DEFAULT_OUT,
           manifest: str | Path = DEFAULT_MANIFEST, kaggle_id: str = DEFAULT_KAGGLE_ID,
           license_name: str = DEFAULT_LICENSE, site_dir: str | Path | None = None,
           pages_url: str = DEFAULT_PAGES_URL) -> dict:
    db_path, out_dir = Path(db_path), Path(out_dir)
    _guard_v1(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"{db_path} not found: run `python -m disclosures load` first")
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = fetch_rows(con, manifest_urls(Path(manifest)))
        n_items = con.execute("select count(*) from items").fetchone()[0]
        readme = render_readme(con, len(rows))
        index = render_index(con, pages_url) if site_dir is not None else None
    finally:
        con.close()
    if len(rows) != n_items:  # a join dropped or duplicated items: never publish that
        raise RuntimeError(f"export has {len(rows)} rows but items has {n_items}")
    csv_path = out_dir / CSV_NAME
    write_csv(rows, csv_path)
    kaggle = out_dir / "kaggle"
    kaggle.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(csv_path, kaggle / CSV_NAME)
    (kaggle / "README.md").write_text(readme, encoding="utf-8")
    (kaggle / "dataset-metadata.json").write_text(
        json.dumps(kaggle_metadata(kaggle_id, license_name, readme), indent=2) + "\n", encoding="utf-8")
    if site_dir is not None:
        site = Path(site_dir)
        site.mkdir(parents=True, exist_ok=True)
        (site / "index.html").write_text(index, encoding="utf-8")
        tmp = site / (DB_NAME + ".tmp")
        shutil.copyfile(db_path, tmp)
        tmp.replace(site / DB_NAME)
    return {"rows": len(rows), "csv": str(csv_path), "kaggle": str(kaggle),
            "site": None if site_dir is None else str(site_dir),
            "no_source_url": sum(1 for r in rows if not r[HEADER.index("source_url")])}


def add_arguments(p) -> None:
    p.add_argument("--db", default=DEFAULT_DB, help="v2 database (default: %(default)s)")
    p.add_argument("--out", default=DEFAULT_OUT, help="output directory (default: %(default)s)")
    p.add_argument("--manifest", default=DEFAULT_MANIFEST,
                   help="fills source_url where the DB has none (default: %(default)s)")
    p.add_argument("--kaggle-id", default=DEFAULT_KAGGLE_ID,
                   help="Kaggle dataset id <user>/<slug> (default: %(default)s)")
    p.add_argument("--license", dest="license_name", default=DEFAULT_LICENSE,
                   help="Kaggle licence name (default: %(default)s)")
    p.add_argument("--site", dest="site_dir", default=None, metavar="DIR",
                   help="also write the Pages site (index.html + DB copy) to DIR, e.g. site")
    p.add_argument("--pages-url", default=DEFAULT_PAGES_URL,
                   help="public URL of the Pages site, for the Datasette Lite link "
                        "(default: %(default)s)")


def run(args) -> int:
    try:
        s = export(args.db, args.out, args.manifest, args.kaggle_id, args.license_name,
                   args.site_dir, args.pages_url)
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        print(f"export: {e}", file=sys.stderr)
        return 2
    print(f"export: {s['rows']:,} rows -> {s['csv']} and {s['kaggle']}/ "
          f"({s['no_source_url']:,} rows without source_url)")
    if s["site"]:
        print(f"export: site -> {s['site']}/index.html and {s['site']}/{DB_NAME}")
    return 0
