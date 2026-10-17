"""Write-audit-publish in load_parquet, tested against a fake Snowflake connection.

The fake records every statement, so the tests can assert the exact order: the season is
deleted and copied inside a transaction, audits run before anything is committed, and a
failed audit rolls back instead of committing.
"""

from pathlib import Path

import pytest

from nfl_dagster.snowflake_load import AuditFailed, load_parquet


# The columns RAW.PBP has in the fake warehouse, as Snowflake stores them (uppercase).
TABLE_COLUMNS = ["SEASON", "GAME_ID", "PLAY_ID", "PASSER_ID"]


class FakeCursor:
    def __init__(self, rows_loaded: int, audit_results: dict[str, int],
                 table_columns: list[str] = TABLE_COLUMNS):
        self.rows_loaded = rows_loaded
        self.audit_results = audit_results
        self.table_columns = table_columns
        self.statements: list[str] = []
        self._result = None

    def execute(self, sql, params=None):
        sql = " ".join(sql.split()).lower()
        self.statements.append(sql)
        if sql.startswith("copy into"):
            # COPY INTO returns one row per file: file, status, rows_parsed, rows_loaded, ...
            self._result = [("season=2025.parquet", "LOADED", self.rows_loaded, self.rows_loaded)]
        elif "information_schema.columns" in sql:
            self._result = [(c,) for c in self.table_columns]
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


def run_load(rows_loaded: int, duplicate_plays: int, expected_rows: int = 100,
             expected_columns: list[str] | None = None):
    cursor = FakeCursor(rows_loaded, {"duplicate_plays": duplicate_plays})
    try:
        result = load_parquet(
            FakeConnection(cursor),
            Path("season=2025.parquet"),
            "PBP",
            season=2025,
            expected_rows=expected_rows,
            audits=AUDITS,
            expected_columns=expected_columns,
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


# Column checks. In real Snowflake, a COPY with MATCH_BY_COLUMN_NAME succeeds when the columns
# don't match: extra file columns are dropped and missing ones load as NULL (tried on a
# temporary table: status LOADED, 0 errors). So the load has to compare columns itself.
# The file's names are lowercase (nflverse); the table's are uppercase.
FILE_COLUMNS = ["season", "game_id", "play_id", "passer_id"]


def test_matching_columns_commit():
    statements, result = run_load(rows_loaded=100, duplicate_plays=0, expected_columns=FILE_COLUMNS)
    assert result["columns_not_in_table"] == 0
    assert result["columns_not_in_file"] == 0
    assert "commit" in statements


def test_new_column_in_file_rolls_back():
    """nflverse adds a column: Snowflake would silently drop it on every load."""
    statements, error = run_load(
        rows_loaded=100, duplicate_plays=0, expected_columns=FILE_COLUMNS + ["new_stat"]
    )
    assert isinstance(error, AuditFailed)
    assert error.results["columns_not_in_table"] == 1
    assert "NEW_STAT" in str(error)
    assert "commit" not in statements


def test_renamed_column_rolls_back():
    """nflverse renames passer_id: Snowflake would load passer_id as NULL and drop the new name."""
    renamed = ["season", "game_id", "play_id", "passer_player_id"]
    statements, error = run_load(rows_loaded=100, duplicate_plays=0, expected_columns=renamed)
    assert isinstance(error, AuditFailed)
    assert error.results == {
        "rows_loaded": 100,
        "missing_or_extra_rows": 0,  # the row count looks fine, so only this audit catches it
        "duplicate_plays": 0,
        "columns_not_in_table": 1,
        "columns_not_in_file": 1,
    }
    assert "PASSER_PLAYER_ID" in str(error) and "PASSER_ID" in str(error)
    assert "commit" not in statements


def test_column_check_runs_before_commit():
    statements, _ = run_load(rows_loaded=100, duplicate_plays=0, expected_columns=FILE_COLUMNS)
    check = next(i for i, s in enumerate(statements) if "information_schema.columns" in s)
    assert position(statements, "copy into") < check < position(statements, "commit")


def test_raw_assets_pass_their_columns(monkeypatch):
    """The audit only runs if the caller passes expected_columns, so check that raw.py does."""
    from contextlib import contextmanager

    import polars as pl

    from nfl_dagster.assets import raw

    calls = {}

    def fake_load_parquet(conn, path, table, season=None, **kwargs):
        calls.update(kwargs)
        return {"rows_loaded": 1}

    class FakeSnowflake:
        @contextmanager
        def get_connection(self):
            yield None

    monkeypatch.setattr(raw, "load_parquet", fake_load_parquet)
    df = pl.DataFrame({"season": [2025], "game_id": ["g"]})
    metadata = raw.load_to_snowflake(FakeSnowflake(), df, Path("season=2025.parquet"), "PBP", 2025)
    assert calls["expected_columns"] == ["season", "game_id"]
    # The label names the database NFL_ENV chose (NFL_DEV in tests), not a hard-coded NFL.
    assert metadata["snowflake_table"].value == f"{raw.SNOWFLAKE_DATABASE}.RAW.PBP"
    assert raw.SNOWFLAKE_DATABASE == "NFL_DEV"
