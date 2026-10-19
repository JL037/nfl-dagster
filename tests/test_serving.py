"""Publishing a mart to the serving database, tested against a fake Postgres connection.

publish_table() is write-audit-publish, like load_parquet(): the new rows go into a hidden
staging table, are counted, and only then replace the served table, all in one transaction.
Postgres runs DDL inside transactions, so a reader sees the old table or the new one, never
a half-built one. A failed audit rolls back and the old table keeps serving.
"""

import pytest

from nfl_dagster.serving import PublishFailed, postgres_type, publish_table

COLUMNS = [("qb_season_key", "text"), ("season", "bigint"), ("epa_per_dropback", "double precision")]
ROWS = [("P1-2025", 2025, 0.3), ("P2-2025", 2025, -0.1)]


class FakeCursor:
    def __init__(self, staged_rows: int):
        self.staged_rows = staged_rows
        self.statements: list[str] = []
        self.inserted: list[tuple] = []
        self._result = None

    def execute(self, sql, params=None):
        sql = " ".join(sql.split()).lower()
        self.statements.append(sql)
        self._result = [(self.staged_rows,)] if sql.startswith("select count(*)") else []
        return self

    def executemany(self, sql, rows):
        self.statements.append(" ".join(sql.split()).lower())
        self.inserted.extend(rows)

    def fetchone(self):
        return self._result[0]


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


def run_publish(staged_rows: int, rows=ROWS, table="qb_contract_value"):
    cursor = FakeCursor(staged_rows)
    try:
        result = publish_table(FakeConnection(cursor), table, COLUMNS, rows, source="NFL_DEV.MARTS.QB_CONTRACT_VALUE")
    except PublishFailed as e:
        return cursor.statements, e
    return cursor.statements, result


def position(statements, prefix):
    return next(i for i, s in enumerate(statements) if s.startswith(prefix))


def test_clean_publish_audits_before_swapping_and_committing():
    statements, result = run_publish(staged_rows=2)
    assert result == {"rows_published": 2}
    order = [
        position(statements, p)
        for p in (
            "begin",
            "create table marts._staging_qb_contract_value",
            "insert into marts._staging_qb_contract_value",
            "select count(*) from marts._staging_qb_contract_value",
            "drop table if exists marts.qb_contract_value",
            "alter table marts._staging_qb_contract_value rename to qb_contract_value",
            "insert into marts._publications",
            "commit",
        )
    ]
    assert order == sorted(order), "expected begin -> stage -> audit -> swap -> record -> commit"
    assert "rollback" not in statements


def test_short_staging_table_rolls_back_and_keeps_the_served_table():
    """Fewer rows landed than Snowflake has: the served table must not be touched."""
    statements, error = run_publish(staged_rows=1)
    assert isinstance(error, PublishFailed)
    assert "rollback" in statements
    assert "commit" not in statements
    assert not any(s.startswith("drop table if exists marts.qb_contract_value") for s in statements)
    assert not any(" rename to " in s for s in statements)


def test_empty_mart_is_never_published():
    """An empty mart would make every answer 'no data'; keep serving the previous one."""
    statements, error = run_publish(staged_rows=0, rows=[])
    assert isinstance(error, PublishFailed)
    assert "commit" not in statements


def test_staging_table_has_the_marts_columns_and_rows():
    cursor = FakeCursor(staged_rows=2)
    publish_table(FakeConnection(cursor), "qb_contract_value", COLUMNS, ROWS, source="x")
    create = cursor.statements[position(cursor.statements, "create table marts._staging")]
    assert "qb_season_key text" in create and "epa_per_dropback double precision" in create
    assert cursor.inserted == ROWS


def test_publication_is_recorded_with_bound_values():
    """The 'how fresh is this data' line in the UI reads marts._publications."""
    statements, _ = run_publish(staged_rows=2)
    record = statements[position(statements, "insert into marts._publications")]
    assert "%s" in record and "qb_contract_value" not in record


def test_unsafe_table_name_is_refused_before_any_sql():
    with pytest.raises(ValueError):
        run_publish(staged_rows=2, table="qb; drop table marts.x")


@pytest.mark.parametrize(
    ("snowflake", "precision", "scale", "expected"),
    [
        ("NUMBER", 38, 0, "bigint"),
        ("NUMBER", 38, 6, "numeric(38, 6)"),
        ("FLOAT", None, None, "double precision"),
        ("TEXT", None, None, "text"),
        ("BOOLEAN", None, None, "boolean"),
        ("DATE", None, None, "date"),
        ("TIMESTAMP_NTZ", None, None, "timestamp"),
        ("TIMESTAMP_TZ", None, None, "timestamptz"),
    ],
)
def test_snowflake_types_map_to_postgres(snowflake, precision, scale, expected):
    assert postgres_type(snowflake, precision, scale) == expected


def test_unknown_snowflake_type_fails_loudly():
    """A VARIANT in a mart has no obvious Postgres type; fail rather than guess."""
    with pytest.raises(ValueError, match="VARIANT"):
        postgres_type("VARIANT", None, None)
