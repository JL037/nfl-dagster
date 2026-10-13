-- One row per game, with results and betting lines. Unplayed games have null scores.
select
    game_id,
    season,
    game_type,
    week,
    cast(gameday as date) as gameday,
    away_team,
    away_score,
    home_team,
    home_score,
    -- result = home_score - away_score
    result,
    total,
    overtime,
    -- spread_line = points the home team is favored by (negative when the away team is favored)
    spread_line,
    total_line,
    home_score is not null as is_played
from {{ source('raw', 'schedules') }}
