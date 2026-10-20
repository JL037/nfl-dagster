-- Offensive line results per team and regular season, from play-by-play, with the line's
-- personnel from the roster. These are unit results: they also reflect the QB (sacks), the
-- running back and the scheme, and there are no individual lineman grades in this data.
-- Pass protection, per dropback: sack_rate = sacks / dropbacks; qb_hit_rate = plays where the
-- QB was hit / dropbacks.
-- Run blocking, designed runs only (no scrambles): rush EPA per play, success rate, yards per
-- carry, stuff_rate = share of runs for 0 yards or fewer, explosive_run_rate = share of 10+.
-- By direction: left, middle and right runs (run_location).
-- Personnel: active (ACT) offensive linemen on the season roster, their average years of
-- experience and age.
with plays as (
    select * from {{ ref('stg_pbp') }} where season_type = 'REG'
),

pass_pro as (
    select season, posteam as team,
        count(*) as dropbacks, sum(sack) as sacks, sum(qb_hit) as qb_hits
    from plays
    where qb_dropback = 1
    group by season, posteam
),

runs as (
    select season, posteam as team,
        count(*) as designed_rushes,
        avg(epa) as rush_epa_per_play,
        avg(success) as rush_success_rate,
        avg(yards_gained) as yards_per_carry,
        avg(iff(yards_gained <= 0, 1, 0)) as stuff_rate,
        avg(iff(yards_gained >= 10, 1, 0)) as explosive_run_rate,
        count_if(run_location = 'left') as left_rushes,
        avg(iff(run_location = 'left', success, null)) as left_success_rate,
        avg(iff(run_location = 'left', yards_gained, null)) as left_yards_per_carry,
        count_if(run_location = 'middle') as middle_rushes,
        avg(iff(run_location = 'middle', success, null)) as middle_success_rate,
        avg(iff(run_location = 'middle', yards_gained, null)) as middle_yards_per_carry,
        count_if(run_location = 'right') as right_rushes,
        avg(iff(run_location = 'right', success, null)) as right_success_rate,
        avg(iff(run_location = 'right', yards_gained, null)) as right_yards_per_carry
    from plays
    where rush_attempt = 1 and qb_scramble = 0
    group by season, posteam
),

line as (
    select season, team,
        count(*) as ol_players,
        avg(years_exp) as ol_avg_years_exp,
        avg(age) as ol_avg_age
    from {{ ref('stg_rosters') }}
    where position = 'OL' and status = 'ACT'
    group by season, team
)

select
    pass_pro.team || '-' || pass_pro.season as team_season_key,
    pass_pro.season,
    pass_pro.team,
    teams.team_name,
    pass_pro.dropbacks,
    pass_pro.sacks,
    pass_pro.sacks / pass_pro.dropbacks as sack_rate,
    pass_pro.qb_hits,
    pass_pro.qb_hits / pass_pro.dropbacks as qb_hit_rate,
    runs.designed_rushes,
    runs.rush_epa_per_play,
    runs.rush_success_rate,
    runs.yards_per_carry,
    runs.stuff_rate,
    runs.explosive_run_rate,
    runs.left_rushes,
    runs.left_success_rate,
    runs.left_yards_per_carry,
    runs.middle_rushes,
    runs.middle_success_rate,
    runs.middle_yards_per_carry,
    runs.right_rushes,
    runs.right_success_rate,
    runs.right_yards_per_carry,
    line.ol_players,
    line.ol_avg_years_exp,
    line.ol_avg_age
from pass_pro
left join runs using (season, team)
left join line using (season, team)
left join {{ ref('stg_teams') }} as teams on teams.team_abbr = pass_pro.team
