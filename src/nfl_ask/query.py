"""The only path from the Ask page's LLM to the data.

Every rule agreed for the website is enforced here, in two layers:

1. validate_sql() parses the query before it runs: exactly one SELECT, reading only the served
   marts, with every text value as a bound parameter (%s). Text typed into the SQL would be
   kept verbatim in Prisma's query statistics (ppg.query_stats), a trace of the question.
2. run_query() runs it inside a READ ONLY transaction, with a statement timeout and a row cap.
   Postgres itself refuses any write there, so even a query that slips past the validator
   can't change anything (Prisma Postgres doesn't allow a separate read-only database user).
"""

from dataclasses import dataclass
from decimal import Decimal

import sqlglot
from sqlglot import exp

SCHEMA = "marts"
# Statement types that change something. None may appear anywhere in the query, including
# inside a CTE (Postgres allows `with d as (delete ... returning *) select ...`).
WRITES = (exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop, exp.Alter,
          exp.Command, exp.Set, exp.Into)


class QueryRejected(ValueError):
    """The query broke a rule; it was never sent to the database."""


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    truncated: bool  # more rows existed than max_rows


def validate_sql(sql: str) -> None:
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except sqlglot.errors.ParseError as e:
        raise QueryRejected(f"Could not parse the SQL: {e}") from e
    if len(statements) != 1:
        raise QueryRejected(f"Exactly one statement is allowed, got {len(statements)}")
    tree = statements[0]

    if not isinstance(tree, exp.Query) or any(isinstance(n, WRITES) for n in tree.walk()):
        raise QueryRejected("Only a SELECT is allowed")

    ctes = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if not table.db and not table.catalog and table.name in ctes:
            continue
        if table.catalog or table.db not in ("", SCHEMA):
            raise QueryRejected(
                f"Only tables in the {SCHEMA} schema can be read, not {table.sql(dialect='postgres')}"
            )

    for literal in tree.find_all(exp.Literal):
        if literal.is_string:
            raise QueryRejected(
                f"Text values must be a bound parameter (%s), not typed into the SQL: {literal.sql()}"
            )


def run_query(conn, sql: str, params=(), *, max_rows: int = 200, timeout_ms: int = 3000,
              validate: bool = True) -> QueryResult:
    """Run one read-only query on `conn` (an autocommit psycopg connection).

    `validate=False` exists only so tests can prove the database layer on its own.
    """
    if validate:
        validate_sql(sql)
    cur = conn.cursor()
    cur.execute("begin read only")
    try:
        # Our statements go first. `select 1` takes the transaction's snapshot: from then on
        # Postgres refuses `set transaction read write` (SET alone takes no snapshot).
        cur.execute("select 1")
        cur.execute(f"set local statement_timeout = {int(timeout_ms)}")
        cur.execute(f"set local search_path = {SCHEMA}")
        cur.execute(sql, params or None)
        columns = [column.name for column in cur.description]
        fetched = cur.fetchmany(max_rows + 1)
    finally:
        cur.execute("rollback")  # read-only: there is never anything to commit
    rows = [
        tuple(float(v) if isinstance(v, Decimal) else v for v in row) for row in fetched[:max_rows]
    ]
    return QueryResult(columns=columns, rows=rows, truncated=len(fetched) > max_rows)
