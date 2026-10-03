"""Static SVG charts for the public site (ADR-W10, AC-B5).

Every chart is a horizontal bar chart (stacked when it has more than one series), drawn as an
inline ``<svg>`` with ``<title>`` and ``<desc>``. Colour comes only from CSS classes
(``bloc-labor``, ``bloc-coalition``, ``bloc-crossbench``, ``seq-1`` to ``seq-4``) and
``currentColor``, so one SVG serves the light and dark themes. There is no hard-coded fill
colour, no random id and no timestamp, so the same data gives the same bytes on every build.

Layout follows DESIGN.md: one value axis at the bottom with a recessive grid, the row label
above each bar (so labels stay readable at 375px), bars 12 units thick with a 4 unit rounded
data end, a 2 unit paper gap between stacked segments, a legend when there are two or more
series, and a direct label with the row total at the end of each bar.
"""
from __future__ import annotations

import math
from html import escape
from typing import Callable, List, Optional, Sequence, Tuple

WIDTH = 400          # viewBox width; the CSS scales the SVG to its column
LABEL_H = 15         # label line (font 12) above each bar
BAR_H = 12
ROW_GAP = 9
GAP = 2              # paper gap between stacked segments
RADIUS = 4           # rounded data end
VALUE_ROOM = 64      # space right of the longest bar for its total
LEGEND_ROW = 20
AXIS_H = 22
MAX_LABEL = 52       # characters before a row label is shortened

BLOC_SERIES = [("Labor", "Labor", "bloc-labor"), ("Coalition", "Coalition", "bloc-coalition"),
               ("Crossbench", "Crossbench", "bloc-crossbench")]
UNKNOWN_BLOC_SERIES = ("Unknown", "Bloc not recorded", "bloc-unknown")
OWNER_SERIES = [("self", "Self", "seq-4"), ("spouse", "Spouse or partner", "seq-3"),
                ("dependent_child", "Dependent child", "seq-2"),
                ("unknown", "Owner not stated", "seq-1")]
SINGLE_CLASS = "seq-3"

Series = Tuple[str, str, str]          # (key, legend label, css class)
Row = Tuple[str, Sequence[float]]      # (row label, one value per series)


def fmt_int(v: float) -> str:
    return f"{int(round(v)):,}"


def fmt_pct(v: float) -> str:
    return f"{v:.1f}%"


def tick_label(v: float, fmt: Callable[[float], str]) -> str:
    """Axis ticks are round numbers: drop the decimals a value format would add."""
    if fmt is fmt_pct:
        return f"{v:g}%"
    return fmt(v)


def _n(x: float) -> str:
    """A coordinate with at most 2 decimals and no trailing zeros (stable text)."""
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def nice_ticks(vmax: float, n: int = 4) -> List[float]:
    """0 and evenly spaced 1/2/5 x 10^k steps up to at least ``vmax``."""
    if vmax <= 0:
        return [0.0, 1.0]
    raw = vmax / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw)
    top = step * math.ceil(vmax / step - 1e-9)
    k = int(round(top / step))
    return [step * i for i in range(k + 1)]


def _short(label: str) -> str:
    return label if len(label) <= MAX_LABEL else label[:MAX_LABEL - 3].rstrip() + "..."


def _bar_path(x: float, y: float, w: float, h: float, round_end: bool) -> str:
    if not round_end or w <= 0.5:
        return f"M{_n(x)} {_n(y)}h{_n(w)}v{_n(h)}h{_n(-w)}z"
    r = min(RADIUS, w, h / 2)
    return (f"M{_n(x)} {_n(y)}h{_n(w - r)}a{_n(r)} {_n(r)} 0 0 1 {_n(r)} {_n(r)}"
            f"v{_n(h - 2 * r)}a{_n(r)} {_n(r)} 0 0 1 {_n(-r)} {_n(r)}h{_n(-(w - r))}z")


def _legend(series: Sequence[Series]) -> Tuple[List[str], float]:
    """Swatch + label per series, wrapped to the chart width. Returns (svg parts, height)."""
    parts, x, y = [], 0.0, 0.0
    for _, label, cls in series:
        w = 12 + 6 + 7.2 * len(label) + 16
        if x and x + w > WIDTH:
            x, y = 0.0, y + LEGEND_ROW
        parts.append(f'<rect class="{cls}" x="{_n(x)}" y="{_n(y + 2)}" width="10" height="10" '
                     f'rx="2"/>')
        parts.append(f'<text x="{_n(x + 16)}" y="{_n(y + 11)}">{escape(label)}</text>')
        x += w
    return parts, y + LEGEND_ROW + 6


