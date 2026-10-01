"""Extractor B, ``gemini-api`` (ADR-5).

    python -m disclosures extract --source gemini [--model ID] [--out-root extractions/gemini-api]
        [--chunk-pages 20] [--max-retries 4] [--force] [--batch] <pdf paths...>

Pipeline per PDF
----------------
1. sha256 + page count (PyMuPDF); chamber/parliament from the path
   (``pdfs/<NN>/x.pdf`` -> house, NN; ``pdfs/senate/<NN>/x.pdf`` -> senate, NN).
2. Split into chunks of <= ``chunk_pages`` pages (in memory, ``insert_pdf``). Each chunk is
   sent as inline PDF bytes plus the shared prompt ``disclosures/prompts/extract.md`` and a
   chunk preamble giving the chunk's absolute page range. Chunks larger than
   ``FILES_API_THRESHOLD_BYTES`` go through the Files API instead and the uploaded file is
   deleted after the call. Output is schema-constrained (``response_json_schema`` =
   :func:`response_schema`), temperature 0.
3. Re-split rule: if a call finishes with ``MAX_TOKENS``, or its text is not a JSON object of
   the expected shape, the chunk is split in half (first half gets the extra page) and each
   half is retried, recursively, down to 1 page. A 1-page chunk that still fails is an error
   for the PDF: no output file is written. Any other non-STOP finish reason (SAFETY,
   RECITATION, ...) is an immediate error for the PDF.
4. Page-offset rule: the preamble asks for absolute source-PDF page numbers. After the call,
   if the chunk starts after page 1 and EVERY returned ``page`` is within ``1..chunk_len``,
   the pages are taken as chunk-relative and ``start - 1`` is added; otherwise they are
   trusted as absolute. This is unambiguous by construction: every chunk that starts after
   page 1 starts after its own length (fixed chunks start at k*chunk_pages+1; halving gives
   the first half the extra page, so a second half [mid+1..end] has length <= mid). Any page
   still outside ``[start, end]`` after that is an error for the PDF (fail loud, no clamping).
5. Merge: items concatenated in page order (stable; model order kept within a page), then
   de-duplicated keeping the first, on :func:`dedup_key`. See that function for why the key
   extends ADR-5's (section, owner, normalised entity/description, page).
   Document fields come from the first chunk with a non-empty value; ``extraction_notes``
   joins the non-empty chunk notes. ``pages_covered`` = 1..page_count (every page was sent).
   ``usage`` sums tokens over every call, including re-split calls (output tokens include
   thinking tokens, which are billed as output).
6. Write ``<out_root>/<chamber>/<parliament>/<stem>.json`` via a temp file, run
   ``validate_file`` on it, and only then move it into place; invalid output is deleted and
   reported. No invalid file is ever left on disk.

Retries: API errors 429 and 5xx are retried with exponential backoff (``sleep`` injectable);
everything else (400, 402 credits depleted, 403, ...) fails the PDF immediately.
``--batch`` (Gemini Batch API) is not implemented; it raises NotImplementedError.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import io
import json
import random
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, get_args

from .gemini_model import resolve_api_key, resolve_gemini_model
from .normalise import normalise_entity
from .schema import SCHEMA_VERSION, ChangeType, Confidence, DatePrecision, Item, Owner
from .validate import sha256_file, validate_file

SOURCE_ID = "gemini-api"
DEFAULT_OUT_ROOT = "extractions/gemini-api"
DEFAULT_CHUNK_PAGES = 20
DEFAULT_MAX_RETRIES = 4  # retries after the first attempt -> at most 5 tries per call
MAX_OUTPUT_TOKENS = 65536
FILES_API_THRESHOLD_BYTES = 15 * 1024 * 1024  # inline request limit is 20 MB
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "extract.md"

# Cost basis (gemini-3.8-flash paid tier, verified 2026-10-01). These prices are valid
# THROUGH 2026-12-31 only; from 2027-01-01 they double ($1.50 / $7.50). Batch API is -50%.
PRICE_USD_PER_MTOK_INPUT_THROUGH_2026_12_31 = 0.75
PRICE_USD_PER_MTOK_OUTPUT_THROUGH_2026_12_31 = 3.75

RETRYABLE_STATUS = {429}  # plus every 5xx
ITEM_FIELDS: Tuple[str, ...] = tuple(Item.model_fields)
DOC_FIELDS = ("member_name_as_printed", "electorate_or_state", "statement_date", "extraction_notes")


# --------------------------------------------------------------------------- schema / prompt

def response_schema() -> dict:
    """JSON Schema for ONE chunk's model output (a Gemini-friendly subset: no $ref/pattern/format).

    Caller-supplied fields (schema_version, source_id, model, pdf_*, page_count,
    pages_covered, chamber, parliament, usage, extracted_at) are set by the extractor.
    """
    nstr = {"type": ["string", "null"]}
    props: Dict[str, Any] = {
        "section": {"type": "integer", "description": "Official section number 1-14."},
        "subsection": dict(nstr, description='e.g. "2(i)", "2(ii)"; null if none.'),
        "owner": {"type": "string", "enum": list(get_args(Owner))},
        "entity_name": dict(nstr, description="Company/bank/organisation/person/trust named, as printed."),
        "description": {"type": "string", "description": "Text of this item only. Never empty."},
        "location": dict(nstr, description="Section 3 only."),
        "purpose": dict(nstr, description="Section 3 only."),
        "is_alteration": {"type": "boolean"},
        "change_type": {"type": "string", "enum": list(get_args(ChangeType))},
        "lodged_date": dict(nstr, description="YYYY-MM-DD or null."),
        "date_precision": {"type": "string", "enum": list(get_args(DatePrecision))},
        "page": {"type": "integer", "description": "1-based page number of the SOURCE PDF."},
        "confidence": {"type": "string", "enum": list(get_args(Confidence))},
    }
    item = {"type": "object", "properties": props, "required": list(props)}
    return {
        "type": "object",
        "properties": {
            "member_name_as_printed": {"type": "string"},
            "electorate_or_state": {"type": "string"},
            "statement_date": dict(nstr, description="YYYY-MM-DD or null."),
            "extraction_notes": {"type": "string"},
            "items": {"type": "array", "items": item},
        },
        "required": list(DOC_FIELDS) + ["items"],
    }


def chunk_preamble(start: int, end: int, page_count: int) -> str:
    n = end - start + 1
    return (
        "## This request\n"
        f"The attached PDF is pages {start}–{end} of a {page_count}-page PDF "
        f"({n} page{'s' if n != 1 else ''}). Attached page 1 is source page {start}.\n"
        f"- `page` on every item MUST be the absolute source-PDF page number, between {start} "
        f"and {end} inclusive.\n"
        "- Only output items that appear on these pages. If the statement's date, the member's "
        'name or electorate are not on these pages, use "" (or null for statement_date).\n'
        "- Output ONE JSON object with exactly these keys: member_name_as_printed, "
        "electorate_or_state, statement_date, extraction_notes, items. Each item has exactly: "
        + ", ".join(ITEM_FIELDS) + ".\n"
        "- The document-level caller fields (schema_version, source_id, model, extracted_at, "
        "pdf_path, pdf_sha256, page_count, pages_covered, chamber, parliament) are added by the "
        "program: do NOT output them.\n"
    )


def load_prompt(path: Path = PROMPT_PATH) -> str:
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- PDF helpers

def infer_chamber_parliament(pdf_rel: str) -> Tuple[str, int]:
    parts = Path(pdf_rel).parts
    if len(parts) >= 3 and parts[0] == "pdfs" and parts[1].isdigit():
        return "house", int(parts[1])
    if len(parts) >= 4 and parts[0] == "pdfs" and parts[1] == "senate" and parts[2].isdigit():
        return "senate", int(parts[2])
    raise ValueError(f"cannot infer chamber/parliament from {pdf_rel!r} "
                     "(expected pdfs/<NN>/x.pdf or pdfs/senate/<NN>/x.pdf)")


def repo_relative(path: str | Path, root: Path) -> str:
    p = Path(path)
    if p.is_absolute():
        try:
            p = p.resolve().relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError(f"{path} is outside the repo root {root}") from exc
    return p.as_posix()


def chunk_ranges(page_count: int, chunk_pages: int) -> List[Tuple[int, int]]:
    return [(s, min(s + chunk_pages - 1, page_count)) for s in range(1, page_count + 1, chunk_pages)]


def pdf_chunk_bytes(src, start: int, end: int) -> bytes:
    """Pages start..end (1-based, inclusive) of an open PyMuPDF document, as PDF bytes."""
    import pymupdf

    out = pymupdf.open()
    try:
        out.insert_pdf(src, from_page=start - 1, to_page=end - 1)
        return out.tobytes(garbage=3, deflate=True)
    finally:
        out.close()


# --------------------------------------------------------------------------- merge

def dedup_key(item: dict) -> tuple:
    """ADR-5's (section, owner, normalised entity-or-description, page), extended with the
    normalised description, subsection, change_type and lodged_date.

    Why extended: chunks are page-disjoint and items outside their chunk's range are
    rejected, so a key containing ``page`` can only ever collide within one chunk. With the
    bare ADR-5 key that would delete genuine distinct items (two Westpac loans on one page,
    self+spouse gifts from one body); on the gold set the bare key collides on 52 of 790
    items, the extended key on 0. The extension still removes exact repeats (a model
    looping over the same rows), which is what de-duplication is for.
    """
    return (
        item.get("section"),
        item.get("owner"),
        normalise_entity(item.get("entity_name") or item.get("description")),
        item.get("page"),
        normalise_entity(item.get("description")),
        item.get("subsection"),
        item.get("change_type"),
        item.get("lodged_date"),
    )


@dataclass
class ChunkResult:
    start: int
    end: int
    data: dict  # model output with absolute pages


def merge_chunks(chunks: Sequence[ChunkResult]) -> dict:
    """Merge chunk outputs into the model-produced part of an extraction document."""
    ordered = sorted(chunks, key=lambda c: c.start)
    items: List[dict] = []
    for c in ordered:
        items.extend(c.data.get("items", []))
    items.sort(key=lambda it: it["page"])  # stable: model order kept within a page
    seen: set = set()
    merged_items = []
    for it in items:
        k = dedup_key(it)
        if k not in seen:
            seen.add(k)
            merged_items.append(it)
    out: Dict[str, Any] = {}
    for f in ("member_name_as_printed", "electorate_or_state", "statement_date"):
        out[f] = next((c.data.get(f) for c in ordered if c.data.get(f)), None)
    out["member_name_as_printed"] = out["member_name_as_printed"] or ""
    out["electorate_or_state"] = out["electorate_or_state"] or ""
    notes = [f"pages {c.start}-{c.end}: {c.data['extraction_notes'].strip()}"
             for c in ordered if (c.data.get("extraction_notes") or "").strip()]
    out["extraction_notes"] = " | ".join(notes)
    out["items"] = merged_items
    return out


def _valid_iso_date(s: Any) -> bool:
    if not isinstance(s, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return False
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        return False
    return True


# --------------------------------------------------------------------------- extractor

class PdfError(Exception):
    """The PDF cannot be extracted; no output file is written."""


class _Resplit(Exception):
    """This chunk's output was truncated or unparseable; split it and retry."""


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def add(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.calls += other.calls

    def cost_usd(self) -> float:
        return estimate_cost_usd(self.input_tokens, self.output_tokens)


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * PRICE_USD_PER_MTOK_INPUT_THROUGH_2026_12_31
            + output_tokens * PRICE_USD_PER_MTOK_OUTPUT_THROUGH_2026_12_31) / 1_000_000


