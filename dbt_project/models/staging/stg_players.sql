-- Player lookup: the full name for each gsis_id (play-by-play's passer_id), which
-- play-by-play itself only gives by initial ("J.Love").
select
    gsis_id as player_id,
    display_name as player_name,
    position
from {{ source('raw', 'players') }}
