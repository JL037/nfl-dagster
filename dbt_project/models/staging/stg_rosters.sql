-- Season rosters: one row per player, team and season (nflverse, 2015 on). Rows without a
-- gsis_id (a handful) are left out: they can't join to play-by-play or the player table.
-- Normalized so every season reads the same way:
-- - team: play-by-play's codes, the same across a relocation (OAK -> LV, SD -> LAC, STL/SL ->
--   LA), and 2015's old codes (ARZ, BLT, CLV, HST) mapped to today's.
-- - position: the group (OL, DL, LB, DB, RB, ...); 2015 lists specific spots (T, G, CB), which
--   stay in position_spot.
with rosters as (
    select
        *,
        case team
            when 'ARZ' then 'ARI' when 'BLT' then 'BAL' when 'CLV' then 'CLE' when 'HST' then 'HOU'
            when 'SL' then 'LA' when 'STL' then 'LA' when 'OAK' then 'LV' when 'SD' then 'LAC'
            else team
        end as team_code
    from {{ source('raw', 'rosters') }}
    where gsis_id is not null
)

select
    gsis_id || '-' || team_code || '-' || season as roster_key,
    season,
    team_code as team,
    gsis_id as player_id,
    full_name as player_name,
    -- The position group (QB, RB, WR, TE, OL, DL, LB, DB, K, P, LS).
    case
        when position in ('T', 'G', 'C', 'OT', 'OG') then 'OL'
        when position in ('DE', 'DT', 'NT') then 'DL'
        when position in ('OLB', 'ILB', 'MLB') then 'LB'
        when position in ('CB', 'SS', 'FS', 'S', 'SAF') then 'DB'
        when position = 'FB' then 'RB'
        else position
    end as position,
    -- The specific spot: T, G or C for offensive linemen, and so on.
    coalesce(depth_chart_position, position) as position_spot,
    jersey_number,
    -- ACT = on the active roster; others are reserve, injured, practice squad and similar.
    status,
    years_exp,
    try_to_date(birth_date::varchar) as birth_date,
    -- Age on September 1 of the season, in whole years.
    floor(datediff('day', try_to_date(birth_date::varchar), date_from_parts(season, 9, 1)) / 365.25) as age,
    height,
    weight,
    college,
    draft_club,
    draft_number,
    rookie_year,
    entry_year
from rosters
