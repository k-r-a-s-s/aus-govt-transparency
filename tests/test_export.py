import csv
import json
import sqlite3
from pathlib import Path

import pytest

from disclosures.cli import main
from disclosures.export import COLUMNS, CSV_NAME, HEADER, export
from disclosures.load import DDL

ITEM = ("insert into items (item_id, pdf_sha256, member_id, chamber, parliament, section, "
        "subsection, category, owner, entity_name_raw, entity_id, description, is_alteration, "
        "change_type, lodged_date, date_precision, page, confidence) "
        "values (?,?,?,?,?,?,?,?,?,?,?,?,0,'initial','2022-07-01','day',?, 'high')")


def make_db(path: Path) -> Path:
    con = sqlite3.connect(path)
    con.executescript(DDL)
    con.executemany("insert into members values (?,?,?)",
                    [("jane_doe", "Jane Doe", "house"), ("sam_roe", "Sam Roe", "senate")])
    con.executemany("insert into member_terms values (?,?,?,?,?,?)",
                    [("jane_doe", "house", 47, "Wills", "ALP", "Labor"),
                     ("jane_doe", "house", 48, "Wills", "ALP", "Labor"),
                     ("sam_roe", "senate", 48, "Tasmania", "IND", "Crossbench")])
    con.executemany("insert into documents (pdf_sha256, pdf_path, chamber, parliament, "
                    "member_id, page_count, source_url, statement_date, extraction_source, "
                    "model) values (?,?,?,?,?,?,?,?,?,?)",
                    [("sha47", "pdfs/47/doej_47p.pdf", "house", 47, "jane_doe", 3, None,
                      "2022-07-01", "gemini-api", "google/gemini-3.8-flash"),
                     ("sha48", "pdfs/48/doej_48p.pdf", "house", 48, "jane_doe", 2,
                      "https://example.org/doej_48p.pdf", None, "gemini-api", "m"),
                     ("shas", "pdfs/senate/48/roes_48s.json", "senate", 48, "sam_roe", 1,
                      None, None, "senate-json", "api")])
    con.execute("insert into entities values ('bhp_group', 'BHP Group', 'listed_company', "
                "'BHP')")
    con.executemany("insert into entity_aliases values (?,?,?,?)",
                    [("bhp group", "bhp_group", "curated", None),
                     ("family trust", None, "generic", None)])
    con.executemany(ITEM, [
        ("i1", "sha47", "jane_doe", "house", 47, 1, None, "Shareholding", "self",
         "BHP Group Ltd", "bhp_group", "BHP Group Ltd", 2),
        ("i2", "sha47", "jane_doe", "house", 47, 2, "2(i)", "Trust", "spouse",
         "Family Trust", None, "Family Trust, beneficiary", 1),
        ("i3", "sha48", "jane_doe", "house", 48, 3, None, "Real estate", "self", None, None,
         "House, Melbourne", 1),
        ("i4", "shas", "sam_roe", "senate", 48, 11, None, "Gift", "self", "BHP group",
         "bhp_group", "Tickets, BHP group", 1),
    ])
    con.execute("insert into meta values ('schema_version', '2.0')")
    con.commit()
    con.close()
    return path


def write_manifest(path: Path) -> Path:
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["chamber", "parliament", "member_name", "electorate_or_state", "source_url",
                    "listed_date", "pdf_path", "pdf_sha256", "page_count", "fetched_at"])
        w.writerow(["house", 47, "Jane Doe", "Wills", "https://example.org/doej_47p.pdf", "",
                    "pdfs/47/doej_47p.pdf", "sha47", 3, ""])
    return path


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def exported(tmp_path):
    db = make_db(tmp_path / "v2.db")
    out = tmp_path / "exports"
    s = export(db, out, write_manifest(tmp_path / "manifest.csv"))
    return db, out, s


