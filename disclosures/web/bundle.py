"""The site's data layer (ADR-W3): ``data/*.json`` and the per-page static API.

``data/items.json`` holds every item, columnar, with string columns dictionary-encoded:

    {"web_bundle_version": "1", "n": <rows>, "columns": [<names in order>],
     "dict": {<dict column>: [<sorted distinct values>]},
     "cols": {<column>: [<n values>]}}

A ``dict`` column's values are indexes into ``dict[column]``; ``-1`` means null. ``int``
columns hold the integer itself. ``dict.member`` is the ``members`` table's ids sorted (the
order of ``data/members.json``) and ``dict.document`` is the documents' sha256 sorted (the
order of ``data/documents.json``), so those indexes also index those files. Rows are in the
order of ``export.QUERY``. ``data/schema.json`` states this contract; ``web_bundle_version``
changes whenever it does.

``data/items-extra.json`` holds what the explorer's "download CSV of this selection" needs and
``items.json`` leaves out, so a CSV built in the browser has every published column. The
explorer fetches it only when a reader downloads, never before it is ready:

    {"web_bundle_version": "1", "n": <rows>, "header": <export.HEADER>,
     "item_id": [<n item ids, row-aligned with items.json>],
     "entity": {"name": [...], "type": [...], "asx": [...]},   # aligned with dict.entity
     "entity_raw_method": [...],                              # aligned with dict.entity_raw
     "category": {"<section>": <category>}}

``members/<id>/items.json`` and ``entities/<id>/items.json`` are arrays of row objects with
the published CSV column names (``export.HEADER``) and the CSV's values.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

from ..export import COLUMNS as EXPORT_COLUMNS
from ..export import HEADER
from . import WEB_BUNDLE_VERSION
from .dataset import Dataset, sections

NULL_INDEX = -1

# (bundle column, kind, Dataset.items() field, published CSV column). Order = bundle order.
BUNDLE_COLUMNS = [
    ("member", "dict", "member_id", "member_id"),
    ("chamber", "dict", "chamber", "chamber"),
    ("parliament", "int", "parliament", "parliament"),
    ("section", "int", "section", "section"),
    ("subsection", "dict", "subsection", "subsection"),
    ("owner", "dict", "owner", "owner"),
    ("entity_raw", "dict", "entity_name_raw", "entity_name_as_printed"),
    ("entity", "dict", "entity_id", "entity_id"),
    ("description", "dict", "description", "description"),
    ("location", "dict", "location", "location"),
    ("purpose", "dict", "purpose", "purpose"),
    ("alteration", "int", "is_alteration", "is_alteration"),
    ("change_type", "dict", "change_type", "change_type"),
    ("lodged_date", "dict", "lodged_date", "lodged_date"),
    ("date_precision", "dict", "date_precision", "date_precision"),
    ("page", "int", "page", "page"),
    ("confidence", "dict", "confidence", "extraction_confidence"),
    ("document", "dict", "pdf_sha256", "source_sha256"),
]
ITEMS_ORDER_TEXT = ("chamber, parliament, member_id, source document path, page, section, "
                    "item_id (the order of the published CSV)")
TOP_ENTITIES = 15
UNKNOWN_BLOC = "Unknown"

DATA_FILES = {
    "data/items.json": "every item, columnar and dictionary-encoded (see columns)",
    "data/members.json": "members sorted by id, with terms, item count and statements",
    "data/entities.json": "entities with 2 or more items, plus every typed or ASX-coded entity",
    "data/documents.json": "statements sorted by sha256, with source URL and URL class",
    "data/items-extra.json": "item ids (row-aligned with items.json); entity names, types, ASX "
                             "codes and match methods (aligned with its dictionaries); the "
                             "published CSV header: what the explorer's CSV download adds",
    "data/search.json": "member and entity names for the index-page search box",
    "data/summary.json": "every number the overview page prints",
    "data/schema.json": "this contract",
    "members/<member_id>/items.json": "the member's items as row objects (published columns)",
    "entities/<entity_id>/items.json": "the entity's items as row objects (published columns), "
                                       "for entities with 2 or more items",
}


def dumps(obj, *, pretty: bool = False, sort_keys: bool = True) -> bytes:
    """Deterministic JSON bytes (UTF-8, trailing newline)."""
    if pretty:
        s = json.dumps(obj, ensure_ascii=False, sort_keys=sort_keys, indent=1)
    else:
        s = json.dumps(obj, ensure_ascii=False, sort_keys=sort_keys, separators=(",", ":"))
    return (s + "\n").encode("utf-8")


def write(out: Path, rel: str, data: bytes) -> None:
    p = out / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


# --- items.json ------------------------------------------------------------------------------

def encode_items(items: List[dict], member_ids: List[str], document_shas: List[str]) -> dict:
    cols: Dict[str, list] = {}
    dicts: Dict[str, list] = {}
    for name, kind, field, _ in BUNDLE_COLUMNS:
        if kind == "int":
            cols[name] = [it[field] for it in items]
            continue
        if name == "member":
            values = list(member_ids)
        elif name == "document":
            values = list(document_shas)
        else:
            values = sorted({it[field] for it in items if it[field] is not None})
        index = {v: i for i, v in enumerate(values)}
        cols[name] = [NULL_INDEX if it[field] is None else index[it[field]] for it in items]
        dicts[name] = values
    return {"web_bundle_version": WEB_BUNDLE_VERSION, "n": len(items),
            "columns": [c[0] for c in BUNDLE_COLUMNS], "dict": dicts, "cols": cols}


def decode_row(bundle: dict, i: int) -> dict:
    """Row ``i`` of a decoded ``items.json`` as {bundle column: value} (None for null)."""
    row = {}
    for name in bundle["columns"]:
        v = bundle["cols"][name][i]
        if name in bundle["dict"]:
            v = None if v == NULL_INDEX else bundle["dict"][name][v]
        row[name] = v
    return row


def schema_doc() -> dict:
    desc = {name: text for name, _, text in EXPORT_COLUMNS}
    return {
        "web_bundle_version": WEB_BUNDLE_VERSION,
        "items": {
            "file": "data/items.json",
            "layout": "columnar: cols[<column>] is an array of n values",
            "order": ITEMS_ORDER_TEXT,
            "null_index": NULL_INDEX,
            "dictionaries": "dict[<column>] lists the distinct values sorted ascending; a dict "
                            "column's values are indexes into it, -1 for null",
            "aligned": {"member": "data/members.json (sorted by id)",
                        "document": "data/documents.json (sorted by sha256)"},
            "columns": [{"name": name, "kind": kind, "published_column": pub,
                         "description": desc[pub]} for name, kind, _, pub in BUNDLE_COLUMNS],
        },
        "items_extra": {
            "file": "data/items-extra.json",
            "header": "the published CSV columns, in order (export.HEADER)",
            "item_id": "n item ids, row-aligned with items.json",
            "entity": "name, type, asx: arrays aligned with dict.entity (null when empty)",
            "entity_raw_method": "entity_match_method per printed name, aligned with "
                                 "dict.entity_raw",
            "category": "section number (as a string) -> category",
        },
        "row_objects": {
            "files": ["members/<member_id>/items.json", "entities/<entity_id>/items.json"],
            "columns": [{"name": n, "type": t, "description": d} for n, t, d in EXPORT_COLUMNS],
            "nulls": "empty string, as in the CSV",
        },
        "files": DATA_FILES,
    }


def extra_doc(bundle: dict, items: List[dict], rows: List[dict]) -> dict:
    """``data/items-extra.json``: the published CSV columns ``items.json`` does not carry,
    taken from the CSV's own rows (``Dataset.export_rows``), aligned with the bundle."""
    if len(rows) != len(items):
        raise RuntimeError(f"export rows {len(rows)} != items {len(items)}")
    for it, r in zip(items, rows):
        if it["item_id"] != r["item_id"]:
            raise RuntimeError("export rows and bundle rows are not in the same order")
    by_entity: Dict[str, tuple] = {}
    by_raw: Dict[str, str] = {}
    category: Dict[str, str] = {}
    for r in rows:
        if r["entity_id"]:
            v = (r["entity_name"], r["entity_type"], r["entity_asx_code"])
            if by_entity.setdefault(r["entity_id"], v) != v:
                raise RuntimeError(f"entity {r['entity_id']} has two names or types")
        if r["entity_name_as_printed"]:
            m = r["entity_match_method"]
            if by_raw.setdefault(r["entity_name_as_printed"], m) != m:
                raise RuntimeError(f"printed name {r['entity_name_as_printed']!r} has two "
                                   f"match methods")
        if category.setdefault(str(r["section"]), r["category"]) != r["category"]:
            raise RuntimeError(f"section {r['section']} has two categories")

    def nul(v):  # the CSV writes null as ""; the JSON keeps null
        return None if v == "" else v

    ents = bundle["dict"]["entity"]
    return {
        "web_bundle_version": WEB_BUNDLE_VERSION,
        "n": len(items),
        "header": list(HEADER),
        "item_id": [it["item_id"] for it in items],
        "entity": {"name": [nul(by_entity[e][0]) for e in ents],
                   "type": [nul(by_entity[e][1]) for e in ents],
                   "asx": [nul(by_entity[e][2]) for e in ents]},
        "entity_raw_method": [nul(by_raw.get(r, "")) for r in bundle["dict"]["entity_raw"]],
        "category": category,
    }


