-- Played games compared against the betting spread ("against the spread", ATS).
-- spread_line is how many points the home team was favored by, and result is home minus away,
-- so the home team covers when it wins by more than the spread: result > spread_line.
select
    game_id,
    season,
    game_type,
    week,
    gameday,
    away_team,
    away_score,
    home_team,
    home_score,
    result,
    spread_line,
    -- How far the home team beat (+) or fell short of (-) the spread.
    result - spread_line as home_cover_margin,
    case
        when result > spread_line then home_team
        when result < spread_line then away_team
        else 'PUSH'
    end as ats_winner,
    case
        when result > spread_line then 'home'
        when result < spread_line then 'away'
        else 'push'
    end as ats_result
from {{ ref('stg_schedules') }}
where is_played
