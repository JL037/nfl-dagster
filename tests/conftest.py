import subprocess

import pytest

from nfl_dagster.resources import REPO_ROOT

DBT_PROJECT_DIR = REPO_ROOT / "dbt_project"


@pytest.fixture(scope="session", autouse=True)
def dbt_manifest():
    """@dbt_assets builds the asset graph from dbt's manifest.json, so make sure it exists.

    CI runs `dbt parse` before pytest; locally this covers a fresh clone. Parsing never
    connects to Snowflake.
    """
    manifest = DBT_PROJECT_DIR / "target" / "manifest.json"
    if not manifest.exists():
        subprocess.run(["dbt", "parse"], cwd=DBT_PROJECT_DIR, check=True)
    return manifest
