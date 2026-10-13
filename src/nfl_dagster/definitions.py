import dagster as dg

from nfl_dagster.assets.dbt import nfl_dbt_models
from nfl_dagster.assets.raw import raw_pbp, raw_schedules, raw_teams
from nfl_dagster.checks import raw_pbp_unique_plays, raw_schedules_scores_present
from nfl_dagster.resources import dbt_resource, duckdb_resource

# Runs only the raw checks, without re-materializing the assets they check.
# The UI can't yet execute a partitioned check on its own (Dagster 1.13: "not yet supported"),
# and a checks-only job doesn't keep a partitions_def, so pick the season with a run tag
# when launching: dagster/partition = 2025.
raw_data_checks = dg.define_asset_job(
    "raw_data_checks",
    selection=dg.AssetSelection.checks(raw_pbp_unique_plays, raw_schedules_scores_present),
)

defs = dg.Definitions(
    assets=[raw_teams, raw_pbp, raw_schedules, nfl_dbt_models],
    asset_checks=[raw_pbp_unique_plays, raw_schedules_scores_present],
    jobs=[raw_data_checks],
    resources={
        # Keys must match the parameter names assets ask for (e.g. `dbt: DbtCliResource`).
        "dbt": dbt_resource,
        "duckdb": duckdb_resource,
    },
)
