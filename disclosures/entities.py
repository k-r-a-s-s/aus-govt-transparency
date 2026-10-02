"""Entity standardisation (ADR-6): ``items.entity_name_raw`` -> ``entities`` / ``entity_aliases``.

    python -m disclosures entities [--db disclosures_v2.db] [--data data/entities] [--offline]

Runs on a DB that ``load`` has just built (entity tables empty) and rewrites ``entities``,
``entity_aliases`` and ``items.entity_id`` in place, in one transaction. Inputs are committed
files only, so a re-run gives identical tables. See ``docs/v2/entities.md``.

Pipeline: normalise each raw name (``normalise_entity``), mark generic descriptors
(``generic_terms.csv`` -> entity NULL), then resolve the rest through the stages in
precedence order curated > asx > llm > singleton. Each stage takes the still-unresolved
aliases and returns the ones it resolves.
"""
from __future__ import annotations

import csv
import hashlib
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .load import DEFAULT_DB, _guard_v1, member_slug
from .normalise import normalise_entity

DEFAULT_DATA = "data/entities"

ENTITY_TYPES = (
    "listed_company", "private_company", "bank_or_financial", "airline", "sporting_body",
    "media_or_entertainment", "government_body", "union", "political_party",
    "association_or_ngo", "education", "person", "trust_or_fund", "other",
)
METHODS = ("generic", "curated", "asx", "llm", "singleton")


@dataclass(frozen=True)
class Resolution:
    canonical_name: str
    entity_type: Optional[str] = None
    asx_code: Optional[str] = None
    confidence: Optional[str] = None


@dataclass
class Context:
    """What every stage can see: alias -> item count, alias -> raw spellings, and inputs."""
    counts: Counter
    spellings: Dict[str, Counter]
    data_dir: Path
    offline: bool


Stage = Callable[[List[str], Context], Dict[str, Resolution]]


def entity_id_for(canonical_name: str) -> str:
    """D2: slug of canonical_name, made the same way as member_id."""
    slug = member_slug(canonical_name)
    if not slug:  # a name with no ASCII letters or digits at all
        slug = "entity_" + hashlib.sha1(canonical_name.encode()).hexdigest()[:10]
    return slug


def load_generic_terms(data_dir: Path) -> set:
    path = data_dir / "generic_terms.csv"
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as f:
        return {normalise_entity(r["term"]) for r in csv.DictReader(f) if r["term"].strip()}


# --- stages (precedence order) ------------------------------------------------------------

def stage_curated(aliases: List[str], ctx: Context) -> Dict[str, Resolution]:
    """ADR-6 step 3: ``aliases.csv`` (alias, canonical_name, entity_type, asx_code, ...)."""
    path = ctx.data_dir / "aliases.csv"
    if not path.exists():
        return {}
    table: Dict[str, Resolution] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            alias = normalise_entity(r["alias"])
            if not alias:
                continue
            table[alias] = Resolution(r["canonical_name"].strip(),
                                      (r.get("entity_type") or "").strip() or None,
                                      (r.get("asx_code") or "").strip() or None)
    return {a: table[a] for a in aliases if a in table}


def stage_asx(aliases: List[str], ctx: Context) -> Dict[str, Resolution]:
    """ADR-6 step 4: exact name / ticker match against the ASX snapshot (lands in T2.2)."""
    return {}


def stage_llm(aliases: List[str], ctx: Context) -> Dict[str, Resolution]:
    """ADR-6 step 5: long-tail LLM grouping for aliases with >= 2 items (lands in T2.6+)."""
    return {}


def stage_singleton(aliases: List[str], ctx: Context) -> Dict[str, Resolution]:
    """Whatever is left becomes its own untyped entity, named by its commonest raw spelling.

    ADR-6 means this for 1-item aliases; until the LLM stage exists it also catches the
    >= 2-item ones, so every named, non-generic item has an entity (AC-3.3).
    """
    out = {}
    for a in aliases:
        spellings = ctx.spellings[a]
        top = max(spellings.values())
        out[a] = Resolution(min(s for s, n in spellings.items() if n == top))
    return out


STAGES: List[Tuple[str, Stage]] = [
    ("curated", stage_curated),
    ("asx", stage_asx),
    ("llm", stage_llm),
    ("singleton", stage_singleton),
]


# --- pipeline -----------------------------------------------------------------------------

