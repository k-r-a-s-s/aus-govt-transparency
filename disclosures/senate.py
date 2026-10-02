"""Senate 48th register: fetch the APH senators' interests API and adapt it to ADR-2 (ADR-9, D3).

    python -m disclosures scrape --chamber senate --parliament 48       # raw payloads + manifest
    python -m disclosures extract --source senate-json pdfs/senate/48/*.json   # adapter, no LLM

The register page is a React app backed by a JSON API (``sources.SENATE_API_BASE``). ``scrape``
saves each senator's ``getSenatorStatement`` payload, pretty-printed with sorted keys, to
``pdfs/senate/48/{surname}{first-initial}_48s.json`` (the listing goes to
``pdfs/senate/48/_query_statements.json``) and upserts its ``pdfs/manifest.csv`` row. That JSON
file is the "source document": ``pdf_path`` points at it, ``pdf_sha256`` is its sha256 and
``page_count`` is 1. Two downloads of the same statement gave identical bytes (2026-10-02),
so the sha256 is the change signal. ``dry_run`` (``refresh --dry-run``) fetches and compares
but writes nothing; ``changes`` collects ``(kind, path)`` for every new/changed statement.

The adapter maps each section key to its official number (an unmapped key, or an unknown field
inside a section, is an error, never a silent drop). Interests are ``initial`` items lodged on
the statement's ``lodgementDate``; alterations carry ``alterationType`` and ``createdOn``.
API timestamps are UTC; dates are the Australia/Sydney calendar date (DECISIONS.md 2026-10-03).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from . import manifest, sources
from .scrape import _ascii_word

SOURCE_ID = "senate-json"
MODEL = "aph-senators-interests-api"
NOTES = "structured source: APH senators' interests API"
LIST_NAME = "_query_statements.json"
ORIGIN = {"Origin": "https://www.aph.gov.au"}
TZ = ZoneInfo("Australia/Sydney")

# section key -> (official number, {field: role}); role is "entity" (entity_name, also in the
# description), "text" (description only), "location"/"purpose" (section 3, also in the
# description) or "subsection" (trust type). Field order is description order.
SECTIONS: Dict[str, Tuple[int, Dict[str, str]]] = {
    "shareHoldings": (1, {"nameOfCompany": "entity"}),
    "trusts": (2, {"nameOfCompany": "entity", "nature": "text", "interest": "text",
                   "type": "subsection"}),
    "realEstate": (3, {"location": "location", "purposeForWhichOwned": "purpose"}),
    "registeredDirectorshipsOfCompanies": (4, {"nameOfCompany": "entity",
                                               "activitiesOfCompany": "text"}),
    "partnerships": (5, {"nameOfPartnership": "entity", "natureOfInterest": "text",
                         "activitiesOfPartnership": "text"}),
    "liabilities": (6, {"natureOfLiability": "text", "creditor": "entity"}),
    "investments": (7, {"typeOfInvestment": "text", "bodyOfWhichInvestmentIsHeld": "entity"}),
    "savingsOrInvestmentAccounts": (8, {"natureOfAccount": "text",
                                        "nameOfBankInstitution": "entity"}),
    "otherAssets": (9, {"nameOfOtherAsset": "text"}),
    "otherIncome": (10, {"nameOfIncome": "text"}),
    "gifts": (11, {"detailOfGifts": "text"}),
    "sponsoredTravelOrHospitality": (12, {"detailOfTravelHospitality": "text"}),
    "officeHolderDonating": (13, {"nameOfOrganisation": "entity"}),
    "otherInterest": (14, {"natureOfInterest": "text"}),
}
NON_SECTION_KEYS = {"senatorInterestStatement", "wasSuccessful", "errors"}
# Section 2 as on the House form: 2(i) a beneficial interest, 2(ii) trustee.
TRUST_SUBSECTION = {"beneficiary": "2(i)", "trustee": "2(ii)"}
CHANGE_TYPES = {"addition": "added", "deletion": "removed", "variation": "varied",
                "change": "varied"}
NIL = {"", "-", "--", "nil", "none", "n/a", "na", "not applicable", "nil.", "none."}


class AdapterError(ValueError):
    """A payload the adapter can't map without dropping data."""


