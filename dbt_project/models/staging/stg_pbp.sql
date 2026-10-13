-- Real offensive plays only: passes (including sacks and scrambles) and runs.
-- Drops kickoffs, punts, kicks, kneels, spikes, and no_play rows (penalties that wiped out a play).
select
    -- play_id is only unique within a game, so build one key for the whole table.
    game_id || '-' || cast(play_id as integer) as play_key,
    game_id,
    cast(play_id as integer) as play_id,
    season,
    cast(week as integer) as week,
    season_type,
    posteam,
    defteam,
    play_type,
    epa,
    -- nflverse stores flags as 1.0 / 0.0; integers make averages read as rates.
    cast(success as integer) as success,
    wp,
    cast(qb_dropback as integer) as qb_dropback,
    cast(qb_scramble as integer) as qb_scramble,
    -- passer / passer_id include scrambles; passer_player_name does not.
    passer_id,
    passer as passer_name
from {{ source('raw', 'pbp') }}
where play_type in ('pass', 'run')
