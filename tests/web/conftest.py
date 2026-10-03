"""Fixtures for the public-site tests (SPEC plans/2026-10-03-public-site, ADR-W12).

All offline. Tests on the real DB skip when ``site/disclosures_v2.db`` is absent.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from web_support import MINI_DB, MINI_MANIFEST, REAL_DB, REAL_MANIFEST


@pytest.fixture(scope="session")
def mini_site(tmp_path_factory) -> Path:
    """A preview site built from the mini fixture (do not modify; copy it first)."""
    from disclosures.web.build import build

    out = tmp_path_factory.mktemp("mini-site") / "site"
    build(MINI_DB, MINI_MANIFEST, out, mode="preview")
    return out


@pytest.fixture
def site_copy(mini_site, tmp_path) -> Path:
    dst = tmp_path / "site"
    shutil.copytree(mini_site, dst)
    return dst


@pytest.fixture(scope="session")
def real_site(tmp_path_factory) -> Path:
    if not (REAL_DB.exists() and REAL_MANIFEST.exists()):
        pytest.skip("real DB / manifest not present")
    from disclosures.web.build import build

    out = tmp_path_factory.mktemp("real-site") / "site"
    build(REAL_DB, REAL_MANIFEST, out, mode="preview")
    return out
