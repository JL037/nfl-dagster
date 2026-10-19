"""The Ask page's only path to the data: validate_sql() and run_query().

The validator tests need no database and run in CI. The integration tests at the bottom run
against the dev serving database and prove the database itself refuses writes inside the
read-only transaction, even when the validator is bypassed. CI has no database, so they skip.
"""

import os

import pytest

from nfl_ask.query import QueryRejected, run_query, validate_sql


# What the LLM is expected to write: one SELECT over the served marts, values as %s.
@pytest.mark.parametrize(
    "sql",
    [
        "select passer_name, epa_over_expected from marts.qb_contract_value where season = 2025",
        "select * from qb_contract_value where passer_name = %s",  # search_path is marts
        "with best as (select * from marts.qb_contract_value where worth_it)"
        " select passer_name from best order by epa_over_expected desc limit 5",
        "select a.passer_name from marts.qb_season_epa a join marts.qb_contract_value b"
        " using (qb_season_key) where a.season = %s",
        "select table_name, published_at from marts._publications",
        # A wildcard alone carries no trace of the question; the name stays a parameter.
        "select * from qb_contract_value where passer_name ilike '%' || %s || '%'",
    ],
)
def test_accepts_one_select_over_the_marts(sql):
    validate_sql(sql)


@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("insert into marts.qb_contract_value (season) values (2025)", "SELECT"),
        ("delete from marts.qb_contract_value", "SELECT"),
        ("drop table marts.qb_contract_value", "SELECT"),
        ("update marts.qb_season_epa set dropbacks = 0", "SELECT"),
        # Writes hidden inside a SELECT: a data-modifying CTE, and SELECT ... INTO a new table.
        ("with d as (delete from marts.qb_season_epa returning *) select * from d", "SELECT"),
        ("select * into marts.copy from marts.qb_season_epa", "SELECT"),
        # Stacked statements: the second could undo the read-only transaction.
        ("select 1; set transaction read write", "one statement"),
        ("select * from marts.qb_season_epa; drop table marts.qb_season_epa", "one statement"),
        # Anything outside the served marts.
        ("select * from pg_catalog.pg_tables", "marts"),
        ("select * from information_schema.tables", "marts"),
        ("select query_sample from ppg.query_stats", "marts"),
        ("select * from public.anything", "marts"),
        # Text typed into the SQL would be kept verbatim in Prisma's query log.
        ("select * from marts.qb_contract_value where passer_name = 'D.Maye'", "bound parameter"),
        ("select * from marts.qb_contract_value where passer_name like '%Maye%'", "bound parameter"),
        ("", "one statement"),
    ],
)
def test_rejects(sql, reason):
    with pytest.raises(QueryRejected, match=reason):
        validate_sql(sql)


def test_a_cte_name_is_not_a_table_outside_the_marts():
    """CTE names look like unqualified tables to the parser; they must not be rejected."""
    validate_sql("with x as (select 1 as n) select n from x")


# --- Integration: the dev serving database ----------------------------------------------

DEV_URL = os.environ.get("SERVING_DB_URL_DEV", "")
needs_db = pytest.mark.skipif(
    not DEV_URL.startswith("postgres"), reason="no dev serving database (CI)"
)


@pytest.fixture
def conn():
    import psycopg

    with psycopg.connect(DEV_URL, autocommit=True, connect_timeout=15) as connection:
        yield connection


@needs_db
def test_runs_a_query_with_bound_values(conn):
    result = run_query(
        conn,
        "select passer_name, round(epa_over_expected::numeric, 3) from qb_contract_value"
        " where season = 2025 and passer_name = %s",
        ["D.Maye"],
    )
    assert result.columns == ["passer_name", "round"]
    assert result.rows == [("D.Maye", pytest.approx(0.295, abs=0.001))]
    assert result.truncated is False


@needs_db
def test_row_cap_truncates_and_says_so(conn):
    result = run_query(conn, "select game_id from game_results_vs_spread", [], max_rows=10)
    assert len(result.rows) == 10
    assert result.truncated is True


@needs_db
def test_database_refuses_writes_even_when_the_validator_is_bypassed(conn):
    """Defense in depth: skip validate_sql() and the read-only transaction still holds."""
    with pytest.raises(Exception, match="read-only transaction"):
        run_query(conn, "create table marts.should_not_exist (x int)", [], validate=False)
    exists = conn.execute(
        "select count(*) from pg_tables where schemaname = 'marts' and tablename = 'should_not_exist'"
    ).fetchone()[0]
    assert exists == 0


@needs_db
def test_statement_timeout_stops_a_slow_query(conn):
    with pytest.raises(Exception, match="statement timeout"):
        run_query(conn, "select pg_sleep(5)", [], validate=False, timeout_ms=500)


@needs_db
def test_cannot_switch_back_to_read_write(conn):
    """run_query() runs `select 1` before anything else: Postgres only locks a transaction as
    read-only once a statement takes a snapshot, and SET statements don't."""
    with pytest.raises(Exception, match="must be set before any query"):
        run_query(conn, "set transaction read write", [], validate=False)
