-- Season rosters: one row per player, team and season (2015 on), for questions like "how has
-- this roster changed since 2018?" (join two seasons on player_id) or "how experienced is
-- this offensive line?". Everyone nflverse lists for the team that season: status says who was
-- on the active roster (ACT) and who was reserve, injured, practice squad and so on.
select
    roster_key,
    season,
    team,
    player_id,
    player_name,
    position,
    position_spot,
    jersey_number,
    status,
    years_exp,
    age,
    height,
    weight,
    college,
    draft_club,
    draft_number,
    rookie_year
from {{ ref('stg_rosters') }}
