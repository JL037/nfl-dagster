-- One row per player, game and role, regular season only: the per-game building block for
-- player_season_efficiency's consistency numbers. Not published (about 200K rows).
-- - passer: every dropback (passes, sacks, scrambles), as in qb_season_epa.
-- - rusher: designed runs only (rush_attempt = 1, qb_scramble = 0); scrambles stay with the
--   passer, so a QB's scramble isn't counted twice.
-- - receiver: pass attempts with a target (sacks have none). The whole play's EPA goes to the
--   target, as nflverse credits it; yards count only on completions.
with plays as (
    select season, week, game_id, posteam as team, 'passer' as role, passer_id as player_id,
        epa, success, yards_gained as yards, complete_pass as completion, pass_touchdown as touchdown,
        interception
    from {{ ref('stg_pbp') }}
    where season_type = 'REG' and qb_dropback = 1 and passer_id is not null

    union all

    select season, week, game_id, posteam, 'rusher', rusher_id,
        epa, success, yards_gained, 0, rush_touchdown, 0
    from {{ ref('stg_pbp') }}
    where season_type = 'REG' and rush_attempt = 1 and qb_scramble = 0 and rusher_id is not null

    union all

    select season, week, game_id, posteam, 'receiver', receiver_id,
        epa, success, iff(complete_pass = 1, yards_gained, 0), complete_pass, pass_touchdown, interception
    from {{ ref('stg_pbp') }}
    where season_type = 'REG' and pass_attempt = 1 and sack = 0 and receiver_id is not null
)

select
    player_id || '-' || game_id || '-' || role as player_game_role_key,
    season,
    week,
    game_id,
    role,
    player_id,
    -- A player is on one team within a game.
    any_value(team) as team,
    count(*) as plays,
    sum(epa) as epa,
    sum(success) as successes,
    sum(yards) as yards,
    sum(completion) as completions,
    sum(touchdown) as touchdowns,
    sum(interception) as interceptions
from plays
group by season, week, game_id, role, player_id
