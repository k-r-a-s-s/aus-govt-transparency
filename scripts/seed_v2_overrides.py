#!/usr/bin/env python3
"""One-off seeding of `data/overrides/*.csv` (Disclosures v2, ADR-7) from v1 assets.

Reads, never writes: v1 `disclosures.db` (opened read-only), `src/cleaning/*.py` (dict literals
parsed with `ast`, nothing imported), `output/all_mps_debug.csv` and
`output/all_mps_most_recent_party.csv` (v1's Wikipedia scrapes), and `git ls-files pdfs`.
Writes the CSVs under `data/overrides/`. The hand-curated parts (identity fixes, PDFs that v1
never loaded) are the `MANUAL_*` tables below, so the output is reproducible:

    .venv/bin/python scripts/seed_v2_overrides.py [--check]

`--check` rebuilds in memory and exits 1 if any committed CSV differs. The script only knows
v1's parliaments (43rd-47th). Rows added later by `python -m disclosures.members` (48th and on:
`pdf_members`/`party_terms`/`unknown_party` rows of parliament >= 48, `member_aliases` rows with
`source=aph_*`) are hand-maintained: the script keeps them as they are and checks the rest.
Once v1 is deleted in
Phase 5 this script stops working; the committed CSVs are then the source of truth and are
edited by hand.
"""
from __future__ import annotations

import argparse
import ast
import csv
import io
import re
import sqlite3
import subprocess
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "overrides"
sys.path.insert(0, str(REPO))
from disclosures.load import member_slug, norm_electorate, norm_person_name  # noqa: E402


# --- v1 dict literals ---------------------------------------------------------------------

def _literal(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
        if isinstance(node, ast.FunctionDef) and node.name == name:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return):
                    return ast.literal_eval(sub.value)
    raise KeyError(f"{name} not found in {path}")


CLEAN = REPO / "src" / "cleaning"
PARTY_MAPPING = _literal(CLEAN / "get_mp_party_affiliations.py", "PARTY_MAPPING")
MP_NAME_SPECIAL_CASES = _literal(CLEAN / "get_mp_party_affiliations.py", "MP_NAME_SPECIAL_CASES")
FALLBACK_MP_PARTIES = _literal(CLEAN / "get_mp_party_affiliations.py", "FALLBACK_MP_PARTIES")
MERGE_OVERRIDES = _literal(CLEAN / "merge_duplicate_mps.py", "get_manual_merge_overrides")
COALITION_PARTIES = _literal(CLEAN / "add_political_bloc.py", "COALITION_PARTIES")
LABOR_PARTIES = _literal(CLEAN / "add_political_bloc.py", "LABOR_PARTIES")

# Party-name variants seen in v1's Wikipedia CSVs (and, last, the APH senators' interests API,
# T3.7) that PARTY_MAPPING does not cover.
EXTRA_PARTY_MAPPING = {
    "Palmer United": "United Australia Party",
    "Xenophon/Centre Alliance": "Centre Alliance",
    "Nationals WA": "National Party of Australia",
    "Liberal / Independent": "Liberal/Independent",
    "Country Liberal Party": "Country Liberal",
}

# --- manual identity fixes ----------------------------------------------------------------

# v1 mp_id -> Wikipedia name, where electorate+surname matching cannot decide (electorate
# renamed, wrong electorate in v1, or the v1 name is a fragment).
MANUAL_V1_TO_WIKI: dict[str, str] = {}

# PDFs v1 never loaded (no rows in v1 `disclosures`). Value: Wikipedia name, or None for a
# non-member document (the register's resolution text, the explanatory-notes booklet).
MANUAL_PDF: dict[str, str | None] = {
    "pdfs/44/alexanderj_44p.pdf": "John Alexander",
    "pdfs/44/elliotj_44p.pdf": "Justine Elliot",
    "pdfs/44/ellisk_44p.pdf": "Kate Ellis",
    "pdfs/44/entschw_44p.pdf": "Warren Entsch",
    "pdfs/44/feeneyd_44p.pdf": "David Feeney",
    "pdfs/44/fergusonl_44p.pdf": "Laurie Ferguson",
    "pdfs/45/wilsonj_45p_2.pdf": "Josh Wilson",
    "pdfs/46/wells_46p.pdf": "Anika Wells",
    "pdfs/47/thwaites_47p.pdf": "Kate Thwaites",
    "pdfs/44/interestsr_44p.pdf": None,
    "pdfs/45/interestsr_45p.pdf": None,
    "pdfs/46/interestsr_46p.pdf": None,
    "pdfs/47/interestsr_47p.pdf": None,
    "pdfs/46/explanatory_notes___booklet_1.pdf": None,
    "pdfs/47/explanatory_notes___booklet_1.pdf": None,
}

