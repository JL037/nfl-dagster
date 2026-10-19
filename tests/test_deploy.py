"""Dagster+ Serverless runs the same code as a laptop, packaged differently: the package is
installed on its own (no repo folder around it), and there's no key file, only environment
variables. These tests pin the pieces that let one codebase work in both places.

None of them connect to Snowflake or Dagster+.
"""

import os
import subprocess
import sys
import tomllib

import dagster as dg
import jinja2
import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from dbt.adapters.snowflake.connections import SnowflakeCredentials

from nfl_dagster.resources import (
    REPO_ROOT,
    choose_dbt_project_dir,
    raw_data_dir,
    snowflake_key_auth,
)

DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "dagster-plus-deploy.yml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PACKAGED_DBT_DIR = "src/nfl_dagster/dbt-project"


@pytest.fixture(scope="module")
def pem_key() -> str:
    """A throwaway key in the same format as the real ones (unencrypted PKCS#8 PEM)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()


# --- Snowflake key: text in the cloud, a file on a laptop ------------------------------------


def test_key_text_is_used_when_set():
    auth = snowflake_key_auth({"SNOWFLAKE_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----..."})
    assert auth == {"private_key": dg.EnvVar("SNOWFLAKE_PRIVATE_KEY")}


def test_key_path_is_used_otherwise():
    auth = snowflake_key_auth({"SNOWFLAKE_PRIVATE_KEY_PATH": "/keys/k.p8"})
    assert auth == {"private_key_path": dg.EnvVar("SNOWFLAKE_PRIVATE_KEY_PATH")}


def test_key_text_and_path_together_are_rejected():
    # dbt refuses this combination too; failing at import makes the mistake obvious at once.
    with pytest.raises(ValueError, match="not both"):
        snowflake_key_auth({"SNOWFLAKE_PRIVATE_KEY": "x", "SNOWFLAKE_PRIVATE_KEY_PATH": "/k.p8"})


def test_snowflake_resource_reads_key_text_from_the_environment():
    # Module-level wiring, so check it in a fresh process like test_resources.py does.
    env = {k: v for k, v in os.environ.items() if not k.startswith("SNOWFLAKE_PRIVATE_KEY")}
    env["SNOWFLAKE_PRIVATE_KEY"] = "placeholder"
    show = (
        "from nfl_dagster.resources import snowflake_resource as s; "
        "print(type(s.private_key).__name__, s.private_key_path)"
    )
    result = subprocess.run([sys.executable, "-c", show], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "EnvVar None"


def dbt_credentials(target: str, env: dict[str, str]) -> SnowflakeCredentials:
    """Render the real profiles.yml the way dbt does, then build dbt-snowflake's credentials."""
    raw = (REPO_ROOT / "dbt_project" / "profiles.yml").read_text()
    output = yaml.safe_load(raw)["nfl"]["outputs"][target]

    def env_var(name, default=None):
        if name in env:
            return env[name]
        if default is None:
            raise KeyError(name)
        return default

    rendered = {
        k: jinja2.Template(v).render(env_var=env_var) if isinstance(v, str) else v
        for k, v in output.items()
    }
    rendered.pop("type")
    rendered.pop("threads")
    return SnowflakeCredentials.from_dict(rendered)


BASE_ENV = {
    "SNOWFLAKE_ACCOUNT": "acct",
    "SNOWFLAKE_USER": "user",
    "SNOWFLAKE_ROLE": "role",
    "SNOWFLAKE_WAREHOUSE": "wh",
}


@pytest.mark.parametrize("target", ["dev", "prod"])
def test_dbt_profile_loads_key_text_without_a_path(target, pem_key):
    creds = dbt_credentials(target, {**BASE_ENV, "SNOWFLAKE_PRIVATE_KEY": pem_key})
    assert creds._get_private_key() is not None


@pytest.mark.parametrize("target", ["dev", "prod"])
def test_dbt_profile_still_loads_key_file(target, pem_key, tmp_path):
    key_file = tmp_path / "k.p8"
    key_file.write_text(pem_key)
    creds = dbt_credentials(target, {**BASE_ENV, "SNOWFLAKE_PRIVATE_KEY_PATH": str(key_file)})
    assert creds._get_private_key() is not None


# --- Where the dbt project and the downloaded files live --------------------------------------


def test_repo_dbt_project_is_used_when_present(tmp_path):
    (tmp_path / "dbt_project").mkdir()
    packaged = tmp_path / "pkg" / "dbt-project"
    assert choose_dbt_project_dir(tmp_path, packaged) == tmp_path / "dbt_project"


def test_packaged_dbt_project_is_used_without_the_repo(tmp_path):
    # Dagster+ installs the package on its own, so there's no dbt_project/ beside it.
    packaged = tmp_path / "pkg" / "dbt-project"
    assert choose_dbt_project_dir(tmp_path, packaged) == packaged


def test_raw_data_dir_defaults_to_the_repo():
    assert raw_data_dir({}) == REPO_ROOT / "data" / "raw"


def test_raw_data_dir_can_be_moved(tmp_path):
    assert raw_data_dir({"NFL_DATA_DIR": str(tmp_path)}) == tmp_path / "raw"


# --- Packaging ---------------------------------------------------------------------------------


def test_packaged_dbt_project_ships_in_the_package():
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    package_data = pyproject["tool"]["setuptools"]["package-data"]["nfl_dagster"]
    assert "dbt-project/**/*" in package_data


def test_deploy_environment_has_the_dg_cli():
    # The workflow builds its environment with `uv sync`, which installs the `dev` dependency
    # group, not the `dev` extra that `pip install -e ".[dev]"` reads. Its "Refresh defs state"
    # step then runs `dg` from that environment (first deploy failed: No module named
    # 'dagster_dg_cli').
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    dev_group = pyproject.get("dependency-groups", {}).get("dev", [])
    assert any(req.split("[")[0].split(">")[0].split("=")[0].strip() == "dagster-dg-cli" for req in dev_group)


def test_packaged_dbt_project_is_never_committed():
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", f"{PACKAGED_DBT_DIR}/target/manifest.json"], cwd=REPO_ROOT
    )
    assert ignored.returncode == 0


# --- The deploy workflow -----------------------------------------------------------------------


@pytest.fixture(scope="module")
def deploy():
    return yaml.safe_load(DEPLOY_WORKFLOW.read_text())


def steps(workflow) -> list[dict]:
    (job,) = workflow["jobs"].values()
    return job["steps"]


def test_deploys_only_from_main(deploy):
    # PyYAML reads the `on:` key as True. No pull_request trigger: no branch deployments,
    # which would need their own secrets and spend credits on every PR.
    assert deploy[True] == {"push": {"branches": ["main"]}}


def test_deploy_uses_the_python_version_ci_tests(deploy):
    ci = yaml.safe_load(CI_WORKFLOW.read_text())
    setup = next(s for s in steps(ci) if s.get("uses", "").startswith("actions/setup-python"))
    assert deploy["env"]["PYTHON_VERSION"] == setup["with"]["python-version"]


def test_prod_dbt_manifest_is_built_before_packaging(deploy):
    names = [s.get("name") for s in steps(deploy)]
    prepare = next(s for s in steps(deploy) if "prepare-and-package" in s.get("run", ""))
    assert "--file src/nfl_dagster/resources.py" in prepare["run"]
    # The manifest is built for the target the deployment runs, so its relation names say NFL.
    assert prepare["env"]["NFL_ENV"] == "prod"
    assert names.index(prepare["name"]) < names.index("Build and push")
