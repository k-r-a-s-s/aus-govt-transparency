"""Register sources (ADR-8, AC-4.1): House register URLs, polite HTTP, listing parser.

    from disclosures import sources
    rows = sources.fetch_register(48)          # live; tests use parse_register on fixtures

The 48th lists one table row per member: "Last updated" date, "Surname, Title Given, Member for
Electorate, STATE", and a statement link that is either a static PDF
(``static.aph.gov.au/.../48p/{AB..SZ}/{Surname}_48P.pdf``) or the register API
(``interests-register-api-public.aph.gov.au/api/members/{id}/statement/48``). The 44th-47th
archives use the same table. The 43rd page is an older committee page: a plain list of links
(no dates) to ``?url=pmi/declarations/{stem}_43p.pdf``, whose stems are v1's filenames.

APH and ASX answer 403 to requests with no browser User-Agent, so every request here sends one.
"""
from __future__ import annotations

import datetime as dt
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable, List, Optional
from urllib.parse import urljoin

BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")

_PREV = "https://www.aph.gov.au/Senators_and_Members/Members/Register/Previous_Parliaments"
HOUSE_REGISTER_URLS = {
    # SPEC §0 gives {_PREV}/43P_Members_Interest_Statements; it 404s (2026-10-02). The 48th
    # page itself links the 43rd to this committee page (DECISIONS.md 2026-10-02).
    43: "https://www.aph.gov.au/Parliamentary_Business/Committees/"
        "House_of_Representatives_Committees?url=pmi/declarations.htm",
    44: f"{_PREV}/44P_Members_Interest_Statements",
    45: f"{_PREV}/45P_Members_Interest_Statements",
    46: f"{_PREV}/46P_Members_Interest_Statements",
    47: f"{_PREV}/47th_Parliament_Register_of_Members_interests",
    48: "https://www.aph.gov.au/senators_and_members/members/register",
}
CURRENT_HOUSE_PARLIAMENT = 48

STATES = ("NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT")
TITLES = {"the", "hon", "mr", "mrs", "ms", "miss", "dr", "prof", "professor", "sir", "dame",
          "rev", "am", "ao", "ac", "oam", "mp", "mhr", "qc", "sc", "kc", "csc", "obe"}

_API_RE = re.compile(r"interests-register-api-public\.aph\.gov\.au/api/members/[^/?#\s]+/statement/\d+")
_STATE_RE = re.compile(r"[,\s]+(" + "|".join(STATES) + r")\.?\s*$", re.I)
_MEMBER_FOR_RE = re.compile(r",?\s*Member\s+for\s+", re.I)


@dataclass(frozen=True)
class RegisterRow:
    parliament: int
    listed_date: Optional[str]  # ISO date of "Last updated"; None on the 43rd page
    name_raw: str               # the listing text, whitespace-collapsed
    surname: str
    given: str                  # given name(s), titles and post-nominals stripped
    electorate: str
    state: Optional[str]
    url: str                    # absolute statement URL
    url_kind: str               # 'api' | 'pdf'


def statement_url_kind(url: str) -> Optional[str]:
    """'api' for register-API statements, 'pdf' for a static/committee PDF link, else None."""
    if _API_RE.search(url):
        return "api"
    path = url.split("#", 1)[0]
    if re.search(r"\.pdf($|[?&])", path, re.I):
        return "pdf"
    return None


def parse_listing_text(text: str):
    """"Abdo, Mr Basem, Member for Calwell VIC" -> ("Abdo", "Basem", "Calwell", "VIC")."""
    text = " ".join(text.split())
    parts = _MEMBER_FOR_RE.split(text, maxsplit=1)
    who = parts[0]
    seat = parts[1] if len(parts) > 1 else ""
    state = None
    m = _STATE_RE.search(seat)
    if m:
        state = m.group(1).upper()
        seat = seat[:m.start()]
    seat = seat.strip(" ,")
    surname, comma, rest = who.partition(",")
    if not comma:  # "Doyle Ms Mary": surname is the words before the first title
        words = who.split()
        i = next((k for k, w in enumerate(words) if w.lower().strip(".") in TITLES), 1)
        surname, rest = " ".join(words[:max(i, 1)]), " ".join(words[max(i, 1):])
    given = " ".join(w for w in re.split(r"[\s,]+", rest)
                     if w and w.lower().strip(".") not in TITLES)
    return surname.strip(), given, seat, state


