import dagster as dg

from nfl_dagster.assets.dbt import nfl_dbt_models
from nfl_dagster.assets.raw import raw_contracts, raw_pbp, raw_schedules, raw_teams
from nfl_dagster.checks import raw_pbp_unique_plays, raw_schedules_scores_present
from nfl_dagster.partitions import CURRENT_SEASON
from nfl_dagster.resources import dbt_resource, snowflake_resource

# Runs only the raw checks, without re-materializing the assets they check.
# The UI can't yet execute a partitioned check on its own (Dagster 1.13: "not yet supported"),
# and a checks-only job doesn't keep a partitions_def, so pick the season with a run tag
# when launching: dagster/partition = 2025.
raw_data_checks = dg.define_asset_job(
    "raw_data_checks",
    selection=dg.AssetSelection.checks(raw_pbp_unique_plays, raw_schedules_scores_present),
)

# Refreshes the season in progress. Selecting the assets also selects their checks, so the
# blocking checks run in the same run. raw_teams and the dbt models aren't in this job:
# an asset job can only hold assets with the same partitions definition, and the dbt
# models update through declarative automation instead (see assets/dbt.py).
# Its partitions (one per season) come from the selected assets.
current_season_refresh = dg.define_asset_job(
    "current_season_refresh",
    selection=[raw_pbp, raw_schedules],
)


# 10:00 Pacific on Tuesdays and Fridays: after Sunday/Monday and Thursday games have
# landed in nflverse. The schedule only refreshes the raw data; the dbt models follow on
# their own once it's loaded (and its checks pass).
@dg.schedule(
    job=current_season_refresh,
    cron_schedule="0 10 * * 2,5",
    execution_timezone="America/Los_Angeles",
)
def current_season_schedule():
    return dg.RunRequest(partition_key=str(CURRENT_SEASON))


# Contracts change any week (signings, releases, extensions), and nothing refreshes them
# otherwise. raw_contracts isn't partitioned, so it can't join current_season_refresh (a job
# holds assets with one partitions definition); it gets its own job on the same schedule, so
# all raw data refreshes together. stg_cap_hits and qb_contract_value follow through
# declarative automation, like every dbt model.
contracts_refresh = dg.define_asset_job("contracts_refresh", selection=[raw_contracts])

contracts_schedule = dg.ScheduleDefinition(
    job=contracts_refresh,
    cron_schedule=current_season_schedule.cron_schedule,
    execution_timezone="America/Los_Angeles",
)


defs = dg.Definitions(
    assets=[raw_teams, raw_contracts, raw_pbp, raw_schedules, nfl_dbt_models],
    asset_checks=[raw_pbp_unique_plays, raw_schedules_scores_present],
    jobs=[raw_data_checks, current_season_refresh, contracts_refresh],
    schedules=[current_season_schedule, contracts_schedule],
    resources={
        # Keys must match the parameter names assets ask for (e.g. `dbt: DbtCliResource`).
        "dbt": dbt_resource,
        "snowflake": snowflake_resource,
    },
)
