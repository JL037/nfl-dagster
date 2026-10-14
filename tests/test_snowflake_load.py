"""Write-audit-publish in load_parquet, tested against a fake Snowflake connection.

The fake records every statement, so the tests can assert the exact order: the season is
deleted and copied inside a transaction, audits run before anything is committed, and a
failed audit rolls back instead of committing.
"""

from pathlib import Path

import pytest

from nfl_dagster.snowflake_load import AuditFailed, load_parquet


class FakeCursor:
    def __init__(self, rows_loaded: int, audit_results: dict[str, int]):
        self.rows_loaded = rows_loaded
        self.audit_results = audit_results
        self.statements: list[str] = []
        self._result = None

    def execute(self, sql, params=None):
        sql = " ".join(sql.split()).lower()
        self.statements.append(sql)
        if sql.startswith("copy into"):
            # COPY INTO returns one row per file: file, status, rows_parsed, rows_loaded, ...
            self._result = [("season=2025.parquet", "LOADED", self.rows_loaded, self.rows_loaded)]
        else:
            name = next((n for n in self.audit_results if f"-- {n}" in sql), None)
            self._result = [(self.audit_results[name],)] if name else []
        return self

    def fetchall(self):
        return self._result

    def fetchone(self):
        return self._result[0]


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


# Each audit query is tagged with a SQL comment so the fake knows which result to return.
AUDITS = {"duplicate_plays": "select 1 -- duplicate_plays"}


def run_load(rows_loaded: int, duplicate_plays: int, expected_rows: int = 100):
    cursor = FakeCursor(rows_loaded, {"duplicate_plays": duplicate_plays})
    try:
        result = load_parquet(
            FakeConnection(cursor),
            Path("season=2025.parquet"),
            "PBP",
            season=2025,
            expected_rows=expected_rows,
            audits=AUDITS,
        )
    except AuditFailed as e:
        return cursor.statements, e
    return cursor.statements, result


def position(statements, prefix):
    return next(i for i, s in enumerate(statements) if s.startswith(prefix))


def test_clean_load_audits_before_committing():
    statements, result = run_load(rows_loaded=100, duplicate_plays=0)
    assert result == {"rows_loaded": 100, "missing_or_extra_rows": 0, "duplicate_plays": 0}
    order = [position(statements, p) for p in ("begin", "delete", "copy into", "select 1", "commit")]
    assert order == sorted(order), "expected begin -> delete -> copy -> audit -> commit"
    assert not any(s.startswith("rollback") for s in statements)


def test_failed_audit_rolls_back_and_never_commits():
    statements, error = run_load(rows_loaded=101, duplicate_plays=1, expected_rows=101)
    assert isinstance(error, AuditFailed)
    assert error.results["duplicate_plays"] == 1
    assert "rollback" in statements
    assert "commit" not in statements


def test_row_count_mismatch_rolls_back():
    statements, error = run_load(rows_loaded=99, duplicate_plays=0, expected_rows=100)
    assert isinstance(error, AuditFailed)
    assert error.results["missing_or_extra_rows"] == 1
    assert "commit" not in statements


def test_empty_load_rolls_back():
    statements, error = run_load(rows_loaded=0, duplicate_plays=0, expected_rows=0)
    assert isinstance(error, AuditFailed)
    assert "commit" not in statements


def test_delete_is_scoped_to_the_season():
    statements, _ = run_load(rows_loaded=100, duplicate_plays=0)
    delete = statements[position(statements, "delete")]
    assert delete == "delete from raw.pbp where season = %s"
