-- Played games compared against the betting spread ("against the spread", ATS).
-- spread_line is how many points the home team was favored by, and result is home minus away,
-- so the home team covers when it wins by more than the spread: result > spread_line.
--
-- A game with no spread_line has no ATS result. Both comparisons below are then NULL (not
-- true, not false), so without the first WHEN the CASE would fall through to ELSE and call
-- the game a push. Pushes are rare (about 2.6% of games), so a few mislabeled games would
-- noticeably inflate the push rate, and nothing would fail: 'push' is an accepted value.
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
        when spread_line is null then null
        when result > spread_line then home_team
        when result < spread_line then away_team
        else 'PUSH'
    end as ats_winner,
    case
        when spread_line is null then null
        when result > spread_line then 'home'
        when result < spread_line then 'away'
        else 'push'
    end as ats_result
from {{ ref('stg_schedules') }}
where is_played