def test_one_row_per_item_with_joins(exported):
    db, out, s = exported
    rows = read_csv(out / CSV_NAME)
    n = sqlite3.connect(db).execute("select count(*) from items").fetchone()[0]
    assert s["rows"] == len(rows) == n == 4
    assert list(rows[0]) == HEADER
    by_id = {r["item_id"]: r for r in rows}
    i1 = by_id["i1"]
    assert (i1["member_name"], i1["party"], i1["political_bloc"], i1["electorate_or_state"]) == \
        ("Jane Doe", "ALP", "Labor", "Wills")
    assert (i1["entity_name"], i1["entity_type"], i1["entity_asx_code"],
            i1["entity_match_method"]) == ("BHP Group", "listed_company", "BHP", "curated")
    assert i1["statement_date"] == "2022-07-01" and i1["page"] == "2"
    assert by_id["i2"]["entity_match_method"] == "generic" and by_id["i2"]["entity_id"] == ""
    assert by_id["i2"]["subsection"] == "2(i)"
    assert by_id["i3"]["entity_name_as_printed"] == "" and by_id["i3"]["entity_match_method"] == ""
    assert by_id["i4"]["party"] == "IND" and by_id["i4"]["entity_id"] == "bhp_group"


def test_source_url_from_db_then_manifest(exported):
    _, out, s = exported
    urls = {r["item_id"]: r["source_url"] for r in read_csv(out / CSV_NAME)}
    assert urls["i1"] == "https://example.org/doej_47p.pdf"  # manifest fallback
    assert urls["i3"] == "https://example.org/doej_48p.pdf"  # documents.source_url
    assert urls["i4"] == "" and s["no_source_url"] == 1


def test_kaggle_package(exported):
    _, out, _ = exported
    k = out / "kaggle"
    assert (k / CSV_NAME).read_bytes() == (out / CSV_NAME).read_bytes()
    readme = (k / "README.md").read_text()
    for col in HEADER:  # AC-5.1: the field dictionary covers every CSV column
        assert f"| `{col}` |" in readme
    assert "prompt v0" in readme and "untyped" in readme
    assert "| house | 47 | 1 | 1 | 2 |" in readme
    meta = json.loads((k / "dataset-metadata.json").read_text())
    assert meta["id"].count("/") == 1 and meta["licenses"][0]["name"]
    assert [f["name"] for f in meta["resources"][0]["schema"]["fields"]] == HEADER
    assert len(HEADER) == len(set(HEADER)) == len(COLUMNS)


def test_deterministic(tmp_path, exported):
    db, out, _ = exported
    out2 = tmp_path / "again"
    export(db, out2, tmp_path / "missing_manifest.csv")
    export(db, out2, tmp_path / "manifest.csv")
    for rel in (CSV_NAME, "kaggle/README.md", "kaggle/dataset-metadata.json"):
        assert (out / rel).read_bytes() == (out2 / rel).read_bytes()


def test_db_is_not_modified(exported):
    db, out, _ = exported
    before = db.read_bytes()
    export(db, out, out / "none.csv")
    assert db.read_bytes() == before


def test_row_count_mismatch_refuses(tmp_path):
    db = make_db(tmp_path / "v2.db")
    con = sqlite3.connect(db)
    con.execute("insert into member_terms values ('jane_doe', 'house', 47, 'Wills', 'ALP', "
                "'Labor') on conflict do nothing")
    # an item whose document is missing would be dropped by the join
    con.execute("pragma foreign_keys = off")
    con.execute(ITEM, ("i9", "nodoc", "jane_doe", "house", 47, 1, None, "Shareholding", "self",
                       None, None, "x", 1))
    con.commit()
    con.close()
    with pytest.raises(RuntimeError, match="4 rows but items has 5"):
        export(db, tmp_path / "out", tmp_path / "m.csv")
    assert not (tmp_path / "out" / CSV_NAME).exists()


def test_cli(tmp_path, capsys):
    db = make_db(tmp_path / "v2.db")
    rc = main(["export", "--db", str(db), "--out", str(tmp_path / "x"),
               "--manifest", str(tmp_path / "none.csv"), "--kaggle-id", "kev/test-ds",
               "--license", "CC-BY-4.0"])
    assert rc == 0 and "4 rows" in capsys.readouterr().out
    meta = json.loads((tmp_path / "x/kaggle/dataset-metadata.json").read_text())
    assert meta["id"] == "kev/test-ds" and meta["licenses"] == [{"name": "CC-BY-4.0"}]
    assert main(["export", "--db", str(tmp_path / "missing.db")]) == 2
