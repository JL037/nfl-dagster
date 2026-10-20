"""Roster rows nflverse lists twice: dropped only when the copies differ in nothing but other
sites' ids, so a real duplicate still reaches the load's audit and rolls it back."""

import polars as pl

from nfl_dagster.assets.raw import drop_id_only_duplicates


def roster(*rows):
    columns = ["season", "team", "gsis_id", "full_name", "position", "espn_id", "pfr_id", "sportradar_id", "rotowire_id"]
    return pl.DataFrame(rows, schema=columns, orient="row")


def test_copies_differing_only_in_other_sites_ids_become_one():
    df = roster((1999, "JAX", "00-0016098", "Fred Taylor", "RB", "2", "TaylFr00", "b", None),
                (1999, "JAX", "00-0016098", "Fred Taylor", "RB", "1", "TaylFr00", "a", "9"),
                (2025, "PHI", "00-0036900", "Jalen Hurts", "QB", "5", "HurtJa00", "c", "7"))
    kept, dropped = drop_id_only_duplicates(df)
    assert dropped == 1 and kept.height == 2
    taylor = kept.filter(pl.col("gsis_id") == "00-0016098")
    assert taylor["espn_id"].to_list() == ["1"]  # the same copy every time: the smallest ids


def test_rows_that_differ_in_anything_else_are_kept_for_the_audit():
    df = roster((2001, "ARI", "00-0019641", "Thomas Jones", "RB", "1", "x", "a", None),
                (2001, "ARI", "00-0019641", "Thomas Jones", "WR", "2", "x", "b", None))
    kept, dropped = drop_id_only_duplicates(df)
    assert dropped == 0 and kept.height == 2  # the load's duplicate_player_team_season audit fails


def test_no_duplicates_changes_nothing():
    df = roster((2025, "PHI", "00-0036900", "Jalen Hurts", "QB", "5", "HurtJa00", "c", "7"))
    kept, dropped = drop_id_only_duplicates(df)
    assert dropped == 0 and kept.equals(df)
