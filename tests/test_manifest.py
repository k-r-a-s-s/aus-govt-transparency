"""pdfs/manifest.csv (ADR-8, AC-4.3) and the listing matcher behind its back-fill."""
import csv
import hashlib
import subprocess
from pathlib import Path

import pytest

from disclosures import manifest as M
from disclosures import sources as S

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures" / "aph"


def tracked():
    out = subprocess.run(["git", "ls-files", "pdfs"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout.split("\n")
    return sorted(p for p in out if M.is_source_document(p))


def test_ac_4_3_manifest_covers_every_tracked_pdf_and_shas_match():
    with open(ROOT / "pdfs" / "manifest.csv", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == M.COLUMNS
        rows = list(reader)
    paths = [r["pdf_path"] for r in rows]
    assert len(paths) == len(set(paths))
    # row count == `git ls-files pdfs | grep -c '\.pdf$'` plus the Senate JSON statements
    assert sorted(paths) == tracked()
    for r in rows:
        h = hashlib.sha256((ROOT / r["pdf_path"]).read_bytes()).hexdigest()
        assert r["pdf_sha256"] == h, r["pdf_path"]
        assert r["parliament"] == r["pdf_path"].split("/")[-2], r["pdf_path"]
        senate = r["pdf_path"].startswith("pdfs/senate/")
        assert r["chamber"] == ("senate" if senate else "house") and int(r["page_count"]) > 0
        assert r["source_url"] == "" or S.statement_url_kind(r["source_url"]) is not None
    statements = [r for r in rows if r["member_name"]]
    assert sum(1 for r in statements if r["source_url"]) / len(statements) > 0.95


def test_link_stem():
    assert M.link_stem("https://static.aph.gov.au/-/media/x/45p/AB/AlexanderJ_45P_2.pdf?rev=1&hash=2") \
        == "alexanderj_45p_2"
    assert M.link_stem("https://www.aph.gov.au/P/C/H?url=pmi/declarations/abbotta_43p.pdf") \
        == "abbotta_43p"


def _member(name, seat):
    return {"member_id": name.lower().replace(" ", "_"), "canonical_full_name": name,
            "electorate_or_state": seat}


def test_match_listing_stem_then_seat_and_surname():
    rows = S.parse_register((FIX / "house_46_register.html").read_text(), 46)
    alb = next(r for r in rows if r.surname == "Albanese")
    aly = next(r for r in rows if r.surname == "Aly")
    pdfs = {
        "pdfs/46/albanese_46p.pdf": _member("Anthony Albanese", "Grayndler"),  # stem
        "pdfs/46/alya_46p.pdf": _member("Anne Aly", "Cowan"),                 # seat + surname
        "pdfs/46/nobody_46p.pdf": _member("No Body", "Nowhere"),
        "pdfs/46/interestsr_46p.pdf": {},
    }
    got = M.match_listing(pdfs, rows)
    assert got == {"pdfs/46/albanese_46p.pdf": (alb.url, alb.listed_date),
                   "pdfs/46/alya_46p.pdf": (aly.url, aly.listed_date)}


def test_match_listing_never_gives_one_row_to_two_pdfs():
    rows = S.parse_register((FIX / "house_46_register.html").read_text(), 46)
    pdfs = {"pdfs/46/alya_46p.pdf": _member("Anne Aly", "Cowan"),
            "pdfs/46/alyanne_46p.pdf": _member("Anne Aly", "Cowan")}
    assert M.match_listing(pdfs, rows) == {}


def test_match_listing_extra_links_have_no_date():
    url = "https://static.aph.gov.au/-/media/R/Explanatory_notes/Explanatory_Notes___Booklet_1.pdf?rev=9"
    got = M.match_listing({"pdfs/46/explanatory_notes___booklet_1.pdf": {}}, [], [url])
    assert got == {"pdfs/46/explanatory_notes___booklet_1.pdf": (url, "")}


def test_page_pdf_links_include_non_member_links():
    html = ('<a href="/x/Explanatory_Notes.pdf?rev=1&amp;hash=2">notes</a>'
            '<a href="/x/page.htm">not a pdf</a>')
    assert M.page_pdf_links(html, "https://static.aph.gov.au/a/b") == \
        ["https://static.aph.gov.au/x/Explanatory_Notes.pdf?rev=1&hash=2"]


def test_write_manifest_sorted_and_round_trips(tmp_path):
    p = tmp_path / "m.csv"
    rows = [{c: "" for c in M.COLUMNS} | {"pdf_path": "pdfs/47/b.pdf", "parliament": "47"},
            {c: "" for c in M.COLUMNS} | {"pdf_path": "pdfs/43/a.pdf", "parliament": "43"}]
    M.write_manifest(rows, p)
    back = M.read_manifest(p)
    assert [r["pdf_path"] for r in back] == ["pdfs/43/a.pdf", "pdfs/47/b.pdf"]
    assert list(back[0]) == M.COLUMNS
