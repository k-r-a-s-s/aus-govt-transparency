import copy
import csv
import hashlib
import os
import sqlite3
from pathlib import Path

import pytest

from conftest import write_json
from disclosures.cli import main
from disclosures.load import (CATEGORY, SANITY_QUERIES, Overrides, item_id, item_key, load_db,
                              member_slug, norm_electorate, norm_person_name)

REPO = Path(__file__).resolve().parent.parent
REAL_OVERRIDES = REPO / "data" / "overrides"

ADR7_COLUMNS = {
    "documents": ["pdf_sha256", "pdf_path", "chamber", "parliament", "member_id", "page_count",
                  "source_url", "fetched_at", "statement_date", "extraction_source", "model"],
    "members": ["member_id", "full_name", "chamber"],
    "member_terms": ["member_id", "chamber", "parliament", "electorate_or_state", "party",
                     "political_bloc"],
    "items": ["item_id", "pdf_sha256", "member_id", "chamber", "parliament", "section",
              "subsection", "category", "owner", "entity_name_raw", "entity_id", "description",
              "location", "purpose", "is_alteration", "change_type", "lodged_date",
              "date_precision", "page", "confidence"],
    "entities": ["entity_id", "canonical_name", "entity_type", "asx_code"],
    "entity_aliases": ["alias_normalised", "entity_id", "method", "confidence"],
    "meta": ["key", "value"],
}


def make_pdf(root: Path, rel: str, pages: int, tag: str) -> str:
    import pymupdf

    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    d = pymupdf.open()
    for i in range(pages):
        d.new_page().insert_text((72, 72), f"{tag} page {i + 1}")
    d.save(path)
    d.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


@pytest.fixture
def load_repo(fake_repo):
    """tmp repo with 3 valid extraction files, 1 invalid one and tiny override CSVs."""
    root, doc = fake_repo
    ex = root / "extractions" / "workflow-claude" / "house"

    # 1. Jane Fixture (45th), attached through pdf_members.csv.
    write_json(ex / "45" / "fixture_45p.json", doc)

    # 2. Same member, 46th, attached through member_aliases.csv (not in pdf_members).
    d2 = copy.deepcopy(doc)
    d2["pdf_path"] = "pdfs/46/fixture_46p.pdf"
    d2["pdf_sha256"] = make_pdf(root, d2["pdf_path"], 3, "second")
    d2["parliament"] = 46
    d2["member_name_as_printed"] = "FIXTURE, Jane Mary"
    d2["electorate_or_state"] = ""
    d2["statement_date"] = "2019-07-01"
    # two identical items -> same key, ordinal 0 and 1
    twin = copy.deepcopy(d2["items"][0])
    d2["items"] = [twin, copy.deepcopy(twin)] + [
        dict(copy.deepcopy(d2["items"][0]), section=s, entity_name=None,
             description=f"section {s} thing", page=2) for s in range(2, 15)]
    write_json(ex / "46" / "fixture_46p.json", d2)

    # 3. A member in no override table: slugged from the printed name, no party.
    d3 = copy.deepcopy(doc)
    d3["pdf_path"] = "pdfs/47/newbie_47p.pdf"
    d3["pdf_sha256"] = make_pdf(root, d3["pdf_path"], 3, "third")
    d3["parliament"] = 47
    d3["member_name_as_printed"] = "Néwbie O'Member"
    d3["electorate_or_state"] = "Nowhere"
    write_json(ex / "47" / "newbie_47p.json", d3)

    # 4. Invalid: pages_covered incomplete.
    bad = copy.deepcopy(doc)
    bad["pages_covered"] = [1, 2]
    write_json(ex / "45" / "broken_45p.json", bad)

    ov = root / "data" / "overrides"
    write_csv(ov / "pdf_members.csv",
              ["pdf_path", "member_id", "canonical_full_name", "electorate_or_state", "source"],
              [["pdfs/45/fixture_45p.pdf", "jane_fixture", "Jane Fixture", "Testville", "v1"]])
    write_csv(ov / "member_aliases.csv",
              ["name_variant", "electorate_or_state", "member_id", "canonical_full_name", "source"],
              [["Jane Mary Fixture", "", "jane_fixture", "Jane Fixture", "test"]])
    write_csv(ov / "party_terms.csv",
              ["member_id", "chamber", "parliament", "party", "political_bloc", "source"],
              [["jane_fixture", "house", 45, "Australian Labor Party", "Labor", "test"],
               ["jane_fixture", "house", 46, "Independent", "Crossbench", "test"]])
    write_csv(ov / "unknown_party.csv", ["member_id", "chamber", "parliament", "note"],
              [["newbie_o_member", "house", 47, "test"]])
    return root, ov


def _load(root, ov, db="v2.db"):
    return load_db("workflow-claude", root / db, root / "extractions", ov)


