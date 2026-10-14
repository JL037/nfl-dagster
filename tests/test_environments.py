"""Each `make` target must pair an environment with its own workspace, location name, and
port. If these drift apart (say, `make prod` loading the dev workspace), the UI would show
the wrong environment name while writing to the other database."""

import re

import pytest
import yaml

from nfl_dagster.resources import REPO_ROOT

EXPECTED = {
    "dev": {"workspace": "workspaces/dev.yaml", "location": "nfl_dagster_dev", "port": "3000"},
    "prod": {"workspace": "workspaces/prod.yaml", "location": "nfl_dagster_prod", "port": "3001"},
}


def make_command(env: str) -> str:
    """The `dagster dev` line that sets NFL_ENV=<env> in the Makefile."""
    makefile = (REPO_ROOT / "Makefile").read_text()
    lines = [line for line in makefile.splitlines() if f"NFL_ENV={env} " in line and "dagster dev" in line]
    assert len(lines) == 1, f"expected one `dagster dev` line for NFL_ENV={env}"
    return lines[0]


@pytest.mark.parametrize("env", EXPECTED)
def test_make_target_uses_its_own_workspace_and_port(env):
    command = make_command(env)
    assert f"-w {EXPECTED[env]['workspace']}" in command
    assert re.search(rf"-p {EXPECTED[env]['port']}\b", command)
    assert f".dagster_home/{env}" in (REPO_ROOT / "Makefile").read_text()


@pytest.mark.parametrize("env", EXPECTED)
def test_workspace_location_name_matches_environment(env):
    workspace = yaml.safe_load((REPO_ROOT / EXPECTED[env]["workspace"]).read_text())
    (entry,) = workspace["load_from"]
    module = entry["python_module"]
    assert module["module_name"] == "nfl_dagster.definitions"
    assert module["location_name"] == EXPECTED[env]["location"]