def resolve(items: List[Tuple[str, str]], data_dir: Path, offline: bool = True,
            stages: List[Tuple[str, Stage]] = STAGES):
    """items: (item_id, entity_name_raw) with raw non-null.

    Returns (entities, aliases, item_entity): entities = {entity_id: (canonical, type, asx)},
    aliases = {alias: (entity_id|None, method, confidence)}, item_entity = {item_id: id|None}.
    """
    counts: Counter = Counter()
    spellings: Dict[str, Counter] = defaultdict(Counter)
    item_alias: Dict[str, str] = {}
    for iid, raw in items:
        alias = normalise_entity(raw)
        item_alias[iid] = alias
        counts[alias] += 1
        spellings[alias][" ".join(raw.split())] += 1
    ctx = Context(counts, spellings, data_dir, offline)

    generic = load_generic_terms(data_dir)
    aliases: Dict[str, Tuple[Optional[str], str, Optional[str]]] = {}
    for a in sorted(counts):
        if a in generic or not a:
            aliases[a] = (None, "generic", None)

    entities: Dict[str, Tuple[str, Optional[str], Optional[str]]] = {}
    unresolved = sorted(a for a in counts if a not in aliases)
    for method, stage in stages:
        if not unresolved:
            break
        found = stage(unresolved, ctx)
        for a in sorted(found):
            res = found[a]
            eid = entity_id_for(res.canonical_name)
            # An id that already exists (same canonical slug from an earlier stage or alias)
            # is the same organisation: the alias joins it and the first definition stands.
            if eid not in entities:
                entities[eid] = (res.canonical_name, res.entity_type, res.asx_code)
            aliases[a] = (eid, method, res.confidence)
        unresolved = [a for a in unresolved if a not in found]
    item_entity = {iid: aliases[a][0] for iid, a in item_alias.items()}
    return entities, aliases, item_entity


def run_entities(db_path: str | Path = DEFAULT_DB, data_dir: str | Path = DEFAULT_DATA,
                 offline: bool = True) -> dict:
    db_path = Path(db_path)
    _guard_v1(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"{db_path} not found: run `python -m disclosures load` first")
    con = sqlite3.connect(db_path)
    try:
        items = con.execute("select item_id, entity_name_raw from items "
                            "where entity_name_raw is not null order by item_id").fetchall()
        entities, aliases, item_entity = resolve(items, Path(data_dir), offline)
        with con:
            con.execute("update items set entity_id = NULL")
            con.execute("delete from entity_aliases")
            con.execute("delete from entities")
            con.executemany("insert into entities values (?,?,?,?)",
                            [(eid, *entities[eid]) for eid in sorted(entities)])
            con.executemany("insert into entity_aliases values (?,?,?,?)",
                            [(a, *aliases[a]) for a in sorted(aliases)])
            con.executemany("update items set entity_id = ? where item_id = ?",
                            [(eid, iid) for iid, eid in sorted(item_entity.items())
                             if eid is not None])
        summary = {
            "entities": len(entities),
            "aliases": dict(con.execute("select method, count(*) from entity_aliases "
                                        "group by 1").fetchall()),
            "items": dict(Counter(aliases[normalise_entity(raw)][1] for _, raw in items)),
            "named_items": len(items),
            # AC-3.3: named items whose alias isn't generic but got no entity
            "unresolved": con.execute(
                "select count(*) from items where entity_name_raw is not null and "
                "entity_id is null").fetchone()[0],
        }
    finally:
        con.close()
    summary["unresolved"] -= summary["items"].get("generic", 0)
    return summary


def print_summary(s: dict, out=None) -> None:
    out = out or sys.stdout
    print(f"entities: {s['named_items']} named items -> {s['entities']} entities", file=out)
    print(f"  {'method':10s} {'aliases':>8s} {'items':>8s}", file=out)
    for m in METHODS:
        print(f"  {m:10s} {s['aliases'].get(m, 0):8d} {s['items'].get(m, 0):8d}", file=out)
    flag = "OK" if s["unresolved"] == 0 else "FAIL"
    print(f"  non-generic named items without an entity (AC-3.3): {s['unresolved']} {flag}",
          file=out)


def add_arguments(p) -> None:
    p.add_argument("--db", default=DEFAULT_DB, help=f"DB built by load (default {DEFAULT_DB})")
    p.add_argument("--data", default=DEFAULT_DATA,
                   help=f"committed entity inputs (default {DEFAULT_DATA})")
    p.add_argument("--offline", action="store_true",
                   help="use only committed inputs; never call the LLM")


def run(args) -> int:
    try:
        s = run_entities(args.db, args.data, args.offline)
    except (FileNotFoundError, ValueError, sqlite3.OperationalError, OSError) as exc:
        print(f"entities: {exc}", file=sys.stderr)
        return 2
    print_summary(s)
    return 0 if s["unresolved"] == 0 else 1
