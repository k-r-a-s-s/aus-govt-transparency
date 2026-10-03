"""``web check <site> [--db DB]``: the gate a site must pass before deploy (ADR-W3, AC-A5).

Exit 0 when every rule passes, 1 when any rule fails (each failure is printed as
``FAIL <rule>: <detail>``), 2 on bad input (no such directory, no readable
``web-manifest.json``, unreadable ``--db``).

Rules:

- ``forbidden-file``: no ``.db``, ``.sqlite``, ``.sqlite3``, ``.csv``, ``.csv.gz``, ``.jsonl``,
  ``.jsonl.gz`` or ``.parquet`` file (the full data files belong on R2, ADR-W6).
- ``file-too-large``: every file is at most 20 MiB (the asset limit is 25 MiB).
- ``too-many-files``: at most 12,000 files (the free-plan limit is 20,000).
- ``site-too-large``: at most 300 MiB in total.
- ``html-too-large``: every HTML page is at most 2 MiB.
- ``footer-missing``: every HTML page has ``<footer class="site-footer" ...>`` containing
  ``CC BY 4.0`` (the page contract of ADR-W4/W9; phase B's templates emit it).
- ``external-asset``: no ``<script src>``, stylesheet, preload or modulepreload ``<link>`` points
  at another origin (any absolute or protocol-relative URL).
- ``noindex-in-production``: a production build has no ``noindex`` robots meta and no
  ``X-Robots-Tag: noindex`` in ``_headers``.
- ``noindex-missing-in-preview``: a preview build has ``X-Robots-Tag: noindex`` in ``_headers``
  and the robots ``noindex`` meta on every HTML page.
- ``manifest-mismatch``: every file is listed in ``web-manifest.json`` with its sha256 and size,
  and every listed file exists (the site was not edited after the build).
- ``member-json-missing`` (with ``--db``): every member in the DB has ``members/<id>/items.json``.
- ``member-page-missing`` (with ``--db``): every member in the DB has
  ``members/<id>/index.html``.
- ``entity-page-missing`` (with ``--db``): every entity with 2 or more items has
  ``entities/<id>/index.html``.
- ``sitemap-missing-page``: every HTML page except ``404.html`` is listed in ``sitemap.xml``
  (by path; the sitemap's absolute URLs are compared on their path).
- ``canonical-missing``: every HTML page has a ``<link rel="canonical">`` with an absolute
  http(s) URL.

HTML rules pass vacuously when the site has no HTML.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import quote, urlsplit

from .build import HEADERS_NAME, MANIFEST_NAME, MODES

MiB = 1024 * 1024
MAX_FILE = 20 * MiB
MAX_FILES = 12_000
MAX_TOTAL = 300 * MiB
MAX_HTML = 2 * MiB
FORBIDDEN_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".csv", ".csv.gz", ".jsonl", ".jsonl.gz",
                      ".parquet")
FOOTER_CLASS = "site-footer"
FOOTER_LICENCE = "CC BY 4.0"
FOOTER_MARKER = f'<footer class="{FOOTER_CLASS}"'

RULES = ("forbidden-file", "file-too-large", "too-many-files", "site-too-large",
         "html-too-large", "footer-missing", "external-asset", "noindex-in-production",
         "noindex-missing-in-preview", "manifest-mismatch", "member-json-missing",
         "member-page-missing", "entity-page-missing", "sitemap-missing-page",
         "canonical-missing")
SITEMAP_NAME = "sitemap.xml"
NOT_IN_SITEMAP = ("404.html",)


class CheckInputError(ValueError):
    """Bad input (exit 2)."""


def _is_external(url: Optional[str]) -> bool:
    if not url:
        return False
    u = url.strip().lower()
    return u.startswith("//") or bool(re.match(r"^[a-z][a-z0-9+.-]*:", u)) and \
        not u.startswith(("data:", "blob:"))


class _PageScan(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.external: List[str] = []
        self.noindex = False
        self.footer_depth = 0
        self.footer_found = False
        self.footer_text: List[str] = []
        self.canonical: Optional[str] = None

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "script" and _is_external(a.get("src")):
            self.external.append(f"<script src={a['src']}>")
        elif tag == "link":
            rel = set(a.get("rel", "").lower().split())
            if rel & {"stylesheet", "preload", "modulepreload"} and _is_external(a.get("href")):
                self.external.append(f"<link rel={a.get('rel')} href={a['href']}>")
            if "canonical" in rel and self.canonical is None:
                self.canonical = a.get("href", "")
        elif tag == "meta" and a.get("name", "").lower() in ("robots", "googlebot") and \
                "noindex" in a.get("content", "").lower():
            self.noindex = True
        elif tag == "footer":
            if self.footer_depth:
                self.footer_depth += 1
            elif FOOTER_CLASS in a.get("class", "").split():
                self.footer_found = True
                self.footer_depth = 1

    def handle_endtag(self, tag):
        if tag == "footer" and self.footer_depth:
            self.footer_depth -= 1

    def handle_data(self, data):
        if self.footer_depth:
            self.footer_text.append(data)

    @property
    def footer_ok(self) -> bool:
        return self.footer_found and FOOTER_LICENCE in " ".join("".join(self.footer_text).split())


def scan_html(text: str) -> _PageScan:
    p = _PageScan()
    p.feed(text)
    p.close()
    return p


def headers_noindex(text: str) -> bool:
    return any(line.strip().lower().startswith("x-robots-tag:") and "noindex" in line.lower()
               for line in text.splitlines() if not line.lstrip().startswith("#"))


def _db_ids(db: Path) -> Tuple[List[str], List[str]]:
    """(member ids, ids of entities with 2 or more items) from the DB, read-only."""
    if not db.is_file():
        raise CheckInputError(f"--db {db} not found")
    try:
        con = sqlite3.connect(f"file:{quote(str(db.resolve()))}?mode=ro", uri=True)
        try:
            members = [r[0] for r in con.execute("select member_id from members order by 1")]
            entities = [r[0] for r in con.execute(
                "select entity_id from items where entity_id is not null group by 1 "
                "having count(*) >= 2 order by 1")]
            return members, entities
        finally:
            con.close()
    except sqlite3.DatabaseError as e:
        raise CheckInputError(f"--db {db}: {e}") from e


def page_path(rel: str) -> str:
    """Site path of an HTML file: ``index.html`` -> ``/``, ``a/index.html`` -> ``/a/``."""
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[:-len("index.html")]
    return "/" + rel


def sitemap_paths(text: str) -> set:
    return {urlsplit(html.unescape(m)).path or "/"
            for m in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text)}


def check_site(site: str | Path, db: str | Path | None = None) -> Tuple[List[Tuple[str, str]],
                                                                           List[str]]:
    """Return (failures as (rule, detail), notes). Raises ``CheckInputError`` on bad input."""
    site = Path(site)
    if not site.is_dir():
        raise CheckInputError(f"{site} is not a directory")
    try:
        manifest = json.loads((site / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CheckInputError(f"{site / MANIFEST_NAME} missing or unreadable: {e}") from e
    mode = manifest.get("mode") if isinstance(manifest, dict) else None
    if mode not in MODES:
        raise CheckInputError(f"{MANIFEST_NAME}: mode is {mode!r}, expected one of {MODES}")
    ids, entity_ids = _db_ids(Path(db)) if db is not None else (None, None)

    fails: List[Tuple[str, str]] = []
    notes: List[str] = [f"mode: {mode}"]

    def fail(rule: str, detail: str) -> None:
        fails.append((rule, detail))

    files = sorted(p for p in site.rglob("*") if p.is_file())
    rels = [p.relative_to(site).as_posix() for p in files]
    sizes = [p.stat().st_size for p in files]
    total = sum(sizes)
    notes.append(f"{len(files):,} files, {total / MiB:.1f} MiB")

    for rel, size in zip(rels, sizes):
        if rel.lower().endswith(FORBIDDEN_SUFFIXES):
            fail("forbidden-file", f"{rel} (data files go to R2, not the site)")
        if size > MAX_FILE:
            fail("file-too-large", f"{rel} is {size / MiB:.1f} MiB (max {MAX_FILE // MiB} MiB)")
    if len(files) > MAX_FILES:
        fail("too-many-files", f"{len(files):,} files (max {MAX_FILES:,})")
    if total > MAX_TOTAL:
        fail("site-too-large", f"{total / MiB:.1f} MiB (max {MAX_TOTAL // MiB} MiB)")

    # web-manifest.json integrity
    listed = manifest.get("files") or {}
    actual = set(rels) - {MANIFEST_NAME}
    for rel in sorted(actual - set(listed)):
        fail("manifest-mismatch", f"{rel} is not listed in {MANIFEST_NAME}")
    for rel in sorted(set(listed) - actual):
        fail("manifest-mismatch", f"{rel} is listed in {MANIFEST_NAME} but missing")
    for p, rel, size in zip(files, rels, sizes):
        want = listed.get(rel)
        if want is None:
            continue
        if want.get("size") != size or \
                want.get("sha256") != hashlib.sha256(p.read_bytes()).hexdigest():
            fail("manifest-mismatch", f"{rel} differs from {MANIFEST_NAME}")

    # headers
    hdr_path = site / HEADERS_NAME
    hdr_noindex = hdr_path.is_file() and headers_noindex(hdr_path.read_text(encoding="utf-8"))
    if mode == "production" and hdr_noindex:
        fail("noindex-in-production", f"{HEADERS_NAME} sets X-Robots-Tag: noindex")
    if mode == "preview" and not hdr_noindex:
        fail("noindex-missing-in-preview", f"{HEADERS_NAME} has no X-Robots-Tag: noindex")

    # HTML
    html = [(p, rel, size) for p, rel, size in zip(files, rels, sizes)
            if rel.lower().endswith((".html", ".htm"))]
    notes.append(f"{len(html):,} HTML pages")
    in_sitemap: Optional[set] = None
    if html:
        try:
            in_sitemap = sitemap_paths((site / SITEMAP_NAME).read_text(encoding="utf-8"))
        except OSError:
            fail("sitemap-missing-page", f"{SITEMAP_NAME} is missing")
    for p, rel, size in html:
        if size > MAX_HTML:
            fail("html-too-large", f"{rel} is {size / MiB:.2f} MiB (max 2 MiB)")
        scan = scan_html(p.read_text(encoding="utf-8", errors="replace"))
        if not scan.footer_ok:
            fail("footer-missing", f"{rel} has no {FOOTER_MARKER}> containing "
                                   f"'{FOOTER_LICENCE}'")
        for ext in scan.external:
            fail("external-asset", f"{rel}: {ext}")
        if mode == "production" and scan.noindex:
            fail("noindex-in-production", f"{rel} has a robots noindex meta")
        if mode == "preview" and not scan.noindex:
            fail("noindex-missing-in-preview", f"{rel} has no robots noindex meta")
        canon = urlsplit(scan.canonical or "")
        if canon.scheme not in ("http", "https") or not canon.netloc:
            fail("canonical-missing", f"{rel} has no absolute <link rel=canonical>")
        if in_sitemap is not None and rel not in NOT_IN_SITEMAP and \
                page_path(rel) not in in_sitemap:
            fail("sitemap-missing-page", f"{rel} ({page_path(rel)}) is not in {SITEMAP_NAME}")

    # members (needs --db)
    if ids is None:
        notes.append("member rules skipped (no --db)")
    else:
        relset = set(rels)
        for mid in ids:
            if f"members/{mid}/items.json" not in relset:
                fail("member-json-missing", f"members/{mid}/items.json")
        for mid in ids:
            if f"members/{mid}/index.html" not in relset:
                fail("member-page-missing", f"members/{mid}/index.html")
        for eid in entity_ids:
            if f"entities/{eid}/index.html" not in relset:
                fail("entity-page-missing", f"entities/{eid}/index.html")
    return fails, notes


def run_check(site, db=None) -> int:
    try:
        fails, notes = check_site(site, db)
    except CheckInputError as e:
        print(f"web check: {e}")
        return 2
    for n in notes:
        print(f"web check: {n}")
    for rule, detail in fails:
        print(f"FAIL {rule}: {detail}")
    if fails:
        rules = sorted({r for r, _ in fails})
        print(f"web check: FAILED ({len(fails)} problems; rules: {', '.join(rules)})")
        return 1
    print("web check: ok")
    return 0
