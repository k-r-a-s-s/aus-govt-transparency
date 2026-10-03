"""Read-only access to ``disclosures_v2.db`` and ``pdfs/manifest.csv`` for the web build.

The DB is opened with ``mode=ro``; nothing here writes anywhere. Every value the site prints
comes through this module, so pages, charts and JSON share one source of numbers (ADR-W2).
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

from ..dbconst import CATEGORY, _guard_v1
from ..export import HEADER, fetch_rows, manifest_urls
from ..normalise import normalise_entity
from . import urls as U

ID_RE = re.compile(r"^[a-z0-9_]+$")
TABLES = ("documents", "members", "member_terms", "items", "entities", "entity_aliases", "meta")

# Canonical item order: the same as export.QUERY, so the bundle, the per-page JSON and the CSV
# list items in one order.
ITEM_ORDER = "i.chamber, i.parliament, i.member_id, d.pdf_path, i.page, i.section, i.item_id"

ITEMS_SQL = f"""
select i.item_id, i.member_id, i.chamber, i.parliament, i.section, i.subsection, i.owner,
       i.entity_name_raw, i.entity_id, i.description, i.location, i.purpose, i.is_alteration,
       i.change_type, i.lodged_date, i.date_precision, i.page, i.confidence, i.pdf_sha256
from items i join documents d on d.pdf_sha256 = i.pdf_sha256
order by {ITEM_ORDER}
"""
ITEM_FIELDS = ("item_id", "member_id", "chamber", "parliament", "section", "subsection", "owner",
               "entity_name_raw", "entity_id", "description", "location", "purpose",
               "is_alteration", "change_type", "lodged_date", "date_precision", "page",
               "confidence", "pdf_sha256")


class DatasetError(ValueError):
    """Bad input: missing or wrong DB, missing manifest URL, unsafe id (exit 2)."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_id(kind: str, value: str) -> str:
    if not isinstance(value, str) or not ID_RE.match(value):
        raise DatasetError(f"{kind} id {value!r} is not URL-safe (must match {ID_RE.pattern})")
    return value


def sections() -> List[dict]:
    """The 14 register sections (House numbering) with their names, from ``load.CATEGORY``."""
    return [{"section": n, "name": name} for n, name in sorted(CATEGORY.items())]


