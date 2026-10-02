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
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from .load import Overrides, member_slug, norm_electorate, norm_person_name

MANIFEST = Path("pdfs/manifest.csv")
OVERRIDES = Path("data/overrides")
PDF_MEMBERS_HEADER = ["pdf_path", "member_id", "canonical_full_name", "electorate_or_state", "source"]
ALIASES_HEADER = ["name_variant", "electorate_or_state", "member_id", "canonical_full_name", "source"]


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
    part = pdf_path.split("/")[1] if pdf_path.count("/") >= 2 else ""
    return int(part) if part.isdigit() else None


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
    src = f"aph_{parliament}"
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


def _lookalikes(mid: str, canonical: str, ov: Overrides, earlier: Dict[str, set]) -> str:
    """Earlier members who share this new member's surname: the eyeball list for a returning
    MP misread as new (a nickname, a full given name, a changed seat)."""
    sur = _surname(canonical)
    hits = [f"{o} ({ov.member_electorate.get(o, '?')}, {min(ps)}-{max(ps)})"
            for o, ps in sorted(earlier.items()) if o != mid and _surname(ov.canonical_name.get(o, o)) == sur]
    return f"  CHECK same surname: {'; '.join(hits)}" if hits else ""


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m disclosures.members", description=__doc__.split("\n")[0])
    p.add_argument("--chamber", choices=["house"], default="house")
    p.add_argument("--parliament", type=int, required=True)
    p.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    args = p.parse_args(argv)
    counts = resolve(args.chamber, args.parliament, write=not args.dry_run)
    return 1 if counts["collisions"] else 0


if __name__ == "__main__":
    sys.exit(main())
