"""Validate extraction files against the ADR-2 contract plus completeness checks.

    python -m disclosures validate <path-or-dir> [...]

Paths inside files (`pdf_path`) are resolved relative to the current working
directory, which must be the repo root.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Iterable, List

from pydantic import ValidationError

from .schema import Extraction

# Files that live alongside extraction JSON but are not extractions.
NON_EXTRACTION_NAMES = {"selection.json"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pdf_page_count(path: Path) -> int:
    import pymupdf as fitz  # PyMuPDF

    with fitz.open(path) as doc:
        return doc.page_count


def iter_json_files(paths: Iterable[str | Path]) -> List[Path]:
    """Expand files and directories (recursive *.json), sorted, de-duplicated."""
    out: list[Path] = []
    seen: set[Path] = set()
    for p in paths:
        p = Path(p)
        found = sorted(p.rglob("*.json")) if p.is_dir() else [p]
        for f in found:
            if p.is_dir() and f.name in NON_EXTRACTION_NAMES:
                continue
            key = f.resolve()
            if key not in seen:
                seen.add(key)
                out.append(f)
    return out


def _format_pydantic_error(exc: ValidationError) -> List[str]:
    msgs = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", ())) or "<root>"
        msgs.append(f"schema: {loc}: {err.get('msg')}")
    return msgs


def _pdf_path_error(pdf_path: str, root: Path) -> str | None:
    """pdf_path must be repo-relative, contain no `..` segments and stay inside root."""
    rel = Path(pdf_path)
    if rel.is_absolute() or pdf_path.startswith(("/", "\\")):
        return f"pdf_path must be repo-relative, got {pdf_path!r}"
    if ".." in pdf_path.replace("\\", "/").split("/"):
        return f"pdf_path must not contain '..' segments, got {pdf_path!r}"
    root_resolved = root.resolve()
    try:
        (root_resolved / rel).resolve().relative_to(root_resolved)
    except ValueError:
        return f"pdf_path resolves outside the repo root, got {pdf_path!r}"
    return None


def validate_file(path: str | Path, root: str | Path | None = None) -> List[str]:
    """Return a list of error strings for one extraction file (empty = valid)."""
    path = Path(path)
    root = Path(root) if root is not None else Path.cwd()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ["file not found"]
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [f"not valid JSON: {exc}"]
    try:
        doc = Extraction.model_validate(raw)
    except ValidationError as exc:
        return _format_pydantic_error(exc)

    errors: list[str] = []
    expected = list(range(1, doc.page_count + 1))
    if doc.pages_covered != expected:
        covered = set(doc.pages_covered)
        missing = [p for p in expected if p not in covered]
        extra = sorted(p for p in covered if p > doc.page_count)
        dupes = sorted({p for p in doc.pages_covered if doc.pages_covered.count(p) > 1})
        detail = []
        if missing:
            detail.append(f"missing pages {missing}")
        if extra:
            detail.append(f"pages beyond page_count {extra}")
        if dupes:
            detail.append(f"duplicate pages {dupes}")
        if not detail:
            detail.append("not sorted")
        errors.append(f"pages_covered != [1..{doc.page_count}]: " + "; ".join(detail))

    for i, item in enumerate(doc.items):
        if item.page > doc.page_count:
            errors.append(f"items[{i}].page {item.page} > page_count {doc.page_count}")
        # lodged_date is null <=> date_precision == "unknown" (both directions).
        if item.lodged_date is None and item.date_precision != "unknown":
            errors.append(f"items[{i}]: lodged_date null but date_precision {item.date_precision!r}")
        elif item.lodged_date is not None and item.date_precision == "unknown":
            errors.append(f"items[{i}]: lodged_date {item.lodged_date} but date_precision 'unknown'")

    pdf = root / doc.pdf_path
    path_error = _pdf_path_error(doc.pdf_path, root)
    if path_error:
        errors.append(path_error)
    elif not pdf.is_file():
        errors.append(f"pdf_path not found: {doc.pdf_path}")
    else:
        actual_sha = sha256_file(pdf)
        if actual_sha != doc.pdf_sha256:
            errors.append(f"pdf_sha256 mismatch: file has {actual_sha}, json says {doc.pdf_sha256}")
        try:
            actual_pages = pdf_page_count(pdf)
        except Exception as exc:  # corrupt PDF
            errors.append(f"cannot open PDF {doc.pdf_path}: {exc}")
        else:
            if actual_pages != doc.page_count:
                errors.append(f"page_count {doc.page_count} != actual PDF page count {actual_pages}")
    return errors


def validate_paths(paths: Iterable[str | Path], root: str | Path | None = None) -> dict:
    """Validate many files. Returns {"valid": [paths], "invalid": {path: [errors]}}."""
    valid: list[str] = []
    invalid: dict[str, list[str]] = {}
    for f in iter_json_files(paths):
        errs = validate_file(f, root=root)
        if errs:
            invalid[str(f)] = errs
        else:
            valid.append(str(f))
    return {"valid": valid, "invalid": invalid}


def run(paths: List[str]) -> int:
    for p in paths:
        if not Path(p).exists():
            print(f"INVALID {p}: path does not exist")
            return 1
    result = validate_paths(paths)
    for f, errs in result["invalid"].items():
        for e in errs:
            print(f"INVALID {f}: {e}")
    n_valid, n_invalid = len(result["valid"]), len(result["invalid"])
    print(f"{n_valid} valid, {n_invalid} invalid")
    return 1 if n_invalid else 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