def _q(db, sql):
    with sqlite3.connect(db) as c:
        return c.execute(sql).fetchall()


def test_tables_and_columns_match_adr7(load_repo):
    root, ov = load_repo
    _load(root, ov)
    with sqlite3.connect(root / "v2.db") as c:
        for table, cols in ADR7_COLUMNS.items():
            assert [r[1] for r in c.execute(f"pragma table_info({table})")] == cols, table
        idx = {r[0] for r in c.execute("select name from sqlite_master where type='index'")}
    assert {"idx_items_pdf_sha256", "idx_items_member_id", "idx_items_section",
            "idx_items_entity_id", "idx_documents_member_id"} <= idx
    assert _q(root / "v2.db", "select count(*) from entities") == [(0,)]
    assert _q(root / "v2.db", "select count(*) from entity_aliases") == [(0,)]
    meta = dict(_q(root / "v2.db", "select key, value from meta"))
    assert meta["schema_version"] == "2.0" and meta["source_id"] == "workflow-claude"
    assert meta["n_files"] == "3" and meta["loaded_at"]


def test_documents_equal_valid_files_and_invalid_reported(load_repo):
    root, ov = load_repo
    s = _load(root, ov)
    assert s["files_loaded"] == 3
    assert _q(root / "v2.db", "select count(*) from documents") == [(3,)]
    assert list(s["files_skipped"]) == [str(root / "extractions/workflow-claude/house/45/broken_45p.json")]
    assert "pages_covered" in s["files_skipped"][next(iter(s["files_skipped"]))][0]
    row = _q(root / "v2.db", "select extraction_source, model, source_url, fetched_at, statement_date "
                             "from documents where pdf_path='pdfs/45/fixture_45p.pdf'")
    assert row == [("workflow-claude", "fixture", None, None, "2016-08-30")]


def test_sanity_queries_zero(load_repo):
    root, ov = load_repo
    s = _load(root, ov)
    for label, n, hard in s["sanity"]:
        if hard:
            assert n == 0, label
    # the queries the summary reports are the AC-2.7 ones, run against the built DB
    for _, sql, _ in SANITY_QUERIES:
        assert _q(root / "v2.db", sql)[0][0] == 0


def test_reload_is_idempotent(load_repo):
    root, ov = load_repo
    _load(root, ov)
    first = _q(root / "v2.db", "select item_id from items order by 1")
    full1 = _q(root / "v2.db", "select * from items order by 1")
    _load(root, ov)
    assert _q(root / "v2.db", "select item_id from items order by 1") == first
    assert _q(root / "v2.db", "select * from items order by 1") == full1
    assert len(first) == 2 + 15 + 2
    assert len({r[0] for r in first}) == len(first)


def test_item_id_recipe_and_ordinals(load_repo):
    root, ov = load_repo
    _load(root, ov)
    sha = _q(root / "v2.db", "select pdf_sha256 from documents where parliament=46")[0][0]
    item = {"page": 1, "section": 1, "owner": "self", "entity_name": "BHP Group Limited",
            "description": "BHP Group Limited"}
    key = item_key(sha, item)
    assert key == (sha, 1, 1, "self", "bhp group")
    ids = {r[0] for r in _q(root / "v2.db", f"select item_id from items where pdf_sha256='{sha}' "
                                            "and section=1")}
    assert ids == {item_id(key, 0), item_id(key, 1)}


def test_category_from_section(load_repo):
    root, ov = load_repo
    _load(root, ov)
    rows = dict(_q(root / "v2.db", "select section, category from items group by 1, 2"))
    assert rows == {s: CATEGORY[s] for s in range(1, 15)}
    assert CATEGORY[1] == "Shareholding" and CATEGORY[12] == "Sponsored travel/hospitality"
    assert CATEGORY[14] == "Other interest"


def test_item_fields_carried(load_repo):
    root, ov = load_repo
    _load(root, ov)
    row = _q(root / "v2.db", "select owner, entity_name_raw, entity_id, description, is_alteration, "
                             "change_type, lodged_date, date_precision, page, confidence, member_id, "
                             "chamber, parliament from items where parliament=45 and section=8")
    assert row == [("spouse", "Commonwealth Bank of Australia", None, "Savings account", 1, "added",
                    "2017-03-01", "month", 3, "medium", "jane_fixture", "house", 45)]


