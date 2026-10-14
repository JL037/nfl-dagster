import dagster as dg
import nflreadpy as nfl
import polars as pl
from dagster_snowflake import SnowflakeResource
from tabulate import tabulate

from nfl_dagster.partitions import season_partitions
from nfl_dagster.resources import REPO_ROOT
from nfl_dagster.snowflake_load import AuditFailed, load_parquet

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


# Audits run inside the load transaction, before the new rows are committed (see
# snowflake_load.py). Each query counts bad rows in the season just loaded; any non-zero
# count rolls the load back. The asset checks in checks.py test the same rules, but after
# the fact, as the per-season report in the UI.
AUDITS = {
    "PBP": {
        "duplicate_plays": (
            "select count(*) - count(distinct game_id, play_id) from RAW.PBP where season = %s"
        ),
    },
    "SCHEDULES": {
        "mismatched_scores": (
            "select count_if((home_score is null) <> (away_score is null))"
            " from RAW.SCHEDULES where season = %s"
        ),
    },
}


def load_to_snowflake(snowflake: SnowflakeResource, df: pl.DataFrame, path, table: str,
                      season: int | None = None) -> dict:
    """Load the Parquet file into RAW.<table> (write-audit-publish) and return metadata.

    If an audit fails, the load is rolled back, so Snowflake keeps its previous data, and
    the asset raises. A failed asset records no materialization, so automation downstream
    never sees an "update" to react to.
    """
    with snowflake.get_connection() as conn:
        try:
            results = load_parquet(
                conn, path, table, season, expected_rows=df.height, audits=AUDITS.get(table)
            )
        except AuditFailed as e:
            raise dg.Failure(
                description=str(e),
                metadata={name: dg.MetadataValue.int(n) for name, n in e.results.items()},
            ) from e
    return {
        "snowflake_table": dg.MetadataValue.text(f"NFL.RAW.{table}"),
        **{name: dg.MetadataValue.int(n) for name, n in results.items()},
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
