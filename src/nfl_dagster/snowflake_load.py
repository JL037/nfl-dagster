"""Load a local Parquet file into a Snowflake table: PUT to a stage, then COPY INTO.

This is the standard lake -> warehouse load. The Parquet file stays the source of truth,
and the Snowflake table can always be rebuilt from it.

Loads follow write-audit-publish: the new rows are written and audited inside one
transaction, and only committed (published) if every audit passes. Otherwise the
transaction rolls back and the table keeps its previous data.
"""

from collections.abc import Collection, Mapping
from pathlib import Path

STAGE = "RAW.RAW_STAGE"
FILE_FORMAT = "RAW.RAW_PARQUET"


class AuditFailed(Exception):
    """Raised when a load's audits find problems. Nothing was committed."""

    def __init__(self, table: str, results: Mapping[str, int], details: str = ""):
        self.table = table
        self.results = dict(results)
        failed = {name: n for name, n in results.items() if name != "rows_loaded" and n}
        message = f"RAW.{table} audits failed, load rolled back: {failed}"
        super().__init__(f"{message}. {details}" if details else message)


def column_differences(conn, table: str, file_columns: Collection[str]) -> dict[str, list[str]]:
    """Columns in the file but not the table, and in the table but not the file.

    Why this audit exists: COPY INTO with MATCH_BY_COLUMN_NAME never complains about a
    column mismatch. A column the table doesn't have is silently dropped, and a table column
    the file doesn't have is silently filled with NULL. The COPY still reports LOADED with
    zero errors and the right row count, so no other audit notices. If nflverse renamed
    passer_id, every new season would load with passer_id NULL and every QB mart would
    quietly lose those plays.

    The table's columns were fixed by the first file ever loaded (INFER_SCHEMA below), and
    IGNORE_CASE made them uppercase, so compare in uppercase.
    """
    table_columns = {
        row[0]
        for row in conn.cursor().execute(
            "select column_name from information_schema.columns"
            " where table_schema = 'RAW' and table_name = %s",
            (table,),
        ).fetchall()
    }
    file_columns = {c.upper() for c in file_columns}
    return {
        "columns_not_in_table": sorted(file_columns - table_columns),
        "columns_not_in_file": sorted(table_columns - file_columns),
    }


def load_parquet(
    conn,
    path: Path,
    table: str,
    season: int | None = None,
    expected_rows: int | None = None,
    audits: Mapping[str, str] | None = None,
    expected_columns: Collection[str] | None = None,
) -> dict[str, int]:
    """Replace one season of `table` (or the whole table if season is None) with `path`.

    `audits` maps a name to a SQL query that returns one number: how many rows are bad.
    Queries for a season get it as their only bind parameter (%s). They run after the copy,
    inside the transaction, so they see the new rows before anyone else can.

    `expected_columns` is the file's column names. If given, the table must have exactly
    those columns (see column_differences for why).

    Returns rows_loaded plus every audit's result. Raises AuditFailed (after rolling back)
    if any audit finds bad rows, rows_loaded != expected_rows, or the columns differ.
    """
    folder = table.lower()
    staged_file = f"@{STAGE}/{folder}/{path.name}"
    cur = conn.cursor()

    # Created on first use, so a fresh Snowflake account only needs snowflake/setup.sql.
    cur.execute(f"create file format if not exists {FILE_FORMAT} type = parquet")
    cur.execute(f"create stage if not exists {STAGE} file_format = {FILE_FORMAT}")

    # Upload the file. Parquet is already compressed, so don't gzip it again.
    cur.execute(
        f"put 'file://{path.resolve()}' @{STAGE}/{folder}/ overwrite = true auto_compress = false"
    )

    # First load only: create the table with the column names and types Snowflake reads
    # from the Parquet file itself. IGNORE_CASE makes the columns plain uppercase
    # identifiers (GAME_ID), so SQL doesn't need quotes around every column name.
    cur.execute(
        f"""
        create table if not exists RAW.{table}
        using template (
            select array_agg(object_construct(*)) within group (order by order_id)
            from table(infer_schema(
                location => '{staged_file}',
                file_format => '{FILE_FORMAT}',
                ignore_case => true
            ))
        )
        """
    )

    cur.execute("begin")
    try:
        # Write.
        if season is None:
            cur.execute(f"delete from RAW.{table}")
        else:
            cur.execute(f"delete from RAW.{table} where season = %s", (season,))
        # MATCH_BY_COLUMN_NAME lines Parquet columns up with table columns by name, not position.
        # FORCE: Snowflake skips files it already loaded in the last 64 days, even when we just
        # deleted their rows. Without FORCE a re-run would delete a season and load 0 rows.
        cur.execute(
            f"""
            copy into RAW.{table}
            from @{STAGE}/{folder}/
            files = ('{path.name}')
            file_format = (format_name = '{FILE_FORMAT}')
            match_by_column_name = case_insensitive
            force = true
            """
        )
        rows_loaded = sum(row[3] for row in cur.fetchall())  # columns: file, status, rows_parsed, rows_loaded, ...

        # Audit, before anything is visible outside this transaction.
        results = {"rows_loaded": rows_loaded}
        details = ""
        if expected_rows is not None:
            results["missing_or_extra_rows"] = abs(rows_loaded - expected_rows)
        if expected_columns is not None:
            differences = column_differences(conn, table, expected_columns)
            results.update({name: len(columns) for name, columns in differences.items()})
            # The counts go into Dagster metadata; the names are what you need to fix it.
            details = "; ".join(f"{name}: {cols}" for name, cols in differences.items() if cols)
        for name, sql in (audits or {}).items():
            params = (season,) if season is not None else None
            results[name] = cur.execute(sql, params).fetchone()[0]

        bad = {name: n for name, n in results.items() if name != "rows_loaded" and n}
        if bad or rows_loaded == 0:
            raise AuditFailed(table, results, details)

        # Publish.
        cur.execute("commit")
    except Exception:
        cur.execute("rollback")
        raise
    return results
