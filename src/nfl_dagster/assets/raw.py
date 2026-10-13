import dagster as dg
import nflreadpy as nfl
import polars as pl
from tabulate import tabulate

from nfl_dagster.resources import REPO_ROOT

RAW_DIR = REPO_ROOT / "data" / "raw"


def parquet_metadata(df: pl.DataFrame, path, preview_columns: list[str] | None = None) -> dict:
    """Metadata shown on the asset page after each materialization."""
    preview = df.select(preview_columns) if preview_columns else df
    return {
        "path": dg.MetadataValue.path(str(path)),
        "row_count": dg.MetadataValue.int(df.height),
        "column_count": dg.MetadataValue.int(df.width),
        "preview": dg.MetadataValue.md(
            tabulate(preview.head(5).rows(), headers=preview.columns, tablefmt="github")
        ),
    }


# The asset key comes from the function name: `raw_teams`. That's the same key the dbt
# source `raw.teams` declares in sources.yml, so Dagster links them: raw_teams -> stg_teams.
@dg.asset(group_name="raw", kinds={"python", "parquet"})
def raw_teams() -> dg.MaterializeResult:
    """One row per NFL team, from nflreadpy.load_teams()."""
    df = nfl.load_teams()

    path = RAW_DIR / "teams.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)

    # We wrote the file ourselves, so there's no return value for an IO manager to store;
    # MaterializeResult just records that the asset was materialized, plus metadata.
    return dg.MaterializeResult(metadata=parquet_metadata(df, path))