def parse_date(text: str) -> Optional[str]:
    text = " ".join(re.sub(r"(\d)([A-Za-z])", r"\1 \2", text).split())  # "1April 2020"
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            return dt.datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


class _RegisterHTML(HTMLParser):
    """Collects table rows (date cell + cells + links) and, outside rows, bare links."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows: List[dict] = []   # {"date": str|None, "cells": [str], "hrefs": [str]}
        self.links: List[tuple] = []  # (href, text) for anchors outside any <tr>
        self._row: Optional[dict] = None
        self._cell: Optional[List[str]] = None
        self._cell_is_date = False
        self._a: Optional[List] = None  # [href, [text]]

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "tr":
            self._row = {"date": None, "cells": [], "hrefs": []}
        elif tag == "td" and self._row is not None:
            self._cell = []
            self._cell_is_date = "date" in (a.get("class") or "").split()
        elif tag == "a" and a.get("href"):
            if self._row is not None:
                self._row["hrefs"].append(a["href"])
            else:
                self._a = [a["href"], []]

    def handle_endtag(self, tag):
        if tag == "td" and self._row is not None and self._cell is not None:
            text = " ".join("".join(self._cell).split())
            if self._cell_is_date:
                self._row["date"] = text
            else:
                self._row["cells"].append(text)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None
        elif tag == "a" and self._a is not None:
            self.links.append((self._a[0], " ".join("".join(self._a[1]).split())))
            self._a = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)
        if self._a is not None:
            self._a[1].append(data)


def parse_register(html: str, parliament: int, base_url: Optional[str] = None) -> List[RegisterRow]:
    """Member rows (with a statement link) from a House register listing page."""
    base = base_url or HOUSE_REGISTER_URLS[parliament]
    p = _RegisterHTML()
    p.feed(html)
    p.close()
    out: List[RegisterRow] = []

    def add(date_text, text, href):
        url = urljoin(base, href.strip())
        kind = statement_url_kind(url)
        if kind is None or not _MEMBER_FOR_RE.search(text):
            return
        surname, given, seat, state = parse_listing_text(text)
        out.append(RegisterRow(parliament, parse_date(date_text) if date_text else None,
                               " ".join(text.split()), surname, given, seat, state, url, kind))

    for r in p.rows:
        if r["date"] is None:
            continue
        hrefs = [h for h in r["hrefs"] if statement_url_kind(urljoin(base, h.strip()))]
        if not hrefs:
            continue
        text = next((c for c in r["cells"] if _MEMBER_FOR_RE.search(c)), "")
        add(r["date"], text, hrefs[0])
    if not out:  # 43rd layout: list of links, the link text is the member
        for href, text in p.links:
            add(None, text, href)
    return out


def http_client(timeout: float = 60.0):
    """An httpx client that sends the browser User-Agent on every request."""
    import httpx

    return httpx.Client(timeout=timeout, follow_redirects=True,
                        headers={"User-Agent": BROWSER_UA})


def fetch(url: str, *, client=None, retries: int = 3, backoff: float = 2.0,
          headers: Optional[dict] = None, sleep: Callable[[float], None] = time.sleep):
    """GET with a browser UA; retry transport errors, 429 and 5xx with exponential backoff.

    Returns the final ``httpx.Response`` (raises ``httpx.HTTPStatusError`` on a 4xx/5xx after
    retries, ``httpx.TransportError`` if the host never answers)."""
    import httpx

    own = client is None
    client = client or http_client()
    hdrs = {"User-Agent": BROWSER_UA, **(headers or {})}
    try:
        for attempt in range(retries + 1):
            try:
                resp = client.get(url, headers=hdrs)
            except httpx.TransportError:
                if attempt == retries:
                    raise
            else:
                if resp.status_code != 429 and resp.status_code < 500 or attempt == retries:
                    resp.raise_for_status()
                    return resp
            sleep(backoff * (2 ** attempt))
    finally:
        if own:
            client.close()
    raise AssertionError("unreachable")


def fetch_register(parliament: int, *, client=None) -> List[RegisterRow]:
    url = HOUSE_REGISTER_URLS[parliament]
    return parse_register(fetch(url, client=client).text, parliament, url)
