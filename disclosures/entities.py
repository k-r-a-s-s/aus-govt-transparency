"""Entity standardisation (ADR-6): ``items.entity_name_raw`` -> ``entities`` / ``entity_aliases``.

    python -m disclosures entities [--db disclosures_v2.db] [--data data/entities] [--offline]
    python -m disclosures entities --fetch-asx    # download a new ASX snapshot, then stop

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
import datetime as dt
import hashlib
import string
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .load import DEFAULT_DB, _guard_v1, member_slug
from .normalise import normalise_entity

DEFAULT_DATA = "data/entities"
ASX_URL = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
# APH and ASX answer 403 to requests without a browser User-Agent (AGENTS.md).
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")

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
    """What every stage can see: alias -> item count, alias -> raw spellings, alias ->
    sections it occurs in, and inputs. ``reference_dir`` holds the ASX snapshots."""
    counts: Counter
    spellings: Dict[str, Counter]
    data_dir: Path
    offline: bool
    sections: Dict[str, set] = None
    reference_dir: Optional[Path] = None


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


def load_asx_exclusions(data_dir: Path) -> set:
    path = data_dir / "asx_exclusions.csv"
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as f:
        return {normalise_entity(r["alias"]) for r in csv.DictReader(f) if r["alias"].strip()}


def newest_asx_snapshot(reference_dir: Optional[Path]) -> Optional[Path]:
    """D2: ``asx_listed_companies_<YYYY-MM-DD>.csv``, the newest by date wins."""
    if reference_dir is None or not reference_dir.is_dir():
        return None
    snaps = sorted(reference_dir.glob("asx_listed_companies_????-??-??.csv"))
    return snaps[-1] if snaps else None


def read_asx_snapshot(path: Path) -> List[Tuple[str, str]]:
    """(company name, ASX code) rows. The file opens with a title line, then a blank line,
    then the header ``Company name,ASX code,GICS industry group``."""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith("Company name,")), None)
    if start is None:
        raise ValueError(f"{path}: no 'Company name,ASX code,...' header line")
    rows = []
    for r in csv.DictReader(lines[start:]):
        name, code = (r.get("Company name") or "").strip(), (r.get("ASX code") or "").strip()
        if name and code:
            rows.append((name, code.upper()))
    return rows


def asx_display_name(name: str) -> str:
    """ASX lists names in capitals: ``BHP GROUP LIMITED`` -> ``Bhp Group Limited``."""
    return string.capwords(name.lower())


def stage_asx(aliases: List[str], ctx: Context) -> Dict[str, Resolution]:
    """ADR-6 step 4: exact normalised company name, else exact ticker, against the newest
    ASX snapshot. Only aliases seen on a section-1 item are eligible (D2); the match then
    applies to every item with that alias.

    Aliases in ``asx_exclusions.csv`` never match (a ticker that is also another
    organisation's usual name, e.g. ``ING``). Normalised names shared by two listed
    companies are ambiguous and match nothing. All
    aliases matched to one code share a canonical name: the commonest raw spelling among
    the name-matched aliases (ties: alphabetically first), else the ASX name in capwords.
    """
    snap = newest_asx_snapshot(ctx.reference_dir)
    if snap is None:
        return {}
    by_name: Dict[str, set] = defaultdict(set)
    asx_names: Dict[str, str] = {}
    for name, code in read_asx_snapshot(snap):
        by_name[normalise_entity(name)].add(code)
        asx_names.setdefault(code, name)
    by_name = {n: next(iter(c)) for n, c in by_name.items() if n and len(c) == 1}
    sections = ctx.sections or {}
    excluded = load_asx_exclusions(ctx.data_dir)

    matched: Dict[str, Tuple[str, bool]] = {}  # alias -> (code, matched by name)
    for a in aliases:
        if 1 not in sections.get(a, ()) or a in excluded:
            continue
        if a in by_name:
            matched[a] = (by_name[a], True)
        elif a.upper() in asx_names:
            matched[a] = (a.upper(), False)

    spellings: Dict[str, Counter] = defaultdict(Counter)
    for a, (code, by_name_match) in matched.items():
        if by_name_match:
            spellings[code].update(ctx.spellings[a])
    out = {}
    for a, (code, _) in matched.items():
        sp = spellings.get(code)
        if sp:
            top = max(sp.values())
            canonical = min(s for s, n in sp.items() if n == top)
        else:
            canonical = asx_display_name(asx_names[code])
        out[a] = Resolution(canonical, "listed_company", code)
    return out


def fetch_asx(reference_dir: Path, http=None, today: Optional[dt.date] = None) -> Tuple[Path, int]:
    """Download the ASX listed-companies CSV to ``asx_listed_companies_<today>.csv``.

    Checks the file parses before writing it; returns (path, company rows).
    """
    import httpx

    client = http or httpx.Client(timeout=60.0, follow_redirects=True)
    resp = client.get(ASX_URL, headers={"User-Agent": BROWSER_UA})
    resp.raise_for_status()
    reference_dir.mkdir(parents=True, exist_ok=True)
    path = reference_dir / f"asx_listed_companies_{(today or dt.date.today()).isoformat()}.csv"
    tmp = path.with_suffix(".csv.tmp")
    tmp.write_bytes(resp.content)
    try:
        n = len(read_asx_snapshot(tmp))
        if n == 0:
            raise ValueError(f"{ASX_URL}: no company rows")
    except Exception:
        tmp.unlink()
        raise
    tmp.replace(path)
    return path, n


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

def resolve(items: List[Tuple], data_dir: Path, offline: bool = True,
            stages: List[Tuple[str, Stage]] = STAGES, reference_dir: Optional[Path] = None):
    """items: (item_id, entity_name_raw[, section]) with raw non-null.

    Returns (entities, aliases, item_entity): entities = {entity_id: (canonical, type, asx)},
    aliases = {alias: (entity_id|None, method, confidence)}, item_entity = {item_id: id|None}.
    """
    counts: Counter = Counter()
    spellings: Dict[str, Counter] = defaultdict(Counter)
    sections: Dict[str, set] = defaultdict(set)
    item_alias: Dict[str, str] = {}
    for iid, raw, *rest in items:
        alias = normalise_entity(raw)
        item_alias[iid] = alias
        counts[alias] += 1
        spellings[alias][" ".join(raw.split())] += 1
        if rest:
            sections[alias].add(rest[0])
    ctx = Context(counts, spellings, data_dir, offline, sections, reference_dir)

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


def default_reference_dir(data_dir: Path) -> Path:
    """``data/entities`` -> ``data/reference``."""
    return Path(data_dir).parent / "reference"


def run_entities(db_path: str | Path = DEFAULT_DB, data_dir: str | Path = DEFAULT_DATA,
                 offline: bool = True, reference_dir: str | Path | None = None) -> dict:
    db_path = Path(db_path)
    reference_dir = Path(reference_dir) if reference_dir else default_reference_dir(data_dir)
    _guard_v1(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"{db_path} not found: run `python -m disclosures load` first")
    con = sqlite3.connect(db_path)
    try:
        items = con.execute("select item_id, entity_name_raw, section from items "
                            "where entity_name_raw is not null order by item_id").fetchall()
        entities, aliases, item_entity = resolve(items, Path(data_dir), offline,
                                                 reference_dir=reference_dir)
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
            "items": dict(Counter(aliases[normalise_entity(raw)][1] for _, raw, _ in items)),
            "asx_snapshot": str(newest_asx_snapshot(reference_dir) or "none"),
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
    print(f"  ASX snapshot: {s.get('asx_snapshot', 'none')}", file=out)
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
    p.add_argument("--reference", default=None,
                   help="ASX snapshot directory (default: <data>/../reference)")
    p.add_argument("--offline", action="store_true",
                   help="use only committed inputs; never call the LLM")
    p.add_argument("--fetch-asx", action="store_true",
                   help="download a new ASX listed-companies snapshot into the reference "
                        "directory, then stop (the pipeline isn't run)")


def run(args) -> int:
    if args.fetch_asx:
        ref = Path(args.reference) if args.reference else default_reference_dir(args.data)
        try:
            path, n = fetch_asx(ref)
        except Exception as exc:  # network, HTTP status, unparseable file
            print(f"entities --fetch-asx: {exc}", file=sys.stderr)
            return 2
        print(f"entities: wrote {path} ({n} companies)")
        return 0
    try:
        s = run_entities(args.db, args.data, args.offline, args.reference)
    except (FileNotFoundError, ValueError, sqlite3.OperationalError, OSError) as exc:
        print(f"entities: {exc}", file=sys.stderr)
        return 2
    print_summary(s)
    return 0 if s["unresolved"] == 0 else 1
