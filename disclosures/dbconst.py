"""Stdlib-only constants and guards shared by ``load``, ``export`` and ``web``.

Kept apart from ``load`` (which imports pydantic through ``schema``) so that ``export`` and the
web build import nothing heavier than the standard library (public-site SPEC ADR-W2).
``load`` re-exports every name here, so ``from disclosures.load import CATEGORY`` still works.
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DB = "disclosures_v2.db"
V1_DB_NAME = "disclosures.db"

CATEGORY = {
    1: "Shareholding",
    2: "Trust",
    3: "Real estate",
    4: "Directorship",
    5: "Partnership",
    6: "Liability",
    7: "Bond/debenture",
    8: "Account",
    9: "Other asset",
    10: "Income",
    11: "Gift",
    12: "Sponsored travel/hospitality",
    13: "Membership",
    14: "Other interest",
}


def _guard_v1(db_path: Path) -> None:
    """Refuse to overwrite the frozen v1 database, including case variants (macOS APFS is
    case-insensitive, so ``DISCLOSURES.DB`` is the same file) and symlinks to it."""
    v1 = Path.cwd() / V1_DB_NAME
    same = False
    if db_path.name.lower() == V1_DB_NAME.lower():
        same = True
    elif db_path.exists() and v1.exists():
        try:
            same = os.path.samefile(db_path, v1)
        except OSError:
            same = False
    if same or db_path.resolve() == v1.resolve():
        raise ValueError(f"refusing to write {db_path}: that is the frozen v1 database")
