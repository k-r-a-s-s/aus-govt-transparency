"""AC-A4: the bundle contract (``data/items.json`` + ``data/schema.json``) equals SQL; the other
data files and the per-page static API agree with the DB."""
from __future__ import annotations

import random
from collections import Counter, defaultdict

import pytest
from web_support import MINI_DB, MINI_MANIFEST, REAL_DB, load_json, needs_real, ro

from disclosures.export import HEADER, fetch_rows, manifest_urls
from disclosures.web.bundle import decode_row

# Independent of disclosures.web: bundle column -> items column, rows in the CSV's order.
SQL_COLS = {
    "member": "i.member_id", "chamber": "i.chamber", "parliament": "i.parliament",
    "section": "i.section", "subsection": "i.subsection", "owner": "i.owner",
    "entity_raw": "i.entity_name_raw", "entity": "i.entity_id",
    "description": "i.description", "location": "i.location", "purpose": "i.purpose",
    "alteration": "i.is_alteration", "change_type": "i.change_type",
    "lodged_date": "i.lodged_date", "date_precision": "i.date_precision", "page": "i.page",
    "confidence": "i.confidence", "document": "i.pdf_sha256",
}
EXPECTED_COLUMNS = list(SQL_COLS)


def sql_rows(con):
    q = (f"select {', '.join(SQL_COLS.values())} from items i "
         "join documents d on d.pdf_sha256 = i.pdf_sha256 "
         "order by i.chamber, i.parliament, i.member_id, d.pdf_path, i.page, i.section, "
         "i.item_id")
    return [dict(zip(SQL_COLS, r)) for r in con.execute(q)]


def check_contract(site, db, sample=None):
    b = load_json(site / "data" / "items.json")
    schema = load_json(site / "data" / "schema.json")
    con = ro(db)
    n = con.execute("select count(*) from items").fetchone()[0]
    assert b["web_bundle_version"] == "1" == schema["web_bundle_version"]
    assert b["n"] == n
    cols = [c["name"] for c in schema["items"]["columns"]]
    assert cols == b["columns"] == EXPECTED_COLUMNS
    for c in schema["items"]["columns"]:
        assert c["published_column"] in HEADER
        name = c["name"]
        assert len(b["cols"][name]) == n, name
        if c["kind"] == "dict":
            d = b["dict"][name]
            assert d == sorted(d), f"dict {name} not sorted"
            assert len(set(d)) == len(d)
            assert all(v == -1 or 0 <= v < len(d) for v in b["cols"][name]), name
        else:
            assert c["kind"] == "int" and name not in b["dict"]
            assert all(isinstance(v, int) for v in b["cols"][name])
    expected = sql_rows(con)
    idx = range(n) if sample is None else random.Random(20261003).sample(range(n), sample)
    for i in idx:
        assert decode_row(b, i) == expected[i], f"row {i}"
    return b


def test_items_json_equals_sql_on_mini(mini_site):
    check_contract(mini_site, MINI_DB)


@needs_real
def test_items_json_on_real(real_site):
    """AC-A4 on Real: n = 50936, 200 random rows equal SQL, raw <= 8 MB."""
    b = check_contract(real_site, REAL_DB, sample=200)
    assert b["n"] == 50936
    assert (real_site / "data" / "items.json").stat().st_size <= 8_000_000


def test_aligned_dictionaries(mini_site):
    b = load_json(mini_site / "data" / "items.json")
    members = load_json(mini_site / "data" / "members.json")
    docs = load_json(mini_site / "data" / "documents.json")
    con = ro(MINI_DB)
    assert b["dict"]["member"] == [m["id"] for m in members] == \
        [r[0] for r in con.execute("select member_id from members order by 1")]
    assert b["dict"]["document"] == [d["sha256"] for d in docs] == \
        [r[0] for r in con.execute("select pdf_sha256 from documents order by 1")]


def test_members_json(mini_site):
    con = ro(MINI_DB)
    members = {m["id"]: m for m in load_json(mini_site / "data" / "members.json")}
    for mid, name, ch in con.execute("select member_id, full_name, chamber from members"):
        m = members[mid]
        assert (m["name"], m["chamber"]) == (name, ch)
        assert m["items"] == con.execute("select count(*) from items where member_id = ?",
                                         (mid,)).fetchone()[0]
        terms = con.execute("select chamber, parliament, electorate_or_state, party, "
                            "political_bloc from member_terms where member_id = ? "
                            "order by chamber, parliament", (mid,)).fetchall()
        assert [(t["chamber"], t["parliament"], t["electorate_or_state"], t["party"], t["bloc"])
                for t in m["terms"]] == terms
        assert sorted(m["documents"]) == sorted(r[0] for r in con.execute(
            "select pdf_sha256 from documents where member_id = ?", (mid,)))


def test_entities_json(mini_site):
    con = ro(MINI_DB)
    want = {r[0] for r in con.execute(
        "select e.entity_id from entities e where e.entity_type is not null or "
        "e.asx_code is not null or (select count(*) from items i "
        "where i.entity_id = e.entity_id) >= 2")}
    ents = load_json(mini_site / "data" / "entities.json")
    assert {e["id"] for e in ents} == want
    for e in ents:
        n, m = con.execute("select count(*), count(distinct member_id) from items "
                           "where entity_id = ?", (e["id"],)).fetchone()
        assert (e["items"], e["members"], e["page"]) == (n, m, n >= 2)


