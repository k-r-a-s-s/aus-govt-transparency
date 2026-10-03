"""AC-B5: static SVG charts. Every page type's SVG has ``<title>`` and ``<desc>``, colours
come only from classes and ``currentColor``, and the SVGs are byte-identical across builds."""
from __future__ import annotations

import re

import pytest
from html_tree import parse_file
from web_support import MINI_DB, MINI_MANIFEST

from disclosures.web import charts as C
from disclosures.web.build import build

ALLOWED_CLASSES = {"chart", "chart-legend", "chart-label", "chart-value", "chart-tick",
                   "chart-grid", "chart-axis", "bloc-labor", "bloc-coalition",
                   "bloc-crossbench", "bloc-unknown", "seq-1", "seq-2", "seq-3", "seq-4"}
SVG_RE = re.compile(r"<svg\b.*?</svg>", re.S)

PAGE_TYPES = {  # page type -> (rel path, number of charts)
    "overview": ("index.html", 4),
    "member": ("members/wayne_swan/index.html", 1),
    "entity": ("entities/qantas_airways/index.html", 1),
    "section": ("sections/1/index.html", 1),
    "parliament": ("parliaments/house-47/index.html", 1),
}


def svgs(path):
    return SVG_RE.findall(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("kind", sorted(PAGE_TYPES))
def test_svg_title_desc_and_colour_rules(mini_site, kind):
    rel, n = PAGE_TYPES[kind]
    found = svgs(mini_site / rel)
    assert len(found) == n
    doc = parse_file(mini_site / rel)
    for svg in doc.find_all("svg"):
        kids = [c for c in svg.children if not isinstance(c, str)]
        assert [k.tag for k in kids[:2]] == ["title", "desc"], kind
        assert kids[0].text and len(kids[1].text) > 20
        assert svg.attrs["role"] == "img"
        ids = svg.attrs["aria-labelledby"].split()
        assert ids == [kids[0].attrs["id"], kids[1].attrs["id"]]
        for el in [svg, *svg.iter()]:
            fill = el.attrs.get("fill")
            assert fill in (None, "currentColor"), (kind, el.tag, fill)
            assert "stroke" not in el.attrs, (kind, el.tag)
            assert "style" not in el.attrs, (kind, el.tag)
            assert set(el.classes) <= ALLOWED_CLASSES, (kind, el.classes)
            if el.tag in ("path", "rect"):
                assert el.classes, (kind, "unclassed mark")
    for raw in found:
        assert not re.search(r"(fill|stroke)\s*[=:]\s*[\"']?#", raw), kind
        assert not re.search(r"#[0-9a-fA-F]{3,6}\b", raw), kind


def test_bloc_marks_use_bloc_classes(mini_site):
    raw = svgs(mini_site / "index.html")[0]
    for cls in ("bloc-labor", "bloc-coalition", "bloc-crossbench"):
        assert f'class="{cls}"' in raw
    assert "Labor" in raw and "Coalition" in raw and "Crossbench" in raw  # legend


def test_single_series_has_no_legend(mini_site):
    raw = svgs(mini_site / "members" / "wayne_swan" / "index.html")[0]
    assert "chart-legend" not in raw and 'class="seq-3"' in raw


def test_svgs_byte_identical_across_builds(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    build(MINI_DB, MINI_MANIFEST, a)
    build(MINI_DB, MINI_MANIFEST, b)
    n = 0
    for p in sorted(a.rglob("*.html")):
        q = b / p.relative_to(a)
        assert svgs(p) == svgs(q), p
        assert p.read_bytes() == q.read_bytes(), p
        n += len(svgs(p))
    assert n > 100


def test_nice_ticks():
    assert C.nice_ticks(0) == [0.0, 1.0]
    assert C.nice_ticks(142) == [0, 50, 100, 150]
    assert C.nice_ticks(196) == [0, 50, 100, 150, 200]
    assert C.nice_ticks(9) == [0, 5, 10] or C.nice_ticks(9)[-1] >= 9
    for v in (1, 7, 13, 99, 1234, 49.2):
        t = C.nice_ticks(v)
        assert t[0] == 0 and t[-1] >= v and len(t) <= 6


def test_chart_function_is_pure():
    rows = [("A", [3, 2, 1]), ("B very long label " * 6, [0, 5, 0])]
    one = C.stacked("x", "T", "Lead.", rows, C.BLOC_SERIES)
    two = C.stacked("x", "T", "Lead.", rows, C.BLOC_SERIES)
    assert one == two
    assert "..." in one  # long labels shortened
    assert one.count('<path class="') == 4  # zero segments are not drawn
