import os
from collections.abc import Mapping
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



def choose_dbt_project_dir(repo_root: Path, packaged_dir: Path) -> Path:
    """The repo's dbt_project/ when it's there (a laptop), else the copy inside the package.

    Dagster+ Serverless installs this package on its own, without the repo around it. The
    deploy workflow runs `dagster-dbt project prepare-and-package`, which copies dbt_project/
    (with a fresh manifest) into the package as nfl_dagster/dbt-project. DbtProject switches
    to that copy by itself, but only after checking that project_dir exists, hence this.
    """
    repo_dir = repo_root / "dbt_project"
    return repo_dir if repo_dir.exists() else packaged_dir


PACKAGED_DBT_PROJECT_DIR = Path(__file__).resolve().parent / "dbt-project"
dbt_project = DbtProject(
    project_dir=choose_dbt_project_dir(REPO_ROOT, PACKAGED_DBT_PROJECT_DIR),
    packaged_project_dir=PACKAGED_DBT_PROJECT_DIR,
    target=NFL_ENV,
)
# Builds the dbt manifest when running `dagster dev`; deploys build it in the workflow instead.
dbt_project.prepare_if_dev()


def raw_data_dir(environ: Mapping[str, str]) -> Path:
    """Where raw assets write their Parquet files: data/raw in the repo, unless NFL_DATA_DIR
    says otherwise (Dagster+ sets it to a temp folder, since there's no repo folder there)."""
    return Path(environ.get("NFL_DATA_DIR", REPO_ROOT / "data")) / "raw"


def snowflake_key_auth(environ: Mapping[str, str]) -> dict[str, dg.EnvVar]:
    """Key text (SNOWFLAKE_PRIVATE_KEY) where there's no key file, as on Dagster+; otherwise the
    file at SNOWFLAKE_PRIVATE_KEY_PATH, as on each laptop.

    The text is the PEM itself, newlines and all: both dagster-snowflake and dbt-snowflake read
    PEM, but their base64 forms differ (base64 of the PEM vs. of the binary key).
    """
    if environ.get("SNOWFLAKE_PRIVATE_KEY"):
        if environ.get("SNOWFLAKE_PRIVATE_KEY_PATH"):
            raise ValueError(
                "Set SNOWFLAKE_PRIVATE_KEY or SNOWFLAKE_PRIVATE_KEY_PATH, not both (dbt refuses both)"
            )
        return {"private_key": dg.EnvVar("SNOWFLAKE_PRIVATE_KEY")}
    return {"private_key_path": dg.EnvVar("SNOWFLAKE_PRIVATE_KEY_PATH")}


# dg.EnvVar is read when a run starts, not when this file is imported, and the UI shows
# only the variable's name, never its value. Locally the values come from .env, which
# `dagster dev` loads automatically; in a deployment they'd come from a secrets manager.
snowflake_resource = SnowflakeResource(
    account=dg.EnvVar("SNOWFLAKE_ACCOUNT"),
    user=dg.EnvVar("SNOWFLAKE_USER"),
    # Key-pair auth: the service user has no password, so there's nothing to leak or rotate here.
    **snowflake_key_auth(os.environ),
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
