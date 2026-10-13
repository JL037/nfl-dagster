import dagster as dg
import duckdb

from nfl_dagster.assets.raw import raw_pbp, raw_schedules, season_path
from nfl_dagster.partitions import season_partitions

# Checks open their own in-memory DuckDB connection and read the Parquet file directly,
# instead of using the shared `duckdb` resource. Only dbt writes to data/nfl.duckdb, and
# DuckDB allows one writing process at a time, so the checks stay out of its way.
#
# partitions_def makes each check run per season, against only that season's file.
# blocking=True means: if the check fails during a run, steps downstream of the asset
# in that same run are skipped.


@dg.asset_check(asset=raw_pbp, partitions_def=season_partitions, blocking=True)
def raw_pbp_unique_plays(context: dg.AssetCheckExecutionContext) -> dg.AssetCheckResult:
    """Every (game_id, play_id) appears once in the season's play-by-play."""
    season = int(context.partition_key)
    path = season_path("pbp", season)
    total_rows, duplicate_rows = duckdb.connect().sql(
        f"""
        select count(*), count(*) - count(distinct (game_id, play_id))
        from read_parquet('{path}')
        """
    ).fetchone()
    return dg.AssetCheckResult(
        passed=duplicate_rows == 0,
        metadata={"season": season, "total_rows": total_rows, "duplicate_rows": duplicate_rows},
    )


@dg.asset_check(asset=raw_schedules, partitions_def=season_partitions, blocking=True)
def raw_schedules_scores_present(context: dg.AssetCheckExecutionContext) -> dg.AssetCheckResult:
    """home_score and away_score are both set (game played) or both null (not played yet)."""
    season = int(context.partition_key)
    path = season_path("schedules", season)
    games, played, unplayed, mismatched = duckdb.connect().sql(
        f"""
        select
            count(*),
            count(*) filter (where home_score is not null and away_score is not null),
            count(*) filter (where home_score is null and away_score is null),
            count(*) filter (where (home_score is null) <> (away_score is null))
        from read_parquet('{path}')
        """
    ).fetchone()
    return dg.AssetCheckResult(
        passed=mismatched == 0,
        metadata={
            "season": season,
            "games": games,
            "played": played,
            "unplayed": unplayed,
            "mismatched": mismatched,
        },
    )