# PDF -> Wikipedia name where v1's filename->mp mapping is wrong.
MANUAL_PDF_FIX: dict[str, str] = {}

# (member Wikipedia name, parliament) -> party, where "most recent party" is wrong for an
# earlier term and the fact is recorded in v1's own data. Empty unless documented.
MANUAL_PARTY_TERM: dict[tuple[str, int], str] = {}


# --- helpers ------------------------------------------------------------------------------

def clean_wiki_name(name: str) -> str:
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"\s*\[[^\]]*\]", "", name)
    return re.sub(r"\s+", " ", name.replace(" ", " ")).strip()


def canon_party(p: str | None) -> str | None:
    if p is None or not str(p).strip():
        return None
    p = str(p).strip()
    p = EXTRA_PARTY_MAPPING.get(p, p)
    return PARTY_MAPPING.get(p, p)


def bloc(party: str | None) -> str | None:
    if party is None:
        return None
    if party in COALITION_PARTIES:
        return "Coalition"
    if party in LABOR_PARTIES:
        return "Labor"
    return "Crossbench"


def earlier_term_party(party: str) -> str:
    """'Liberal/Independent' in the latest term means the defection happened in that term:
    earlier terms were plain Liberal (same for National / Labor)."""
    m = re.match(r"^\s*(Liberal|National|Labor)\s*/\s*Independent\s*$", party)
    if not m:
        return party
    return {"Liberal": "Liberal Party of Australia", "National": "National Party of Australia",
            "Labor": "Australian Labor Party"}[m.group(1)]


def surname_tokens(name: str) -> list[str]:
    toks = norm_person_name(name).split()
    return toks


def parl_of(path: str) -> int:
    """pdfs/{NN}/x.pdf (House) or pdfs/senate/{NN}/x.json (Senate) -> NN."""
    parts = path.split("/")
    return int(parts[2] if parts[1] == "senate" else parts[1])


V1_LAST_PARLIAMENT = 47


def hand_rows(name: str) -> list[list[str]]:
    """Committed rows this script doesn't derive (see the module docstring); kept verbatim."""
    path = OUT / name
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if name == "pdf_members.csv":
        keep = [r for r in rows if parl_of(r["pdf_path"]) > V1_LAST_PARLIAMENT]
    elif name == "member_aliases.csv":
        keep = [r for r in rows if r["source"].startswith("aph_")]
    elif name in ("party_terms.csv", "unknown_party.csv"):
        keep = [r for r in rows if int(r["parliament"]) > V1_LAST_PARLIAMENT]
    else:
        keep = []
    return [list(r.values()) for r in keep]


# --- build --------------------------------------------------------------------------------

