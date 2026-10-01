import csv
import json
from pathlib import Path

import pytest
from conftest import write_json

from disclosures import gold

REPO = Path(__file__).resolve().parent.parent
SELECTION = REPO / "eval" / "gold" / "selection.json"
GOLD_DIR = REPO / "eval" / "gold"


@pytest.fixture(scope="module")
def selection():
    return json.loads(SELECTION.read_text())


def _gold_docs():
    return [json.loads(f.read_text()) for f in gold.gold_files(GOLD_DIR)]


def test_selection_metadata(selection):
    assert isinstance(selection["seed"], int)
    assert selection["generated_at"] and selection["method"]
    assert 12 <= len(selection["pdfs"]) <= 15
    paths = [p["pdf_path"] for p in selection["pdfs"]]
    assert len(set(paths)) == len(paths)
    for p in selection["pdfs"]:
        assert (REPO / p["pdf_path"]).is_file()
        assert {"pdf_path", "parliament", "page_count", "no_text_fraction", "strata",
                "heuristic_spouse", "heuristic_alteration"} <= p.keys()


def test_selection_covers_coverable_strata(selection):
    pdfs = selection["pdfs"]
    assert {p["parliament"] for p in pdfs} >= {43, 44, 45, 46, 47}
    assert sum(p["page_count"] > 30 for p in pdfs) >= 3
    assert sum(p["no_text_fraction"] > 0.70 for p in pdfs) >= 3
    stats = gold.read_stats(REPO / "eval" / "pdf_stats.csv")
    max_pages = max(r["page_count"] for r in stats)
    assert max_pages == 81
    assert any(p["page_count"] == max_pages and "max_pages" in p["strata"] for p in pdfs)


def test_selection_strata_tags_consistent_with_stats(selection):
    stats = {r["pdf_path"]: r for r in gold.read_stats(REPO / "eval" / "pdf_stats.csv")}
    for p in selection["pdfs"]:
        s = stats[p["pdf_path"]]
        assert s["is_statement"]
        assert p["page_count"] == s["page_count"]
        assert f"parliament_{s['parliament']}" in p["strata"]
        assert ("gt30pages" in p["strata"]) == (s["page_count"] > 30)
        assert ("no_text_gt70" in p["strata"]) == (s["no_text_fraction"] > 0.70)


def test_stats_csv_covers_all_pdfs():
    stats = gold.read_stats(REPO / "eval" / "pdf_stats.csv")
    on_disk = sorted(p.relative_to(REPO).as_posix() for p in (REPO / "pdfs").glob("[0-9][0-9]/*.pdf"))
    assert sorted(r["pdf_path"] for r in stats) == on_disk


def test_select_is_deterministic_for_seed():
    stats = gold.read_stats(REPO / "eval" / "pdf_stats.csv")
    a = gold.select(stats, seed=7, n=12)
    b = gold.select(stats, seed=7, n=12)
    assert a == b and len(a) == 12


def test_gold_content_strata():
    docs = _gold_docs()
    if not docs:
        pytest.skip("no eval/gold/*.json yet: spouse/dependent and alteration-heavy strata are "
                    "judged from gold content, which is drafted in Phase 1b")
    spouse = sum(any(i["owner"] in ("spouse", "dependent_child") for i in d["items"]) for d in docs)
    alter = sum(sum(bool(i["is_alteration"]) for i in d["items"]) >= 5 for d in docs)
    assert spouse >= 2, f"only {spouse} gold PDFs have spouse/dependent items"
    assert alter >= 2, f"only {alter} gold PDFs are alteration-heavy (>=5 alteration items)"


# --- review sheet ---------------------------------------------------------------

def _gold_doc(stem, items):
    return {"pdf_path": f"pdfs/45/{stem}.pdf", "items": items, "reviewed_by": None, "reviewed_at": None}


def _it(page, section, entity, confidence="high"):
    return {"section": section, "subsection": None, "owner": "self", "entity_name": entity,
            "description": entity, "change_type": "initial", "lodged_date": None, "page": page,
            "confidence": confidence}


def test_review_sheet_header_only_when_empty(tmp_path):
    write_json(tmp_path / "selection.json", {"seed": 1})
    assert gold.write_review_sheet(tmp_path) == 0
    rows = list(csv.reader(open(tmp_path / "review.csv")))
    assert rows == [gold.REVIEW_FIELDS]
    assert gold.REVIEW_FIELDS == ["stem", "page", "section", "subsection", "owner", "entity_name",
                                  "description", "change_type", "lodged_date", "confidence",
                                  "kevin_ok", "kevin_fix"]


def test_review_sheet_sorted_and_apply_review(tmp_path):
    write_json(tmp_path / "b_45p.json", _gold_doc("b_45p", [_it(2, 8, "ANZ"), _it(1, 1, "BHP")]))
    write_json(tmp_path / "a_45p.json", _gold_doc("a_45p", [_it(3, 4, "Acme", "medium"), _it(3, 1, "CSL")]))
    assert gold.write_review_sheet(tmp_path) == 4
    with open(tmp_path / "review.csv") as fh:
        rows = list(csv.DictReader(fh))
    assert [(r["stem"], r["page"], r["section"]) for r in rows] == [
        ("a_45p", "3", "1"), ("a_45p", "3", "4"), ("b_45p", "1", "1"), ("b_45p", "2", "8")]
    assert rows[0]["subsection"] == "" and rows[0]["kevin_ok"] == "" and rows[0]["kevin_fix"] == ""
    assert [r["confidence"] for r in rows] == ["high", "medium", "high", "high"]
    assert gold.REVIEW_FIELDS[-3:] == ["confidence", "kevin_ok", "kevin_fix"]

    # tick all of a_45p, only one row of b_45p
    for r in rows:
        if r["stem"] == "a_45p" or r["page"] == "1":
            r["kevin_ok"] = "y"
    with open(tmp_path / "review.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=gold.REVIEW_FIELDS)
        w.writeheader()
        w.writerows(rows)
    res = gold.apply_review(tmp_path, today="2026-10-02")
    assert res == {"reviewed": ["a_45p"], "unreviewed": ["b_45p"]}
    a = json.loads((tmp_path / "a_45p.json").read_text())
    b = json.loads((tmp_path / "b_45p.json").read_text())
    assert (a["reviewed_by"], a["reviewed_at"]) == ("kevin", "2026-10-02")
    assert b["reviewed_by"] is None
