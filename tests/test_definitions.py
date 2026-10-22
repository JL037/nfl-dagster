"""Tests that the Dagster definitions are wired the way the pipeline relies on.

None of these connect to Snowflake: they load the code and inspect the asset graph,
automation conditions, jobs, and schedule.
"""

import dagster as dg
import pytest

from nfl_dagster.assets.dbt import DBT_AUTOMATION_CONDITION
from nfl_dagster.assets.serving import SERVED_MARTS, SERVING_AUTOMATION_CONDITION
from nfl_dagster.definitions import contracts_schedule, current_season_schedule, defs
from nfl_dagster.partitions import CURRENT_SEASON, FIRST_SEASON, season_partitions

RAW_ASSETS = {"raw_pbp", "raw_schedules", "raw_teams", "raw_contracts", "raw_players", "raw_rosters",
              "raw_player_stats", "raw_team_stats", "raw_injuries"}
DBT_ASSETS = {
    "staging/stg_pbp",
    "staging/stg_schedules",
    "staging/stg_teams",
    "staging/stg_fourth_downs",
    "staging/stg_cap_hits",
    "staging/stg_players",
    "staging/stg_rosters",
    "staging/league_salary_caps",
    "intermediate/int_player_games",
    "marts/team_season_epa",
    "marts/qb_season_epa",
    "marts/game_results_vs_spread",
    "marts/team_fourth_down",
    "marts/qb_contract_value",
    "marts/player_season_efficiency",
    "marts/team_player_leaders",
    "marts/team_rosters",
    "marts/team_offensive_line",
    "marts/player_season_vs_league",
    "marts/player_careers",
    "staging/stg_player_stats",
    "staging/stg_team_stats",
    "marts/player_season_stats",
    "marts/team_season_stats",
    "staging/stg_injuries",
    "marts/injury_reports",
    "marts/player_season_injuries",
}

# One serving asset per published mart: the copy the website reads.
SERVING_ASSETS = {f"serving/{mart}" for mart in SERVED_MARTS}


@pytest.fixture(scope="module")
def asset_graph():
    return defs.resolve_asset_graph()


def keys(asset_keys) -> set[str]:
    return {k.to_user_string() for k in asset_keys}


def test_assets(asset_graph):
    assert keys(asset_graph.get_all_asset_keys()) == RAW_ASSETS | DBT_ASSETS | SERVING_ASSETS


def test_every_mart_is_served():
    """A mart the website can't see might as well not exist; a new mart must be added here."""
    marts = {k.split("/", 1)[1] for k in DBT_ASSETS if k.startswith("marts/")}
    assert set(SERVED_MARTS) == marts


def test_served_primary_keys_are_tested_unique_in_dbt(asset_graph):
    """Each served table's primary key is the column dbt already tests as unique on its mart,
    so the serving grain and the tested grain can't drift apart."""
    check_names = {c.name for c in asset_graph.asset_check_keys}
    for mart, key in SERVED_MARTS.items():
        assert f"unique_{mart}_{key}" in check_names, f"{mart}.{key} has no dbt unique test"


@pytest.mark.parametrize("mart", sorted(SERVING_ASSETS))
def test_serving_asset_reads_its_mart(asset_graph, mart):
    node = asset_graph.get(dg.AssetKey.from_user_string(mart))
    assert keys(node.parent_keys) == {mart.replace("serving/", "marts/")}


