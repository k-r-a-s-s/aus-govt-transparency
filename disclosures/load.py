"""Loader (ADR-7): validated extraction files -> ``disclosures_v2.db``.

    python -m disclosures load --source <source_id> [--source <source_id> ...] \
        [--db disclosures_v2.db] [--extractions extractions] [--overrides data/overrides]

Rebuilds the DB from scratch (written to a temp file, then renamed over the target, so a
failed load leaves the previous DB intact). Never touches v1's ``disclosures.db``.
See ``docs/v2/loading.md``.
"""
from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import json
import os
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .normalise import normalise_entity
from .schema import SCHEMA_VERSION
from .validate import iter_json_files, validate_file

# DEFAULT_DB, V1_DB_NAME, CATEGORY and _guard_v1 live in the stdlib-only ``dbconst`` so
# that ``export`` and ``web`` do not import pydantic; re-exported here unchanged.
from .dbconst import CATEGORY, DEFAULT_DB, V1_DB_NAME, _guard_v1  # noqa: E402,F401

DEFAULT_EXTRACTIONS = "extractions"
DEFAULT_OVERRIDES = "data/overrides"

DDL = """
CREATE TABLE documents (
    pdf_sha256 TEXT PRIMARY KEY,
    pdf_path TEXT NOT NULL,
    chamber TEXT NOT NULL,
    parliament INTEGER NOT NULL,
    member_id TEXT REFERENCES members(member_id),
    page_count INTEGER NOT NULL,
    source_url TEXT,
    fetched_at TEXT,
    statement_date TEXT,
    extraction_source TEXT NOT NULL,
    model TEXT
);
CREATE TABLE members (
    member_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    chamber TEXT NOT NULL
);
CREATE TABLE member_terms (
    member_id TEXT NOT NULL REFERENCES members(member_id),
    chamber TEXT NOT NULL,
    parliament INTEGER NOT NULL,
    electorate_or_state TEXT,
    party TEXT,
    political_bloc TEXT,
    PRIMARY KEY (member_id, chamber, parliament)
);
CREATE TABLE entities (
    entity_id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE,
    entity_type TEXT,
    asx_code TEXT
);
CREATE TABLE entity_aliases (
    alias_normalised TEXT PRIMARY KEY,
    entity_id TEXT REFERENCES entities(entity_id),
    method TEXT NOT NULL,
    confidence TEXT
);
CREATE TABLE items (
    item_id TEXT PRIMARY KEY,
    pdf_sha256 TEXT NOT NULL REFERENCES documents(pdf_sha256),
    member_id TEXT REFERENCES members(member_id),
    chamber TEXT NOT NULL,
    parliament INTEGER NOT NULL,
    section INTEGER NOT NULL,
    subsection TEXT,
    category TEXT NOT NULL,
    owner TEXT NOT NULL,
    entity_name_raw TEXT,
    entity_id TEXT REFERENCES entities(entity_id),
    description TEXT NOT NULL,
    location TEXT,
    purpose TEXT,
    is_alteration INTEGER NOT NULL,
    change_type TEXT NOT NULL,
    lodged_date TEXT,
    date_precision TEXT NOT NULL,
    page INTEGER NOT NULL,
    confidence TEXT NOT NULL
);
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE INDEX idx_items_pdf_sha256 ON items(pdf_sha256);
CREATE INDEX idx_items_member_id ON items(member_id);
CREATE INDEX idx_items_section ON items(section);
CREATE INDEX idx_items_entity_id ON items(entity_id);
CREATE INDEX idx_documents_member_id ON documents(member_id);
CREATE INDEX idx_member_terms_parliament ON member_terms(parliament);
"""

# AC-2.7 sanity queries: (label, sql, hard_gate). Hard gates must be 0.
SANITY_QUERIES: List[Tuple[str, str, bool]] = [
    ("items with bad section/owner/page",
     "select count(*) from items where section not between 1 and 14 or owner not in "
     "('self','spouse','dependent_child','unknown') or page < 1", True),
    ("items with page > document page_count",
     "select count(*) from items i join documents d using(pdf_sha256) where i.page > d.page_count", True),
    ("items with out-of-range or malformed lodged_date",
     "select count(*) from items where lodged_date is not null and (lodged_date < '1990-01-01' "
     "or lodged_date > date('now') or lodged_date not glob "
     "'[12][0-9][0-9][0-9]-[01][0-9]-[0-3][0-9]')", True),
    ("items lodged before 2010 with confidence != 'low' (informational)",
     "select count(*) from items where lodged_date < '2010-01-01' and confidence != 'low'", False),
]


