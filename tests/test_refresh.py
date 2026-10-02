"""disclosures.refresh (AC-4.5): change detection against a fixture manifest, on the recorded
House 48th listing and Senate payloads served by an httpx MockTransport. No network, no API calls
(sub-commands are stubbed)."""
import io
import json

import httpx
import pytest

import test_scrape as TS
import test_senate as TSE
from disclosures import manifest as M
from disclosures import refresh as R
from disclosures import scrape as SC
from disclosures import senate as SE
from disclosures.cli import main as cli_main

NOW = "2026-10-03T00:00:00Z"


class Both:
    """The House server and the Senate server behind one transport."""

    def __init__(self):
        self.house, self.senate = TS.Server(), TSE.Server()

    def __call__(self, request: httpx.Request):
        host = request.url.host
        return (self.senate if host in SE.sources.SENATE_API_BASE else self.house)(request)

    def client(self):
        return httpx.Client(transport=httpx.MockTransport(self))


@pytest.fixture
def world(tmp_path):
    (tmp_path / "pdfs").mkdir()
    srv = Both()
    out = io.StringIO()
    SC.scrape("house", 48, root=tmp_path, client=srv.client(), out=out, delay=0, now=lambda: NOW)
    SE.scrape(48, root=tmp_path, client=srv.client(), out=out, delay=0, now=lambda: NOW)
    return tmp_path, srv


def _refresh(root, srv, **kw):
    out, calls = io.StringIO(), []
    rc = R.refresh(root=root, client=srv.client(), out=out, delay=0, now=lambda: NOW,
                   main=lambda argv: calls.append(argv) or 0, **kw)
    return rc, out.getvalue(), calls


def _snapshot(root):
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _tamper(root, path):
    rows = M.read_manifest(root / M.MANIFEST_PATH)
    for r in rows:
        if r["pdf_path"] == path:
            r["pdf_sha256"] = "f" * 64
    M.write_manifest(rows, root / M.MANIFEST_PATH)


def test_ac_4_5_dry_run_selects_exactly_the_file_whose_sha_differs(world):
    root, srv = world
    target = sorted(r["pdf_path"] for r in M.read_manifest(root / M.MANIFEST_PATH)
                    if r["parliament"] == "48" and r["chamber"] == "house")[17]
    _tamper(root, target)
    before = _snapshot(root)
    rc, log, calls = _refresh(root, srv, dry_run=True)
    assert rc == 0 and calls == []
    assert "refresh: 1 new/changed (1 house, 0 senate)" in log
    assert f"changed house  {target}" in log
    assert _snapshot(root) == before  # dry run writes nothing


def test_dry_run_with_nothing_changed_selects_nothing(world):
    root, srv = world
    rc, log, calls = _refresh(root, srv, dry_run=True)
    assert (rc, calls) == (0, [])
    assert "refresh: 0 new/changed (0 house, 0 senate)" in log


def test_dry_run_reports_changed_and_new_senators(world):
    root, srv = world
    srv.senate.statements["281503"] = dict(TSE.CICCONE, errors=["changed"])
    rows = M.read_manifest(root / M.MANIFEST_PATH)
    M.write_manifest([r for r in rows if r["pdf_path"] != "pdfs/senate/48/allmanpaynep_48s.json"],
                     root / M.MANIFEST_PATH)
    (root / "pdfs/senate/48/allmanpaynep_48s.json").unlink()  # a senator never seen before
    rc, log, _ = _refresh(root, srv, dry_run=True)
    assert "refresh: 2 new/changed (0 house, 2 senate)" in log
    assert "changed senate pdfs/senate/48/cicconer_48s.json" in log
    assert "new     senate pdfs/senate/48/allmanpaynep_48s.json" in log


def test_gemini_refresh_extracts_only_the_changed_files_then_loads(world):
    root, srv = world
    target = next(r["pdf_path"] for r in M.read_manifest(root / M.MANIFEST_PATH)
                  if r["parliament"] == "48" and r["chamber"] == "house")
    _tamper(root, target)
    srv.senate.statements["281503"] = dict(TSE.CICCONE, errors=["changed"])
    rc, log, calls = _refresh(root, srv)
    assert rc == 0
    assert calls == [
        ["extract", *R.G2_EXTRACT, target],
        ["extract", "--source", "senate-json", "pdfs/senate/48/cicconer_48s.json"],
        ["load", "--source", "gemini-api", "--source", "senate-json"],
        ["entities"],
    ]
    rows = {r["pdf_path"]: r for r in M.read_manifest(root / M.MANIFEST_PATH)}
    assert rows[target]["pdf_sha256"] == M.sha256_file(root / target)  # manifest repaired
    assert rows["pdfs/senate/48/cicconer_48s.json"]["pdf_sha256"] == \
        M.sha256_file(root / "pdfs/senate/48/cicconer_48s.json")
    rc, log, calls = _refresh(root, srv)  # second run: nothing to do
    assert (rc, calls) == (0, [])


def test_g2_config_parses_as_an_extract_command():
    from disclosures.cli import build_parser

    a = build_parser().parse_args(["extract", *R.G2_EXTRACT, "pdfs/48/x_48p.pdf"])
    assert (a.source, a.provider, a.model, a.provider_order, a.fallback_model,
            a.ignore_providers, a.workers) == (
        "gemini", "openrouter", "google/gemini-3.8-flash", "google-ai-studio/flex",
        "anthropic/claude-sonnet-5.5", "azure", 8)


def test_workflow_source_prints_the_workflow_args(world):
    root, srv = world
    target = next(r for r in M.read_manifest(root / M.MANIFEST_PATH)
                  if r["parliament"] == "48" and r["chamber"] == "house")
    _tamper(root, target["pdf_path"])
    rc, log, calls = _refresh(root, srv, source="workflow")
    assert rc == 0 and calls == []  # no LLM extraction, no load: Kevin runs the Workflow first
    line = next(x for x in log.splitlines() if "Workflow name=extract-disclosures args=" in x)
    args = json.loads(line.split("args=", 1)[1])
    assert args == {"pdfs": [target["pdf_path"]],
                    "page_counts": {target["pdf_path"]: int(target["page_count"])},
                    "extracted_at": NOW}
    assert "python -m disclosures load --source workflow-claude --source gemini-api " \
           "--source senate-json" in log


def test_download_failure_is_an_error_not_a_partial_selection(world):
    root, srv = world
    srv.senate.statements.pop("281503")
    rc, log, calls = _refresh(root, srv, dry_run=True)
    assert (rc, calls) == (1, [])
    assert "failed to download" in log


def test_cli_routes_refresh(monkeypatch):
    seen = {}
    monkeypatch.setattr(R, "refresh", lambda **kw: seen.update(kw) or 0)
    assert cli_main(["refresh", "--dry-run"]) == 0
    assert seen == {"source": "gemini", "dry_run": True}