# --- summary ---------------------------------------------------------------------------------

def summary_doc(ds: Dataset, items: List[dict], members: List[dict], entities: List[dict],
                documents: List[dict]) -> dict:
    meta = ds.meta()
    blocs = ds.item_blocs()
    names = {s["section"]: s["name"] for s in sections()}

    def bloc(it):
        return blocs.get((it["member_id"], it["chamber"], it["parliament"])) or UNKNOWN_BLOC

    by_sb = Counter((it["section"], bloc(it)) for it in items)
    by_po = Counter((it["chamber"], it["parliament"], it["owner"]) for it in items)
    reg_items = Counter((it["chamber"], it["parliament"]) for it in items)
    reg_alt = Counter((it["chamber"], it["parliament"]) for it in items if it["is_alteration"])
    top = sorted((e for e in entities if e["items"]),
                 key=lambda e: (-e["members"], -e["items"], e["id"]))[:TOP_ENTITIES]
    return {
        "web_bundle_version": WEB_BUNDLE_VERSION,
        "items": len(items),
        "members": len(members),
        "statements": len(documents),
        "parliaments": len({it["parliament"] for it in items}),
        "registers": len(reg_items),
        "entities": len(entities),
        "entities_with_page": sum(1 for e in entities if e["page"]),
        "items_without_entity": sum(1 for it in items if it["entity_id"] is None),
        "loaded_at": meta.get("loaded_at"),
        "data_date": (meta.get("loaded_at") or "")[:10] or None,
        "schema_version": meta.get("schema_version"),
        "sections": sections(),
        "items_by_section_bloc": [
            {"section": s, "name": names[s], "bloc": b, "items": n}
            for (s, b), n in sorted(by_sb.items())],
        "top_entities_by_members": [
            {"id": e["id"], "name": e["name"], "type": e["type"], "asx": e["asx"],
             "members": e["members"], "items": e["items"]} for e in top],
        "items_by_parliament_owner": [
            {"chamber": c, "parliament": p, "owner": o, "items": n}
            for (c, p, o), n in sorted(by_po.items())],
        "alterations_by_parliament": [
            {"chamber": c, "parliament": p, "items": n, "alterations": reg_alt[(c, p)],
             "share": round(reg_alt[(c, p)] / n, 4)}
            for (c, p), n in sorted(reg_items.items())],
        "coverage": ds.coverage(),
    }


