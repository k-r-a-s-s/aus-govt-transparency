"""disclosures.senate (ADR-9, D3): the Senate API adapter and scraper, on recorded payloads
(the 48th listing plus two senators' statements) served by an httpx MockTransport. No network."""
import io
import json
import shutil
from pathlib import Path

import httpx
import pytest

from disclosures import manifest as M
from disclosures import senate as SE
from disclosures import sources as S
from disclosures.validate import validate_file

FIX = Path(__file__).parent / "fixtures" / "senate"
LISTING = json.loads((FIX / "query_statements.json").read_text())
ALLMAN = json.loads((FIX / "statement_298839.json").read_text())   # alterations: Deletion, Addition
CICCONE = json.loads((FIX / "statement_281503.json").read_text())  # trusts, a NIL partnership


def test_listing_fixture_has_76_senators_with_distinct_file_names():
    rows = LISTING["statementOfRegisterableInterests"]
    assert len(rows) == LISTING["rowCount"] == 76
    taken = set()
    for r in rows:
        taken.add(SE.file_name(r["name"], 48, taken))
    assert len(taken) == 76
    assert "allmanpaynep_48s.json" in taken and "cicconer_48s.json" in taken


def test_file_name_collisions():
    taken = {"smithd_48s.json"}
    assert SE.file_name("Smith, Dean", 48, taken) == "smithdean_48s.json"
    taken.add("smithdean_48s.json")
    assert SE.file_name("Smith, Dean", 48, taken) == "smithdean_48s_2.json"


def test_dates_are_sydney_calendar_dates():
    assert SE.utc_to_local_date("2025-11-11T21:00:00Z") == "2025-11-12"   # 08:00 AEDT
    assert SE.utc_to_local_date("2026-05-13T09:00:00Z") == "2026-05-13"   # 19:00 AEST
    assert SE.utc_to_local_date("8/14/2025 1:31:50 PM") == "2025-08-14"
    assert SE.utc_to_local_date("2026-05-25T17:07:53") == "2026-05-26"    # listing: no Z, UTC
    assert SE.utc_to_local_date("") is None


def test_every_section_key_is_mapped_to_1_to_14():
    assert sorted(n for n, _ in SE.SECTIONS.values()) == list(range(1, 15))
    keys = set(ALLMAN) - SE.NON_SECTION_KEYS
    assert keys == set(SE.SECTIONS)


def test_interests_and_alterations_allman_payne():
    items = SE.payload_items(ALLMAN)
    by = lambda **kw: [i for i in items if all(i[k] == v for k, v in kw.items())]  # noqa: E731
    homes = by(section=3, is_alteration=False)
    assert [(i["location"], i["purpose"]) for i in homes] == [
        ("South Gladstone, Queensland", "Residential"),
        ("Cleveland, Queensland", "Investment (former home)")]
    assert all(i["change_type"] == "initial" and i["lodged_date"] == "2025-08-14" and
               i["date_precision"] == "day" for i in by(is_alteration=False))
    [sold] = by(section=3, is_alteration=True)
    assert sold["change_type"] == "removed" and sold["lodged_date"] == "2025-11-12"
    assert sold["description"] == "Investment property at Cleveland QLD (sold)"
    [shirt] = by(section=11)
    assert shirt["change_type"] == "added" and shirt["lodged_date"] == "2026-05-13"
    assert {i["entity_name"] for i in by(section=6, is_alteration=False)} == {"Auswide Bank"}
    assert {i["entity_name"] for i in by(section=8)} == {"Auswide Bank", "Suncorp Bank"}
    assert by(section=9)[0]["entity_name"] is None
    assert len(by(section=13)) == 5
    assert all(i["owner"] == "self" and i["page"] == 1 and i["confidence"] == "high"
               for i in items)
    assert len(items) == 17  # 3 + 3 + 2 + 1 + 1 + 1 + 5 + 1


