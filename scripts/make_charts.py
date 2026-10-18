"""Draw the README charts from the marts, in light and dark versions.

    NFL_ENV=prod python scripts/make_charts.py     # reads NFL.MARTS (default env: dev)

Writes PNGs to docs/images/. The README shows the light or dark one to match the reader's
GitHub theme. Each chart has a single series, so there's no legend: the title says what's
plotted. The numbers are also in the README's tables.
"""

import os
from pathlib import Path

import dagster as dg
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath

from nfl_dagster.resources import REPO_ROOT, SNOWFLAKE_DATABASE, snowflake_resource

OUT = REPO_ROOT / "docs" / "images"
LAST_FULL_SEASON = 2025

THEMES = {
    "light": {
        "surface": "#fcfcfb", "text": "#0b0b0b", "secondary": "#52514e",
        "muted": "#898781", "grid": "#e1e0d9", "series": "#2a78d6",
    },
    "dark": {
        "surface": "#1a1a19", "text": "#ffffff", "secondary": "#c3c2b7",
        "muted": "#898781", "grid": "#2c2c2a", "series": "#3987e5",
    },
}

FOURTH_DOWN_SQL = f"""
    select season, round(100 * sum(went_for_it) / sum(fourth_downs), 1)
    from {SNOWFLAKE_DATABASE}.marts.team_fourth_down
    where season <= %s
    group by season order by season
"""

QB_SQL = f"""
    select passer_name, team, epa_per_dropback, dropbacks
    from {SNOWFLAKE_DATABASE}.marts.qb_season_epa
    where season = %s
    order by epa_per_dropback desc
    limit 10
"""

CONTRACT_VALUE_SQL = f"""
    select passer_name, cap_share, epa_per_dropback, expected_epa_per_dropback
    from {SNOWFLAKE_DATABASE}.marts.qb_contract_value
    where season = %s and is_cap_hit_for_team
    order by cap_share
"""

# Direct labels for the QBs that tell the story, not every dot: the best values, paid and
# producing, the most expensive, and the worst values. Offsets (points) keep labels clear
# of neighbouring dots.
CONTRACT_VALUE_LABELS = {
    "D.Maye": (8, 6),
    "B.Purdy": (8, -4),
    "J.Love": (-10, 8),
    "M.Stafford": (-14, 8),
    "D.Prescott": (8, 0),
    "G.Smith": (-10, -14),
    "S.Sanders": (8, 4),
}


def query(sql: str, params: tuple = ()) -> list[tuple]:
    # Values go in as bound parameters (%s), never into the SQL text; only the database
    # name, an identifier that can't be bound, is interpolated above.
    with dg.build_resources({"snowflake": snowflake_resource}) as r:
        with r.snowflake.get_connection() as conn:
            return conn.cursor().execute(sql, params).fetchall()


def style_axes(ax, t: dict, grid_axis: str) -> None:
    ax.set_facecolor(t["surface"])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(t["grid"])
    ax.spines["bottom"].set_linewidth(1)
    ax.tick_params(colors=t["secondary"], labelsize=10, length=0)
    ax.grid(axis=grid_axis, color=t["grid"], linewidth=1, linestyle="-")
    ax.set_axisbelow(True)


def titles(fig, t: dict, title: str, subtitle: str, source: str) -> None:
    fig.text(0.04, 0.95, title, color=t["text"], fontsize=15, fontweight="bold", va="top")
    fig.text(0.04, 0.885, subtitle, color=t["secondary"], fontsize=10.5, va="top")
    fig.text(0.04, 0.025, source, color=t["muted"], fontsize=8.5, va="bottom")


