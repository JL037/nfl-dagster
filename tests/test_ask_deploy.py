"""The Ask page's deployment (Railway): what the host runs and how the app finds its database.
Nothing here deploys; it pins the config the host reads."""

import json
import re

from fastapi.testclient import TestClient

from nfl_ask.web import create_app, serving_url
from nfl_dagster.resources import REPO_ROOT


def test_the_website_prefers_the_pooled_database_url():
    env = {"SERVING_DB_URL_PROD": "direct", "SERVING_DB_URL_PROD_POOLED": "pooled"}
    assert serving_url("prod", env) == "pooled"  # many short web requests: the pooler's job


def test_the_direct_url_is_the_fallback():
    assert serving_url("dev", {"SERVING_DB_URL_DEV": "direct"}) == "direct"


def test_health_answers_without_touching_the_database():
    def no_database():
        raise AssertionError("health must not read the database")
    app = create_app(ask=lambda q: None, freshness=no_database)
    response = TestClient(app).get("/health")
    assert response.status_code == 200 and response.text == "ok"


def test_railway_builds_the_dockerfile_and_checks_health():
    config = json.loads((REPO_ROOT / "railway.json").read_text())
    assert config["build"]["builder"] == "DOCKERFILE"
    assert (REPO_ROOT / config["build"]["dockerfilePath"]).exists()
    assert config["deploy"]["healthcheckPath"] == "/health"


def test_the_container_runs_the_app_without_access_logs():
    """Access logs would keep every visitor's IP address; the page promises we keep nothing."""
    config = json.loads((REPO_ROOT / "railway.json").read_text())
    dockerfile = (REPO_ROOT / config["build"]["dockerfilePath"]).read_text()
    command = dockerfile.split("CMD", 1)[1]
    assert "nfl_ask.web:create_production_app" in command and "--factory" in command
    assert "--no-access-log" in command
    assert "$PORT" in command or "${PORT" in command  # Railway picks the port


def test_the_container_installs_the_project_in_place():
    """Editable install: the catalog reads dbt_project/models from the repo next to the code."""
    config = json.loads((REPO_ROOT / "railway.json").read_text())
    dockerfile = (REPO_ROOT / config["build"]["dockerfilePath"]).read_text()
    assert re.search(r"pip install .*-e \.", dockerfile)
    assert "COPY . ." in dockerfile and (REPO_ROOT / ".dockerignore").exists()
