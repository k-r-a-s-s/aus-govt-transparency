"""disclosures.scrape (AC-4.2, AC-4.4): recorded 48th listing + fake statement PDFs served by an
httpx MockTransport. No network."""
import csv
import io
from pathlib import Path

import httpx
import pymupdf
import pytest

from disclosures import manifest as M
from disclosures import scrape as SC
from disclosures import sources as S

FIX = Path(__file__).parent / "fixtures" / "aph"
LISTING = (FIX / "house_48_register.html").read_text()


def fake_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


class Server:
    """Serves the 48th listing and one distinct PDF per statement URL; records requests."""

    def __init__(self, listing=LISTING):
        self.listing = listing
        self.pdfs = {}
        self.requests = []

    def __call__(self, request: httpx.Request):
        url = str(request.url)
        self.requests.append(url)
        assert request.headers["user-agent"] == S.BROWSER_UA
        if url == S.HOUSE_REGISTER_URLS[48]:
            return httpx.Response(200, text=self.listing)
        if S.statement_url_kind(url):
            data = self.pdfs.setdefault(SC.url_key(url), fake_pdf(url))
            return httpx.Response(200, content=data, headers={"content-type": "application/pdf"})
        return httpx.Response(404)

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self))


def run(root, server, **kw):
    out = io.StringIO()
    counts = SC.scrape("house", 48, root=root, client=server.client(), out=out, delay=0,
                       now=lambda: "2026-10-03T00:00:00Z", **kw)
    return counts, out.getvalue()


@pytest.fixture
def root(tmp_path):
    (tmp_path / "pdfs").mkdir()
    # one pre-existing v1 row that must survive the upsert
    M.write_manifest([{"chamber": "house", "parliament": "47", "member_name": "X",
                       "electorate_or_state": "Y", "pdf_path": "pdfs/47/x_47p.pdf",
                       "pdf_sha256": "0" * 64, "page_count": "1"}], tmp_path / M.MANIFEST_PATH)
    return tmp_path


def rows48(root):
    return [r for r in M.read_manifest(root / M.MANIFEST_PATH) if r["parliament"] == "48"]


def test_ac_4_2_downloads_both_link_kinds_and_writes_manifest(root):
    srv = Server()
    counts, log = run(root, srv)
    assert counts == dict(listed=151, new=151, changed=0, unchanged=0, refused=0, failed=0)
    r = rows48(root)
    assert 150 <= len(r) <= 155
    assert {S.statement_url_kind(x["source_url"]) for x in r} == {"api", "pdf"}
    assert len({x["pdf_path"] for x in r}) == 151
    for x in r:
        assert x["pdf_path"].startswith("pdfs/48/") and x["pdf_path"].endswith("_48p.pdf") \
            or "_48p_" in x["pdf_path"]
        assert M.sha256_file(root / x["pdf_path"]) == x["pdf_sha256"]
        assert x["page_count"] == "1" and x["listed_date"] and x["fetched_at"]
    abdo = next(x for x in r if x["member_name"] == "Basem Abdo")
    assert (abdo["pdf_path"], abdo["electorate_or_state"], abdo["listed_date"]) == \
        ("pdfs/48/abdob_48p.pdf", "Calwell", "2025-10-10")
    assert any(x["pdf_path"] == "pdfs/48/albanesea_48p.pdf" for x in r)
    assert len(M.read_manifest(root / M.MANIFEST_PATH)) == 152  # v1 row kept
    assert "scrape house 48: 151 listed, 151 new, 0 changed" in log


def test_ac_4_4_second_run_downloads_nothing(root):
    srv = Server()
    run(root, srv)
    before = (root / M.MANIFEST_PATH).read_bytes()
    srv.requests.clear()
    counts, log = run(root, srv)
    assert "0 new, 0 changed" in log
    assert counts["unchanged"] == 151
    assert srv.requests == [S.HOUSE_REGISTER_URLS[48]]  # listing only
    assert (root / M.MANIFEST_PATH).read_bytes() == before


