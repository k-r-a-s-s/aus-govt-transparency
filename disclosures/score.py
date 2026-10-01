"""Scoring harness (ADR-4).

    python -m disclosures score --pred <dir> --gold eval/gold [--json out.json]
    python -m disclosures score --v1 disclosures.db --gold eval/gold [--json out.json]

Per PDF, predicted items are matched to gold items by maximum-weight bipartite
matching (scipy linear_sum_assignment). A pair is eligible only if the sections
are equal (section-strict mode) and rapidfuzz token_set_ratio of the normalised
keys is >= 85. Key = normalise_entity(entity_name) when BOTH sides have an
entity_name, else normalise_entity(description) on both sides.

The pair weight is the ratio plus a tie-break bonus < 0.01 that prefers pairs
agreeing on page/owner/change_type/lodged_date. The bonus only decides between
candidates whose ratios are (near-)equal, e.g. the same company disclosed on
several pages; it never makes an ineligible pair eligible.

Undefined metrics (zero denominator) are reported as null.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from rapidfuzz import fuzz
from scipy.optimize import linear_sum_assignment

from .normalise import normalise_entity

THRESHOLD = 85.0
FIELDS = ("owner", "change_type", "is_alteration", "page", "lodged_date")
N_WORST = 10


# --------------------------------------------------------------------------- loading

def _is_extraction(obj: Any) -> bool:
    return isinstance(obj, dict) and isinstance(obj.get("items"), list) and "pdf_path" in obj


def load_gold(gold_dir: str | Path) -> List[dict]:
    """Flat *.json in gold_dir that look like extraction files (skips selection.json etc.)."""
    docs = []
    for f in sorted(Path(gold_dir).glob("*.json")):
        obj = json.loads(f.read_text(encoding="utf-8"))
        if _is_extraction(obj):
            obj["_file"] = str(f)
            docs.append(obj)
    return docs


def load_pred(pred_dir: str | Path) -> List[dict]:
    """Recursive *.json under pred_dir that look like extraction files."""
    docs = []
    for f in sorted(Path(pred_dir).rglob("*.json")):
        try:
            obj = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if _is_extraction(obj):
            obj["_file"] = str(f)
            docs.append(obj)
    return docs


def doc_stem(doc: dict) -> str:
    if doc.get("pdf_path"):
        return Path(doc["pdf_path"]).stem
    return Path(doc.get("_file", "")).stem


def pair_docs(preds: Sequence[dict], golds: Sequence[dict]) -> List[Tuple[dict, Optional[dict]]]:
    """Pair each gold doc with a pred doc by pdf_sha256, falling back to stem."""
    by_sha: Dict[str, dict] = {}
    by_stem: Dict[str, dict] = {}
    for p in preds:
        if p.get("pdf_sha256"):
            by_sha.setdefault(p["pdf_sha256"], p)
        by_stem.setdefault(doc_stem(p), p)
        by_stem.setdefault(Path(p.get("_file", "")).stem, p)
    out = []
    for g in golds:
        p = by_sha.get(g.get("pdf_sha256") or "")
        if p is None:
            p = by_stem.get(doc_stem(g))
        out.append((g, p))
    return out


# --------------------------------------------------------------------------- matching

def item_keys(a: dict, b: dict) -> Tuple[str, str]:
    if a.get("entity_name") and b.get("entity_name"):
        return normalise_entity(a["entity_name"]), normalise_entity(b["entity_name"])
    return normalise_entity(a.get("description") or ""), normalise_entity(b.get("description") or "")


def pair_ratio(pred: dict, gold: dict) -> float:
    kp, kg = item_keys(pred, gold)
    return float(fuzz.token_set_ratio(kp, kg))


def _tiebreak(pred: dict, gold: dict) -> float:
    agree = (
        4 * (pred.get("page") == gold.get("page"))
        + 2 * (pred.get("owner") == gold.get("owner"))
        + (pred.get("change_type") == gold.get("change_type"))
        + (pred.get("lodged_date") == gold.get("lodged_date"))
    )
    return 0.001 * agree  # max 0.008 < 0.01


def match_items(
    pred_items: Sequence[dict], gold_items: Sequence[dict], section_strict: bool = True
) -> List[Tuple[int, int, float]]:
    """Return matched (pred_idx, gold_idx, ratio) triples."""
    if not pred_items or not gold_items:
        return []
    w = np.zeros((len(pred_items), len(gold_items)))
    ratios = np.zeros_like(w)
    for i, p in enumerate(pred_items):
        for j, g in enumerate(gold_items):
            if section_strict and p.get("section") != g.get("section"):
                continue
            r = pair_ratio(p, g)
            if r >= THRESHOLD:
                ratios[i, j] = r
                w[i, j] = r + _tiebreak(p, g)
    rows, cols = linear_sum_assignment(w, maximize=True)
    return [(int(i), int(j), float(ratios[i, j])) for i, j in zip(rows, cols) if w[i, j] > 0]


def best_ratio(gold: dict, pred_items: Sequence[dict]) -> float:
    return max((pair_ratio(p, gold) for p in pred_items), default=0.0)


# --------------------------------------------------------------------------- metrics

def _div(a: float, b: float) -> Optional[float]:
    return float(a) / float(b) if b else None


def _f1(p: Optional[float], r: Optional[float]) -> Optional[float]:
    if p is None or r is None:
        return None
    return 2 * p * r / (p + r) if (p + r) else 0.0


def _prf(tp: int, n_pred: int, n_gold: int) -> Dict[str, Optional[float]]:
    p, r = _div(tp, n_pred), _div(tp, n_gold)
    return {"precision": p, "recall": r, "f1": _f1(p, r)}


@dataclass
class _Acc:
    correct: Dict[str, int] = field(default_factory=lambda: {f: 0 for f in FIELDS})
    total: Dict[str, int] = field(default_factory=lambda: {f: 0 for f in FIELDS})

    def add(self, pred: dict, gold: dict) -> None:
        for f in FIELDS:
            if f == "lodged_date" and gold.get("lodged_date") is None:
                continue
            self.total[f] += 1
            self.correct[f] += int(pred.get(f) == gold.get(f))


def _miss_record(stem: str, gold: dict, pred_items: Sequence[dict], hit_ignoring_section: bool) -> dict:
    return {
        "stem": stem,
        "page": gold.get("page"),
        "section": gold.get("section"),
        "owner": gold.get("owner"),
        "entity_name": gold.get("entity_name"),
        "description": gold.get("description"),
        "best_ratio": best_ratio(gold, pred_items),
        "matched_if_section_ignored": hit_ignoring_section,
    }


def score_pairs(pairs: Sequence[Tuple[dict, Optional[dict]]], v1_mode: bool = False) -> dict:
    """Score paired (gold_doc, pred_doc_or_None). In v1_mode only section-ignored metrics."""
    tot = {"n_gold": 0, "n_pred": 0, "tp": 0, "tp_section_ignored": 0}
    acc = _Acc()
    per_pdf = []
    misses = []
    for gold_doc, pred_doc in pairs:
        stem = doc_stem(gold_doc)
        g_items = gold_doc.get("items", [])
        p_items = pred_doc.get("items", []) if pred_doc else []
        loose = match_items(p_items, g_items, section_strict=False)
        loose_gold = {j for _, j, _ in loose}
        if v1_mode:
            strict, strict_gold = [], set()
        else:
            strict = match_items(p_items, g_items, section_strict=True)
            strict_gold = {j for _, j, _ in strict}
            for i, j, _ in strict:
                acc.add(p_items[i], g_items[j])
        tot["n_gold"] += len(g_items)
        tot["n_pred"] += len(p_items)
        tot["tp"] += len(strict)
        tot["tp_section_ignored"] += len(loose)
        per_pdf.append(
            {
                "stem": stem,
                "pdf_path": gold_doc.get("pdf_path"),
                "has_pred": pred_doc is not None,
                "n_gold": len(g_items),
                "n_pred": len(p_items),
                "matched": None if v1_mode else len(strict),
                "matched_section_ignored": len(loose),
                "recall": None if v1_mode else _div(len(strict), len(g_items)),
                "recall_section_ignored": _div(len(loose), len(g_items)),
            }
        )
        missed_set = loose_gold if v1_mode else strict_gold
        for j, g in enumerate(g_items):
            if j not in missed_set:
                misses.append(_miss_record(stem, g, p_items, j in loose_gold))

    misses.sort(key=lambda m: (m["matched_if_section_ignored"], m["best_ratio"], m["stem"], m["page"] or 0))
    strict_prf = _prf(tot["tp"], tot["n_pred"], tot["n_gold"])
    loose_prf = _prf(tot["tp_section_ignored"], tot["n_pred"], tot["n_gold"])
    if v1_mode:
        strict_prf = {k: None for k in strict_prf}
        accuracies = {f: None for f in FIELDS}
        acc_counts = {f: None for f in FIELDS}
    else:
        accuracies = {f: _div(acc.correct[f], acc.total[f]) for f in FIELDS}
        acc_counts = {f: {"correct": acc.correct[f], "total": acc.total[f]} for f in FIELDS}
    return {
        "mode": "v1" if v1_mode else "pred",
        "threshold": THRESHOLD,
        "n_pdfs": len(pairs),
        "n_pdfs_without_pred": sum(1 for _, p in pairs if p is None),
        "counts": {
            "n_gold": tot["n_gold"],
            "n_pred": tot["n_pred"],
            "matched": None if v1_mode else tot["tp"],
            "matched_section_ignored": tot["tp_section_ignored"],
        },
        "precision": strict_prf["precision"],
        "recall": strict_prf["recall"],
        "f1": strict_prf["f1"],
        "section_ignored": loose_prf,
        "accuracy": accuracies,
        "accuracy_counts": acc_counts,
        "per_pdf": per_pdf,
        "worst_misses": misses[:N_WORST],
    }


def score_dirs(pred_dir: str | Path, gold_dir: str | Path) -> dict:
    golds = load_gold(gold_dir)
    report = score_pairs(pair_docs(load_pred(pred_dir), golds))
    report["pred"], report["gold"] = str(pred_dir), str(gold_dir)
    return report


# --------------------------------------------------------------------------- v1 baseline

def v1_items_for(conn: sqlite3.Connection, pdf_basename: str) -> List[dict]:
    rows = conn.execute(
        "SELECT raw_entity, raw_description FROM disclosures WHERE pdf_filename = ?",
        (pdf_basename,),
    ).fetchall()
    return [
        {"section": None, "entity_name": (ent or None), "description": desc or ""}
        for ent, desc in rows
    ]


def score_v1(db_path: str | Path, gold_dir: str | Path) -> dict:
    golds = load_gold(gold_dir)
    uri = f"file:{Path(db_path).resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)  # read-only: v1 DB must not change
    try:
        pairs = []
        for g in golds:
            items = v1_items_for(conn, Path(g["pdf_path"]).name)
            pairs.append((g, {"pdf_path": g["pdf_path"], "items": items, "_file": "v1"}))
    finally:
        conn.close()
    report = score_pairs(pairs, v1_mode=True)
    report["v1_db"], report["gold"] = str(db_path), str(gold_dir)
    return report


# --------------------------------------------------------------------------- report

def _fmt(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def format_report(r: dict) -> str:
    c = r["counts"]
    lines = [
        f"Scoring mode: {r['mode']}  (threshold token_set_ratio >= {r['threshold']:.0f})",
        f"PDFs: {r['n_pdfs']}  (without pred: {r['n_pdfs_without_pred']})",
        f"Items: gold={c['n_gold']} pred={c['n_pred']} matched={c['matched']} "
        f"matched_section_ignored={c['matched_section_ignored']}",
        "",
        f"precision={_fmt(r['precision'])} recall={_fmt(r['recall'])} f1={_fmt(r['f1'])}",
        "section-ignored: "
        f"precision={_fmt(r['section_ignored']['precision'])} "
        f"recall={_fmt(r['section_ignored']['recall'])} f1={_fmt(r['section_ignored']['f1'])}",
        "field accuracy (matched pairs): "
        + " ".join(f"{f}={_fmt(v)}" for f, v in r["accuracy"].items()),
        "",
        "Per-PDF recall:",
        f"  {'stem':<28} {'gold':>5} {'pred':>5} {'recall':>7} {'rec_noSec':>9}",
    ]
    for p in r["per_pdf"]:
        lines.append(
            f"  {p['stem']:<28} {p['n_gold']:>5} {p['n_pred']:>5} {_fmt(p['recall']):>7} "
            f"{_fmt(p['recall_section_ignored']):>9}" + ("" if p["has_pred"] else "  (no pred)")
        )
    lines.append("")
    lines.append(f"Worst misses (up to {N_WORST}):")
    if not r["worst_misses"]:
        lines.append("  (none)")
    for m in r["worst_misses"]:
        what = m["entity_name"] or m["description"] or ""
        tag = " [mis-sectioned]" if m["matched_if_section_ignored"] else ""
        lines.append(
            f"  {m['stem']} p{m['page']} s{m['section']} {m['owner']}: {what[:70]!r} "
            f"(best ratio {m['best_ratio']:.0f}){tag}"
        )
    return "\n".join(lines)


def run(args) -> int:
    if not Path(args.gold).is_dir():
        print(f"score: gold dir not found: {args.gold}", file=sys.stderr)
        return 2
    if args.v1:
        if not Path(args.v1).is_file():
            print(f"score: v1 db not found: {args.v1}", file=sys.stderr)
            return 2
        report = score_v1(args.v1, args.gold)
    else:
        if not Path(args.pred).is_dir():
            print(f"score: pred dir not found: {args.pred}", file=sys.stderr)
            return 2
        report = score_dirs(args.pred, args.gold)
    print(format_report(report))
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {out}")
    return 0


def add_arguments(p) -> None:
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--pred", help="directory of predicted extraction JSON (recursive)")
    src.add_argument("--v1", help="path to v1 disclosures.db (section-ignored baseline)")
    p.add_argument("--gold", default="eval/gold", help="gold directory (flat *.json)")
    p.add_argument("--json", help="write the full report as JSON to this path")