def test_documents_json(mini_site):
    from disclosures.web.urls import classify

    con = ro(MINI_DB)
    urls = manifest_urls(MINI_MANIFEST)
    docs = load_json(mini_site / "data" / "documents.json")
    assert len(docs) == con.execute("select count(*) from documents").fetchone()[0]
    for d in docs:
        path, ch, p, pages, mid, date, src, model = con.execute(
            "select pdf_path, chamber, parliament, page_count, member_id, statement_date, "
            "extraction_source, model from documents where pdf_sha256 = ?",
            (d["sha256"],)).fetchone()
        assert (d["path"], d["chamber"], d["parliament"], d["pages"], d["member_id"],
                d["statement_date"], d["extraction_source"], d["model"]) == \
            (path, ch, p, pages, mid, date, src, model)
        assert d["url"] == urls[d["sha256"]]
        assert d["url_class"] == classify(d["url"])


def test_per_member_and_entity_items_json(mini_site):
    """The static API: published column names, the CSV's values, counts equal SQL."""
    con = ro(MINI_DB)
    rows = [dict(zip(HEADER, r)) for r in fetch_rows(con, manifest_urls(MINI_MANIFEST))]
    by_m, by_e = defaultdict(list), defaultdict(list)
    for r in rows:
        by_m[r["member_id"]].append(r)
        if r["entity_id"]:
            by_e[r["entity_id"]].append(r)
    for (mid,) in con.execute("select member_id from members"):
        got = load_json(mini_site / "members" / mid / "items.json")
        assert got == by_m[mid]
        assert all(list(r) == HEADER for r in got)
    with_page = {r[0] for r in con.execute(
        "select entity_id from items where entity_id is not null group by 1 "
        "having count(*) >= 2")}
    on_disk = {p.name for p in (mini_site / "entities").iterdir()}
    assert on_disk == with_page
    for eid in with_page:
        assert load_json(mini_site / "entities" / eid / "items.json") == by_e[eid]


def test_search_json(mini_site):
    s = load_json(mini_site / "data" / "search.json")
    con = ro(MINI_DB)
    assert [m[0] for m in s["members"]] == [r[0] for r in con.execute(
        "select member_id from members order by 1")]
    assert {e[0] for e in s["entities"]} == {p.name for p in (mini_site / "entities").iterdir()}


def test_summary_json_equals_sql(mini_site):
    s = load_json(mini_site / "data" / "summary.json")
    con = ro(MINI_DB)
    one = lambda q: con.execute(q).fetchone()[0]  # noqa: E731
    assert s["items"] == one("select count(*) from items")
    assert s["members"] == one("select count(*) from members")
    assert s["statements"] == one("select count(*) from documents")
    assert s["entities"] == one("select count(*) from entities")
    assert s["parliaments"] == one("select count(distinct parliament) from items")
    assert s["loaded_at"] == one("select value from meta where key = 'loaded_at'")
    assert s["data_date"] == s["loaded_at"][:10]
    sb = con.execute("select i.section, t.political_bloc, count(*) from items i join "
                     "member_terms t on t.member_id = i.member_id and t.chamber = i.chamber "
                     "and t.parliament = i.parliament group by 1, 2 order by 1, 2").fetchall()
    assert [(r["section"], r["bloc"], r["items"]) for r in s["items_by_section_bloc"]] == sb
    top = con.execute("select entity_id, count(distinct member_id) m, count(*) n from items "
                      "where entity_id is not null group by 1 order by m desc, n desc, "
                      "entity_id limit 15").fetchall()
    assert [(e["id"], e["members"], e["items"]) for e in s["top_entities_by_members"]] == top
    po = con.execute("select chamber, parliament, owner, count(*) from items "
                     "group by 1, 2, 3 order by 1, 2, 3").fetchall()
    assert [(r["chamber"], r["parliament"], r["owner"], r["items"])
            for r in s["items_by_parliament_owner"]] == po
    alt = con.execute("select chamber, parliament, count(*), sum(is_alteration) from items "
                      "group by 1, 2 order by 1, 2").fetchall()
    assert [(r["chamber"], r["parliament"], r["items"], r["alterations"])
            for r in s["alterations_by_parliament"]] == alt
    for r in s["alterations_by_parliament"]:
        assert r["share"] == pytest.approx(r["alterations"] / r["items"], abs=1e-4)
    cov = con.execute("select chamber, parliament, count(distinct member_id), "
                      "count(distinct pdf_sha256), count(*) from items group by 1, 2 "
                      "order by 1, 2").fetchall()
    assert [(c["chamber"], c["parliament"], c["members"], c["statements"], c["items"])
            for c in s["coverage"]] == cov
    assert [x["section"] for x in s["sections"]] == list(range(1, 15))


def test_schema_documents_every_column(mini_site):
    from disclosures.export import COLUMNS

    schema = load_json(mini_site / "data" / "schema.json")
    assert [c["name"] for c in schema["row_objects"]["columns"]] == HEADER
    desc = {n: d for n, _, d in COLUMNS}
    for c in schema["items"]["columns"]:
        assert c["description"] == desc[c["published_column"]]
    assert schema["items"]["null_index"] == -1


def test_json_files_are_utf8_and_end_with_newline(mini_site):
    for p in (mini_site / "data").iterdir():
        raw = p.read_bytes()
        raw.decode("utf-8")
        assert raw.endswith(b"\n")


@needs_real
def test_real_counts(real_site):
    s = load_json(real_site / "data" / "summary.json")
    assert (s["items"], s["members"], s["statements"], s["entities"]) == \
        (50936, 408, 995, 11542)
    assert s["entities_with_page"] == 4448
    assert len(list((real_site / "entities").iterdir())) == 4448
    assert len(list((real_site / "members").iterdir())) == 408
    c = Counter(d["url_class"] for d in load_json(real_site / "data" / "documents.json"))
    assert c["senate-json"] == 76