def load_wiki():
    """Wikipedia name -> {"electorate", "terms": {parliament: party}} (latest wins on clash)."""
    people: dict[str, dict] = {}
    for fn in ("output/all_mps_most_recent_party.csv", "output/all_mps_debug.csv"):
        with open(REPO / fn, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                name = clean_wiki_name(r["Name"])
                p = people.setdefault(name, {"electorate": r["Electorate"], "terms": {}})
                parl = int(r["Parliament"])
                p["terms"][parl] = canon_party(r["Party"])
                if parl >= max(p["terms"]):
                    p["electorate"] = r["Electorate"]
    return people


def match_v1_to_wiki(v1_rows, wiki):
    by_elec = defaultdict(list)
    for name, p in wiki.items():
        by_elec[norm_electorate(p["electorate"])].append(name)
    out, unresolved = {}, []
    for mp_id, full_name, electorate, _party in v1_rows:
        if mp_id in MANUAL_V1_TO_WIKI:
            out[mp_id] = MANUAL_V1_TO_WIKI[mp_id]
            continue
        # 1. v1's own name tables (special cases, merge overrides).
        alias = MP_NAME_SPECIAL_CASES.get(full_name)
        if alias is None:
            for (frm, elec), to in MERGE_OVERRIDES.items():
                if norm_person_name(frm) == norm_person_name(full_name):
                    alias = MP_NAME_SPECIAL_CASES.get(to, to)
        toks = set(surname_tokens(full_name))
        cands = []
        if alias and alias in wiki:
            cands = [alias]
        else:
            # 2. same electorate, Wikipedia surname tokens all present in the v1 name.
            for name in by_elec.get(norm_electorate(electorate), []):
                sur = surname_tokens(name)[-1:]
                if sur and set(sur) <= toks:
                    cands.append(name)
            if len(cands) > 1:  # several with that surname: require the first name too
                cands = [n for n in cands if surname_tokens(n)[0] in toks] or cands
        if len(cands) != 1:
            # 3. anywhere: surname + first name (or nickname via special cases).
            cands = [n for n in wiki
                     if surname_tokens(n)[-1] in toks and surname_tokens(n)[0] in toks]
        if len(cands) == 1:
            out[mp_id] = cands[0]
        else:
            unresolved.append((mp_id, full_name, electorate, cands))
    return out, unresolved


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--report", action="store_true", help="print matching diagnostics")
    args = ap.parse_args(argv)

    conn = sqlite3.connect(f"file:{REPO / 'disclosures.db'}?mode=ro", uri=True)
    v1_rows = conn.execute("select mp_id, full_name, electorate, party from mps").fetchall()
    v1_by_id = {r[0]: r for r in v1_rows}
    pdf_to_mp = dict(conn.execute("select pdf_filename, min(mp_id) from disclosures group by 1"))
    files = subprocess.run(["git", "ls-files", "pdfs"], cwd=REPO, capture_output=True, text=True,
                           check=True).stdout.split()
    files = sorted(f for f in files if f.lower().endswith(".pdf") and parl_of(f) <= V1_LAST_PARLIAMENT)
    wiki = load_wiki()
    v1_to_wiki, unresolved = match_v1_to_wiki(v1_rows, wiki)

    if args.report:
        for u in unresolved:
            print("UNRESOLVED v1", u)

    # Person key: Wikipedia name when matched, else v1 full_name with special cases applied.
    def person_of_v1(mp_id: str) -> str:
        if mp_id in v1_to_wiki:
            return v1_to_wiki[mp_id]
        full = v1_by_id[mp_id][1]
        return MP_NAME_SPECIAL_CASES.get(full, full)

    # documents -> person
    pdf_rows = []
    person_parls = defaultdict(set)
    def pdf_electorate(person, v1_elec):
        """v1's per-record electorate (closest to per-PDF: renamed seats keep the old name),
        spelt as Wikipedia does when they agree; Wikipedia's latest otherwise."""
        w = wiki.get(person, {}).get("electorate", "")
        if not v1_elec or norm_electorate(v1_elec) == norm_electorate(w):
            return w
        v1_elec = re.sub(r"\s+(WA|NSW|VIC|QLD|SA|TAS|NT|ACT)$", "", v1_elec.strip())
        return v1_elec.title() if v1_elec.isupper() else v1_elec

    for f in files:
        base = f.split("/")[-1]
        if f in MANUAL_PDF_FIX:
            person, source = MANUAL_PDF_FIX[f], "manual"
            v1_elec = ""
        elif base in pdf_to_mp and f not in MANUAL_PDF:
            person, source = person_of_v1(pdf_to_mp[base]), "v1"
            v1_elec = v1_by_id[pdf_to_mp[base]][2]
        elif f in MANUAL_PDF:
            person, source = MANUAL_PDF[f], ("stem" if MANUAL_PDF[f] else "non_member")
            v1_elec = ""
        else:
            raise SystemExit(f"no member for {f}: add it to MANUAL_PDF")
        if person is None:
            pdf_rows.append([f, "", "", "", source])
            continue
        elec = pdf_electorate(person, v1_elec)
        pdf_rows.append([f, member_slug(person), person, elec, source])
        person_parls[person].add(parl_of(f))
        if args.report:
            stem = re.sub(r"[^a-z]", "", base.split("_")[0].lower()) or base
            toks = norm_person_name(person).split()
            sufs = ["".join(toks[i:]) for i in range(1, len(toks))]
            if not any(stem.startswith(x[:5]) for x in sufs):
                print("CHECK stem/name", f, person, source)

    # member_aliases
    alias_rows = set()
    def add_alias(variant, elec, person, source):
        # only people who own a tracked PDF (drops v1's placeholder mp "Unknown")
        if variant and person and person in person_parls:
            alias_rows.add((variant, elec or "", member_slug(person), person, source))
    for mp_id, full, elec, _ in v1_rows:
        person = person_of_v1(mp_id)
        add_alias(full, elec, person, "v1_mps.full_name")
        add_alias(mp_id, elec, person, "v1_mps.mp_id")
    for (frm, elec), to in MERGE_OVERRIDES.items():
        to_person = MP_NAME_SPECIAL_CASES.get(to, to)
        to_person = next((v1_to_wiki[i] for i, r in v1_by_id.items() if r[1] == to and i in v1_to_wiki),
                         to_person)
        add_alias(frm, elec, to_person, "v1_merge_overrides")
        add_alias(to, elec, to_person, "v1_merge_overrides")
    persons_by_norm = defaultdict(set)
    for r in alias_rows:
        persons_by_norm[norm_person_name(r[0])].add(r[3])
    for db_name, wiki_name in MP_NAME_SPECIAL_CASES.items():
        persons = persons_by_norm.get(norm_person_name(db_name), set()) | (
            {wiki_name} if wiki_name in wiki else set())
        for person in persons:
            add_alias(db_name, "", person, "v1_name_special_cases")
            add_alias(wiki_name, "", person, "v1_name_special_cases")
    for person in person_parls:
        add_alias(person, wiki.get(person, {}).get("electorate", ""), person, "canonical")
    alias_rows = sorted(alias_rows, key=lambda r: (r[2], r[0].casefold(), r[0], r[1], r[4]))

    # party_terms / unknown_party
    party_rows, unknown_rows = [], []
    for person in sorted(person_parls, key=member_slug):
        mid = member_slug(person)
        terms = wiki.get(person, {}).get("terms", {})
        latest = max(terms) if terms else None
        v1_party = None
        for mp_id, r in v1_by_id.items():
            if person_of_v1(mp_id) == person and r[3]:
                v1_party = canon_party(r[3])
        fallback = canon_party(FALLBACK_MP_PARTIES.get(person))
        for parl in sorted(person_parls[person]):
            if (person, parl) in MANUAL_PARTY_TERM:
                party, src = MANUAL_PARTY_TERM[(person, parl)], "manual"
            elif parl in terms:
                party, src = terms[parl], f"wikipedia_{parl}"
            elif latest is not None and parl < latest:
                party, src = earlier_term_party(terms[latest]), f"wikipedia_{latest}_carried_back"
            elif latest is not None:
                party, src = terms[latest], f"wikipedia_{latest}_carried_forward"
            elif v1_party and v1_party != "N/A":
                party, src = (earlier_term_party(v1_party) if parl < max(person_parls[person])
                              else v1_party), "v1_mps.party"
            elif fallback and fallback != "N/A":
                party, src = fallback, "v1_fallback_parties"
            else:
                unknown_rows.append([mid, "house", parl, "no party in v1 sources"])
                continue
            party_rows.append([mid, "house", parl, party, bloc(party), src])

    mapping_rows = sorted({(k, v) for k, v in PARTY_MAPPING.items()}
                          | {(k, canon_party(v)) for k, v in EXTRA_PARTY_MAPPING.items()},
                          key=lambda r: r[0].casefold())
    bloc_rows = sorted({(p, "Coalition") for p in COALITION_PARTIES}
                       | {(p, "Labor") for p in LABOR_PARTIES})

    outputs = {
        "pdf_members.csv": (["pdf_path", "member_id", "canonical_full_name", "electorate_or_state", "source"],
                            pdf_rows),
        "member_aliases.csv": (["name_variant", "electorate_or_state", "member_id", "canonical_full_name",
                                "source"], alias_rows),
        "party_terms.csv": (["member_id", "chamber", "parliament", "party", "political_bloc", "source"],
                            party_rows),
        "unknown_party.csv": (["member_id", "chamber", "parliament", "note"], unknown_rows),
        "party_mapping.csv": (["variant", "canonical_party"], mapping_rows),
        "political_blocs.csv": (["party", "bloc"], bloc_rows),
    }
    sort_keys = {
        "pdf_members.csv": lambda r: r[0],
        "member_aliases.csv": lambda r: (r[2], r[0].casefold(), r[0], r[1], r[4]),
        "party_terms.csv": lambda r: (r[0], r[1], int(r[2])),
        "unknown_party.csv": lambda r: (r[0], r[1], int(r[2])),
    }
    for name, key in sort_keys.items():
        header, rows = outputs[name]
        outputs[name] = (header, sorted([list(r) for r in rows] + hand_rows(name), key=key))
    stale = []
    for name, (header, rows) in outputs.items():
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
        path = OUT / name
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != buf.getvalue():
                stale.append(name)
        else:
            OUT.mkdir(parents=True, exist_ok=True)
            path.write_text(buf.getvalue(), encoding="utf-8")
            print(f"wrote {path.relative_to(REPO)} ({len(rows)} rows)")
    if args.check:
        print("overrides up to date" if not stale else f"STALE: {', '.join(stale)}")
        return 1 if stale else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