def test_new_listing_date_same_bytes_is_unchanged_but_row_refreshed(root):
    srv = Server()
    run(root, srv)
    abdo_url = "https://interests-register-api-public.aph.gov.au/api/members/316915/statement/48"
    srv.listing = LISTING.replace("10 October 2025", "1 December 2025")  # Abdo's row only
    srv.requests.clear()
    counts, log = run(root, srv)
    assert (counts["new"], counts["changed"], counts["unchanged"]) == (0, 0, 151)
    assert srv.requests == [S.HOUSE_REGISTER_URLS[48], abdo_url]
    abdo = next(x for x in rows48(root) if x["pdf_path"] == "pdfs/48/abdob_48p.pdf")
    assert abdo["listed_date"] == "2025-12-01" and abdo["fetched_at"] == "2026-10-03T00:00:00Z"


def test_changed_bytes_overwrite_in_place(root):
    srv = Server()
    run(root, srv)
    alb = next(x for x in rows48(root) if x["pdf_path"] == "pdfs/48/albanesea_48p.pdf")
    # APH replaces the file: new ?rev= on the static link, new bytes
    new_url = alb["source_url"].split("?")[0] + "?rev=new"
    srv.listing = LISTING.replace(alb["source_url"].split("?")[1], "rev=new")
    srv.pdfs[SC.url_key(new_url)] = fake_pdf("replaced statement")
    counts, log = run(root, srv)
    assert (counts["new"], counts["changed"]) == (0, 1)
    after = next(x for x in rows48(root) if x["pdf_path"] == "pdfs/48/albanesea_48p.pdf")
    assert after["source_url"] == new_url and after["pdf_sha256"] != alb["pdf_sha256"]
    assert M.sha256_file(root / after["pdf_path"]) == after["pdf_sha256"]
    assert "changed pdfs/48/albanesea_48p.pdf" in log


def test_verify_redownloads_everything(root):
    srv = Server()
    run(root, srv)
    srv.requests.clear()
    counts, log = run(root, srv, verify=True)
    assert len(srv.requests) == 152 and counts["unchanged"] == 151
    assert "0 new, 0 changed" in log


def test_refuses_files_over_limit(root, monkeypatch):
    monkeypatch.setattr(SC, "MAX_BYTES", 100)
    counts, log = run(root, Server(), limit=3)
    assert counts["refused"] == 3 and counts["new"] == 0
    assert "REFUSED" in log and not list((root / "pdfs" / "48").glob("*.pdf"))
    assert rows48(root) == []


def test_non_pdf_body_fails_without_writing(root):
    srv = Server()
    srv.pdfs = type("D", (dict,), {"setdefault": lambda self, k, v: b"<html>login</html>"})()
    counts, log = run(root, srv, limit=2)
    assert counts["failed"] == 2 and "not a PDF" in log
    assert rows48(root) == []


def test_only_current_house_parliament(root):
    with pytest.raises(ValueError, match="back-filled"):
        SC.scrape("house", 47, root=root, client=Server().client())


def _row(surname, given, url="https://x/a.pdf"):
    return S.RegisterRow(48, "2025-01-01", "", surname, given, "Seat", "NSW", url, "pdf")


def test_file_name_collisions_and_ascii():
    assert SC.file_name(_row("O'Dowd", "Ken"), set()) == "odowdk_48p.pdf"
    assert SC.file_name(_row("Van Manen", "Bert"), set()) == "vanmanenb_48p.pdf"
    assert SC.file_name(_row("Bürney", "Linda"), set()) == "burneyl_48p.pdf"
    taken = {"smithj_48p.pdf"}
    assert SC.file_name(_row("Smith", "John"), taken) == "smithjohn_48p.pdf"
    taken.add("smithjohn_48p.pdf")
    assert SC.file_name(_row("Smith", "John"), taken) == "smithjohn_48p_2.pdf"


def test_url_key_ignores_query():
    assert SC.url_key("https://static.aph.gov.au/a/B.pdf?rev=1") == \
        SC.url_key("https://STATIC.aph.gov.au/a/b.pdf?rev=2")
