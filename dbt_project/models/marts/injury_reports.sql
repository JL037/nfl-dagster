-- Every weekly injury report, 2009 on: one row per player, team and week, with the game status
-- the team listed (Out, Doubtful, Questionable, Probable before 2016, Note) and the practice
-- status. Players on injured reserve aren't listed, so these reports undercount games missed.
select
    reports.injury_report_key,
    reports.season,
    reports.season_type,
    reports.game_type,
    reports.week,
    reports.team,
    teams.team_name,
    reports.player_id,
    reports.player_name,
    reports.position,
    reports.game_status,
    reports.injury,
    reports.secondary_injury,
    reports.practice_status
from {{ ref('stg_injuries') }} as reports
left join {{ ref('stg_teams') }} as teams on teams.team_abbr = reports.team
