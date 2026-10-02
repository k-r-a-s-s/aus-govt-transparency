"""Top-level CLI: ``python -m disclosures <command>``."""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

# command -> phase in which it lands (stubs until then)
STUBS: dict = {}
ORDER = ["scrape", "extract", "validate", "score", "load", "entities", "export", "refresh"]
HELP = {
    "scrape": "download register PDFs and update the manifest",
    "extract": "run an extractor over PDFs into extractions/",
    "validate": "validate extraction JSON files (contract + completeness)",
    "score": "score predictions (or the v1 DB) against the gold set",
    "load": "load validated extractions into disclosures_v2.db",
    "entities": "run the entity standardisation pipeline",
    "export": "export the published dataset",
    "refresh": "scrape + extract + load new PDFs end to end",
}


def build_parser() -> argparse.ArgumentParser:
    from . import score

    parser = argparse.ArgumentParser(
        prog="python -m disclosures",
        description="Disclosures v2 pipeline.",
    )
    sub = parser.add_subparsers(dest="command", metavar="{" + ",".join(ORDER) + "}")
    for name in ORDER:
        p = sub.add_parser(name, help=HELP[name], description=HELP[name])
        if name == "validate":
            p.add_argument("paths", nargs="+", help="extraction JSON files and/or directories")
        elif name == "score":
            score.add_arguments(p)
        elif name == "extract":
            from . import extract_gemini

            extract_gemini.add_arguments(p)
        elif name == "load":
            from . import load

            load.add_arguments(p)
        elif name == "entities":
            from . import entities

            entities.add_arguments(p)
        elif name == "scrape":
            from . import scrape

            scrape.add_arguments(p)
        elif name == "refresh":
            from . import refresh

            refresh.add_arguments(p)
        elif name == "export":
            from . import export

            export.add_arguments(p)
        else:
            p.add_argument("rest", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    if args.command == "validate":
        from .validate import run

        return run(args.paths)
    if args.command == "score":
        from .score import run

        return run(args)
    if args.command == "extract":
        from .extract_gemini import run

        return run(args)
    if args.command == "load":
        from .load import run

        return run(args)
    if args.command == "entities":
        from .entities import run

        return run(args)
    if args.command == "scrape":
        from .scrape import run

        return run(args)
    if args.command == "refresh":
        from .refresh import run

        return run(args)
    if args.command == "export":
        from .export import run

        return run(args)
    print(f"{args.command}: not implemented yet (Phase {STUBS[args.command]})", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
