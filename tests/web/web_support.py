"""Shared paths and helpers for the public-site tests (imported by tests/web/*)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO / "tests" / "fixtures" / "web"
MINI_DB = FIXTURE_DIR / "mini.db"
MINI_MANIFEST = FIXTURE_DIR / "mini-manifest.csv"
REAL_DB = REPO / "site" / "disclosures_v2.db"
REAL_MANIFEST = REPO / "pdfs" / "manifest.csv"

needs_real = pytest.mark.skipif(not (REAL_DB.exists() and REAL_MANIFEST.exists()),
                                reason="real DB / manifest not present")


def ro(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
