-- Efficiency and consistency per player, season and role, regular season only.
-- Roles: passer (every dropback, scrambles included), rusher (designed runs only), receiver
-- (targets). A QB who runs designed runs has a passer row and a rusher row.
-- Efficiency: epa_per_play = EPA per dropback, per rush or per target; success_rate is the
-- share of those plays nflverse counts as successful; yards_per_play the same way.
-- Consistency is measured over qualifying games (at least 10 dropbacks, 5 rushes or 3 targets
-- in the game): positive_game_share = share of those games with positive total EPA;
-- game_epa_per_play_sd = the standard deviation of EPA per play across them (lower = steadier).
-- "Most consistent" = highest positive_game_share, ties broken by the lower sd.
-- Volume minimum per full season: 200 dropbacks, 150 rushes, 50 targets, pro-rated while a
-- season is in progress (is_season_complete = false: treat as estimates).
with season_progress as (
    select season, count_if(is_played) / count(*) as season_progress
    from {{ ref('stg_schedules') }}
    where game_type = 'REG'
    group by season
),

minimums as (
    select 'passer' as role, 200 as min_plays, 10 as min_game_plays
    union all select 'rusher', 150, 5
    union all select 'receiver', 50, 3
),

games as (
    select g.*, m.min_plays, m.min_game_plays, g.plays >= m.min_game_plays as is_qualifying
    from {{ ref('int_player_games') }} as g
    inner join minimums as m using (role)
),

main_team as (
    -- The team he made the most plays for in this role (matters for mid-season trades).
    select player_id, season, role, team
    from games
    group by player_id, season, role, team
    qualify row_number() over (partition by player_id, season, role order by sum(plays) desc, team) = 1
),

seasons as (
    select
        player_id,
        season,
        role,
        any_value(min_plays) as min_plays,
        count(*) as games,
        sum(plays) as plays,
        sum(epa) as epa,
        sum(successes) as successes,
        sum(yards) as yards,
        sum(completions) as completions,
        sum(touchdowns) as touchdowns,
        sum(interceptions) as interceptions,
        count_if(is_qualifying) as qualifying_games,
        avg(iff(is_qualifying, iff(epa > 0, 1, 0), null)) as positive_game_share,
        stddev_samp(iff(is_qualifying, epa / plays, null)) as game_epa_per_play_sd
    from games
    group by player_id, season, role
)

select
    seasons.player_id || '-' || seasons.season || '-' || seasons.role as player_season_role_key,
    seasons.season,
    seasons.player_id,
    coalesce(players.player_name, seasons.player_id) as player_name,
    players.position,
    main_team.team,
    seasons.role,
    seasons.games,
    seasons.plays,
    seasons.epa / seasons.plays as epa_per_play,
    seasons.successes / seasons.plays as success_rate,
    seasons.yards,
    seasons.yards / seasons.plays as yards_per_play,
    seasons.touchdowns,
    seasons.completions,
    iff(seasons.role = 'rusher', null, seasons.completions / seasons.plays) as completion_rate,
    iff(seasons.role = 'rusher', null, seasons.interceptions) as interceptions,
    seasons.qualifying_games,
    seasons.positive_game_share,
    seasons.game_epa_per_play_sd,
    progress.season_progress = 1 as is_season_complete
from seasons
inner join season_progress as progress using (season)
inner join main_team using (player_id, season, role)
left join {{ ref('stg_players') }} as players on players.player_id = seasons.player_id
where seasons.plays >= seasons.min_plays * progress.season_progress * {{ var('player_min_plays_scale', 1) }}
