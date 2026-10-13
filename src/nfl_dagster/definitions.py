import dagster as dg

from nfl_dagster.assets.dbt import nfl_dbt_models
from nfl_dagster.resources import dbt_resource, duckdb_resource

defs = dg.Definitions(
    assets=[nfl_dbt_models],
    resources={
        # Keys must match the parameter names assets ask for (e.g. `dbt: DbtCliResource`).
        "dbt": dbt_resource,
        "duckdb": duckdb_resource,
    },
)
