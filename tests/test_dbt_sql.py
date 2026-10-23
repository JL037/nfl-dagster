"""SQL habits that bit us in Snowflake and that CI (which never runs SQL) can still catch."""

import re
from pathlib import Path

import pytest

DBT = Path(__file__).parent.parent / "dbt_project"
SQL = sorted(p for folder in ("models", "macros", "tests") for p in (DBT / folder).rglob("*.sql"))


@pytest.mark.parametrize("path", SQL, ids=lambda p: str(p.relative_to(DBT)))
def test_trim_names_the_characters(path):
    """Snowflake's trim(x) strips only spaces: nflverse's "\\n    " practice statuses came out as
    "\\n", not empty, and failed stg_injuries' unit test in prod. Name the characters:
    trim(x, ' \\t\\n\\r')."""
    bare = re.findall(r"\b[lr]?trim\(\s*[^,()]+\)", path.read_text(), flags=re.IGNORECASE)
    assert not bare, f"{path.name}: {bare} strips spaces only; use trim(x, ' \\t\\n\\r')"
