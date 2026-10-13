from pathlib import Path

from dagster_dbt import DbtCliResource, DbtProject
from dagster_duckdb import DuckDBResource

REPO_ROOT = Path(__file__).resolve().parents[2]
DUCKDB_PATH = REPO_ROOT / "data" / "nfl.duckdb"

dbt_project = DbtProject(project_dir=REPO_ROOT / "dbt_project")
# Builds the dbt manifest when running `dagster dev`; in production you'd run `dbt parse` at build time.
dbt_project.prepare_if_dev()

duckdb_resource = DuckDBResource(database=str(DUCKDB_PATH))
dbt_resource = DbtCliResource(project_dir=dbt_project)