class Dataset:
    """A read-only view of one DB + manifest. Use as a context manager."""

    def __init__(self, db_path: str | Path, manifest_path: str | Path):
        self.db_path = Path(db_path)
        self.manifest_path = Path(manifest_path)
        try:
            _guard_v1(self.db_path)
        except ValueError as e:
            raise DatasetError(f"{self.db_path}: the web build reads the v2 DB only ({e})") from e
        if not self.db_path.is_file():
            raise DatasetError(f"{self.db_path} not found")
        if not self.manifest_path.is_file():
            raise DatasetError(f"{self.manifest_path} not found")
        self.db_sha256 = sha256_file(self.db_path)
        self.manifest_sha256 = sha256_file(self.manifest_path)
        self.urls: Dict[str, str] = manifest_urls(self.manifest_path)
        self.con = sqlite3.connect(f"file:{quote(str(self.db_path.resolve()))}?mode=ro",
                                   uri=True)
        try:
            have = {r[0] for r in self.con.execute(
                "select name from sqlite_master where type = 'table'")}
        except sqlite3.DatabaseError as e:
            self.con.close()
            raise DatasetError(f"{self.db_path}: not a SQLite database ({e})") from e
        missing = [t for t in TABLES if t not in have]
        if missing:
            self.con.close()
            raise DatasetError(f"{self.db_path}: not a v2 DB (missing tables {missing})")
        self._cache: dict = {}

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> "Dataset":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _q(self, sql: str, params=()) -> list:
        return self.con.execute(sql, params).fetchall()

    # --- tables -------------------------------------------------------------------------

    def meta(self) -> Dict[str, str]:
        return dict(self._q("select key, value from meta order by key"))

    def members(self) -> List[dict]:
        """Members sorted by id, each with its terms (sorted by chamber, parliament)."""
        if "members" in self._cache:
            return self._cache["members"]
        terms = defaultdict(list)
        for mid, ch, p, elec, party, bloc in self._q(
                "select member_id, chamber, parliament, electorate_or_state, party, political_bloc "
                "from member_terms order by member_id, chamber, parliament"):
            terms[mid].append({"chamber": ch, "parliament": p, "electorate_or_state": elec,
                               "party": party, "bloc": bloc})
        n_items = dict(self._q("select member_id, count(*) from items group by 1"))
        docs = defaultdict(list)
        for mid, sha in self._q("select member_id, pdf_sha256 from documents "
                                "order by member_id, chamber, parliament, pdf_path"):
            docs[mid].append(sha)
        out = []
        for mid, name, ch in self._q("select member_id, full_name, chamber from members "
                                     "order by member_id"):
            check_id("member", mid)
            out.append({"id": mid, "name": name, "chamber": ch, "terms": terms.get(mid, []),
                        "items": n_items.get(mid, 0), "documents": docs.get(mid, [])})
        self._cache["members"] = out
        return out

    def alias_methods(self) -> Dict[str, str]:
        """alias_normalised -> match method (``curated``/``asx``/``llm``/``singleton``/``generic``)."""
        return dict(self._q("select alias_normalised, method from entity_aliases"))

    def aliases(self) -> Dict[str, List[dict]]:
        """entity_id -> its aliases (normalised name, method, confidence), sorted by name."""
        out = defaultdict(list)
        for alias, eid, method, conf in self._q(
                "select alias_normalised, entity_id, method, confidence from entity_aliases "
                "where entity_id is not null order by entity_id, alias_normalised"):
            out[eid].append({"alias": alias, "method": method, "confidence": conf})
        return dict(out)

    def entities(self) -> List[dict]:
        """Every entity sorted by id, with item and distinct-member counts and match methods."""
        if "entities" in self._cache:
            return self._cache["entities"]
        counts = {eid: (n, m) for eid, n, m in self._q(
            "select entity_id, count(*), count(distinct member_id) from items "
            "where entity_id is not null group by 1")}
        methods = defaultdict(set)
        for eid, method in self._q("select entity_id, method from entity_aliases "
                                   "where entity_id is not null"):
            methods[eid].add(method)
        out = []
        for eid, name, typ, asx in self._q("select entity_id, canonical_name, entity_type, "
                                           "asx_code from entities order by entity_id"):
            check_id("entity", eid)
            n, m = counts.get(eid, (0, 0))
            out.append({"id": eid, "name": name, "type": typ, "asx": asx, "items": n,
                        "members": m, "methods": sorted(methods.get(eid, ())),
                        "page": n >= 2})
        self._cache["entities"] = out
        return out

    def documents(self) -> List[dict]:
        """Every document sorted by sha256, with its manifest URL and ADR-W5 URL class.

        Raises ``DatasetError`` when a document has no manifest URL or the URL has no class:
        every item must be able to link to its source.
        """
        if "documents" in self._cache:
            return self._cache["documents"]
        out = []
        for sha, path, ch, p, mid, pages, src, date, xsrc, model in self._q(
                "select pdf_sha256, pdf_path, chamber, parliament, member_id, page_count, "
                "source_url, statement_date, extraction_source, model from documents "
                "order by pdf_sha256"):
            url = src or self.urls.get(sha)
            if not url:
                raise DatasetError(f"document {path} ({sha[:12]}) has no source URL in "
                                   f"{self.manifest_path}")
            try:
                cls = U.classify(url)
            except U.UnknownUrlClass as e:
                raise DatasetError(f"document {path}: {e}") from e
            out.append({"sha256": sha, "path": path, "chamber": ch, "parliament": p,
                        "member_id": mid, "pages": pages, "url": url, "url_class": cls,
                        "statement_date": date, "extraction_source": xsrc, "model": model})
        self._cache["documents"] = out
        return out

    def items(self) -> List[dict]:
        """Every item as a dict of ``ITEM_FIELDS``, in the canonical (export) order."""
        return [dict(zip(ITEM_FIELDS, r)) for r in self._q(ITEMS_SQL)]

    def export_rows(self) -> List[dict]:
        """Every item as a row object with the published CSV column names (``export.HEADER``),
        with the values ``export.fetch_rows`` writes to the CSV (empty string for null)."""
        return [dict(zip(HEADER, r)) for r in fetch_rows(self.con, self.urls)]

    def match_method(self, entity_name_raw: Optional[str],
                     methods: Optional[Dict[str, str]] = None) -> Optional[str]:
        """The match method for a printed entity name, as ``export.fetch_rows`` derives it."""
        if entity_name_raw is None:
            return None
        methods = self.alias_methods() if methods is None else methods
        return methods.get(normalise_entity(entity_name_raw))

    def item_blocs(self) -> Dict[tuple, Optional[str]]:
        """(member_id, chamber, parliament) -> political bloc for that term."""
        return {(m, c, p): b for m, c, p, b in self._q(
            "select member_id, chamber, parliament, political_bloc from member_terms")}

    def coverage(self) -> List[dict]:
        from ..export import coverage
        return [{"chamber": ch, "parliament": p, "members": m, "statements": d, "items": n}
                for ch, p, m, d, n in coverage(self.con)]
