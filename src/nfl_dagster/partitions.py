import dagster as dg
import nflreadpy as nfl

# nflverse play-by-play goes back to 1999; start smaller so first backfills are quick.
FIRST_SEASON = 2015
CURRENT_SEASON = nfl.get_current_season()

season_partitions = dg.StaticPartitionsDefinition(
    [str(season) for season in range(FIRST_SEASON, CURRENT_SEASON + 1)]
)
