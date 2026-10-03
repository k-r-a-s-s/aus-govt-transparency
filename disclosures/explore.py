"""Data for the site's explorer page (``site/explore.html``): ``explore.json``.

For each view (gifts and travel, shareholdings, directorships, memberships, everything) it
keeps the entities most members declared, the members who declared them and one link per
(member, entity) pair. Every entity type is included, people named in the registers too (they
are public records). Written by ``export --site``; reads the DB read-only.
"""
from __future__ import annotations

import sqlite3
from typing import Dict, List

VIEWS = [  # (key, label, categories; empty = every category)
    ("gifts", "Gifts and sponsored travel", ("Gift", "Sponsored travel/hospitality")),
    ("shares", "Shareholdings", ("Shareholding",)),
    ("memberships", "Memberships", ("Membership",)),
    ("all", "Everything", ()),
]
TOP_ENTITIES = 60
BLOCS = ("Labor", "Coalition", "Crossbench")


def _members(con: sqlite3.Connection) -> Dict[str, dict]:
    """member_id -> name plus the latest term's chamber, party, bloc and seat."""
    out: Dict[str, dict] = {}
    for mid, name, chamber, parl, seat, party, bloc in con.execute(
            "select m.member_id, m.full_name, t.chamber, t.parliament, t.electorate_or_state, "
            "t.party, t.political_bloc from members m join member_terms t using (member_id) "
            "order by m.member_id, t.parliament, t.chamber"):
        m = out.setdefault(mid, {"id": mid, "name": name, "parliaments": []})
        if parl not in m["parliaments"]:
            m["parliaments"].append(parl)
        m.update(chamber=chamber, seat=seat or "", party=party or "",
                 bloc=bloc if bloc in BLOCS else "Crossbench")
    return out


def _view(con: sqlite3.Connection, cats: tuple, members: Dict[str, dict]) -> dict:
    where = "i.entity_id is not null"
    args: list = []
    if cats:
        where += f" and i.category in ({','.join('?' * len(cats))})"
        args = list(cats)
    pairs = con.execute(
        f"select i.entity_id, i.member_id, count(*), min(substr(i.lodged_date, 1, 4)), "
        f"max(substr(i.lodged_date, 1, 4)) from items i join entities e using (entity_id) "
        f"where {where} and i.member_id is not null group by 1, 2", args).fetchall()
    per_entity: Dict[str, list] = {}
    for eid, mid, n, lo, hi in pairs:
        per_entity.setdefault(eid, []).append((mid, n, lo, hi))
    top = sorted(per_entity, key=lambda e: (-len(per_entity[e]), e))[:TOP_ENTITIES]
    meta = {eid: (name, etype, asx) for eid, name, etype, asx in con.execute(
        f"select entity_id, canonical_name, entity_type, asx_code from entities "
        f"where entity_id in ({','.join('?' * len(top))})", top)} if top else {}
    entities, links, used = [], [], set()
    for eid in top:
        rows = per_entity[eid]
        split = {b: 0 for b in BLOCS}
        for mid, n, lo, hi in rows:
            split[members[mid]["bloc"]] += 1
            links.append([mid, eid, n])
            used.add(mid)
        years = [y for r in rows for y in r[2:] if y]
        name, etype, asx = meta[eid]
        entities.append({"id": eid, "name": name, "type": etype or "", "asx": asx or "",
                         "members": len(rows), "items": sum(r[1] for r in rows),
                         "blocs": split, "years": [min(years), max(years)] if years else []})
    return {"entities": entities, "links": links, "members": sorted(used)}


def explore_data(con: sqlite3.Connection) -> dict:
    members = _members(con)
    views = {key: dict(label=label, **_view(con, cats, members)) for key, label, cats in VIEWS}
    used = {mid for v in views.values() for mid in v["members"]}
    for v in views.values():
        del v["members"]
    loaded = dict(con.execute("select key, value from meta")).get("loaded_at", "")
    return {"loaded_at": loaded, "blocs": list(BLOCS),
            "members": [members[m] for m in sorted(used)], "views": views}
