"""Turning query results into something people read: column names in English, numbers in the
form people expect (3.0%, $55.3M, 0.295), tables without internal keys, and each mart's
description from the dbt docs (the same source the model's catalog uses)."""

from collections.abc import Sequence
from functools import cache
from pathlib import Path

import yaml

from nfl_ask.catalog import MARTS_DIR, PROJECT_ROOT
from nfl_ask.query import QueryResult

LABELS = {
    "passer_name": "Quarterback", "team": "Team", "team_name": "Team", "season": "Season",
    "week": "Week", "gameday": "Date", "game_type": "Game type", "dropbacks": "Dropbacks",
    "epa_per_dropback": "EPA per dropback", "expected_epa_per_dropback": "Expected EPA per dropback",
    "epa_over_expected": "EPA over expected", "is_season_complete": "Season complete",
    "cap_number": "Cap hit", "cap_share": "Cap share", "is_cap_hit_for_team": "Cap hit is this team's",
    "worth_it": "Worth it", "success_rate": "Success rate", "scrambles": "Scrambles",
    "season_progress": "Season progress", "fourth_downs": "Fourth downs", "went_for_it": "Went for it",
    "go_pct": "Go-for-it rate", "converted": "Converted", "conversion_pct": "Conversion rate",
    "off_plays": "Offense plays", "off_epa_per_play": "Offense EPA per play",
    "off_success_rate": "Offense success rate", "def_plays": "Defense plays",
    "def_epa_per_play": "Defense EPA per play", "def_success_rate": "Defense success rate",
    "net_epa_per_play": "Net EPA per play", "team_conf": "Conference", "team_division": "Division",
    "away_team": "Away", "home_team": "Home", "away_score": "Away score", "home_score": "Home score",
    "result": "Home margin", "spread_line": "Spread", "home_cover_margin": "Home cover margin",
    "ats_winner": "Covered", "ats_result": "Result vs spread",
}
WORDS = {"epa": "EPA", "qb": "QB", "qbs": "QBs", "ats": "ATS", "id": "ID", "pct": "%", "avg": "Avg"}
YEARLIKE = {"season", "week", "year"}
MONEY = ("cap_number", "cap_hit", "salary", "apy")
MINUS = "−"  # a real minus sign: the hyphen reads as a dash in tables


MART_NAMES = {
    "qb_contract_value": "QB contract value", "qb_season_epa": "QB season EPA",
    "team_season_epa": "Team season EPA", "game_results_vs_spread": "Game results vs the spread",
    "team_fourth_down": "Team fourth-down decisions",
}


def mart_name(table: str) -> str:
    return MART_NAMES.get(table, column_label(table))


def column_label(column: str) -> str:
    if column in LABELS:
        return LABELS[column]
    words = [WORDS.get(w) or (w[:-3] + "%" if w.endswith("pct") and w[:-3].isdigit() else w)
             for w in column.split("_") if w]
    if words and words[0] == words[0].lower():
        words[0] = words[0].capitalize()
    return " ".join(words)


def is_percent(column: str) -> bool:
    return column.endswith(("_share", "_rate", "_pct")) or "pct" in column or column == "season_progress"


def format_value(column: str, value, decimals: int | None = None) -> str:
    """`decimals` overrides the default for plain decimals (axis ticks need only their step's)."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if not isinstance(value, (int, float)):
        return str(value)
    if is_percent(column):
        shown = f"{value * 100 if abs(value) <= 1 else value:.1f}%"
    elif any(word in column for word in MONEY):
        size = abs(value)
        shown = f"${value / 1e6:.1f}M" if size >= 1e6 else f"${value / 1e3:.0f}K" if size >= 1e3 else f"${value:,.0f}"
    elif column in YEARLIKE:
        shown = str(int(value))
    elif isinstance(value, int):
        shown = f"{value:,}"
    elif decimals is not None:
        shown = f"{value:,.{decimals}f}"
    elif abs(value) >= 100:
        shown = f"{value:,.0f}"
    elif abs(value) >= 10:
        shown = f"{value:,.1f}"
    else:
        shown = f"{value:.3f}"
    return shown.replace("-", MINUS, 1) if shown.startswith(("-", "$-")) else shown


def is_internal(column: str) -> bool:
    return column.endswith(("_key", "_id"))


def is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def data_table(result: QueryResult, max_rows: int = 25, first: Sequence[str] = ()) -> dict:
    """The rows behind an answer, ready for a table: readable headers and values, keys hidden,
    the charted columns first, and columns that are the same in every row moved to a note."""
    keep = [i for i, c in enumerate(result.columns) if not is_internal(c)] or list(range(len(result.columns)))
    keep.sort(key=lambda i: first.index(result.columns[i]) if result.columns[i] in first else len(first))
    constants = []
    if len(result.rows) > 1:
        for i in list(keep):
            values = {result.rows[0][i] == row[i] for row in result.rows}
            if values == {True} and result.columns[i] not in first and len(keep) > 1:
                constants.append((column_label(result.columns[i]), format_value(result.columns[i], result.rows[0][i])))
                keep.remove(i)
    columns = [result.columns[i] for i in keep]
    rows = [[format_value(result.columns[i], row[i]) for i in keep] for row in result.rows[:max_rows]]
    numeric = [all(is_number(row[i]) or row[i] is None for row in result.rows) for i in keep]
    return {
        "constants": constants,
        "columns": columns,
        "labels": [column_label(c) for c in columns],
        "numeric": numeric,
        "rows": rows,
        "hidden": max(0, len(result.rows) - max_rows),
        "truncated": result.truncated,  # the query itself hit the row cap
    }


@cache
def mart_docs(project_root: Path = PROJECT_ROOT) -> dict[str, dict]:
    """Each mart's description and column notes, from dbt_project/models/marts/*.yml."""
    docs = {}
    for path in sorted((project_root / MARTS_DIR).glob("*.yml")):
        for model in yaml.safe_load(path.read_text()).get("models", []):
            docs[model["name"]] = {
                "description": " ".join(model.get("description", "").split()),
                "columns": {c["name"]: " ".join(c.get("description", "").split())
                            for c in model.get("columns", []) if c.get("description")},
            }
    return docs


def notes_for(table: str, columns: Sequence[str]) -> list[tuple[str, str]]:
    """Definitions of the columns an answer shows, for "Where this comes from"."""
    notes = mart_docs().get(table, {}).get("columns", {})
    return [(column_label(c), notes[c]) for c in columns if c in notes]
