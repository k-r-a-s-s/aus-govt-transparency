"""AC-B8: JSON-LD ``Dataset`` on ``/`` and ``/data/``, ``sitemap.xml``, ``robots.txt``, and the
``changes.xml`` RSS feed."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest
from html_tree import parse_file
from web_support import MINI_DB, MINI_MANIFEST, ro

from disclosures.cli import main
from disclosures.web.build import build
from disclosures.web.check import page_path

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
R2_DATA = {"disclosures_v2.db": "application/vnd.sqlite3", "disclosures_v2.csv": "text/csv",
           "disclosures_v2.csv.gz": "application/gzip",
           "disclosures_v2.jsonl.gz": "application/gzip"}


def jsonld(path):
    scripts = parse_file(path).find_all("script", type="application/ld+json")
    assert len(scripts) == 1
    return json.loads(scripts[0].raw_text())


def check_dataset(doc, data_base="https://data.kevinrassool.com/interests/"):
    assert doc["@context"] == "https://schema.org/" and doc["@type"] == "Dataset"
    for key in ("name", "description", "license", "creator", "temporalCoverage",
                "distribution", "isAccessibleForFree", "url", "version"):
        assert key in doc, key
    assert 50 <= len(doc["description"]) <= 5000
    assert doc["license"] == "https://creativecommons.org/licenses/by/4.0/"
    assert doc["isAccessibleForFree"] is True
    assert doc["creator"]["name"] == "Kevin Rassool"
    dist = {d["name"]: d for d in doc["distribution"]}
    assert set(dist) == set(R2_DATA)
    for name, d in dist.items():
        assert d["@type"] == "DataDownload"
        assert d["contentUrl"] == f"{data_base}latest/{name}"
        assert d["encodingFormat"] == R2_DATA[name]


@pytest.mark.parametrize("rel", ["index.html", "data/index.html"])
def test_jsonld_dataset(mini_site, rel):
    doc = jsonld(mini_site / rel)
    check_dataset(doc)
    assert "identifier" not in doc
    loaded = ro(MINI_DB).execute("select value from meta where key = 'loaded_at'").fetchone()[0]
    assert doc["version"] == f"v2.{loaded[:10]}"


def test_jsonld_only_on_overview_and_data(mini_site):
    with_ld = sorted(p.relative_to(mini_site).as_posix() for p in mini_site.rglob("*.html")
                     if "application/ld+json" in p.read_text())
    assert with_ld == ["data/index.html", "index.html"]


def test_doi_and_site_url_flags(tmp_path):
    out = tmp_path / "s"
    assert main(["web", "build", "--db", str(MINI_DB), "--manifest", str(MINI_MANIFEST),
                 "--out", str(out), "--mode", "production", "--doi",
                 "https://doi.org/10.5281/zenodo.123", "--site-url", "https://example.org/",
                 "--data-base", "https://files.example.org/x/"]) == 0
    for rel in ("index.html", "data/index.html"):
        doc = jsonld(out / rel)
        check_dataset(doc, "https://files.example.org/x/")
        assert doc["identifier"] == "https://doi.org/10.5281/zenodo.123"
        assert doc["url"] == "https://example.org/"
    home = parse_file(out / "index.html")
    assert home.find("link", rel="canonical").attrs["href"] == "https://example.org/"
    assert "10.5281/zenodo.123" in home.find("footer", "site-footer").text
    assert "https://doi.org/10.5281/zenodo.123" in home.find("pre", "cite").text
    robots = (out / "robots.txt").read_text()
    assert "Sitemap: https://example.org/sitemap.xml" in robots
    locs = [e.text for e in ET.parse(out / "sitemap.xml").getroot().iter(f"{SITEMAP_NS}loc")]
    assert all(u.startswith("https://example.org/") for u in locs)


@pytest.mark.parametrize("args", [["--doi", "not-a-doi"], ["--site-url", "ftp://x"],
                                  ["--site-url", "https://x.org/sub/"],
                                  ["--data-files", "/nonexistent/dir"]])
def test_bad_metadata_flags_exit_2(tmp_path, args):
    out = tmp_path / "s"
    assert main(["web", "build", "--db", str(MINI_DB), "--manifest", str(MINI_MANIFEST),
                 "--out", str(out), *args]) == 2
    assert not out.exists()


def test_sitemap_lists_every_page(mini_site):
    root = ET.parse(mini_site / "sitemap.xml").getroot()
    locs = [e.text for e in root.iter(f"{SITEMAP_NS}loc")]
    assert locs == sorted(locs) and len(locs) == len(set(locs))
    assert all(u.startswith("https://interests.kevinrassool.com/") for u in locs)
    pages = {page_path(p.relative_to(mini_site).as_posix()) for p in mini_site.rglob("*.html")}
    pages.discard("/404.html")
    assert {u[len("https://interests.kevinrassool.com"):] for u in locs} == pages


def test_robots(mini_site, tmp_path):
    assert (mini_site / "robots.txt").read_text() == \
        "# Preview build: not for indexing.\nUser-agent: *\nDisallow: /\n"
    build(MINI_DB, MINI_MANIFEST, tmp_path / "p", mode="production")
    assert (tmp_path / "p" / "robots.txt").read_text() == (
        "User-agent: *\nAllow: /\n\nSitemap: https://interests.kevinrassool.com/sitemap.xml\n")


def test_changes_xml_is_rss2_with_one_entry(mini_site):
    root = ET.parse(mini_site / "changes.xml").getroot()
    assert root.tag == "rss" and root.attrib["version"] == "2.0"
    channel = root.find("channel")
    for tag in ("title", "link", "description"):
        assert channel.find(tag).text
    items = channel.findall("item")
    assert len(items) == 1
    loaded = ro(MINI_DB).execute("select value from meta where key = 'loaded_at'").fetchone()[0]
    assert items[0].find("title").text == f"Dataset v2.{loaded[:10]}"
    assert items[0].find("pubDate").text.endswith("GMT")
    assert items[0].find("guid").text == f"aus-interests-v2.{loaded[:10]}"
    home = parse_file(mini_site / "index.html")
    assert home.find("link", rel="alternate").attrs["href"] == "/changes.xml"
