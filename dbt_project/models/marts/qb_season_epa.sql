-- QB efficiency per season on dropbacks (passes, sacks, and scrambles), regular season only.
-- Grouped by passer_id, not name: abbreviated names like "J.Daniels" belong to several players.
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
    sum(qb_scramble) as scrambles
from {{ ref('stg_pbp') }}
where qb_dropback = 1
    and season_type = 'REG'
    and passer_id is not null
group by season, passer_id
-- Leave out backups and spot starters, whose small samples swing wildly.
having count(*) >= 200
