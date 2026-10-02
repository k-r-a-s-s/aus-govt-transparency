"""Find House statements whose bound-in attachments were not itemised (SPEC-DELTA D1, T1.1).

A file is a candidate when either rule fires:

(a) a v2 item's entity_name/description points at an attachment ("see attached", "Attachment A",
    "annexure", "schedule", "as per list", ...) and that item's section+owner has <= 2 items on
    later pages;
(b) extraction_notes mention an attachment, schedule, broker or portfolio statement, and >= 3
    distinct v1 named entities for the same PDF have no v2 match
    (rapidfuzz partial_ratio < 85 against every v2 entity_name + description).

Writes eval/attachment_gaps.csv with a blank `verdict` column for T1.2 to fill in.
v1's disclosures.db is opened read-only.

    .venv/bin/python scripts/find_attachment_gaps.py [--extractions DIR] [--v1 DB] [--out CSV]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from pathlib import Path

from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from disclosures.normalise import normalise_entity  # noqa: E402

ITEM_RE = re.compile(
    r"\battach(?:ed|ment)?s?\b|\bannex(?:ure)?s?\b|\bschedules?\b|\bas per (?:the )?list\b",
    re.IGNORECASE,
)
NOTES_RE = re.compile(
    r"\battach(?:ed|ment)s?\b|\bschedules?\b|\bbroker\b|\bportfolio statement",
    re.IGNORECASE,
)
MAX_LATER_ITEMS = 2
MIN_V1_UNMATCHED = 3
MATCH_THRESHOLD = 85
SAMPLE_SIZE = 5

FIELDS = [
    "stem", "pdf_path", "reason", "ref_page", "ref_section", "ref_owner",
    "v2_item_count", "v1_unmatched_count", "v1_unmatched_sample", "verdict",
]


def v1_entities(v1_db: Path | None) -> dict[str, list[str]]:
    """pdf filename -> distinct v1 raw entity names (deduped on normalised form)."""
    if v1_db is None or not v1_db.exists():
        return {}
    con = sqlite3.connect(f"file:{v1_db}?mode=ro", uri=True)
    out: dict[str, dict[str, str]] = {}
    for fname, ent in con.execute(
        "select pdf_filename, raw_entity from disclosures where raw_entity is not null"
    ):
        key = normalise_entity(ent)
        if len(key) >= 3:
            out.setdefault(fname, {}).setdefault(key, ent)
    con.close()
    return {f: list(d.values()) for f, d in out.items()}


def attachment_refs(items: list[dict]) -> list[dict]:
    """Rule (a): referencing items whose section+owner has few items on later pages."""
    hits = []
    for it in items:
        text = " ".join(filter(None, [it.get("entity_name"), it.get("description")]))
        if not ITEM_RE.search(text):
            continue
        later = sum(
            1 for o in items
            if o is not it
            and o.get("section") == it.get("section")
            and o.get("owner") == it.get("owner")
            and (o.get("page") or 0) > (it.get("page") or 0)
        )
        if later <= MAX_LATER_ITEMS:
            hits.append(it)
    return hits


def unmatched_v1(items: list[dict], v1_names: list[str]) -> list[str]:
    haystack = [
        normalise_entity(" ".join(filter(None, [it.get("entity_name"), it.get("description")])))
        for it in items
    ]
    out = []
    for name in v1_names:
        n = normalise_entity(name)
        if not any(fuzz.partial_ratio(n, h) >= MATCH_THRESHOLD for h in haystack if h):
            out.append(name)
    return out


def scan(extractions: Path, v1_db: Path | None) -> list[dict]:
    v1 = v1_entities(v1_db)
    rows = []
    for path in sorted(extractions.rglob("*.json")):
        doc = json.loads(path.read_text())
        items = doc.get("items") or []
        stem = path.stem
        notes = doc.get("extraction_notes") or ""
        refs = attachment_refs(items)
        notes_hit = bool(NOTES_RE.search(notes))
        missing = unmatched_v1(items, v1.get(f"{stem}.pdf", [])) if (refs or notes_hit) else []
        rule_b = notes_hit and len(missing) >= MIN_V1_UNMATCHED
        if not refs and not rule_b:
            continue
        reasons = []
        if refs:
            reasons.append("a:item-references-attachment")
        if rule_b:
            reasons.append("b:notes-attachment+v1-unmatched")
        rows.append({
            "stem": stem,
            "pdf_path": doc.get("pdf_path", ""),
            "reason": ";".join(reasons),
            "ref_page": ";".join(str(r.get("page")) for r in refs),
            "ref_section": ";".join(str(r.get("section")) for r in refs),
            "ref_owner": ";".join(str(r.get("owner")) for r in refs),
            "v2_item_count": len(items),
            "v1_unmatched_count": len(missing),
            "v1_unmatched_sample": " | ".join(missing[:SAMPLE_SIZE]),
            "verdict": "",
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--extractions", type=Path, default=ROOT / "extractions/gemini-api/house")
    ap.add_argument("--v1", type=Path, default=ROOT / "disclosures.db")
    ap.add_argument("--out", type=Path, default=ROOT / "eval/attachment_gaps.csv")
    args = ap.parse_args(argv)
    rows = scan(args.extractions, args.v1)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} candidate files -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
