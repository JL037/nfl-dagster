-- Weekly injury reports (nflverse, 2009 on), one row per player, team and week: the game status
-- the team listed (Out, Doubtful, Questionable, ...) and the practice status. Players on injured
-- reserve aren't on these reports, so counting reports undercounts games missed.
-- Team codes become play-by-play's (OAK -> LV, SD -> LAC, STL -> LA); whitespace-only values
-- (some practice statuses) become null.
select
    gsis_id || '-' || team_code || '-' || season || '-' || week || '-' || game_type as injury_report_key,
    season,
    season_type,
    game_type,
    week,
    team_code as team,
    gsis_id as player_id,
    full_name as player_name,
    position,
    nullif(trim(report_status), '') as game_status,
    nullif(trim(report_primary_injury), '') as injury,
    nullif(trim(report_secondary_injury), '') as secondary_injury,
    nullif(trim(practice_status), '') as practice_status,
    nullif(trim(practice_primary_injury), '') as practice_injury
from (
    select
        *,
        case team when 'OAK' then 'LV' when 'SD' then 'LAC' when 'STL' then 'LA' else team end as team_code
    from {{ source('raw', 'injuries') }}
)
