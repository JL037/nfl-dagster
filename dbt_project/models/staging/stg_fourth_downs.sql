-- One row per fourth-down decision: the offense went for it (pass or run) or kicked
-- (punt or field goal). Kept separate from stg_pbp, which holds only pass and run plays,
-- because a go-for-it rate needs the kicks too, and widening stg_pbp would change
-- every mart built on it.
--
-- Left out: no_play (a penalty wiped the play out, so the decision never played out),
-- qb_kneel and qb_spike (clock management, not a decision). Fake punts and fake field
-- goals are logged as pass or run, so they count as going for it.
select
    -- play_id is only unique within a game, so build one key for the whole table.
    game_id || '-' || cast(play_id as integer) as play_key,
    game_id,
    season,
    cast(week as integer) as week,
    season_type,
    posteam,
    defteam,
    play_type,
    play_type in ('pass', 'run') as went_for_it,
    cast(ydstogo as integer) as ydstogo,
    -- Distance from the opponent's end zone: 1 means at their 1-yard line.
    cast(yardline_100 as integer) as yardline_100,
    -- The offense's win probability before the snap.
    wp,
    -- Both are 1/0 flags, and null when the team kicked.
    cast(fourth_down_converted as integer) as fourth_down_converted,
    cast(fourth_down_failed as integer) as fourth_down_failed
from {{ source('raw', 'pbp') }}
where down = 4
    and play_type in ('pass', 'run', 'punt', 'field_goal')
