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
    "passer_name": "Quarterback", "passer_full_name": "Quarterback", "team": "Team", "team_name": "Team", "season": "Season",
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
    # Player, roster and offensive-line marts
    "player_name": "Player", "role": "Role", "games": "Games", "plays": "Plays",
    "epa_per_play": "EPA per play", "yards": "Yards", "yards_per_play": "Yards per play",
    "touchdowns": "TDs", "completions": "Completions", "completion_rate": "Completion rate",
    "interceptions": "INTs", "qualifying_games": "Qualifying games",
    "positive_game_share": "Positive-EPA games", "game_epa_per_play_sd": "Game-to-game spread",
    "most_efficient_player_name": "Most efficient", "most_efficient_epa_per_play": "EPA per play",
    "most_consistent_player_name": "Most consistent",
    "most_consistent_positive_game_share": "Positive-EPA games",
    "most_consistent_game_epa_per_play_sd": "Game-to-game spread",
    "position": "Position", "position_spot": "Spot", "jersey_number": "Jersey", "status": "Status",
    "years_exp": "Years in NFL", "age": "Age", "height": "Height", "weight": "Weight",
    "college": "College", "draft_club": "Drafted by", "draft_number": "Draft pick",
    "rookie_year": "Rookie year", "dropbacks": "Dropbacks", "sacks": "Sacks", "qb_hits": "QB hits",
    "sack_rate": "Sack rate", "qb_hit_rate": "QB-hit rate", "designed_rushes": "Designed runs",
    "rush_epa_per_play": "Rush EPA per play", "rush_success_rate": "Rush success rate",
    "yards_per_carry": "Yards per carry", "stuff_rate": "Stuff rate",
    "explosive_run_rate": "Explosive run rate", "ol_players": "Linemen",
    "ol_avg_years_exp": "Linemen's avg years", "ol_avg_age": "Linemen's avg age",
}
WORDS = {"epa": "EPA", "qb": "QB", "qbs": "QBs", "ats": "ATS", "id": "ID", "pct": "%", "avg": "Avg"}
YEARLIKE = {"season", "week", "year"}
MONEY = ("cap_number", "cap_hit", "salary", "apy")
MINUS = "−"  # a real minus sign: the hyphen reads as a dash in tables


MART_NAMES = {
    "qb_contract_value": "QB contract value", "qb_season_epa": "QB season EPA",
    "team_season_epa": "Team season EPA", "game_results_vs_spread": "Game results vs the spread",
    "team_fourth_down": "Team fourth-down decisions",
    "player_season_efficiency": "Player efficiency and consistency",
    "team_player_leaders": "Team leaders by role",
    "team_rosters": "Team rosters", "team_offensive_line": "Offensive lines",
}


# Where each mart's data comes from, for credit on every answer (and in the PDF). nflverse data
# is CC BY 4.0: credit, a link, the license, and a note that we changed it (we aggregate it).
NFLVERSE = "https://github.com/nflverse/nflverse-data"
CC_BY = ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/")
SOURCES = {
    "pbp": {"name": "nflverse play-by-play", "url": NFLVERSE, "license": CC_BY,
            "note": "EPA from the nflfastR model"},
    "schedules": {"name": "nflverse schedules and betting lines", "url": NFLVERSE, "license": CC_BY},
    "players": {"name": "nflverse players", "url": NFLVERSE, "license": CC_BY},
    "teams": {"name": "nflverse teams", "url": NFLVERSE, "license": CC_BY},
    "rosters": {"name": "nflverse rosters", "url": NFLVERSE, "license": CC_BY},
    "contracts": {"name": "OverTheCap contracts", "url": "https://overthecap.com", "license": None,
                  "note": "via nflverse"},
    "salary_caps": {"name": "NFL salary cap figures", "url": None, "license": None,
                    "note": "as announced by the league"},
}
MART_SOURCES = {
    "qb_season_epa": ["pbp", "schedules", "players"],
    "qb_contract_value": ["pbp", "schedules", "players", "contracts", "salary_caps"],
    "team_season_epa": ["pbp", "teams"],
    "game_results_vs_spread": ["schedules"],
    "team_fourth_down": ["pbp", "teams"],
    "player_season_efficiency": ["pbp", "schedules", "players"],
    "team_player_leaders": ["pbp", "schedules", "players"],
    "team_rosters": ["rosters"],
    "team_offensive_line": ["pbp", "rosters", "teams"],
}


def sources_for(tables) -> list[dict]:
    """The sources behind the marts an answer read, each once, in a stable order."""
    keys = {key for t in tables for key in MART_SOURCES.get(t, [])}
    return [SOURCES[key] for key in SOURCES if key in keys]


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
    elif ("years_exp" in column or column.endswith("age")) and isinstance(value, float):
        shown = f"{value:.1f}"  # experience and age in years
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


# A column shown only when its fuller version isn't in the same result.
SUPERSEDED_BY = {"passer_name": "passer_full_name"}


def is_internal(column: str) -> bool:
    return column.endswith(("_key", "_id"))


def is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def data_table(result: QueryResult, max_rows: int = 25, first: Sequence[str] = ()) -> dict:
    """The rows behind an answer, ready for a table: readable headers and values, keys hidden,
    the charted columns first, and columns that are the same in every row moved to a note."""
    keep = [i for i, c in enumerate(result.columns)
            if not is_internal(c) and SUPERSEDED_BY.get(c) not in result.columns] or list(range(len(result.columns)))
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
