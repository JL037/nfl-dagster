import os
from pathlib import Path

import dagster as dg
from dagster_dbt import DbtCliResource, DbtProject
from dagster_snowflake import SnowflakeResource

from nfl_dagster.serving import ServingPostgresResource

REPO_ROOT = Path(__file__).resolve().parents[2]

# Which warehouse environment this process works against. Set it in the shell (the Makefile
# does: `make dev` / `make prod`), never in .env: Dagster's .env loading overrides the shell,
# so a value there would silently win over what you typed. Unset means dev, so production is
# only ever used on purpose.
ENVIRONMENTS = {"dev": "NFL_DEV", "prod": "NFL"}
NFL_ENV = os.getenv("NFL_ENV", "dev")
if NFL_ENV not in ENVIRONMENTS:
    raise ValueError(f"NFL_ENV must be one of {sorted(ENVIRONMENTS)}, got {NFL_ENV!r}")
SNOWFLAKE_DATABASE = ENVIRONMENTS[NFL_ENV]

dbt_project = DbtProject(project_dir=REPO_ROOT / "dbt_project", target=NFL_ENV)
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
    # Not a secret, and chosen by NFL_ENV above: NFL_DEV for dev, NFL for prod.
    database=SNOWFLAKE_DATABASE,
    schema="RAW",
)

# dbt picks the matching target from profiles.yml (dev -> NFL_DEV, prod -> NFL).
dbt_resource = DbtCliResource(project_dir=dbt_project, target=NFL_ENV)

# The serving database (Prisma Postgres) the website reads. Dev and prod are separate
# databases, chosen by NFL_ENV like everything above: a branch never publishes to prod.
SERVING_DB_URL_VAR = f"SERVING_DB_URL_{NFL_ENV.upper()}"
serving_resource = ServingPostgresResource(url=dg.EnvVar(SERVING_DB_URL_VAR))
