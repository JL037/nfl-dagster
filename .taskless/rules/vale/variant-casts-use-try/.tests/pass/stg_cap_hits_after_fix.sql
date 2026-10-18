-- From stg_cap_hits after the fix, and from stg_pbp: casts that can't fail on a bad VARIANT
-- value, and ordinary casts of typed columns.
select
    players.otc_id || '-' || season.value:year::string as player_season_key,
    -- try_to_number, not ::int: Snowflake may cast before applying the WHERE below.
    try_to_number(season.value:year::string) as season,
    nullif(season.value:team::string, '') as team_name,
    try_to_double(season.value:cap_number::string) as cap_number,
    cast(play_id as integer) as play_id,
    cast(week as integer) as week,
    play_id::int as play_id_int
from players,
    lateral flatten(input => players.season_history) as season
where season.value:year::string regexp '[0-9]{4}'
