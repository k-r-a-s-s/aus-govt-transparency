"""PDF provenance manifest (ADR-8, AC-4.3): ``pdfs/manifest.csv``, one row per tracked PDF.

    python -m disclosures.manifest --backfill                 # live archive listings 43-47
    python -m disclosures.manifest --backfill --html-dir DIR  # cached house_{p}.html pages

The back-fill covers v1's PDFs: sha256 from the file, page_count from ``eval/pdf_stats.csv``
(PyMuPDF if missing), parliament from the path, member/electorate from
``data/overrides/pdf_members.csv``. ``source_url``/``listed_date`` come from the archive
listing when a PDF matches one listing row (first by the link's file stem, then by electorate
plus surname); otherwise they stay empty. v1's ``fetched_at`` is unknown and stays empty.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import subprocess
import sys
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import unquote, urljoin, urlparse

from . import sources
from .load import norm_electorate, norm_person_name

COLUMNS = ["chamber", "parliament", "member_name", "electorate_or_state", "source_url",
           "listed_date", "pdf_path", "pdf_sha256", "page_count", "fetched_at"]
MANIFEST_PATH = Path("pdfs/manifest.csv")
PDF_MEMBERS = Path("data/overrides/pdf_members.csv")
PDF_STATS = Path("eval/pdf_stats.csv")
_PARL_RE = re.compile(r"^pdfs/(?:(senate)/)?(\d+)/")


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_manifest(path=MANIFEST_PATH) -> List[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_manifest(rows: Iterable[dict], path=MANIFEST_PATH) -> None:
    """Write rows sorted by pdf_path, atomically."""
    path = Path(path)
    tmp = path.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in sorted(rows, key=lambda r: r["pdf_path"]):
            w.writerow({c: r.get(c, "") if r.get(c) is not None else "" for c in COLUMNS})
    os.replace(tmp, path)


def is_source_document(path: str) -> bool:
    """A House/Senate PDF, or a saved Senate API statement (``pdfs/senate/<p>/*.json``, not
    the ``_``-prefixed listing)."""
    name = path.rsplit("/", 1)[-1]
    return path.lower().endswith(".pdf") or (
        path.startswith("pdfs/senate/") and name.endswith(".json") and not name.startswith("_"))


def tracked_pdfs(root: Path = Path(".")) -> List[str]:
    """Tracked source documents (PDFs and Senate JSON statements)."""
    out = subprocess.run(["git", "ls-files", "pdfs"], cwd=root, capture_output=True, text=True,
                         check=True).stdout.split("\n")
    return sorted(p for p in out if is_source_document(p))


def link_stem(url: str) -> str:
    """Lower-case file stem of a statement link ("…/45p/AB/AlexanderJ_45P_2.pdf?rev=…" ->
    "alexanderj_45p_2"); the 43rd's committee links carry the path in ``?url=``."""
    q = urlparse(url)
    path = q.query.split("url=", 1)[1].split("&", 1)[0] if "url=" in q.query else q.path
    return unquote(path.rsplit("/", 1)[-1]).rsplit(".", 1)[0].lower()


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs: List[str] = []

    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get("href")
        if tag == "a" and href:
            self.hrefs.append(href.strip())


def page_pdf_links(html: str, base_url: str) -> List[str]:
    """Every PDF link on a listing page (member rows and others, e.g. explanatory notes)."""
    p = _Links()
    p.feed(html)
    p.close()
    urls = (urljoin(base_url, h) for h in p.hrefs)
    return [u for u in urls if sources.statement_url_kind(u) == "pdf"]


def match_listing(pdfs: Dict[str, dict], rows: List[sources.RegisterRow],
                  extra_links: Iterable[str] = ()) -> Dict[str, tuple]:
    """pdf_path -> (source_url, listed_date) for one parliament.

    ``pdfs`` maps pdf_path -> its pdf_members.csv row. Pass 1 matches the listing link's file
    stem to the PDF's stem (also against ``extra_links``, which carry no date). Pass 2 matches
    the rest by electorate plus surname, only where exactly one unclaimed row fits. A listing
    row is never given to two PDFs."""
    by_stem: Dict[str, tuple] = {}
    for u in extra_links:
        by_stem.setdefault(link_stem(u), (u, "", None))
    for r in rows:
        by_stem[link_stem(r.url)] = (r.url, r.listed_date or "", r)
    out: Dict[str, tuple] = {}
    claimed = set()
    for path in pdfs:
        hit = by_stem.get(Path(path).stem.lower())
        if hit:
            out[path] = hit[:2]
            claimed.add(hit[0])
    by_seat = defaultdict(list)
    for r in rows:
        if r.url not in claimed:
            by_seat[norm_electorate(r.electorate)].append(r)
    wanted = defaultdict(list)
    for path, m in pdfs.items():
        if path in out or not m.get("canonical_full_name"):
            continue
        name = norm_person_name(m["canonical_full_name"])
        cands = [r for r in by_seat.get(norm_electorate(m.get("electorate_or_state")), [])
                 if norm_person_name(r.surname) and
                 (" " + name).endswith(" " + norm_person_name(r.surname))]
        if len(cands) == 1:
            wanted[cands[0].url].append((path, cands[0]))
    for url, hits in wanted.items():
        if len(hits) == 1:
            path, r = hits[0]
            out[path] = (r.url, r.listed_date or "")
    return out


def _page_counts() -> Dict[str, str]:
    if not PDF_STATS.exists():
        return {}
    with open(PDF_STATS, newline="", encoding="utf-8") as fh:
        return {r["pdf_path"]: r["page_count"] for r in csv.DictReader(fh)}


def _page_count(path: str, known: Dict[str, str]) -> str:
    if known.get(path):
        return known[path]
    if path.lower().endswith(".json"):
        return "1"
    import pymupdf

    with pymupdf.open(path) as doc:
        return str(doc.page_count)


def backfill(listings: Dict[int, str], existing: Optional[List[dict]] = None,
             out=sys.stdout) -> List[dict]:
    """Manifest rows for every tracked PDF. ``listings`` maps parliament -> listing HTML.
    Rows already in ``existing`` keep their source_url/listed_date/fetched_at when the
    listing gives nothing (so a scrape's 48th rows survive a re-run)."""
    with open(PDF_MEMBERS, newline="", encoding="utf-8") as fh:
        members = {r["pdf_path"]: r for r in csv.DictReader(fh)}
    prior = {r["pdf_path"]: r for r in existing or []}
    pages = _page_counts()
    paths = tracked_pdfs()
    by_parl = defaultdict(dict)
    for path in paths:
        m = _PARL_RE.match(path)
        if not m:
            raise ValueError(f"{path}: no parliament in path")
        by_parl[(m.group(1) or "house", int(m.group(2)))][path] = members.get(path, {})
    rows = []
    for (chamber, parl), pdfs in sorted(by_parl.items()):
        matched = {}
        if chamber == "house" and parl in listings:
            base = sources.HOUSE_REGISTER_URLS[parl]
            html = listings[parl]
            matched = match_listing(pdfs, sources.parse_register(html, parl, base),
                                    page_pdf_links(html, base))
        statements = sum(1 for p in pdfs if pdfs[p].get("member_id"))
        hit_st = sum(1 for p in matched if pdfs[p].get("member_id"))
        print(f"{chamber} {parl}: {len(pdfs)} PDFs, source_url matched {len(matched)} "
              f"({hit_st}/{statements} member statements)", file=out)
        for path, m in pdfs.items():
            old = prior.get(path, {})
            url, listed = matched.get(path, (old.get("source_url", ""), old.get("listed_date", "")))
            rows.append({
                "chamber": chamber, "parliament": str(parl),
                "member_name": m.get("canonical_full_name") or old.get("member_name", ""),
                "electorate_or_state": (m.get("electorate_or_state")
                                        or old.get("electorate_or_state", "")),
                "source_url": url, "listed_date": listed, "pdf_path": path,
                "pdf_sha256": sha256_file(path), "page_count": _page_count(path, pages),
                "fetched_at": old.get("fetched_at", ""),
            })
    n = sum(1 for r in rows if r["source_url"])
    print(f"manifest: {len(rows)} rows, source_url matched {n} ({100 * n / max(len(rows), 1):.1f}%)",
          file=out)
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m disclosures.manifest", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backfill", action="store_true", required=True,
                    help="rebuild pdfs/manifest.csv for every tracked PDF")
    ap.add_argument("--html-dir", type=Path,
                    help="read listings from DIR/house_{p}.html instead of fetching them")
    ap.add_argument("--parliaments", default="43,44,45,46,47")
    args = ap.parse_args(argv)
    listings = {}
    for p in (int(x) for x in args.parliaments.split(",")):
        if args.html_dir:
            f = args.html_dir / f"house_{p}.html"
            if f.exists():
                listings[p] = f.read_text(encoding="utf-8")
        else:
            listings[p] = sources.fetch(sources.HOUSE_REGISTER_URLS[p]).text
    rows = backfill(listings, read_manifest())
    write_manifest(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
