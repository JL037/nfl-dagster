"""Publish a finished mart to the serving database (Prisma Postgres), write-audit-publish.

The website and its LLM read only this database, never Snowflake: visitors cost no warehouse
time, Snowflake credentials stay out of the app, and the site keeps working if Snowflake is
down. Snowflake builds and tests the answers; Postgres serves them.

Like load_parquet(), a publish is one transaction: the rows go into a hidden staging table,
are counted, and only then replace the served table. Postgres runs DDL inside transactions,
so readers see the old table or the new one, never a half-built one. A failed audit rolls
back, and the previous table keeps serving.
"""

import re
from collections.abc import Sequence
from contextlib import contextmanager

import dagster as dg

SCHEMA = "marts"
# Read by the website for "how fresh is this data": one row per served table.
PUBLICATIONS = f"{SCHEMA}._publications"

# Table and column names are interpolated into SQL (identifiers can't be bound parameters),
# so only plain lowercase names are allowed.
IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


class PublishFailed(Exception):
    """Raised when a publish's audit fails. Nothing was committed; the old table still serves."""


def postgres_type(snowflake_type: str, precision: int | None, scale: int | None) -> str:
    """The Postgres type for a Snowflake column type, as information_schema reports it.

    Only the types the marts use. Anything else fails, rather than being guessed at.
    """
    if snowflake_type == "NUMBER":
        return "bigint" if not scale else f"numeric({precision}, {scale})"
    simple = {
        "FLOAT": "double precision",
        "TEXT": "text",
        "BOOLEAN": "boolean",
        "DATE": "date",
        "TIMESTAMP_NTZ": "timestamp",
        "TIMESTAMP_TZ": "timestamptz",
        "TIMESTAMP_LTZ": "timestamptz",
    }
    if snowflake_type not in simple:
        raise ValueError(f"No Postgres type mapped for Snowflake type {snowflake_type}")
    return simple[snowflake_type]


def check_identifier(name: str) -> str:
    if not IDENTIFIER.match(name):
        raise ValueError(f"Not a plain lowercase identifier: {name!r}")
    return name


def publish_table(
    conn, table: str, columns: Sequence[tuple[str, str]], rows: Sequence[tuple], source: str
) -> dict[str, int]:
    """Replace marts.<table> in the serving database with `rows`, or change nothing.

    `columns` is (name, Postgres type) pairs in row order. `source` names where the rows came
    from (the Snowflake table), recorded with the publication.
    """
    table = check_identifier(table)
    names = [check_identifier(name) for name, _ in columns]
    staging = f"_staging_{table}"
    cur = conn.cursor()

    cur.execute("begin")
    try:
        # Write, into a table nobody reads.
        cur.execute(f"create schema if not exists {SCHEMA}")
        cur.execute(f"drop table if exists {SCHEMA}.{staging}")
        cur.execute(
            f"create table {SCHEMA}.{staging} ("
            + ", ".join(f"{name} {pg_type}" for name, pg_type in columns)
            + ")"
        )
        placeholders = ", ".join(["%s"] * len(names))
        cur.executemany(
            f"insert into {SCHEMA}.{staging} ({', '.join(names)}) values ({placeholders})", rows
        )

        # Audit: every row from Snowflake landed, and there is something to serve. An empty
        # mart would turn every answer into "no data", so the previous table keeps serving.
        staged = cur.execute(f"select count(*) from {SCHEMA}.{staging}").fetchone()[0]
        if staged != len(rows) or staged == 0:
            raise PublishFailed(
                f"{SCHEMA}.{table}: staged {staged} rows, expected {len(rows)}; nothing published"
            )

        # Publish: swap the staging table in, and record when.
        cur.execute(f"drop table if exists {SCHEMA}.{table}")
        cur.execute(f"alter table {SCHEMA}.{staging} rename to {table}")
        cur.execute(
            f"create table if not exists {PUBLICATIONS} ("
            "table_name text primary key, row_count bigint, source text, published_at timestamptz)"
        )
        cur.execute(
            f"insert into {PUBLICATIONS} (table_name, row_count, source, published_at)"
            " values (%s, %s, %s, now())"
            " on conflict (table_name) do update set row_count = excluded.row_count,"
            " source = excluded.source, published_at = excluded.published_at",
            (table, staged, source),
        )
        cur.execute("commit")
    except Exception:
        cur.execute("rollback")
        raise
    return {"rows_published": staged}


class ServingPostgresResource(dg.ConfigurableResource):
    """A connection to the serving database. `url` is a direct (not pooled) Postgres URL:
    a publish is one transaction, and a pooler may send each statement to a different
    connection."""

    url: str

    @contextmanager
    def get_connection(self):
        import psycopg

        # autocommit: the transaction is opened and closed explicitly by publish_table().
        with psycopg.connect(self.url, autocommit=True, connect_timeout=15) as conn:
            yield conn
