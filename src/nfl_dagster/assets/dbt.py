from collections.abc import Mapping
from typing import Any

import dagster as dg
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, dbt_assets

from nfl_dagster.resources import dbt_project

# When should a dbt model rebuild on its own?
#
# eager(): as soon as anything it depends on updates, but not while an upstream partition is
# missing (e.g. a season that was never loaded) or an upstream run is still in progress.
#
# The gate: not while a direct upstream asset has a failed *blocking* check against its latest
# materialization. A blocking check only stops later steps in the same run, and automation
# starts the dbt models in a separate run, so without this gate a bad raw load whose check
# failed would still flow into the marts.
NO_FAILED_BLOCKING_CHECKS_UPSTREAM = (
    ~dg.AutomationCondition.any_deps_match(
        dg.AutomationCondition.any_checks_match(
            dg.AutomationCondition.check_failed(), blocking_only=True
        )
    )
).with_label("no_failed_blocking_checks_upstream")

DBT_AUTOMATION_CONDITION = dg.AutomationCondition.eager() & NO_FAILED_BLOCKING_CHECKS_UPSTREAM


class NflDbtTranslator(DagsterDbtTranslator):
    """Customizes how dbt models become Dagster assets. Here: when they should rebuild."""

    def get_automation_condition(
        self, dbt_resource_props: Mapping[str, Any]
    ) -> dg.AutomationCondition | None:
        return DBT_AUTOMATION_CONDITION


# Every model, seed, and snapshot in the dbt project becomes its own Dagster asset,
# read from dbt's manifest.json. dbt tests become asset checks on those assets.
@dbt_assets(manifest=dbt_project.manifest_path, dagster_dbt_translator=NflDbtTranslator())
def nfl_dbt_models(context: dg.AssetExecutionContext, dbt: DbtCliResource):
    # `build` runs models and their tests in dependency order; stream() reports each
    # model and test back to Dagster as it finishes.
    yield from dbt.cli(["build"], context=context).stream()
