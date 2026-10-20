-- Each qualifying player season (player_season_efficiency's minimums) next to that season's
-- league average for the same role, so seasons from different eras can be compared: a rushing
-- season is measured against the league's rushing that year, not against today's.
-- League average = every regular-season play in that role that season, all players included
-- (int_player_games), not just the qualifiers.
-- - epa_per_play_over_league: EPA per play minus the league's. 0 = average for the season.
-- - success_rate_over_league: the same for success rate.
-- - yards_per_play_index: yards per play as a share of the league's, x100. 100 = average,
--   120 = 20% more yards per play than the league that season.
-- - season_rank: by epa_per_play among that season's qualifiers in the role (1 = best), out of
--   qualifiers.
with league as (
    select
        season,
        role,
        sum(epa) / sum(plays) as league_epa_per_play,
        sum(successes) / sum(plays) as league_success_rate,
        sum(yards) / sum(plays) as league_yards_per_play
    from {{ ref('int_player_games') }}
    group by season, role
)

select
    players.player_season_role_key,
    players.season,
    players.player_id,
    players.player_name,
    players.position,
    players.team,
    players.role,
    players.games,
    players.plays,
    players.yards,
    players.touchdowns,
    players.epa_per_play,
    league.league_epa_per_play,
    players.epa_per_play - league.league_epa_per_play as epa_per_play_over_league,
    players.success_rate,
    league.league_success_rate,
    players.success_rate - league.league_success_rate as success_rate_over_league,
    players.yards_per_play,
    league.league_yards_per_play,
    100 * players.yards_per_play / nullif(league.league_yards_per_play, 0) as yards_per_play_index,
    rank() over (partition by players.season, players.role order by players.epa_per_play desc) as season_rank,
    count(*) over (partition by players.season, players.role) as qualifiers,
    players.is_season_complete
from {{ ref('player_season_efficiency') }} as players
inner join league using (season, role)
