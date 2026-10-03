"""Phase B build plumbing: staging inside ``--out`` only, size limits, assets (CSS hash, fonts,
optional JS bundle), and the phase A verification fixes (source_link input error, v1 message)."""
from __future__ import annotations

import hashlib
import os

import pytest
from html_tree import parse_file
from web_support import MINI_DB, MINI_MANIFEST, load_json

from disclosures.cli import main
from disclosures.web import build as B
from disclosures.web import urls as U
from disclosures.web.check import check_site

PDF = ("https://static.aph.gov.au/-/media/03_Senators_and_Members/32_Members/Register/47p/"
       "AB/AbbottA_47P.pdf?rev=abc&hash=DEF")


def listing(d):
    return sorted(p.name for p in d.iterdir())


def test_nothing_written_or_deleted_outside_out(tmp_path):
    """The old staging dir lived beside --out and an existing one was removed; now a dir of
    that old name is left alone and the parent gains only --out."""
    old_style = tmp_path / f".out.tmp-{os.getpid()}"
    old_style.mkdir()
    (old_style / "keep.txt").write_text("not ours")
    before = listing(tmp_path)
    assert main(["web", "build", "--db", str(MINI_DB), "--manifest", str(MINI_MANIFEST),
                 "--out", str(tmp_path / "out")]) == 0
    assert listing(tmp_path) == sorted(before + ["out"])
    assert (old_style / "keep.txt").read_text() == "not ours"
    assert not [p for p in (tmp_path / "out").iterdir() if p.name.startswith(".staging")]


def test_failure_cleans_up_inside_out_only(tmp_path, monkeypatch):
    import disclosures.web.pages as P

    def boom(*a, **k):
        raise RuntimeError("render failed")

    monkeypatch.setattr(P, "render_site", boom)
    before = listing(tmp_path)
    with pytest.raises(RuntimeError):
        B.build(MINI_DB, MINI_MANIFEST, tmp_path / "new")
    assert listing(tmp_path) == before  # --out created by the build is removed again
    existing = tmp_path / "empty"
    existing.mkdir()
    with pytest.raises(RuntimeError):
        B.build(MINI_DB, MINI_MANIFEST, existing)
    assert existing.is_dir() and listing(existing) == []


def test_size_limits_fail_closed(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(B, "MAX_TOTAL", 1000)
    assert main(["web", "build", "--db", str(MINI_DB), "--manifest", str(MINI_MANIFEST),
                 "--out", str(tmp_path / "s")]) == 2
    assert "MiB (max 0 MiB)" in capsys.readouterr().err
    assert not (tmp_path / "s").exists()
    monkeypatch.setattr(B, "MAX_TOTAL", 300 * B.MiB)
    monkeypatch.setattr(B, "MAX_FILES", 10)
    assert main(["web", "build", "--db", str(MINI_DB), "--manifest", str(MINI_MANIFEST),
                 "--out", str(tmp_path / "t")]) == 2
    assert "files (max 10)" in capsys.readouterr().err
    assert not (tmp_path / "t").exists()


def test_css_fonts_and_no_js(tmp_path):
    out = tmp_path / "s"
    s = B.build(MINI_DB, MINI_MANIFEST, out, web_dist=tmp_path / "no-dist")
    assert s["js"] == []
    css = list((out / "assets").glob("style.*.css"))
    assert len(css) == 1
    data = css[0].read_bytes()
    assert css[0].name == f"style.{hashlib.sha256(data).hexdigest()[:8]}.css"
    assert data == (B.STATIC_DIR / "style.css").read_bytes()
    fonts = listing(out / "fonts")
    for f in ("young-serif-latin.woff2", "atkinson-hyperlegible-next-latin.woff2",
              "jetbrains-mono-latin.woff2", "OFL-youngserif.txt",
              "OFL-atkinsonhyperlegiblenext.txt", "OFL-jetbrainsmono.txt"):
        assert f in fonts
    for url in ("/fonts/young-serif-latin.woff2", "/fonts/jetbrains-mono-latin.woff2"):
        assert f"url({url})" in data.decode()
    doc = parse_file(out / "members" / "index.html")
    assert doc.find_all("script", type="module") == []
    assert doc.find("link", rel="stylesheet").attrs["href"] == "/" + css[0].relative_to(out).as_posix()


def test_js_bundle_copied_with_hash_and_referenced(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    js = b"document.title='x';\n"
    (dist / "index-search.js").write_bytes(js)
    (dist / "explore.js").write_bytes(b"/* explorer */\n")
    out = tmp_path / "s"
    s = B.build(MINI_DB, MINI_MANIFEST, out, web_dist=dist)
    assert s["js"] == ["explore", "index-search"]
    name = f"index-search.{hashlib.sha256(js).hexdigest()[:8]}.js"
    assert (out / "assets" / name).read_bytes() == js
    for rel in ("members/index.html", "entities/index.html"):
        srcs = [e.attrs["src"] for e in parse_file(out / rel).find_all("script", type="module")]
        assert srcs == [f"/assets/{name}"], rel
    srcs = [e.attrs["src"] for e in parse_file(out / "explore" / "index.html").find_all(
        "script", type="module")]
    assert len(srcs) == 1 and srcs[0].startswith("/assets/explore.")
    assert parse_file(out / "index.html").find_all("script", type="module") == []
    assert load_json(out / "web-manifest.json")["assets"]["js"]["index-search"] == f"/assets/{name}"
    assert check_site(out, MINI_DB)[0] == []


def test_every_asset_url_is_root_relative(mini_site):
    for p in mini_site.rglob("*.html"):
        doc = parse_file(p)
        for e in doc.find_all("link") + doc.find_all("script"):
            url = e.attrs.get("href") or e.attrs.get("src")
            rel = e.attrs.get("rel", "")
            if url and rel not in ("canonical",):
                assert url.startswith("/") and not url.startswith("//"), (p, url)


@pytest.mark.parametrize("page", [None, 0, -1, "3", 2.0, True])
def test_source_link_rejects_bad_page(page):
    with pytest.raises(U.SourceLinkError, match="page must be a positive integer"):
        U.source_link(PDF, page)
    assert issubclass(U.SourceLinkError, ValueError)


def test_v1_refusal_message(tmp_path, capsys):
    import shutil

    v1 = tmp_path / "disclosures.db"
    shutil.copy2(MINI_DB, v1)
    assert main(["web", "build", "--db", str(v1), "--manifest", str(MINI_MANIFEST),
                 "--out", str(tmp_path / "out")]) == 2
    err = capsys.readouterr().err
    assert "refusing to open the frozen v1 database" in err
    assert "refusing to write" not in err
