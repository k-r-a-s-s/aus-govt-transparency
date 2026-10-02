#!/usr/bin/env python3
"""Print the remaining OpenRouter credit, without ever printing the key.

    python3 scripts/ralph/credit.py [--min 3.00]

Stdlib only. The key comes from OPENROUTER_KEY / OPENROUTER_API_KEY in the environment
(cloud sessions) or from those lines in .env.local (local). Output:

    OPENROUTER-CREDIT: remaining=US$18.87 total=US$70.00 used=US$51.13

Exit codes: 0 ok, 4 remaining is below --min, 2 no key found, 1 the request failed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

URL = "https://openrouter.ai/api/v1/credits"
KEY_VARS = ("OPENROUTER_KEY", "OPENROUTER_API_KEY")


def find_key(env=os.environ, dotenv: Path = Path(".env.local")) -> Optional[str]:
    for var in KEY_VARS:
        if env.get(var):
            return env[var].strip()
    if dotenv.is_file():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            name, sep, value = line.strip().partition("=")
            if sep and name.strip().removeprefix("export ").strip() in KEY_VARS and value.strip():
                return value.strip().strip("'\"")
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Remaining OpenRouter credit (never prints the key).")
    ap.add_argument("--min", type=float, default=None, metavar="USD",
                    help="exit 4 if the remaining credit is below this")
    args = ap.parse_args(argv)
    key = find_key()
    if not key:
        print("OPENROUTER-CREDIT: no key (set OPENROUTER_KEY in the environment or .env.local)")
        return 2
    req = urllib.request.Request(URL, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)["data"]
    except (urllib.error.URLError, KeyError, ValueError) as exc:
        print(f"OPENROUTER-CREDIT: request failed: {type(exc).__name__}: {exc}")
        return 1
    total, used = float(data["total_credits"]), float(data["total_usage"])
    remaining = total - used
    print(f"OPENROUTER-CREDIT: remaining=US${remaining:.2f} total=US${total:.2f} used=US${used:.2f}")
    if args.min is not None and remaining < args.min:
        print(f"OPENROUTER-CREDIT: BELOW FLOOR (US${args.min:.2f}). Do not start paid calls; "
              f"block the task as 'blocked (kevin): OpenRouter top-up needed'.")
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