def _reason_name(fr: Any) -> Optional[str]:
    if fr is None:
        return None
    return getattr(fr, "name", None) or str(fr).split(".")[-1]


def _is_retryable(exc: Exception) -> bool:
    from google.genai import errors

    if not isinstance(exc, errors.APIError):
        return False
    code = getattr(exc, "code", None)
    return isinstance(code, int) and (code in RETRYABLE_STATUS or 500 <= code < 600)


@dataclass
class GeminiExtractor:
    """Runs one PDF at a time. ``client`` is anything with ``.models.generate_content``
    (and ``.files.upload/delete`` if a chunk exceeds ``files_threshold``)."""

    client: Any
    model: str
    chunk_pages: int = DEFAULT_CHUNK_PAGES
    max_retries: int = DEFAULT_MAX_RETRIES
    sleep: Callable[[float], None] = time.sleep
    backoff_base: float = 2.0
    files_threshold: int = FILES_API_THRESHOLD_BYTES
    prompt: str = field(default_factory=load_prompt)

    # -- API call -------------------------------------------------------------------------
    def _config(self):
        from google.genai import types

        return types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=response_schema(),
            temperature=0,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )

    def _with_retry(self, fn: Callable[[], Any]) -> Any:
        attempt = 0
        while True:
            try:
                return fn()
            except Exception as exc:
                if attempt >= self.max_retries or not _is_retryable(exc):
                    raise
                delay = self.backoff_base * (2 ** attempt) + random.uniform(0, 1)
                attempt += 1
                self.sleep(delay)

    def _generate(self, chunk: bytes, text: str, label: str):
        from google.genai import types

        uploaded = None
        try:
            if len(chunk) > self.files_threshold:
                uploaded = self._with_retry(lambda: self.client.files.upload(
                    file=io.BytesIO(chunk),
                    config=types.UploadFileConfig(mime_type="application/pdf", display_name=label)))
                part = types.Part.from_uri(file_uri=uploaded.uri, mime_type="application/pdf")
            else:
                part = types.Part.from_bytes(data=chunk, mime_type="application/pdf")
            return self._with_retry(lambda: self.client.models.generate_content(
                model=self.model, contents=[part, text], config=self._config()))
        finally:
            if uploaded is not None:
                try:
                    self.client.files.delete(name=uploaded.name)
                except Exception as exc:  # never mask the real result
                    print(f"warning: could not delete uploaded file {uploaded.name}: {exc}", file=sys.stderr)

    # -- one chunk ------------------------------------------------------------------------
    def _call_chunk(self, src, start: int, end: int, page_count: int, label: str, usage: Usage) -> dict:
        from google.genai import errors

        text = self.prompt.rstrip() + "\n\n" + chunk_preamble(start, end, page_count)
        try:
            resp = self._generate(pdf_chunk_bytes(src, start, end), text, f"{label} p{start}-{end}")
        except errors.APIError as exc:
            raise PdfError(f"pages {start}-{end}: API error {exc.code}: {exc}") from exc
        usage.calls += 1
        um = getattr(resp, "usage_metadata", None)
        if um is not None:
            usage.input_tokens += getattr(um, "prompt_token_count", None) or 0
            usage.output_tokens += ((getattr(um, "candidates_token_count", None) or 0)
                                    + (getattr(um, "thoughts_token_count", None) or 0))
        cands = getattr(resp, "candidates", None) or []
        reason = _reason_name(getattr(cands[0], "finish_reason", None)) if cands else None
        if reason == "MAX_TOKENS":
            raise _Resplit("finish_reason MAX_TOKENS")
        if reason not in (None, "STOP", "FINISH_REASON_UNSPECIFIED"):
            raise PdfError(f"pages {start}-{end}: finish_reason {reason}")
        try:
            data = json.loads(resp.text or "")
        except (ValueError, TypeError) as exc:
            raise _Resplit(f"response is not valid JSON ({exc})") from exc
        if not isinstance(data, dict) or not isinstance(data.get("items"), list) or not all(
                isinstance(it, dict) and all(k in it for k in ITEM_FIELDS) for it in data["items"]):
            raise _Resplit("response JSON does not have the expected shape")
        return data

    def _offset_pages(self, data: dict, start: int, end: int) -> dict:
        items = data["items"]
        pages = [it.get("page") for it in items]
        if not all(isinstance(p, int) and not isinstance(p, bool) for p in pages):
            raise PdfError(f"pages {start}-{end}: non-integer page value in {pages}")
        n = end - start + 1
        if start > 1 and items and all(1 <= p <= n for p in pages):
            for it in items:
                it["page"] += start - 1  # chunk-relative -> absolute (see module docstring)
        bad = sorted({it["page"] for it in items if not start <= it["page"] <= end})
        if bad:
            raise PdfError(f"pages {start}-{end}: model returned item pages outside the chunk: {bad}")
        return data

    def extract_range(self, src, start: int, end: int, page_count: int, label: str,
                      usage: Usage) -> List[ChunkResult]:
        try:
            data = self._call_chunk(src, start, end, page_count, label, usage)
        except _Resplit as why:
            if start == end:
                raise PdfError(f"page {start}: {why} even as a 1-page chunk") from None
            mid = (start + end) // 2
            return (self.extract_range(src, start, mid, page_count, label, usage)
                    + self.extract_range(src, mid + 1, end, page_count, label, usage))
        data["items"] = [{k: it[k] for k in ITEM_FIELDS} for it in data["items"]]  # drop extra keys
        return [ChunkResult(start, end, self._offset_pages(data, start, end))]

    # -- one PDF --------------------------------------------------------------------------
    def extract_pdf(self, pdf_rel: str, root: Path, usage: Usage,
                    now: Optional[Callable[[], str]] = None) -> dict:
        import pymupdf

        chamber, parliament = infer_chamber_parliament(pdf_rel)
        pdf = root / pdf_rel
        sha = sha256_file(pdf)
        chunks: List[ChunkResult] = []
        with pymupdf.open(pdf) as src:
            page_count = src.page_count
            for start, end in chunk_ranges(page_count, self.chunk_pages):
                chunks.extend(self.extract_range(src, start, end, page_count, Path(pdf_rel).stem, usage))
        merged = merge_chunks(chunks)
        notes = merged["extraction_notes"]
        if merged["statement_date"] is not None and not _valid_iso_date(merged["statement_date"]):
            notes = (notes + " | " if notes else "") + f"statement_date {merged['statement_date']!r} unparseable, set null"
            merged["statement_date"] = None
        return {
            "schema_version": SCHEMA_VERSION,
            "source_id": SOURCE_ID,
            "model": self.model,
            "extracted_at": now() if now else utc_now(),
            "pdf_path": pdf_rel,
            "pdf_sha256": sha,
            "page_count": page_count,
            "pages_covered": list(range(1, page_count + 1)),
            "chamber": chamber,
            "parliament": parliament,
            "member_name_as_printed": merged["member_name_as_printed"],
            "electorate_or_state": merged["electorate_or_state"],
            "statement_date": merged["statement_date"],
            "items": merged["items"],
            "extraction_notes": notes,
            "usage": {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
        }


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def output_path(out_root: Path, doc_or_rel: str, chamber: str, parliament: int) -> Path:
    return out_root / chamber / str(parliament) / (Path(doc_or_rel).stem + ".json")


@dataclass
class RunResult:
    ok: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    failed: Dict[str, str] = field(default_factory=dict)
    usage: Usage = field(default_factory=Usage)

    @property
    def exit_code(self) -> int:
        return 1 if self.failed else 0


def extract_pdfs(paths: Sequence[str | Path], *, client: Any, model: str,
                 out_root: str | Path = DEFAULT_OUT_ROOT, chunk_pages: int = DEFAULT_CHUNK_PAGES,
                 max_retries: int = DEFAULT_MAX_RETRIES, force: bool = False, batch: bool = False,
                 sleep: Callable[[float], None] = time.sleep, root: str | Path | None = None,
                 now: Optional[Callable[[], str]] = None, out=None, **extractor_kw) -> RunResult:
    """Extract each PDF; print a status line per PDF and an end summary to ``out``."""
    if batch:
        raise NotImplementedError("--batch (Gemini Batch API) is not implemented yet; "
                                  "run without --batch (synchronous calls, same output).")
    out = out or sys.stdout
    root = Path(root) if root is not None else Path.cwd()
    out_root = Path(out_root)
    if not out_root.is_absolute():
        out_root = root / out_root
    ex = GeminiExtractor(client=client, model=model, chunk_pages=chunk_pages,
                         max_retries=max_retries, sleep=sleep, **extractor_kw)
    res = RunResult()
    for p in paths:
        label = str(p)
        try:
            rel = repo_relative(p, root)
            label = rel
            if not (root / rel).is_file():
                raise PdfError(f"PDF not found: {rel}")
            chamber, parliament = infer_chamber_parliament(rel)
            dest = output_path(out_root, rel, chamber, parliament)
            if dest.exists() and not force and not validate_file(dest, root=root):
                res.skipped.append(rel)
                print(f"skip    {rel}: {dest.relative_to(root) if dest.is_relative_to(root) else dest} "
                      "exists and is valid (use --force)", file=out)
                continue
            usage = Usage()
            try:
                doc = ex.extract_pdf(rel, root, usage, now=now)
            finally:
                res.usage.add(usage)
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".tmp")
            tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            errs = validate_file(tmp, root=root)
            if errs:
                tmp.unlink()
                raise PdfError("output failed validation (not written): " + "; ".join(errs))
            tmp.replace(dest)
            res.ok.append(rel)
            print(f"ok      {rel}: {len(doc['items'])} items, {usage.calls} calls, "
                  f"{usage.input_tokens} in / {usage.output_tokens} out tokens", file=out)
        except Exception as exc:  # one bad PDF (corrupt file, network error) must not stop the run
            res.failed[label] = str(exc) if isinstance(exc, PdfError) else f"{type(exc).__name__}: {exc}"
            print(f"FAILED  {label}: {exc}", file=out)
    u = res.usage
    print(f"{len(res.ok)} ok, {len(res.failed)} failed, {len(res.skipped)} skipped; "
          f"tokens {u.input_tokens} in / {u.output_tokens} out over {u.calls} calls; "
          f"est. cost US${u.cost_usd():.4f} (at ${PRICE_USD_PER_MTOK_INPUT_THROUGH_2026_12_31}/"
          f"${PRICE_USD_PER_MTOK_OUTPUT_THROUGH_2026_12_31} per MTok in/out, prices valid through "
          "2026-12-31)", file=out)
    if res.failed:
        print("Failed PDFs:", file=out)
        for f, why in res.failed.items():
            print(f"  {f}: {why}", file=out)
    return res


