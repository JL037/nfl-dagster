"""Charts as inline SVG, drawn from a query's own rows: the model only picks the kind and the
columns (agent.valid_chart checks they exist), so a chart can't show a number no query returned.

Drawn on the server: no chart library, no CDN, and vector output that prints sharply (the PDF).
The marks follow the dataviz rules: one hue for a single series, blue/red only for values above
and below zero, at most three series (each in a fixed categorical slot), thin marks with 4px
rounded data-ends, hairline grids, one axis, sparing labels, a legend only for two or more
series, and a <title> tooltip on every mark. Colors are CSS variables (style.css), so the
same SVG follows light and dark mode and prints in light.
"""

import math
from html import escape

from nfl_ask.query import QueryResult
from nfl_ask.web.present import column_label, format_value

WIDTH = 680
MAX_SERIES = 3  # the categorical slots that stay distinguishable for everyone, in every form
CHAR = 6.6  # average label width per character at 12px, for sizing the margin


def nice_ticks(lo: float, hi: float, count: int = 4) -> list[float]:
    if lo == hi:
        lo, hi = (lo - 1, hi + 1) if lo == 0 else (lo - abs(lo) * 0.1, hi + abs(hi) * 0.1)
    raw = (hi - lo) / count
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    start = math.floor(lo / step) * step
    ticks, t = [], start
    while t <= hi + step * 0.5:
        ticks.append(round(t, 10))
        t += step
    return ticks


def tick_label(column: str, tick: float, ticks: list[float]) -> str:
    """A tick with only the decimals its step needs: 0, 0.1, 0.2 (not 0.000, 0.100)."""
    step = abs(ticks[1] - ticks[0]) if len(ticks) > 1 else 1
    text = f"{step:.10f}".rstrip("0")
    decimals = len(text.split(".")[1]) if "." in text else 0
    return format_value(column, tick, decimals=decimals)


def scale(lo, hi, a, b):
    span = (hi - lo) or 1
    return lambda v: a + (v - lo) / span * (b - a)


def text(x, y, content, cls="tick", anchor="start", dy="0.32em"):
    return f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" dy="{dy}" text-anchor="{anchor}">{escape(str(content))}</text>'


def rounded_bar(x0, x1, y, h, r=4.0):
    """A horizontal bar square at the baseline (x0) with a rounded data-end (x1)."""
    r = min(r, abs(x1 - x0), h / 2)
    if x1 >= x0:
        return (f"M{x0:.1f},{y:.1f} H{x1 - r:.1f} Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f} "
                f"V{y + h - r:.1f} Q{x1:.1f},{y + h:.1f} {x1 - r:.1f},{y + h:.1f} H{x0:.1f} Z")
    return (f"M{x0:.1f},{y:.1f} H{x1 + r:.1f} Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f} "
            f"V{y + h - r:.1f} Q{x1:.1f},{y + h:.1f} {x1 + r:.1f},{y + h:.1f} H{x0:.1f} Z")


def frame(title: str, height: float, body: list[str]) -> str:
    return (f'<svg class="chart" viewBox="0 0 {WIDTH} {height:.0f}" role="img" aria-label="{escape(title)}" '
            f'xmlns="http://www.w3.org/2000/svg"><title>{escape(title)}</title>{"".join(body)}</svg>')


def bar_chart(chart, result: QueryResult) -> str | None:
    xi, yi = result.columns.index(chart["x"]), result.columns.index(chart["y"])
    rows = [(str(row[xi]), row[yi]) for row in result.rows if row[yi] is not None]
    if not rows:
        return None
    values = [v for _, v in rows]
    ticks = nice_ticks(min(0, min(values)), max(0, max(values)))
    left = min(220, 12 + CHAR * max(len(name) for name, _ in rows))
    right, row_h, bar_h, top = 64, 28, 16, 8
    height = top + row_h * len(rows) + 30
    x = scale(ticks[0], ticks[-1], left, WIDTH - right)
    zero = x(0)
    body = []
    for t in ticks:  # hairline grid, then the baseline at zero
        body.append(f'<line class="grid" x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{top}" y2="{height - 26}"/>')
        body.append(text(x(t), height - 12, tick_label(chart["y"], t, ticks), anchor="middle"))
    body.append(f'<line class="axis" x1="{zero:.1f}" x2="{zero:.1f}" y1="{top}" y2="{height - 26}"/>')
    for i, (name, value) in enumerate(rows):
        y = top + i * row_h + (row_h - bar_h) / 2
        sign = "neg" if value < 0 else "pos"
        shown = format_value(chart["y"], value)
        body.append(f'<path class="bar {sign}" d="{rounded_bar(zero, x(value), y, bar_h)}">'
                    f"<title>{escape(name)}: {escape(shown)}</title></path>")
        body.append(text(left - 8, y + bar_h / 2, name, cls="label", anchor="end"))
        tip = x(value) + (6 if value >= 0 else -6)
        body.append(text(tip, y + bar_h / 2, shown, cls="value", anchor="start" if value >= 0 else "end"))
    return frame(chart["title"], height, body)


