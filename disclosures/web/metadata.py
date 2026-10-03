"""Machine-readable metadata for the public site (ADR-W4, AC-B8): schema.org ``Dataset``
JSON-LD, ``sitemap.xml``, ``robots.txt`` and the ``changes.xml`` RSS feed.

Everything here is a pure function of the dataset facts passed in, so the output is the same
on every build of the same inputs (no clock reads; the feed date is ``meta.loaded_at``).
"""
from __future__ import annotations

import datetime as dt
import json
from email.utils import format_datetime
from typing import Dict, Iterable, List, Optional
from xml.sax.saxutils import escape as xml_escape

DATASET_NAME = "Australian Parliament Registers of Interests"
CREATOR = {"@type": "Person", "name": "Kevin Rassool", "url": "https://kevinrassool.com"}
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
SOURCE_LICENSE_URL = "https://creativecommons.org/licenses/by-nc-nd/4.0/"
KAGGLE_URL = ("https://www.kaggle.com/datasets/"
              "kevrass/australian-parliament-registers-of-interests")
APH_HOUSE_REGISTER = "https://www.aph.gov.au/Senators_and_Members/Members/Register"

# The files publish-data puts on R2 under interests/<version>/ and interests/latest/ (ADR-W6):
# (file name, encodingFormat, label, is a data distribution, optional)
R2_FILES = [
    ("disclosures_v2.db", "application/vnd.sqlite3", "SQLite database (all tables)", True, False),
    ("disclosures_v2.csv", "text/csv", "CSV, one row per item", True, False),
    ("disclosures_v2.csv.gz", "application/gzip", "CSV, gzip-compressed", True, False),
    ("disclosures_v2.jsonl.gz", "application/gzip", "JSON Lines, gzip-compressed", True, False),
    ("disclosures_v2.parquet", "application/vnd.apache.parquet", "Parquet", True, True),
    ("README.md", "text/markdown", "README: field dictionary, method, limitations", False,
     False),
    ("datapackage.json", "application/json", "Frictionless Data Package descriptor", False,
     False),
    ("MANIFEST.json", "application/json", "sha256 and size of every file", False, False),
]


def dataset_version(meta: Dict[str, str]) -> str:
    """``v2.<loaded_at date>`` (ADR-W6), e.g. ``v2.2026-10-02``."""
    return f"v2.{(meta.get('loaded_at') or 'unknown')[:10]}"


def data_url(data_base: str, name: str) -> str:
    return f"{data_base}latest/{name}"


def doi_url(doi: Optional[str]) -> Optional[str]:
    return f"https://doi.org/{doi}" if doi else None


def dataset_description(summary: dict) -> str:
    return (f"Every interest Australian federal MPs and senators disclosed in the Registers of "
            f"Members' and Senators' Interests, transcribed item by item from the official "
            f"statements: {summary['items']:,} items from {summary['statements']:,} statements "
            f"of {summary['members']:,} members (House of Representatives, 43rd to 48th "
            f"parliaments; Senate, 48th parliament), each joined with the member's party and "
            f"a standardised entity. Each item links to the page of the source document.")


def dataset_jsonld(summary: dict, meta: Dict[str, str], *, site_url: str, data_base: str,
                   distribution: Iterable[dict], doi: Optional[str] = None) -> dict:
    """The schema.org ``Dataset`` object for ``/`` and ``/data/``."""
    data_date = (meta.get("loaded_at") or "")[:10]
    doc = {
        "@context": "https://schema.org/",
        "@type": "Dataset",
        "name": DATASET_NAME,
        "description": dataset_description(summary),
        "url": f"{site_url}/",
        "sameAs": KAGGLE_URL,
        "version": dataset_version(meta),
        "dateModified": data_date,
        "license": LICENSE_URL,
        "creator": CREATOR,
        "publisher": CREATOR,
        "isAccessibleForFree": True,
        "isBasedOn": APH_HOUSE_REGISTER,
        "keywords": ["Australia", "Parliament", "register of interests", "politics",
                     "transparency", "members of parliament", "senators"],
        "spatialCoverage": "Australia",
        "temporalCoverage": f"2010/{data_date[:4] or '..'}",
        "distribution": [
            {"@type": "DataDownload", "name": d["name"], "description": d["label"],
             "contentUrl": d["url"], "encodingFormat": d["format"]}
            for d in distribution],
    }
    if doi:
        doc["identifier"] = doi_url(doi)
    return doc


def jsonld_script(doc: dict) -> str:
    """JSON for a ``<script type="application/ld+json">`` body (``<`` escaped)."""
    s = json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=False)
    return s.replace("<", "\\u003c")


def sitemap_xml(site_url: str, paths: Iterable[str], lastmod: Optional[str]) -> str:
    """``sitemap.xml`` listing every page path (absolute URLs), sorted."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in sorted(set(paths)):
        lm = f"<lastmod>{xml_escape(lastmod)}</lastmod>" if lastmod else ""
        lines.append(f"<url><loc>{xml_escape(site_url + p)}</loc>{lm}</url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def robots_txt(mode: str, site_url: str) -> str:
    if mode == "production":
        return f"User-agent: *\nAllow: /\n\nSitemap: {site_url}/sitemap.xml\n"
    return "# Preview build: not for indexing.\nUser-agent: *\nDisallow: /\n"


def _rfc822(loaded_at: Optional[str]) -> Optional[str]:
    if not loaded_at:
        return None
    try:
        t = dt.datetime.fromisoformat(loaded_at)
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return format_datetime(t.astimezone(dt.timezone.utc), usegmt=True)


def changes_xml(site_url: str, summary: dict, meta: Dict[str, str]) -> str:
    """RSS 2.0 with one entry for the current dataset version (from ``meta.loaded_at``)."""
    version = dataset_version(meta)
    date = _rfc822(meta.get("loaded_at"))
    pub = f"<pubDate>{date}</pubDate>" if date else ""
    title = f"Dataset {version}"
    desc = (f"Data loaded {meta.get('loaded_at', 'unknown')}: {summary['items']:,} items, "
            f"{summary['members']:,} members, {summary['statements']:,} statements.")
    link = f"{site_url}/data/"
    items: List[str] = [
        "<item>",
        f"<title>{xml_escape(title)}</title>",
        f"<link>{xml_escape(link)}</link>",
        f'<guid isPermaLink="false">aus-interests-{xml_escape(version)}</guid>',
        pub,
        f"<description>{xml_escape(desc)}</description>",
        "</item>",
    ]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        "<channel>",
        f"<title>{xml_escape(DATASET_NAME)}: dataset versions</title>",
        f"<link>{xml_escape(site_url)}/</link>",
        "<description>New versions of the Registers of Interests dataset.</description>",
        "<language>en-au</language>",
        f"<lastBuildDate>{date}</lastBuildDate>" if date else "",
        *items,
        "</channel>",
        "</rss>",
    ]
    return "\n".join(x for x in lines if x) + "\n"
