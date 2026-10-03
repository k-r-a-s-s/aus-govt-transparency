"""AC-A5: ``web check`` exits 1 naming the rule for each planted fault (one test per fault,
on copies of the mini site). After planting, ``reseal`` rewrites ``web-manifest.json`` so the
planted fault is the only rule that fires."""
from __future__ import annotations

import json

import pytest
from web_support import MINI_DB, load_json, ro

from disclosures.cli import main
from disclosures.web import check as C
from disclosures.web.build import file_index


def page(*, noindex=True, footer=True, head="", body=""):
    robots = '<meta name="robots" content="noindex,nofollow">' if noindex else ""
    foot = ('<footer class="site-footer"><p>Transcribed from the Parliament of Australia '
            'registers; CC BY 4.0; check the source.</p></footer>' if footer else "")
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>{robots}{head}"
            f"<title>t</title></head><body><main>{body}</main>{foot}</body></html>")


def reseal(site):
    m = load_json(site / "web-manifest.json")
    m["files"] = file_index(site)
    (site / "web-manifest.json").write_text(json.dumps(m))


def set_mode(site, mode):
    m = load_json(site / "web-manifest.json")
    m["mode"] = mode
    (site / "web-manifest.json").write_text(json.dumps(m))


def rules(site, db=None):
    fails, _ = C.check_site(site, db)
    return {r for r, _ in fails}


def test_clean_mini_site_passes(site_copy, capsys):
    assert main(["web", "check", str(site_copy), "--db", str(MINI_DB)]) == 0
    assert "web check: ok" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["data/disclosures_v2.db", "x.csv", "data/x.parquet",
                                  "y.sqlite", "z.csv.gz"])
def test_forbidden_data_file(site_copy, name, capsys):
    (site_copy / name).write_bytes(b"x")
    reseal(site_copy)
    assert rules(site_copy) == {"forbidden-file"}
    assert main(["web", "check", str(site_copy)]) == 1
    assert "FAIL forbidden-file" in capsys.readouterr().out


def test_file_over_20_mib(site_copy):
    with (site_copy / "big.bin").open("wb") as f:
        f.truncate(20 * 1024 * 1024 + 1)
    reseal(site_copy)
    assert rules(site_copy) == {"file-too-large"}


def test_more_than_12000_files(site_copy):
    d = site_copy / "many"
    d.mkdir()
    for i in range(12_001):
        (d / f"{i}.txt").write_bytes(b"")
    reseal(site_copy)
    assert rules(site_copy) == {"too-many-files"}


def test_total_over_limit(site_copy, monkeypatch):
    monkeypatch.setattr(C, "MAX_TOTAL", 1000)
    assert rules(site_copy) == {"site-too-large"}


def test_html_rules_pass_vacuously_without_html(site_copy):
    assert not list(site_copy.rglob("*.html"))
    assert rules(site_copy) == set()


def test_good_html_passes(site_copy):
    (site_copy / "index.html").write_text(page(head='<link rel="stylesheet" href="/assets/a.css">'
                                               '<script src="/assets/a.js"></script>'))
    reseal(site_copy)
    assert rules(site_copy) == set()


def test_html_over_2_mib(site_copy):
    (site_copy / "index.html").write_text(page(body="x" * (2 * 1024 * 1024 + 1)))
    reseal(site_copy)
    assert rules(site_copy) == {"html-too-large"}


def test_html_without_footer(site_copy):
    (site_copy / "index.html").write_text(page(footer=False))
    reseal(site_copy)
    assert rules(site_copy) == {"footer-missing"}


def test_footer_without_licence(site_copy):
    (site_copy / "index.html").write_text(
        page(footer=False, body='<footer class="site-footer">no licence</footer>'))
    reseal(site_copy)
    assert rules(site_copy) == {"footer-missing"}


