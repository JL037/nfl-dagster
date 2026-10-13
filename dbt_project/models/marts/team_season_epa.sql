-- Offense and defense efficiency per team and season, regular season only.
-- Playoffs are left out so every team is measured over the same kind of games: only
-- 12-14 teams play in January, and a deep run would weigh their numbers toward playoff opponents.
with offense as (
    select
        season,
        posteam as team,
        count(*) as off_plays,
        avg(epa) as off_epa_per_play,
        avg(success) as off_success_rate
    from {{ ref('stg_pbp') }}
    where season_type = 'REG'
    group by season, posteam
),

defense as (
    select
        season,
        defteam as team,
        count(*) as def_plays,
        -- EPA allowed: lower is better for a defense.
        avg(epa) as def_epa_per_play,
        avg(success) as def_success_rate
    from {{ ref('stg_pbp') }}
    where season_type = 'REG'
    group by season, defteam
)

select
    offense.team || '-' || offense.season as team_season_key,
    offense.season,
    offense.team,
    teams.team_name,
    teams.team_conf,
    teams.team_division,
    offense.off_plays,
    offense.off_epa_per_play,
    offense.off_success_rate,
    defense.def_plays,
    defense.def_epa_per_play,
    defense.def_success_rate,
    -- Positive means the team gains more expected points per play than it gives up.
    offense.off_epa_per_play - defense.def_epa_per_play as net_epa_per_play
from offense
join defense
    on offense.season = defense.season
    and offense.team = defense.team
left join {{ ref('stg_teams') }} as teams
    on offense.team = teams.team_abbr
