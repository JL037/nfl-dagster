"""dbt unit tests run only in Snowflake (inside dbt build), which CI doesn't reach. One mistake
CI can catch: dbt turns a fixture's rows into a UNION, and Snowflake rejects a union whose rows
list different columns ("invalid number of result columns for set operator"). That failed the
first prod build of player_careers. So every fixture's rows must list the same columns."""

from pathlib import Path

import pytest
import yaml

MODELS = Path(__file__).parent.parent / "dbt_project" / "models"


def unit_tests():
    for path in sorted(MODELS.rglob("*.yml")):
        for test in (yaml.safe_load(path.read_text()) or {}).get("unit_tests", []):
            yield pytest.param(test, id=test["name"])


@pytest.mark.parametrize("test", unit_tests())
def test_fixture_rows_list_the_same_columns(test):
    fixtures = {f"given {g['input']}": g.get("rows", []) for g in test.get("given", [])}
    fixtures["expect"] = test.get("expect", {}).get("rows", [])
    for name, rows in fixtures.items():
        if not isinstance(rows, list):
            continue  # format: sql or csv, written as one block: dbt doesn't union row by row
        columns = {tuple(sorted(row)) for row in rows}
        assert len(columns) <= 1, f"{name}: rows list different columns: {sorted(columns)}"
