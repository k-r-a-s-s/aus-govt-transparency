"""Member identity for newly scraped PDFs (D3 new-members rule): ``python -m disclosures.members``.

    python -m disclosures.members --chamber house --parliament 48           # write overrides
    python -m disclosures.members --chamber house --parliament 48 --dry-run # report only

For every ``pdfs/manifest.csv`` row of that chamber/parliament without a ``pdf_members.csv``
row: the listing's member name + electorate resolve through ``member_aliases.csv`` (normalised
name with the electorate first, then the name alone, as ``Overrides.resolve_member``). A
resolved member is ``returning`` if an earlier parliament's PDF already carries its member_id.
Unresolved names are ``new``: member_id = slug of the canonical name, plus a
``member_aliases.csv`` row (``source=aph_{NN}``). Returning MPs whose listing name differs from
every known variant ("Robert Katter" for Bob Katter) and new MPs whose Wikipedia name differs
from the listing ("Thomas French" -> Tom French) are handled by hand-added alias rows, which
this command then resolves. Every new member is printed with any earlier member who shares
its surname, so a misread returning MP can't silently split a history.

    python -m disclosures.members --parliament 48 --party-terms --wiki-revision 1303424746 \
        --wiki-revision 1377733140

``--party-terms`` (D3 48th parties) reads the Wikipedia "Members of the Australian House of
Representatives" table at each pinned revision (the first one at the start of the term; later
ones only add members the earlier ones lack, i.e. by-elections) and writes a
``party_terms.csv`` row (``source=wikipedia_{NN}``) for every member of that parliament's PDFs
that has none, or an ``unknown_party.csv`` row when no table row matches. Party names go
through ``party_mapping.csv``; a Queensland Liberal or National is ``Liberal National Party``
(v1's convention); blocs come from ``political_blocs.csv``, else Crossbench.

    python -m disclosures.members --chamber senate --parliament 48 [--dry-run]
    python -m disclosures.members --chamber senate --parliament 48 --party-terms

The Senate (T3.7) works the same way on the ``pdfs/senate/NN/*.json`` manifest rows
(``source=aph_senate_{NN}``); a senator who was an MP resolves to the House member_id by name and
is printed as ``CROSS-CHAMBER``. Senate ``--party-terms`` needs no Wikipedia: it reads
``senatorParty`` from each saved API payload (``source=aph_senate_api``), the party at scrape
time.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from .load import Overrides, member_slug, norm_electorate, norm_person_name

MANIFEST = Path("pdfs/manifest.csv")
OVERRIDES = Path("data/overrides")
PDF_MEMBERS_HEADER = ["pdf_path", "member_id", "canonical_full_name", "electorate_or_state", "source"]
ALIASES_HEADER = ["name_variant", "electorate_or_state", "member_id", "canonical_full_name", "source"]
PARTY_HEADER = ["member_id", "chamber", "parliament", "party", "political_bloc", "source"]
UNKNOWN_HEADER = ["member_id", "chamber", "parliament", "note"]
WIKI_TITLE = {48: "Members of the Australian House of Representatives, 2025\u20132028"}
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/140.0 Safari/537.36")


def _read(path: Path) -> List[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _write(path: Path, header: List[str], rows: List[dict]) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=header, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8")


def _parliament(pdf_path: str) -> Optional[int]:
    """pdfs/{NN}/x.pdf (House) or pdfs/senate/{NN}/x.json (Senate) -> NN."""
    parts = pdf_path.split("/")
    part = parts[2] if len(parts) >= 4 and parts[1] == "senate" else (
        parts[1] if len(parts) >= 3 else "")
    return int(part) if part.isdigit() else None


def _chamber(pdf_path: str) -> str:
    parts = pdf_path.split("/")
    return "senate" if len(parts) >= 4 and parts[1] == "senate" else "house"


def _surname(name: str) -> str:
    toks = norm_person_name(name).split()
    return toks[-1] if toks else ""


def resolve(chamber: str, parliament: int, *, root: Path = Path("."), write: bool = True,
            out=sys.stdout) -> Dict[str, int]:
    """-> counts {returning, new, already, collisions}. Writes the two CSVs unless ``write`` is
    False. ``collisions`` > 0 (a new slug equal to an existing member_id) writes nothing."""
    ov_dir = root / OVERRIDES
    ov = Overrides(ov_dir)
    pdf_rows = _read(ov_dir / "pdf_members.csv")
    alias_rows = _read(ov_dir / "member_aliases.csv")
    earlier: Dict[str, set] = defaultdict(set)  # member_id -> parliaments before this one
    for r in pdf_rows:
        p = _parliament(r["pdf_path"])
        if r["member_id"] and p is not None and p < parliament:
            earlier[r["member_id"]].add(p)
    known_ids = set(ov.canonical_name) | {r["member_id"] for r in pdf_rows if r["member_id"]}

    todo = [r for r in _read(root / MANIFEST)
            if r["chamber"] == chamber and int(r["parliament"]) == parliament]
    counts = {"returning": 0, "new": 0, "already": 0, "collisions": 0}
    new_pdf, new_alias, new_ids = [], [], {}
    src = f"aph_{parliament}" if chamber == "house" else f"aph_senate_{parliament}"
    house_ids = {r["member_id"] for r in pdf_rows if r["member_id"] and _chamber(r["pdf_path"]) == "house"}
    for m in sorted(todo, key=lambda r: r["pdf_path"]):
        if m["pdf_path"] in ov.pdf_members:
            counts["already"] += 1
            continue
        name, elec = m["member_name"].strip(), m["electorate_or_state"].strip()
        key = norm_person_name(name)
        hits = ov.alias_by_name_elec.get((key, norm_electorate(elec)), set())
        if len(hits) != 1:
            hits = ov.alias_by_name.get(key, set())
        if len(hits) > 1:
            raise SystemExit(f"members: {name} ({elec}) matches several members {sorted(hits)}; "
                             "add an electorate-specific member_aliases.csv row")
        if hits:
            mid = next(iter(hits))
            canonical = ov.canonical_name[mid]
            kind = "returning" if earlier.get(mid) else "new"
        else:
            canonical, mid, kind = name, member_slug(name), "new"
            if mid in known_ids or mid in new_ids:
                counts["collisions"] += 1
                print(f"COLLISION {m['pdf_path']}: slug {mid} is already a member", file=out)
                continue
            new_ids[mid] = canonical
            new_alias.append({"name_variant": name, "electorate_or_state": elec, "member_id": mid,
                              "canonical_full_name": canonical, "source": src})
        counts[kind] += 1
        new_pdf.append({"pdf_path": m["pdf_path"], "member_id": mid, "canonical_full_name": canonical,
                        "electorate_or_state": elec, "source": src})
        if kind == "new":
            print(f"NEW {mid:28} {canonical} ({elec}){_lookalikes(mid, canonical, ov, earlier)}",
                  file=out)
        elif norm_person_name(name) != norm_person_name(canonical):
            print(f"RETURNING via alias {name} ({elec}) -> {mid}", file=out)
        if chamber == "senate" and mid in house_ids:
            print(f"CROSS-CHAMBER {name} ({elec}) -> {mid} (House "
                  f"{','.join(str(p) for p in sorted(earlier.get(mid, ())))})", file=out)

    print(f"members {chamber} {parliament}: {counts['returning']} returning, {counts['new']} new, "
          f"{counts['already']} already in pdf_members, {counts['collisions']} slug collisions",
          file=out)
    if write and not counts["collisions"] and (new_pdf or new_alias):
        pdf_rows = sorted(pdf_rows + new_pdf, key=lambda r: r["pdf_path"])
        seen = {(r["name_variant"], r["electorate_or_state"], r["member_id"]) for r in alias_rows}
        alias_rows += [r for r in new_alias
                       if (r["name_variant"], r["electorate_or_state"], r["member_id"]) not in seen]
        alias_rows.sort(key=lambda r: (r["member_id"], r["name_variant"].casefold(), r["name_variant"],
                                       r["electorate_or_state"], r["source"]))
        _write(ov_dir / "pdf_members.csv", PDF_MEMBERS_HEADER, pdf_rows)
        _write(ov_dir / "member_aliases.csv", ALIASES_HEADER, alias_rows)
    return counts


def parse_wiki_members(wikitext: str) -> List[dict]:
    """Rows of the "== Members ==" table: {name, party, electorate, state}. The party is the
    first ``{{Australian politics/name|X}}`` (or ``[[...|X]]`` link) after the name."""
    start = wikitext.index("== Members ==")
    end = wikitext.find("\n==", start + 13)
    out = []
    for row in wikitext[start:end if end > 0 else None].split("\n|-")[1:]:
        m = re.search(r"\{\{sortname\|([^|}]+)\|([^|}]+)", row)
        if not m:
            continue
        rest = row[m.end():]
        party = re.search(r"\{\{Australian politics/name\|([^}|]+)", rest)
        if party is None:
            party = re.search(r"colspan=\"?2\"?\s*\|\s*\[\[[^|\]]+\|([^\]]+)\]\]", rest)
        elec = re.search(r"\[\[Division of [^|\]]+\|([^\]]+)\]\]", rest)
        state = re.search(r"Division of [^\]]+\]\][\s|]*(NSW|VIC|QLD|WA|SA|TAS|ACT|NT)\b", rest, re.I)
        out.append({"name": f"{m.group(1).strip()} {m.group(2).strip()}",
                    "party": party.group(1).strip() if party else "",
                    "electorate": elec.group(1).strip() if elec else "",
                    "state": state.group(1).upper() if state else ""})
    return out


def fetch_wiki_revision(parliament: int, revid: int) -> str:
    q = urllib.parse.urlencode({"action": "query", "prop": "revisions", "revids": revid,
                                "rvprop": "content", "rvslots": "main", "format": "json",
                                "formatversion": 2})
    req = urllib.request.Request(f"https://en.wikipedia.org/w/api.php?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        page = json.load(resp)["query"]["pages"][0]
    if page.get("title") != WIKI_TITLE[parliament]:
        raise SystemExit(f"members: revision {revid} is of {page.get('title')!r}, not {WIKI_TITLE[parliament]!r}")
    return page["revisions"][0]["slots"]["main"]["content"]


def party_terms(chamber: str, parliament: int, wikitexts: List[str], *, root: Path = Path("."),
                write: bool = True, out=sys.stdout) -> Dict[str, int]:
    """-> counts {added, unknown, already}. ``wikitexts`` in priority order (start of term first)."""
    ov_dir = root / OVERRIDES
    ov = Overrides(ov_dir)
    mapping = {r["variant"].casefold(): r["canonical_party"] for r in _read(ov_dir / "party_mapping.csv")}
    blocs = {r["party"]: r["bloc"] for r in _read(ov_dir / "political_blocs.csv")}
    by_mid: Dict[str, dict] = {}
    for text in wikitexts:
        for w in parse_wiki_members(text):
            key = norm_person_name(w["name"])
            hits = ov.alias_by_name_elec.get((key, norm_electorate(w["electorate"])), set())
            if len(hits) != 1:
                hits = ov.alias_by_name.get(key, set())
            mid = next(iter(hits)) if len(hits) == 1 else member_slug(w["name"])
            by_mid.setdefault(mid, w)
    mids = sorted({r["member_id"] for p, r in ov.pdf_members.items()
                   if r["member_id"] and _parliament(p) == parliament and _chamber(p) == chamber})
    counts = {"added": 0, "unknown": 0, "already": 0}
    new_party, new_unknown = [], []
    src = f"wikipedia_{parliament}"
    for mid in mids:
        key = (mid, chamber, parliament)
        if key in ov.party_terms or key in ov.unknown_party:
            counts["already"] += 1
            continue
        w = by_mid.get(mid)
        party = mapping.get(w["party"].casefold(), w["party"]) if w and w["party"] else ""
        if party in ("Liberal Party of Australia", "National Party of Australia") and w["state"] == "QLD":
            party = "Liberal National Party"
        if not party:
            counts["unknown"] += 1
            new_unknown.append({"member_id": mid, "chamber": chamber, "parliament": parliament,
                                "note": f"no row in Wikipedia {WIKI_TITLE.get(parliament, '')}"})
            print(f"UNKNOWN {mid}", file=out)
            continue
        counts["added"] += 1
        new_party.append({"member_id": mid, "chamber": chamber, "parliament": parliament, "party": party,
                          "political_bloc": blocs.get(party, "Crossbench"), "source": src})
    print(f"party terms {chamber} {parliament}: {counts['added']} added, {counts['unknown']} unknown, "
          f"{counts['already']} already present", file=out)
    if write and (new_party or new_unknown):
        order = lambda r: (r["member_id"], r["chamber"], int(r["parliament"]))
        _write(ov_dir / "party_terms.csv", PARTY_HEADER,
               sorted(_read(ov_dir / "party_terms.csv") + new_party, key=order))
        _write(ov_dir / "unknown_party.csv", UNKNOWN_HEADER,
               sorted(_read(ov_dir / "unknown_party.csv") + new_unknown, key=order))
    return counts


def senate_party_terms(parliament: int, *, root: Path = Path("."), write: bool = True,
                       out=sys.stdout) -> Dict[str, int]:
    """D3: the party of each Senate member term is the API's ``senatorParty`` in the saved
    payload (``source=aph_senate_api``). That is the current party, not the start-of-term one.
    -> counts {added, unknown, already}."""
    ov_dir = root / OVERRIDES
    ov = Overrides(ov_dir)
    mapping = {r["variant"].casefold(): r["canonical_party"] for r in _read(ov_dir / "party_mapping.csv")}
    blocs = {r["party"]: r["bloc"] for r in _read(ov_dir / "political_blocs.csv")}
    counts = {"added": 0, "unknown": 0, "already": 0}
    new_party, new_unknown = [], []
    for path, r in sorted(ov.pdf_members.items()):
        mid = r["member_id"]
        if not mid or _chamber(path) != "senate" or _parliament(path) != parliament:
            continue
        key = (mid, "senate", parliament)
        if key in ov.party_terms or key in ov.unknown_party:
            counts["already"] += 1
            continue
        st = json.loads((root / path).read_text(encoding="utf-8"))["senatorInterestStatement"]
        raw = (st.get("senatorParty") or "").strip()
        party = mapping.get(raw.casefold(), raw)
        if party in ("Liberal Party of Australia", "National Party of Australia") and \
                (st.get("electorateState") or "").strip().lower() == "queensland":
            party = "Liberal National Party"
        if not party:
            counts["unknown"] += 1
            new_unknown.append({"member_id": mid, "chamber": "senate", "parliament": parliament,
                                "note": "no senatorParty in the APH senators' interests API"})
            print(f"UNKNOWN {mid}", file=out)
            continue
        counts["added"] += 1
        new_party.append({"member_id": mid, "chamber": "senate", "parliament": parliament,
                          "party": party, "political_bloc": blocs.get(party, "Crossbench"),
                          "source": "aph_senate_api"})
    print(f"party terms senate {parliament}: {counts['added']} added, {counts['unknown']} unknown, "
          f"{counts['already']} already present", file=out)
    if write and (new_party or new_unknown):
        order = lambda r: (r["member_id"], r["chamber"], int(r["parliament"]))
        _write(ov_dir / "party_terms.csv", PARTY_HEADER,
               sorted(_read(ov_dir / "party_terms.csv") + new_party, key=order))
        _write(ov_dir / "unknown_party.csv", UNKNOWN_HEADER,
               sorted(_read(ov_dir / "unknown_party.csv") + new_unknown, key=order))
    return counts


def _lookalikes(mid: str, canonical: str, ov: Overrides, earlier: Dict[str, set]) -> str:
    """Earlier members who share this new member's surname: the eyeball list for a returning
    MP misread as new (a nickname, a full given name, a changed seat)."""
    sur = _surname(canonical)
    hits = [f"{o} ({ov.member_electorate.get(o, '?')}, {min(ps)}-{max(ps)})"
            for o, ps in sorted(earlier.items()) if o != mid and _surname(ov.canonical_name.get(o, o)) == sur]
    return f"  CHECK same surname: {'; '.join(hits)}" if hits else ""


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m disclosures.members", description=__doc__.split("\n")[0])
    p.add_argument("--chamber", choices=["house", "senate"], default="house")
    p.add_argument("--parliament", type=int, required=True)
    p.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    p.add_argument("--party-terms", action="store_true", help="write party_terms rows from Wikipedia")
    p.add_argument("--wiki-revision", type=int, action="append", default=[],
                   help="pinned revision id of the members list (repeatable; start of term first)")
    args = p.parse_args(argv)
    if args.party_terms and args.chamber == "senate":
        senate_party_terms(args.parliament, write=not args.dry_run)
        return 0
    if args.party_terms:
        if not args.wiki_revision:
            p.error("--party-terms needs at least one --wiki-revision")
        texts = [fetch_wiki_revision(args.parliament, r) for r in args.wiki_revision]
        counts = party_terms(args.chamber, args.parliament, texts, write=not args.dry_run)
        return 0
    counts = resolve(args.chamber, args.parliament, write=not args.dry_run)
    return 1 if counts["collisions"] else 0


if __name__ == "__main__":
    sys.exit(main())
