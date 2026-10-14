import dagster as dg
import nflreadpy as nfl
import polars as pl
from dagster_snowflake import SnowflakeResource
from tabulate import tabulate

from nfl_dagster.partitions import season_partitions
from nfl_dagster.resources import REPO_ROOT
from nfl_dagster.snowflake_load import load_parquet

RAW_DIR = REPO_ROOT / "data" / "raw"

# pbp has 372 columns; preview just the ones that tell you what happened on the play.
PBP_PREVIEW_COLUMNS = [
    "game_id", "play_id", "week", "posteam", "defteam", "play_type", "epa", "success",
]
SCHEDULES_PREVIEW_COLUMNS = [
    "game_id", "week", "away_team", "away_score", "home_team", "home_score",
    "spread_line", "total_line",
]


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


def load_to_snowflake(snowflake: SnowflakeResource, df: pl.DataFrame, path, table: str,
                      season: int | None = None) -> dict:
    """Load the Parquet file into RAW.<table> and return metadata about the load.

    Raises if Snowflake loaded a different number of rows than the file has, so a silent
    partial load fails the run instead of showing up later as wrong numbers.
    """
    with snowflake.get_connection() as conn:
        rows_loaded = load_parquet(conn, path, table, season)
    if rows_loaded != df.height:
        raise dg.Failure(f"RAW.{table}: loaded {rows_loaded} rows, expected {df.height}")
    return {
        "snowflake_table": dg.MetadataValue.text(f"NFL.RAW.{table}"),
        "rows_loaded": dg.MetadataValue.int(rows_loaded),
    }


# The asset key comes from the function name: `raw_teams`. That's the same key the dbt
# source `raw.teams` declares in sources.yml, so Dagster links them: raw_teams -> stg_teams.
@dg.asset(group_name="raw", kinds={"python", "parquet", "snowflake"})
def raw_teams(snowflake: SnowflakeResource) -> dg.MaterializeResult:
    """One row per NFL team, from nflreadpy.load_teams()."""
    df = nfl.load_teams()

    path = RAW_DIR / "teams.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)

    # We wrote the file ourselves, so there's no return value for an IO manager to store;
    # MaterializeResult just records that the asset was materialized, plus metadata.
    return dg.MaterializeResult(
        metadata={**parquet_metadata(df, path), **load_to_snowflake(snowflake, df, path, "TEAMS")}
    )


def season_path(name: str, season: int):
    """data/raw/<name>/season=YYYY.parquet, shared by the raw assets and their checks."""
    return RAW_DIR / name / f"season={season}.parquet"


def write_season(df: pl.DataFrame, name: str, season: int, preview_columns: list[str],
                 snowflake: SnowflakeResource):
    """Write one season to data/raw/<name>/season=YYYY.parquet and return its metadata.

    One file per season means re-running a partition overwrites exactly its own file,
    and the Snowflake load replaces exactly that season's rows in RAW.<NAME>.
    """
    path = season_path(name, season)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)
    return {
        **parquet_metadata(df, path, preview_columns),
        **load_to_snowflake(snowflake, df, path, name.upper(), season),
    }


# partitions_def splits this asset into one slice per season ("2016" ... "2026").
# Each run materializes a single partition, and the UI tracks every season separately.
@dg.asset(partitions_def=season_partitions, group_name="raw", kinds={"python", "parquet", "snowflake"})
def raw_pbp(context: dg.AssetExecutionContext, snowflake: SnowflakeResource) -> dg.MaterializeResult:
    """Play-by-play for one season, from nflreadpy.load_pbp(). One row per play."""
    # The partition key is always a string, so convert it before handing it to nflreadpy.
    season = int(context.partition_key)
    df = nfl.load_pbp([season])
    # goal_to_go is the only column whose type changes between seasons (Int32 in 7 seasons,
    # Float64 in 2020 and 2024-2026). The Snowflake table takes its types from the first file
    # loaded, so pin this one to Float64 so every season's file agrees.
    df = df.with_columns(pl.col("goal_to_go").cast(pl.Float64))
    return dg.MaterializeResult(
        metadata=write_season(df, "pbp", season, PBP_PREVIEW_COLUMNS, snowflake)
    )


@dg.asset(partitions_def=season_partitions, group_name="raw", kinds={"python", "parquet", "snowflake"})
def raw_schedules(context: dg.AssetExecutionContext, snowflake: SnowflakeResource) -> dg.MaterializeResult:
    """Schedule and results for one season, from nflreadpy.load_schedules(). One row per game."""
    season = int(context.partition_key)
    df = nfl.load_schedules([season])
    return dg.MaterializeResult(
        metadata=write_season(df, "schedules", season, SCHEDULES_PREVIEW_COLUMNS, snowflake)
    )
