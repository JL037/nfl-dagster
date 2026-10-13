import dagster as dg
from dagster_dbt import DbtCliResource, dbt_assets

from nfl_dagster.resources import dbt_project


# Every model, seed, and snapshot in the dbt project becomes its own Dagster asset,
# read from dbt's manifest.json. dbt tests become asset checks on those assets.
@dbt_assets(manifest=dbt_project.manifest_path)
def nfl_dbt_models(context: dg.AssetExecutionContext, dbt: DbtCliResource):
    # `build` runs models and their tests in dependency order; stream() reports each
    # model and test back to Dagster as it finishes.
    yield from dbt.cli(["build"], context=context).stream()
