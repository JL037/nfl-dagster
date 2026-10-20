-- Season box-score totals per team and season type (REG = regular season, POST = playoffs):
-- yards, touchdowns, turnovers, sacks and penalties, for questions team_season_epa's
-- efficiency numbers don't answer ("who threw the most interceptions in 2010?").
select
    s.team || '-' || s.season || '-' || s.season_type as team_season_type_key,
    s.season,
    s.season_type,
    s.team,
    teams.team_name,
    count(*) as games,
    sum(s.completions) as completions,
    sum(s.attempts) as pass_attempts,
    sum(s.passing_yards) as passing_yards,
    sum(s.passing_tds) as passing_tds,
    sum(s.passing_interceptions) as interceptions_thrown,
    sum(s.sacks_suffered) as sacks_taken,
    sum(s.carries) as carries,
    sum(s.rushing_yards) as rushing_yards,
    sum(s.rushing_tds) as rushing_tds,
    sum(s.fumbles_lost) as fumbles_lost,
    sum(s.passing_interceptions) + sum(s.fumbles_lost) as turnovers,
    sum(s.def_sacks) as sacks,
    sum(s.def_interceptions) as interceptions,
    sum(s.def_fumbles_forced) as forced_fumbles,
    sum(s.def_tds) as defensive_tds,
    sum(s.penalties) as penalties,
    sum(s.penalty_yards) as penalty_yards,
    sum(s.fg_made) as fg_made,
    sum(s.fg_att) as fg_attempts
from {{ ref('stg_team_stats') }} as s
left join {{ ref('stg_teams') }} as teams on teams.team_abbr = s.team
group by s.team, s.season, s.season_type, teams.team_name