@pytest.mark.parametrize("head", [
    '<script src="https://cdn.example.com/x.js"></script>',
    '<script src="//cdn.example.com/x.js"></script>',
    '<link rel="stylesheet" href="https://fonts.example.com/x.css">',
    '<link rel="modulepreload" href="https://cdn.example.com/m.js">',
])
def test_external_script_or_stylesheet(site_copy, head):
    (site_copy / "index.html").write_text(page(head=head))
    reseal(site_copy)
    assert rules(site_copy) == {"external-asset"}


def test_production_with_noindex_header(site_copy):
    set_mode(site_copy, "production")  # _headers still carries the preview noindex
    assert rules(site_copy) == {"noindex-in-production"}


def test_production_with_noindex_meta(site_copy):
    (site_copy / "_headers").write_text("/data/*\n  Access-Control-Allow-Origin: *\n")
    (site_copy / "index.html").write_text(page(noindex=True))
    set_mode(site_copy, "production")
    reseal(site_copy)
    assert rules(site_copy) == {"noindex-in-production"}


def test_preview_without_noindex_header(site_copy):
    (site_copy / "_headers").write_text("/data/*\n  Access-Control-Allow-Origin: *\n")
    reseal(site_copy)
    assert rules(site_copy) == {"noindex-missing-in-preview"}


def test_preview_page_without_noindex_meta(site_copy):
    (site_copy / "index.html").write_text(page(noindex=False))
    reseal(site_copy)
    assert rules(site_copy) == {"noindex-missing-in-preview"}


def _member_pages(site, skip=()):
    ids = [r[0] for r in ro(MINI_DB).execute("select member_id from members order by 1")]
    for mid in ids:
        if mid not in skip:
            (site / "members" / mid / "index.html").write_text(page())
    return ids


def test_member_page_missing(site_copy, capsys):
    ids = _member_pages(site_copy, skip={"wayne_swan"})
    assert "wayne_swan" in ids
    reseal(site_copy)
    assert rules(site_copy, MINI_DB) == {"member-page-missing"}
    assert main(["web", "check", str(site_copy), "--db", str(MINI_DB)]) == 1
    assert "FAIL member-page-missing: members/wayne_swan/index.html" in capsys.readouterr().out


def test_all_member_pages_present(site_copy):
    _member_pages(site_copy)
    reseal(site_copy)
    assert rules(site_copy, MINI_DB) == set()


def test_member_pages_skipped_in_phase_a(site_copy):
    fails, notes = C.check_site(site_copy, MINI_DB)
    assert fails == []
    assert any("member-page-missing skipped" in n for n in notes)


def test_member_json_missing(site_copy):
    (site_copy / "members" / "wayne_swan" / "items.json").unlink()
    reseal(site_copy)
    assert rules(site_copy, MINI_DB) == {"member-json-missing"}


def test_manifest_mismatch_on_edited_file(site_copy):
    (site_copy / "data" / "summary.json").write_text("{}\n")
    assert rules(site_copy) == {"manifest-mismatch"}


def test_manifest_mismatch_on_unlisted_file(site_copy):
    (site_copy / "extra.txt").write_text("x")
    assert rules(site_copy) == {"manifest-mismatch"}


def test_bad_input_exits_2(tmp_path, site_copy):
    assert main(["web", "check", str(tmp_path / "nope")]) == 2
    empty = tmp_path / "empty"
    empty.mkdir()
    assert main(["web", "check", str(empty)]) == 2
    assert main(["web", "check", str(site_copy), "--db", str(tmp_path / "nope.db")]) == 2
    set_mode(site_copy, "staging")
    assert main(["web", "check", str(site_copy)]) == 2


def test_every_rule_is_named():
    assert set(C.RULES) == {
        "forbidden-file", "file-too-large", "too-many-files", "site-too-large",
        "html-too-large", "footer-missing", "external-asset", "noindex-in-production",
        "noindex-missing-in-preview", "manifest-mismatch", "member-json-missing",
        "member-page-missing"}
