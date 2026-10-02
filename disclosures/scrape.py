"""House register scraper (ADR-8, AC-4.2, AC-4.4): ``python -m disclosures scrape``.

    python -m disclosures scrape --chamber house --parliament 48
    python -m disclosures scrape --chamber house --parliament 48 --verify   # re-download all
    python -m disclosures scrape --chamber senate --parliament 48           # disclosures/senate.py

Reads the live listing (``sources.fetch_register``), downloads each member's statement (static
PDF or register-API link) to ``pdfs/48/{surname}{first-initial}_48p.pdf`` and upserts its row
in ``pdfs/manifest.csv``.

Change detection (D3, checked 2026-10-02: two downloads of the same API statement, and of the
same static PDF, gave identical sha256). A listing row whose link and "Last updated" date match
its manifest row, and whose file is on disk, is ``unchanged`` and not downloaded. Otherwise the
statement is downloaded: no manifest row -> ``new``; a different sha256 -> ``changed`` (the
file is overwritten in place, so git history versions it); the same sha256 -> ``unchanged``
(the row's link/date are refreshed). ``--verify`` downloads every statement and compares bytes.
Files over 95 MB are refused and reported, never written. ``dry_run`` (``refresh --dry-run``)
downloads and compares the same way but writes nothing; ``changes`` collects ``(kind, path)``
for every new/changed statement.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse

from . import manifest, sources
from .load import ascii_fold, norm_electorate, norm_person_name

MAX_BYTES = 95 * 1024 * 1024
SCRAPABLE = {("house", sources.CURRENT_HOUSE_PARLIAMENT)}


def url_key(url: str) -> str:
    """A statement link without its query string: static links carry a ``?rev=`` that
    changes when APH replaces the file, API links are keyed by member id in the path."""
    q = urlparse(url)
    return f"{q.netloc.lower()}{q.path.lower()}"


def _ascii_word(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", ascii_fold(s).lower())


def file_name(row: sources.RegisterRow, taken: set) -> str:
    """``{surname}{first-initial}_{NN}p.pdf``; on a collision the full given name, then a
    numeric suffix (ADR-8, D3)."""
    sur, given = _ascii_word(row.surname), _ascii_word(row.given)
    suffix = f"_{row.parliament}p"
    cands = [f"{sur}{given[:1]}{suffix}.pdf", f"{sur}{given}{suffix}.pdf"]
    for name in cands:
        if name not in taken:
            return name
    n = 2
    while f"{sur}{given}{suffix}_{n}.pdf" in taken:
        n += 1
    return f"{sur}{given}{suffix}_{n}.pdf"


def _find_prior(row: sources.RegisterRow, prior: List[dict], used: set) -> Optional[dict]:
    """The manifest row for this listing row: same link (sans query), else the only row with
    this surname and electorate (a member whose link changed kind)."""
    key = url_key(row.url)
    for r in prior:
        if r["pdf_path"] not in used and r["source_url"] and url_key(r["source_url"]) == key:
            return r
    sur = norm_person_name(row.surname)
    seat = norm_electorate(row.electorate)
    hits = [r for r in prior if r["pdf_path"] not in used and
            norm_electorate(r["electorate_or_state"]) == seat and sur and
            (" " + norm_person_name(r["member_name"])).endswith(" " + sur)]
    return hits[0] if len(hits) == 1 else None


def _page_count(data: bytes) -> int:
    import pymupdf

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return doc.page_count


def _write_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def scrape(chamber: str, parliament: int, *, root: Path = Path("."), client=None,
           verify: bool = False, limit: Optional[int] = None, delay: float = 0.3,
           out=sys.stdout, now: Callable[[], str] = None,
           sleep: Callable[[float], None] = time.sleep, dry_run: bool = False,
           changes: Optional[List[tuple]] = None) -> Dict[str, int]:
    """Download new/changed statements and upsert their manifest rows. Returns counts."""
    if (chamber, parliament) not in SCRAPABLE:
        raise ValueError(f"scrape: only {sorted(SCRAPABLE)} (archives are back-filled by "
                         "`python -m disclosures.manifest --backfill`)")
    now = now or (lambda: dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    own = client is None
    client = client or sources.http_client()
    mpath = root / manifest.MANIFEST_PATH
    rel_dir = Path("pdfs") / str(parliament)
    if not dry_run:
        (root / rel_dir).mkdir(parents=True, exist_ok=True)
    counts = dict(listed=0, new=0, changed=0, unchanged=0, refused=0, failed=0)
    try:
        listing = sources.fetch_register(parliament, client=client)
        if limit is not None:
            listing = listing[:limit]
        counts["listed"] = len(listing)
        rows = manifest.read_manifest(mpath)
        by_path = {r["pdf_path"]: r for r in rows}
        prior = [r for r in rows
                 if r["chamber"] == chamber and r["parliament"] == str(parliament)]
        taken = {Path(r["pdf_path"]).name for r in prior} | \
            {p.name for p in (root / rel_dir).glob("*.pdf")}
        used: set = set()
        fetched = 0
        for row in listing:
            old = _find_prior(row, prior, used)
            if old:
                used.add(old["pdf_path"])
                if (not verify and old["source_url"] == row.url and
                        old["listed_date"] == (row.listed_date or "") and
                        (root / old["pdf_path"]).exists()):
                    counts["unchanged"] += 1
                    continue
            if fetched:
                sleep(delay)
            fetched += 1
            try:
                data = sources.fetch(row.url, client=client).content
            except Exception as e:  # noqa: BLE001 - report and carry on with the rest
                counts["failed"] += 1
                print(f"  FAILED {row.name_raw}: {row.url}: {e}", file=out)
                continue
            if len(data) > MAX_BYTES:
                counts["refused"] += 1
                print(f"  REFUSED {row.name_raw}: {len(data) / 2**20:.1f} MB > 95 MB: {row.url}",
                      file=out)
                continue
            if not data.startswith(b"%PDF-"):
                counts["failed"] += 1
                print(f"  FAILED {row.name_raw}: not a PDF ({data[:20]!r}): {row.url}", file=out)
                continue
            sha = hashlib.sha256(data).hexdigest()
            if old:
                rel = old["pdf_path"]
                kind = "unchanged" if old["pdf_sha256"] == sha and (root / rel).exists() \
                    else "changed"
            else:
                name = file_name(row, taken)
                taken.add(name)
                rel = str(rel_dir / name)
                kind = "new"
            if kind != "unchanged":
                if not dry_run:
                    _write_atomic(root / rel, data)
                if changes is not None:
                    changes.append((kind, rel))
                print(f"  {kind} {rel} ({len(data) / 2**20:.1f} MB) {row.name_raw}", file=out)
            counts[kind] += 1
            by_path[rel] = {
                "chamber": chamber, "parliament": str(parliament),
                "member_name": f"{row.given} {row.surname}".strip(),
                "electorate_or_state": row.electorate, "source_url": row.url,
                "listed_date": row.listed_date or "", "pdf_path": rel, "pdf_sha256": sha,
                "page_count": str(_page_count(data)),
                "fetched_at": now() if kind != "unchanged" or not old else old["fetched_at"],
            }
            if not dry_run:
                manifest.write_manifest(by_path.values(), mpath)  # after every file: resumable
    finally:
        if own:
            client.close()
    print(f"{'dry run: ' if dry_run else ''}scrape {chamber} {parliament}: {counts['listed']} listed, {counts['new']} new, "
          f"{counts['changed']} changed, {counts['unchanged']} unchanged, "
          f"{counts['refused']} refused, {counts['failed']} failed", file=out)
    return counts


def add_arguments(p) -> None:
    p.add_argument("--chamber", choices=["house", "senate"], default="house",
                   help="senate: the senators' interests API (disclosures/senate.py)")
    p.add_argument("--parliament", type=int, default=sources.CURRENT_HOUSE_PARLIAMENT)
    p.add_argument("--verify", action="store_true",
                   help="download every statement and compare sha256, even if the listing "
                        "date and link are unchanged")
    p.add_argument("--limit", type=int, help="only the first N listing rows (testing)")


def run(args) -> int:
    try:
        if args.chamber == "senate":
            from . import senate

            c = senate.scrape(args.parliament, limit=args.limit)
            return 1 if c["failed"] else 0
        c = scrape(args.chamber, args.parliament, verify=args.verify, limit=args.limit)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    return 1 if c["refused"] or c["failed"] else 0
