import dagster as dg
import nflreadpy as nfl

# nflverse play-by-play (with EPA and win probability) starts in 1999, and so does this.
# Seasons load one partition at a time, each replacing only its own rows (load_parquet), so
# adding earlier seasons never touches the ones already loaded.
FIRST_SEASON = 1999
CURRENT_SEASON = nfl.get_current_season()

season_partitions = dg.StaticPartitionsDefinition(
    [str(season) for season in range(FIRST_SEASON, CURRENT_SEASON + 1)]
)
