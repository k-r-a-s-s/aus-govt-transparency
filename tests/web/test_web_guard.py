"""AC-B11: the build renders only DB columns and manifest URLs (no other data source in the
templates or the page code), and no secret-like string reaches the built site."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
from web_support import REPO

import disclosures.web as W

PKG = Path(W.__file__).parent
TEMPLATES = sorted((PKG / "templates").glob("*.html"))

# Network or script hooks that could pull data from somewhere other than the build.
TEMPLATE_SOURCES = re.compile(
    r"src=\"(https?:)?//|<iframe|<object|<embed|\bfetch\(|XMLHttpRequest|\bimport\(|"
    r"\{%\s*include\s+\"(?!_)", re.I)
# Every name a template may read: what pages.Renderer passes to render(). Anything else
# (a global, a filter that reads files) would be another data source.
CONTEXT_NAMES = {"site", "page", "m", "s", "charts", "coverage_rows", "section_head",
                 "section_rows", "top_rows", "owner_head", "owner_rows", "alt_rows", "rows",
                 "mem", "terms", "statements", "n_items", "groups", "chart", "alterations",
                 "n_singletons", "ent", "variants", "aliases", "by_reg_head", "by_reg_rows",
                 "member_rows", "sec", "head", "others", "reg", "downloads",
                 "downloads_known", "manifest_href", "datapackage_href", "datasette_href",
                 "kaggle_href", "db_note", "columns", "api_routes", "example_member",
                 "bundle_version", "attribution", "method", "limitations", "prompts",
                 "accuracy_rows", "labels", "changelog", "explorer"}
PY_SOURCES = re.compile(r"^\s*(import|from)\s+(urllib\.request|http\.client|socket|requests|"
                        r"httpx|subprocess|os\.environ)\b|\bos\.environ\b|\burlopen\(",
                        re.M)


def test_templates_have_no_other_data_source():
    from jinja2 import Environment, meta

    assert TEMPLATES
    hits = {p.name: TEMPLATE_SOURCES.findall(p.read_text()) for p in TEMPLATES}
    assert {k: v for k, v in hits.items() if v} == {}
    env = Environment()
    env.filters["num"] = str  # the build's only custom filter (pages.fmt)
    for p in TEMPLATES:
        ast = env.parse(p.read_text())
        names = meta.find_undeclared_variables(ast)
        assert names <= CONTEXT_NAMES, (p.name, names - CONTEXT_NAMES)
        refs = set(meta.find_referenced_templates(ast))
        assert refs <= {"base.html", "_macros.html"}, (p.name, refs)


def test_page_code_has_no_network_or_environment_access():
    for name in ("pages.py", "charts.py", "metadata.py", "bundle.py", "dataset.py", "urls.py"):
        text = (PKG / name).read_text()
        assert PY_SOURCES.findall(text) == [], name


def test_pages_read_only_dataset_and_export():
    """pages.py takes its data from Dataset (DB + manifest) and export's fixed prose."""
    text = (PKG / "pages.py").read_text()
    imports = set(re.findall(r"^from (\S+) import", text, re.M)) | \
        set(re.findall(r"^import (\S+)", text, re.M))
    assert imports <= {"__future__", "json", "re", "collections", "dataclasses", "html",
                       "pathlib", "typing", "jinja2", "markupsafe", "..", ".", ".bundle",
                       ".dataset"}


def _patterns():
    path = REPO / "scripts" / "check_sensitive_info.py"
    try:
        spec = importlib.util.spec_from_file_location("check_sensitive_info", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return [(re.compile(p), label) for p, label in mod.SENSITIVE_PATTERNS]
    except Exception:  # pragma: no cover - fallback when the script is absent
        return [(re.compile(p), label) for p, label in [
            (r"AIza[A-Za-z0-9_-]{35}", "Google API Key"), (r"AKIA[A-Z0-9]{16}", "AWS key"),
            (r"-----BEGIN (RSA|DSA|EC|OPENSSH) PRIVATE KEY-----", "Private Key"),
            (r"sk-[A-Za-z0-9]{20,}", "API key"), (r"sk-or-v1-[0-9a-f]{20,}", "OpenRouter")]]


EXTRA = [(re.compile(r"sk-or-v1-[0-9a-f]{20,}"), "OpenRouter key"),
         (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "Anthropic key"),
         (re.compile(r"CLOUDFLARE_API_TOKEN\s*=\s*\S"), "Cloudflare token")]


def _combined(pats):
    """One alternation of every pattern (scoped ``(?i:...)`` instead of a leading ``(?i)``),
    so each file is searched once; the label is found only on a hit."""
    parts = []
    for rx, _ in pats:
        src = rx.pattern
        parts.append(f"(?i:{src[4:]})" if src.startswith("(?i)") else f"(?:{src})")
    return re.compile("|".join(parts))


def scan(site: Path):
    pats = _patterns() + EXTRA
    big = _combined(pats)
    hits = []
    for p in sorted(site.rglob("*")):
        if not p.is_file() or p.suffix in (".woff2",):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if not big.search(text):
            continue
        for rx, label in pats:
            m = rx.search(text)
            if m:
                hits.append((p.relative_to(site).as_posix(), label, m.group(0)[:40]))
    return hits


def test_sensitive_patterns_imported_from_script():
    assert len(_patterns()) >= 10  # the script's list, not the fallback


def test_no_secrets_in_mini_site(mini_site):
    assert scan(mini_site) == []


def test_scan_catches_a_planted_key(site_copy):
    (site_copy / "index.html").write_text('<p>key = "AIza' + "x" * 35 + '"</p>')
    assert [h[1] for h in scan(site_copy)][:1] in (["API Key"], ["Google API Key"])


def test_no_secrets_in_real_site(real_site):
    assert scan(real_site) == []
