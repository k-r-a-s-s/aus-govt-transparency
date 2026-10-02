"""Entity standardisation (ADR-6): ``items.entity_name_raw`` -> ``entities`` / ``entity_aliases``.

    python -m disclosures entities [--db disclosures_v2.db] [--data data/entities] [--offline]
    python -m disclosures entities --fetch-asx    # download a new ASX snapshot, then stop
    python -m disclosures entities --draft-candidates [--top 200]   # curation worksheet, then stop

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
import json
import os
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
    llm: Optional["LLMRunner"] = None  # online long-tail runner; None = cache only


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
    table = load_curated(ctx.data_dir)
    return {a: table[a] for a in aliases if a in table}


def load_curated(data_dir: Path) -> Dict[str, Resolution]:
    """``aliases.csv`` as {normalised alias: Resolution}; empty if the file is missing."""
    path = data_dir / "aliases.csv"
    table: Dict[str, Resolution] = {}
    if not path.exists():
        return table
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            alias = normalise_entity(r["alias"])
            if not alias:
                continue
            table[alias] = Resolution(r["canonical_name"].strip(),
                                      (r.get("entity_type") or "").strip() or None,
                                      (r.get("asx_code") or "").strip().upper() or None)
    return table


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


def asx_index(reference_dir: Optional[Path]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """From the newest snapshot: ({normalised name: code} for names only one company has,
    {code: ASX name}); both empty with no snapshot."""
    snap = newest_asx_snapshot(reference_dir)
    if snap is None:
        return {}, {}
    by_name: Dict[str, set] = defaultdict(set)
    asx_names: Dict[str, str] = {}
    for name, code in read_asx_snapshot(snap):
        by_name[normalise_entity(name)].add(code)
        asx_names.setdefault(code, name)
    return {n: next(iter(c)) for n, c in by_name.items() if n and len(c) == 1}, asx_names


def stage_asx(aliases: List[str], ctx: Context) -> Dict[str, Resolution]:
    """ADR-6 step 4: exact normalised company name, else exact ticker, against the newest
    ASX snapshot. Only aliases seen on a section-1 item are eligible (D2); the match then
    applies to every item with that alias.

    Aliases in ``asx_exclusions.csv`` never match (a ticker that is also another
    organisation's usual name, e.g. ``ING``). Normalised names shared by two listed
    companies are ambiguous and match nothing. All
    aliases matched to one code share a canonical name: the commonest raw spelling among
    the name-matched aliases (ties: alphabetically first), else the ASX name in capwords.
    A code that ``aliases.csv`` already uses takes that row's canonical name and type.
    """
    by_name, asx_names = asx_index(ctx.reference_dir)
    if not asx_names:
        return {}
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
    # A code the curated table already names joins that entity rather than starting a
    # second one under a different spelling (first curated row per code wins).
    curated_by_code: Dict[str, Resolution] = {}
    for res in load_curated(ctx.data_dir).values():
        if res.asx_code:
            curated_by_code.setdefault(res.asx_code, res)
    out = {}
    for a, (code, _) in matched.items():
        sp = spellings.get(code)
        if code in curated_by_code:
            cur = curated_by_code[code]
            out[a] = Resolution(cur.canonical_name, cur.entity_type, code)
            continue
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


LLM_CACHE_FILE = "llm_decisions.jsonl"
LLM_PROMPT_FILE = Path(__file__).parent / "prompts" / "entities_llm.md"
LLM_PROMPT_VERSION = "entities-llm-v1"
LLM_MODEL = "google/gemini-3.8-flash"
LLM_PROVIDER_ORDER = "google-ai-studio/flex"
LLM_IGNORE_PROVIDERS = "azure"
LLM_MIN_ITEMS = 2
LLM_FUZZ = 85
LLM_PACK_ALIASES = 40  # aliases per request; a block is never split across requests
CONFIDENCES = ("high", "medium", "low")


class LLMCacheMiss(Exception):
    """Long-tail blocks with no cached decision (offline, a request limit, or bad replies)."""

    def __init__(self, blocks: List[List[str]], reason: str):
        super().__init__(f"{len(blocks)} long-tail block(s) uncached: {reason}")
        self.blocks = blocks
        self.reason = reason


def llm_blocks(aliases: List[str], counts: Counter, min_items: int = LLM_MIN_ITEMS,
               threshold: int = LLM_FUZZ) -> List[List[str]]:
    """D2: aliases with >= ``min_items`` items, blocked by first token; within a block, names
    joined by a chain of rapidfuzz ``token_set_ratio`` >= ``threshold`` form one candidate
    block. Names with no such neighbour are 1-name blocks (typed, never merged). Sorted."""
    from rapidfuzz import fuzz

    by_token: Dict[str, List[str]] = defaultdict(list)
    for a in sorted(aliases):
        if counts[a] >= min_items:
            by_token[a.split()[0]].append(a)
    blocks = []
    for names in by_token.values():
        parent = {a: a for a in names}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if fuzz.token_set_ratio(a, b) >= threshold:
                    ra, rb = find(a), find(b)
                    if ra != rb:
                        parent[max(ra, rb)] = min(ra, rb)
        comps: Dict[str, List[str]] = defaultdict(list)
        for a in names:
            comps[find(a)].append(a)
        blocks.extend(sorted(c) for c in comps.values())
    return sorted(blocks)


def block_key(members: List[str], prompt_version: str = LLM_PROMPT_VERSION) -> str:
    """D2: sha1 of the sorted block members plus the prompt version."""
    return hashlib.sha1(json.dumps([sorted(members), prompt_version]).encode()).hexdigest()


def read_llm_cache(data_dir: Path) -> Dict[str, dict]:
    """``llm_decisions.jsonl`` as {key: record}; the last line for a key wins."""
    path = Path(data_dir) / LLM_CACHE_FILE
    out: Dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                out[rec["key"]] = rec
    return out


def write_llm_cache(data_dir: Path, records: Dict[str, dict]) -> None:
    """Rewrite the cache sorted by key (deterministic diffs), atomically."""
    path = Path(data_dir) / LLM_CACHE_FILE
    tmp = path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for k in sorted(records):
            f.write(json.dumps(records[k], ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(path)


def llm_response_schema() -> dict:
    group = {"type": "object", "properties": {
        "members": {"type": "array", "items": {"type": "string"}},
        "canonical_name": {"type": "string"},
        "entity_type": {"type": "string", "enum": list(ENTITY_TYPES)},
        "confidence": {"type": "string", "enum": list(CONFIDENCES)},
    }, "required": ["members", "canonical_name", "entity_type", "confidence"]}
    block = {"type": "object", "properties": {
        "block_id": {"type": "string"},
        "groups": {"type": "array", "items": group},
    }, "required": ["block_id", "groups"]}
    return {"type": "object", "properties": {"blocks": {"type": "array", "items": block}},
            "required": ["blocks"]}


def llm_prompt(blocks: List[List[str]], ctx: Context) -> str:
    lines = [LLM_PROMPT_FILE.read_text(encoding="utf-8").rstrip(), ""]
    for i, members in enumerate(blocks, 1):
        lines.append(f"BLOCK b{i}")
        for a in members:
            secs = ",".join(str(x) for x in sorted((ctx.sections or {}).get(a, ())))
            sp = "; ".join(f'"{s}" ({n})' for s, n in sorted(
                ctx.spellings[a].items(), key=lambda kv: (-kv[1], kv[0]))[:3])
            lines.append(f'- "{a}": {ctx.counts[a]} items; sections {secs or "?"}; printed {sp}')
        lines.append("")
    return "\n".join(lines)


def check_groups(members: List[str], groups) -> List[dict]:
    """The groups must partition ``members`` exactly, with valid fields; else ValueError."""
    if not isinstance(groups, list) or not groups:
        raise ValueError("no groups")
    seen: List[str] = []
    out = []
    for g in groups:
        ms = g.get("members") if isinstance(g, dict) else None
        name = (g.get("canonical_name") or "").strip() if isinstance(g, dict) else ""
        if not ms or not name:
            raise ValueError(f"group without members or canonical_name: {g!r}"[:200])
        if g.get("entity_type") not in ENTITY_TYPES or g.get("confidence") not in CONFIDENCES:
            raise ValueError(f"bad entity_type/confidence: {g!r}"[:200])
        seen.extend(ms)
        out.append({"members": sorted(ms), "canonical_name": name,
                    "entity_type": g["entity_type"], "confidence": g["confidence"]})
    if sorted(seen) != sorted(members):
        raise ValueError(f"groups don't partition the block {members[:3]}...")
    return sorted(out, key=lambda g: g["members"])


def pack_blocks(blocks: List[List[str]], size: int = LLM_PACK_ALIASES) -> List[List[List[str]]]:
    packs: List[List[List[str]]] = []
    cur: List[List[str]] = []
    n = 0
    for b in blocks:
        if cur and n + len(b) > size:
            packs.append(cur)
            cur, n = [], 0
        cur.append(b)
        n += len(b)
    if cur:
        packs.append(cur)
    return packs


@dataclass
class LLMRunner:
    """Online long-tail calls. ``backend`` has ``complete_json(text, schema, name, retry)``
    (:class:`disclosures.openrouter.OpenRouterBackend`). ``limit`` caps requests per run."""
    backend: object
    model: str
    workers: int = 8
    limit: Optional[int] = None
    pack_size: int = LLM_PACK_ALIASES
    max_retries: int = 4
    sleep: Callable[[float], None] = None
    log: object = None
    spent: float = 0.0
    requests: int = 0

    def _retry(self, fn):
        import random
        import time

        attempt = 0
        while True:
            try:
                return fn()
            except Exception as exc:
                if attempt >= self.max_retries or not self.backend.is_retryable(exc):
                    raise
                (self.sleep or time.sleep)(2.0 * (2 ** attempt) + random.uniform(0, 1))
                attempt += 1

    def _call(self, pack: List[List[str]], ctx: Context):
        """-> ({key: record} for the blocks that came back valid, [failed blocks], cost)."""
        try:
            r = self.backend.complete_json(llm_prompt(pack, ctx), llm_response_schema(),
                                           "entity_groups", self._retry)
        except Exception as exc:  # transport, HTTP, cut-off or non-JSON reply
            self._print(f"  llm: request failed ({type(exc).__name__}: {str(exc)[:200]})")
            return {}, pack, 0.0
        by_id = {b.get("block_id"): b for b in r.data.get("blocks", []) if isinstance(b, dict)}
        got, failed = {}, []
        for i, members in enumerate(pack, 1):
            try:
                groups = check_groups(members, (by_id.get(f"b{i}") or {}).get("groups"))
            except ValueError as exc:
                self._print(f"  llm: block {members[0]!r}: {exc}")
                failed.append(members)
                continue
            key = block_key(members)
            got[key] = {"key": key, "prompt_version": LLM_PROMPT_VERSION, "model": self.model,
                        "members": members, "groups": groups}
        return got, failed, r.cost_usd or 0.0

    def _print(self, msg: str) -> None:
        print(msg, file=self.log or sys.stderr, flush=True)

    def run(self, blocks: List[List[str]], ctx: Context, cache: Dict[str, dict]) -> List[List[str]]:
        """Resolve ``blocks`` (all uncached), appending each request's results to the cache
        file as they arrive. A pack with bad blocks retries those blocks alone, once.
        Returns the blocks still uncached."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        path = Path(ctx.data_dir) / LLM_CACHE_FILE
        packs = pack_blocks(blocks, self.pack_size)
        if self.limit is not None:
            packs = packs[:max(self.limit, 0)]
        left = {block_key(b): b for b in blocks}
        retried = set()
        with path.open("a", encoding="utf-8") as f, ThreadPoolExecutor(self.workers) as pool:
            futs = {pool.submit(self._call, p, ctx): p for p in packs}
            while futs:
                for fut in as_completed(list(futs)):
                    futs.pop(fut)
                    got, failed, cost = fut.result()
                    self.requests += 1
                    self.spent += cost
                    for k, rec in got.items():
                        cache[k] = rec
                        left.pop(k, None)
                        f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
                    f.flush()
                    for b in failed:
                        k = block_key(b)
                        if k not in retried:
                            retried.add(k)
                            futs[pool.submit(self._call, [b], ctx)] = [b]
                    self._print(f"  llm: {self.requests} requests, {len(cache)} cached blocks, "
                                f"US${self.spent:.4f} so far")
                    break
        return sorted(left.values())


def stage_llm(aliases: List[str], ctx: Context) -> Dict[str, Resolution]:
    """ADR-6 step 5: long-tail grouping of aliases with >= 2 items, from the committed cache
    ``llm_decisions.jsonl``. Uncached blocks are sent to the LLM when ``ctx.llm`` is set
    (online), else (``--offline``) they raise :class:`LLMCacheMiss`, as do blocks still
    uncached after the online run (request limit, bad replies). ``confidence`` is the LLM's.
    """
    blocks = llm_blocks(aliases, ctx.counts)
    if not blocks:
        return {}
    cache = read_llm_cache(ctx.data_dir)
    missing = [b for b in blocks if block_key(b) not in cache]
    if missing:
        if ctx.offline or ctx.llm is None:
            raise LLMCacheMiss(missing, "--offline uses the cache only" if ctx.offline
                               else "no LLM configured")
        missing = ctx.llm.run(missing, ctx, cache)
        write_llm_cache(ctx.data_dir, read_llm_cache(ctx.data_dir))
        if missing:
            raise LLMCacheMiss(missing, "still uncached after this run; re-run to continue")
    by_name, _ = asx_index(ctx.reference_dir)
    excluded = load_asx_exclusions(ctx.data_dir)
    out = {}
    for b in blocks:
        for g in cache[block_key(b)]["groups"]:
            etype, code = g["entity_type"], None
            if etype == "listed_company":
                # AC-3.4: listed_company needs a code from the snapshot. Take the one the
                # canonical name (else a member) matches exactly; none (foreign-listed,
                # delisted) -> other, as for delisted curated rows (DECISIONS T2.5).
                names = [normalise_entity(g["canonical_name"])] + [
                    a for a in g["members"] if a not in excluded]
                code = next((by_name[n] for n in names if n in by_name), None)
                etype = "listed_company" if code else "other"
            res = Resolution(g["canonical_name"], etype, code, g["confidence"])
            for a in g["members"]:
                out[a] = res
    return out


def stage_singleton(aliases: List[str], ctx: Context) -> Dict[str, Resolution]:
    """Whatever is left becomes its own untyped entity, named by its commonest raw spelling.

    ADR-6 means 1-item aliases (the LLM stage takes every >= 2-item one), so every named,
    non-generic item has an entity (AC-3.3).
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
            stages: Optional[List[Tuple[str, Stage]]] = None,
            reference_dir: Optional[Path] = None, llm: Optional[LLMRunner] = None):
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
    ctx = Context(counts, spellings, data_dir, offline, sections, reference_dir, llm)
    stages = STAGES if stages is None else stages

    generic = load_generic_terms(data_dir)
    aliases: Dict[str, Tuple[Optional[str], str, Optional[str]]] = {}
    for a in sorted(counts):
        if a in generic or not a:
            aliases[a] = (None, "generic", None)

    entities: Dict[str, Tuple[str, Optional[str], Optional[str]]] = {}
    code_entity: Dict[str, str] = {}
    unresolved = sorted(a for a in counts if a not in aliases)
    for method, stage in stages:
        if not unresolved:
            break
        found = stage(unresolved, ctx)
        for a in sorted(found):
            res = found[a]
            eid = entity_id_for(res.canonical_name)
            # One entity per ASX code: a later stage's alias with a code an entity already
            # has joins that entity (curated > asx > llm).
            if res.asx_code and res.asx_code in code_entity:
                eid = code_entity[res.asx_code]
            # An id that already exists (same canonical slug from an earlier stage or alias)
            # is the same organisation: the alias joins it and the first definition stands.
            if eid not in entities:
                entities[eid] = (res.canonical_name, res.entity_type, res.asx_code)
            if entities[eid][2]:
                code_entity.setdefault(entities[eid][2], eid)
            aliases[a] = (eid, method, res.confidence)
        unresolved = [a for a in unresolved if a not in found]
    item_entity = {iid: aliases[a][0] for iid, a in item_alias.items()}
    return entities, aliases, item_entity


def llm_plan(db_path: str | Path, data_dir: str | Path,
             reference_dir: str | Path | None = None) -> dict:
    """``--llm-dry-run``: the long-tail blocks the real DB would produce, how many are
    uncached, and the requests and prompt size that would take. No calls, no writes."""
    db_path, data_dir = Path(db_path), Path(data_dir)
    reference_dir = Path(reference_dir) if reference_dir else default_reference_dir(data_dir)
    if not db_path.exists():
        raise FileNotFoundError(f"{db_path} not found: run `python -m disclosures load` first")
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        items = con.execute("select item_id, entity_name_raw, section from items "
                            "where entity_name_raw is not null order by item_id").fetchall()
    finally:
        con.close()
    seen: dict = {}

    def spy(aliases, ctx):
        seen["blocks"] = llm_blocks(aliases, ctx.counts)
        seen["ctx"] = ctx
        return {}

    stages = [(m, spy if m == "llm" else st) for m, st in STAGES]
    resolve(items, data_dir, True, stages, reference_dir)
    blocks, ctx = seen.get("blocks", []), seen.get("ctx")
    cache = read_llm_cache(data_dir)
    missing = [b for b in blocks if block_key(b) not in cache]
    packs = pack_blocks(missing)
    return {"blocks": len(blocks), "multi": sum(len(b) > 1 for b in blocks),
            "aliases": sum(len(b) for b in blocks),
            "items": sum(ctx.counts[a] for b in blocks for a in b) if ctx else 0,
            "uncached": len(missing), "requests": len(packs),
            "prompt_chars": sum(len(llm_prompt(p, ctx)) for p in packs)}


COVERAGE_TOP = 200
COVERAGE_MIN = 0.95


def curated_coverage(counts: Counter, data_dir: Path, top: int = COVERAGE_TOP) -> Tuple[int, int]:
    """AC-3.2: items of the ``top`` non-generic normalised names (by item count, ties
    alphabetical, as in ``--draft-candidates``) whose name has a row in ``aliases.csv``.
    Returns (covered items, total items)."""
    generic = load_generic_terms(data_dir)
    curated = load_curated(data_dir)
    heads = sorted((a for a in counts if a and a not in generic),
                   key=lambda a: (-counts[a], a))[:top]
    return sum(counts[a] for a in heads if a in curated), sum(counts[a] for a in heads)


def default_reference_dir(data_dir: Path) -> Path:
    """``data/entities`` -> ``data/reference``."""
    return Path(data_dir).parent / "reference"


def run_entities(db_path: str | Path = DEFAULT_DB, data_dir: str | Path = DEFAULT_DATA,
                 offline: bool = True, reference_dir: str | Path | None = None,
                 llm: Optional[LLMRunner] = None) -> dict:
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
                                                 reference_dir=reference_dir, llm=llm)
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
            "coverage": curated_coverage(Counter(normalise_entity(raw) for _, raw, _ in items),
                                         Path(data_dir)),
            # AC-3.3: named items whose alias isn't generic but got no entity
            "unresolved": con.execute(
                "select count(*) from items where entity_name_raw is not null and "
                "entity_id is null").fetchone()[0],
        }
    finally:
        con.close()
    summary["unresolved"] -= summary["items"].get("generic", 0)
    return summary


CANDIDATE_FIELDS = ("rank", "alias", "item_count", "sections", "sample_spellings", "asx_code",
                    "asx_name", "variant_count", "variants")
CANDIDATES_FILE = "alias_candidates.csv"


def draft_candidates(items: List[Tuple], data_dir: Path, reference_dir: Optional[Path] = None,
                     top: int = 200, threshold: int = 90) -> List[dict]:
    """ADR-6 step 3 worksheet: the ``top`` normalised names by item count (generic removed),
    each with every other non-generic normalised name whose ``token_set_ratio`` to it is
    >= ``threshold``. items as for ``resolve``. ``asx_code`` is what the ASX stage would give
    the head; a variant that would ASX-match shows its code in brackets.
    """
    from rapidfuzz import fuzz, process

    counts: Counter = Counter()
    spellings: Dict[str, Counter] = defaultdict(Counter)
    sections: Dict[str, set] = defaultdict(set)
    for _, raw, *rest in items:
        alias = normalise_entity(raw)
        counts[alias] += 1
        spellings[alias][" ".join(raw.split())] += 1
        if rest:
            sections[alias].add(rest[0])
    generic = load_generic_terms(data_dir)
    names = sorted(a for a in counts if a and a not in generic)
    ctx = Context(counts, spellings, data_dir, True, sections, reference_dir)
    asx = stage_asx(names, ctx)
    snap = newest_asx_snapshot(reference_dir)
    asx_names = {code: name for name, code in read_asx_snapshot(snap)} if snap else {}

    def by_count(a):
        return (-counts[a], a)

    rows = []
    for rank, head in enumerate(sorted(names, key=by_count)[:top], 1):
        hits = process.extract(head, names, scorer=fuzz.token_set_ratio,
                               score_cutoff=threshold, limit=None)
        variants = sorted((h[0] for h in hits if h[0] != head), key=by_count)
        code = asx[head].asx_code if head in asx else ""
        rows.append({
            "rank": rank,
            "alias": head,
            "item_count": counts[head],
            "sections": " ".join(str(x) for x in sorted(sections.get(head, ()))),
            "sample_spellings": " | ".join(
                f"{s} ({n})" for s, n in sorted(spellings[head].items(),
                                                key=lambda kv: (-kv[1], kv[0]))[:3]),
            "asx_code": code,
            "asx_name": asx_names.get(code, "") if code else "",
            "variant_count": len(variants),
            "variants": " | ".join(
                f"{v} ({counts[v]})" + (f" [{asx[v].asx_code}]" if v in asx else "")
                for v in variants),
        })
    return rows


def write_candidates(db_path: str | Path, data_dir: str | Path, out: Optional[Path] = None,
                     reference_dir: str | Path | None = None, top: int = 200) -> Tuple[Path, int]:
    db_path, data_dir = Path(db_path), Path(data_dir)
    reference_dir = Path(reference_dir) if reference_dir else default_reference_dir(data_dir)
    if not db_path.exists():
        raise FileNotFoundError(f"{db_path} not found: run `python -m disclosures load` first")
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        items = con.execute("select item_id, entity_name_raw, section from items "
                            "where entity_name_raw is not null order by item_id").fetchall()
    finally:
        con.close()
    rows = draft_candidates(items, data_dir, reference_dir, top)
    out = Path(out) if out else data_dir / CANDIDATES_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CANDIDATE_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return out, len(rows)


def print_summary(s: dict, out=None) -> None:
    out = out or sys.stdout
    print(f"entities: {s['named_items']} named items -> {s['entities']} entities", file=out)
    print(f"  ASX snapshot: {s.get('asx_snapshot', 'none')}", file=out)
    print(f"  {'method':10s} {'aliases':>8s} {'items':>8s}", file=out)
    for m in METHODS:
        print(f"  {m:10s} {s['aliases'].get(m, 0):8d} {s['items'].get(m, 0):8d}", file=out)
    if "coverage" in s:
        covered, total = s["coverage"]
        pct = covered / total if total else 0.0
        print(f"  aliases.csv coverage of the top {COVERAGE_TOP} names (AC-3.2): "
              f"{covered}/{total} items = {pct:.1%} {'OK' if pct >= COVERAGE_MIN else 'FAIL'}",
              file=out)
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
    p.add_argument("--draft-candidates", nargs="?", const="", default=None, metavar="CSV",
                   help="write the curation worksheet (top names by item count plus fuzzy "
                        "variants, default <data>/alias_candidates.csv), then stop")
    p.add_argument("--top", type=int, default=200,
                   help="heads in the --draft-candidates worksheet (default 200)")
    g = p.add_argument_group("long-tail LLM (online mode only; paid, OpenRouter)")
    g.add_argument("--llm-dry-run", action="store_true",
                   help="print the long-tail blocks, uncached count and requests, then stop")
    g.add_argument("--llm-limit", type=int, default=None, metavar="N",
                   help="send at most N requests this run (the rest stay uncached; exit 1)")
    g.add_argument("--model", default=LLM_MODEL, help=f"OpenRouter model (default {LLM_MODEL})")
    g.add_argument("--provider-order", default=LLM_PROVIDER_ORDER,
                   help=f"OpenRouter endpoints, comma-separated (default {LLM_PROVIDER_ORDER})")
    g.add_argument("--ignore-providers", default=LLM_IGNORE_PROVIDERS,
                   help=f"OpenRouter providers to skip (default {LLM_IGNORE_PROVIDERS})")
    g.add_argument("--workers", type=int, default=8, help="parallel requests (default 8)")


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
    if args.draft_candidates is not None:
        try:
            path, n = write_candidates(args.db, args.data, args.draft_candidates or None,
                                       args.reference, args.top)
        except (FileNotFoundError, ValueError, sqlite3.OperationalError, OSError) as exc:
            print(f"entities --draft-candidates: {exc}", file=sys.stderr)
            return 2
        print(f"entities: wrote {path} ({n} heads)")
        return 0
    if args.llm_dry_run:
        try:
            plan = llm_plan(args.db, args.data, args.reference)
        except (FileNotFoundError, ValueError, sqlite3.OperationalError, OSError) as exc:
            print(f"entities --llm-dry-run: {exc}", file=sys.stderr)
            return 2
        print(f"entities: long tail {plan['aliases']} aliases / {plan['items']} items in "
              f"{plan['blocks']} blocks ({plan['multi']} with > 1 name); {plan['uncached']} "
              f"uncached -> {plan['requests']} requests, ~{plan['prompt_chars'] // 4} prompt "
              f"tokens")
        return 0
    llm = None
    if not args.offline:
        try:
            llm = make_llm_runner(args)
        except ValueError as exc:
            print(f"entities: {exc}", file=sys.stderr)
            return 2
    try:
        s = run_entities(args.db, args.data, args.offline, args.reference, llm=llm)
    except LLMCacheMiss as exc:
        print(f"entities: {exc}", file=sys.stderr)
        for b in exc.blocks[:20]:
            print(f"  {' | '.join(b)}", file=sys.stderr)
        if len(exc.blocks) > 20:
            print(f"  ... and {len(exc.blocks) - 20} more", file=sys.stderr)
        if llm is not None:
            print(f"entities: llm {llm.requests} requests, US${llm.spent:.4f}", file=sys.stderr)
        return 1
    except (FileNotFoundError, ValueError, sqlite3.OperationalError, OSError) as exc:
        print(f"entities: {exc}", file=sys.stderr)
        return 2
    print_summary(s)
    if llm is not None:
        print(f"  llm: {llm.requests} requests this run, US${llm.spent:.4f}")
    return 0 if s["unresolved"] == 0 else 1


def make_llm_runner(args, http=None, env=None) -> LLMRunner:
    """The online long-tail runner from CLI args; the key comes from the environment or
    ``.env.local`` (never printed). ValueError if there's no key or the model is banned."""
    from .openrouter import OpenRouterBackend, resolve_openrouter_key, resolve_openrouter_model

    if env is None:
        from dotenv import load_dotenv

        load_dotenv(".env.local", override=False)
        env = os.environ
    key = resolve_openrouter_key(env)
    if not key:
        raise ValueError("no OpenRouter key: set OPENROUTER_KEY (environment or .env.local), "
                         "or run with --offline")
    model = resolve_openrouter_model(args.model, env=env)
    split = lambda v: [x.strip() for x in (v or "").split(",") if x.strip()] or None
    backend = OpenRouterBackend(key, model, http=http, provider_order=split(args.provider_order),
                                ignore_providers=split(args.ignore_providers),
                                max_tokens=32768, response_schema=llm_response_schema())
    return LLMRunner(backend, model, workers=max(args.workers, 1), limit=args.llm_limit)