def test_checks(asset_graph):
    checks = asset_graph.asset_check_keys
    raw_checks = {c.name for c in checks if c.asset_key.to_user_string() in RAW_ASSETS}
    assert raw_checks == {"raw_pbp_unique_plays", "raw_schedules_scores_present"}
    # The rest are dbt tests (schema tests and singular tests in dbt_project/tests/),
    # which dagster-dbt turns into asset checks.
    # dbt unit tests (unit_tests: in the YAML) are not asset checks; they run inside dbt build.
    # +3 for players: unique and not_null on stg_players.player_id, not_null on passer_full_name.
    # +15 for rosters, player games, player efficiency, leaders and offensive line: unique and
    # not_null on each key (12), accepted_values on role (2), not_null player_name (1).
    # +4 for the cross-era marts: unique and not_null on each key.
    # +8 for box-score stats: unique and not_null on the keys of 2 staging models and 2 marts.
    # +6 for injuries: unique and not_null on the keys of stg_injuries and 2 marts.
    assert len(checks) == 81
    names = {c.name for c in checks}
    assert "assert_team_fourth_down_counts_consistent" in names
    # A missing spread would otherwise go unnoticed (see game_results_vs_spread.sql).
    assert "not_null_game_results_vs_spread_spread_line" in names
    # Reads raw.contracts and stg_cap_hits; its meta.dagster.ref picks which asset owns it.
    assert dg.AssetCheckKey(
        dg.AssetKey(["staging", "stg_cap_hits"]), "assert_cap_hits_keep_every_season"
    ) in checks
    assert dg.AssetCheckKey(
        dg.AssetKey(["marts", "qb_contract_value"]), "assert_qb_contract_value_keeps_every_qb_season"
    ) in checks


@pytest.mark.parametrize(
    ("asset", "upstream"),
    [
        # Python assets connect to dbt through sources.yml (meta.dagster.asset_key).
        ("staging/stg_pbp", {"raw_pbp"}),
        ("staging/stg_schedules", {"raw_schedules"}),
        ("staging/stg_teams", {"raw_teams"}),
        ("staging/stg_cap_hits", {"raw_contracts"}),
        ("staging/stg_players", {"raw_players"}),
        ("staging/stg_rosters", {"raw_rosters"}),
        # One row per player x game x role (passer, rusher, receiver); not published.
        ("intermediate/int_player_games", {"staging/stg_pbp"}),
        (
            "marts/player_season_efficiency",
            {"intermediate/int_player_games", "staging/stg_players", "staging/stg_schedules"},
        ),
        ("marts/team_player_leaders", {"marts/player_season_efficiency"}),
        ("marts/team_rosters", {"staging/stg_rosters"}),
        ("staging/stg_player_stats", {"raw_player_stats"}),
        ("staging/stg_injuries", {"raw_injuries"}),
        ("marts/injury_reports", {"staging/stg_injuries", "staging/stg_teams"}),
        ("marts/player_season_injuries", {"staging/stg_injuries"}),
        ("staging/stg_team_stats", {"raw_team_stats"}),
        ("marts/player_season_stats", {"staging/stg_player_stats"}),
        ("marts/team_season_stats", {"staging/stg_team_stats", "staging/stg_teams"}),
        # Across eras: each season against its own league average, and careers built from them.
        ("marts/player_season_vs_league", {"marts/player_season_efficiency", "intermediate/int_player_games"}),
        (
            "marts/player_careers",
            {"intermediate/int_player_games", "marts/player_season_vs_league", "staging/stg_rosters",
             "staging/stg_players"},
        ),
        ("marts/team_offensive_line", {"staging/stg_pbp", "staging/stg_rosters", "staging/stg_teams"}),
        (
            "marts/qb_contract_value",
            {
                "marts/qb_season_epa",
                "staging/stg_cap_hits",
                "staging/league_salary_caps",
                "staging/stg_teams",
            },
        ),
        ("marts/team_season_epa", {"staging/stg_pbp", "staging/stg_teams"}),
        # stg_schedules: how much of the season is played, for the pro-rated dropback minimum.
        # stg_players: full names ("Jordan Love", not "J.Love") for the Ask page.
        ("marts/qb_season_epa", {"staging/stg_pbp", "staging/stg_schedules", "staging/stg_players"}),
        ("marts/game_results_vs_spread", {"staging/stg_schedules"}),
        ("staging/stg_fourth_downs", {"raw_pbp"}),
        ("marts/team_fourth_down", {"staging/stg_fourth_downs", "staging/stg_teams"}),
    ],
)
def test_lineage(asset_graph, asset, upstream):
    node = asset_graph.get(dg.AssetKey.from_user_string(asset))
    assert keys(node.parent_keys) == upstream