def statement_url(cdap_id: str) -> str:
    return f"{sources.SENATE_API_BASE}/getSenatorStatement?cdapid={cdap_id}"


def list_url(page_size: int = 100) -> str:
    return (f"{sources.SENATE_API_BASE}/queryStatements?currentPage=1&pageSize={page_size}"
            "&sortBy=senator&sortDirection=ascending")


def dump(payload: dict) -> bytes:
    """The saved form of a payload: pretty-printed, sorted keys, trailing newline."""
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def _clean(v) -> str:
    return re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else ""


def _is_nil(v: str) -> bool:
    return v.lower() in NIL


def utc_to_local_date(value: str) -> Optional[str]:
    """API timestamp -> Australia/Sydney ISO date. Accepts ISO ("2025-11-11T21:00:00Z", or
    without Z) and the statement header's US form ("8/14/2025 1:31:50 PM"); all are UTC."""
    if not value:
        return None
    value = value.strip()
    try:
        t = dt.datetime.strptime(value, "%m/%d/%Y %I:%M:%S %p")
    except ValueError:
        t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(TZ).date().isoformat()


def display_name(name: str) -> Tuple[str, str]:
    """"Allman-Payne, Penny" -> ("Allman-Payne", "Penny")."""
    sur, _, given = name.partition(",")
    return sur.strip(), given.strip()


def file_name(name: str, parliament: int, taken: set) -> str:
    """``{surname}{first-initial}_{NN}s.json``; on a collision the full given name, then a
    numeric suffix (ADR-8's House rule with an ``s``)."""
    sur, given = (_ascii_word(x) for x in display_name(name))
    suffix = f"_{parliament}s"
    for cand in (f"{sur}{given[:1]}{suffix}.json", f"{sur}{given}{suffix}.json"):
        if cand not in taken:
            return cand
    n = 2
    while f"{sur}{given}{suffix}_{n}.json" in taken:
        n += 1
    return f"{sur}{given}{suffix}_{n}.json"


def _item(section, subsection, entity, description, location, purpose, alteration,
          change_type, lodged) -> dict:
    return {
        "section": section, "subsection": subsection, "owner": "self",
        "entity_name": entity, "description": description, "location": location,
        "purpose": purpose, "is_alteration": alteration, "change_type": change_type,
        "lodged_date": lodged, "date_precision": "day" if lodged else "unknown",
        "page": 1, "confidence": "high",
    }


def payload_items(payload: dict) -> List[dict]:
    """ADR-2 items for one getSenatorStatement payload. Raises AdapterError on any key or
    field the mapping doesn't know."""
    unknown = sorted(set(payload) - set(SECTIONS) - NON_SECTION_KEYS)
    if unknown:
        raise AdapterError(f"unmapped section keys {unknown}")
    lodged = utc_to_local_date(payload["senatorInterestStatement"].get("lodgementDate") or "")
    items: List[dict] = []
    for key, (section, fields) in SECTIONS.items():
        block = payload.get(key)
        if block is None:
            continue
        extra = sorted(set(block) - {"interests", "alterations"})
        if extra:
            raise AdapterError(f"{key}: unmapped keys {extra}")
        for row in block.get("interests") or []:
            bad = sorted(set(row) - set(fields) - {"id"})
            if bad:
                raise AdapterError(f"{key}: unmapped interest fields {bad}")
            vals = {f: _clean(row.get(f)) for f in fields}
            content = [v for f, v in vals.items() if fields[f] != "subsection" and not _is_nil(v)]
            if not content:
                continue  # a nil row ("NIL", "-", null) is not an item (ADR-2)
            entity = next((vals[f] for f, r in fields.items()
                           if r == "entity" and not _is_nil(vals[f])), None)
            loc, purpose = (next((None if _is_nil(vals[f]) else vals[f]
                                  for f, r in fields.items() if r == role), None)
                            for role in ("location", "purpose"))
            subsection = None
            for f, r in fields.items():
                if r == "subsection":
                    kind = vals[f].lower()
                    if kind and kind not in TRUST_SUBSECTION:
                        raise AdapterError(f"{key}: unknown trust type {row.get(f)!r}")
                    subsection = TRUST_SUBSECTION.get(kind)
            items.append(_item(section, subsection, entity, "; ".join(content), loc, purpose,
                               False, "initial", lodged))
        for alt in block.get("alterations") or []:
            bad = sorted(set(alt) - {"alterationType", "details", "createdOn", "id"})
            if bad:
                raise AdapterError(f"{key}: unmapped alteration fields {bad}")
            details = _clean(alt.get("details"))
            if _is_nil(details):
                continue
            change = CHANGE_TYPES.get(_clean(alt.get("alterationType")).lower(), "unknown")
            items.append(_item(section, None, None, details, None, None, True, change,
                               utc_to_local_date(alt.get("createdOn") or "")))
    return items


