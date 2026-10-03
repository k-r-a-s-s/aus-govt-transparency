"""``web make-fixture``: a small, deterministic subset of the real DB for tests (ADR-W12).

    python -m disclosures web make-fixture --db site/disclosures_v2.db \
        --manifest pdfs/manifest.csv --out tests/fixtures/web --members 6 --seed 1

Writes ``<out>/mini.db`` (the source DB's exact schema; the chosen members' rows in ``members``,
``member_terms``, ``documents`` and ``items``; the entities their items name; the aliases of
those entities plus the aliases their printed names normalise to; ``meta`` copied with
``fixture = 1``) and ``<out>/mini-manifest.csv`` (the chosen documents' manifest rows, same
header, original order).

Members are picked by slot, each slot a constraint, with ``random.Random(seed)`` choosing
among the sorted candidates that meet it and are small enough (at most ``MAX_ITEMS`` items):

1. ``house-43``: a House 43rd statement (scanned PDF, ``house-redirect`` URL class)
2. ``house-47``: a House 47th statement (``house-pdf``, static.aph.gov.au)
3. ``house-48``: a House 48th statement (``house-api``)
4. ``senate-48``: a Senate 48th statement (``senate-json``)
5. ``family``: spouse and dependent-child items
6. ``alterations``: many alterations (at least the 90th percentile of all members)

The six together must cover the Labor, Coalition and Crossbench blocs and include at least one
``low``-confidence item; the seeded draw repeats until they do. Further members (``--members`` > 6) are drawn from the remaining small members. Same inputs and
seed give the same bytes: rows are inserted in primary-key order, the file is VACUUMed, and
nothing time-dependent is written.
"""
from __future__ import annotations

import csv
import io
import os
import random
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple

from ..normalise import normalise_entity
from . import urls as U
from .dataset import Dataset, DatasetError

MAX_ITEMS = 300
ATTEMPTS = 10_000
REQUIRED_BLOCS = {"Labor", "Coalition", "Crossbench"}
MIN_MEMBERS = 6
DB_NAME = "mini.db"
MANIFEST_NAME = "mini-manifest.csv"

# table -> primary-key order used for inserts
TABLE_ORDER = {
    "members": "member_id",
    "member_terms": "member_id, chamber, parliament",
    "entities": "entity_id",
    "entity_aliases": "alias_normalised",
    "documents": "pdf_sha256",
    "items": "item_id",
    "meta": "key",
}


def _profiles(ds: Dataset) -> Dict[str, dict]:
    docs = ds.documents()
    prof: Dict[str, dict] = {}
    for m in ds.members():
        prof[m["id"]] = {"items": m["items"], "classes": set(), "registers": set(),
                         "blocs": {t["bloc"] for t in m["terms"]}, "low": 0,
                         "spouse": 0, "dependent_child": 0, "alterations": 0}
    for d in docs:
        p = prof[d["member_id"]]
        p["classes"].add(d["url_class"])
        p["registers"].add((d["chamber"], d["parliament"]))
    for mid, owner, n in ds.con.execute(
            "select member_id, owner, count(*) from items group by 1, 2"):
        if owner in ("spouse", "dependent_child"):
            prof[mid][owner] = n
    for mid, n in ds.con.execute(
            "select member_id, count(*) from items where is_alteration = 1 group by 1"):
        prof[mid]["alterations"] = n
    for mid, n in ds.con.execute(
            "select member_id, count(*) from items where confidence = 'low' group by 1"):
        prof[mid]["low"] = n
    return prof


def choose_members(ds: Dataset, n: int, seed: int) -> List[Tuple[str, str]]:
    """[(member_id, slot reason)] in slot order."""
    if n < MIN_MEMBERS:
        raise DatasetError(f"--members must be at least {MIN_MEMBERS} (one per slot)")
    prof = _profiles(ds)
    alts = sorted(p["alterations"] for p in prof.values())
    p90 = alts[int(0.9 * (len(alts) - 1))]
    small = sorted(m for m, p in prof.items() if 0 < p["items"] <= MAX_ITEMS)
    slots = [
        ("house-43", "House 43rd statement, scanned PDF via the APH redirector (house-redirect)",
         lambda p: ("house", 43) in p["registers"] and U.HOUSE_REDIRECT in p["classes"]),
        ("house-47", "House 47th statement, static.aph.gov.au PDF (house-pdf)",
         lambda p: ("house", 47) in p["registers"] and U.HOUSE_PDF in p["classes"]),
        ("house-48", "House 48th statement from the interests-register API (house-api)",
         lambda p: ("house", 48) in p["registers"] and U.HOUSE_API in p["classes"]),
        ("senate-48", "Senate 48th statement from the Senate API (senate-json)",
         lambda p: ("senate", 48) in p["registers"] and U.SENATE_JSON in p["classes"]),
        ("family", "spouse and dependent-child items",
         lambda p: p["spouse"] > 0 and p["dependent_child"] > 0),
        ("alterations", f"many alterations (at least {p90}, the 90th percentile)",
         lambda p: p["alterations"] >= p90),
    ]
    rng = random.Random(seed)
    for _ in range(ATTEMPTS):
        chosen: List[Tuple[str, str]] = []
        taken = set()
        for slot, reason, ok in slots:
            cands = [m for m in small if m not in taken and ok(prof[m])]
            if not cands:
                raise DatasetError(f"no member with at most {MAX_ITEMS} items fits slot {slot}")
            m = rng.choice(cands)
            taken.add(m)
            chosen.append((m, f"{slot}: {reason}"))
        # Set-level requirements: all three blocs, and at least one low-confidence item.
        blocs = set().union(*(prof[m]["blocs"] for m in taken))
        if REQUIRED_BLOCS <= blocs and any(prof[m]["low"] for m in taken):
            break
    else:
        raise DatasetError(f"no selection in {ATTEMPTS} draws covers blocs {REQUIRED_BLOCS} "
                           "and a low-confidence item")
    rest = [m for m in small if m not in taken]
    for m in rng.sample(rest, min(n - len(chosen), len(rest))):
        chosen.append((m, "extra: random small member"))
    return chosen


