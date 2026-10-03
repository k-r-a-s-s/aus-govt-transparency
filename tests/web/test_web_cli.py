"""AC-A1 (help listing), phase A stubs, and ADR-W2 (the web build stays light)."""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap

from web_support import MINI_DB, MINI_MANIFEST, REPO

SUBS = ["build", "check", "publish-data", "make-fixture", "probe-links"]
HEAVY = ["pymupdf", "fitz", "google", "google.genai", "pydantic", "pydantic_core", "numpy",
         "scipy", "rapidfuzz", "httpx"]


def _py(*args, code=None):
    cmd = [sys.executable, *(["-c", code] if code else ["-m", "disclosures", *args])]
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                          env={**os.environ, "PYTHONPATH": str(REPO)})


def test_top_level_help_lists_web():
    r = _py("--help")
    assert r.returncode == 0
    assert ",web}" in r.stdout
    assert "build, check and publish the public site" in r.stdout


def test_web_help_lists_subcommands():
    r = _py("web", "--help")
    assert r.returncode == 0, r.stderr
    assert "{" + ",".join(SUBS) + "}" in r.stdout
    for s in SUBS:
        assert s in r.stdout


def test_web_help_via_full_parser_lists_subcommands():
    from disclosures.cli import build_parser

    p = build_parser()
    sub = next(a for a in p._actions if a.dest == "command")
    web = sub.choices["web"]
    assert "{" + ",".join(SUBS) + "}" in web.format_help()


def test_web_without_subcommand_exits_2():
    from disclosures.cli import main

    assert main(["web"]) == 2


def test_unbuilt_subcommand_exits_2(capsys):
    from disclosures.cli import main

    assert main(["web", "probe-links", "--site", "x"]) == 2
    assert "not implemented yet" in capsys.readouterr().err


def test_web_imports_and_builds_with_heavy_modules_blocked(tmp_path):
    """ADR-W2: no PyMuPDF, google-genai, pydantic, numpy, scipy, rapidfuzz or httpx."""
    out = tmp_path / "site"
    code = textwrap.dedent(f"""
        import sys
        HEAVY = {HEAVY!r}
        for m in HEAVY:
            sys.modules[m] = None   # any import of these raises ImportError
        import disclosures.web, disclosures.web.cli, disclosures.web.build
        import disclosures.web.bundle, disclosures.web.check, disclosures.web.dataset
        import disclosures.web.fixture, disclosures.web.urls
        import disclosures.web.pages, disclosures.web.charts, disclosures.web.metadata
        from disclosures.cli import main
        rc = main(["web", "build", "--db", {str(MINI_DB)!r}, "--manifest",
                   {str(MINI_MANIFEST)!r}, "--out", {str(out)!r}])
        assert rc == 0, rc
        rc = main(["web", "check", {str(out)!r}, "--db", {str(MINI_DB)!r}])
        assert rc == 0, rc
        loaded = [m for m in HEAVY if sys.modules.get(m) is not None]
        assert not loaded, loaded
        print("LIGHT-OK")
    """)
    r = _py(code=code)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "LIGHT-OK" in r.stdout
    assert (out / "data" / "items.json").exists()


def test_web_help_with_heavy_modules_blocked():
    code = textwrap.dedent(f"""
        import sys
        for m in {HEAVY!r}:
            sys.modules[m] = None
        from disclosures.cli import main
        try:
            main(["web", "--help"])
        except SystemExit as e:
            sys.exit(e.code)
    """)
    r = _py(code=code)
    assert r.returncode == 0, r.stderr
    assert "make-fixture" in r.stdout