def test_trust_subsections_and_nil_rows_ciccone():
    items = SE.payload_items(CICCONE)
    trusts = [i for i in items if i["section"] == 2]
    assert [i["subsection"] for i in trusts] == ["2(ii)", "2(i)"]
    assert trusts[0]["entity_name"] == "CICC1 Pty Ltd ATF The Ciccone Trust"
    assert trusts[0]["description"] == ("CICC1 Pty Ltd ATF The Ciccone Trust; "
                                        "Property investment; Joint beneficiary")
    assert not [i for i in items if i["section"] == 5]  # "NIL", "-", "-" is not an item
    assert sum(i["is_alteration"] for i in items) == 9


def test_unmapped_keys_are_errors_not_drops():
    bad = json.loads(json.dumps(ALLMAN))
    bad["cryptoAssets"] = {"interests": [], "alterations": []}
    with pytest.raises(SE.AdapterError, match="cryptoAssets"):
        SE.payload_items(bad)
    bad = json.loads(json.dumps(ALLMAN))
    bad["gifts"]["interests"].append({"detailOfGifts": "x", "valueOfGift": "1", "id": "z"})
    with pytest.raises(SE.AdapterError, match="valueOfGift"):
        SE.payload_items(bad)
    bad = json.loads(json.dumps(ALLMAN))
    bad["trusts"]["interests"].append({"nameOfCompany": "T", "nature": "", "interest": "",
                                       "type": "settlor", "id": "z"})
    with pytest.raises(SE.AdapterError, match="trust type"):
        SE.payload_items(bad)


def test_alteration_types():
    p = json.loads(json.dumps(ALLMAN))
    p["otherInterest"]["alterations"] = [
        {"alterationType": t, "details": f"d{n}", "createdOn": "2026-01-01T00:00:00Z", "id": n}
        for n, t in enumerate(["Addition", "Deletion", "Variation", "Change", "Other", None])]
    got = [i["change_type"] for i in SE.payload_items(p)
           if i["section"] == 14 and i["is_alteration"]]
    assert got == ["added", "removed", "varied", "varied", "unknown", "unknown"]


def _source(root, payload, name="allmanpaynep_48s.json"):
    d = root / "pdfs" / "senate" / "48"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_bytes(SE.dump(payload))
    return f"pdfs/senate/48/{name}"


def test_adapt_writes_valid_extractions_and_is_idempotent(tmp_path):
    rel = _source(tmp_path, ALLMAN)
    out = io.StringIO()
    assert SE.adapt_paths([rel, "pdfs/senate/48/_query_statements.json"], root=tmp_path,
                          out=out) == 0
    dest = tmp_path / "extractions/senate-json/senate/48/allmanpaynep_48s.json"
    doc = json.loads(dest.read_text())
    assert (doc["source_id"], doc["chamber"], doc["parliament"], doc["page_count"],
            doc["pages_covered"], doc["statement_date"]) == (
        "senate-json", "senate", 48, 1, [1], "2025-08-14")
    assert doc["member_name_as_printed"] == "Allman-Payne, Penny"
    assert doc["electorate_or_state"] == "Queensland"
    assert validate_file(dest, root=tmp_path) == []
    before = dest.read_bytes()
    out = io.StringIO()
    SE.adapt_paths([rel], root=tmp_path, out=out)
    assert "0 written, 1 unchanged" in out.getvalue() and dest.read_bytes() == before


def test_validate_json_source_checks_sha_and_page_count(tmp_path):
    rel = _source(tmp_path, ALLMAN)
    SE.adapt_paths([rel], root=tmp_path, out=io.StringIO())
    dest = tmp_path / "extractions/senate-json/senate/48/allmanpaynep_48s.json"
    doc = json.loads(dest.read_text())
    doc["page_count"], doc["pages_covered"] = 2, [1, 2]
    dest.write_text(json.dumps(doc))
    assert any("!= 1 for a JSON source" in e for e in validate_file(dest, root=tmp_path))
    (tmp_path / rel).write_bytes(SE.dump(CICCONE))
    SE.adapt_paths([rel], root=tmp_path, out=io.StringIO(), force=True)
    _source(tmp_path, ALLMAN)
    assert any("pdf_sha256 mismatch" in e for e in validate_file(dest, root=tmp_path))


