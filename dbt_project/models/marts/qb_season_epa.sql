-- QB efficiency per season on dropbacks (passes, sacks, and scrambles), regular season only.
-- Grouped by passer_id, not name: abbreviated names like "J.Daniels" belong to several players.
with season_progress as (
    -- Share of each season's regular-season games already played: 1.0 for a finished season.
    select
        season,
        count_if(is_played) / count(*) as season_progress
    from {{ ref('stg_schedules') }}
    where game_type = 'REG'
    group by season
)

select
    passer_id || '-' || season as qb_season_key,
    season,
    passer_id,
    -- A passer_id always has one name; any_value just picks it.
    any_value(passer_name) as passer_name,
    -- The team with the most of this QB's dropbacks (matters for mid-season trades).
    mode(posteam) as team,
    count(*) as dropbacks,
    avg(epa) as epa_per_dropback,
    avg(success) as success_rate,
    sum(qb_scramble) as scrambles,
    any_value(season_progress.season_progress) as season_progress,
    any_value(season_progress.season_progress) = 1 as is_season_complete
from {{ ref('stg_pbp') }}
inner join season_progress using (season)
where qb_dropback = 1
    and season_type = 'REG'
    and passer_id is not null
group by season, passer_id
-- Leave out backups and spot starters, whose small samples swing wildly: 200 dropbacks in a
-- finished season, pro-rated while a season is in progress (58 when 29% of games are played).
-- A flat 200 let only the 8 highest-volume QBs into 2026 after five weeks, while 34 had
-- played substantially. Finished seasons are unchanged.
having count(*) >= 200 * any_value(season_progress.season_progress)
