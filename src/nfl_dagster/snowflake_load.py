"""Load a local Parquet file into a Snowflake table: PUT to a stage, then COPY INTO.

This is the standard lake -> warehouse load. The Parquet file stays the source of truth,
and the Snowflake table can always be rebuilt from it.
"""

from pathlib import Path

STAGE = "RAW.RAW_STAGE"
FILE_FORMAT = "RAW.RAW_PARQUET"


def load_parquet(conn, path: Path, table: str, season: int | None = None) -> int:
    """Replace one season of `table` (or the whole table if season is None) with `path`.

    Returns the number of rows loaded. Safe to re-run: it deletes before it copies, inside
    one transaction, so a failed load leaves the previous data in place.
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
        cur.execute("commit")
    except Exception:
        cur.execute("rollback")
        raise
    return rows_loaded
