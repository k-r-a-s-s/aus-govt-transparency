"""Gold-set tooling (ADR-3): PDF stats, stratified selection, review sheet.

    python -m disclosures.gold stats [--force]          # (re)build eval/pdf_stats.csv
    python -m disclosures.gold select --seed 20261001 --n 12
    python -m disclosures.gold review-sheet             # eval/gold/*.json -> eval/gold/review.csv
    python -m disclosures.gold apply-review             # mark fully-ticked stems reviewed

Run from the repo root.
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import hashlib
import json
import random
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

PDF_ROOT = Path("pdfs")
STATS_PATH = Path("eval/pdf_stats.csv")
GOLD_DIR = Path("eval/gold")
SELECTION_PATH = GOLD_DIR / "selection.json"
REVIEW_PATH = GOLD_DIR / "review.csv"

NO_TEXT_MIN_CHARS = 20
STATS_FIELDS = [
    "pdf_path",
    "parliament",
    "stem",
    "file_size",
    "page_count",
    "no_text_pages",
    "no_text_fraction",
    "alteration_pages",
    "heuristic_spouse",
    "heuristic_alteration",
    "is_statement",
    "sha256",
]
REVIEW_FIELDS = [
    "stem",
    "page",
    "section",
    "subsection",
    "owner",
    "entity_name",
    "description",
    "change_type",
    "lodged_date",
    "confidence",
    "kevin_ok",
    "kevin_fix",
]

# Heuristics ---------------------------------------------------------------
# Alteration-heavy: many pages, or a text layer that mentions alteration notices often.
ALTERATION_MIN_PAGES = 20
ALTERATION_MIN_TEXT_PAGES = 3
_ALTERATION_RE = re.compile(r"alteration", re.I)
# A Spouse/Partner/Dependent row label followed by something other than a nil marker.
_OWNER_LABEL_RE = re.compile(r"^\s*(spouse|partner|spouse\s*/\s*partner|dependent\s+child(ren)?)\s*:?\s*$", re.I)
_NIL_RE = re.compile(r"^\s*(not\s+applicable|n\s*/\s*a|nil|none|-+)\s*\.?\s*$", re.I)
# Non-statement PDFs (the House resolution text `interestsr_*`, the form's explanatory-notes
# booklet) are excluded from selection. Matched on filename: the statement forms themselves
# quote the resolution and carry "explanatory notes", so text matching over-fires.
_NON_STATEMENT_STEM_RE = re.compile(r"^(interestsr_|explanatory_notes)", re.I)


def _spouse_heuristic(page_texts: Iterable[str]) -> bool:
    for text in page_texts:
        lines = [ln for ln in text.splitlines() if ln.strip()]
        for i, ln in enumerate(lines):
            if _OWNER_LABEL_RE.match(ln):
                nxt = lines[i + 1] if i + 1 < len(lines) else ""
                if nxt and not _NIL_RE.match(nxt) and not _OWNER_LABEL_RE.match(nxt):
                    # skip if the next line is just another row label like "Self"/"Dependent"
                    if not re.match(r"^\s*(self|dependent|children)\b", nxt, re.I):
                        return True
    return False


def pdf_stats(path: Path) -> dict:
    import pymupdf as fitz  # PyMuPDF

    data = path.read_bytes()
    with fitz.open(stream=data, filetype="pdf") as doc:
        texts = [page.get_text() for page in doc]
    no_text = sum(1 for t in texts if len(t.strip()) < NO_TEXT_MIN_CHARS)
    alteration_pages = sum(1 for t in texts if _ALTERATION_RE.search(t))
    n = len(texts)
    is_statement = not _NON_STATEMENT_STEM_RE.match(path.stem)
    return {
        "pdf_path": path.as_posix(),
        "parliament": int(path.parent.name),
        "stem": path.stem,
        "file_size": len(data),
        "page_count": n,
        "no_text_pages": no_text,
        "no_text_fraction": round(no_text / n, 4) if n else 0.0,
        "alteration_pages": alteration_pages,
        "heuristic_spouse": _spouse_heuristic(texts),
        "heuristic_alteration": n >= ALTERATION_MIN_PAGES or alteration_pages >= ALTERATION_MIN_TEXT_PAGES,
        "is_statement": is_statement,
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def build_stats(pdf_root: Path = PDF_ROOT) -> List[dict]:
    files = sorted(pdf_root.glob("[0-9][0-9]/*.pdf"))
    rows = []
    for i, f in enumerate(files, 1):
        rows.append(pdf_stats(f))
        if i % 100 == 0:
            print(f"  stats: {i}/{len(files)}", file=sys.stderr)
    return rows


def write_stats(rows: List[dict], path: Path = STATS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=STATS_FIELDS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({**r, "heuristic_spouse": int(r["heuristic_spouse"]),
                        "heuristic_alteration": int(r["heuristic_alteration"]),
                        "is_statement": int(r["is_statement"])})


def read_stats(path: Path = STATS_PATH) -> List[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "pdf_path": r["pdf_path"],
                "parliament": int(r["parliament"]),
                "stem": r["stem"],
                "file_size": int(r["file_size"]),
                "page_count": int(r["page_count"]),
                "no_text_pages": int(r["no_text_pages"]),
                "no_text_fraction": float(r["no_text_fraction"]),
                "alteration_pages": int(r["alteration_pages"]),
                "heuristic_spouse": r["heuristic_spouse"] == "1",
                "heuristic_alteration": r["heuristic_alteration"] == "1",
                "is_statement": r["is_statement"] == "1",
                "sha256": r["sha256"],
            })
    return rows


def load_or_build_stats(force: bool = False) -> List[dict]:
    if STATS_PATH.exists() and not force:
        return read_stats()
    rows = build_stats()
    write_stats(rows)
    return read_stats()


# Selection ----------------------------------------------------------------

def strata_for(row: dict, max_pages: int) -> List[str]:
    tags = [f"parliament_{row['parliament']}"]
    if row["page_count"] > 30:
        tags.append("gt30pages")
    if row["page_count"] == max_pages:
        tags.append("max_pages")
    if row["no_text_fraction"] > 0.70:
        tags.append("no_text_gt70")
    if row["heuristic_spouse"]:
        tags.append("heuristic_spouse")
    if row["heuristic_alteration"]:
        tags.append("heuristic_alteration")
    return tags


def select(rows: List[dict], seed: int, n: int = 12) -> List[dict]:
    """Greedy stratified selection with a seeded RNG.

    Quotas filled in order (each pick may satisfy several strata):
      1. the single largest PDF (max pages);
      2. >= 3 PDFs with > 30 pages;
      3. >= 3 PDFs with > 70% no-text pages;
      4. >= 2 heuristic-spouse PDFs, >= 2 heuristic-alteration PDFs (best effort);
      5. >= 2 PDFs from every House parliament 43-47;
      6. top up to n at random.
    Within each quota, candidates that also satisfy other unmet strata are preferred.
    """
    if not 12 <= n <= 15:
        raise ValueError("n must be between 12 and 15")
    rng = random.Random(seed)
    pool = [r for r in rows if r["is_statement"]]
    rng.shuffle(pool)
    max_pages = max(r["page_count"] for r in pool)
    chosen: List[dict] = []

    def count(pred) -> int:
        return sum(1 for r in chosen if pred(r))

    def parl_count(p: int) -> int:
        return count(lambda r: r["parliament"] == p)

    preds = {
        "gt30": lambda r: r["page_count"] > 30,
        "notext": lambda r: r["no_text_fraction"] > 0.70,
        "spouse": lambda r: r["heuristic_spouse"],
        "alter": lambda r: r["heuristic_alteration"],
    }
    targets = {"gt30": 3, "notext": 3, "spouse": 2, "alter": 2}

    def bonus(r: dict) -> int:
        b = sum(1 for k, f in preds.items() if f(r) and count(f) < targets[k])
        if parl_count(r["parliament"]) < 2:
            b += 1
        return b

    def pick(pred, need: int) -> None:
        while count(pred) < need and len(chosen) < n:
            cands = [r for r in pool if pred(r) and r not in chosen]
            if not cands:
                return
            best = max(bonus(r) for r in cands)
            chosen.append(next(r for r in cands if bonus(r) == best))  # pool order is seeded

    pick(lambda r: r["page_count"] == max_pages, 1)
    for key in ("gt30", "notext", "spouse", "alter"):
        pick(preds[key], targets[key])
    for p in (43, 44, 45, 46, 47):
        pick(lambda r, p=p: r["parliament"] == p, 2)
    pick(lambda r: True, n)

    chosen.sort(key=lambda r: (r["parliament"], r["stem"]))
    return [
        {
            "pdf_path": r["pdf_path"],
            "parliament": r["parliament"],
            "page_count": r["page_count"],
            "no_text_fraction": r["no_text_fraction"],
            "strata": strata_for(r, max_pages),
            "heuristic_spouse": r["heuristic_spouse"],
            "heuristic_alteration": r["heuristic_alteration"],
        }
        for r in chosen
    ]


def write_selection(pdfs: List[dict], seed: int) -> dict:
    doc = {
        "seed": seed,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat(),
        "method": (
            "Greedy stratified selection over eval/pdf_stats.csv (House statements only; the "
            "resolution-text and explanatory-notes PDFs are excluded), seeded shuffle for tie-breaks. Quotas: the "
            "largest PDF; >=3 with >30 pages; >=3 with >70% no-text-layer pages (<20 chars); "
            ">=2 heuristic spouse/dependent (text-layer row label followed by non-nil text); "
            ">=2 heuristic alteration-heavy (>=20 pages or >=3 text pages mentioning "
            "'alteration'); >=2 per parliament 43-47; topped up at random. Regenerate with "
            "`python -m disclosures.gold select --seed <seed> --n <n>`."
        ),
        "n": len(pdfs),
        "pdfs": pdfs,
    }
    SELECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    SELECTION_PATH.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


# Review sheet --------------------------------------------------------------

def gold_files(gold_dir: Path = GOLD_DIR) -> List[Path]:
    out = []
    for f in sorted(gold_dir.glob("*.json")):
        if f.name == SELECTION_PATH.name:
            continue
        out.append(f)
    return out


def _cell(v) -> str:
    if v is None:
        return ""
    return str(v)


def write_review_sheet(gold_dir: Path = GOLD_DIR, out: Optional[Path] = None) -> int:
    out = out or gold_dir / REVIEW_PATH.name
    rows = []
    for f in gold_files(gold_dir):
        doc = json.loads(f.read_text(encoding="utf-8"))
        for it in doc.get("items", []):
            rows.append({
                "stem": f.stem,
                "page": it.get("page"),
                "section": it.get("section"),
                "subsection": it.get("subsection"),
                "owner": it.get("owner"),
                "entity_name": it.get("entity_name"),
                "description": it.get("description"),
                "change_type": it.get("change_type"),
                "lodged_date": it.get("lodged_date"),
                "confidence": it.get("confidence"),
                "kevin_ok": "",
                "kevin_fix": "",
            })
    rows.sort(key=lambda r: (r["stem"], r["page"] or 0, r["section"] or 0))
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=REVIEW_FIELDS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: _cell(v) for k, v in r.items()})
    return len(rows)


def apply_review(gold_dir: Path = GOLD_DIR, review: Optional[Path] = None,
                 today: Optional[str] = None) -> Dict[str, List[str]]:
    """Mark gold files reviewed when every review row for their stem has kevin_ok set.

    Returns {"reviewed": [...stems], "unreviewed": [...stems]}. Gold files with no rows in the
    sheet (e.g. zero items, or sheet out of date) are reported as unreviewed.
    """
    review = review or gold_dir / REVIEW_PATH.name
    today = today or _dt.date.today().isoformat()
    ok: Dict[str, bool] = {}
    if review.exists():
        with open(review, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                stem = r["stem"]
                ok[stem] = ok.get(stem, True) and bool((r.get("kevin_ok") or "").strip())
    result = {"reviewed": [], "unreviewed": []}
    for f in gold_files(gold_dir):
        doc = json.loads(f.read_text(encoding="utf-8"))
        n_items = len(doc.get("items", []))
        stem_ok = ok.get(f.stem, False) if n_items else False
        if stem_ok:
            doc["reviewed_by"] = "kevin"
            doc["reviewed_at"] = today
            f.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            result["reviewed"].append(f.stem)
        else:
            result["unreviewed"].append(f.stem)
    return result


# CLI ----------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m disclosures.gold")
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stats", help="(re)build eval/pdf_stats.csv")
    s.add_argument("--force", action="store_true")
    s = sub.add_parser("select", help="write eval/gold/selection.json")
    s.add_argument("--seed", type=int, required=True)
    s.add_argument("--n", type=int, default=12)
    s.add_argument("--rebuild-stats", action="store_true")
    sub.add_parser("review-sheet", help="write eval/gold/review.csv from eval/gold/*.json")
    sub.add_parser("apply-review", help="set reviewed_by/at on fully-ticked gold files")
    args = parser.parse_args(argv)

    if args.cmd == "stats":
        rows = load_or_build_stats(force=args.force)
        print(f"{len(rows)} PDFs in {STATS_PATH}")
    elif args.cmd == "select":
        rows = load_or_build_stats(force=args.rebuild_stats)
        doc = write_selection(select(rows, args.seed, args.n), args.seed)
        for p in doc["pdfs"]:
            print(f"{p['pdf_path']:<40} {p['page_count']:>3}p notext={p['no_text_fraction']:.2f} {','.join(p['strata'])}")
        print(f"wrote {SELECTION_PATH} ({doc['n']} PDFs, seed {args.seed})")
    elif args.cmd == "review-sheet":
        n = write_review_sheet()
        print(f"wrote {REVIEW_PATH} ({n} item rows)")
    elif args.cmd == "apply-review":
        res = apply_review()
        print(f"reviewed: {len(res['reviewed'])} {' '.join(res['reviewed'])}")
        print(f"still unreviewed: {len(res['unreviewed'])} {' '.join(res['unreviewed'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