# --------------------------------------------------------------------------- CLI

SOURCES = ("gemini",)


def add_arguments(p: argparse.ArgumentParser) -> None:
    p.add_argument("--source", required=True, choices=SOURCES,
                   help="extractor (the workflow-claude arm runs as a Claude Code Workflow, not here)")
    p.add_argument("--model", default=None, help="Gemini model id (default: $GEMINI_MODEL, else built-in)")
    p.add_argument("--out-root", default=DEFAULT_OUT_ROOT)
    p.add_argument("--chunk-pages", type=int, default=DEFAULT_CHUNK_PAGES)
    p.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES,
                   help="retries per API call on 429/5xx (exponential backoff)")
    p.add_argument("--force", action="store_true", help="re-extract even if a valid output exists")
    p.add_argument("--batch", action="store_true", help="use the Gemini Batch API (not implemented)")
    p.add_argument("pdfs", nargs="+", help="PDF paths (repo-relative, e.g. pdfs/45/x.pdf)")


def run(args: argparse.Namespace, client: Any = None, env=None) -> int:
    if args.chunk_pages < 1 or args.max_retries < 0:
        print("extract: --chunk-pages must be >= 1 and --max-retries >= 0", file=sys.stderr)
        return 2
    if args.batch:
        print("extract: --batch (Gemini Batch API) is not implemented yet; run without --batch.",
              file=sys.stderr)
        return 2
    if client is None and env is None:
        from dotenv import load_dotenv

        load_dotenv(".env.local", override=False)
    try:
        model = resolve_gemini_model(args.model, env=env)
    except ValueError as exc:
        print(f"extract: {exc}", file=sys.stderr)
        return 2
    if client is None:
        key = resolve_api_key(env)
        if not key:
            print("extract: no API key: set GOOGLE_API_KEY (or GEMINI_API_KEY) in the environment "
                  "or .env.local", file=sys.stderr)
            return 2
        from google import genai

        client = genai.Client(api_key=key)
    print(f"extract: source=gemini model={model} chunk_pages={args.chunk_pages} pdfs={len(args.pdfs)}")
    res = extract_pdfs(args.pdfs, client=client, model=model, out_root=args.out_root,
                       chunk_pages=args.chunk_pages, max_retries=args.max_retries, force=args.force)
    return res.exit_code
