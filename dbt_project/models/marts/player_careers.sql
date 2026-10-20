-- One row per player and role (passer, rusher, receiver) over every regular season in the data
-- (1999 on), for comparing players across eras:
-- - Totals (games, plays, yards, touchdowns) count every play, qualifying season or not.
-- - epa_per_play_over_league: the career's EPA per play minus what the league averaged on the
--   same number of plays in the same seasons (each season's average weighted by his plays that
--   season), so a long career in a low-scoring era isn't penalized for the era.
-- - yards_per_play_index: his yards per play against the league's, weighted the same way. 100 =
--   average.
-- - Peak, from player_season_vs_league (qualifying seasons only): best_season by
--   epa_per_play_over_league, and top_5_seasons = seasons ranked in the league's top 5.
-- - is_partial_career: his NFL career started before the data does (rookie_year from rosters
--   is earlier than the first season in play-by-play, 1999): Emmitt Smith's 1990-1998 aren't
--   in it. Answers about such a player must say only part of his career is covered. (Not his
--   own first season here: a backup who arrived in 2005 and first threw in 2007 is complete.)
with league as (
    select season, role, sum(epa) / sum(plays) as epa_per_play, sum(yards) / sum(plays) as yards_per_play
    from {{ ref('int_player_games') }}
    group by season, role
),

seasons as (
    select
        g.player_id,
        g.role,
        g.season,
        count(*) as games,
        sum(g.plays) as plays,
        sum(g.epa) as epa,
        sum(g.yards) as yards,
        sum(g.touchdowns) as touchdowns,
        sum(g.plays) * any_value(league.epa_per_play) as league_epa,
        sum(g.plays) * any_value(league.yards_per_play) as league_yards
    from {{ ref('int_player_games') }} as g
    inner join league using (season, role)
    group by g.player_id, g.role, g.season
),

careers as (
    select
        player_id,
        role,
        min(season) as first_season,
        max(season) as last_season,
        count(*) as seasons,
        sum(games) as games,
        sum(plays) as plays,
        sum(yards) as yards,
        sum(touchdowns) as touchdowns,
        sum(epa) / sum(plays) as epa_per_play,
        (sum(epa) - sum(league_epa)) / sum(plays) as epa_per_play_over_league,
        sum(yards) / sum(plays) as yards_per_play,
        100 * sum(yards) / nullif(sum(league_yards), 0) as yards_per_play_index
    from seasons
    group by player_id, role
),

peaks as (
    select
        player_id,
        role,
        count(*) as qualifying_seasons,
        count_if(season_rank <= 5) as top_5_seasons,
        max_by(season, epa_per_play_over_league) as best_season,
        max(epa_per_play_over_league) as best_season_epa_per_play_over_league
    from {{ ref('player_season_vs_league') }}
    group by player_id, role
),

rookies as (
    select player_id, min(rookie_year) as rookie_year
    from {{ ref('stg_rosters') }}
    group by player_id
)

select
    careers.player_id || '-' || careers.role as player_role_key,
    careers.player_id,
    coalesce(players.player_name, careers.player_id) as player_name,
    players.position,
    careers.role,
    careers.first_season,
    careers.last_season,
    rookies.rookie_year,
    coalesce(rookies.rookie_year < (select min(season) from league), false) as is_partial_career,
    careers.seasons,
    careers.games,
    careers.plays,
    careers.yards,
    careers.touchdowns,
    careers.epa_per_play,
    careers.epa_per_play_over_league,
    careers.yards_per_play,
    careers.yards_per_play_index,
    coalesce(peaks.qualifying_seasons, 0) as qualifying_seasons,
    coalesce(peaks.top_5_seasons, 0) as top_5_seasons,
    peaks.best_season,
    peaks.best_season_epa_per_play_over_league
from careers
left join peaks using (player_id, role)
left join rookies using (player_id)
left join {{ ref('stg_players') }} as players on players.player_id = careers.player_id
