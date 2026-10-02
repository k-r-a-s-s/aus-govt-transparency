"""disclosures.sources: register URLs, User-Agent, listing parser (AC-4.1). Offline: recorded
fixtures in tests/fixtures/aph/ (fetched 2026-10-02)."""
from pathlib import Path

import httpx
import pytest

from disclosures import sources as S

FIX = Path(__file__).parent / "fixtures" / "aph"


def rows(parliament):
    return S.parse_register((FIX / f"house_{parliament}_register.html").read_text(), parliament)


def test_house_urls():
    assert set(S.HOUSE_REGISTER_URLS) == {43, 44, 45, 46, 47, 48}
    assert S.HOUSE_REGISTER_URLS[48] == "https://www.aph.gov.au/senators_and_members/members/register"
    assert S.HOUSE_REGISTER_URLS[47].endswith(
        "/Previous_Parliaments/47th_Parliament_Register_of_Members_interests")
    for p in (44, 45, 46):
        assert S.HOUSE_REGISTER_URLS[p].endswith(f"/Previous_Parliaments/{p}P_Members_Interest_Statements")
    assert S.HOUSE_REGISTER_URLS[43].endswith("?url=pmi/declarations.htm")
    assert len(set(S.HOUSE_REGISTER_URLS.values())) == 6


def test_ac_4_1_48th_rows():
    r = rows(48)
    assert 150 <= len(r) <= 155
    assert all(x.url_kind in ("api", "pdf") for x in r)
    assert {x.url_kind for x in r} == {"api", "pdf"}  # both link kinds occur on the page
    assert all(x.listed_date and x.surname and x.given and x.electorate for x in r)
    assert len({x.url for x in r}) == len(r)
    abdo = next(x for x in r if x.surname == "Abdo")
    assert (abdo.listed_date, abdo.given, abdo.electorate, abdo.state) == \
        ("2025-10-10", "Basem", "Calwell", "VIC")
    assert abdo.url == "https://interests-register-api-public.aph.gov.au/api/members/316915/statement/48"
    alb = next(x for x in r if x.surname == "Albanese")
    assert alb.url_kind == "pdf" and "/48p/AB/Albanese_48P.pdf" in alb.url
    assert (alb.given, alb.electorate, alb.state) == ("Anthony", "Grayndler", "NSW")
    # alphanumeric API member ids
    assert any(x.url.endswith("/members/DZS/statement/48") for x in r)


def test_46th_archive_rows():
    r = rows(46)
    assert 150 <= len(r) <= 155
    assert all(x.url_kind == "pdf" and "/46p/" in x.url for x in r)
    assert all(x.listed_date for x in r)
    husic = next(x for x in r if x.surname == "Husic")
    assert husic.listed_date == "2020-04-01"  # "1April 2020" on the page
    assert "&amp;" not in husic.url and "&hash=" in husic.url


def test_43rd_link_list():
    r = rows(43)
    assert len(r) == 150
    assert all(x.listed_date is None and x.url_kind == "pdf" for x in r)
    abbott = r[0]
    assert (abbott.surname, abbott.given, abbott.electorate) == ("Abbott", "Tony", "Warringah")
    assert abbott.url.endswith("?url=pmi/declarations/abbotta_43p.pdf")
    assert abbott.url.startswith("https://www.aph.gov.au/")
    # link stems are v1's filenames
    tracked = {p.stem for p in (Path(__file__).parent.parent / "pdfs" / "43").glob("*.pdf")}
    if tracked:
        stems = {x.url.rsplit("/", 1)[1][:-4] for x in r}
        assert stems == tracked


@pytest.mark.parametrize("text,want", [
    ("Abdo, Mr Basem, Member for Calwell VIC", ("Abdo", "Basem", "Calwell", "VIC")),
    ("Aly, Hon Dr Anne, Member for Cowan, WA", ("Aly", "Anne", "Cowan", "WA")),
    ("Doyle Ms Mary, Member for Aston, VIC", ("Doyle", "Mary", "Aston", "VIC")),
    ("Adams, The Hon Dick, Member  for  Lyons", ("Adams", "Dick", "Lyons", None)),
    ("O'Brien, Llewellyn, Member for Wide Bay", ("O'Brien", "Llewellyn", "Wide Bay", None)),
])
def test_parse_listing_text(text, want):
    assert S.parse_listing_text(text) == want


def test_statement_url_kind():
    assert S.statement_url_kind(
        "https://interests-register-api-public.aph.gov.au/api/members/00AMR/statement/48") == "api"
    assert S.statement_url_kind("https://static.aph.gov.au/x/Ley_48P.pdf?rev=1") == "pdf"
    assert S.statement_url_kind("https://www.aph.gov.au/x?url=pmi/declarations/a_43p.pdf") == "pdf"
    assert S.statement_url_kind("/Senators_and_Members/Members/Register") is None


def test_fetch_sends_ua_and_retries():
    seen = []

    def handler(req):
        seen.append(req.headers.get("user-agent"))
        return httpx.Response(503 if len(seen) < 3 else 200, text="ok")

    sleeps = []
    client = httpx.Client(transport=httpx.MockTransport(handler))
    resp = S.fetch("https://www.aph.gov.au/x", client=client, sleep=sleeps.append)
    assert resp.text == "ok"
    assert seen == [S.BROWSER_UA] * 3
    assert sleeps == [2.0, 4.0]


def test_fetch_gives_up_and_does_not_retry_404():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(404 if "missing" in str(req.url) else 500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        S.fetch("https://www.aph.gov.au/missing", client=client, sleep=lambda s: None)
    assert len(calls) == 1
    with pytest.raises(httpx.HTTPStatusError):
        S.fetch("https://www.aph.gov.au/down", client=client, retries=2, sleep=lambda s: None)
    assert len(calls) == 4


def test_fetch_register_uses_client():
    html = (FIX / "house_48_register.html").read_text()
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, text=html)))
    assert len(S.fetch_register(48, client=client)) == 151
