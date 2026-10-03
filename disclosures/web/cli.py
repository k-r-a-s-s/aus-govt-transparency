"""``python -m disclosures web <subcommand>``.

Exit codes: 0 ok, 1 check failed, 2 bad input or clobber guard.
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from ..dbconst import DEFAULT_DB

DEFAULT_MANIFEST = "pdfs/manifest.csv"
SUBCOMMANDS = ("build", "check", "publish-data", "make-fixture", "probe-links")
HELP = {
    "build": "build the static site (data bundle, static API, headers, manifest) into --out",
    "check": "check a built site against the deploy rules (exit 1 naming each failed rule)",
    "publish-data": "write the R2 data files and print the upload commands (phase D)",
    "make-fixture": "write the small test DB and manifest (tests/fixtures/web)",
    "probe-links": "GET a sample of source links and report how many serve a PDF (network)",
}


def add_arguments(p: argparse.ArgumentParser) -> None:
    from .build import DEFAULT_DATA_BASE, MODES

    sub = p.add_subparsers(dest="web_command", metavar="{" + ",".join(SUBCOMMANDS) + "}")
    for name in SUBCOMMANDS:
        s = sub.add_parser(name, help=HELP[name], description=HELP[name])
        if name == "build":
            s.add_argument("--db", default=DEFAULT_DB, help="v2 database (default: %(default)s)")
            s.add_argument("--manifest", default=DEFAULT_MANIFEST,
                           help="source URLs by sha256 (default: %(default)s)")
            s.add_argument("--out", required=True,
                           help="output directory; must not exist or be empty")
            s.add_argument("--mode", choices=MODES, default="preview",
                           help="preview (noindex) or production (default: %(default)s)")
            s.add_argument("--data-base", default=DEFAULT_DATA_BASE,
                           help="base URL of the R2 data files (default: %(default)s)")
        elif name == "check":
            s.add_argument("site", help="built site directory")
            s.add_argument("--db", default=None,
                           help="DB to check member coverage against (optional)")
        elif name == "make-fixture":
            s.add_argument("--db", default=DEFAULT_DB, help="source DB (default: %(default)s)")
            s.add_argument("--manifest", default=DEFAULT_MANIFEST,
                           help="source manifest (default: %(default)s)")
            s.add_argument("--out", required=True,
                           help="directory for mini.db and mini-manifest.csv")
            s.add_argument("--members", type=int, default=6,
                           help="members to include, at least 6 (default: %(default)s)")
            s.add_argument("--seed", type=int, default=1, help="selection seed (default: 1)")
        elif name == "publish-data":
            s.add_argument("--db", default=DEFAULT_DB, help="v2 database (default: %(default)s)")
            s.add_argument("--version", default="auto", help="dataset version (default: auto)")
            s.add_argument("--out", default=None, help="staging directory")
            s.add_argument("--dry-run", action="store_true", help="upload nothing")
        elif name == "probe-links":
            s.add_argument("--site", required=True, help="built site directory")
            s.add_argument("--sample", type=int, default=30, help="links to probe (default: 30)")


def run(args) -> int:
    cmd = getattr(args, "web_command", None)
    if cmd is None:
        print("web: choose a subcommand: " + ", ".join(SUBCOMMANDS), file=sys.stderr)
        return 2
    if cmd == "build":
        from .build import BuildError, build
        from .dataset import DatasetError

        try:
            s = build(args.db, args.manifest, args.out, args.mode, args.data_base)
        except (BuildError, DatasetError) as e:
            print(f"web build: {e}", file=sys.stderr)
            return 2
        print(f"web build: {s['items']:,} items, {s['members']:,} members, "
              f"{s['entities_listed']:,} entities listed ({s['entity_files']:,} with items.json), "
              f"{s['documents']:,} statements; data/items.json {s['items_json_bytes']:,} bytes; "
              f"{s['files']:,} files, {s['bytes']:,} bytes -> {s['out']} ({args.mode})")
        return 0
    if cmd == "check":
        from .check import run_check

        return run_check(args.site, args.db)
    if cmd == "make-fixture":
        from .dataset import DatasetError
        from .fixture import make_fixture

        try:
            s = make_fixture(args.db, args.manifest, args.out, args.members, args.seed)
        except DatasetError as e:
            print(f"web make-fixture: {e}", file=sys.stderr)
            return 2
        for mid, why in s["members"]:
            print(f"  {mid}: {why}")
        counts = ", ".join(f"{k} {v:,}" for k, v in s["counts"].items())
        print(f"web make-fixture: {s['db']} ({s['bytes']:,} bytes; {counts}) and {s['manifest']}")
        return 0
    print(f"web {cmd}: not implemented in phase A", file=sys.stderr)
    return 2


def main(argv: Optional[List[str]] = None) -> int:
    """Entry for ``python -m disclosures web ...`` without building the full pipeline parser
    (which imports numpy, scipy and pydantic): the web build needs only the stdlib + Jinja2."""
    p = argparse.ArgumentParser(prog="python -m disclosures web",
                                description="build, check and publish the public site")
    add_arguments(p)
    return run(p.parse_args(argv))
