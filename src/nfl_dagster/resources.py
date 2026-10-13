from pathlib import Path

import dagster as dg
from dagster_dbt import DbtCliResource, DbtProject
from dagster_snowflake import SnowflakeResource

REPO_ROOT = Path(__file__).resolve().parents[2]

dbt_project = DbtProject(project_dir=REPO_ROOT / "dbt_project")
# Builds the dbt manifest when running `dagster dev`; in production you'd run `dbt parse` at build time.
dbt_project.prepare_if_dev()

# dg.EnvVar is read when a run starts, not when this file is imported, and the UI shows
# only the variable's name, never its value. Locally the values come from .env, which
# `dagster dev` loads automatically; in a deployment they'd come from a secrets manager.
snowflake_resource = SnowflakeResource(
    account=dg.EnvVar("SNOWFLAKE_ACCOUNT"),
    user=dg.EnvVar("SNOWFLAKE_USER"),
    # Key-pair auth: the service user has no password, so there's nothing to leak or rotate here.
    private_key_path=dg.EnvVar("SNOWFLAKE_PRIVATE_KEY_PATH"),
    role=dg.EnvVar("SNOWFLAKE_ROLE"),
    warehouse=dg.EnvVar("SNOWFLAKE_WAREHOUSE"),
    database=dg.EnvVar("SNOWFLAKE_DATABASE"),
    schema="RAW",
)

dbt_resource = DbtCliResource(project_dir=dbt_project)
