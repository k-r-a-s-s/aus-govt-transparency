"""ADR-W5 / AC-A6: URL classes and source links."""
from __future__ import annotations

from collections import Counter

import pytest
from web_support import REAL_DB, REAL_MANIFEST, needs_real, ro

from disclosures.export import manifest_urls
from disclosures.web import urls as U

PDF = ("https://static.aph.gov.au/-/media/03_Senators_and_Members/32_Members/Register/47p/"
       "AB/AbbottA_47P.pdf?rev=abc&hash=DEF")
API = "https://interests-register-api-public.aph.gov.au/api/members/00AMR/statement/48"
REDIR = ("https://www.aph.gov.au/Parliamentary_Business/Committees/"
         "House_of_Representatives_Committees?url=pmi/declarations/abbotta_43p.pdf")
SENATE = "https://pbs-apim-aqcdgxhvaug7f8em.z01.azurefd.net/api/getSenatorStatement?cdapid=1"


@pytest.mark.parametrize("url,cls", [(PDF, U.HOUSE_PDF), (API, U.HOUSE_API),
                                     (REDIR, U.HOUSE_REDIRECT), (SENATE, U.SENATE_JSON)])
def test_classify(url, cls):
    assert U.classify(url) == cls


@pytest.mark.parametrize("url", [
    "", "http://static.aph.gov.au/x.pdf", "https://static.aph.gov.au/x.html",
    "https://example.com/x.pdf", "https://interests-register-api-public.aph.gov.au/api/other",
    "https://www.aph.gov.au/Parliamentary_Business/Committees/"
    "House_of_Representatives_Committees?url=other/x.pdf",
    "https://pbs-apim-aqcdgxhvaug7f8em.z01.azurefd.net/api/getSenators",
])
def test_unknown_urls_raise(url):
    with pytest.raises(U.UnknownUrlClass):
        U.classify(url)


def test_source_links():
    assert U.source_link(PDF, 3) == (PDF + "#page=3", "page 3")
    assert U.source_link(PDF + "#page=9", 3) == (PDF + "#page=3", "page 3")
    assert U.source_link(API, 12) == (API + "#page=12", "page 12")
    assert U.source_link(REDIR, 5) == (REDIR, "page 5 of the PDF")
    assert U.source_link(SENATE, 1) == (U.SENATE_REGISTER_INDEX,
                                        "Senate register (structured source, no page)")


@needs_real
def test_every_real_document_resolves_to_a_url_class():
    """AC-A6: every document has a manifest URL and a class; senate-json == Senate docs == 76."""
    urls = manifest_urls(REAL_MANIFEST)
    con = ro(REAL_DB)
    docs = con.execute("select pdf_sha256, chamber, parliament from documents").fetchall()
    missing = [d for d in docs if d[0] not in urls]
    assert missing == []
    by = Counter((U.classify(urls[s]), ch, p) for s, ch, p in docs)
    n_senate = con.execute("select count(*) from documents where chamber = 'senate'").fetchone()[0]
    assert n_senate == 76
    assert sum(n for (c, _, _), n in by.items() if c == U.SENATE_JSON) == n_senate
    assert by[(U.SENATE_JSON, "senate", 48)] == n_senate
    # each class sits where ADR-W5 says it does
    for (c, ch, p), n in by.items():
        assert (c, ch) != (U.SENATE_JSON, "house")
        if c == U.HOUSE_REDIRECT:
            assert (ch, p) == ("house", 43)
        if c == U.HOUSE_API:
            assert (ch, p) == ("house", 48)
        if c == U.HOUSE_PDF:  # 44th-47th, plus 4 House 48th statements published as PDFs
            assert ch == "house" and 44 <= p <= 48
    assert sum(by.values()) == len(docs) == 995
    assert by[(U.HOUSE_REDIRECT, "house", 43)] == 150
    assert by[(U.HOUSE_API, "house", 48)] + by[(U.HOUSE_PDF, "house", 48)] == 151