# --- writer ----------------------------------------------------------------------------------

def write_data(ds: Dataset, out: Path) -> dict:
    """Write ``data/*.json`` and the per-member / per-entity ``items.json`` under ``out``."""
    members = ds.members()
    entities = ds.entities()
    documents = ds.documents()
    items = ds.items()
    n_items = ds.con.execute("select count(*) from items").fetchone()[0]
    if len(items) != n_items:
        raise RuntimeError(f"bundle has {len(items)} rows but items has {n_items}")

    bundle = encode_items(items, [m["id"] for m in members], [d["sha256"] for d in documents])
    write(out, "data/items.json", dumps(bundle))
    write(out, "data/members.json", dumps(members))
    listed = [e for e in entities if e["page"] or e["type"] or e["asx"]]
    write(out, "data/entities.json", dumps(listed))
    write(out, "data/documents.json", dumps(documents))
    search = {
        "members": [[m["id"], m["name"], m["chamber"]] for m in members],
        "entities": [[e["id"], e["name"], e["items"]] for e in entities if e["page"]],
    }
    write(out, "data/search.json", dumps(search))
    write(out, "data/summary.json", dumps(summary_doc(ds, items, members, entities, documents),
                                          pretty=True))
    write(out, "data/schema.json", dumps(schema_doc(), pretty=True))

    rows = ds.export_rows()
    if len(rows) != n_items:
        raise RuntimeError(f"export rows {len(rows)} != items {n_items}")
    write(out, "data/items-extra.json", dumps(extra_doc(bundle, items, rows)))
    by_member = defaultdict(list)
    by_entity = defaultdict(list)
    for r in rows:
        by_member[r["member_id"]].append(r)
        if r["entity_id"]:
            by_entity[r["entity_id"]].append(r)
    for m in members:
        write(out, f"members/{m['id']}/items.json", dumps(by_member.get(m["id"], []),
                                                          sort_keys=False))
    n_entity_files = 0
    for e in entities:
        if e["page"]:
            write(out, f"entities/{e['id']}/items.json", dumps(by_entity[e["id"]],
                                                               sort_keys=False))
            n_entity_files += 1
    return {"items": len(items), "members": len(members), "entities": len(entities),
            "entities_listed": len(listed), "entity_files": n_entity_files,
            "documents": len(documents),
            "items_json_bytes": (out / "data/items.json").stat().st_size}


_unknown = [c[3] for c in BUNDLE_COLUMNS if c[3] not in HEADER]
if _unknown:  # the bundle contract names published CSV columns only
    raise ImportError(f"BUNDLE_COLUMNS name unknown published columns {_unknown}")