class Server:
    """Serves the recorded listing (cut to two senators) and their statements."""

    def __init__(self):
        rows = [r for r in LISTING["statementOfRegisterableInterests"]
                if r["cdapId"] in ("298839", "281503")]
        self.listing = dict(LISTING, statementOfRegisterableInterests=rows, rowCount=2)
        self.statements = {"298839": ALLMAN, "281503": CICCONE}
        self.requests = []

    def __call__(self, request: httpx.Request):
        url = str(request.url)
        self.requests.append(url)
        assert request.headers["user-agent"] == S.BROWSER_UA
        assert request.headers["origin"] == "https://www.aph.gov.au"
        if url == SE.list_url():
            return httpx.Response(200, json=self.listing)
        cid = request.url.params.get("cdapid")
        if url.startswith(f"{S.SENATE_API_BASE}/getSenatorStatement") and cid in self.statements:
            return httpx.Response(200, json=self.statements[cid])
        return httpx.Response(404)

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self))


def _scrape(root, server):
    out = io.StringIO()
    counts = SE.scrape(48, root=root, client=server.client(), out=out, delay=0,
                       now=lambda: "2026-10-03T00:00:00Z")
    return counts, out.getvalue()


def test_scrape_saves_payloads_and_manifest_rows_then_is_stable(tmp_path):
    server = Server()
    counts, log = _scrape(tmp_path, server)
    assert (counts["new"], counts["failed"]) == (2, 0)
    rows = {r["pdf_path"]: r for r in M.read_manifest(tmp_path / M.MANIFEST_PATH)}
    r = rows["pdfs/senate/48/allmanpaynep_48s.json"]
    assert (r["chamber"], r["parliament"], r["member_name"], r["electorate_or_state"],
            r["listed_date"], r["page_count"]) == (
        "senate", "48", "Penny Allman-Payne", "Queensland", "2026-05-13", "1")
    assert S.statement_url_kind(r["source_url"]) == "senate-api"
    assert r["pdf_sha256"] == M.sha256_file(tmp_path / r["pdf_path"])
    assert (tmp_path / "pdfs/senate/48/_query_statements.json").exists()
    assert json.loads((tmp_path / r["pdf_path"]).read_text()) == ALLMAN
    counts, log = _scrape(tmp_path, server)
    assert "0 new, 0 changed, 2 unchanged" in log
    server.statements["281503"] = dict(CICCONE, errors=["changed"])
    counts, log = _scrape(tmp_path, server)
    assert (counts["new"], counts["changed"], counts["unchanged"]) == (0, 1, 1)
    assert "changed pdfs/senate/48/cicconer_48s.json" in log


def test_scrape_rejects_other_parliaments(tmp_path):
    with pytest.raises(ValueError):
        SE.scrape(47, root=tmp_path, client=Server().client())


def test_extract_cli_routes_senate_json_to_the_adapter(tmp_path, monkeypatch):
    from disclosures.cli import main

    rel = _source(tmp_path, CICCONE, "cicconer_48s.json")
    monkeypatch.chdir(tmp_path)
    assert main(["extract", "--source", "senate-json", rel]) == 0
    assert (tmp_path / "extractions/senate-json/senate/48/cicconer_48s.json").exists()
    assert main(["validate", "extractions/senate-json"]) == 0


def test_is_source_document():
    assert M.is_source_document("pdfs/48/abdob_48p.pdf")
    assert M.is_source_document("pdfs/senate/48/wongp_48s.json")
    assert not M.is_source_document("pdfs/senate/48/_query_statements.json")
    assert not M.is_source_document("pdfs/manifest.csv")
