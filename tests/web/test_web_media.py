"""Member photos, organisation logos and Open Graph cards (SPEC decisions log 2026-10-04).

The build reads ``--media`` (``media.json`` + files), copies each listed image to a hashed
name under ``/media/`` and links it from the pages; every page gets an ``og:image`` on the
card host and an entry in ``og-cards.json``. All offline: the media folder here is made by
the test.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from web_support import MINI_DB, MINI_MANIFEST

from disclosures.web.build import BuildError, build

PHOTO = b"\xff\xd8\xff\xe0" + b"fake jpeg for josh_wilson" * 200
LOGO = b"\x89PNG\r\n\x1a\n" + b"fake png for amp" * 100


def _media(root: Path, *, photo=PHOTO, sha=None, extra_member=False) -> Path:
    m = root / "media"
    (m / "photos").mkdir(parents=True)
    (m / "logos").mkdir()
    (m / "photos" / "josh_wilson.jpg").write_bytes(photo)
    (m / "logos" / "amp.png").write_bytes(LOGO)
    photos = [{"member_id": "josh_wilson", "file": "photos/josh_wilson.jpg",
               "sha256": sha or hashlib.sha256(photo).hexdigest(), "aph_id": "E0H",
               "source_url": "https://www.aph.gov.au/api/parliamentarian/E0H/image",
               "source_page": "https://www.aph.gov.au/Senators_and_Members/Parliamentarian?MPID=E0H",
               "licence": "CC BY-NC-ND 4.0",
               "licence_url": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
               "credit": "Parliament of Australia", "retrieved": "2026-10-04"}]
    if extra_member:
        (m / "photos" / "not_in_fixture.jpg").write_bytes(photo)
        photos.append({**photos[0], "member_id": "not_in_fixture",
                       "file": "photos/not_in_fixture.jpg"})
    logos = [{"entity_id": "amp", "file": "logos/amp.png",
              "sha256": hashlib.sha256(LOGO).hexdigest(), "source_url": "https://example.org/amp.svg",
              "source_page": "https://commons.wikimedia.org/wiki/File:AMP_logo.svg",
              "source_kind": "wikimedia_commons", "licence": "Public domain", "licence_url": "",
              "author": "AMP Limited", "retrieved": "2026-10-04", "notes": ""}]
    (m / "media.json").write_text(json.dumps({"media_version": 1, "photos": photos,
                                              "logos": logos}))
    return m


@pytest.fixture(scope="module")
def media_site(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("media-site")
    out = root / "site"
    build(MINI_DB, MINI_MANIFEST, out, mode="preview", media=_media(root, extra_member=True))
    return out


def _page(site: Path, rel: str) -> str:
    return (site / rel / "index.html").read_text(encoding="utf-8")


def test_photo_copied_with_hashed_name_and_shown(media_site):
    href = f"/media/p/josh_wilson.{hashlib.sha256(PHOTO).hexdigest()[:8]}.jpg"
    assert (media_site / href.lstrip("/")).read_bytes() == PHOTO  # byte for byte
    html = _page(media_site, "members/josh_wilson")
    assert f'<img class="portrait" src="{href}" alt="Official portrait of ' in html
    assert f'src="{href}"' in _page(media_site, "members")
    # A member without a photo keeps the placeholder, not a broken image.
    assert 'class="portrait"' not in _page(media_site, "members/wayne_swan")


def test_logo_shown_on_entity_page_and_credited(media_site):
    href = f"/media/l/amp.{hashlib.sha256(LOGO).hexdigest()[:8]}.png"
    assert (media_site / href.lstrip("/")).read_bytes() == LOGO
    assert f'<img src="{href}" alt="AMP logo"' in _page(media_site, "entities/amp")
    about = _page(media_site, "about")
    assert 'id="image-credits"' in about and 'id="logo-credits"' in about
    assert "https://commons.wikimedia.org/wiki/File:AMP_logo.svg" in about
    assert "CC BY-NC-ND 4.0" in about and "Parliament of Australia" in about


def test_media_index_for_the_graph(media_site):
    idx = json.loads((media_site / "data" / "media.json").read_text())
    assert set(idx) == {"members", "entities"}
    assert list(idx["members"]) == ["josh_wilson"]          # not_in_fixture skipped
    assert list(idx["entities"]) == ["amp"]
    assert not list((media_site / "media" / "p").glob("not_in_fixture*"))
    assert "/media/*" in (media_site / "_headers").read_text()


def test_sha_mismatch_fails_the_build(tmp_path):
    with pytest.raises(BuildError, match="sha256"):
        build(MINI_DB, MINI_MANIFEST, tmp_path / "site", media=_media(tmp_path, sha="0" * 64))
    assert not (tmp_path / "site").exists()


def test_media_folder_without_media_json_is_refused(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(BuildError, match="media.json"):
        build(MINI_DB, MINI_MANIFEST, tmp_path / "site", media=tmp_path / "empty")


def test_no_media_no_images(mini_site):
    assert 'class="portrait"' not in _page(mini_site, "members/josh_wilson")
    idx = json.loads((mini_site / "data" / "media.json").read_text())
    assert idx == {"members": {}, "entities": {}}
    assert 'id="image-credits"' not in _page(mini_site, "about")


OG = re.compile(r'<meta property="og:image" content="([^"]+)">')


def test_every_page_has_a_card(media_site):
    spec = json.loads((media_site / "og-cards.json").read_text())
    base = spec["og_base"]
    assert re.fullmatch(r"https://data\.kevinrassool\.com/interests/og/v2\.[0-9-]+\.c\d+/", base)
    cards = {c["path"]: c for c in spec["cards"]}
    files = [c["file"] for c in spec["cards"]]
    assert len(files) == len(set(files))
    pages = sorted(media_site.rglob("*.html"))
    assert len(cards) == len(pages)
    for p in pages:
        html = p.read_text(encoding="utf-8")
        rel = "/" + p.relative_to(media_site).as_posix()
        path = rel[: -len("index.html")] if rel.endswith("/index.html") else rel
        card = cards[path]
        assert OG.search(html).group(1) == base + card["file"]
        assert '<meta name="twitter:card" content="summary_large_image">' in html
        assert '<meta property="og:image:width" content="1200">' in html
        assert len(card["stats"]) == 3 and card["title"] and card["eyebrow"]


def test_member_and_entity_cards_carry_their_own_numbers(media_site):
    cards = {c["path"]: c for c in json.loads((media_site / "og-cards.json").read_text())["cards"]}
    m = cards["/members/josh_wilson/"]
    assert m["title"] == "Josh Wilson" and m["file"] == "members/josh_wilson.png"
    n_items = len(json.loads((media_site / "members/josh_wilson/items.json").read_text()))
    assert m["stats"][0][0] == f"{n_items:,}" and m["accent"] == "Labor"
    e = cards["/entities/amp/"]
    assert e["bar"] and sum(b["value"] for b in e["bar"]) >= int(e["stats"][0][0].replace(",", ""))
    assert cards["/"]["file"] == "index.png" and cards["/404.html"]["file"] == "404.png"


def test_og_base_option(tmp_path):
    out = tmp_path / "site"
    build(MINI_DB, MINI_MANIFEST, out, og_base="https://cards.example.org/x/")
    assert 'content="https://cards.example.org/x/members/josh_wilson.png"' in \
        _page(out, "members/josh_wilson")
    with pytest.raises(BuildError):
        build(MINI_DB, MINI_MANIFEST, tmp_path / "s2", og_base="not a url")
