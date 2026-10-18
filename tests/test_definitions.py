"""Tests that the Dagster definitions are wired the way the pipeline relies on.

None of these connect to Snowflake: they load the code and inspect the asset graph,
automation conditions, jobs, and schedule.
"""

import dagster as dg
import pytest

from nfl_dagster.assets.dbt import DBT_AUTOMATION_CONDITION
from nfl_dagster.definitions import current_season_schedule, defs
from nfl_dagster.partitions import CURRENT_SEASON, FIRST_SEASON, season_partitions

RAW_ASSETS = {"raw_pbp", "raw_schedules", "raw_teams", "raw_contracts"}
DBT_ASSETS = {
    "staging/stg_pbp",
    "staging/stg_schedules",
    "staging/stg_teams",
    "staging/stg_fourth_downs",
    "staging/stg_cap_hits",
    "staging/league_salary_caps",
    "marts/team_season_epa",
    "marts/qb_season_epa",
    "marts/game_results_vs_spread",
    "marts/team_fourth_down",
    "marts/qb_contract_value",
}


@pytest.fixture(scope="module")
def asset_graph():
    return defs.resolve_asset_graph()


def keys(asset_keys) -> set[str]:
    return {k.to_user_string() for k in asset_keys}


def test_assets(asset_graph):
    assert keys(asset_graph.get_all_asset_keys()) == RAW_ASSETS | DBT_ASSETS


def test_checks(asset_graph):
    checks = asset_graph.asset_check_keys
    raw_checks = {c.name for c in checks if c.asset_key.to_user_string() in RAW_ASSETS}
    assert raw_checks == {"raw_pbp_unique_plays", "raw_schedules_scores_present"}
    # The rest are dbt tests (schema tests and singular tests in dbt_project/tests/),
    # which dagster-dbt turns into asset checks.
    # dbt unit tests (unit_tests: in the YAML) are not asset checks; they run inside dbt build.
    assert len(checks) == 45
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
        ("marts/qb_season_epa", {"staging/stg_pbp", "staging/stg_schedules"}),
        ("marts/game_results_vs_spread", {"staging/stg_schedules"}),
        ("staging/stg_fourth_downs", {"raw_pbp"}),
        ("marts/team_fourth_down", {"staging/stg_fourth_downs", "staging/stg_teams"}),
    ],
)
def test_lineage(asset_graph, asset, upstream):
    node = asset_graph.get(dg.AssetKey.from_user_string(asset))
    assert keys(node.parent_keys) == upstream


def test_raw_assets_are_partitioned_by_season(asset_graph):
    for asset in ("raw_pbp", "raw_schedules"):
        assert asset_graph.get(dg.AssetKey(asset)).partitions_def == season_partitions
    for asset in ("raw_teams", "raw_contracts"):
        assert asset_graph.get(dg.AssetKey(asset)).partitions_def is None
    expected = [str(s) for s in range(FIRST_SEASON, CURRENT_SEASON + 1)]
    assert season_partitions.get_partition_keys() == expected


def test_automation_only_on_dbt_models(asset_graph):
    """dbt models rebuild on their own (eager + the failed-check gate); raw assets are scheduled."""
    for key in asset_graph.get_all_asset_keys():
        condition = asset_graph.get(key).automation_condition
        if key.to_user_string() in DBT_ASSETS:
            assert condition == DBT_AUTOMATION_CONDITION
            labels = [child.get_label() for child in condition.children]
            assert labels == ["eager", "no_failed_blocking_checks_upstream"]
        else:
            assert condition is None, f"{key.to_user_string()} should not be automated"


def test_current_season_refresh_job():
    job = defs.resolve_job_def("current_season_refresh")
    assert keys(job.asset_layer.selected_asset_keys) == {"raw_pbp", "raw_schedules"}
    assert job.partitions_def == season_partitions


def test_raw_data_checks_job_selects_only_checks():
    job = defs.resolve_job_def("raw_data_checks")
    assert job.asset_layer.selected_asset_keys == set()


def test_schedule_requests_current_season():
    assert current_season_schedule.cron_schedule == "0 10 * * 2,5"
    assert current_season_schedule.execution_timezone == "America/Los_Angeles"
    assert current_season_schedule.job_name == "current_season_refresh"
    with dg.build_schedule_context() as context:
        request = current_season_schedule(context)
    assert request.partition_key == str(CURRENT_SEASON)