def fourth_down_chart(rows: list[tuple], t: dict, path: Path) -> None:
    seasons = [int(s) for s, _ in rows]
    rates = [float(r) for _, r in rows]

    fig, ax = plt.subplots(figsize=(8, 4.4), dpi=200)
    fig.patch.set_facecolor(t["surface"])
    fig.subplots_adjust(left=0.08, right=0.95, top=0.78, bottom=0.14)
    style_axes(ax, t, "y")

    ax.fill_between(seasons, rates, color=t["series"], alpha=0.10, linewidth=0)
    ax.plot(seasons, rates, color=t["series"], linewidth=2, solid_capstyle="round", solid_joinstyle="round")
    # End markers with a ring in the surface color, plus direct labels at both ends.
    ax.scatter([seasons[0], seasons[-1]], [rates[0], rates[-1]], s=70, color=t["series"],
               edgecolors=t["surface"], linewidths=2, zorder=3)
    ax.annotate(f"{rates[0]:.1f}%", (seasons[0], rates[0]), xytext=(0, 10), textcoords="offset points",
                ha="center", color=t["text"], fontsize=11, fontweight="bold")
    ax.annotate(f"{rates[-1]:.1f}%", (seasons[-1], rates[-1]), xytext=(0, 10), textcoords="offset points",
                ha="center", color=t["text"], fontsize=11, fontweight="bold")

    ax.set_ylim(0, 75)
    ax.set_yticks([0, 25, 50, 75])
    ax.set_yticklabels(["0%", "25%", "50%", "75%"])
    ax.set_xlim(seasons[0] - 0.5, seasons[-1] + 0.5)
    ax.set_xticks(seasons)
    ax.set_xticklabels([str(s) if s % 2 else "" for s in seasons])

    titles(
        fig, t,
        "The fourth-down revolution",
        "How often NFL teams went for it on 4th-and-2 or less in competitive games (win probability 10–90%)",
        f"Regular season, {seasons[0]}–{seasons[-1]}. Source: nflverse play-by-play, mart team_fourth_down.",
    )
    fig.savefig(path, facecolor=t["surface"])
    plt.close(fig)


def bar_path(x0: float, y_center: float, length: float, height: float, rx: float, ry: float) -> MplPath:
    """A horizontal bar: square at the baseline (x0), rounded corners at the data end.

    rx and ry are the same on-screen radius expressed in x and y data units, which differ
    because the two axes have different scales.
    """
    y0, y1 = y_center - height / 2, y_center + height / 2
    x1 = x0 + length
    rx, ry = min(rx, length / 2), min(ry, height / 2)
    verts = [
        (x0, y0), (x1 - rx, y0), (x1, y0), (x1, y0 + ry),
        (x1, y1 - ry), (x1, y1), (x1 - rx, y1), (x0, y1), (x0, y0),
    ]
    codes = [
        MplPath.MOVETO, MplPath.LINETO, MplPath.CURVE3, MplPath.CURVE3,
        MplPath.LINETO, MplPath.CURVE3, MplPath.CURVE3, MplPath.LINETO, MplPath.CLOSEPOLY,
    ]
    return MplPath(verts, codes)


def qb_chart(rows: list[tuple], t: dict, path: Path) -> None:
    rows = list(reversed(rows))  # best at the top
    labels = [f"{name}  ({team})" for name, team, _, _ in rows]
    values = [float(v) for _, _, v, _ in rows]

    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=200)
    fig.patch.set_facecolor(t["surface"])
    fig.subplots_adjust(left=0.24, right=0.93, top=0.79, bottom=0.12)
    style_axes(ax, t, "x")

    x_max = 0.40
    bar_height = 0.55  # in band units; leaves air between bars
    # 4 CSS px of rounding at the data end (8 image px at this 2x resolution), in data units.
    radius_px = 4 * fig.dpi / 100
    pos = ax.get_position()
    rx = radius_px * x_max / (pos.width * fig.get_size_inches()[0] * fig.dpi)
    ry = radius_px * len(values) / (pos.height * fig.get_size_inches()[1] * fig.dpi)
    for i, value in enumerate(values):
        ax.add_patch(PathPatch(bar_path(0, i, value, bar_height, rx, ry), facecolor=t["series"], linewidth=0))
        ax.text(value + x_max * 0.012, i, f"{value:.3f}", va="center", ha="left", color=t["text"], fontsize=9.5)

    ax.set_xlim(0, x_max)
    ax.set_ylim(-0.6, len(values) - 0.4)
    ax.set_yticks(range(len(values)))
    ax.set_yticklabels(labels, color=t["text"], fontsize=10)
    ax.set_xticks([0, 0.1, 0.2, 0.3, 0.4])
    ax.set_xticklabels(["0", "0.1", "0.2", "0.3", "0.4"])

    titles(
        fig, t,
        f"Best quarterbacks by EPA per dropback, {LAST_FULL_SEASON}",
        "Expected points added per pass attempt, sack, or scramble (minimum 200 dropbacks)",
        f"Regular season {LAST_FULL_SEASON}. Source: nflverse play-by-play, mart qb_season_epa.",
    )
    fig.savefig(path, facecolor=t["surface"])
    plt.close(fig)