# --- name / slug helpers (shared with disclosures.members) ---------------------------------

_TITLES_RE = re.compile(r"\b(the hon|hon|dr|mr|mrs|ms|miss|sir|dame|mp|am|ao|qc|sc|oam)\b\.?")


def ascii_fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", s))
    return "".join(c for c in s if not unicodedata.combining(c)).encode("ascii", "ignore").decode()


def member_slug(name: str) -> str:
    """ADR-7 member_id: lower, ASCII-fold, every run of non-alphanumerics -> ``_``."""
    s = ascii_fold(name).lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def norm_person_name(name: Optional[str]) -> str:
    """Matching key for a person's name: "Surname, Given" reordered, ASCII-fold, lower,
    parentheticals/brackets and honorifics dropped, apostrophes deleted, other
    punctuation (incl. ``_``) -> space, whitespace collapsed."""
    if not name:
        return ""
    s = ascii_fold(name)
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", s)
    if s.count(",") == 1:
        last, first = (p.strip() for p in s.split(","))
        if last and first:
            s = f"{first} {last}"
    s = s.lower().replace("_", " ")
    s = re.sub(r"['`’]", "", s)
    s = _TITLES_RE.sub(" ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


_STATE_SUFFIX = {"wa", "nsw", "vic", "qld", "sa", "tas", "nt", "act", "queensland", "victoria",
                 "tasmania", "western australia", "south australia", "new south wales",
                 "northern territory", "australian capital territory"}


def norm_electorate(e: Optional[str]) -> str:
    """Matching key for an electorate: drop ", State" / trailing state, ASCII-fold, lower,
    strip all non-alphanumerics ("Mc Mahon" == "McMahon")."""
    if not e:
        return ""
    s = ascii_fold(e).lower().strip()
    if "," in s:
        s = s.split(",")[0]
    for suf in sorted(_STATE_SUFFIX, key=len, reverse=True):
        if s.endswith(" " + suf):
            s = s[: -len(suf) - 1]
            break
    return re.sub(r"[^a-z0-9]+", "", s)


# --- overrides ----------------------------------------------------------------------------

def _read_csv(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class Overrides:
    """The committed ``data/overrides/*.csv`` tables (ADR-7)."""

    def __init__(self, overrides_dir: Path):
        self.dir = Path(overrides_dir)
        # pdf_path -> row (member_id may be "" for non-member documents)
        self.pdf_members: Dict[str, dict] = {
            r["pdf_path"]: r for r in _read_csv(self.dir / "pdf_members.csv")}
        self.alias_by_name_elec: Dict[Tuple[str, str], set] = defaultdict(set)
        self.alias_by_name: Dict[str, set] = defaultdict(set)
        self.canonical_name: Dict[str, str] = {}
        self.member_electorate: Dict[str, str] = {}
        for r in _read_csv(self.dir / "member_aliases.csv"):
            key = norm_person_name(r["name_variant"])
            mid = r["member_id"]
            self.alias_by_name[key].add(mid)
            if r.get("electorate_or_state"):
                self.alias_by_name_elec[(key, norm_electorate(r["electorate_or_state"]))].add(mid)
            self.canonical_name.setdefault(mid, r["canonical_full_name"])
        for r in self.pdf_members.values():
            if r.get("member_id"):
                self.canonical_name.setdefault(r["member_id"], r["canonical_full_name"])
                if r.get("electorate_or_state"):
                    self.member_electorate.setdefault(r["member_id"], r["electorate_or_state"])
        self.party_terms: Dict[Tuple[str, str, int], dict] = {
            (r["member_id"], r["chamber"], int(r["parliament"])): r
            for r in _read_csv(self.dir / "party_terms.csv")}
        self.unknown_party = {
            (r["member_id"], r["chamber"], int(r["parliament"]))
            for r in _read_csv(self.dir / "unknown_party.csv")}

    def resolve_member(self, pdf_path: str, name_as_printed: str,
                       electorate: str) -> Tuple[Optional[str], Optional[str], str]:
        """-> (member_id, canonical_full_name, how). member_id None = non-member document."""
        row = self.pdf_members.get(pdf_path)
        if row is not None:
            if not row.get("member_id"):
                return None, None, "pdf_members(non_member)"
            return row["member_id"], row["canonical_full_name"], "pdf_members"
        key = norm_person_name(name_as_printed)
        hits = self.alias_by_name_elec.get((key, norm_electorate(electorate)), set())
        if len(hits) != 1:
            hits = self.alias_by_name.get(key, set())
        if len(hits) == 1:
            mid = next(iter(hits))
            return mid, self.canonical_name[mid], "member_aliases"
        mid = member_slug(name_as_printed)
        return mid, name_as_printed.strip(), "slug"


# --- item ids -----------------------------------------------------------------------------

def item_key(pdf_sha256: str, item: dict) -> Tuple:
    return (pdf_sha256, item["page"], item["section"], item["owner"],
            normalise_entity(item.get("entity_name") or item.get("description")))


def item_id(key: Tuple, ordinal: int) -> str:
    payload = json.dumps(list(key) + [ordinal], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


# --- load ---------------------------------------------------------------------------------

def load_db(source_ids: str | List[str], db_path: str | Path = DEFAULT_DB,
            extractions_root: str | Path = DEFAULT_EXTRACTIONS,
            overrides_dir: str | Path = DEFAULT_OVERRIDES,
            root: str | Path | None = None) -> dict:
    """Build ``db_path`` from scratch from ``extractions_root/<source_id>`` for each source id
    (one string, or a list: ``gemini-api`` for the House plus ``senate-json`` for the Senate).
    Returns a summary dict (files loaded/skipped, counts, sanity query results, unresolved
    members)."""
    if isinstance(source_ids, str):
        source_ids = [source_ids]
    if not source_ids or len(set(source_ids)) != len(source_ids):
        raise ValueError(f"need one or more distinct --source ids, got {source_ids}")
    db_path = Path(db_path)
    _guard_v1(db_path)
    src_dirs = [Path(extractions_root) / s for s in source_ids]
    for src_dir in src_dirs:
        if not src_dir.is_dir():
            raise FileNotFoundError(f"no extraction directory {src_dir}")
    if not Path(overrides_dir).is_dir():
        raise FileNotFoundError(f"no overrides directory {overrides_dir}")
    ov = Overrides(Path(overrides_dir))

    valid: List[Tuple[Path, dict, str]] = []
    skipped: Dict[str, List[str]] = {}
    for source_id, src_dir in zip(source_ids, src_dirs):
        for f in iter_json_files([src_dir]):
            errs = validate_file(f, root=root)
            if errs:
                skipped[str(f)] = errs
                continue
            valid.append((f, json.loads(f.read_text(encoding="utf-8")), source_id))

    documents, items = [], []
    # member_id -> (full_name, {chamber: latest (parliament, statement_date)})
    members: Dict[str, Tuple[str, Dict[str, Tuple[int, str]]]] = {}
    terms: Dict[Tuple[str, str, int], dict] = {}
    resolution = defaultdict(int)
    slug_members: List[Tuple[str, str]] = []
    seen_sha: Dict[str, str] = {}
    duplicates: Dict[str, List[str]] = {}
    for f, doc, source_id in valid:
        sha = doc["pdf_sha256"]
        if sha in seen_sha:
            duplicates[str(f)] = [f"duplicate pdf_sha256 (already loaded from {seen_sha[sha]})"]
            continue
        seen_sha[sha] = str(f)
        chamber, parl = doc["chamber"], doc["parliament"]
        mid, full_name, how = ov.resolve_member(doc["pdf_path"], doc["member_name_as_printed"],
                                                doc["electorate_or_state"])
        resolution[how] += 1
        if how == "slug":
            slug_members.append((doc["pdf_path"], mid))
        if mid is not None:
            latest = members.setdefault(mid, (full_name, {}))[1]
            latest[chamber] = max(latest.get(chamber, (0, "")), (parl, doc["statement_date"] or ""))
            tkey = (mid, chamber, parl)
            elec = (doc["electorate_or_state"].strip()
                    or ov.pdf_members.get(doc["pdf_path"], {}).get("electorate_or_state")
                    or ov.member_electorate.get(mid) or None)
            pt = ov.party_terms.get(tkey)
            party = (pt.get("party") or None) if pt else None
            bloc = (pt.get("political_bloc") or None) if pt else None
            if tkey not in terms:
                terms[tkey] = {"electorate_or_state": elec, "party": party, "political_bloc": bloc}
            elif not terms[tkey]["electorate_or_state"] and elec:
                terms[tkey]["electorate_or_state"] = elec
        documents.append((sha, doc["pdf_path"], chamber, parl, mid, doc["page_count"], None, None,
                          doc["statement_date"], source_id, doc.get("model")))
        ordinals: Dict[Tuple, int] = defaultdict(int)
        for it in doc["items"]:
            key = item_key(sha, it)
            ordinal = ordinals[key]
            ordinals[key] += 1
            items.append((
                item_id(key, ordinal), sha, mid, chamber, parl, it["section"], it["subsection"],
                CATEGORY[it["section"]], it["owner"], it["entity_name"], None, it["description"],
                it["location"], it["purpose"], int(bool(it["is_alteration"])), it["change_type"],
                it["lodged_date"], it["date_precision"], it["page"], it["confidence"]))
    skipped.update(duplicates)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_name(db_path.name + f".tmp-{os.getpid()}")
    if tmp.exists():
        tmp.unlink()
    try:
        conn = sqlite3.connect(tmp)
        try:
            conn.executescript(DDL)
            with conn:
                # D3: members.chamber is the chamber of the member's most recent term
                # (latest parliament, then latest statement date); member_terms keeps one
                # row per chamber and parliament.
                conn.executemany("insert into members values (?,?,?)", sorted(
                    (m, n, max(lat, key=lambda c: (lat[c], c))) for m, (n, lat) in members.items()))
                conn.executemany(
                    "insert into member_terms values (?,?,?,?,?,?)",
                    [(m, c, p, t["electorate_or_state"], t["party"], t["political_bloc"])
                     for (m, c, p), t in sorted(terms.items())])
                conn.executemany("insert into documents values (?,?,?,?,?,?,?,?,?,?,?)",
                                 sorted(documents, key=lambda d: d[1]))
                conn.executemany(
                    "insert into items values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", items)
                loaded_at = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()
                conn.executemany("insert into meta values (?,?)", [
                    ("schema_version", SCHEMA_VERSION), ("source_id", ",".join(source_ids)),
                    ("loaded_at", loaded_at), ("n_files", str(len(documents)))])
            sanity = [(label, conn.execute(sql).fetchone()[0], hard)
                      for label, sql, hard in SANITY_QUERIES]
            no_party = [tuple(r) for r in conn.execute(
                "select member_id, chamber, parliament from member_terms where party is null "
                "order by 1, 3")]
        finally:
            conn.close()
        os.replace(tmp, db_path)
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise

    return {
        "db": str(db_path),
        "source_id": ",".join(source_ids),
        "files_loaded": len(documents),
        "files_skipped": skipped,
        "members": len(members),
        "terms": len(terms),
        "items": len(items),
        "resolution": dict(resolution),
        "slug_members": slug_members,
        "no_party_terms": no_party,
        "no_party_unlisted": [t for t in no_party if t not in ov.unknown_party],
        "sanity": sanity,
    }


def print_summary(s: dict, out=None) -> None:
    out = out or sys.stdout
    for f, errs in sorted(s["files_skipped"].items()):
        for e in errs:
            print(f"SKIPPED {f}: {e}", file=out)
    print(f"loaded {s['files_loaded']} files, skipped {len(s['files_skipped'])} "
          f"(source {s['source_id']}) -> {s['db']}", file=out)
    print(f"members {s['members']}, member_terms {s['terms']}, items {s['items']}", file=out)
    print("member resolution: " + ", ".join(f"{k} {v}" for k, v in sorted(s["resolution"].items())),
          file=out)
    for pdf, mid in s["slug_members"]:
        print(f"WARNING member not in overrides, slugged from the printed name: {pdf} -> {mid}",
              file=out)
    print(f"member_terms with no party: {len(s['no_party_terms'])} "
          f"({len(s['no_party_unlisted'])} not listed in unknown_party.csv)", file=out)
    for m, c, p in s["no_party_unlisted"]:
        print(f"WARNING no party and not in unknown_party.csv: {m} {c} {p}", file=out)
    print("AC-2.7 sanity queries:", file=out)
    for label, n, hard in s["sanity"]:
        flag = "" if not hard else (" OK" if n == 0 else " FAIL")
        print(f"  {n:6d}  {label}{flag}", file=out)


def add_arguments(p) -> None:
    p.add_argument("--source", required=True, action="append",
                   help="source_id, e.g. gemini-api; repeat to load several "
                        "(--source gemini-api --source senate-json)")
    p.add_argument("--db", default=DEFAULT_DB, help=f"output DB (default {DEFAULT_DB})")
    p.add_argument("--extractions", default=DEFAULT_EXTRACTIONS,
                   help=f"extractions root (default {DEFAULT_EXTRACTIONS})")
    p.add_argument("--overrides", default=DEFAULT_OVERRIDES,
                   help=f"override CSV directory (default {DEFAULT_OVERRIDES})")


def run(args) -> int:
    try:
        s = load_db(args.source, args.db, args.extractions, args.overrides)
    except (FileNotFoundError, ValueError, sqlite3.OperationalError, OSError) as exc:
        print(f"load: {exc}", file=sys.stderr)
        return 2
    print_summary(s)
    if any(hard and n for _, n, hard in s["sanity"]):
        return 1
    return 0
