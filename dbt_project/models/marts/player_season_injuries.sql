-- Per player, team and regular season (2009 on): how many weekly injury reports listed him and
-- with what game status, and the injury listed most often. Players on injured reserve aren't on
-- the reports, so weeks_out undercounts games missed (a season on IR shows few or no weeks).
with weeks as (
    select *
    from {{ ref('stg_injuries') }}
    where season_type = 'REG'
),

main_injury as (
    select player_id, team, season, injury
    from weeks
    where injury is not null
    group by player_id, team, season, injury
    qualify row_number() over (partition by player_id, team, season order by count(*) desc, injury) = 1
)

select
    weeks.player_id || '-' || weeks.team || '-' || weeks.season as player_team_season_key,
    weeks.season,
    weeks.team,
    weeks.player_id,
    any_value(weeks.player_name) as player_name,
    any_value(weeks.position) as position,
    count(*) as weeks_listed,
    count_if(weeks.game_status = 'Out') as weeks_out,
    count_if(weeks.game_status = 'Doubtful') as weeks_doubtful,
    count_if(weeks.game_status = 'Questionable') as weeks_questionable,
    any_value(main_injury.injury) as most_listed_injury
from weeks
left join main_injury using (player_id, team, season)
group by weeks.player_id, weeks.team, weeks.season
