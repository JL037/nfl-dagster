"""NFL_ENV picks the warehouse environment. These run in a subprocess because the choice is
made when nfl_dagster.resources is imported."""

import os
import subprocess
import sys

import pytest

SHOW = (
    "from nfl_dagster import resources as r; "
    "print(r.NFL_ENV, r.SNOWFLAKE_DATABASE, r.dbt_resource.target)"
)


def import_resources(nfl_env: str | None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "NFL_ENV"}
    if nfl_env is not None:
        env["NFL_ENV"] = nfl_env
    return subprocess.run([sys.executable, "-c", SHOW], env=env, capture_output=True, text=True)


@pytest.mark.parametrize(
    ("nfl_env", "expected"),
    [
        (None, "dev NFL_DEV dev"),  # unset means dev: production is only used on purpose
        ("dev", "dev NFL_DEV dev"),
        ("prod", "prod NFL prod"),
    ],
)
def test_nfl_env_selects_database_and_dbt_target(nfl_env, expected):
    result = import_resources(nfl_env)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


def test_unknown_nfl_env_is_rejected():
    result = import_resources("staging")
    assert result.returncode != 0
    assert "NFL_ENV must be one of" in result.stderr