def test_member_resolution_and_party_join(load_repo):
    root, ov = load_repo
    s = _load(root, ov)
    assert s["resolution"] == {"pdf_members": 1, "member_aliases": 1, "slug": 1}
    assert _q(root / "v2.db", "select * from members order by 1") == [
        ("jane_fixture", "Jane Fixture", "house"), ("newbie_o_member", "Néwbie O'Member", "house")]
    terms = _q(root / "v2.db", "select * from member_terms order by 1, 3")
    assert terms == [
        ("jane_fixture", "house", 45, "Testville", "Australian Labor Party", "Labor"),
        # extraction electorate empty -> taken from the overrides
        ("jane_fixture", "house", 46, "Testville", "Independent", "Crossbench"),
        ("newbie_o_member", "house", 47, "Nowhere", None, None),
    ]
    # unknown party -> NULL, and it is listed in unknown_party.csv so not flagged
    assert s["no_party_terms"] == [("newbie_o_member", "house", 47)]
    assert s["no_party_unlisted"] == []
    assert s["slug_members"] == [("pdfs/47/newbie_47p.pdf", "newbie_o_member")]


def test_unknown_party_not_listed_is_flagged(load_repo, capsys):
    root, ov = load_repo
    write_csv(ov / "unknown_party.csv", ["member_id", "chamber", "parliament", "note"], [])
    s = _load(root, ov)
    assert s["no_party_unlisted"] == [("newbie_o_member", "house", 47)]
    from disclosures.load import print_summary
    print_summary(s)
    assert "no party and not in unknown_party.csv: newbie_o_member house 47" in capsys.readouterr().out


def test_non_member_document(load_repo):
    root, ov = load_repo
    write_csv(ov / "pdf_members.csv",
              ["pdf_path", "member_id", "canonical_full_name", "electorate_or_state", "source"],
              [["pdfs/45/fixture_45p.pdf", "", "", "", "non_member"]])
    _load(root, ov)
    assert _q(root / "v2.db", "select member_id from documents where parliament=45") == [(None,)]
    assert _q(root / "v2.db", "select count(*) from member_terms where parliament=45") == [(0,)]


def test_failed_load_keeps_previous_db(load_repo, monkeypatch):
    root, ov = load_repo
    _load(root, ov)
    before = (root / "v2.db").read_bytes()
    import disclosures.load as L

    monkeypatch.setattr(L, "CATEGORY", {})  # KeyError while building rows
    with pytest.raises(KeyError):
        _load(root, ov)
    assert (root / "v2.db").read_bytes() == before
    assert not list(root.glob("v2.db.tmp*"))


def test_refuses_v1_db(load_repo):
    root, ov = load_repo
    with pytest.raises(ValueError):
        load_db("workflow-claude", root / "disclosures.db", root / "extractions", ov)


