import dagster as dg
from dagster_snowflake import SnowflakeResource

from nfl_dagster.assets.raw import raw_pbp, raw_schedules
from nfl_dagster.partitions import season_partitions

# The checks query the Snowflake raw tables through the same `snowflake` resource the
# assets load with. That checks what the warehouse actually holds (what dbt will read),
# not just the local Parquet file.
#
# partitions_def makes each check run per season, filtering to only that season's rows.
# blocking=True means: if the check fails during a run, steps downstream of the asset
# in that same run are skipped.


@dg.asset_check(asset=raw_pbp, partitions_def=season_partitions, blocking=True)
def raw_pbp_unique_plays(
    context: dg.AssetCheckExecutionContext, snowflake: SnowflakeResource
) -> dg.AssetCheckResult:
    """Every (game_id, play_id) appears once in the season's play-by-play."""
    season = int(context.partition_key)
    with snowflake.get_connection() as conn:
        total_rows, duplicate_rows = conn.cursor().execute(
            """
            select count(*), count(*) - count(distinct game_id, play_id)
            from RAW.PBP
            where season = %s
            """,
            (season,),
        ).fetchone()
    return dg.AssetCheckResult(
        # A season with no rows would trivially have no duplicates, so require rows too.
        passed=total_rows > 0 and duplicate_rows == 0,
        metadata={"season": season, "total_rows": total_rows, "duplicate_rows": duplicate_rows},
    )


@dg.asset_check(asset=raw_schedules, partitions_def=season_partitions, blocking=True)
def raw_schedules_scores_present(
    context: dg.AssetCheckExecutionContext, snowflake: SnowflakeResource
) -> dg.AssetCheckResult:
    """home_score and away_score are both set (game played) or both null (not played yet)."""
    season = int(context.partition_key)
    with snowflake.get_connection() as conn:
        games, played, unplayed, mismatched = conn.cursor().execute(
            """
            select
                count(*),
                count_if(home_score is not null and away_score is not null),
                count_if(home_score is null and away_score is null),
                count_if((home_score is null) <> (away_score is null))
            from RAW.SCHEDULES
            where season = %s
            """,
            (season,),
        ).fetchone()
    return dg.AssetCheckResult(
        passed=games > 0 and mismatched == 0,
        metadata={
            "season": season,
            "games": games,
            "played": played,
            "unplayed": unplayed,
            "mismatched": mismatched,
        },
    )
