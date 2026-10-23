"""Injury reports change format across seasons; the loader makes every season match before the
load's exact column check, and keeps only the latest report per player and week."""

from datetime import UTC, datetime

import polars as pl

from nfl_dagster.assets.raw import INJURY_COLUMNS, keep_latest_reports, normalize_injuries

OLD = {"season": [2012.0], "game_type": ["REG"], "team": ["OAK"], "week": [1.0], "gsis_id": ["A"],
       "position": ["RB"], "full_name": ["A"], "first_name": ["A"], "last_name": ["A"],
       "report_primary_injury": ["Knee"], "report_secondary_injury": [None], "report_status": ["Out"],
       "practice_primary_injury": [None], "practice_secondary_injury": [None], "practice_status": [None],
       "date_modified": [datetime(2012, 9, 8, tzinfo=UTC)]}


def test_every_season_comes_out_in_the_same_columns_and_types():
    old = normalize_injuries(pl.DataFrame(OLD))  # 2009-2020: Float64 season and week
    new = pl.DataFrame({**{k: v for k, v in OLD.items() if k != "date_modified"},
                        "season": [2025], "week": [3], "season_type": ["REG"]},
                       schema_overrides={"season": pl.Int32, "week": pl.Int32})
    new = normalize_injuries(new)  # 2025: no date_modified, has season_type
    assert old.columns == new.columns == INJURY_COLUMNS
    assert old.schema == new.schema
    assert old["season"].to_list() == [2012] and old["season_type"].to_list() == ["REG"]
    assert new["date_modified"].to_list() == [None]


def test_playoff_game_types_get_season_type_post():
    df = normalize_injuries(pl.DataFrame({**OLD, "game_type": ["WC"]}))
    assert df["season_type"].to_list() == ["POST"]


def test_the_latest_report_wins():
    rows = normalize_injuries(pl.DataFrame({k: v * 2 for k, v in OLD.items()}).with_columns(
        pl.Series("report_status", ["Questionable", "Out"]),
        pl.Series("date_modified", [datetime(2024, 12, 15, 3, tzinfo=UTC), datetime(2024, 12, 15, 14, tzinfo=UTC)])))
    kept, dropped = keep_latest_reports(rows)
    assert dropped == 1 and kept["report_status"].to_list() == ["Out"]


def test_different_players_or_weeks_are_kept():
    df = normalize_injuries(pl.DataFrame({k: v * 2 for k, v in OLD.items()}).with_columns(pl.Series("week", [1.0, 2.0])))
    kept, dropped = keep_latest_reports(df)
    assert dropped == 0 and kept.height == 2
