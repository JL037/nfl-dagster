-- The leaders per team, season and role from player_season_efficiency (so the same volume
-- minimums apply): the most efficient player (highest epa_per_play) and the most consistent
-- (highest positive_game_share, ties broken by the lower game_epa_per_play_sd, then volume).
with efficient as (
    select season, team, role, player_id, player_name, epa_per_play
    from {{ ref('player_season_efficiency') }}
    qualify row_number() over (partition by season, team, role order by epa_per_play desc, plays desc) = 1
),

consistent as (
    select season, team, role, player_id, player_name, positive_game_share, game_epa_per_play_sd
    from {{ ref('player_season_efficiency') }}
    where positive_game_share is not null
    qualify row_number() over (
        partition by season, team, role
        order by positive_game_share desc, game_epa_per_play_sd asc nulls last, plays desc
    ) = 1
)

select
    efficient.team || '-' || efficient.season || '-' || efficient.role as team_season_role_key,
    efficient.season,
    efficient.team,
    efficient.role,
    efficient.player_id as most_efficient_player_id,
    efficient.player_name as most_efficient_player_name,
    efficient.epa_per_play as most_efficient_epa_per_play,
    consistent.player_id as most_consistent_player_id,
    consistent.player_name as most_consistent_player_name,
    consistent.positive_game_share as most_consistent_positive_game_share,
    consistent.game_epa_per_play_sd as most_consistent_game_epa_per_play_sd
from efficient
left join consistent using (season, team, role)
