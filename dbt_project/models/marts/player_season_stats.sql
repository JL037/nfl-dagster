-- Season box-score totals per player and season type (REG = regular season, POST = playoffs):
-- the official-style counting stats (yards, touchdowns, tackles, sacks, field goals) that
-- play-by-play efficiency (player_season_efficiency) doesn't give. One row per player, season
-- and season type; team is the one he played the most games for (mid-season trades).
with main_team as (
    select player_id, season, season_type, team
    from {{ ref('stg_player_stats') }}
    group by player_id, season, season_type, team
    qualify row_number() over (partition by player_id, season, season_type order by count(*) desc, team) = 1
)

select
    s.player_id || '-' || s.season || '-' || s.season_type as player_season_type_key,
    s.season,
    s.season_type,
    s.player_id,
    any_value(s.player_name) as player_name,
    any_value(s.position) as position,
    any_value(s.position_group) as position_group,
    main_team.team,
    count(*) as games,
    sum(s.completions) as completions,
    sum(s.attempts) as pass_attempts,
    sum(s.passing_yards) as passing_yards,
    sum(s.passing_tds) as passing_tds,
    sum(s.passing_interceptions) as interceptions_thrown,
    sum(s.sacks_suffered) as sacks_taken,
    sum(s.completions) / nullif(sum(s.attempts), 0) as completion_rate,
    sum(s.carries) as carries,
    sum(s.rushing_yards) as rushing_yards,
    sum(s.rushing_tds) as rushing_tds,
    sum(s.rushing_yards) / nullif(sum(s.carries), 0) as yards_per_carry,
    sum(s.receptions) as receptions,
    sum(s.targets) as targets,
    sum(s.receiving_yards) as receiving_yards,
    sum(s.receiving_tds) as receiving_tds,
    sum(s.receiving_yards) / nullif(sum(s.receptions), 0) as yards_per_reception,
    sum(s.fumbles_lost) as fumbles_lost,
    sum(s.def_tackles_solo) + sum(s.def_tackle_assists) as tackles,
    sum(s.def_tackles_for_loss) as tackles_for_loss,
    sum(s.def_sacks) as sacks,
    sum(s.def_qb_hits) as qb_hits,
    sum(s.def_interceptions) as interceptions,
    sum(s.def_pass_defended) as passes_defended,
    sum(s.def_fumbles_forced) as forced_fumbles,
    sum(s.def_tds) as defensive_tds,
    sum(s.fg_made) as fg_made,
    sum(s.fg_att) as fg_attempts,
    max(s.fg_long) as fg_long,
    sum(s.pat_made) as pat_made,
    sum(s.pat_att) as pat_attempts,
    sum(s.special_teams_tds) as special_teams_tds
from {{ ref('stg_player_stats') }} as s
inner join main_team using (player_id, season, season_type)
group by s.player_id, s.season, s.season_type, main_team.team
