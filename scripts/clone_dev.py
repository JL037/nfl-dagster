"""(Re)create the dev warehouse as a zero-copy clone of production.

    make clone-dev        # or: python scripts/clone_dev.py

`create or replace database NFL_DEV clone NFL` copies every schema, table, and view
instantly. The clone shares storage with production until either side changes, so it
costs nothing up front. Use it to reset dev whenever experiments leave it messy.

Production is never written: the target is hard-coded to the dev database, and the script
refuses to run if it would ever be the same as the source.
"""

import os
import sys

import snowflake.connector
from dotenv import load_dotenv

SOURCE = "NFL"
TARGET = "NFL_DEV"


def main() -> None:
    if TARGET == SOURCE or not TARGET.endswith("_DEV"):
        sys.exit(f"Refusing to replace {TARGET!r}: only a *_DEV database can be recreated.")

    load_dotenv()  # same .env as Dagster and dbt
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key_file=os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"],
        role=os.environ["SNOWFLAKE_ROLE"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
    )
    with conn:
        cur = conn.cursor()
        cur.execute(f"create or replace database {TARGET} clone {SOURCE}")
        tables = cur.execute(
            f"select table_schema, count(*) from {TARGET}.information_schema.tables"
            " where table_schema <> 'INFORMATION_SCHEMA' group by 1 order by 1"
        ).fetchall()
    print(f"{TARGET} recreated as a clone of {SOURCE}: " + ", ".join(f"{s} ({n})" for s, n in tables))


if __name__ == "__main__":
    main()