def series_of(chart, result: QueryResult) -> dict[str, list[tuple]] | None:
    xi, yi = result.columns.index(chart["x"]), result.columns.index(chart["y"])
    si = result.columns.index(chart["series"]) if chart.get("series") else None
    groups: dict[str, list[tuple]] = {}
    for row in result.rows:
        if row[yi] is None or not isinstance(row[xi], (int, float)):
            continue
        groups.setdefault(str(row[si]) if si is not None else "", []).append((row[xi], row[yi], row))
    if not groups or len(groups) > MAX_SERIES:
        return None
    return groups


def legend(names: list[str], mark: str) -> list[str]:
    if len(names) < 2:
        return []  # a single series is named by the title
    items, cx = [], 56
    for i, name in enumerate(names):
        key = (f'<line class="key s{i + 1}" x1="{cx}" x2="{cx + 16}" y1="10" y2="10"/>' if mark == "line"
               else f'<circle class="key s{i + 1}" cx="{cx + 6}" cy="10" r="4.5"/>')
        items.append(key + text(cx + 22, 10, name, cls="label"))
        cx += 22 + CHAR * len(name) + 22
    return [f'<g class="legend">{"".join(items)}</g>']


def xy_axes(chart, xs, ys, top, height, right, x_ticks=None):
    left, bottom = 64, height - 40
    xt = x_ticks or nice_ticks(min(xs), max(xs))
    yt = nice_ticks(min(ys), max(ys))
    x = scale(xt[0], xt[-1], left, WIDTH - right)
    y = scale(yt[0], yt[-1], bottom, top)
    body = []
    for t in yt:
        cls = "axis" if t == 0 else "grid"
        body.append(f'<line class="{cls}" x1="{left}" x2="{WIDTH - right}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>')
        body.append(text(left - 8, y(t), tick_label(chart["y"], t, yt), anchor="end"))
    for t in xt:
        body.append(text(x(t), bottom + 16, tick_label(chart["x"], t, xt), anchor="middle"))
    body.append(text((left + WIDTH - right) / 2, height - 6, column_label(chart["x"]), cls="axis-title", anchor="middle", dy="0"))
    body.append(text(12, top - 18, column_label(chart["y"]), cls="axis-title", dy="0"))
    return x, y, body


def point_name(result: QueryResult, row) -> str:
    """What a point is, for its tooltip: the row's first text column (a player or team), plus season."""
    name = next((v for c, v in zip(result.columns, row) if isinstance(v, str) and not c.endswith(("_key", "_id"))), "")
    season = dict(zip(result.columns, row)).get("season")
    return f"{name} {season}".strip() if season is not None and name else str(name or season or "")


def line_chart(chart, result: QueryResult) -> str | None:
    groups = series_of(chart, result)
    if not groups:
        return None
    points = [p for g in groups.values() for p in g]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    distinct = sorted(set(xs))
    top, height = 60, 316
    x, y, body = xy_axes(chart, xs, ys, top, height, right=24,
                         x_ticks=distinct if len(distinct) <= 12 and all(isinstance(v, int) for v in distinct) else None)
    names = list(groups)
    for i, name in enumerate(names):
        pts = sorted(groups[name], key=lambda p: p[0])
        d = " ".join(f"{'M' if j == 0 else 'L'}{x(px):.1f},{y(py):.1f}" for j, (px, py, _) in enumerate(pts))
        body.append(f'<path class="line s{i + 1}" d="{d}"/>')
        for px, py, _ in pts:
            label = f"{name + ' · ' if name else ''}{format_value(chart['x'], px)}: {format_value(chart['y'], py)}"
            body.append(f'<circle class="dot s{i + 1}" cx="{x(px):.1f}" cy="{y(py):.1f}" r="4"><title>{escape(label)}</title></circle>')
    return frame(chart["title"], height, legend(names, "line") + body)


def scatter_chart(chart, result: QueryResult) -> str | None:
    groups = series_of(chart, result)
    if not groups:
        return None
    points = [p for g in groups.values() for p in g]
    top, height = 60, 356
    x, y, body = xy_axes(chart, [p[0] for p in points], [p[1] for p in points], top, height, right=24)
    names = list(groups)
    for i, name in enumerate(names):
        for px, py, row in groups[name]:
            label = f"{point_name(result, row)}: {column_label(chart['x'])} {format_value(chart['x'], px)}, {column_label(chart['y'])} {format_value(chart['y'], py)}"
            body.append(f'<circle class="dot s{i + 1}" cx="{x(px):.1f}" cy="{y(py):.1f}" r="4.5"><title>{escape(label)}</title></circle>')
    # Label sparingly: just the highest and lowest points.
    best, worst = max(points, key=lambda p: p[1]), min(points, key=lambda p: p[1])
    for px, py, row in {id(best): best, id(worst): worst}.values():
        body.append(text(x(px) + 8, y(py), point_name(result, row), cls="label"))
    return frame(chart["title"], height, legend(names, "dot") + body)


DRAW = {"bar": bar_chart, "line": line_chart, "scatter": scatter_chart}


def render_chart(chart: dict | None, result: QueryResult | None) -> str | None:
    if not chart or result is None or chart.get("kind") not in DRAW:
        return None
    return DRAW[chart["kind"]](chart, result)