def contract_value_chart(rows: list[tuple], t: dict, path: Path) -> None:
    names = [n for n, _, _, _ in rows]
    shares = [100 * float(c) for _, c, _, _ in rows]  # percent of the league cap
    epa = [float(e) for _, _, e, _ in rows]
    expected = [float(x) for _, _, _, x in rows]

    fig, ax = plt.subplots(figsize=(8, 5.2), dpi=200)
    fig.patch.set_facecolor(t["surface"])
    fig.subplots_adjust(left=0.1, right=0.95, top=0.79, bottom=0.16)
    style_axes(ax, t, "both")

    # The expected line: what QBs paid each share of the cap usually produce. Every row's
    # expected value sits on it, so the first and last rows (sorted by cap share) give it.
    x_max = 22  # room right of the most expensive QB for his label; ticks stop at 20%
    slope = (expected[-1] - expected[0]) / (shares[-1] - shares[0])
    line_x = [0, x_max]
    line_y = [expected[0] + slope * (x - shares[0]) for x in line_x]
    ax.plot(line_x, line_y, color=t["muted"], linewidth=1.5, zorder=1)
    # Label the line where it runs through empty space, below it, clear of the dots.
    label_x = 8
    ax.annotate("Expected for the money", (label_x, line_y[0] + slope * label_x), xytext=(0, -14),
                textcoords="offset points", ha="center", color=t["secondary"], fontsize=9)

    ax.scatter(shares, epa, s=55, color=t["series"], edgecolors=t["surface"], linewidths=1.5, zorder=3)
    for name, x, y in zip(names, shares, epa):
        if name in CONTRACT_VALUE_LABELS:
            dx, dy = CONTRACT_VALUE_LABELS[name]
            ax.annotate(name, (x, y), xytext=(dx, dy), textcoords="offset points",
                        ha="left" if dx >= 0 else "right", va="center",
                        color=t["text"], fontsize=9.5, fontweight="bold")

    ax.set_xlim(0, x_max)
    ax.set_xticks([0, 5, 10, 15, 20])
    ax.set_xticklabels(["0%", "5%", "10%", "15%", "20%"])
    ax.set_xlabel("Cap hit as a share of the league salary cap", color=t["secondary"], fontsize=10)
    ax.set_ylim(-0.3, 0.4)
    ax.set_yticks([-0.2, 0, 0.2, 0.4])
    ax.set_yticklabels(["-0.2", "0", "0.2", "0.4"])

    titles(
        fig, t,
        f"Which quarterbacks were worth the money, {LAST_FULL_SEASON}",
        "EPA per dropback against share of the cap. Above the line: better than QBs paid the same usually play",
        f"Regular season {LAST_FULL_SEASON}, {len(rows)} QBs; line fitted on 2015–{LAST_FULL_SEASON}. "
        "Source: nflverse, OverTheCap; mart qb_contract_value.",
    )
    fig.savefig(path, facecolor=t["surface"])
    plt.close(fig)


def main() -> None:
    load_dotenv()
    OUT.mkdir(parents=True, exist_ok=True)
    fourth_down = query(FOURTH_DOWN_SQL, (LAST_FULL_SEASON,))
    qbs = query(QB_SQL, (LAST_FULL_SEASON,))
    contract_value = query(CONTRACT_VALUE_SQL, (LAST_FULL_SEASON,))
    plt.rcParams["font.family"] = "DejaVu Sans"
    for mode, t in THEMES.items():
        fourth_down_chart(fourth_down, t, OUT / f"fourth_down_trend-{mode}.png")
        qb_chart(qbs, t, OUT / f"qb_epa_{LAST_FULL_SEASON}-{mode}.png")
        contract_value_chart(contract_value, t, OUT / f"qb_contract_value_{LAST_FULL_SEASON}-{mode}.png")
    print(f"Wrote charts from {SNOWFLAKE_DATABASE} (NFL_ENV={os.getenv('NFL_ENV', 'dev')}) to {OUT}")


if __name__ == "__main__":
    main()