def adapt(source_path: str, root: Path = Path("."), extracted_at: Optional[str] = None) -> dict:
    """The ADR-2 extraction for one saved payload (``source_path`` repo-relative)."""
    raw = (root / source_path).read_bytes()
    payload = json.loads(raw)
    if not payload.get("wasSuccessful", True):
        raise AdapterError(f"{source_path}: wasSuccessful false: {payload.get('errors')}")
    head = payload["senatorInterestStatement"]
    m = re.match(r"^pdfs/senate/(\d+)/", source_path)
    if not m:
        raise AdapterError(f"{source_path}: not under pdfs/senate/<parliament>/")
    return {
        "schema_version": "2.0", "source_id": SOURCE_ID, "model": MODEL,
        "extracted_at": extracted_at or dt.datetime.now(dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "pdf_path": source_path, "pdf_sha256": hashlib.sha256(raw).hexdigest(),
        "page_count": 1, "pages_covered": [1], "chamber": "senate",
        "parliament": int(m.group(1)),
        "member_name_as_printed": _clean(head.get("senatorName")),
        "electorate_or_state": _clean(head.get("electorateState")),
        "statement_date": utc_to_local_date(head.get("lodgementDate") or ""),
        "items": payload_items(payload), "extraction_notes": NOTES,
    }


def out_path(source_path: str, out_root: Path) -> Path:
    m = re.match(r"^pdfs/senate/(\d+)/(.+)\.json$", source_path)
    if not m:
        raise AdapterError(f"{source_path}: not a pdfs/senate/<parliament>/<stem>.json path")
    return out_root / "senate" / m.group(1) / f"{m.group(2)}.json"


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def adapt_paths(paths: List[str], *, root: Path = Path("."), out_root: Optional[Path] = None,
                force: bool = False, out=sys.stdout) -> int:
    """Write one extraction per source document. ``extracted_at`` is the manifest's
    ``fetched_at`` so re-runs are byte-identical; a file whose sha256 already matches is
    skipped unless ``force``. Returns the exit code (1 if any document failed)."""
    out_root = out_root or root / "extractions" / SOURCE_ID
    fetched = {r["pdf_path"]: r.get("fetched_at") or None
               for r in manifest.read_manifest(root / manifest.MANIFEST_PATH)}
    counts = dict(written=0, skipped=0, failed=0)
    for p in sorted(set(paths)):
        rel = Path(p).as_posix()
        if Path(rel).name.startswith("_"):
            continue  # the saved listing, not a statement
        try:
            dest = out_path(rel, out_root)
            if not force and dest.exists():
                old = json.loads(dest.read_text(encoding="utf-8"))
                if old.get("pdf_sha256") == manifest.sha256_file(root / rel):
                    counts["skipped"] += 1
                    continue
            doc = adapt(rel, root=root, extracted_at=fetched.get(rel))
        except (AdapterError, OSError, KeyError, ValueError) as e:
            counts["failed"] += 1
            print(f"  FAILED {rel}: {e}", file=out)
            continue
        _write_atomic(dest, (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode())
        counts["written"] += 1
        print(f"  wrote {dest} ({len(doc['items'])} items)", file=out)
    print(f"senate-json: {counts['written']} written, {counts['skipped']} unchanged, "
          f"{counts['failed']} failed", file=out)
    return 1 if counts["failed"] else 0


def scrape(parliament: int, *, root: Path = Path("."), client=None, limit: Optional[int] = None,
           delay: float = 0.3, out=sys.stdout, now: Callable[[], str] = None,
           sleep: Callable[[float], None] = time.sleep, dry_run: bool = False,
           changes: Optional[List[tuple]] = None) -> Dict[str, int]:
    """Fetch the listing and every statement, save new/changed payloads, upsert manifest rows."""
    if parliament != sources.CURRENT_SENATE_PARLIAMENT:
        raise ValueError(f"scrape: the senators' interests API only serves the "
                         f"{sources.CURRENT_SENATE_PARLIAMENT}th Parliament")
    now = now or (lambda: dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    own = client is None
    client = client or sources.http_client()
    mpath = root / manifest.MANIFEST_PATH
    rel_dir = Path("pdfs") / "senate" / str(parliament)
    if not dry_run:
        (root / rel_dir).mkdir(parents=True, exist_ok=True)
    counts = dict(listed=0, new=0, changed=0, unchanged=0, failed=0)
    try:
        listing = sources.fetch(list_url(), client=client, headers=ORIGIN).json()
        rows = listing.get("statementOfRegisterableInterests") or []
        if not listing.get("wasSuccessful", True) or len(rows) != listing.get("rowCount", len(rows)):
            raise ValueError(f"scrape: bad listing ({len(rows)} rows, rowCount "
                             f"{listing.get('rowCount')}, errors {listing.get('errors')})")
        if not dry_run:
            _write_atomic(root / rel_dir / LIST_NAME, dump(listing))
        if limit is not None:
            rows = rows[:limit]
        counts["listed"] = len(rows)
        by_path = {r["pdf_path"]: r for r in manifest.read_manifest(mpath)}
        by_url = {r["source_url"]: r for r in by_path.values()
                  if r["chamber"] == "senate" and r["parliament"] == str(parliament)}
        taken = {Path(p).name for p in by_path} | {p.name for p in (root / rel_dir).glob("*.json")}
        for i, row in enumerate(rows):
            if i:
                sleep(delay)
            url = statement_url(row["cdapId"])
            try:
                payload = sources.fetch(url, client=client, headers=ORIGIN).json()
                if not payload.get("wasSuccessful", True) or "senatorInterestStatement" not in payload:
                    raise ValueError(f"unsuccessful payload: {payload.get('errors')}")
            except Exception as e:  # noqa: BLE001 - report and carry on with the rest
                counts["failed"] += 1
                print(f"  FAILED {row.get('name')}: {url}: {e}", file=out)
                continue
            data = dump(payload)
            sha = hashlib.sha256(data).hexdigest()
            old = by_url.get(url)
            if old:
                rel = old["pdf_path"]
                kind = "unchanged" if old["pdf_sha256"] == sha and (root / rel).exists() \
                    else "changed"
            else:
                name = file_name(row["name"], parliament, taken)
                taken.add(name)
                rel = str(rel_dir / name)
                kind = "new"
            if kind != "unchanged":
                if not dry_run:
                    _write_atomic(root / rel, data)
                if changes is not None:
                    changes.append((kind, rel))
                print(f"  {kind} {rel} {row['name']}", file=out)
            counts[kind] += 1
            sur, given = display_name(row["name"])
            by_path[rel] = {
                "chamber": "senate", "parliament": str(parliament),
                "member_name": f"{given} {sur}".strip(), "electorate_or_state": row["state"],
                "source_url": url, "listed_date": utc_to_local_date(row["lastDateUpdated"]) or "",
                "pdf_path": rel, "pdf_sha256": sha, "page_count": "1",
                "fetched_at": old["fetched_at"] if old and kind == "unchanged" else now(),
            }
            if not dry_run:
                manifest.write_manifest(by_path.values(), mpath)  # after every file: resumable
    finally:
        if own:
            client.close()
    print(f"{'dry run: ' if dry_run else ''}scrape senate {parliament}: {counts['listed']} listed, {counts['new']} new, "
          f"{counts['changed']} changed, {counts['unchanged']} unchanged, "
          f"{counts['failed']} failed", file=out)
    return counts