def test_cli_load(load_repo, capsys):
    root, ov = load_repo
    rc = main(["load", "--source", "workflow-claude", "--db", str(root / "cli.db"),
               "--extractions", str(root / "extractions"), "--overrides", str(ov)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "loaded 3 files, skipped 1" in out
    assert "SKIPPED" in out and "broken_45p.json" in out
    assert "members 2, member_terms 3, items 19" in out
    assert "AC-2.7 sanity queries:" in out and "FAIL" not in out
    assert main(["load", "--source", "nope", "--db", str(root / "x.db"),
                 "--extractions", str(root / "extractions"), "--overrides", str(ov)]) == 2
    assert main(["load", "--source", "workflow-claude", "--db", str(root / "x.db"),
                 "--extractions", str(root / "extractions"), "--overrides", str(root / "none")]) == 2
    assert not (root / "x.db").exists()


def test_slug_and_name_normalisation():
    assert member_slug("Clare O'Neil") == "clare_o_neil"
    assert member_slug("  Néwbie  O'Member ") == "newbie_o_member"
    assert norm_person_name("Van Manen, Albertus Johannes") == "albertus johannes van manen"
    assert norm_person_name("Hon. Edham (Ed) Nurredin Husic MP") == "edham nurredin husic"
    assert norm_person_name("christopher_eyles_bowen") == "christopher eyles bowen"
    assert norm_electorate("Mc Mahon") == norm_electorate("McMahon") == "mcmahon"
    assert norm_electorate("Ryan, Queensland") == norm_electorate("Ryan") == "ryan"
    assert norm_electorate("Canning WA") == norm_electorate("CANNING") == "canning"


# --- the real committed overrides (data/overrides) ----------------------------------------

V1_MERGE_CASES = {
    # merge_duplicate_mps.py:29-50, (full_name, electorate) -> canonical
    "chris_bowen": [("Christopher Bowen", "Mc Mahon"), ("Christopher Eyles Bowen", "McMahon"),
                    ("chris_bowen", "McMahon"), ("christopher_bowen", "Mc Mahon"),
                    ("christopher_eyles_bowen", "McMahon"), ("Chris Bowen", "McMahon")],
    "louise_markus": [("MARKUS", "MACQUARIE"), ("markus", "MACQUARIE"), ("Louise Markus", "Macquarie")],
    "bert_van_manen": [("Albertus Van Manen", "Forde"), ("albertus_van_manen", "Forde"),
                       ("Albertus Johannes Van Manen", "Forde"), ("Bert Van Manen", "Forde"),
                       ("Van Manen, Albertus Johannes", "")],
    "milton_dick": [("DICK DUGALD MILTON", "OXLEY"), ("dick_dugald_milton", "OXLEY"),
                    ("Milton Dick", "Oxley")],
    "clare_o_neil": [("Clare O'Neil", "Hotham"), ("clare_o'neil", "HOTHAM"),
                     ("Clare Ellen O'Neil", "Hotham")],
}


@pytest.mark.parametrize("member_id", sorted(V1_MERGE_CASES))
def test_v1_merge_cases_unify(member_id):
    ov = Overrides(REAL_OVERRIDES)
    resolved = {ov.resolve_member("pdfs/99/not_a_listed_pdf.pdf", name, elec)[0]
                for name, elec in V1_MERGE_CASES[member_id]}
    assert resolved == {member_id}


V1_MERGE_CASE_PDFS = {
    "chris_bowen": ["pdfs/43/bowenc_43p.pdf", "pdfs/44/bowenc_44p.pdf", "pdfs/45/bowenc_45p.pdf",
                    "pdfs/46/bowen_46p.pdf", "pdfs/47/bowen_47p.pdf"],
    "louise_markus": ["pdfs/43/markusl_43p.pdf", "pdfs/44/markusl_44p.pdf"],
    "bert_van_manen": ["pdfs/43/vanmanenb_43p.pdf", "pdfs/44/vanmanenb_44p.pdf",
                       "pdfs/45/vanmanena_45p.pdf", "pdfs/46/van_manen_46p.pdf",
                       "pdfs/47/van_manen_47p.pdf"],
    "milton_dick": ["pdfs/45/dickm_45p.pdf", "pdfs/46/dick_46p.pdf", "pdfs/47/dick_47p.pdf"],
    "clare_o_neil": ["pdfs/44/oneilc44p.pdf", "pdfs/45/oneilc45p.pdf", "pdfs/46/oneil_46p.pdf",
                     "pdfs/47/oneil_47p.pdf"],
}


def test_v1_merge_case_pdfs_unify():
    """Every PDF of a v1 duplicate-MP case attaches to the one member_id, and no other PDF does."""
    ov = Overrides(REAL_OVERRIDES)
    for mid, pdfs in V1_MERGE_CASE_PDFS.items():
        assert {ov.resolve_member(p, "whatever", "")[0] for p in pdfs} == {mid}
        assert sorted(p for p, r in ov.pdf_members.items() if r["member_id"] == mid) == pdfs


def test_real_overrides_cover_all_tracked_pdfs():
    import subprocess

    tracked = subprocess.run(["git", "ls-files", "pdfs"], cwd=REPO, capture_output=True, text=True,
                             check=True).stdout.split()
    tracked = sorted(p for p in tracked if p.lower().endswith(".pdf"))
    ov = Overrides(REAL_OVERRIDES)
    assert sorted(ov.pdf_members) == tracked
    with open(REAL_OVERRIDES / "pdf_members.csv", newline="") as fh:
        paths = [r["pdf_path"] for r in csv.DictReader(fh)]
    assert paths == sorted(paths)  # reviewable: sorted by path
    # every (member, parliament) with a PDF has a party, or is listed as unknown
    for path, r in ov.pdf_members.items():
        if r["member_id"]:
            key = (r["member_id"], "house", int(path.split("/")[1]))
            assert key in ov.party_terms or key in ov.unknown_party, key
            pt = ov.party_terms.get(key)
            if pt:
                assert pt["political_bloc"] in {"Coalition", "Labor", "Crossbench"}
    with open(REAL_OVERRIDES / "unknown_party.csv", newline="") as fh:
        assert len(list(csv.DictReader(fh))) <= 5


def test_refuses_v1_db_case_variants(load_repo, tmp_path):
    """macOS APFS is case-insensitive: DISCLOSURES.DB is the v1 file (verifier finding)."""
    root, _ = load_repo
    (root / "disclosures.db").write_bytes(b"v1 stand-in")
    for name in ("DISCLOSURES.DB", "Disclosures.db", "./DISCLOSURES.db"):
        with pytest.raises(ValueError):
            load_db("workflow-claude", name, root / "extractions", root / "data" / "overrides")
    assert (root / "disclosures.db").read_bytes() == b"v1 stand-in"


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root ignores chmod")
def test_unwritable_target_exits_2(load_repo, capsys):
    root, _ = load_repo
    ro = root / "readonly"
    ro.mkdir()
    ro.chmod(0o500)
    try:
        rc = main(["load", "--source", "workflow-claude", "--db", str(ro / "out.db"),
                   "--extractions", str(root / "extractions"), "--overrides", str(root / "data" / "overrides")])
    finally:
        ro.chmod(0o700)
    assert rc == 2
    assert "load:" in capsys.readouterr().err
