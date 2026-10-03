"""Source URL classes and per-item source links (ADR-W5).

The DB stores no source URL; each document's URL comes from ``pdfs/manifest.csv``. The URL
shape tells us what the link serves and whether ``#page=N`` can deep-link into it:

- ``house-pdf``: ``https://static.aph.gov.au/...pdf?rev=...&hash=...`` (House 44th-47th), a PDF.
- ``house-api``: ``https://interests-register-api-public.aph.gov.au/api/members/<id>/statement/<p>``
  (House 48th), serves the PDF.
- ``house-redirect``: ``https://www.aph.gov.au/.../House_of_Representatives_Committees?url=pmi/...``
  (House 43rd), an APH redirector that may drop the fragment.
- ``senate-json``: the Senate interests API (``SENATE_API_BASE/getSenatorStatement?cdapid=...``),
  JSON rather than a PDF, so there is no page to link to.
"""
from __future__ import annotations

import re
from typing import Tuple
from urllib.parse import parse_qs, urlsplit, urlunsplit

from ..sources import SENATE_API_BASE

HOUSE_PDF = "house-pdf"
HOUSE_API = "house-api"
HOUSE_REDIRECT = "house-redirect"
SENATE_JSON = "senate-json"
URL_CLASSES = (HOUSE_PDF, HOUSE_API, HOUSE_REDIRECT, SENATE_JSON)

SENATE_REGISTER_INDEX = ("https://www.aph.gov.au/Parliamentary_Business/Committees/Senate/"
                         "Senators_Interests/Senators_Interests_Register")
SENATE_LINK_TEXT = "Senate register (structured source, no page)"

_SENATE = urlsplit(SENATE_API_BASE)
_API_PATH = re.compile(r"^/api/members/[^/]+/statement/\d+$")


class UnknownUrlClass(ValueError):
    """A manifest URL matches none of the ADR-W5 classes (the build fails closed)."""


class SourceLinkError(ValueError):
    """An item's page is missing or not a positive integer, so no source link can be built."""


def classify(url: str) -> str:
    """Return the ADR-W5 class of a manifest source URL; raise ``UnknownUrlClass`` otherwise."""
    if not url:
        raise UnknownUrlClass("empty source URL")
    u = urlsplit(url)
    host = (u.hostname or "").lower()
    if u.scheme != "https":
        raise UnknownUrlClass(f"not an https URL: {url}")
    if host == "static.aph.gov.au" and u.path.lower().endswith(".pdf"):
        return HOUSE_PDF
    if host == "interests-register-api-public.aph.gov.au" and _API_PATH.match(u.path):
        return HOUSE_API
    if host in ("www.aph.gov.au", "aph.gov.au") and \
            u.path.endswith("/House_of_Representatives_Committees") and \
            any(v.startswith("pmi/") for v in parse_qs(u.query).get("url", [])):
        return HOUSE_REDIRECT
    if host == (_SENATE.hostname or "").lower() and u.path == _SENATE.path + "/getSenatorStatement":
        return SENATE_JSON
    raise UnknownUrlClass(f"no ADR-W5 class for {url}")


def _without_fragment(url: str) -> str:
    return urlunsplit(urlsplit(url)._replace(fragment=""))


def source_link(url: str, page: int) -> Tuple[str, str]:
    """``(href, text)`` for an item on ``page`` of the document at ``url`` (ADR-W5).

    Raises ``SourceLinkError`` when ``page`` is not a positive integer and ``UnknownUrlClass``
    when the URL has no class.
    """
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise SourceLinkError(f"page must be a positive integer, got {page!r} (source {url})")
    cls = classify(url)
    if cls in (HOUSE_PDF, HOUSE_API):
        return f"{_without_fragment(url)}#page={int(page)}", f"page {int(page)}"
    if cls == HOUSE_REDIRECT:
        return url, f"page {int(page)} of the PDF"
    # senate-json: the manifest and members table carry no per-senator register page.
    return SENATE_REGISTER_INDEX, SENATE_LINK_TEXT
