-- stg_cap_hits keeps one contract row per player before flattening season_history. That's
-- only safe while every contract row for a player carries the same list (true today for all
-- 8,118 players with more than one row). This checks the outcome instead of the assumption:
-- flattening every contract row, then removing repeats, must give exactly the player-seasons
-- that stg_cap_hits has. Any row returned is a season lost (or invented) by the dedupe.
--
-- It reads both the source and the model, so dagster-dbt needs to be told which asset the
-- check belongs to: the ref puts it on stg_cap_hits.
{{ config(meta={'dagster': {'ref': {'name': 'stg_cap_hits'}}}) }}

with every_contract_row as (
    select distinct contracts.otc_id, season.value:year::string as season
    from {{ source('raw', 'contracts') }} as contracts,
        lateral flatten(input => contracts.season_history) as season
    where season.value:year::string regexp '[0-9]{4}'
),

cap_hits as (
    select otc_id, to_varchar(season) as season
    from {{ ref('stg_cap_hits') }}
)

(select 'missing from stg_cap_hits' as problem, * from every_contract_row
 except
 select 'missing from stg_cap_hits', * from cap_hits)
union all
(select 'not in raw.contracts', * from cap_hits
 except
 select 'not in raw.contracts', * from every_contract_row)
