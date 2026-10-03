"""``web build``: determinism, read-only inputs and the clobber guard (AC-A3), headers and
``web-manifest.json``."""
from __future__ import annotations

import hashlib
import os
import shutil
import stat

import pytest
from web_support import MINI_DB, MINI_MANIFEST, load_json

from disclosures.cli import main
from disclosures.web.build import build, file_index


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def snapshot(root):
    """rel path -> (sha256, mtime_ns, mode) for every file and dir under root."""
    out = {}
    for p in sorted(root.rglob("*")):
        st = p.stat()
        out[p.relative_to(root).as_posix()] = (sha(p) if p.is_file() else None, st.st_mtime_ns,
                                                stat.S_IMODE(st.st_mode))
    return out


def _build(db, manifest, out, *extra):
    return main(["web", "build", "--db", str(db), "--manifest", str(manifest), "--out", str(out),
                 *extra])


def test_build_is_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    assert _build(MINI_DB, MINI_MANIFEST, a) == 0
    assert _build(MINI_DB, MINI_MANIFEST, b) == 0
    fa, fb = file_index(a), file_index(b)
    assert fa == fb
    ma, mb = load_json(a / "web-manifest.json"), load_json(b / "web-manifest.json")
    ma.pop("built_at"), mb.pop("built_at")
    assert ma == mb


def test_source_date_epoch_fixes_build_time(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1759449600")
    build(MINI_DB, MINI_MANIFEST, tmp_path / "s")
    assert load_json(tmp_path / "s" / "web-manifest.json")["built_at"] == \
        "2025-10-03T00:00:00+00:00"


def test_build_on_read_only_inputs(tmp_path):
    """AC-A3: inputs in a chmod -R a-w dir; build succeeds; sha256 and mtime unchanged."""
    ds = tmp_path / "dataset"
    ds.mkdir()
    shutil.copy2(MINI_DB, ds / "disclosures_v2.db")
    shutil.copy2(MINI_MANIFEST, ds / "manifest.csv")
    for p in [*ds.iterdir(), ds]:
        p.chmod(p.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    try:
        before = snapshot(ds)
        assert not os.access(ds, os.W_OK)
        out = tmp_path / "out"
        assert _build(ds / "disclosures_v2.db", ds / "manifest.csv", out) == 0
        assert snapshot(ds) == before
        assert sorted(p.name for p in ds.iterdir()) == ["disclosures_v2.db", "manifest.csv"]
        m = load_json(out / "web-manifest.json")
        assert m["inputs"]["db"]["sha256"] == sha(MINI_DB)
        assert m["inputs"]["manifest"]["sha256"] == sha(MINI_MANIFEST)
    finally:
        for p in [ds, *ds.iterdir()]:
            p.chmod(p.stat().st_mode | stat.S_IWUSR)


def test_non_empty_out_exits_2_and_writes_nothing(tmp_path, capsys):
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep.txt").write_text("mine")
    before_out, before_parent = snapshot(out), sorted(p.name for p in tmp_path.iterdir())
    assert _build(MINI_DB, MINI_MANIFEST, out) == 2
    assert "not empty" in capsys.readouterr().err
    assert snapshot(out) == before_out
    assert sorted(p.name for p in tmp_path.iterdir()) == before_parent


def test_out_that_is_a_file_exits_2(tmp_path):
    f = tmp_path / "out"
    f.write_text("x")
    assert _build(MINI_DB, MINI_MANIFEST, f) == 2
    assert f.read_text() == "x"


def test_empty_out_dir_is_used(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    assert _build(MINI_DB, MINI_MANIFEST, out) == 0
    assert (out / "data" / "items.json").exists()
    assert [p.name for p in tmp_path.iterdir()] == ["out"]  # no staging dir left behind


def test_refuses_v1_db(tmp_path):
    v1 = tmp_path / "disclosures.db"
    shutil.copy2(MINI_DB, v1)
    assert _build(v1, MINI_MANIFEST, tmp_path / "out") == 2
    assert not (tmp_path / "out").exists()


def test_missing_inputs_exit_2(tmp_path):
    assert _build(tmp_path / "nope.db", MINI_MANIFEST, tmp_path / "o1") == 2
    assert _build(MINI_DB, tmp_path / "nope.csv", tmp_path / "o2") == 2
    assert not (tmp_path / "o1").exists() and not (tmp_path / "o2").exists()


def test_document_without_manifest_url_fails_closed(tmp_path):
    lines = MINI_MANIFEST.read_text().splitlines(keepends=True)
    short = tmp_path / "short.csv"
    short.write_text("".join(lines[:-1]))
    assert _build(MINI_DB, short, tmp_path / "out") == 2
    assert not (tmp_path / "out").exists()
    assert [p.name for p in tmp_path.iterdir()] == ["short.csv"]


def test_bad_data_base_exits_2(tmp_path):
    assert _build(MINI_DB, MINI_MANIFEST, tmp_path / "o", "--data-base", "ftp://x") == 2
    assert _build(MINI_DB, MINI_MANIFEST, tmp_path / "o", "--data-base", "https://x/no-slash") == 2


def test_unsafe_member_id_fails(tmp_path):
    db = tmp_path / "bad.db"
    shutil.copy2(MINI_DB, db)
    import sqlite3

    con = sqlite3.connect(db)
    con.execute("insert into members values ('Bad Id', 'Bad', 'house')")
    con.commit()
    con.close()
    assert _build(db, MINI_MANIFEST, tmp_path / "out") == 2


def test_headers_preview_and_production(tmp_path):
    build(MINI_DB, MINI_MANIFEST, tmp_path / "p", mode="preview")
    build(MINI_DB, MINI_MANIFEST, tmp_path / "q", mode="production")
    pv = (tmp_path / "p" / "_headers").read_text()
    pr = (tmp_path / "q" / "_headers").read_text()
    for h in (pv, pr):
        assert "/data/*\n  Access-Control-Allow-Origin: *\n" in h
        assert "/*/items.json\n  Access-Control-Allow-Origin: *\n" in h
        assert "/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n" in h
    assert "X-Robots-Tag: noindex" in pv
    assert "noindex" not in pr


def test_web_manifest(mini_site):
    m = load_json(mini_site / "web-manifest.json")
    assert m["mode"] == "preview"
    assert m["web_bundle_version"] == "1"
    assert m["data_base"] == "https://data.kevinrassool.com/interests/"
    assert m["inputs"]["db"]["sha256"] == sha(MINI_DB)
    assert m["inputs"]["manifest"]["sha256"] == sha(MINI_MANIFEST)
    assert m["meta"]["fixture"] == "1"
    assert m["files"] == file_index(mini_site)
    assert "web-manifest.json" not in m["files"]
    for rel in ("_headers", "data/items.json", "data/members.json", "data/entities.json",
                "data/documents.json", "data/search.json", "data/summary.json",
                "data/schema.json"):
        assert rel in m["files"], rel


@pytest.mark.parametrize("mode", ["preview", "production"])
def test_built_site_passes_check(tmp_path, mode):
    from disclosures.web.check import check_site

    build(MINI_DB, MINI_MANIFEST, tmp_path / "s", mode=mode)
    fails, notes = check_site(tmp_path / "s", MINI_DB)
    assert fails == []
    assert not any("skipped" in n for n in notes if "member" in n)
    assert (tmp_path / "s" / "members" / "wayne_swan" / "index.html").is_file()