def bar_chart(chart_id: str, title: str, desc: str, rows: Sequence[Row],
              series: Sequence[Series], fmt: Callable[[float], str] = fmt_int,
              axis_max: Optional[float] = None) -> str:
    """A horizontal (stacked) bar chart as an SVG string. ``chart_id`` must be unique on the
    page; it prefixes the ids of ``<title>`` and ``<desc>``."""
    multi = len(series) > 1
    parts: List[str] = []
    top = 0.0
    if multi:
        legend, top = _legend(series)
        parts.append('<g class="chart-legend">' + "".join(legend) + "</g>")
    totals = [sum(v for v in vals) for _, vals in rows]
    vmax = max(totals, default=0)
    ticks = nice_ticks(axis_max if axis_max is not None else vmax)
    scale_max = ticks[-1]
    plot_w = WIDTH - VALUE_ROOM
    row_h = LABEL_H + BAR_H + ROW_GAP
    plot_h = row_h * len(rows)

    def sx(v: float) -> float:
        return plot_w * v / scale_max if scale_max else 0.0

    # grid and the one value axis
    grid = []
    for t in ticks:
        gx = sx(t)
        grid.append(f'<line class="chart-grid" x1="{_n(gx)}" x2="{_n(gx)}" y1="{_n(top)}" '
                    f'y2="{_n(top + plot_h)}"/>')
    parts.append('<g aria-hidden="true">' + "".join(grid) + "</g>")

    body = []
    for i, ((label, vals), total) in enumerate(zip(rows, totals)):
        y = top + i * row_h
        body.append(f'<text class="chart-label" x="0" y="{_n(y + 11)}">{escape(_short(label))}'
                    f"</text>")
        by = y + LABEL_H
        x0 = 0.0
        drawn = [(k, v) for k, v in enumerate(vals) if v > 0]
        for j, (k, v) in enumerate(drawn):
            x1 = x0 + sx(v)
            start = x0 + (GAP if j else 0.0)
            w = x1 - start
            if w > 0.5:
                key, slabel, cls = series[k]
                tip = f"{label}: {slabel} {fmt(v)}" if multi else f"{label}: {fmt(v)}"
                body.append(f'<path class="{cls}" d="{_bar_path(start, by, w, BAR_H, j == len(drawn) - 1)}">'
                            f"<title>{escape(tip)}</title></path>")
            x0 = x1
        body.append(f'<text class="chart-value" x="{_n(sx(total) + 4)}" y="{_n(by + 10)}">'
                    f"{escape(fmt(total))}</text>")
    parts.append("".join(body))

    axis_y = top + plot_h
    axis = [f'<line class="chart-axis" x1="0" x2="{_n(plot_w)}" y1="{_n(axis_y)}" '
            f'y2="{_n(axis_y)}"/>']
    for t in ticks:
        anchor = "start" if t == ticks[0] else ("end" if t == ticks[-1] else "middle")
        axis.append(f'<text class="chart-tick" x="{_n(sx(t))}" y="{_n(axis_y + 15)}" '
                    f'text-anchor="{anchor}">{escape(tick_label(t, fmt))}</text>')
    parts.append('<g aria-hidden="true">' + "".join(axis) + "</g>")

    height = axis_y + AXIS_H
    tid, did = f"{chart_id}-title", f"{chart_id}-desc"
    return (f'<svg class="chart" id="{chart_id}" viewBox="0 0 {WIDTH} {_n(height)}" '
            f'role="img" aria-labelledby="{tid} {did}" fill="currentColor" '
            f'xmlns="http://www.w3.org/2000/svg">'
            f'<title id="{tid}">{escape(title)}</title><desc id="{did}">{escape(desc)}</desc>'
            + "".join(parts) + "</svg>")


def _row_summary(rows: Sequence[Row], fmt: Callable[[float], str]) -> str:
    return "; ".join(f"{label} {fmt(sum(vals))}" for label, vals in rows)


def bloc_series(present: Sequence[str]) -> List[Series]:
    """The three bloc series in fixed order, plus "Unknown" only when the data has it."""
    out = list(BLOC_SERIES)
    if "Unknown" in present:
        out.append(UNKNOWN_BLOC_SERIES)
    return out


def stacked(chart_id: str, title: str, lead: str, rows: Sequence[Row],
            series: Sequence[Series], fmt: Callable[[float], str] = fmt_int) -> str:
    totals = {}
    for _, vals in rows:
        for (key, label, _), v in zip(series, vals):
            totals[label] = totals.get(label, 0) + v
    split = ", ".join(f"{label} {fmt(v)}" for label, v in totals.items())
    desc = f"{lead} Totals by series: {split}. By row: {_row_summary(rows, fmt)}."
    return bar_chart(chart_id, title, desc, rows, series, fmt)


def single(chart_id: str, title: str, lead: str, rows: Sequence[Tuple[str, float]],
           fmt: Callable[[float], str] = fmt_int, axis_max: Optional[float] = None) -> str:
    rws = [(label, [v]) for label, v in rows]
    desc = f"{lead} {_row_summary(rws, fmt)}."
    return bar_chart(chart_id, title, desc, rws, [("value", "value", SINGLE_CLASS)], fmt,
                     axis_max)
