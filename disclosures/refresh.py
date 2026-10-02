"""Incremental refresh (AC-4.5, D3): ``python -m disclosures refresh``.

    python -m disclosures refresh --dry-run            # list new/changed statements, write nothing
    python -m disclosures refresh                      # scrape, extract (G2), load, entities
    python -m disclosures refresh --source workflow    # scrape, then print the Workflow args

Change detection downloads every House 48th statement and every Senate payload and compares
its sha256 with ``pdfs/manifest.csv`` (``scrape --verify`` semantics: the listing's "Last
updated" date alone could miss a replaced file). A statement with no manifest row is ``new``;
one whose sha256 differs is ``changed``. ``--dry-run`` writes nothing (no PDFs, no manifest).

A real run with ``--source gemini`` saves the new/changed files, extracts only those House PDFs
with the G2 config (``G2_EXTRACT``), runs the Senate adapter on the changed senators, then
``load``s all sources into ``$V2`` and runs ``entities`` (online: uncached long-tail blocks are
paid). With ``--source workflow`` it saves the files, runs the (free) Senate adapter and prints
the exact ``extract-disclosures`` Workflow invocation for the House PDFs plus the load and
entities commands to run after it; nothing is extracted by an LLM here.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from . import manifest, scrape, senate, sources

# The only allowed extraction config (G2; plans/2026-10-02-ralph-phases-3-5/AGENTS.md).
G2_EXTRACT = ["--source", "gemini", "--provider", "openrouter",
              "--model", "google/gemini-3.8-flash", "--provider-order", "google-ai-studio/flex",
              "--fallback-model", "anthropic/claude-sonnet-5.5", "--ignore-providers", "azure",
              "--workers", "8"]
LOAD_SOURCES = ["gemini-api", "senate-json"]
BATCH = 20  # PDFs per extract call (AGENTS.md)


def detect(*, root: Path = Path("."), client=None, dry_run: bool = True, out=sys.stdout,
           now: Callable[[], str] = None, delay: float = 0.3,
           chambers: Tuple[str, ...] = ("house", "senate")) -> List[Tuple[str, str, str]]:
    """Scrape House 48th and Senate 48th, comparing downloaded sha256 to the manifest.
    Returns ``[(chamber, kind, path)]`` for every new/changed statement, in listing order.
    Raises RuntimeError if any statement failed to download (the selection would be partial)."""
    own = client is None
    client = client or sources.http_client()
    found: List[Tuple[str, str, str]] = []
    failed = 0
    try:
        if "house" in chambers:
            ch: list = []
            c = scrape.scrape("house", sources.CURRENT_HOUSE_PARLIAMENT, root=root, client=client,
                              verify=True, delay=delay, out=out, now=now, dry_run=dry_run,
                              changes=ch)
            failed += c["failed"] + c["refused"]
            found += [("house", k, p) for k, p in ch]
        if "senate" in chambers:
            ch = []
            c = senate.scrape(sources.CURRENT_SENATE_PARLIAMENT, root=root, client=client,
                              delay=delay, out=out, now=now, dry_run=dry_run, changes=ch)
            failed += c["failed"]
            found += [("senate", k, p) for k, p in ch]
    finally:
        if own:
            client.close()
    if failed:
        raise RuntimeError(f"refresh: {failed} statement(s) failed to download; re-run")
    return found


def workflow_args(paths: List[str], root: Path = Path("."),
                  extracted_at: Optional[str] = None) -> dict:
    """The ``extract-disclosures`` Workflow args for these House PDFs (with page counts)."""
    pages = {r["pdf_path"]: int(r["page_count"])
             for r in manifest.read_manifest(root / manifest.MANIFEST_PATH)
             if r["pdf_path"] in paths and r.get("page_count")}
    return {"pdfs": list(paths), "page_counts": {p: pages[p] for p in paths if p in pages},
            "extracted_at": extracted_at or dt.datetime.now(dt.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ")}


def _cmd(argv: List[str]) -> str:
    return "python -m disclosures " + " ".join(argv)


def refresh(*, source: str = "gemini", dry_run: bool = False, root: Path = Path("."),
            client=None, out=sys.stdout, main: Callable[[List[str]], int] = None,
            now: Callable[[], str] = None, delay: float = 0.3) -> int:
    """Returns the exit code. ``main`` runs a sub-command (default ``cli.main``; tests stub it)."""
    if main is None:
        from .cli import main
    try:
        found = detect(root=root, client=client, dry_run=dry_run, out=out, now=now, delay=delay)
    except RuntimeError as e:
        print(e, file=out)
        return 1
    house = [p for ch, _, p in found if ch == "house"]
    sen = [p for ch, _, p in found if ch == "senate"]
    print(f"refresh: {len(found)} new/changed ({len(house)} house, {len(sen)} senate)", file=out)
    for ch, kind, p in found:
        print(f"  {kind:7s} {ch:6s} {p}", file=out)
    if dry_run or not found:
        return 0
    if source == "workflow":
        if sen:
            rc = main(["extract", "--source", "senate-json", *sen])
            if rc:
                return rc
        if house:
            args = workflow_args(house, root=root, extracted_at=now() if now else None)
            print("Run in Claude Code (extract-disclosures Workflow, Extractor A):", file=out)
            print(f"  Workflow name=extract-disclosures args={json.dumps(args)}", file=out)
        print("then:", file=out)
        print(f"  {_cmd(['load', '--source', 'workflow-claude', *sum((['--source', s] for s in LOAD_SOURCES), [])])}",
              file=out)
        print(f"  {_cmd(['entities'])}", file=out)
        return 0
    for i in range(0, len(house), BATCH):
        rc = main(["extract", *G2_EXTRACT, *house[i:i + BATCH]])
        if rc:
            print(f"refresh: extract exited {rc}; re-run `refresh` (extract is idempotent)",
                  file=out)
            return rc
    if sen:
        rc = main(["extract", "--source", "senate-json", *sen])
        if rc:
            return rc
    rc = main(["load", *sum((["--source", s] for s in LOAD_SOURCES), [])])
    if rc:
        return rc
    return main(["entities"])


def add_arguments(p) -> None:
    p.add_argument("--dry-run", action="store_true",
                   help="list new/changed House 48th and Senate statements; write nothing")
    p.add_argument("--source", choices=["gemini", "workflow"], default="gemini",
                   help="gemini (default): extract with the G2 config, then load + entities; "
                        "workflow: print the extract-disclosures Workflow args for Kevin")


def run(args) -> int:
    return refresh(source=args.source, dry_run=args.dry_run)