def _rows(con: sqlite3.Connection, table: str, where: str, params: list) -> Tuple[list, list]:
    cur = con.execute(f"select * from {table} {where} order by {TABLE_ORDER[table]}", params)
    return [c[0] for c in cur.description], cur.fetchall()


def _in(col: str, values) -> Tuple[str, list]:
    values = sorted(values)
    return f"where {col} in ({','.join('?' * len(values))})" if values else "where 0", values


def make_fixture(db: str | Path, manifest: str | Path, out: str | Path, members: int = 6,
                 seed: int = 1) -> dict:
    db, manifest, out = Path(db), Path(manifest), Path(out)
    out_db = out / DB_NAME
    if out_db.exists() and os.path.samefile(out_db, db):
        raise DatasetError(f"{out_db} is the source DB")
    with Dataset(db, manifest) as ds:
        chosen = choose_members(ds, members, seed)
        ids = [m for m, _ in chosen]
        src = ds.con
        tables: Dict[str, Tuple[list, list]] = {}
        tables["members"] = _rows(src, "members", *_in("member_id", ids))
        tables["member_terms"] = _rows(src, "member_terms", *_in("member_id", ids))
        tables["items"] = _rows(src, "items", *_in("member_id", ids))
        cols = tables["items"][0]
        items = [dict(zip(cols, r)) for r in tables["items"][1]]
        where, params = _in("member_id", ids)
        shas = {it["pdf_sha256"] for it in items} | {
            r[0] for r in src.execute(f"select pdf_sha256 from documents {where}", params)}
        tables["documents"] = _rows(src, "documents", *_in("pdf_sha256", shas))
        eids = {it["entity_id"] for it in items if it["entity_id"]}
        tables["entities"] = _rows(src, "entities", *_in("entity_id", eids))
        norms = {normalise_entity(it["entity_name_raw"]) for it in items
                 if it["entity_name_raw"] is not None}
        acols, arows = _rows(src, "entity_aliases", "", [])
        ia, ie = acols.index("alias_normalised"), acols.index("entity_id")
        tables["entity_aliases"] = (acols, [r for r in arows
                                            if r[ie] in eids or r[ia] in norms])
        mcols, mrows = _rows(src, "meta", "", [])
        meta = dict(mrows)
        meta["fixture"] = "1"
        tables["meta"] = (mcols, sorted(meta.items()))
        schema = [r[0] for r in src.execute(
            "select sql from sqlite_master where sql is not null order by rowid")]
        page_size = src.execute("pragma page_size").fetchone()[0]
        doc_shas = {r[0] for r in tables["documents"][1]}

    out.mkdir(parents=True, exist_ok=True)
    tmp = out / (DB_NAME + ".tmp")
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(tmp)
    try:
        con.execute(f"pragma page_size = {int(page_size)}")
        for sql in schema:
            con.execute(sql)
        for table in TABLE_ORDER:
            cols, rows = tables[table]
            con.executemany(f"insert into {table} ({','.join(cols)}) values "
                            f"({','.join('?' * len(cols))})", rows)
        con.commit()
        con.execute("vacuum")
    finally:
        con.close()
    tmp.replace(out_db)

    text = manifest.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    kept = [lines[0]]
    header = next(csv.reader(io.StringIO(lines[0])))
    i_sha = header.index("pdf_sha256")
    for line in lines[1:]:
        row = next(csv.reader(io.StringIO(line)), None)
        if row and len(row) == len(header) and row[i_sha] in doc_shas:
            kept.append(line)
    if len(kept) - 1 != len(doc_shas):
        raise DatasetError(f"manifest has {len(kept) - 1} rows for {len(doc_shas)} documents")
    (out / MANIFEST_NAME).write_text("".join(kept), encoding="utf-8")
    return {"members": chosen, "db": str(out_db), "manifest": str(out / MANIFEST_NAME),
            "bytes": out_db.stat().st_size,
            "counts": {t: len(tables[t][1]) for t in TABLE_ORDER}}