def test_raw_assets_are_partitioned_by_season(asset_graph):
    for asset in ("raw_pbp", "raw_schedules", "raw_player_stats", "raw_team_stats"):
        assert asset_graph.get(dg.AssetKey(asset)).partitions_def == season_partitions
    for asset in ("raw_teams", "raw_contracts", "raw_injuries"):  # injuries start in 2009
        assert asset_graph.get(dg.AssetKey(asset)).partitions_def is None
    expected = [str(s) for s in range(FIRST_SEASON, CURRENT_SEASON + 1)]
    assert season_partitions.get_partition_keys() == expected


def test_automation_on_dbt_models_and_serving(asset_graph):
    """dbt models and serving copies rebuild on their own; raw assets are scheduled."""
    for key in asset_graph.get_all_asset_keys():
        condition = asset_graph.get(key).automation_condition
        labels = [child.get_label() for child in condition.children] if condition else None
        if key.to_user_string() in DBT_ASSETS:
            assert condition == DBT_AUTOMATION_CONDITION
            assert labels == ["eager", "no_failed_blocking_checks_upstream"]
        elif key.to_user_string() in SERVING_ASSETS:
            # Stricter than the dbt models: ANY failed check on the mart (a failing dbt test
            # is not blocking) holds the website's copy back.
            assert condition == SERVING_AUTOMATION_CONDITION
            assert labels == ["eager", "no_failed_checks_upstream"]
        else:
            assert condition is None, f"{key.to_user_string()} should not be automated"


def test_current_season_refresh_job():
    job = defs.resolve_job_def("current_season_refresh")
    # Box-score stats refresh with the games they come from.
    assert keys(job.asset_layer.selected_asset_keys) == {"raw_pbp", "raw_schedules", "raw_player_stats", "raw_team_stats"}
    assert job.partitions_def == season_partitions


def test_raw_data_checks_job_selects_only_checks():
    job = defs.resolve_job_def("raw_data_checks")
    assert job.asset_layer.selected_asset_keys == set()


def test_schedule_requests_current_season():
    # Monday (Sunday games), Tuesday (Monday night), Friday (Thursday night).
    assert current_season_schedule.cron_schedule == "0 10 * * 1,2,5"
    assert current_season_schedule.execution_timezone == "America/Los_Angeles"
    assert current_season_schedule.job_name == "current_season_refresh"
    with dg.build_schedule_context() as context:
        request = current_season_schedule(context)
    assert request.partition_key == str(CURRENT_SEASON)


def test_contracts_refresh_job_and_schedule():
    """Contracts and players aren't partitioned, so they can't share current_season_refresh; they
    get their own job on the same Monday/Tuesday/Friday schedule, so all raw data refreshes together."""
    job = defs.resolve_job_def("contracts_refresh")
    assert keys(job.asset_layer.selected_asset_keys) == {"raw_contracts", "raw_players", "raw_rosters", "raw_injuries"}
    assert job.partitions_def is None
    assert contracts_schedule.cron_schedule == current_season_schedule.cron_schedule
    assert contracts_schedule.execution_timezone == "America/Los_Angeles"
    assert contracts_schedule.job_name == "contracts_refresh"


def test_players_load_is_audited_for_missing_and_duplicate_ids():
    """A duplicate id would double every QB season it joins to; a missing one can't join."""
    from nfl_dagster.assets.raw import AUDITS

    assert set(AUDITS["PLAYERS"]) == {"missing_gsis_id", "duplicate_gsis_id"}


def test_rosters_load_is_audited_for_duplicate_rows():
    """One row per player, team and season: a duplicate would double a player in a roster."""
    from nfl_dagster.assets.raw import AUDITS

    assert set(AUDITS["ROSTERS"]) == {"duplicate_player_team_season"}


def test_intermediate_models_are_not_served():
    """int_player_games is ~200K rows a refresh; the site only needs the season marts built on it."""
    assert not any(key.startswith("serving/intermediate") for key in SERVING_ASSETS)
